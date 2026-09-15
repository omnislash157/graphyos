"""The shell's installer (graphyos #52): the router a cold agent reads first names the memory
lane's doors with the installing interpreter's path, and the doors answer over the archive the
hooks fill."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from graphy.shell import install as shell_install


def _eaten_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".graphy" / "substrate").mkdir(parents=True)
    (repo / ".graphy" / "tenant.json").write_text(json.dumps({"data_home": str(repo / ".graphy" / "substrate")}), encoding="utf-8")
    (repo / ".graphy" / "substrate" / "ring.json").write_text(json.dumps({"root": "acme"}), encoding="utf-8")
    return repo


def test_GREEN_memory_taps_in_the_rendered_router_name_the_doors_with_the_installing_interpreter(tmp_path):
    repo = _eaten_repo(tmp_path)
    info = shell_install.install(repo, python="/opt/venv/bin/python")
    router = (repo / "GRAPHY.md").read_text(encoding="utf-8")
    assert "## MEMORY" in router
    for door in ("-m graphy.lightning ", "-m graphy.lightning.bloodhound", "-m graphy.lightning.reseed_graph",
                 "-m graphy.reseed --project-dir"):
        assert door in router, door
    sessions = (repo.resolve() / ".claude" / "recovery" / "sessions").as_posix()   # spelled POSIX on every host (graphyos #125)
    assert router.count(f"/opt/venv/bin/python -m graphy.lightning") >= 5
    assert router.count(f"--path {sessions}") >= 5
    assert "{{" not in router, "an unfilled placeholder reached the router"
    assert info["memory_taps"] == 7 == shell_install.memory_taps(router)
    assert info["history"].startswith("none ("), "a tenant with no history shard is named, never minted by install"
    assert "-m graphy history --symbol" in router and "needs the tenant's history shard" not in router
    assert "reseed_tail.md" in router and "sessions/" in router


def test_GREEN_memory_bloodhound_answers_over_an_installed_repo_sessions(tmp_path):
    repo = _eaten_repo(tmp_path)
    shell_install.install(repo, python=sys.executable)
    sessions = repo / ".claude" / "recovery" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "001.md").write_text(
        "--- [1] USER\n\nthe gate blocked an edit to routing\n\n--- [1] ASSISTANT\n\n"
        "the walk from get_request_handler to the root module stored, the gate opened\n", encoding="utf-8")
    router = (repo / "GRAPHY.md").read_text(encoding="utf-8")
    tap = next(ln for ln in router.splitlines() if "-m graphy.lightning.bloodhound" in ln and ln.startswith("| "))
    cmd = tap.split("`")[1].replace('"<A>"', "gate").replace('"<B>"', "walk")
    out = subprocess.run(cmd.split(), capture_output=True, text=True, encoding="utf-8", timeout=60)   # the child writes utf-8
    assert out.returncode == 0, out.stderr
    assert "gate" in out.stdout and "001.md" in out.stdout


# graphyos #67 — the wiring per harness.

def test_GREEN_install_writes_the_wiring_each_harness_reads_and_refuses_one_that_has_none(tmp_path):
    repo = _eaten_repo(tmp_path)
    info = shell_install.install(repo, python="/opt/venv/bin/python", harness=("claude", "codex", "cursor"), os_name="posix")
    assert set(info["harness"]) == {"claude", "codex", "cursor"}
    codex = json.loads((repo / ".codex" / "hooks.json").read_text())
    assert set(codex["hooks"]) == {"SessionStart", "SessionEnd", "PreCompact"}, "the gate is not wired for Codex"
    cmd = codex["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert repo.resolve().as_posix() in cmd and "$CLAUDE_PROJECT_DIR" not in cmd and cmd.endswith('session_start.sh"')
    cursor = json.loads((repo / ".cursor" / "hooks.json").read_text())
    assert cursor["version"] == 1 and set(cursor["hooks"]) == {"sessionStart", "sessionEnd", "preCompact"}
    assert cursor["hooks"]["sessionStart"][0]["command"].endswith('session_start.sh" --json')   # quoted: a spaced path is one word
    assert (repo / ".claude" / "settings.json").is_file()
    # idempotent: a second install adds nothing
    shell_install.install(repo, python="/opt/venv/bin/python", harness=("codex", "cursor"), os_name="posix")
    assert len(json.loads((repo / ".cursor" / "hooks.json").read_text())["hooks"]["sessionStart"]) == 1
    assert len(json.loads((repo / ".codex" / "hooks.json").read_text())["hooks"]["SessionStart"]) == 1
    with pytest.raises(shell_install.ShellError, match="no wiring for harness aider"):
        shell_install.install(repo, harness=("aider",))


def test_RED_a_repo_path_carrying_a_backslash_writes_wiring_the_harness_can_parse(tmp_path):
    """graphyos #125: on Windows the repo path was spliced raw into `codex/hooks.json` and `cursor/hooks.json`,
    and the file written did not parse (`Invalid \\escape: line 8 column 29`) — the harness the install was
    for could not read what it wrote. Every template value is escaped by json.dumps into the JSON, and every
    path is spelled POSIX; proven with a directory whose name carries a backslash — on a POSIX box a character
    in a name, the one shape it can spell; on Windows the separator itself, so the same test reads the
    platform's own case — and the interpreter path spelled the Windows way."""
    repo = _eaten_repo(tmp_path / "back\\slash")
    info = shell_install.install(repo, python=r"C:\venv\Scripts\python.exe", harness=("claude", "codex", "cursor"), os_name="posix")
    codex = json.loads((repo / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    cmd = codex["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert repo.resolve().as_posix() in cmd and cmd.endswith('session_start.sh"')
    if os.name != "nt":
        assert "back\\slash" in cmd                                # the backslash travelled, escaped, and came back
    cursor = json.loads((repo / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert cursor["hooks"]["sessionStart"][0]["command"] == f'"{repo.resolve().as_posix()}/.graphy/hooks/session_start.sh" --json'
    # the shell hooks and the router spell the interpreter POSIX — `C:/venv/Scripts/python.exe` on Windows, a form
    # every shell there accepts; on this host a backslash is a character in a name and as_posix leaves it alone
    py = Path(r"C:\venv\Scripts\python.exe").as_posix()
    hook = (repo / ".graphy" / "hooks" / "session_start.sh").read_text(encoding="utf-8")
    assert f'"{py}"' in hook and f'--project-dir "{repo.resolve().as_posix()}"' in hook
    assert f"{py} -m graphy.lightning" in (repo / "GRAPHY.md").read_text(encoding="utf-8")
    assert info["python"] == r"C:\venv\Scripts\python.exe"        # the receipt keeps what was asked


# graphyos #93 — the hooks run on the host they were written for.

TRANSCRIPT = Path(__file__).parent / "fixtures" / "transcript" / "session.jsonl"


def test_RED_every_byte_the_install_writes_is_the_byte_it_means(tmp_path):
    """graphyos #93: `write_text` without `newline=` translated every `\\n` to `os.linesep`, so on Windows each
    `.sh` hook's shebang read `#!/usr/bin/env bash\\r` and bash could not find `bash\\r` even where it exists —
    the file looked right in every editor. Asserted on the bytes on disk, never on the string handed to the
    writer: LF everywhere, and CRLF in the `.cmd` twins, which cmd.exe reads. The red is Windows' own: on a
    host whose line separator is `\\n` the old writer wrote these same bytes."""
    repo = _eaten_repo(tmp_path)
    shell_install.install(repo, python=sys.executable, harness=("claude", "codex", "cursor"), os_name="nt"
                          if shell_install.git_bash("nt") else "posix")
    hooks = repo / ".graphy" / "hooks"
    lf = [*hooks.glob("*.sh"), repo / ".claude" / "settings.json", repo / ".codex" / "hooks.json",
          repo / ".cursor" / "hooks.json", repo / "GRAPHY.md", repo / ".claude" / "recovery" / ".gitignore"]
    for f in lf:
        assert b"\r" not in f.read_bytes(), f"{f.name} carries a CR"
    for f in hooks.glob("*.sh"):
        assert f.read_bytes().startswith(b"#!/usr/bin/env bash\n"), f.name
    for f in hooks.glob("*.cmd"):
        body = f.read_bytes()
        assert body.count(b"\n") == body.count(b"\r\n") > 0, f"{f.name} is not CRLF throughout"


def test_RED_windows_with_no_git_bash_refuses_the_claude_wiring_by_name_and_wires_the_cmd_hooks(tmp_path, monkeypatch):
    """graphyos #93: the install wired only bash hooks and reported success on a Windows box with no bash, so
    the memory lane it installed never ran. Claude Code runs a hook through Git Bash there and PowerShell
    when it finds none, so with no Git Bash its wiring refuses by name before a byte is written; Codex and
    Cursor are wired to `.cmd` twins that need no bash, the path quoted and matched by the hook's own name — a
    folder carrying `.sh` or a space is part of the path (review round 1). An earlier install's `.sh` command,
    which the host cannot run, is retired from the wiring rather than left to fail beside the twin."""
    monkeypatch.setattr(shell_install, "git_bash", lambda os_name=None: None)
    repo = _eaten_repo(tmp_path / "josh.shaw" / "First Last")
    shell_install.install(repo, python=r"C:\venv\Scripts\python.exe", harness=("codex", "cursor"), os_name="posix")
    with pytest.raises(shell_install.ShellError, match="no Git Bash here .* install Git for Windows"):
        shell_install.install(repo, python=r"C:\venv\Scripts\python.exe", os_name="nt")
    assert not (repo / ".claude" / "settings.json").exists() and not list((repo / ".graphy" / "hooks").glob("*.cmd"))
    shell_install.install(repo, python=r"C:\venv\Scripts\python.exe", harness=("codex", "cursor"), os_name="nt")
    hooks = repo / ".graphy" / "hooks"
    assert sorted(p.name for p in hooks.glob("*.cmd")) == ["before_edit.cmd", "session_end.cmd", "session_start.cmd"]
    cmd = json.loads((repo / ".codex" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["SessionEnd"][0]["hooks"][0]["command"]
    base = repo.resolve().as_posix()
    assert cmd == f'"{base}/.graphy/hooks/session_end.cmd"'
    cursor = json.loads((repo / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert cursor["hooks"]["sessionStart"] == [{"command": f'"{base}/.graphy/hooks/session_start.cmd" --json', "timeout": 15}]
    every = [h["command"] for f in (".codex", ".cursor") for groups in json.loads((repo / f / "hooks.json").read_text(encoding="utf-8"))["hooks"].values()
             for g in groups for h in g.get("hooks", [g])]
    assert every and not any(c.endswith('.sh"') or '.sh" ' in c for c in every), every          # the earlier .sh wiring retired
    with pytest.raises(shell_install.ShellError, match="did not write"):
        shell_install._host_command("notify-send done", "nt")
    body = (hooks / "session_end.cmd").read_text(encoding="utf-8")
    py = Path(r"C:\venv\Scripts\python.exe").as_posix()             # `C:/venv/Scripts/python.exe` where that is a path
    assert f'"{py}" -m graphy.reseed --project-dir "{repo.resolve().as_posix()}" capture' in body and "{{" not in body


def _run_wiring(command: str, harness: str, stdin: str, repo: Path) -> subprocess.CompletedProcess:
    """A wiring command as its harness runs it on this host: `sh -c` off Windows; on Windows Git Bash for
    Claude Code, and cmd.exe for the `.cmd` twins Codex and Cursor are wired to."""
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    if os.name != "nt":
        argv = ["sh", "-c", command]
    elif harness == "claude":
        # the command as a script file, never an argv: Windows re-quotes an argv for the child, and MSYS bash
        # parses the re-quoted `"$CLAUDE_PROJECT_DIR/…"` as an unterminated string. CLAUDE_PROJECT_DIR stays
        # `str(repo)`, the backslash spelling Claude Code sets there (review round 1)
        script = repo / ".graphy" / f"wiring-{abs(hash(command))}.sh"
        script.write_text(command + "\n", encoding="utf-8", newline="\n")
        argv = [shell_install.git_bash("nt"), script.as_posix()]
    else:
        # one command line, never an argv list: list2cmdline escapes a quote as `\"`, which cmd.exe never reads
        argv = f'cmd /d /s /c "{command}"'

    return subprocess.run(argv, input=stdin, capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)


@pytest.mark.parametrize("where", ["plain", "josh.shaw/First Last"])
@pytest.mark.parametrize("harness", ["claude", "codex", "cursor"])
def test_GREEN_the_wiring_captures_and_injects_on_the_host_it_was_written_for(tmp_path, harness, where):
    """graphyos #93's done line: not that the JSON parses, but that each command the install wrote runs on this
    host — the end-of-session hook captures the transcript's tail into the archive, and the start-of-session
    hook prints it back. Run through the shell the harness uses here, with the harness's payload on stdin."""
    if os.name == "nt" and harness == "claude" and shell_install.git_bash("nt") is None:
        pytest.skip("Claude Code's wiring refuses by name on a Windows box with no Git Bash (the RED test above)")
    repo = _eaten_repo(tmp_path / where)                   # a folder carrying `.sh` and a space is part of the path
    shell_install.install(repo, python=sys.executable, harness=(harness,))
    wiring = {"claude": repo / ".claude" / "settings.json", "codex": repo / ".codex" / "hooks.json",
              "cursor": repo / ".cursor" / "hooks.json"}[harness]
    hooks = json.loads(wiring.read_text(encoding="utf-8"))["hooks"]
    end_event, start_event = ("sessionEnd", "sessionStart") if harness == "cursor" else ("SessionEnd", "SessionStart")
    command = lambda ev: (hooks[ev][0].get("hooks") or [hooks[ev][0]])[0]["command"]
    payload = json.dumps({"session_id": "fx-session-0001", "conversation_id": "fx-session-0001",
                          "transcript_path": str(TRANSCRIPT), "cwd": str(repo), "hook_event_name": "SessionEnd", "reason": "clear"})
    end = _run_wiring(command(end_event), harness, payload, repo)
    assert end.returncode == 0, (command(end_event), end.stdout, end.stderr)
    assert (repo / ".claude" / "recovery" / "reseed_tail.md").is_file(), (end.stdout, end.stderr)
    start = _run_wiring(command(start_event), harness, json.dumps({"session_id": "next", "source": "clear"}), repo)
    assert start.returncode == 0, (command(start_event), start.stdout, start.stderr)
    assert "fx-session-0001" in start.stdout, start.stdout[-600:]


# `git show v0.2.4:engine/graphy/shell/cursor/hooks.json` on omnislash157/graphyos, byte for byte: the tag is not in a
# CI checkout, and a test that skips where it cannot fetch its specimen proves nothing
RELEASED_024_CURSOR = """{
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "command": "{{repo}}/.graphy/hooks/session_start.sh --json",
        "timeout": 15
      }
    ],
    "sessionEnd": [
      {
        "command": "{{repo}}/.graphy/hooks/session_end.sh",
        "timeout": 30
      }
    ],
    "preCompact": [
      {
        "command": "{{repo}}/.graphy/hooks/session_end.sh",
        "timeout": 30
      }
    ]
  }
}
"""


@pytest.mark.parametrize("os_name", ["posix", "nt"])
def test_RED_an_install_over_the_released_wiring_leaves_one_entry_per_event(tmp_path, monkeypatch, os_name):
    """Review round 2 of graphyos #93: 0.2.4's Cursor wiring spelled the hook path bare, and the quoted spelling this
    rung writes did not match it, so an upgrade kept both and every event ran twice (on Windows, once more through a
    `.sh` the host cannot run). Every earlier spelling of our own command is retired on every host; a user's own
    entry survives. Seeded with the 0.2.4 template's bytes, filled the way 0.2.4 filled them, installed three times."""
    monkeypatch.setattr(shell_install, "git_bash", lambda os_name=None: "bash")
    repo = _eaten_repo(tmp_path / "josh.shaw" / "First Last")
    seeded = json.loads(RELEASED_024_CURSOR.replace("{{repo}}", repo.resolve().as_posix()))
    seeded["hooks"]["sessionEnd"].append({"command": "notify-send done", "timeout": 5})
    (repo / ".cursor").mkdir(parents=True)
    (repo / ".cursor" / "hooks.json").write_text(json.dumps(seeded), encoding="utf-8", newline="\n")
    for _ in range(3):
        shell_install.install(repo, python=sys.executable, harness=("cursor",), os_name=os_name)
    hooks = json.loads((repo / ".cursor" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    ours = {ev: [d["command"] for d in defs if "notify-send" not in d["command"]] for ev, defs in hooks.items()}
    assert all(len(v) == 1 for v in ours.values()), ours
    ext = ".cmd" if os_name == "nt" else ".sh"
    assert all(v[0].startswith('"') and f'{ext}"' in v[0] for v in ours.values()), ours
    assert any(d["command"] == "notify-send done" for d in hooks["sessionEnd"]), "a user's own hook was dropped"
