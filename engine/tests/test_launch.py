"""A repo-local `graphy/` that shadows the engine is refused by name, never an ImportError (graphyos #83)."""

from __future__ import annotations

import importlib.machinery
import os
import subprocess
import sys
from pathlib import Path

import _graphy_launch

ENGINE = Path(_graphy_launch.__file__).resolve().parent


def _launch(tmp_path: Path, *argv: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(tmp_path), str(ENGINE)])}
    code = "import _graphy_launch; raise SystemExit(_graphy_launch.main())"
    return subprocess.run([sys.executable, "-c", code, *argv], cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=60)


def test_an_empty_graphy_package_on_the_path_is_refused_naming_both_paths(tmp_path):
    (tmp_path / "graphy").mkdir()
    (tmp_path / "graphy" / "__init__.py").write_text("")
    proc = _launch(tmp_path, "--help")
    assert proc.returncode == 2, proc.stderr
    assert "No module named" not in proc.stderr
    assert "REFUSED" in proc.stderr
    assert str(tmp_path / "graphy") in proc.stderr
    assert str(ENGINE / "graphy") in proc.stderr


def test_the_engine_itself_launches(tmp_path):
    proc = _launch(tmp_path, "--help")
    assert proc.returncode == 0, proc.stderr
    assert "REFUSED" not in proc.stderr


def test_a_namespace_package_is_refused_as_one():
    spec = importlib.machinery.ModuleSpec("graphy", None, is_package=True)
    spec.submodule_search_locations = ["/elsewhere/graphy"]
    reason = _graphy_launch.shadowing(spec)
    assert reason and "namespace package" in reason and "/elsewhere/graphy" in reason


def test_the_intended_spec_passes():
    assert _graphy_launch.shadowing(importlib.util.find_spec("graphy")) is None


def test_both_console_scripts_enter_through_the_launcher():
    import re
    text = (ENGINE / "pyproject.toml").read_text()
    scripts = re.search(r"^\[project\.scripts\]\n(.*?)(?=^\[)", text, re.S | re.M).group(1)
    entries = dict(re.findall(r'^(\w+)\s*=\s*"([^"]+)"', scripts, re.M))
    assert entries == {"graphy": "_graphy_launch:main", "graphyos": "_graphy_launch:main"}
