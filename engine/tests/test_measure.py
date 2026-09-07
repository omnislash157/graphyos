"""The receipt's diff: a regression is named, tolerance holds, a verdict flipping is red. A floor;
the receipt itself is RECON's."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("measure", Path(__file__).parents[2] / "measure.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)

OLD = {"floor": {"passed": 400, "failed": 0, "seconds": 60.0}, "gate": {"ok": True, "seconds": 90.0},
       "wheel": {"wheel_bytes": 240000}, "tenants": {"fastapi": {"ok": True, "seconds": 3.0, "shards": 10, "nodes": 5126}}}


def test_GREEN_diff_names_better_and_regressions_with_tolerance():
    new = json.loads(json.dumps(OLD))
    new["floor"]["passed"] = 405                      # better
    new["floor"]["seconds"] = 66.0                    # +10%: within tolerance
    lines, bad = measure.diff(OLD, new)
    assert not bad and any("floor.passed: 400 -> 405" in l and "better" in l for l in lines)
    new["gate"]["seconds"] = 120.0                    # +33%: a regression
    new["tenants"]["fastapi"]["shards"] = 9           # a count moved the wrong way
    new["wheel"]["wheel_bytes"] = 200000              # better
    lines, bad = measure.diff(OLD, new)
    assert any("gate.seconds" in b for b in bad) and any("fastapi.shards 10 -> 9" in b for b in bad)
    assert not any("wheel_bytes" in b for b in bad)
    new["gate"]["ok"] = False
    _, bad = measure.diff(OLD, new)
    assert any("gate.ok flipped to false" in b for b in bad)


def test_GREEN_cli_diff_exit_codes(tmp_path, capsys):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(OLD)); b.write_text(json.dumps(OLD))
    assert measure.main(["diff", str(a), str(b)]) == 0 and "no number moved" in capsys.readouterr().out
    worse = json.loads(json.dumps(OLD)); worse["floor"]["failed"] = 2
    b.write_text(json.dumps(worse))
    assert measure.main(["diff", str(a), str(b)]) == 1 and "MEASURE REGRESSION" in capsys.readouterr().out


def test_GREEN_profile_dir_makes_every_verb_leave_its_stats_and_rss(tmp_path, monkeypatch):
    """GRAPHY_PROFILE_DIR set: the verb runs under cProfile and leaves <verb>-<pid>.prof + .json
    (verb · argv · seconds · rss_kb). Unset: nothing is written and nothing is imported for it."""
    import subprocess
    import sys
    d = tmp_path / "prof"
    env = {"GRAPHY_PROFILE_DIR": str(d)}
    p = subprocess.run([sys.executable, "-m", "graphy", "index", "--index", str(tmp_path / "no-index")],
                       env={**__import__("os").environ, **env}, capture_output=True, text=True)
    profs, sides = sorted(d.glob("index-*.prof")), sorted(d.glob("index-*.json"))
    assert len(profs) == 1 and len(sides) == 1, (p.stdout, p.stderr)
    side = json.loads(sides[0].read_text())
    assert side["verb"] == "index" and side["argv"][0] == "index" and side["rss_kb"] > 0 and side["seconds"] >= 0
    clean = tmp_path / "clean"
    subprocess.run([sys.executable, "-m", "graphy"], env={k: v for k, v in __import__("os").environ.items()
                                                          if k != "GRAPHY_PROFILE_DIR"}, capture_output=True, cwd=str(tmp_path))
    assert not clean.exists() and not list(tmp_path.glob("*.prof"))


def test_GREEN_summarize_names_the_hot_frames_the_rss_and_whether_the_engine_is_hot(tmp_path):
    import cProfile
    d = tmp_path / "lane"; d.mkdir()

    def burn():
        return sum(i * i for i in range(200000))
    prof = cProfile.Profile(); prof.runcall(burn); prof.dump_stats(str(d / "walk-1.prof"))
    (d / "walk-1.json").write_text(json.dumps({"verb": "walk", "argv": ["walk"], "seconds": 0.1, "rss_kb": 50000}))
    (d / "build-2.json").write_text(json.dumps({"verb": "build", "argv": ["build"], "seconds": 0.2, "rss_kb": 91000}))
    s = measure.summarize_profiles(d)
    assert s["verbs"] == 1 and len(s["hot"]) <= measure.HOT_N and any("burn" in h or "genexpr" in h for h in s["hot"])
    assert s["rss_kb"] == 91000 and s["rss_verb"] == "build"
    assert s["stdlib_hot"] is True                      # a test file is not the engine
    assert measure._engine_owned(str(measure.ENGINE / "graphy" / "cli.py"))
    assert measure._engine_owned("/v/lib/python3.12/site-packages/graphy/ir.py")
    assert not measure._engine_owned(str(measure.ENGINE / "tests" / "test_x.py"))
    assert not measure._engine_owned("/home/u/graphy/.venv/lib/python3.12/site-packages/duckdb/__init__.py")
    assert "ENGINE" in measure._fmt_frame(str(measure.ENGINE / "graphy" / "smash.py"), 1, "mint", 1.5)


def test_GREEN_the_pass_number_counts_engine_hot_lanes_and_rss_regresses_like_a_time():
    r = {"floor": {"stdlib_hot": True}, "tenants": {"a": {"stdlib_hot": False}, "b": {"stdlib_hot": True}},
         "quickstart": {"q": {"stdlib_hot": False}}, "index": {}}
    p = measure.pass_summary(r)
    assert p["engine_hot_lanes"] == 2 and p["engine_hot"] == ["quickstart.q", "tenants.a"]
    old = {"pass": {"engine_hot_lanes": 2}, "tenants": {"a": {"rss_kb": 100000, "stdlib_hot": False}}}
    new = {"pass": {"engine_hot_lanes": 0}, "tenants": {"a": {"rss_kb": 110000, "stdlib_hot": True}}}
    lines, bad = measure.diff(old, new)
    assert not bad and any("engine_hot_lanes: 2 -> 0" in l and "better" in l for l in lines)
    new["tenants"]["a"]["rss_kb"] = 130000              # +30%: past tolerance
    new["tenants"]["a"]["stdlib_hot"] = False
    new["pass"]["engine_hot_lanes"] = 3
    _, bad = measure.diff(old, new)
    assert any("rss_kb" in b for b in bad) and any("engine_hot_lanes" in b for b in bad)
    old2 = {"t": {"stdlib_hot": True}}; new2 = {"t": {"stdlib_hot": False}}
    _, bad = measure.diff(old2, new2)
    assert any("stdlib_hot flipped to false" in b for b in bad)
