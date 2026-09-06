"""The arms door: the walk-derived half of an arm file as a marked generated region, and the
verify that names drift. A floor, never the proof — the proof is the FastAPI run in RECON."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import graphy.arms as arms
import graphy.cli as cli
import graphy.fanout as fanout


class _Store:
    def __init__(self, records, edges, generation="gen-1", owner="pkg"):
        self._records, self._edges, self._gen, self._owner = records, edges, generation, owner

    def owned(self, owner):
        if owner == self._owner:
            yield from self._records.items()

    def edges(self):
        yield from self._edges

    def generation(self):
        return self._gen


def _rec(nid, node_type):
    dotted = nid.split("/", 3)[-1]
    mod = dotted if node_type == "module" else dotted.rsplit(".", 1)[0]
    if node_type == "method":
        mod = mod.rsplit(".", 1)[0]
    return nid, {"node_type": node_type, "dotted": dotted, "module": mod, "file": mod.replace(".", "/") + ".py"}


def _store(generation="gen-1", extra_func=False):
    ids = [("pkg://module/pkg.hub", "module"), ("pkg://class/pkg.hub.Hub", "class"),
           ("pkg://method/pkg.hub.Hub.run", "method"), ("pkg://method/pkg.hub.Hub.stop", "method"),
           ("pkg://func/pkg.hub.spin", "func"), ("pkg://module/pkg.base", "module"),
           ("pkg://class/pkg.base.Base", "class"), ("pkg://func/pkg.base.prim", "func"),
           ("pkg://module/pkg.misc", "module"), ("pkg://func/pkg.misc.m", "func")]
    if extra_func:
        ids.append(("pkg://func/pkg.hub.spin_again", "func"))
    records = dict(_rec(n, t) for n, t in ids)
    edges = [("pkg://class/pkg.hub.Hub", "pkg://class/pkg.base.Base", "inherits"),
             ("pkg://class/pkg.base.Base", "ext://class/ext.thing.Thing", "inherits"),
             ("pkg://func/pkg.hub.spin", "pkg://func/pkg.base.prim", "calls"),
             ("pkg://func/pkg.misc.m", "pkg://func/pkg.base.prim", "calls"),
             ("pkg://func/pkg.misc.m", "pkg://func/pkg.hub.spin", "calls")]
    return _Store(records, edges, generation)


def _cut(tmp_path):
    p = tmp_path / "partition.json"
    p.write_text(json.dumps({"groups": {"HUB": ["pkg.hub"], "BASE": ["pkg.base"]}, "rest": "EDGE"}), encoding="utf-8")
    return fanout.load_partition(p)


def _regions(tmp_path, **kw):
    return arms.render_all(_store(**kw), "pkg", _cut(tmp_path), tenant_dir="tenants/pkg", tenant_id="pkg")


def test_GREEN_region_carries_inventory_joins_and_rewalk(tmp_path):
    regs = _regions(tmp_path)
    hub = regs["HUB"].body
    assert "**`pkg.hub`** — classes: `Hub` (2); functions: `spin`" in hub
    assert "- `hub.Hub` ──inherits──▶ `pkg.base.Base` [BASE]" in hub
    assert "- `base.Base` ──inherits──▶ `ext.thing.Thing` ext" in regs["BASE"].body
    assert "graphy blast pkg://func/pkg.base.prim --tenant $T/tenant.json --tenant-id pkg" in regs["BASE"].body
    assert "graphy blast pkg://func/pkg.hub.spin " in hub
    assert "--partition $T/partition.json --dir $T/arms --verify" in hub
    assert "EDGE" not in regs                                    # the rest is routed, never an arm
    text = regs["HUB"].text()
    assert text.startswith("<!-- graphy:arm HUB generated") and text.rstrip().endswith("<!-- /graphy:arm HUB -->")
    assert f"store=gen-1 cut=sha256:{_cut(tmp_path).sha256} content=sha256:" in text


def test_GREEN_generate_creates_appends_replaces_and_never_touches_the_prose(tmp_path):
    d = tmp_path / "arms"
    d.mkdir()
    (d / "HUB.md").write_text("# HUB — the spine\n\nJudgment above.\n", encoding="utf-8")
    regs = _regions(tmp_path)
    assert dict(arms.generate(regs, d)) == {"HUB": "appended", "BASE": "created"}
    hub = (d / "HUB.md").read_text(encoding="utf-8")
    assert hub.startswith("# HUB — the spine\n\nJudgment above.\n")
    assert (d / "BASE.md").read_text(encoding="utf-8").startswith("# BASE — (the judgment prose goes here")
    assert dict(arms.generate(regs, d)) == {"HUB": "unchanged", "BASE": "unchanged"}
    # prose after the region survives a replace
    (d / "HUB.md").write_text(hub + "\nA note after the region.\n", encoding="utf-8")
    regs2 = _regions(tmp_path, generation="gen-2", extra_func=True)
    assert dict(arms.generate(regs2, d))["HUB"] == "replaced"
    hub2 = (d / "HUB.md").read_text(encoding="utf-8")
    assert hub2.startswith("# HUB — the spine\n\nJudgment above.\n") and hub2.endswith("\nA note after the region.\n")
    assert "`spin_again`" in hub2 and hub2.count("graphy:arm HUB generated") == 1


def test_RED_verify_names_every_kind_of_drift(tmp_path):
    d = tmp_path / "arms"
    regs = _regions(tmp_path)
    arms.generate(regs, d)
    assert [v.state for v in arms.verify(regs, d)] == ["match", "match"]
    text, rc = arms.render_verdicts(arms.verify(regs, d))
    assert rc == 0 and text.startswith("ARMS OK: 2 arm(s) match")
    # the walk moved: a new generation adds a symbol
    moved = _regions(tmp_path, generation="gen-2", extra_func=True)
    v = {x.name: x for x in arms.verify(moved, d)}
    assert v["HUB"].state == "moved" and "gen-1" in v["HUB"].detail and "gen-2" in v["HUB"].detail
    assert any("spin_again" in l for l in v["HUB"].diff) and v["BASE"].state == "match"
    text, rc = arms.render_verdicts(list(v.values()))
    assert rc == 1 and text.startswith("ARMS DRIFT: 1 of 2")
    # a hand inside the markers
    p = d / "BASE.md"
    p.write_text(p.read_text(encoding="utf-8").replace("`prim`", "`prim` · `ghost`"), encoding="utf-8")
    assert {x.name: x.state for x in arms.verify(regs, d)}["BASE"] == "edited"
    # no region, no file
    p.write_text("# BASE\n\nprose only\n", encoding="utf-8")
    assert {x.name: x.state for x in arms.verify(regs, d)}["BASE"] == "no-region"
    p.unlink()
    assert {x.name: x.state for x in arms.verify(regs, d)}["BASE"] == "no-file"
    # a region that opens and never closes is refused, not guessed
    p.write_text(regs["BASE"].text().replace("<!-- /graphy:arm BASE -->", ""), encoding="utf-8")
    with pytest.raises(arms.ArmsError, match="never closes"):
        arms.verify(regs, d)


def test_RED_a_depth_cut_names_no_arm(tmp_path):
    with pytest.raises(arms.ArmsError, match="depth cut"):
        arms.render_all(_store(), "pkg", fanout.Cut(depth=2), tenant_dir="t", tenant_id="pkg")


def test_RED_cli_refuses_without_its_four_flags(tmp_path, capsys):
    rc = cli.main(["arms", "--tenant", str(tmp_path / "nope.json"), "--tenant-id", "x", "--partition", "p", "--dir", "d"])
    assert rc == 2 and "ARMS REFUSED" in capsys.readouterr().err
    rc = cli.main(["arms", "--tenant", str(tmp_path / "nope.json"), "--tenant-id", "x"])
    assert rc == 2 and "--partition is required" in capsys.readouterr().err
