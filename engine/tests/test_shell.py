"""The shell's installer (graphyos #52): the router a cold agent reads first names the memory
lane's doors with the installing interpreter's path, and the doors answer over the archive the
hooks fill."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from graphy.shell import install as shell_install


def _eaten_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".graphy" / "substrate").mkdir(parents=True)
    (repo / ".graphy" / "tenant.json").write_text(json.dumps({"tenants": {}}), encoding="utf-8")
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
    sessions = str(repo.resolve() / ".claude" / "recovery" / "sessions")
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
    out = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert "gate" in out.stdout and "001.md" in out.stdout
