"""The one-liner: eat provisions the repo's dependencies itself and says what it did. A floor with
pip and npm injected; the proof is the three cold eats in RECON."""
from __future__ import annotations

import json
import sys
import sysconfig
from pathlib import Path

import pytest

import graphy.cli as cli
from graphy import provision


def _fake_venv(venv: Path, *, layout: str, version: str = "3.12.3") -> None:
    """What `python -m venv` leaves behind, on either host: the cfg naming its version, the
    interpreter and an empty site-packages."""
    venv.mkdir(parents=True, exist_ok=True)
    (venv / "pyvenv.cfg").write_text(f"home = /usr/bin\nversion = {version}\n")
    if layout == "nt":
        (venv / "Scripts").mkdir()
        (venv / "Scripts" / "python.exe").write_text("")
        (venv / "Lib" / "site-packages").mkdir(parents=True)
    else:
        (venv / "bin").mkdir()
        (venv / "bin" / "python").write_text("")
        (venv / "lib" / f"python{version.rsplit('.', 1)[0]}" / "site-packages").mkdir(parents=True)


def test_GREEN_python_repo_gets_a_venv_and_pip_install(tmp_path):
    repo = tmp_path / "pkg"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[project]\nname="pkg"\nversion="0"\n')
    calls = []

    def runner(cmd, cwd=None, timeout=0):
        calls.append(cmd)
        if cmd[1:3] == ["-m", "venv"]:
            _fake_venv(Path(cmd[3]), layout="posix")
        return 0, ""

    pv = provision.provision(repo, "python_ast", runner=runner)
    assert pv.installed and pv.site == repo / ".graphy" / "venv" / "lib" / "python3.12" / "site-packages"
    assert calls[0][1:3] == ["-m", "venv"] and calls[1][-1] == str(repo) and "pip" in calls[1]
    # the receipt beside the venv pins the declaration: a second provision under the same
    # pyproject skips pip and says so; the declaration moving runs it again
    receipt = repo / ".graphy" / "venv" / provision.RECEIPT_NAME
    assert receipt.is_file()
    n = len(calls)
    skipped = provision.provision(repo, "python_ast", runner=runner)
    assert skipped.installed and "skipped" in skipped.how and len(calls) == n
    (repo / "pyproject.toml").write_text('[project]\nname="pkg"\nversion="1"\ndependencies=["x"]\n')
    again = provision.provision(repo, "python_ast", runner=runner)
    assert again.installed and "skipped" not in again.how and len(calls) == n + 1 and "pip" in calls[-1]
    # a repo that will not install is minted alone, and the line says so — and leaves no receipt
    receipt.unlink()
    pv2 = provision.provision(repo, "python_ast", runner=lambda cmd, cwd=None, timeout=0: (1, "boom") if "pip" in cmd else (0, ""))
    assert not pv2.installed and "did not pip-install" in pv2.how and "boom" in pv2.how
    assert not receipt.exists()
    # no metadata at all: no pip is run
    bare = tmp_path / "bare"
    (bare / "x").mkdir(parents=True)
    pv3 = provision.provision(bare, "python_ast", runner=runner)
    assert not pv3.installed and "no pyproject.toml" in pv3.how


def test_RED_venv_layout_is_sysconfig_on_both_hosts(tmp_path):
    """Red-team finding 9: the venv's interpreter and site-packages were `bin/python` and a glob
    over `lib/python*` — on Windows a venv is `Scripts\\python.exe` and `Lib\\site-packages`, and
    `eat` died with `has no site-packages`. Now `venv_layout` asks `sysconfig` for the scheme's
    paths under the venv, with the version the venv's own `pyvenv.cfg` names."""
    posix = tmp_path / "p"
    _fake_venv(posix, layout="posix", version="3.11.9")
    lay = provision.venv_layout(posix, os_name="posix")
    assert lay.scheme == "posix_prefix" and lay.python == posix / "bin" / "python"
    assert lay.site == posix / "lib" / "python3.11" / "site-packages" and lay.site.is_dir()
    assert lay.scripts == posix / "bin"
    nt = tmp_path / "w"
    _fake_venv(nt, layout="nt", version="3.12.4")
    lay = provision.venv_layout(nt, os_name="nt")
    assert lay.scheme == "nt" and lay.python == nt / "Scripts" / "python.exe"
    assert lay.site == nt / "Lib" / "site-packages" and lay.site.is_dir() and lay.scripts == nt / "Scripts"
    # no cfg: the running interpreter's version, never a guess from a glob
    bare = tmp_path / "b"
    bare.mkdir()
    assert provision.venv_layout(bare, os_name="posix").site == bare / "lib" / (
        "python" + sysconfig.get_config_var("py_version_short")) / "site-packages"
    # the box's own venv resolves to where the live interpreter really reads from
    if sys.prefix != sys.base_prefix:
        live = provision.venv_layout(sys.prefix)
        assert live.python.exists() and live.site.is_dir()
        assert live.site == Path(sysconfig.get_paths()["purelib"])
    # eat on a Windows host: the venv provisioned by the fake runner lays out as nt, and the
    # provision resolves it — the old code raised `has no site-packages` here
    repo = tmp_path / "pkg"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[project]\nname="pkg"\nversion="0"\n')
    calls = []

    def runner(cmd, cwd=None, timeout=0):
        calls.append(cmd)
        if cmd[1:3] == ["-m", "venv"]:
            _fake_venv(Path(cmd[3]), layout="nt")
        return 0, ""

    pv = provision.provision(repo, "python_ast", runner=runner, os_name="nt")
    venv = repo / ".graphy" / "venv"
    assert pv.installed and pv.site == venv / "Lib" / "site-packages"
    assert calls[1][0] == str(venv / "Scripts" / "python.exe") and "pip" in calls[1]
    # a venv whose site-packages is missing is named with the path looked for and the layout
    broken = tmp_path / "broken"
    (broken / "x").mkdir(parents=True)
    (broken / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n")
    (broken / ".graphy" / "venv").mkdir(parents=True)
    (broken / ".graphy" / "venv" / "pyvenv.cfg").write_text("version = 3.12.0\n")
    with pytest.raises(RuntimeError, match=r"no site-packages at .*lib/python3\.12/site-packages \(posix_prefix layout\)"):
        provision.provision(broken, "python_ast", runner=runner)


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
