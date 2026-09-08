"""The draw door: the codebase drawn from the store — units, pillars, an arm, a neighbourhood —
as ASCII and as a checked HTML+SVG page. A floor; the proof is the FastAPI atlas in RECON."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import graphy.cli as cli
import graphy.draw as draw
import graphy.fanout as fanout
import graphy.federated_store as fs
import graphy.sugiyama as sugi
from test_doors import SEED, _fixture


def _cut(tmp_path: Path) -> Path:
    p = tmp_path / "partition.json"
    p.write_text(json.dumps({"groups": {"ROUTING": ["fastapi.routing"], "DEPS": ["fastapi.dependencies"]}, "rest": "EDGE"}))
    return p


def test_GREEN_units_pillars_arm_and_neighbourhood_draw_from_the_store(tmp_path):
    tenant, desc, roster = _fixture(tmp_path)
    store = fs.open_for(roster, tenant=tenant, tenant_id="doors")
    u = draw.units(store, "fastapi", depth=2, min_weight=1)
    assert "fastapi.routing" in u.nodes and u.edges and u.dropped >= 0
    text = draw.render(u, lr=True)
    assert "routing" in text and "[LR]" in text
    cut = fanout.load_partition(_cut(tmp_path))
    p = draw.pillars(store, "fastapi", cut)
    assert set(p.nodes) >= {"ROUTING", "DEPS"} and ("ROUTING", "DEPS") in p.edges
    a = draw.arm(store, "fastapi", cut, "ROUTING")
    assert "fastapi.routing" in a.nodes and any(n.startswith("[") for n in a.nodes)
    n = draw.neighbourhood(store, SEED, radius=1)
    assert SEED in n.nodes and "widgets://func/widgets.gadget" in n.nodes
    assert n.labels["widgets://func/widgets.gadget"].endswith("·widgets") and n.meta[SEED]["file"] == "fastapi/routing.py"
    with pytest.raises(draw.DrawError, match="not a group"):
        draw.arm(store, "fastapi", cut, "NOPE")
    with pytest.raises(draw.DrawError, match="not a node"):
        draw.neighbourhood(store, "nowhere://x/y")


def test_GREEN_html_page_checks_green_and_a_doctored_one_red(tmp_path):
    tenant, desc, roster = _fixture(tmp_path)
    store = fs.open_for(roster, tenant=tenant, tenant_id="doors")
    pic = draw.neighbourhood(store, SEED, radius=1)
    page = tmp_path / "n.html"
    page.write_text(draw.render(pic, emit="html", lr=True, interactive=True), encoding="utf-8")
    assert sugi.check_artifact(page) == []
    html = page.read_text()
    assert "routing.py" in html and "https://" not in html and 'data-interactive="1"' in html
    bad = tmp_path / "bad.html"
    bad.write_text(html.replace('[data-theme="dark"]', "").replace("<script", "<!--"), encoding="utf-8")
    red = sugi.check_artifact(bad)
    assert any("data-theme" in r for r in red) and any("no <script>" in r for r in red)


def test_GREEN_atlas_and_cli(tmp_path, capsys):
    tenant, desc, roster = _fixture(tmp_path)
    cut = _cut(tmp_path)
    rc = cli.main(["draw", "--tenant", str(desc), "--tenant-id", "doors", "--corpus", "fastapi", "--pillars",
                   "--partition", str(cut), "--lr"])
    out = capsys.readouterr().out
    assert rc == 0 and "ROUTING" in out and "DRAW: " in out
    rc = cli.main(["draw", "--tenant", str(desc), "--tenant-id", "doors", "--symbol", "get_request_handler",
                   "--radius", "1", "--emit", "html", "-o", str(tmp_path / "s.html")])
    assert rc == 0 and "CHECK GREEN" in capsys.readouterr().out
    rc = cli.main(["draw", "--check", str(tmp_path / "s.html")])
    assert rc == 0 and "CHECK GREEN" in capsys.readouterr().out
    rc = cli.main(["draw", "--tenant", str(desc), "--tenant-id", "doors", "--corpus", "fastapi", "--partition", str(cut),
                   "--atlas", str(tmp_path / "atlas")])
    assert rc == 0 and "ATLAS OK: 4 picture(s)" in capsys.readouterr().out
    receipt = json.loads((tmp_path / "atlas" / draw.RECEIPT).read_text())
    assert set(receipt["pictures"]) == {"PILLARS", "UNITS", "ROUTING", "DEPS"} and len(receipt["files"]) == 8
    rc = cli.main(["draw", "--tenant", str(desc), "--tenant-id", "doors", "--symbol", "zzz_nothing"])
    assert rc == 1 and "DRAW UNANSWERABLE" in capsys.readouterr().err
    rc = cli.main(["draw", "--tenant", str(desc), "--tenant-id", "doors"])
    assert rc == 2 and "name one with --corpus" in capsys.readouterr().err


def test_GREEN_the_atlas_lays_each_picture_out_once_and_places_it_once(tmp_path, monkeypatch):
    """Two emits per picture, ascii and html, share one layout and one coordinate pass: the atlas
    hands render the layout it computed, and _placed memoizes the pass per orientation on the
    layout — the same files as two independent renders (graphyos #30)."""
    import graphy.sugiyama as S
    tenant, desc, roster = _fixture(tmp_path)
    cut = fanout.load_partition(_cut(tmp_path))
    store = fs.open_for(roster, tenant=tenant, tenant_id="doors")
    plain = draw.atlas(store, "fastapi", cut, tmp_path / "plain")
    calls = {"layout": 0, "place": 0}
    real_layout, real_place = S.layout, S._place
    monkeypatch.setattr(S, "layout", lambda *a, **k: (calls.__setitem__("layout", calls["layout"] + 1), real_layout(*a, **k))[1])
    monkeypatch.setattr(S, "_place", lambda *a, **k: (calls.__setitem__("place", calls["place"] + 1), real_place(*a, **k))[1])
    spied = draw.atlas(store, "fastapi", cut, tmp_path / "spied")
    n = len(spied["pictures"])
    assert n >= 3 and calls == {"layout": n, "place": n}, (n, calls)
    assert spied["files"] == plain["files"], "the same bytes as before: a layout once, an emit twice"
    pic = draw.units(store, "fastapi")
    lo = S.layout(pic.nodes, pic.edges, pic.labels)
    assert draw.render(pic, emit="ascii", lr=True, layout=lo) == draw.render(pic, emit="ascii", lr=True)
    assert set(lo.placed) == {False}, "the LR pass was memoized on the layout, and only it"


def test_GREEN_svg_emit_is_a_standalone_file_for_a_readme(tmp_path, capsys):
    tenant, desc, roster = _fixture(tmp_path)
    store = fs.open_for(roster, tenant=tenant, tenant_id="doors")
    cut = fanout.load_partition(_cut(tmp_path))
    pic = draw.pillars(store, "fastapi", cut)
    svg = draw.render(pic, emit="svg", lr=True)
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox=') and svg.rstrip().endswith("</svg>")
    assert "<script" not in svg and 'data-interactive' not in svg and "https://" not in svg
    assert "prefers-color-scheme: dark" in svg and '[data-theme="dark"]' in svg and ".card {" in svg and "body {" not in svg
    import xml.dom.minidom
    xml.dom.minidom.parseString(svg)                                   # one well-formed document, as an <img> reads it
    out = tmp_path / "p.svg"
    rc = cli.main(["draw", "--tenant", str(desc), "--tenant-id", "doors", "--corpus", "fastapi", "--pillars",
                   "--partition", str(_cut(tmp_path)), "--lr", "--emit", "svg", "-o", str(out)])
    assert rc == 0 and "CHECK GREEN" in capsys.readouterr().out
    assert out.read_text() == svg                                      # the same bytes twice: the gate compares them
