"""The showcase page: composed from the store and the proposal, checked. A floor; the proof is the
three cold showcases in RECON."""
from __future__ import annotations

import json
from pathlib import Path

import graphy.cli as cli
import graphy.federated_store as fs
import graphy.fanout as fanout
import graphy.pillars as pillars
import graphy.showcase as showcase
import graphy.sugiyama as sugi
from test_doors import _fixture


def test_GREEN_compose_writes_a_checked_page_and_text(tmp_path):
    tenant, desc, roster = _fixture(tmp_path)
    store = fs.open_for(roster, tenant=tenant, tenant_id="doors")
    part = tmp_path / "partition.json"
    part.write_text(json.dumps({"groups": {"ROUTING": ["fastapi.routing"], "DEPS": ["fastapi.dependencies"]}, "rest": "EDGE"}))
    cut = fanout.load_partition(part)
    proposal = pillars.Proposal(corpus="fastapi", depth=2, floor=5, owned=2 / 3, client=1 / 3, rest="EDGE",
                                crowns={"ROUTING": "fastapi.routing", "DEPS": "fastapi.dependencies"}, floor_arm=None,
                                arms={"ROUTING": ["fastapi.routing"], "DEPS": ["fastapi.dependencies"]},
                                rulings=[pillars.Ruling(unit="fastapi.routing", arm="ROUTING", role="orchestrator", fan_in=1, fan_out=9, how="crown")],
                                total=10)
    ring = {"root": "fastapi", "minted": {"fastapi": {}, "widgets": {}}, "unresolved": {"brotli": "not under x"}}
    html, text = showcase.compose(store, package="fastapi", desc=desc, home=tmp_path, proposal=proposal, cut=cut, ring=ring,
                                  graphy_cmd=["graphy"], origin="https://example.invalid/fastapi.git")
    page = tmp_path / "index.html"
    page.write_text(html, encoding="utf-8")
    assert sugi.check_artifact(page) == []
    assert '&quot;mcpServers&quot;' in html and "graphy blast fastapi.routing" in html and "widgets" in html and "brotli" in html
    assert "https://" not in html.replace("https://example.invalid/fastapi.git", "")
    assert text.startswith("fastapi — drawn by graphy in one command") and "ADD YOUR MODEL" in text and "ASK IT" in text
    assert "THE PILLARS" in text and "ROUTING" in text


def test_RED_showcase_refusals(tmp_path, capsys):
    rc = cli.main(["showcase"])
    assert rc == 2 and "name a git url or a repo path" in capsys.readouterr().err
    rc = cli.main(["showcase", str(tmp_path / "nowhere")])
    assert rc == 2 and "not a directory" in capsys.readouterr().err
