"""``graphy shell install --repo <abs>``: bolt the hooks onto an eaten repo. Writes
``<repo>/.graphy/hooks/*.sh`` (the entry points, the installing interpreter's absolute path baked
in — machine-local, ignored by the repo like everything under .graphy/), merges the three hook
events into ``<repo>/.claude/settings.json`` (portable: it names only $CLAUDE_PROJECT_DIR), and
writes ``<repo>/GRAPHY.md``, the router a cold agent reads first, with this tenant's taps and the
memory lane's — the doors over ``.claude/recovery/sessions/`` the hooks fill."""
from __future__ import annotations

import json
import os
import re
import shutil
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


def _spell(v) -> str:
    """A template value as it travels: a path is POSIX on every host (`C:/venv/Scripts/python.exe`, which
    every Windows shell and interpreter accepts), so no separator the reader must escape is ever written."""
    return Path(v).as_posix() if isinstance(v, Path) else str(v)


def _fill(text: str, values: dict) -> str:
    """The shell and markdown templates: each `{{key}}` becomes its value's spelling."""
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", _spell(v))
    return text


def _fill_json(text: str, values: dict) -> str:
    """The JSON templates (`codex/hooks.json` · `cursor/hooks.json`): every value is escaped by `json.dumps`
    inside its string, never spliced raw — a path carrying a backslash or a quote wrote a file the harness
    could not parse (`Invalid \\escape`, graphyos #125). The templates keep their own quotes."""
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", json.dumps(_spell(v), ensure_ascii=False)[1:-1])
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


def _write(path: Path, text: str, *, newline: str = "\n") -> None:
    """Every byte the installer writes is the byte it means, on every host: text mode translates `\n` to
    `os.linesep`, so on Windows a `.sh` hook's shebang read `bash\r` and failed even where bash exists
    (graphyos #93). A generated file passes through no `.gitattributes` a repo declares, so the engine
    says the line ending itself: LF, except a `.cmd`, which cmd.exe reads CRLF."""
    path.write_text(text, encoding="utf-8", newline=newline)


def git_bash(os_name: str | None = None) -> str | None:
    """The bash a harness runs a `.sh` hook through, or None. Off Windows, `bash` on PATH. On Windows,
    Claude Code runs a hook command through Git Bash when it is installed and PowerShell otherwise
    (code.claude.com/docs/en/hooks-guide); the `bash` on PATH there may be WSL's `System32` stub, which
    runs nothing of the repo's, so Git Bash is looked for beside `git` as well."""
    if (os_name or os.name) != "nt":
        return shutil.which("bash")
    found = shutil.which("bash")
    if found and "\\system32\\" not in found.lower().replace("/", "\\") and "windowsapps" not in found.lower():
        return found
    git = shutil.which("git")
    if git:
        for cand in (Path(git).resolve().parent.parent / "bin" / "bash.exe", Path(git).resolve().parent / "bash.exe"):
            if cand.is_file():
                return str(cand)
    return None


HOOK_COMMAND = re.compile(r'^"(?P<path>.*/\.graphy/hooks/(?P<name>[a-z_]+))\.sh"(?P<args>(?: [^"]*)?)$')


def _host_command(cmd: str, os_name: str) -> str:
    """A codex or cursor wiring command as the host runs it: `"<repo>/.graphy/hooks/<name>.sh"[ args]`, the
    path always quoted so a repo under `C:/Users/First Last` is one word. On Windows the hook is its `.cmd`
    twin, matched by the hook's own name at the end of the path, never the first `.sh` anywhere in it (a
    folder `josh.shaw`, review round 1 of graphyos #93). Which shell Codex and Cursor run a command through
    on Windows is not documented; the quoted form is the one cmd.exe runs, which is what a Node process's
    shell spawn uses there."""
    if os_name != "nt":
        return cmd
    m = HOOK_COMMAND.match(cmd)
    if m is None:
        raise ShellError(f"a wiring command this installer did not write reached the host rewrite: {cmd!r}")
    return f'"{m.group("path")}.cmd"{m.group("args")}'


def _spellings(cmd: str) -> set[str]:
    """Every spelling an earlier install wrote for this hook command: quoted and unquoted (0.2.4's Cursor
    wiring left the path bare), `.sh` and `.cmd`."""
    m = HOOK_COMMAND.match(cmd)
    if m is None:
        return {cmd}
    path, args = m.group("path"), m.group("args")
    return {f'{q}{path}{ext}{q}{args}' for q in ('"', "") for ext in (".sh", ".cmd")}


def _host_wiring(ours: dict, os_name: str) -> tuple[dict, set[str]]:
    """The wiring with each command as the host runs it, and every other spelling of that command an earlier
    install wrote — 0.2.4's unquoted path, a `.sh` a Windows host cannot run — retired from the file on merge,
    so an upgrade leaves one entry per event on every host (review round 2 of graphyos #93)."""
    replaced: set[str] = set()
    for defs in ours["hooks"].values():
        for d in defs:
            for h in d.get("hooks", [d]):
                host = _host_command(h["command"], os_name)
                replaced |= _spellings(h["command"]) - {host}
                h["command"] = host
    return ours, replaced


def _retire(current: dict, stale: set[str]) -> dict:
    """Drop the hook entries whose command is one this install replaced for the host, and any group left empty."""
    for event, groups in list(current.get("hooks", {}).items()):
        kept = []
        for g in groups:
            if "hooks" in g:
                g["hooks"] = [h for h in g["hooks"] if h.get("command") not in stale]
                if g["hooks"]:
                    kept.append(g)
            elif g.get("command") not in stale:
                kept.append(g)
        current["hooks"][event] = kept
    return current


def _write_wiring(path: Path, ours: dict, merge, stale: set[str] = frozenset()) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    current = _retire(json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}, set(stale))
    _write(path, json.dumps(merge(current, ours), indent=2) + "\n")
    return path


def install(repo: str | Path, python: str | None = None, *, log=print, harness: tuple[str, ...] = ("claude",),
            os_name: str | None = None) -> dict:
    unknown = sorted(set(harness) - set(HARNESSES))
    if unknown:
        raise ShellError(f"no wiring for harness {', '.join(unknown)} — the ones that exist: {', '.join(HARNESSES)}")
    host = os_name or os.name
    if host == "nt" and "claude" in harness and git_bash(host) is None:
        raise ShellError("Claude Code runs a hook through Git Bash on Windows, and through PowerShell when it finds none; "
                         "the hooks this wires for it are bash and there is no Git Bash here — install Git for Windows and run "
                         "`graphy shell install` again, or use WSL; "
                         "`--harness codex` and `--harness cursor` wire the .cmd hooks, which need no bash (graphyos #93)")
    repo = Path(repo).expanduser().resolve()
    desc = repo / ".graphy" / "tenant.json"
    from graphy.cli import served_data_home
    served = served_data_home(desc)
    ring = served / "ring.json" if served is not None else None
    if ring is None or not ring.is_file():
        raise ShellError(f"no eaten tenant under {repo / '.graphy'} — run `graphy eat --repo {repo} "
                         f"--site-packages <its venv's site-packages>` first")
    tid = json.loads(ring.read_text(encoding="utf-8"))["root"]
    py = python or sys.executable
    values = {"python": Path(py), "repo": repo, "desc": desc, "tid": tid, "root_module": f"{tid}://module/{tid}",
              "graphy": Path(py).parent / "graphy", "sessions": repo / ".claude" / "recovery" / "sessions"}
    hooks_dir = repo / ".graphy" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for src in sorted((HERE / "hooks").glob("*.sh")):
        dst = hooks_dir / src.name
        _write(dst, _fill(src.read_text(encoding="utf-8"), values))
        dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)   # POSIX's executability; a no-op on Windows
        written.append(dst)
    if host == "nt":                              # the twins a host with no bash runs; cmd.exe reads them CRLF
        for src in sorted((HERE / "hooks").glob("*.cmd")):
            dst = hooks_dir / src.name
            _write(dst, _fill(src.read_text(encoding="utf-8"), values), newline="\r\n")
            written.append(dst)
    if "claude" in harness:
        ours = json.loads((HERE / "claude" / "settings.json").read_text(encoding="utf-8"))
        written.append(_write_wiring(repo / ".claude" / "settings.json", ours, _merge_hooks))
    if "codex" in harness:                      # the same event names and hook shape as Claude Code; the repo path filled in
        ours, stale = _host_wiring(json.loads(_fill_json((HERE / "codex" / "hooks.json").read_text(encoding="utf-8"), values)), host)
        written.append(_write_wiring(repo / ".codex" / "hooks.json", ours, _merge_hooks, stale))
    if "cursor" in harness:
        ours, stale = _host_wiring(json.loads(_fill_json((HERE / "cursor" / "hooks.json").read_text(encoding="utf-8"), values)), host)
        written.append(_write_wiring(repo / ".cursor" / "hooks.json", ours, _merge_cursor, stale))
    recovery = repo / ".claude" / "recovery"
    recovery.mkdir(parents=True, exist_ok=True)
    _write(recovery / ".gitignore", "*\n")   # the operator's sessions never reach the repo
    router = repo / "GRAPHY.md"
    _write(router, _fill((HERE / "claude" / "GRAPHY.md").read_text(encoding="utf-8"), values))
    written.append(router)
    return {"repo": repo, "tenant_id": tid, "python": py, "written": written,
            "memory_taps": memory_taps(router.read_text(encoding="utf-8")),
            "harness": {h: HARNESS_NOTE[h] for h in HARNESSES if h in harness},
            "history": remint_history(repo, tid, log=log)}


def remint_history(repo: Path, tid: str, *, log=print) -> str:
    """The history shard `eat` minted, minted again over the archive as it stands and the store
    recompiled behind it (graphyos #66) — the install is the moment the hooks start growing the
    archive, so the weld is current from the first session. A tenant with no history shard is named,
    never minted here: `eat` decides whether the repo is a git checkout. The re-mint is `graphy history
    --remint`: a staged generation landed in one descriptor rename, never the served one written in
    place (graphyos #119, folded into #132). Returns the one-word state."""
    from graphy import cli
    from graphy import smash as smash_lane
    home = repo / ".graphy"
    sub = cli.served_data_home(home / "tenant.json")
    if sub is None or not (sub / f"{cli.HISTORY_SLUG}_graph" / smash_lane.PROVENANCE_NAME).is_file():
        return "none (`graphy eat .` mints it beside the code shard when the repo is a git checkout)"
    rc = cli.main(["history", "--remint", "--tenant", str(home / "tenant.json"), "--tenant-id", tid])
    if rc == 1:      # landed; the check that follows the landing named a lane (the cursor's, when the wiring just written is untracked)
        return "re-minted, store recompiled; `graphy check` reads red — its lines above name the lane"
    if rc != 0:
        return f"re-mint refused (exit {rc}) — the served store stands; run `graphy history --remint --tenant " \
               f"{(home / 'tenant.json').as_posix()} --tenant-id {tid}` to read why"
    return "re-minted, store recompiled"


def memory_taps(router_text: str) -> int:
    """The memory doors the rendered router names: one table row per tap under MEMORY, each
    running the installing interpreter over the archive. Counted from the text, never declared."""
    rows = [ln for ln in router_text.splitlines() if ln.startswith("| ")
            and ("-m graphy.lightning" in ln or "-m graphy.reseed" in ln)]
    return len(rows)
