"""The one-liner: eat provisions the repo's dependencies itself and says what it did. A floor with
pip and npm injected; the proof is the three cold eats in RECON."""
from __future__ import annotations

import json
from pathlib import Path

import graphy.cli as cli
from graphy import provision


def test_GREEN_python_repo_gets_a_venv_and_pip_install(tmp_path):
    repo = tmp_path / "pkg"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[project]\nname="pkg"\nversion="0"\n')
    calls = []

    def runner(cmd, cwd=None, timeout=0):
        calls.append(cmd)
        if cmd[1:3] == ["-m", "venv"]:
            sp = Path(cmd[3]) / "lib" / "python3.12" / "site-packages"
            sp.mkdir(parents=True)
            (Path(cmd[3]) / "bin").mkdir()
            (Path(cmd[3]) / "bin" / "python").write_text("")
        return 0, ""

    pv = provision.provision(repo, "python_ast", runner=runner)
    assert pv.installed and pv.site == repo / ".graphy" / "venv" / "lib" / "python3.12" / "site-packages"
    assert calls[0][1:3] == ["-m", "venv"] and calls[1][-1] == str(repo) and "pip" in calls[1]
    # a repo that will not install is minted alone, and the line says so
    pv2 = provision.provision(repo, "python_ast", runner=lambda cmd, cwd=None, timeout=0: (1, "boom") if "pip" in cmd else (0, ""))
    assert not pv2.installed and "did not pip-install" in pv2.how and "boom" in pv2.how
    # no metadata at all: no pip is run
    bare = tmp_path / "bare"
    (bare / "x").mkdir(parents=True)
    pv3 = provision.provision(bare, "python_ast", runner=runner)
    assert not pv3.installed and "no pyproject.toml" in pv3.how


def test_GREEN_package_json_repo_gets_npm_install(tmp_path, monkeypatch):
    repo = tmp_path / "js"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({"name": "js", "dependencies": {"ms": "2"}}))
    calls = []
    monkeypatch.setattr(provision.shutil, "which", lambda name: "/usr/bin/npm")
    pv = provision.provision(repo, "typescript_ast", runner=lambda cmd, cwd=None, timeout=0: (calls.append((cmd, cwd)), (0, ""))[1])
    assert pv.installed and pv.site == repo / "node_modules" and calls[0][0][:2] == ["npm", "install"] and calls[0][1] == repo
    monkeypatch.setattr(provision.shutil, "which", lambda name: None)
    pv2 = provision.provision(repo, "typescript_ast")
    assert not pv2.installed and "npm is not on PATH" in pv2.how


def test_RED_eat_refuses_without_a_repo_and_accepts_a_positional(tmp_path, capsys, monkeypatch):
    rc = cli.main(["eat"])
    assert rc == 2 and "name the codebase to eat" in capsys.readouterr().err
    rc = cli.main(["eat", str(tmp_path / "nowhere")])
    assert rc == 2 and "not a directory" in capsys.readouterr().err
