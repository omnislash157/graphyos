#!/usr/bin/env python3
"""march — the board loop. One open issue is armed; the Stop hook refuses to let the session
stop while it is open, and the moment it closes the hook arms the next one, acks `/clear` into
the session's own tmux pane, and kicks the fresh context every two minutes until it acks back.

Verbs (all from the repo root, python3 .claude/hooks/march.py <verb>):
  arm --issue N | --next   arm an issue (for --next: the first of the declared order that is open without
                           `blocked` or `operator`, then the lowest such number)
  ack                      the fresh context reports in; the wake loop stops kicking
  status                   the state file, the watcher pid, the live board state of the issue
  next                     print the next open unblocked issue number
  order [N …]              declare the board's order for --next (the first tenant's priority); a rung not
                           listed comes after, by number; bare, print it; --clear returns to the sequence
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
ORDER = RECOVERY / "march_order.json"
LOG = RECOVERY / "march.log"
TSEND = Path(__file__).resolve().with_name("tsend.sh")
REPO = os.environ.get("MARCH_REPO", "omnislash157/graphyos")

CLEAR_DELAY = float(os.environ.get("MARCH_CLEAR_DELAY", "5"))
CADENCE = float(os.environ.get("MARCH_CADENCE", "120"))
GATE_TOKEN = "MARCH GATE"
OPERATOR_LABEL = "operator"
# A hold is a handhold for entropy: the loop never stops on a rung that needs the operator. It gates
# THAT rung — labeled `operator` on the board with the exact step — and marches the next one. Only the
# gates no walk can derive pass (the Enterprise "ur call" gate, #682, ported): a ruling on the law, money,
# an outside account, making something public, an irreversible act outside git.
REAL_GATES = {
    "LAW": "a ruling on CLAUDE.md, a law, or the nine words",
    "MONEY": "money or an outbound send",
    "ACCOUNT": "an outside account or a credential",
    "PUBLIC": "making a repo, a release or a page public",
    "IRREVERSIBLE": "a destructive act git cannot undo",
}
# the verb is an order only at the start of a line, outside code spans — naming it in prose is not a gate
_GATE_RE = re.compile(r"^\s*" + re.escape(GATE_TOKEN) + r"\s*:\s*(?P<gate>[A-Za-z.]+)\s*[—–-]+\s*(?P<step>\S.*?)(?:\*\*|__)?\s*$",
                      re.MULTILINE | re.IGNORECASE)
_GATE_BARE_RE = re.compile(r"^\s*" + re.escape(GATE_TOKEN) + r"\b(?P<rest>.*)$", re.MULTILINE | re.IGNORECASE)
_CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
PUNTS = (
    r"^\s*MARCH HOLD\b",
    r"\byour call\b", r"\bup to you\b", r"\byou decide\b",
    r"\bwould you like me to\b", r"\bdo you want me to\b", r"\bwant me to\b",
    r"\b(?:should|shall) i (?:proceed|go ahead|continue|start|commit|push|close|ship|file|merge|arm)\b",
    r"\bhow would you like (?:me )?to\b", r"\b(?:call it|say which|tell me which) and i'?ll\b",
    r"\bi'?m not guessing\b", r"\bboth yours\b(?!\s+and)", r"\byour go-?ahead\b",
    r"\bneeds? the operator to (?:decide|rule|call|sign)\b",
    r"\bwhich (?:would you prefer|do you (?:want|prefer))\b",
    r"\blet me know (?:how|which|if|whether) you\b",
    r"\b(?:calls?|decisions?|rulings?)\s+(?:that\s+)?(?:are|is)\s+yours\b",
    r"\byours to (?:call|rule|decide|make)\b",
    r"\bneeds? (?:your|an? operator(?:'s)?) (?:call|ruling|decision|sign-?off)\b",
    r"\bblocked on the operator\b", r"\bwaiting (?:on|for) (?:you|the operator)\b",
)
_PUNT_RE = re.compile("|".join(PUNTS), re.IGNORECASE | re.MULTILINE)
_DECOR_RE = re.compile(r"^[ \t]*(?:[-*>]+[ \t]*)?(?:\*\*|__)?", re.MULTILINE)   # `- `, `> `, `**` before a line's verb

INTERROGATION = """MARCH — the closing message defers to the operator: "{quote}"

A hold is not a stop. Before any rung is handed to the operator, answer the four (the Enterprise
"ur call" gate, #682, in the operator's words):

  1. IS IT REALLY THEIR CALL? A past ruling on the board, in CLAUDE.md or in RECON already settled
     it: cite it and act.
  2. IS IT MECHANICALLY DERIVABLE? Walk it — graphy blast · descend · explain, the receipt, the
     battery, the done block. A fork the tree answers resolves; it does not ask.
  3. DOES THE BOARD OR THE PROCESS ALREADY ANSWER IT? The rung, its done block, the review round,
     the skill: you are asking for permission you were handed.
  4. WHICH REAL GATE IS IT? Only these: {gates}.

Then one of two:
  • it resolves → derive it, march, and report the result, not the option;
  • it is one of the gates → a line of its own, outside code:
        MARCH GATE: <{names}> — <the exact step the operator takes>
    The hook labels issue {issue} `{label}`, comments the step, and marches the next rung.
    The loop does not stop.
"""

BAD_GATE = """MARCH — `{got}` names no real gate. A gate line is not a password: it names which gate no walk
can derive, and there are only these: {gates}. Written as

    MARCH GATE: <{names}> — <the exact step the operator takes>

If none fits, it is not a gate — it is a walk not yet taken. Take it, then report the result.
"""


def _prose(message: str) -> str:
    text = message or ""
    if text.count("```") % 2:                          # an unclosed fence: everything after it is code
        text = text.rsplit("```", 1)[0]
    return _DECOR_RE.sub("", _CODE_RE.sub(" ", text))


def gate_of(message: str) -> tuple[str, str] | None:
    """(GATE, step) when the closing message carries a well-formed gate line naming a real gate."""
    for m in _GATE_RE.finditer(_prose(message)):
        if m.group("gate").upper() in REAL_GATES:
            return m.group("gate").upper(), m.group("step").strip()
    return None


def bad_gate(message: str) -> str | None:
    """The text of a gate line that names no real gate or carries no step, else None."""
    prose = _prose(message)
    for m in _GATE_BARE_RE.finditer(prose):
        good = _GATE_RE.match(m.group(0))
        if not good or good.group("gate").upper() not in REAL_GATES:
            return m.group(0).strip()
    return None


def punt_of(message: str) -> str | None:
    """The quoted deferral anywhere in the closing message's prose, when there is one."""
    prose = _prose(message)
    hit = _PUNT_RE.search(prose)
    if not hit:
        return None
    start, end = max(0, hit.start() - 40), min(len(prose), hit.end() + 40)
    return " ".join(prose[start:end].split())


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


def read_order() -> tuple[list[int], str | None]:
    """The declared order and why it cannot be read: absent is the empty order (quiet); a file that
    is there and does not parse as a list of ints is NAMED — never a silent fall-back to the sequence.
    One read, so a hand edit between two reads cannot raise inside a hook."""
    try:
        text = ORDER.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [], None
    except OSError as exc:
        return [], f"{ORDER} unreadable: {exc.__class__.__name__}: {exc}"
    try:
        rows = json.loads(text)
    except ValueError as exc:
        return [], f"{ORDER} unreadable: {exc.__class__.__name__}: {exc}"
    if not isinstance(rows, list) or not all(isinstance(n, int) and not isinstance(n, bool) for n in rows):
        return [], f"{ORDER} is not a list of issue numbers"
    return list(rows), None


def order_error() -> str | None:
    return read_order()[1]


def load_order() -> list[int]:
    """The declared order of the board (`march.py order 122 124 …`): the first tenant's priority,
    written once, read by every `--next`. A file that cannot be read is logged by name and is the
    empty order — never a crash in a hook."""
    rows, err = read_order()
    if err:
        log(f"order ignored — {err}")
    return rows


def next_issue(exclude: int | None = None) -> int | None:
    rows = json.loads(gh("issue", "list", "--state", "open", "--limit", "200", "--json", "number,labels"))
    candidates = [
        r["number"] for r in rows
        if r["number"] != exclude and not any(l["name"] in ("blocked", OPERATOR_LABEL) for l in r.get("labels", []))
    ]
    if not candidates:
        return None
    for n in load_order():                      # the declared order first: a closed or gated rung falls through
        if n in candidates:
            return n
    return min(candidates)                      # then the number sequence


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


def cmd_order(args: argparse.Namespace) -> int:
    if args.clear:
        ORDER.unlink(missing_ok=True)
        log("order cleared — --next follows the number sequence")
        print("march: order cleared")
        return 0
    if args.issues:
        RECOVERY.mkdir(parents=True, exist_ok=True)
        seen: list[int] = []
        for n in args.issues:
            if n not in seen:
                seen.append(n)
        tmp = ORDER.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(seen), encoding="utf-8")
        os.replace(tmp, ORDER)
        log(f"order declared: {seen}")
    err = order_error()
    if err:
        print(f"march: order IGNORED — {err}; --next follows the number sequence until it is redeclared")
        return 1
    order = load_order()
    print("march: order " + (" ".join(f"#{n}" for n in order) if order else "— none, the number sequence"))
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


_NOTIFIED_RE = re.compile(r"<task-id>([A-Za-z0-9_-]+)</task-id>")
_TOOL_USE_RE = re.compile(r'"type":\s*"tool_use"')


def transcript_facts(path: str | None) -> tuple[set[str], int]:
    """(background tasks launched and not yet notified, tool calls made) — read from the transcript the
    hook is handed. A wait on a live background task is not a stall, and a turn that called a tool made
    progress: neither is what the block cap exists to catch. An unreadable transcript is (∅, 0)."""
    try:
        text = Path(path).read_text(errors="replace") if path else ""
    except OSError:
        return set(), 0
    # a launch is the harness's own structured record (toolUseResult), never text: an id quoted in a
    # tool's output or an injected reseed tail launches nothing
    launched: set[str] = set()
    for line in text.splitlines():
        if '"toolUseResult"' not in line:
            continue
        try:
            result = json.loads(line).get("toolUseResult")
        except ValueError:
            continue
        if isinstance(result, dict):
            task = result.get("agentId") if result.get("status") == "async_launched" else result.get("backgroundTaskId")
            if isinstance(task, str) and task:
                launched.add(task)
    notified = set(_NOTIFIED_RE.findall(text))
    return launched - notified, len(_TOOL_USE_RE.findall(text))


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
    message = payload.get("last_assistant_message") or ""
    if not state.get("issue") or state.get("phase") is None:
        return allow()
    if state.get("phase") == "hold":
        # a cap or a drain holds the loop, never the gate: a gate line still labels its rung and marches
        # on. Only the operator's disarm is deaf to it.
        gated = gate_of(message)
        capped = str(state.get("held_because", "")).endswith("still open")      # the block cap, not a drain or a disarm
        ours = state.get("session") in (None, payload.get("session_id"))
        if gated and capped and ours:
            return gate(state, int(state["issue"]), *gated)
        if capped and ours:
            # a rung finished while the loop was held is still finished: the close marches the next one
            try:
                closed = issue_state(int(state["issue"])) != "OPEN"
            except Exception as exc:  # noqa: BLE001
                log(f"gh failed on held issue {state['issue']}: {exc}")
                return allow()
            if closed:
                unblock(int(state["issue"]))
                return advance(state, int(state["issue"]), f"issue {state['issue']} closed during a hold")
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
    gates = " · ".join(f"{k} ({v})" for k, v in REAL_GATES.items())
    names = " | ".join(REAL_GATES)
    gated = gate_of(message)
    if gated is not None:
        return gate(state, issue, *gated)
    # A deferral or a malformed gate is questioned once per message, and every question counts toward
    # the cap: asked on the first stop of a chain and on every later one (stop_hook_active is true for
    # nearly every stop of a march), never twice in a row, never unbounded.
    wrong = bad_gate(message)
    quote = None if wrong else punt_of(message)
    if (wrong or quote) and state.get("last_block") != "question":
        state.update(blocks=int(state.get("blocks", 0)) + 1, last_block="question")
        save(state)
        if wrong:
            log(f"bad gate on issue {issue}: {wrong}")
            return block(BAD_GATE.format(got=wrong, gates=gates, names=names))
        log(f"deferral without a gate on issue {issue}: {quote}")
        return block(INTERROGATION.format(quote=quote, gates=gates, names=names, issue=issue, label=OPERATOR_LABEL))
    try:
        live = issue_state(issue)
    except Exception as exc:  # noqa: BLE001
        log(f"gh failed on issue {issue}: {exc}")
        return allow(f"could not read issue {issue} from GitHub ({exc}); letting the session stop")

    if live == "OPEN":
        pending, tool_uses = transcript_facts(payload.get("transcript_path"))
        if pending:
            # the session is waiting on its own background work, whose notification wakes it: let it
            # stop, count nothing — a review round in flight is the march working, not stalling
            state.update(blocks=0, last_block="waiting", tool_uses=tool_uses)
            save(state)
            log(f"waiting on issue {issue}: {len(pending)} background task(s) pending ({', '.join(sorted(pending))})")
            return allow(f"issue {issue} is open and {len(pending)} background task(s) are still running; "
                         f"their notification wakes the session")
        if tool_uses > int(state.get("tool_uses", 0)):
            state["blocks"] = 0            # a turn that called a tool made progress; the stall count is progress-reset, never a cap
        state["tool_uses"] = tool_uses
        # no cap: the loop never limits itself — an open issue with no background work is always blocked
        blocks = int(state.get("blocks", 0)) + 1
        state.update(blocks=blocks, last_block="open")
        save(state)
        log(f"blocked stop on issue {issue} ({blocks} stalled)")
        return block(
            f"MARCH — issue {issue} is still OPEN on the board ({blocks} stalled continuation(s)). "
            f"The loop does not stop on an open issue. Keep marching: run its done check, then review "
            f"rounds until one reads SHIP (rung-discipline §2.6), land the evidence, commit and push, then "
            f"`gh issue close {issue} --repo {REPO} --comment <evidence>`. "
            f"A rung only the operator can finish is gated, never held: a line `{GATE_TOKEN}: <gate> — <step>` "
            f"naming one of {names}, and the march moves to the next rung."
        )
    red = ci_red()
    if red:                                  # no cap: every stop on a red main is blocked until it is green
        pending, tool_uses = transcript_facts(payload.get("transcript_path"))
        if pending:                          # §125: a wait on the session's own background work never holds (round 1)
            state.update(last_block="waiting", tool_uses=tool_uses)
            save(state)
            log(f"issue {issue} closed on a red main ({red}); waiting on {len(pending)} background task(s)")
            return allow(f"issue {issue} is closed but ci on main is red at {red}; {len(pending)} background task(s) "
                         f"are still running and their notification wakes the session")
        state.update(blocks=int(state.get("blocks", 0)) + 1, last_block=f"ci {red}")
        save(state)
        log(f"issue {issue} closed on a red main: ci failed on {red}")
        return block(
            f"MARCH — issue {issue} is closed, but `ci` on main is RED at {red}. A rung is not landed on a red "
            f"main: `gh run list --repo {REPO} --workflow ci --branch main --limit 1`, `python3 workflows.py --run .github/workflows/ci.yml <job>` runs every step here, read the failed job's log, fix it, run the "
            f"gate, commit and push; the next stop on a green or pending main arms the next rung."
        )
    unblock(issue)
    return advance(state, issue, f"issue {issue} closed")


def ci_red() -> str | None:
    """The head sha of main's newest `ci` run when that run FAILED, else None. Pending, green or unreadable never
    holds the loop; a definite red does — eight rungs once closed on a red main because nothing read it (#88)."""
    try:
        rows = json.loads(gh("run", "list", "--workflow", "ci", "--branch", "main", "--limit", "1",
                             "--json", "status,conclusion,headSha") or "[]")
    except Exception as exc:  # noqa: BLE001
        log(f"could not read ci on main: {exc}")
        return None
    if rows and rows[0].get("status") == "completed" and rows[0].get("conclusion") in ("failure", "timed_out", "startup_failure"):
        return str(rows[0].get("headSha", ""))[:12] or "?"
    return None


def gate(state: dict, issue: int, name: str, step: str) -> int:
    """Hand one rung to the operator and march the next: the label, the step as a comment, advance."""
    gh("issue", "edit", str(issue), "--add-label", OPERATOR_LABEL)
    gh("issue", "comment", str(issue), "--body", f"MARCH GATE: {name} — {step}\n\nThe march moved on; "
       f"this rung waits for the operator. Removing the `{OPERATOR_LABEL}` label returns it to the board.")
    log(f"gate {name} on issue {issue}: {step}")
    return advance(state, issue, f"issue {issue} gated ({name}) and labeled `{OPERATOR_LABEL}`")


_BLOCKED_BY_RE = re.compile(r"\bblocked (?:by|on)\s+#(\d+)", re.IGNORECASE)


def unblock(closed: int) -> list[int]:
    """A wait ends when its blocker closes: every open `blocked` issue whose body or comments say
    `blocked by #N` loses the label once each issue it names is closed. A `blocked` issue that names
    no blocker keeps its label and is left for the operator's eye in the log."""
    freed: list[int] = []
    rows = json.loads(gh("issue", "list", "--state", "open", "--label", "blocked", "--limit", "200",
                         "--json", "number,body,comments"))
    for r in rows:
        text = (r.get("body") or "") + "\n" + "\n".join(c.get("body") or "" for c in r.get("comments") or [])
        waits = {int(n) for n in _BLOCKED_BY_RE.findall(text)}
        if not waits:
            log(f"issue {r['number']} is `blocked` and names no blocker")
            continue
        if closed in waits and all(n == closed or issue_state(n) == "CLOSED" for n in waits):
            gh("issue", "edit", str(r["number"]), "--remove-label", "blocked")
            log(f"issue {r['number']} unblocked: its blockers {sorted(waits)} are closed")
            freed.append(r["number"])
    return freed


def advance(state: dict, issue: int, why: str) -> int:
    """The rung is done or gated: arm the next unblocked, unGated issue and clear into it."""
    nxt = next_issue(issue)
    kill_watcher(state)
    if nxt is None:
        state.update(phase="hold", held_at=now(), held_because="board drained", closed=issue)
        save(state)
        log(f"{why}; board drained")
        return allow(f"{why}, and the board has no open unblocked issue. A drained board is not a stop: run "
                     f"the optimization pass (rung-discipline §3), file what it measures, `march.py arm --next`. "
                     f"The clean stop is a pass that files nothing (rung-discipline §2.4).")
    state = {"issue": nxt, "phase": "clearing", "blocks": 0, "armed_at": now(), "previous": issue}
    target = pane()
    if target:
        state["watcher_pid"] = spawn_watcher(target, nxt)
        state["pane"] = target
        save(state)
        log(f"{why}; armed {nxt}; watcher {state['watcher_pid']} on {target}")
        return allow(f"{why}. Issue {nxt} armed. `/clear` lands in pane {target} in "
                     f"{CLEAR_DELAY:.0f}s; the wake kicks every {CADENCE:.0f}s until the fresh context acks.")
    save(state)
    log(f"{why}; armed {nxt}; no tmux pane — operator ack")
    return allow(f"{why}. Issue {nxt} armed. Not in tmux: the ack is yours — press /clear "
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
    print(f"Then march issue {issue} until its done check holds on a real run and a review round reads SHIP "
          f"(rung-discipline §2.6): land the evidence, commit, push, and "
          f"`gh issue close {issue} --repo {REPO} --comment <evidence>`. The Stop hook refuses to "
          f"stop while it is open and arms the next issue the moment it closes. A rung only the operator can "
          f"finish is gated with a line `{GATE_TOKEN}: <{' | '.join(REAL_GATES)}> — <the exact step>`: it is "
          f"labeled `{OPERATOR_LABEL}` and the march moves on. Only the operator's `march.py disarm` stops the loop.")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    target, issue = args.pane, int(args.issue)
    log(f"watcher up for issue {issue} on {target}: clear in {CLEAR_DELAY}s, cadence {CADENCE}s, kicks until acked")
    time.sleep(CLEAR_DELAY)
    tsend(target, "/clear")
    k = 0
    while True:                            # no kick cap: the watcher kicks until the fresh context acks
        k += 1
        time.sleep(CADENCE)
        state = load()
        if state.get("issue") != issue or state.get("phase") != "clearing":
            log(f"watcher done after {k - 1} kicks: phase={state.get('phase')} issue={state.get('issue')}")
            return 0
        tsend(target, wake_text(issue))
        log(f"kick {k}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="march", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="verb", required=True)
    a = sub.add_parser("arm"); a.add_argument("--issue", type=int); a.add_argument("--next", action="store_true")
    a.set_defaults(fn=cmd_arm)
    for name, fn in (("ack", cmd_ack), ("clear", cmd_clear), ("status", cmd_status), ("next", cmd_next), ("disarm", cmd_disarm),
                     ("stop-hook", cmd_stop_hook), ("inject", cmd_inject)):
        sub.add_parser(name).set_defaults(fn=fn)
    w = sub.add_parser("watch"); w.add_argument("pane"); w.add_argument("issue"); w.set_defaults(fn=cmd_watch)
    o = sub.add_parser("order"); o.add_argument("issues", type=int, nargs="*"); o.add_argument("--clear", action="store_true")
    o.set_defaults(fn=cmd_order)
    args = ap.parse_args(argv)
    if args.verb == "order" and args.clear and args.issues:
        ap.error("order takes numbers or --clear, never both")
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
