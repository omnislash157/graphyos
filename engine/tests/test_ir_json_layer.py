
from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from graphy.cartograph import resolve_graph
from graphy.native_json_graph_ir import (
    _CLASSIFICATION_TABLE,
    _classify_path,
    load_graph_ir,
    load_override_ir,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "fastapi_graph"


def _mk_graph(d: Path, marker: str) -> None:
    d.mkdir(parents=True)
    (d / "nodes.json").write_text(json.dumps({"marker": marker}), encoding="utf-8")


HOST_TENANT = "host" + "_codebase"



def test_load_graph_ir_pins_fixture_counts():
    ir = load_graph_ir(FIXTURE_DIR)
    assert len(ir.nodes) == 507
    assert len(ir.edges) + len(ir.residuals) == 3715
    raw_edges = json.loads((FIXTURE_DIR / "edges.json").read_text(encoding="utf-8"))
    assert len(raw_edges) == 3715



def test_real_dir_resolves_to_itself(tmp_path):
    d = tmp_path / "real_graph"
    _mk_graph(d, "solo")
    out = resolve_graph(d)
    assert out == d.resolve()
    assert json.loads((out / "nodes.json").read_text())["marker"] == "solo"



def test_sibling_symlink_pins_to_versioned_realpath(tmp_path):
    data = tmp_path / "data"
    v1 = data / "bar_graph.v1"
    _mk_graph(v1, "v1")
    surface = data / "bar_graph"
    surface.symlink_to(v1.name, target_is_directory=True)

    out = resolve_graph(surface)
    assert out == v1.resolve(), f"versioned graph must return the REALPATH pin, got {out}"
    assert json.loads((out / "nodes.json").read_text())["marker"] == "v1"



def test_T7_escaping_symlink_returns_read_surface(tmp_path):
    real = tmp_path / "graph_farm" / "foo_graph"
    _mk_graph(real, "v1")
    surface = tmp_path / "data" / "foo_graph"
    surface.parent.mkdir(parents=True)
    surface.symlink_to(Path("../graph_farm/foo_graph"), target_is_directory=True)

    out = resolve_graph(surface)
    assert out == surface, f"farm graph must return the READ-SURFACE, got {out}"
    assert "graph_farm" not in [p.name for p in out.parents]
    assert json.loads((out / "nodes.json").read_text())["marker"] == "v1"



def test_transient_enoint_retry_materializes_on_first_sleep(tmp_path, monkeypatch):
    real = tmp_path / "real" / "foo_graph.v1"
    data = tmp_path / "data"
    data.mkdir(parents=True)
    surface = data / "foo_graph"
    surface.symlink_to(Path("../real/foo_graph.v1"), target_is_directory=True)

    calls = {"n": 0}

    def _materialize_on_first_sleep(_seconds):
        calls["n"] += 1
        if calls["n"] == 1:
            _mk_graph(real, "v1")

    monkeypatch.setattr("graphy.cartograph.time.sleep", _materialize_on_first_sleep)

    out = resolve_graph(surface)
    assert out == real.resolve(), "the retry must return the STRICT resolution, not a fallback"
    assert out.exists(), "the retry must have materialized the target via the first sleep"
    assert calls["n"] == 1, "the retry lane must engage time.sleep exactly once"


def test_missing_forever_resolves_non_strict_and_loader_fails_loud(tmp_path, monkeypatch):
    absent = tmp_path / "data" / "gone_graph"
    monkeypatch.setattr("graphy.cartograph.time.sleep", lambda _seconds: None)

    out = resolve_graph(absent)
    assert out == absent.resolve(), "exhausted retries must resolve non-strict, never raise"
    assert not out.exists()

    with pytest.raises(FileNotFoundError):
        load_graph_ir(absent)



def _residual_prefixes_value():
    tree = ast.parse(inspect.getsource(load_override_ir))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "residual_prefixes"
        ):
            expr = ast.Expression(node.value)
            return eval(compile(expr, "<residual_prefixes>", "eval"), {"frozenset": frozenset}, {})
    raise AssertionError("residual_prefixes assignment not found in load_override_ir")


HOST_TABLE_LENGTH = 19
DROPPED_HOST_KEYED_ROWS = 4


def test_classification_delta_is_exact_not_exemplars():
    host_keyed = [row for row in _CLASSIFICATION_TABLE if HOST_TENANT in row[0]]
    assert host_keyed == []

    assert len(_CLASSIFICATION_TABLE) == HOST_TABLE_LENGTH - DROPPED_HOST_KEYED_ROWS
    assert len(_CLASSIFICATION_TABLE) == 15

    assert _residual_prefixes_value() == frozenset()


def test_surviving_row_classifies_to_declared_kind():
    assert _classify_path(("alias_overrides", "fastapi")) == "alias"
    assert _classify_path(("substrates", "frontend", "specifier_overrides", "x")) == "alias"
    assert _classify_path(("registered_joins", "literal_joins", "pkg://x")) == "federation_policy"
    assert _classify_path(("projection_registry", "visual://x")) == "projection"


def test_host_substrate_shaped_path_takes_the_documented_fallthrough():
    assert _classify_path(("substrates", HOST_TENANT, "app_route_overrides", "/health")) is None
    assert _classify_path(("substrates", HOST_TENANT, "route_handler_overrides", "_unbound")) is None


def test_host_substrate_shaped_leaf_raises_in_loader(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({
        "substrates": {
            HOST_TENANT: {
                "app_route_overrides": {"/health": "health_route"},
            }
        }
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="no locked classification"):
        load_override_ir(reg, tenant_id="tenant")


def test_surviving_row_classifies_in_loader(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({
        "alias_overrides": {"fastapi": "starlette"},
    }), encoding="utf-8")
    ir = load_override_ir(reg, tenant_id="tenant")
    assert len(ir.records) == 1
    assert ir.records[0].record_kind == "alias"
    assert ir.records[0].source_path == "/alias_overrides/fastapi"
