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
