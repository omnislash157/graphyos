#!/usr/bin/env python3
"""march — the board loop. One open issue is armed; the Stop hook refuses to let the session
stop while it is open, and the moment it closes the hook arms the next one, acks `/clear` into
the session's own tmux pane, and kicks the fresh context every two minutes until it acks back.

Verbs (all from the repo root, python3 .claude/hooks/march.py <verb>):
  arm --issue N | --next   arm an issue (the lowest open issue without `blocked`, for --next)
  ack                      the fresh context reports in; the wake loop stops kicking
  status                   the state file, the watcher pid, the live board state of the issue
  next                     print the next open unblocked issue number
  clear                    a batch boundary on purpose: keep the issue, /clear this pane, kick until acked
  disarm                   phase hold; kill the watcher
  stop-hook                Stop hook (stdin = hook JSON): block while open, advance when closed
  inject                   SessionStart hook: print the order for the fresh context
  watch PANE ISSUE         the detached loop (internal)

State lives in .claude/recovery/march.json (gitignored). Every failure is fail-open: a hook
that cannot decide lets the session stop and says why in the systemMessage.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
RECOVERY = ROOT / ".claude" / "recovery"
STATE = RECOVERY / "march.json"
LOG = RECOVERY / "march.log"
TSEND = Path(__file__).resolve().with_name("tsend.sh")
REPO = os.environ.get("MARCH_REPO", "omnislash157/graphyos")

CLEAR_DELAY = float(os.environ.get("MARCH_CLEAR_DELAY", "5"))
CADENCE = float(os.environ.get("MARCH_CADENCE", "120"))
MAX_KICKS = int(os.environ.get("MARCH_MAX_KICKS", "30"))
MAX_BLOCKS = int(os.environ.get("MARCH_MAX_BLOCKS", "4"))
HOLD_TOKEN = "MARCH HOLD"
# the verb is an order only at the start of a line, outside code spans — naming it in prose is not a hold
_HOLD_RE = re.compile(r"^\s*" + re.escape(HOLD_TOKEN) + r"\b", re.MULTILINE)
_CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)


def holds(message: str) -> bool:
    return bool(_HOLD_RE.search(_CODE_RE.sub(" ", message or "")))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(line: str) -> None:
    try:
        RECOVERY.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{now()} [{os.getpid()}] {line}\n")
    except OSError:
        pass


def load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(state: dict) -> None:
    RECOVERY.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, STATE)


def gh(*args: str, timeout: float = 15) -> str:
    out = subprocess.run(["gh", *args, "--repo", REPO], capture_output=True, text=True, timeout=timeout)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or f"gh exited {out.returncode}")
    return out.stdout


def issue_state(n: int) -> str:
    return json.loads(gh("issue", "view", str(n), "--json", "state"))["state"]


def next_issue(exclude: int | None = None) -> int | None:
    rows = json.loads(gh("issue", "list", "--state", "open", "--limit", "200", "--json", "number,labels"))
    candidates = [
        r["number"] for r in rows
        if r["number"] != exclude and not any(l["name"] == "blocked" for l in r.get("labels", []))
    ]
    return min(candidates) if candidates else None


def alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def kill_watcher(state: dict) -> None:
    pid = state.get("watcher_pid")
    if alive(pid):
        try:
            os.kill(pid, 15)
            log(f"watcher {pid} killed")
        except OSError:
            pass
    state.pop("watcher_pid", None)


def pane() -> str | None:
    p = os.environ.get("MARCH_PANE") or os.environ.get("TMUX_PANE")
    return p if p and shutil.which("tmux") else None


def tsend(target: str, msg: str) -> int:
    cmd = f'source "{TSEND}" && tsend "$1" "$2"'
    out = subprocess.run(["bash", "-c", cmd, "_", target, msg], capture_output=True, text=True, timeout=30)
    log(f"tsend {target} rc={out.returncode} {out.stdout.strip()} {out.stderr.strip()}".strip())
    return out.returncode


def spawn_watcher(target: str, issue: int) -> int:
    RECOVERY.mkdir(parents=True, exist_ok=True)
    fh = LOG.open("a", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "watch", target, str(issue)],
        cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=fh, stderr=fh,
        start_new_session=True, close_fds=True,
    )
    return proc.pid


def wake_text(issue: int) -> str:
    return (f"MARCH WAKE — issue {issue} is armed. Read the reseed file named by the SessionStart "
            f"injection, run python3 .claude/hooks/march.py ack, then gh issue view {issue} and march.")


# ── verbs ──────────────────────────────────────────────────────────────────────────────────

def cmd_arm(args: argparse.Namespace) -> int:
    state = load()
    kill_watcher(state)
    issue = args.issue if args.issue else next_issue()
    if issue is None:
        print("march: the board has no open unblocked issue — nothing to arm")
        return 1
    st = issue_state(issue)
    if st != "OPEN":
        print(f"march: issue {issue} is {st}, refusing to arm it")
        return 1
    state = {"issue": issue, "phase": "working", "blocks": 0, "armed_at": now(), "acked_at": now()}
    save(state)
    log(f"armed issue {issue}")
    print(f"march: armed issue {issue} — the session will not stop while it is open")
    return 0


def cmd_ack(_: argparse.Namespace) -> int:
    state = load()
    if not state.get("issue"):
        print("march: nothing armed")
        return 1
    state.update(phase="working", blocks=0, acked_at=now())
    state.pop("session", None)             # the next Stop binds the fresh session
    save(state)
    log(f"acked issue {state['issue']}")
    print(f"march: acked — issue {state['issue']} is the lane; the wake loop stands down")
    return 0


def cmd_clear(_: argparse.Namespace) -> int:
    """A batch boundary on purpose: keep the armed issue, ack /clear into this pane, kick until the fresh context acks."""
    state = load()
    if not state.get("issue"):
        print("march: nothing armed — arm first")
        return 1
    target = pane()
    if not target:
        print("march: not in tmux — press /clear yourself; the injection carries the order")
        return 1
    kill_watcher(state)
    state.update(phase="clearing", blocks=0, cleared_at=now(), pane=target)
    state.pop("session", None)
    state["watcher_pid"] = spawn_watcher(target, int(state["issue"]))
    save(state)
    log(f"clear on purpose: issue {state['issue']} kept; watcher {state['watcher_pid']} on {target}")
    print(f"march: /clear lands in {target} in {CLEAR_DELAY:.0f}s; the wake kicks every {CADENCE:.0f}s until the fresh context acks. Stop talking.")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    state = load()
    if not state:
        print("march: disarmed (no state)")
        return 0
    live = "?"
    try:
        live = issue_state(int(state["issue"]))
    except Exception as exc:  # noqa: BLE001
        live = f"unknown ({exc})"
    print(json.dumps({**state, "issue_live_state": live, "watcher_alive": alive(state.get("watcher_pid")),
                      "pane": pane()}, indent=2))
    return 0


def cmd_next(_: argparse.Namespace) -> int:
    n = next_issue(load().get("issue"))
    print(n if n is not None else "none")
    return 0 if n is not None else 1


def cmd_disarm(_: argparse.Namespace) -> int:
    state = load()
    kill_watcher(state)
    state.update(phase="hold", held_at=now(), held_because="disarm")
    save(state)
    log("disarmed")
    print("march: disarmed (phase hold)")
    return 0


def allow(system_message: str | None = None) -> int:
    if system_message:
        print(json.dumps({"systemMessage": f"march: {system_message}"}))
    return 0


def block(reason: str) -> int:
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


def cmd_stop_hook(_: argparse.Namespace) -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        payload = {}
    state = load()
    if not state.get("issue") or state.get("phase") in (None, "hold"):
        return allow()
    if state.get("phase") == "clearing":
        return allow()                     # the fresh context acks, then its first Stop binds
    issue = int(state["issue"])
    sid = payload.get("session_id")
    bound = state.get("session")
    if sid and not bound:
        state["session"] = sid            # the first Stop after arm binds the loop to this session
        save(state)
    elif sid and bound and sid != bound:
        log(f"stop from foreign session {sid[:8]} on issue {issue}: passing dark")
        return allow()                     # another claude in this repo is not the march
    message = payload.get("last_assistant_message") or ""
    if holds(message):
        kill_watcher(state)
        state.update(phase="hold", held_at=now(), held_because="MARCH HOLD in the closing message")
        save(state)
        log(f"hold on issue {issue}: token")
        return allow(f"issue {issue} held on MARCH HOLD. `march.py arm` re-arms.")
    try:
        live = issue_state(issue)
    except Exception as exc:  # noqa: BLE001
        log(f"gh failed on issue {issue}: {exc}")
        return allow(f"could not read issue {issue} from GitHub ({exc}); letting the session stop")

    if live == "OPEN":
        blocks = int(state.get("blocks", 0)) + 1
        if blocks > MAX_BLOCKS:
            kill_watcher(state)
            state.update(phase="hold", held_at=now(), held_because=f"{blocks - 1} blocks and issue {issue} still open")
            save(state)
            log(f"hold on issue {issue}: block cap")
            return allow(f"issue {issue} is still open after {blocks - 1} continuations; holding. "
                         f"`march.py arm --issue {issue}` re-arms.")
        state["blocks"] = blocks
        save(state)
        log(f"blocked stop on issue {issue} ({blocks}/{MAX_BLOCKS})")
        return block(
            f"MARCH — issue {issue} is still OPEN on the board ({blocks}/{MAX_BLOCKS} continuations). "
            f"The loop does not stop on an open issue. Keep marching: run its done check, land the "
            f"evidence, commit and push, then `gh issue close {issue} --repo {REPO} --comment <evidence>`. "
            f"If it is genuinely blocked on the operator, say `{HOLD_TOKEN}` with the reason in your "
            f"closing message and the loop holds."
        )

    # CLOSED — the condition is met. Advance.
    nxt = next_issue(issue)
    kill_watcher(state)
    if nxt is None:
        state.update(phase="hold", held_at=now(), held_because="board drained", closed=issue)
        save(state)
        log(f"issue {issue} closed; board drained")
        return allow(f"issue {issue} closed and the board has no open unblocked issue. Holding.")
    state = {"issue": nxt, "phase": "clearing", "blocks": 0, "armed_at": now(), "previous": issue}
    target = pane()
    if target:
        state["watcher_pid"] = spawn_watcher(target, nxt)
        state["pane"] = target
        save(state)
        log(f"issue {issue} closed; armed {nxt}; watcher {state['watcher_pid']} on {target}")
        return allow(f"issue {issue} closed. Issue {nxt} armed. `/clear` lands in pane {target} in "
                     f"{CLEAR_DELAY:.0f}s; the wake kicks every {CADENCE:.0f}s until the fresh context acks.")
    save(state)
    log(f"issue {issue} closed; armed {nxt}; no tmux pane — operator ack")
    return allow(f"issue {issue} closed. Issue {nxt} armed. Not in tmux: the ack is yours — press /clear "
                 f"and the injection carries the order.")


def cmd_inject(_: argparse.Namespace) -> int:
    state = load()
    if not state.get("issue") or state.get("phase") in (None, "hold"):
        return 0
    issue = state["issue"]
    print(f"# MARCH — issue {issue} is armed (phase {state.get('phase')})\n")
    print("The board loop is live. FIRST, after the reseed file:\n")
    print("```\npython3 .claude/hooks/march.py ack\n"
          f"gh issue view {issue} --repo {REPO}\n```\n")
    print(f"Then march issue {issue} until its done check holds on a real run: land the evidence, commit, "
          f"push, and `gh issue close {issue} --repo {REPO} --comment <evidence>`. The Stop hook refuses to "
          f"stop while it is open and arms the next issue the moment it closes. `{HOLD_TOKEN}` plus the "
          f"reason in a closing message holds the loop; `python3 .claude/hooks/march.py disarm` does too.")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    target, issue = args.pane, int(args.issue)
    log(f"watcher up for issue {issue} on {target}: clear in {CLEAR_DELAY}s, cadence {CADENCE}s, max {MAX_KICKS}")
    time.sleep(CLEAR_DELAY)
    tsend(target, "/clear")
    for k in range(1, MAX_KICKS + 1):
        time.sleep(CADENCE)
        state = load()
        if state.get("issue") != issue or state.get("phase") != "clearing":
            log(f"watcher done after {k - 1} kicks: phase={state.get('phase')} issue={state.get('issue')}")
            return 0
        tsend(target, wake_text(issue))
        log(f"kick {k}/{MAX_KICKS}")
    state = load()
    if state.get("issue") == issue and state.get("phase") == "clearing":
        state.update(phase="hold", held_at=now(), held_because=f"no ack after {MAX_KICKS} kicks")
        save(state)
    log("watcher gave up — hold")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="march", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="verb", required=True)
    a = sub.add_parser("arm"); a.add_argument("--issue", type=int); a.add_argument("--next", action="store_true")
    a.set_defaults(fn=cmd_arm)
    for name, fn in (("ack", cmd_ack), ("clear", cmd_clear), ("status", cmd_status), ("next", cmd_next), ("disarm", cmd_disarm),
                     ("stop-hook", cmd_stop_hook), ("inject", cmd_inject)):
        sub.add_parser(name).set_defaults(fn=fn)
    w = sub.add_parser("watch"); w.add_argument("pane"); w.add_argument("issue"); w.set_defaults(fn=cmd_watch)
    args = ap.parse_args(argv)
    if args.verb == "arm" and not (args.issue or args.next):
        ap.error("arm needs --issue N or --next")
    try:
        return args.fn(args)
    except Exception as exc:  # noqa: BLE001 — a hook must never wedge the session
        log(f"{args.verb} fail-open: {exc.__class__.__name__}: {exc}")
        if args.verb in ("stop-hook", "inject"):
            if args.verb == "stop-hook":
                print(json.dumps({"systemMessage": f"march: {args.verb} failed open — {exc}"}))
            return 0
        print(f"march: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
