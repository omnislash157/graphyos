"""The burden invariants, each refused by name on synthetic growth. A floor; the gate runs the
real one over the engine."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("burden", Path(__file__).parents[2] / "burden.py")
burden = importlib.util.module_from_spec(spec)
spec.loader.exec_module(burden)
RULES = json.loads((Path(__file__).parents[2] / "burden.json").read_text())


def test_RED_a_runtime_dependency_or_an_undeclared_extra_is_refused(tmp_path):
    pp = tmp_path / "pyproject.toml"
    pp.write_text('[project]\nname="x"\nversion="0"\ndependencies=[]\n[project.optional-dependencies]\nestate=["duckdb>=1"]\n')
    assert burden.check_dependencies(pp, RULES) == []
    pp.write_text('[project]\nname="x"\nversion="0"\ndependencies=["requests>=2"]\n[project.optional-dependencies]\nviz=["matplotlib"]\nestate=["duckdb","pandas"]\n')
    red = burden.check_dependencies(pp, RULES)
    assert any("runtime dependency 'requests>=2'" in r for r in red) and any("extra 'viz'" in r for r in red) and any("'pandas'" in r for r in red)


def test_RED_a_host_and_a_program_off_the_list_are_named_with_their_line(tmp_path):
    root = tmp_path / "graphy"
    root.mkdir()
    (root / "a.py").write_text('import subprocess, shutil\nURL = "https://pypi.org/x"\nBAD = "https://evil.example/x"\n'
                              'GIT_PATH = shutil.which("git")\n'
                              'def run(cmd, timeout=1):\n    return subprocess.run(cmd, timeout=timeout)\n'
                              'def ok(python):\n    subprocess.run([GIT_PATH, "status"])\n    cmd = ["npm", "i"]\n    subprocess.run(cmd)\n'
                              '    base = [python, "-m", "graphy"]\n    run(base + ["check"])\n    run([str(python), "-m", "pip"])\n'
                              'def bad():\n    subprocess.run(["curl", "x"])\n    run(["wget", "y"])\n')
    red, n = burden.scan_hosts(root, RULES)
    assert red == ["graphy/a.py:3: host evil.example is not in burden.json"] and n == 2
    red, n = burden.scan_subprocess(root, RULES)
    assert sorted(red) == ["graphy/a.py:15: subprocess target 'curl' is not in burden.json",
                           "graphy/a.py:16: subprocess target 'wget' is not in burden.json"]


def test_GREEN_the_wheel_cap(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "graphyos-9-py3-none-any.whl").write_bytes(b"x" * 10)
    assert burden.check_wheel(dist, {"wheel_max_bytes": 100})[0] == []
    red, note = burden.check_wheel(dist, {"wheel_max_bytes": 5})
    assert red and "over the 5 byte cap" in red[0]
    assert burden.check_wheel(tmp_path / "nowhere", RULES)[1].endswith("SKIPPED")
