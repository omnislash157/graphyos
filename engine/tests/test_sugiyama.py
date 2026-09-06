
from __future__ import annotations

import json
import pathlib

import pytest

from graphy.sugiyama import (
    Layout,
    draw,
    from_dsl,
    from_graph,
    layout,
    layout_json,
    render,
)

HERE = pathlib.Path(__file__).resolve().parent
FASTAPI = HERE / "fixtures" / "fastapi_graph"
BOX_GLYPHS = "─│┌┐└┘├┤"


def _demo_graph():
    nodes = ["a", "b", "c"]
    edges = [("a", "b"), ("b", "c")]
    labels = {"a": "alpha", "b": "beta", "c": "gamma"}
    return nodes, edges, labels




def test_draw_renders_readable_ascii_with_semantic_labels():
    out = draw(*_demo_graph(), title="demo", color=False)
    assert any(g in out for g in BOX_GLYPHS), "no box-drawing glyphs"
    assert "alpha" in out and "beta" in out and "gamma" in out
    assert "demo" in out


def test_layout_and_render_agree_with_draw():
    nodes, edges, labels = _demo_graph()
    lo = layout(nodes, edges, labels)
    assert isinstance(lo, Layout)
    assert render(lo, title="render", color=False) == draw(
        nodes, edges, labels, title="render", color=False
    )


def test_layout_json_emits_visual_projection():
    lo = layout(["a", "b"], [("a", "b")])
    js = layout_json(lo, graph_id="demo", adapter="test")
    assert js["id"] == "visual://demo"
    assert js["meta"]["adapter"] == "test"
    assert {n["id"] for n in js["nodes"]} == {"a", "b"}
    assert js["edges"] == [{"from": "a", "to": "b", "reversed": False}]




def test_from_dsl_parses_header_edges_labels():
    nodes, edges, labels, title, orient = from_dsl(
        "My Graph · TB\n"
        "a -> b, c\n"
        "b : label bee\n"
    )
    assert title == "My Graph"
    assert orient == "TB"
    assert "a" in nodes and "b" in nodes and "c" in nodes
    assert ("a", "b") in edges and ("a", "c") in edges
    assert labels["b"] == "label bee"


def test_from_dsl_rejects_empty_and_bad_orient():
    with pytest.raises(ValueError, match="empty DSL"):
        from_dsl("")
    with pytest.raises(ValueError, match="orient"):
        from_dsl("title · XX\na -> b\n")


def test_from_dsl_draws_end_to_end():
    nodes, edges, labels, title, orient = from_dsl(
        "Chain · LR\nroot -> mid -> leaf\nmid : middle\n"
    )
    out = draw(nodes, edges, labels, title=title, orient=orient, color=False)
    assert any(g in out for g in BOX_GLYPHS)
    assert "middle" in out


def test_from_graph_loads_a_substrate_shard():
    nodes, edges, labels = from_graph(str(FASTAPI), limit=10)
    assert nodes, "from_graph produced no nodes"
    assert len(nodes) <= 10
    for n in nodes:
        assert n in labels




def test_sugiyama_imports_no_host_package():
    import graphy.sugiyama as mod
    import ast
    import inspect
    host_sdk = "host" + "_sdk"
    hosts = (host_sdk, "ascii_arch", "ascii_graph_poc",
             "recon_tools", "repo_substrate", "cartographer")
    tree = ast.parse(inspect.getsource(mod))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(hosts), \
                    f"sugiyama imports the host package {alias.name!r}"
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(hosts), \
                f"sugiyama imports the host package {node.module!r}"
