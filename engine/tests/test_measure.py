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


def test_GREEN_diff_has_a_time_floor_and_never_judges_the_network(tmp_path):
    """graphyos #60: a time moved less than the floor in seconds is a coin, never a regression (0.5 s → 1.0 s
    is +100 % of nothing); a quickstart's clone-and-install seconds are the network's — shown, tagged, never
    a verdict; the engine's own eat-again seconds are still judged."""
    old = json.loads(json.dumps(OLD))
    old["quickstart"] = {"httpx": {"seconds": 5.0, "eat_seconds": 4.5, "provision_seconds": 3.0, "mint_seconds": 1.5,
                                   "eat_again_seconds": 0.5, "eat_again_parsed": 0}}
    new = json.loads(json.dumps(old))
    new["quickstart"]["httpx"]["eat_again_seconds"] = 1.0      # +100 %, 0.5 s: under the floor
    new["quickstart"]["httpx"]["eat_seconds"] = 9.0            # +100 %: the pip install's, shown as network
    new["quickstart"]["httpx"]["provision_seconds"] = 7.5
    new["quickstart"]["httpx"]["seconds"] = 9.6
    lines, bad = measure.diff(old, new)
    assert not bad, bad
    assert any("quickstart.httpx.eat_seconds: 4.5 -> 9.0" in l and l.endswith("network") for l in lines)
    assert any("provision_seconds: 3.0 -> 7.5" in l and l.endswith("network") for l in lines)
    new["quickstart"]["httpx"]["mint_seconds"] = 3.5           # the engine's own cold mint doubled: judged
    _, bad = measure.diff(old, new)
    assert bad == ["quickstart.httpx.mint_seconds 1.5 -> 3.5 (+133%)"]
    new["quickstart"]["httpx"]["mint_seconds"] = 1.5
    assert any("eat_again_seconds: 0.5 -> 1.0" in l and "REGRESSION" not in l and "network" not in l for l in lines)
    new["quickstart"]["httpx"]["eat_again_seconds"] = 2.0      # +300 %, 1.5 s: past the floor, the engine's — a regression
    _, bad = measure.diff(old, new)
    assert bad == ["quickstart.httpx.eat_again_seconds 0.5 -> 2.0 (+300%)"]
    _, bad = measure.diff(old, new, time_floor=2.0)            # the floor is a flag
    assert not bad
    new["floor"]["seconds"] = 66.0                             # +10 %, 6 s: within tolerance, past the floor — not a regression
    new["quickstart"]["httpx"]["eat_again_seconds"] = 0.5
    _, bad = measure.diff(old, new)
    assert not bad


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


# ---------------------------------------------------------------- adoption (graphyos #51): off-box, never in run

def test_GREEN_stranger_showcases_counts_one_url_by_anyone_but_the_owner():
    issues = [{"number": 45, "user": {"login": "omnislash157"}, "body": "showcase please: https://github.com/pallets/click"},
              {"number": 60, "user": {"login": "someone"}, "body": "https://github.com/x/y please"},
              {"number": 61, "user": {"login": "someone"}, "body": "https://github.com/x/y and https://github.com/x/z"},
              {"number": 62, "user": {"login": "bot"}, "pull_request": {}, "body": "https://github.com/x/y"},
              {"number": 63, "user": {"login": "OmniSlash157"}, "body": "https://github.com/x/y"}]
    found = measure.stranger_showcases(issues, "omnislash157")
    assert [f["number"] for f in found] == [60] and found[0]["url"] == "https://github.com/x/y"


def test_GREEN_adoption_names_a_source_that_does_not_answer_never_a_zero(tmp_path, monkeypatch, capsys):
    answers = {"https://api.github.com/repos/o/r": {"stargazers_count": 3, "forks_count": 2, "subscribers_count": 1, "owner": {"login": "o"}},
               "https://pypistats.org/api/packages/d/recent": {"data": {"last_day": 5, "last_week": 6, "last_month": 7}},
               "https://api.github.com/repos/o/r/issues?state=all&per_page=100&page=1":
                   [{"number": 1, "user": {"login": "s"}, "body": "https://github.com/a/b"}]}
    monkeypatch.setattr(measure, "_fetch_json", lambda url, timeout=20.0: (answers[url], None) if url in answers else (None, "HTTP 404"))
    out = tmp_path / "adoption.json"
    assert measure.main(["adoption", "--repo", "o/r", "--dist", "d", "--out", str(out)]) == 0
    line = capsys.readouterr().out.strip()
    assert line.startswith("ADOPTION: stars 3 · forks 2 · pypi day 5 · week 6 · month 7 · stranger showcases 1 · plugin installs absent")
    a = json.loads(out.read_text())
    assert all("source" in v and "fetched_at" in v for v in a.values() if isinstance(v, dict))
    assert a["showcases"]["issues"][0]["author"] == "s" and a["plugin_installs"]["value"] is None
    assert a["plugin_installs"]["source"] == "absent"
    # a source that does not answer: value None with the error named, exit 1 — never a zero
    monkeypatch.setattr(measure, "_fetch_json", lambda url, timeout=20.0: (None, "URLError: down"))
    assert measure.main(["adoption", "--repo", "o/r", "--dist", "d", "--out", str(out)]) == 1
    assert capsys.readouterr().out.startswith("ADOPTION: stars absent · forks absent · pypi absent · stranger showcases absent")
    a = json.loads(out.read_text())
    assert a["stars"]["value"] is None and "down" in a["stars"]["note"] and a["pypi"]["value"] is None
    # the run receipt never carries the key, so diff over two runs never sees it
    assert "adoption" not in measure.flatten({"floor": {"passed": 1}}) and "adoption" not in measure.BETTER


def test_GREEN_the_native_boundary_is_derived_from_the_engines_source():
    """graphyos #61: the engine frames that call straight into duckdb or tree-sitter — the profiler
    cannot see those calls and charges their time to the calling frame."""
    b = measure.native_boundary()
    assert ("container.py", "_write_parquet") in b and ("container.py", "emit") in b and ("container.py", "emit_all") in b
    assert ("traversal.py", "store_walk") in b and ("index_estate.py", "estate_index") in b or ("index_estate.py", "emit_index") in b
    assert ("typescript_ast.py", "mint_records") in b and ("gate.py", "_cited") in b
    assert not any(f == "python_ast.py" for f, _ in b), "ast.parse is a builtin the profiler sees"
    assert not any(f == "farm.py" for f, _ in b), "Spec.parse is the engine's own"
    assert ("cli.py", "main") not in b and ("federated_store.py", "compile_store") not in b, "sqlite's execute is visible"


def test_GREEN_a_lane_is_judged_on_its_hottest_frame_past_the_native_boundary_and_the_clock(tmp_path):
    """The receipt's number: `_write_parquet` at 3 s self over 1.8 s cumulative is duckdb's threads under
    cProfile's clock — NATIVE by the boundary (and an ARTIFACT by the clock); the lane is judged on the
    first frame that is neither. No such frame: null, never a verdict that ends the pass."""
    import marshal
    wp = (str(measure.ENGINE / "graphy" / "container.py"), 102, "_write_parquet")
    poll = ("~", 0, "<method 'poll' of 'select.poll' objects>")
    main = (str(measure.ENGINE / "graphy" / "cli.py"), 1, "main")
    stats = {wp: (62, 62, 3.01, 1.76, {}), poll: (384, 384, 0.906, 0.9, {}), main: (1, 1, 0.3, 5.0, {})}
    prof = tmp_path / "floor-1.prof"
    prof.write_bytes(marshal.dumps(stats))
    out = measure.summarize_profiles(tmp_path)
    assert out["hot"][0].endswith("_write_parquet 3.01s  ENGINE  NATIVE"), out["hot"]
    assert out["stdlib_hot"] is True and out["judged_on"].startswith("~:<method 'poll'"), out
    stats[poll] = (384, 384, 0.2, 0.2, {})
    prof.write_bytes(marshal.dumps(stats))
    out = measure.summarize_profiles(tmp_path)
    assert out["stdlib_hot"] is False and out["judged_on"].startswith("graphy/cli.py:main"), out
    # a thread-inflated stdlib frame past the top three is still found; nothing honest is null
    stats = {wp: (62, 62, 3.01, 1.76, {}), ("~", 0, "<method 'read' of '_io.BufferedReader' objects>"): (9, 9, 0.137, 0.025, {})}
    prof.write_bytes(marshal.dumps(stats))
    out = measure.summarize_profiles(tmp_path)
    assert out["stdlib_hot"] is None and out["judged_on"].startswith("nothing") and "ARTIFACT" in out["hot"][1]
    r = {"floor": out, "tenants": {}, "quickstart": {}, "index": {}}
    assert measure.pass_summary(r)["engine_hot_lanes"] == 0 and measure.pass_summary(r)["unjudged"] == ["floor"]
