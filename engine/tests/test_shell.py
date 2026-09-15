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
    info = shell_install.install(repo, python="/opt/venv/bin/python", harness=("claude", "codex", "cursor"))
    assert set(info["harness"]) == {"claude", "codex", "cursor"}
    codex = json.loads((repo / ".codex" / "hooks.json").read_text())
    assert set(codex["hooks"]) == {"SessionStart", "SessionEnd", "PreCompact"}, "the gate is not wired for Codex"
    cmd = codex["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert repo.resolve().as_posix() in cmd and "$CLAUDE_PROJECT_DIR" not in cmd and cmd.endswith('session_start.sh"')
    cursor = json.loads((repo / ".cursor" / "hooks.json").read_text())
    assert cursor["version"] == 1 and set(cursor["hooks"]) == {"sessionStart", "sessionEnd", "preCompact"}
    assert cursor["hooks"]["sessionStart"][0]["command"].endswith("session_start.sh --json")
    assert (repo / ".claude" / "settings.json").is_file()
    # idempotent: a second install adds nothing
    shell_install.install(repo, python="/opt/venv/bin/python", harness=("codex", "cursor"))
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
    info = shell_install.install(repo, python=r"C:\venv\Scripts\python.exe", harness=("claude", "codex", "cursor"))
    codex = json.loads((repo / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    cmd = codex["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert repo.resolve().as_posix() in cmd and cmd.endswith('session_start.sh"')
    if os.name != "nt":
        assert "back\\slash" in cmd                                # the backslash travelled, escaped, and came back
    cursor = json.loads((repo / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert cursor["hooks"]["sessionStart"][0]["command"] == f"{repo.resolve().as_posix()}/.graphy/hooks/session_start.sh --json"
    # the shell hooks and the router spell the interpreter POSIX — `C:/venv/Scripts/python.exe` on Windows, a form
    # every shell there accepts; on this host a backslash is a character in a name and as_posix leaves it alone
    py = Path(r"C:\venv\Scripts\python.exe").as_posix()
    hook = (repo / ".graphy" / "hooks" / "session_start.sh").read_text(encoding="utf-8")
    assert f'"{py}"' in hook and f'--project-dir "{repo.resolve().as_posix()}"' in hook
    assert f"{py} -m graphy.lightning" in (repo / "GRAPHY.md").read_text(encoding="utf-8")
    assert info["python"] == r"C:\venv\Scripts\python.exe"        # the receipt keeps what was asked
