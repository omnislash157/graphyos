"""The doors: descend · blast · explain over a compiled store, and the resolver that refuses
to guess. A floor, never the proof — the proof is the FastAPI run in RECON."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import graphy.cli as cli
import graphy.doors as doors
import graphy.federated_store as fs
from graphy.tenant import Tenant

FIXTURES = Path(__file__).parent / "fixtures"
FASTAPI_GRAPH = FIXTURES / "fastapi_graph"
SEED = "fastapi://func/fastapi.routing.get_request_handler"


def _write_graph(dirpath: Path, nodes: dict, edges: list) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    (dirpath / "edges.json").write_text(json.dumps(edges), encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Tenant, Path, list[str]]:
    data_home = tmp_path / "data"
    data_home.mkdir(parents=True)
    shutil.copytree(FASTAPI_GRAPH, data_home / "fastapi_graph")
    _write_graph(data_home / "widgets_graph", {
        "widgets://module/widgets": {"kind": "node", "node_type": "module", "id": "widgets://module/widgets",
                                     "dotted": "widgets", "file": "widgets/__init__.py", "docstring": ""},
        "widgets://func/widgets.gadget": {"kind": "node", "node_type": "func", "id": "widgets://func/widgets.gadget",
                                          "name": "gadget", "dotted": "widgets.gadget", "file": "widgets/gadget.py",
                                          "line": 1, "docstring": "A gadget over the handler."},
        "widgets://func/widgets.helper": {"kind": "node", "node_type": "func", "id": "widgets://func/widgets.helper",
                                          "name": "helper", "dotted": "widgets.helper", "file": "widgets/helper.py", "line": 1},
        "widgets://func/widgets.prim": {"kind": "node", "node_type": "func", "id": "widgets://func/widgets.prim",
                                        "name": "prim", "dotted": "widgets.prim", "file": "widgets/prim.py", "line": 1},
        "widgets://func/widgets.tests.test_gadget.test_it": {
            "kind": "node", "node_type": "func", "id": "widgets://func/widgets.tests.test_gadget.test_it",
            "name": "test_it", "dotted": "widgets.tests.test_gadget.test_it",
            "file": "widgets/tests/test_gadget.py", "line": 4, "docstring": "", "role": "test"},
    }, [
        {"kind": "edge", "edge_type": "calls", "src": "widgets://func/widgets.gadget", "dst": SEED, "line": 2},
        {"kind": "edge", "edge_type": "calls", "src": SEED, "dst": "widgets://func/widgets.helper", "line": 400},
        {"kind": "edge", "edge_type": "calls", "src": "widgets://func/widgets.helper", "dst": "widgets://func/widgets.prim", "line": 2},
        {"kind": "edge", "edge_type": "calls", "src": "widgets://func/widgets.tests.test_gadget.test_it",
         "dst": "widgets://func/widgets.gadget", "line": 5},
    ])
    (data_home / ".federation_scheme_index.json").write_text(json.dumps({
        "_meta": {}, "fastapi": {"own": ["fastapi"], "out": []}, "widgets": {"own": ["widgets"], "out": ["fastapi"]},
    }), encoding="utf-8")
    join_keys = tmp_path / "registry.json"
    join_keys.write_text(json.dumps({"_meta": {}, "registered_joins": {"literal_joins": {}}}), encoding="utf-8")
    lanes = {"fastapi_graph": (None, "static-dep"), "widgets_graph": (None, "static-dep")}
    tenant = Tenant(root=tmp_path, data_home=data_home, adapters=(), build_lanes=lanes, join_keys=join_keys,
                    cursor="sha256:" + "0" * 64, policy="refuse", journal=tmp_path / "journal")
    roster = ["fastapi", "widgets"]
    fs.compile_store(roster, fs.store_path_for(roster, tenant=tenant), tenant=tenant, tenant_id="doors")
    desc = tmp_path / "tenant.json"
    desc.write_text(json.dumps({
        "root": str(tmp_path), "data_home": str(data_home), "adapters": [],
        "build_lanes": {k: [None, v[1]] for k, v in lanes.items()}, "join_keys": str(join_keys),
        "cursor": "sha256:" + "0" * 64, "policy": "refuse", "journal": str(tmp_path / "journal")}), encoding="utf-8")
    return tenant, desc, roster


def _store(tmp_path):
    tenant, desc, roster = _fixture(tmp_path)
    return fs.open_for(roster, tenant=tenant, tenant_id="doors"), tenant, desc


def test_resolve_exact_tail_and_refusals(tmp_path):
    store, _, _ = _store(tmp_path)
    assert doors.resolve(store, SEED) == SEED
    assert doors.resolve(store, "get_request_handler") == SEED
    assert doors.resolve(store, "routing.get_request_handler") == SEED
    with pytest.raises(doors.DoorError, match="names no node"):
        doors.resolve(store, "no_such_symbol_anywhere")
    with pytest.raises(doors.DoorError, match=r"names \d+ nodes; a door never guesses"):
        doors.resolve(store, "__init__")


def test_descend_follows_calls_out_and_names_the_crossing(tmp_path):
    store, _, _ = _store(tmp_path)
    d = doors.descend(store, SEED, max_depth=3)
    assert d.owner == "fastapi"
    # the fixture shard carries its calls as text labels (resolved only by converge --resolve), so the
    # resolved chain under test is the one the widgets shard lays: seed -> helper -> prim
    assert d.reached["widgets://func/widgets.helper"].hop == 1
    assert d.reached["widgets://func/widgets.prim"].hop == 2
    assert [(c.src_owner, c.dst_owner, c.hop, c.dst) for c in d.crossings] == [
        ("fastapi", "widgets", 1, "widgets://func/widgets.helper")]
    assert [r.node for r in d.primitives] == ["widgets://func/widgets.prim"]
    assert d.packages == ["fastapi", "widgets"]
    # a dependent is never a callee: the widget that calls the seed is not in the descent
    assert "widgets://func/widgets.gadget" not in d.reached


def test_blast_walks_against_the_edges_own_and_ring(tmp_path):
    store, _, _ = _store(tmp_path)
    b = doors.blast(store, SEED, max_depth=3)
    ring = {r.node: r.hop for r in b.ring}
    assert b.own == []   # the fixture's own calls are text labels; nothing resolved calls the seed inside fastapi
    assert ring["widgets://func/widgets.gadget"] == 1
    assert ring["widgets://func/widgets.tests.test_gadget.test_it"] == 2
    assert b.by_owner["widgets"] == 2
    # a callee is never a dependent
    assert "widgets://func/widgets.helper" not in b.reached


def test_explain_record_tests_and_honest_absences(tmp_path):
    store, tenant, _ = _store(tmp_path)
    e = doors.explain(store, SEED, max_depth=3, tenant=tenant)
    assert e.record["file"] == "fastapi/routing.py"
    assert [t.node for t in e.tests] == ["widgets://func/widgets.tests.test_gadget.test_it"]
    assert e.docs == []
    assert e.journal is None and "no journal page" in e.journal_note
    rendered = doors.render_explain(e)
    assert "TESTS (test modules that reach it" in rendered and "DOCS: none" in rendered


def test_cli_doors_answer_from_the_store_and_refuse_ambiguity(tmp_path, capsys):
    _, _, desc = _store(tmp_path)
    for door, mark in (("descend", "DESCEND seed="), ("blast", "BLAST seed="), ("explain", "EXPLAIN seed=")):
        assert cli.main([door, "get_request_handler", "--tenant", str(desc), "--tenant-id", "doors"]) == 0
        out = capsys.readouterr().out
        assert out.startswith(mark) and f"DOOR: {door} reads=" in out
    assert cli.main(["blast", "__init__", "--tenant", str(desc), "--tenant-id", "doors"]) == 1
    assert "a door never guesses" in capsys.readouterr().err
    assert cli.main(["descend", "get_request_handler", "--tenant-id", "doors"]) == 2
