"""``graphy shell install --repo <abs>``: bolt the hooks onto an eaten repo. Writes
``<repo>/.graphy/hooks/*.sh`` (the entry points, the installing interpreter's absolute path baked
in — machine-local, ignored by the repo like everything under .graphy/), merges the three hook
events into ``<repo>/.claude/settings.json`` (portable: it names only $CLAUDE_PROJECT_DIR), and
writes ``<repo>/GRAPHY.md``, the router a cold agent reads first, with this tenant's taps and the
memory lane's — the doors over ``.claude/recovery/sessions/`` the hooks fill."""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENTS = ("PreCompact", "SessionEnd", "SessionStart", "PreToolUse")
HARNESSES = ("claude", "codex", "cursor")
# What each harness's wiring carries (graphyos #67). The gate rides only where the pre-edit payload is
# documented (Claude Code's PreToolUse: tool_name · tool_input.file_path); the memory lane rides everywhere.
HARNESS_NOTE = {"claude": ".claude/settings.json — memory + the gate",
                "codex": ".codex/hooks.json — memory; trust it once inside Codex with /hooks; the gate is not wired",
                "cursor": ".cursor/hooks.json — memory (sessionStart answers in JSON); the gate is not wired"}


class ShellError(RuntimeError):
    pass


def _fill(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def _merge_hooks(existing: dict, ours: dict) -> dict:
    hooks = existing.setdefault("hooks", {})
    for event, groups in ours["hooks"].items():
        have = hooks.setdefault(event, [])
        known = {h.get("command") for g in have for h in g.get("hooks", [])}
        for g in groups:
            if not all(h["command"] in known for h in g["hooks"]):
                have.append(g)
    return existing


def _merge_cursor(existing: dict, ours: dict) -> dict:
    """Cursor's hooks.json: `version: 1`, event → [{command, timeout}]; ours join by command."""
    existing.setdefault("version", 1)
    hooks = existing.setdefault("hooks", {})
    for event, defs in ours["hooks"].items():
        have = hooks.setdefault(event, [])
        known = {d.get("command") for d in have}
        have.extend(d for d in defs if d["command"] not in known)
    return existing


def _write_wiring(path: Path, ours: dict, merge) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    path.write_text(json.dumps(merge(current, ours), indent=2) + "\n", encoding="utf-8")
    return path


def install(repo: str | Path, python: str | None = None, *, log=print, harness: tuple[str, ...] = ("claude",)) -> dict:
    unknown = sorted(set(harness) - set(HARNESSES))
    if unknown:
        raise ShellError(f"no wiring for harness {', '.join(unknown)} — the ones that exist: {', '.join(HARNESSES)}")
    repo = Path(repo).expanduser().resolve()
    desc = repo / ".graphy" / "tenant.json"
    ring = repo / ".graphy" / "substrate" / "ring.json"
    if not desc.is_file() or not ring.is_file():
        raise ShellError(f"no eaten tenant under {repo / '.graphy'} — run `graphy eat --repo {repo} "
                         f"--site-packages <its venv's site-packages>` first")
    tid = json.loads(ring.read_text(encoding="utf-8"))["root"]
    py = python or sys.executable
    values = {"python": py, "repo": repo, "desc": desc, "tid": tid, "root_module": f"{tid}://module/{tid}",
              "graphy": Path(py).parent / "graphy", "sessions": repo / ".claude" / "recovery" / "sessions"}
    hooks_dir = repo / ".graphy" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for src in sorted((HERE / "hooks").glob("*.sh")):
        dst = hooks_dir / src.name
        dst.write_text(_fill(src.read_text(encoding="utf-8"), values), encoding="utf-8")
        dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        written.append(dst)
    if "claude" in harness:
        ours = json.loads((HERE / "claude" / "settings.json").read_text(encoding="utf-8"))
        written.append(_write_wiring(repo / ".claude" / "settings.json", ours, _merge_hooks))
    if "codex" in harness:                      # the same event names and hook shape as Claude Code; the repo path filled in
        ours = json.loads(_fill((HERE / "codex" / "hooks.json").read_text(encoding="utf-8"), values))
        written.append(_write_wiring(repo / ".codex" / "hooks.json", ours, _merge_hooks))
    if "cursor" in harness:
        ours = json.loads(_fill((HERE / "cursor" / "hooks.json").read_text(encoding="utf-8"), values))
        written.append(_write_wiring(repo / ".cursor" / "hooks.json", ours, _merge_cursor))
    recovery = repo / ".claude" / "recovery"
    recovery.mkdir(parents=True, exist_ok=True)
    (recovery / ".gitignore").write_text("*\n", encoding="utf-8")   # the operator's sessions never reach the repo
    router = repo / "GRAPHY.md"
    router.write_text(_fill((HERE / "claude" / "GRAPHY.md").read_text(encoding="utf-8"), values), encoding="utf-8")
    written.append(router)
    return {"repo": repo, "tenant_id": tid, "python": py, "written": written,
            "memory_taps": memory_taps(router.read_text(encoding="utf-8")),
            "harness": {h: HARNESS_NOTE[h] for h in HARNESSES if h in harness},
            "history": remint_history(repo, tid, log=log)}


def remint_history(repo: Path, tid: str, *, log=print) -> str:
    """The history shard `eat` minted, minted again over the archive as it stands and the store
    recompiled behind it (graphyos #66) — the install is the moment the hooks start growing the
    archive, so the weld is current from the first session. A tenant with no history shard is named,
    never minted here: `eat` decides whether the repo is a git checkout. Returns the one-word state."""
    from graphy import cli
    from graphy import smash as smash_lane
    home = repo / ".graphy"
    sub = home / "substrate"
    if not (sub / f"{cli.HISTORY_SLUG}_graph" / smash_lane.PROVENANCE_NAME).is_file():
        return "none (`graphy eat .` mints it beside the code shard when the repo is a git checkout)"
    if not cli.eat_history(repo, sub, home, tid, log=log):
        return "skipped"
    for step in (["converge", "--tenant", str(home / "tenant.json"), "--tenant-id", tid, "--resolve"],
                 ["build", "--tenant", str(home / "tenant.json"), "--tenant-id", tid, "--container", "none"]):
        if cli.main(step) != 0:
            return f"re-minted, but the store did not recompile at {step[0]}"
    return "re-minted, store recompiled"


def memory_taps(router_text: str) -> int:
    """The memory doors the rendered router names: one table row per tap under MEMORY, each
    running the installing interpreter over the archive. Counted from the text, never declared."""
    rows = [ln for ln in router_text.splitlines() if ln.startswith("| ")
            and ("-m graphy.lightning" in ln or "-m graphy.reseed" in ln)]
    return len(rows)
