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
