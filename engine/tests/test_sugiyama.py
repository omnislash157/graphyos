
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


def test_GREEN_inversion_crossing_count_equals_the_pairwise_count_on_random_bilayers():
    """graphyos #18: the bilayer crossing count is an inversion count. Random bilayers — sparse,
    dense, with parallel edges, with nodes that reach nothing, upper nodes absent from adj — fed to
    both counters, the same integer every time; the layout that decides on it cannot move."""
    import random
    from graphy.sugiyama import _count_crossings, _count_crossings_pairwise
    rng = random.Random(18)
    for trial in range(400):
        na, nb = rng.randint(0, 14), rng.randint(0, 14)
        a = [f"u{i}" for i in range(na)]
        b = [f"v{i}" for i in range(nb)]
        rng.shuffle(a)
        rng.shuffle(b)
        p = rng.choice((0.05, 0.3, 0.8))
        adj = {}
        for u in a:
            vs = [v for v in b if rng.random() < p]
            if rng.random() < 0.2 and vs:
                vs.append(rng.choice(vs))          # a parallel edge
            if rng.random() < 0.2:
                vs.append("elsewhere")             # a target outside the lower layer
            if vs or rng.random() < 0.5:
                adj[u] = vs
        assert _count_crossings(a, b, adj) == _count_crossings_pairwise(a, b, adj), (trial, a, b, adj)
    # the textbook bilayer: two edges that cross, one that does not
    assert _count_crossings(["x", "y"], ["p", "q"], {"x": ["q"], "y": ["p"]}) == 1
    assert _count_crossings(["x", "y"], ["p", "q"], {"x": ["p"], "y": ["q"]}) == 0
    assert _count_crossings(["x", "y"], ["p", "q"], {"x": ["p", "q"], "y": ["p", "q"]}) == 1


def test_GREEN_the_canvas_renders_the_drawing_not_the_rectangle_and_the_same_bytes():
    """Every writer records the row's last written column and render stops there, emitting the
    blank tail as one run — the same text a walk over every cell produced, including the full-width
    rows and the colour reset before a blank tail (graphyos #31)."""
    import graphy.sugiyama as S

    def reference(cv):                     # the cell-by-cell render this replaced, verbatim
        rows = []
        for r in range(cv.h):
            out, last = [], None
            for c in range(cv.w):
                if cv.cont[r][c]:
                    continue
                g = cv.glyph[r][c]
                if g == " " and cv.bits[r][c]:
                    table = S.THEMES["heavy" if cv.weight[r][c] == 2 else "light"]
                    g = table.get(cv.bits[r][c], " ")
                col = cv.color[r][c]
                if col != last:
                    out.append("\033[0m" + S._ansi(col))
                    last = col
                out.append(g)
            out.append("\033[0m")
            rows.append("".join(out).rstrip())
        return "\n".join(rows)

    cv = S.Canvas(40, 9)
    cv.tile(1, 2, "wide 🌉 glyph", color=3)          # a wide glyph: a continuation cell
    cv.hroad(3, 1, 30, color=5)                       # a coloured road, then blank to the edge: the reset comes first
    cv.vroad(10, 2, 6, weight=2)                      # a heavy vertical road crossing it
    cv.cross(3, 10, color=7)
    cv.bridge(5, 20)
    cv.hroad(7, 0, 39)                                # a road to the last column: no tail
    assert cv.last == [-1, 14, 10, 30, 10, 21, 10, 39, -1], cv.last
    text = cv.render()
    assert text == reference(cv)
    lines = text.split("\n")
    assert lines[0] == " " * 40 + "\033[0m" and lines[8] == lines[0], "an untouched row is full width, as before"
    assert "\033[0m" + " " * 9 + "\033[0m" in lines[3], "the colour resets before the blank tail"
    assert len(lines[7]) == 40 + len("\033[0m")
