"""The pillars door: a corpus's arms deduced from its module graph, every ruling with its evidence.
A floor, never the proof — the proof is the FastAPI and Starlette run in RECON."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import graphy.cli as cli
import graphy.converge as cv
import graphy.federated_store as fs
import graphy.fanout as fanout
import graphy.pillars as pillars
from graphy.tenant import Tenant

FIXTURES = Path(__file__).parent / "fixtures"
FASTAPI_GRAPH = FIXTURES / "fastapi_graph"
CURATED = Path(__file__).parents[1] / "tenants" / "fastapi" / "partition.json"


class _Store:
    """A store the size of a page: owned() and edges() are all the door reads."""

    def __init__(self, records: dict[str, dict], edges: list[tuple[str, str, str]], owner: str = "pkg"):
        self._records = records
        self._edges = edges
        self._owner = owner

    def owned(self, owner):
        if owner == self._owner:
            yield from self._records.items()

    def edges(self):
        yield from self._edges

    def generation(self):
        return "test"


def _mod(dotted: str) -> tuple[str, dict]:
    nid = f"pkg://module/{dotted}"
    return nid, {"node_type": "module", "dotted": dotted, "module": dotted, "file": dotted.replace(".", "/") + ".py"}


def _fn(dotted: str) -> tuple[str, dict]:
    nid = f"pkg://func/{dotted}"
    mod = dotted.rsplit(".", 1)[0]
    return nid, {"node_type": "func", "dotted": dotted, "module": mod, "file": mod.replace(".", "/") + ".py"}


def _synthetic() -> _Store:
    """hub orchestrates worker (5 edges); every unit leans on base (the floor); tiny is under the floor;
    the root is the facade; other is a second crown in hub's league; loner is an orchestrator nobody
    orchestrates, spending half on other's util and half on the floor."""
    records = dict([_mod("pkg"), _mod("pkg.hub"), _mod("pkg.worker"), _mod("pkg.base"), _mod("pkg.tiny"),
                    _mod("pkg.loner"), _mod("pkg.other"), _mod("pkg.util"), _mod("pkg.misc"),
                    _fn("pkg.hub.run"), _fn("pkg.worker.work"), _fn("pkg.base.prim"), _fn("pkg.loner.go"),
                    _fn("pkg.other.o"), _fn("pkg.util.u"), _fn("pkg.misc.m")])
    e = []
    hub, worker, base, loner, other, util, misc = (f"pkg://func/pkg.{m}" for m in
                                                   ("hub.run", "worker.work", "base.prim", "loner.go", "other.o",
                                                    "util.u", "misc.m"))
    e += [(hub, worker, "calls")] * 5                    # hub orchestrates worker
    e += [(hub, base, "calls")] * 8                      # everyone leans on base
    e += [(hub, misc, "calls")] * 6                      # misc: hub's alone; hub leads with fan-out 20
    e += [(worker, base, "calls")] * 7                   # worker: out 7 > in 6, an orchestrator under the league
    e += [(loner, base, "calls")] * 3
    e += [(other, base, "calls")] * 8                    # other: out 13 > in 0, an orchestrator in hub's league
    e += [(other, util, "calls")] * 5
    e += [(loner, util, "imports")] * 3                  # loner spends 3 on util (other's), 3 on the floor
    e += [(hub, "pkg://module/pkg.tiny", "imports")]     # tiny: one edge, under the floor
    e += [("pkg://module/pkg", hub, "imports"), ("pkg://module/pkg", worker, "imports")]   # the facade re-exports
    e += [(hub, worker, "contains")] * 40                # structure is never traffic
    e += [(hub, "other://func/elsewhere.x", "calls")] * 9  # a foreign corpus is not this module graph
    return _Store(records, e)


def test_module_graph_collapses_to_units_and_skips_structure_and_foreign_edges():
    g = pillars.module_graph(_synthetic(), "pkg", depth=2)
    assert g.root == "pkg"
    assert g.weight[("pkg.hub", "pkg.worker")] == 5
    assert ("pkg.hub", "pkg.hub") not in g.weight
    assert g.total == 5 + 8 + 6 + 7 + 3 + 8 + 5 + 3 + 1 + 2
    assert g.fan_in("pkg.base") == 26 and g.fan_out("pkg.base") == 0
    with pytest.raises(pillars.PillarsError, match="owns no module-bearing node"):
        pillars.module_graph(_synthetic(), "nobody")


def test_propose_rules_the_facade_the_edge_the_crowns_the_floor_and_the_client():
    g = pillars.module_graph(_synthetic(), "pkg")
    p = pillars.propose(g, floor=2)
    by = {r.unit: r for r in p.rulings}
    assert by["pkg"].role == "facade" and by["pkg"].arm == "EDGE"
    assert by["pkg.tiny"].role == "edge" and by["pkg.tiny"].arm == "EDGE"
    assert p.crowns["HUB"] == "pkg.hub" and p.crowns["OTHER"] == "pkg.other"
    assert by["pkg.worker"].arm == "HUB" and "orchestrated by HUB (5 of 6" in by["pkg.worker"].how
    # util's consumers are other (5) and loner (3): no arm owns 2/3 of 8, so util is shared — the floor;
    # loner's assigned suppliers are then all floor, so it leans on the floor; misc is hub's alone
    assert p.floor_arm == "BASE" and by["pkg.base"].how.startswith("the floor's crown")
    assert by["pkg.util"].arm == "BASE" and "shared" in by["pkg.util"].how
    assert by["pkg.misc"].arm == "HUB" and "owned by HUB (6 of 6" in by["pkg.misc"].how
    assert by["pkg.loner"].arm == "BASE" and "leans only on the floor" in by["pkg.loner"].how
    assert list(p.arms) == ["HUB", "OTHER", "BASE"]
    assert p.arm_of("pkg.nowhere") == "EDGE"


def test_a_foundation_one_arm_owns_settles_before_the_floor_forms():
    g = pillars.module_graph(_synthetic(), "pkg")
    p = pillars.propose(g, floor=2, owned=0.6)
    by = {r.unit: r for r in p.rulings}
    # at 0.6, other's 5 of 8 owns util (base stays shared: HUB takes 15 of 26); loner then spends 3 of 6 on OTHER
    assert by["pkg.util"].arm == "OTHER" and "owned by OTHER (5 of 8" in by["pkg.util"].how
    assert by["pkg.base"].arm == "BASE"
    assert by["pkg.loner"].arm == "OTHER" and "client of OTHER (3 of 6" in by["pkg.loner"].how


def test_stand_alone_crown_and_arms_bound():
    g = pillars.module_graph(_synthetic(), "pkg")
    p = pillars.propose(g, floor=2, owned=0.6, client=0.75)
    by = {r.unit: r for r in p.rulings}
    assert by["pkg.loner"].arm == "LONER" and "stands alone" in by["pkg.loner"].how
    bounded = pillars.propose(g, floor=2, owned=0.6, client=0.75, arms=3)
    byb = {r.unit: r for r in bounded.rulings}
    assert "LONER" not in bounded.crowns
    assert byb["pkg.loner"].arm == "OTHER" and "--arms 3 forbids" in byb["pkg.loner"].how
    assert len(bounded.arms) == 3


def test_refusals():
    g = pillars.module_graph(_synthetic(), "pkg")
    with pytest.raises(pillars.PillarsError, match="--arms must be at least 2"):
        pillars.propose(g, arms=1)
    with pytest.raises(pillars.PillarsError, match="count of edges"):
        pillars.propose(g, floor=0.5)
    with pytest.raises(pillars.PillarsError, match="owned must be"):
        pillars.propose(g, owned=0.4)
    with pytest.raises(pillars.PillarsError, match="depth must be"):
        pillars.module_graph(_synthetic(), "pkg", depth=0)


def test_to_partition_round_trips_through_fanout_load_partition(tmp_path):
    g = pillars.module_graph(_synthetic(), "pkg")
    p = pillars.propose(g, floor=2)
    doc = pillars.to_partition(p)
    path = tmp_path / "partition.json"
    pillars.write_partition(path, doc)
    cut = fanout.load_partition(path)
    assert cut.group_of("pkg.hub.run") == "HUB"
    assert cut.group_of("pkg.base.prim") == "BASE"
    assert cut.group_of("pkg.tiny") == "EDGE" and cut.rest == "EDGE"
    moved = pillars.diff(p, cut)
    assert moved == []
    assert pillars.render_diff(moved, str(path)).startswith("PILLARS AGREE")
    assert "PILLARS:" in pillars.render(p, g) and "cross-arm edges" in pillars.render(p, g)


def _fastapi_tenant(tmp_path: Path) -> Path:
    data_home = tmp_path / "data"
    data_home.mkdir(parents=True)
    shutil.copytree(FASTAPI_GRAPH, data_home / "fastapi_graph")
    (data_home / ".federation_scheme_index.json").write_text(json.dumps({
        "_meta": {}, "fastapi": {"own": ["fastapi"], "out": []}}), encoding="utf-8")
    cv.resolve(cv.load_ring(data_home, ["fastapi"]), "fastapi", write=True)    # the labels scope binds, as rebuild.sh does
    join_keys = tmp_path / "registry.json"
    join_keys.write_text(json.dumps({"_meta": {}, "registered_joins": {"literal_joins": {}}}), encoding="utf-8")
    lanes = {"fastapi_graph": (None, "static-dep")}
    tenant = Tenant(root=tmp_path, data_home=data_home, adapters=(), build_lanes=lanes, join_keys=join_keys,
                    cursor="sha256:" + "0" * 64, policy="refuse", journal=tmp_path / "journal")
    fs.compile_store(["fastapi"], fs.store_path_for(["fastapi"], tenant=tenant), tenant=tenant, tenant_id="pil")
    desc = tmp_path / "tenant.json"
    desc.write_text(json.dumps({
        "root": str(tmp_path), "data_home": str(data_home), "adapters": [],
        "build_lanes": {k: [None, v[1]] for k, v in lanes.items()}, "join_keys": str(join_keys),
        "cursor": "sha256:" + "0" * 64, "policy": "refuse", "journal": str(tmp_path / "journal")}), encoding="utf-8")
    return desc


def test_cli_pillars_over_the_fastapi_fixture_names_the_four_crowns(tmp_path, capsys):
    desc = _fastapi_tenant(tmp_path)
    out = tmp_path / "proposed.json"
    rc = cli.main(["pillars", "--tenant", str(desc), "--tenant-id", "pil", "--write", str(out)])
    text = capsys.readouterr().out
    assert rc == 0
    assert "PILLARS: fastapi at depth 2" in text
    # the crowns the curated cut named are the crowns the walk finds — routing · dependencies · openapi, and
    # _compat the floor; applications stands alone, and RECON §24 names why
    for line in ("ROUTING        crown: fastapi.routing", "DEPENDENCIES   crown: fastapi.dependencies",
                 "OPENAPI        crown: fastapi.openapi", "COMPAT         the floor: fastapi._compat"):
        assert line in text, text
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["rest"] == "EDGE" and set(doc["groups"]) >= {"ROUTING", "DEPENDENCIES", "OPENAPI", "COMPAT"}
    # the written partition is a cut graphy fanout takes
    fan = tmp_path / "fanout"
    rc = cli.main(["fanout", "--graph-dir", str(tmp_path / "data" / "fastapi_graph"), "--out", str(fan),
                   "--partition", str(out)])
    assert rc == 0
    assert (fan / "ROUTING.md").is_file() and (fan / "COMPAT.md").is_file()
    assert cli.main(["fanout", "--verify", "--out", str(fan)]) == 0


def test_cli_pillars_against_the_curated_partition_exits_one_and_names_each_move(tmp_path, capsys):
    desc = _fastapi_tenant(tmp_path)
    rc = cli.main(["pillars", "--tenant", str(desc), "--tenant-id", "pil", "--against", str(CURATED)])
    text = capsys.readouterr().out
    assert rc in (0, 1)
    if rc == 1:
        assert "PILLARS DIFFER:" in text
        assert "proposed" in text and "curated" in text
    else:
        assert "PILLARS AGREE" in text


def test_cli_pillars_refusals(tmp_path, capsys):
    assert cli.main(["pillars"]) == 2
    assert "--tenant and --tenant-id are required" in capsys.readouterr().err
    desc = _fastapi_tenant(tmp_path)
    assert cli.main(["pillars", "--tenant", str(desc), "--tenant-id", "pil", "--corpus", "starlette"]) == 2
    assert "is not a corpus of this tenant" in capsys.readouterr().err
    assert cli.main(["pillars", "--tenant", str(desc), "--tenant-id", "pil", "--arms", "1"]) == 1
    assert "PILLARS UNANSWERABLE" in capsys.readouterr().err


def test_an_arm_named_from_a_non_dotted_crown_is_a_section_file_name():
    """The crown's last segment names the arm, and an arm name is a section file and an html id
    (graphyos #46): everything outside [A-Za-z0-9_] folds to `_`, a segment of nothing else is ARM."""
    assert pillars._arm_name("pkg.```", []) == "ARM"
    assert pillars._arm_name("pkg.my file", []) == "MY_FILE"
    assert pillars._arm_name("pkg.a-b", ["A_B"]) == "A_B2"
    assert pillars._arm_name("pkg.hub", []) == "HUB"
    import re
    for u in ("pkg.```", "pkg.my file", "pkg.-", "pkg.x.y z"):
        assert re.fullmatch(r"[A-Za-z0-9_]+", pillars._arm_name(u, []))
