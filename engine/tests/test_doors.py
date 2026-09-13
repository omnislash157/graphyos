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
EXCHANGE = "history://exchange/s1/3/user"
NEIGHBOUR_EX = "history://exchange/s1/4/user"


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
    # graphyos #64: a history shard whose exchange mentions the seed — the wormhole on the code's own dotted name
    _write_graph(data_home / "history_graph", {
        "history://session/s1": {"kind": "node", "node_type": "session", "id": "history://session/s1", "dotted": "history.session.s1",
                                 "module": "history", "role": "session", "captured_at": "2026-09-05T11:00:00+00:00", "file": "00001__x__s1.md"},
        EXCHANGE: {"kind": "node", "node_type": "exchange", "id": EXCHANGE, "dotted": "history.exchange.s1.3.user", "module": "history",
                   "role": "exchange", "session": "history://session/s1", "n": 3, "speaker": "user", "literals": 1},
        NEIGHBOUR_EX: {"kind": "node", "node_type": "exchange", "id": NEIGHBOUR_EX, "dotted": "history.exchange.s1.4.user", "module": "history",
                       "role": "exchange", "session": "history://session/s1", "n": 4, "speaker": "user", "literals": 2},
    }, [
        {"kind": "edge", "edge_type": "contains", "src": "history://session/s1", "dst": EXCHANGE},
        {"kind": "edge", "edge_type": "contains", "src": "history://session/s1", "dst": NEIGHBOUR_EX},
        {"kind": "edge", "edge_type": "mentions", "src": EXCHANGE, "dst": SEED, "via": "dotted", "count": 1, "literal": "routing.get_request_handler"},
        # an exchange that named the seed's caller and its callee — never the seed's own reader
        {"kind": "edge", "edge_type": "mentions", "src": NEIGHBOUR_EX, "dst": "widgets://func/widgets.gadget", "via": "dotted", "count": 1, "literal": "widgets.gadget"},
        {"kind": "edge", "edge_type": "mentions", "src": NEIGHBOUR_EX, "dst": "widgets://func/widgets.helper", "via": "dotted", "count": 1, "literal": "widgets.helper"},
    ])
    (data_home / ".federation_scheme_index.json").write_text(json.dumps({
        "_meta": {}, "fastapi": {"own": ["fastapi"], "out": []}, "widgets": {"own": ["widgets"], "out": ["fastapi"]},
        "history": {"own": ["history"], "out": ["fastapi"]},
    }), encoding="utf-8")
    join_keys = tmp_path / "registry.json"
    join_keys.write_text(json.dumps({"_meta": {}, "registered_joins": {"literal_joins": {}}}), encoding="utf-8")
    lanes = {"fastapi_graph": (None, "static-dep"), "widgets_graph": (None, "static-dep"), "history_graph": (None, "static-dep")}
    tenant = Tenant(root=tmp_path, data_home=data_home, adapters=(), build_lanes=lanes, join_keys=join_keys,
                    cursor="sha256:" + "0" * 64, policy="refuse", journal=tmp_path / "journal")
    roster = ["fastapi", "widgets", "history"]
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
    # graphyos #64: an exchange that mentions the seed is a reader of it — a BY OWNER row of its own, and the
    # walk stops there: `contains` is not a blast relation, so the session is never a dependent
    assert ring[EXCHANGE] == 1 and b.reached[EXCHANGE].relation == "mentions" and b.by_owner["history"] == 1
    assert "history://session/s1" not in b.reached
    assert NEIGHBOUR_EX not in b.reached, "the exchange that named the seed's caller (gadget, hop 1) is the caller's reader, not the seed's"
    rendered = doors.render_blast(b)
    assert "history=1" in rendered and f"hop1 history          {EXCHANGE}  ◀─mentions─ {SEED}" in rendered


def test_explain_record_tests_and_honest_absences(tmp_path):
    store, tenant, _ = _store(tmp_path)
    e = doors.explain(store, SEED, max_depth=3, tenant=tenant)
    assert e.record["file"] == "fastapi/routing.py"
    assert [t.node for t in e.tests] == ["widgets://func/widgets.tests.test_gadget.test_it"]
    # graphyos #64: an exchange that mentions the symbol explains it — the DOC_EXPLAINS family, hop 1
    assert e.docs == [{"id": EXCHANGE, "relation": "mentions", "hops": 1, "owner": "history"}]
    assert e.journal is None and "no journal page" in e.journal_note
    rendered = doors.render_explain(e)
    assert "TESTS (test modules that reach it" in rendered and f"hop1 mentions       {EXCHANGE}" in rendered
    # the exchange that named helper (the seed's callee) and gadget (its caller) explains neither the seed nor prim
    assert NEIGHBOUR_EX not in {d["id"] for d in e.docs}
    e = doors.explain(store, "widgets://func/widgets.prim", max_depth=3, tenant=tenant)
    assert e.docs == [] and "DOCS: none" in doors.render_explain(e)
    e = doors.explain(store, "widgets://func/widgets.helper", max_depth=3, tenant=tenant)
    assert [d["id"] for d in e.docs] == [NEIGHBOUR_EX]


def test_cli_doors_answer_from_the_store_and_refuse_ambiguity(tmp_path, capsys):
    _, _, desc = _store(tmp_path)
    for door, mark in (("descend", "DESCEND seed="), ("blast", "BLAST seed="), ("explain", "EXPLAIN seed=")):
        assert cli.main([door, "get_request_handler", "--tenant", str(desc), "--tenant-id", "doors"]) == 0
        out = capsys.readouterr().out
        assert out.startswith(mark) and f"DOOR: {door} reads=" in out
    assert cli.main(["blast", "__init__", "--tenant", str(desc), "--tenant-id", "doors"]) == 1
    assert "a door never guesses" in capsys.readouterr().err
    assert cli.main(["descend", "get_request_handler", "--tenant-id", "doors"]) == 2


# ── the declared relation vocabulary (graphyos #68) ────────────────────────────────────────────
TABLE = "pg_schema://table/pg_schema.enterprise.credit_requests"
READER = "core://func/core.billing.charge"


def _census_lane(data_home: Path, declare: dict | None) -> None:
    """A lane from a producer this engine never wrote: a SQL census whose `reads_table` edges bind
    code to the table it reads. `declare` is what its PROVENANCE says the relation MEANS — None
    writes no vocabulary block at all, which is every shard minted before graphyos #68."""
    _write_graph(data_home / "pg_schema_graph", {
        TABLE: {"kind": "node", "node_type": "table", "id": TABLE,
                "dotted": "pg_schema.enterprise.credit_requests", "module": "pg_schema", "role": "table"},
    }, [])
    _write_graph(data_home / "core_graph", {
        READER: {"kind": "node", "node_type": "func", "id": READER, "dotted": "core.billing.charge",
                 "module": "core", "role": "code", "file": "core/billing.py", "line": 7},
    }, [
        {"kind": "edge", "edge_type": "reads_table", "src": READER, "dst": TABLE, "line": 12},
    ])
    prov = {"counts": {"edge_count": 1, "edge_types": {"reads_table": 1}}}
    if declare is not None:
        prov["vocabulary"] = {"producer": "sql_census", "relations": declare, "undeclared": []}
    (data_home / "core_graph" / "PROVENANCE.json").write_text(json.dumps(prov), encoding="utf-8")


def _census_store(tmp_path: Path, declare: dict | None):
    data_home = tmp_path / "data"
    data_home.mkdir(parents=True)
    _census_lane(data_home, declare)
    (data_home / ".federation_scheme_index.json").write_text(json.dumps({
        "_meta": {}, "pg_schema": {"own": ["pg_schema"], "out": []},
        "core": {"own": ["core"], "out": ["pg_schema"]}}), encoding="utf-8")
    join_keys = tmp_path / "registry.json"
    join_keys.write_text(json.dumps({"_meta": {}, "registered_joins": {"literal_joins": {}}}), encoding="utf-8")
    lanes = {"pg_schema_graph": (None, "static-dep"), "core_graph": (None, "static-dep")}
    tenant = Tenant(root=tmp_path, data_home=data_home, adapters=(), build_lanes=lanes, join_keys=join_keys,
                    cursor="sha256:" + "0" * 64, policy="refuse", journal=tmp_path / "journal")
    roster = ["pg_schema", "core"]
    fs.compile_store(roster, fs.store_path_for(roster, tenant=tenant), tenant=tenant, tenant_id="census")
    return fs.open_for(roster, tenant=tenant, tenant_id="census")


def test_GREEN_a_declared_foreign_relation_reaches_blast_and_an_undeclared_one_does_not(tmp_path):
    """The whole of graphyos #68 in one comparison. A first client minted 67 edge types across 32
    lanes and 35 of them meant `depends`; every door walked four, so `blast` on a table with 22
    inbound edges answered a confident zero while `estate --sql` listed its readers. The fix is not
    "walk everything" — over half that roster is lexical co-occurrence and walking it would bury
    every honest dependent — it is that the producer DECLARES which of its relations mean impact.

    Same shard, same edges, same store, twice. The only difference is the PROVENANCE."""
    silent = _census_store(tmp_path / "silent", declare=None)
    assert silent.relations == {}                       # nothing declared
    assert doors.blast_relations(silent) == doors.BLAST_RELATIONS      # the constants, untouched
    b = doors.blast(silent, TABLE, max_depth=3)
    assert [r for r in b.reached.values() if r.hop > 0] == []          # today's answer: zero

    declared = _census_store(tmp_path / "declared", declare={"reads_table": ["depends"]})
    assert declared.relations == {"reads_table": ["depends"]}
    assert "reads_table" in doors.blast_relations(declared)
    b2 = doors.blast(declared, TABLE, max_depth=3)
    assert [r.node for r in b2.reached.values() if r.hop > 0] == [READER]
    assert b2.reached[READER].relation == "reads_table"


def test_GREEN_a_declared_reaches_relation_opens_descend_the_same_way(tmp_path):
    """DEPENDS and REACHES are separate declarations, so a producer can say a relation means impact
    without also saying a descent should follow it — `imports` is exactly that today."""
    store = _census_store(tmp_path / "both", declare={"reads_table": ["depends", "reaches"]})
    assert "reads_table" in doors.descend_relations(store)
    d = doors.descend(store, READER, max_depth=2)
    assert TABLE in d.reached
    depends_only = _census_store(tmp_path / "one", declare={"reads_table": ["depends"]})
    assert doors.descend_relations(depends_only) == doors.DESCEND_RELATIONS
    assert TABLE not in doors.descend(depends_only, READER, max_depth=2).reached


def test_RED_two_lanes_declaring_one_edge_type_differently_refuse_the_build(tmp_path):
    """A shared vocabulary stays shared only if disagreement cannot be committed. Two producers
    declaring `reads_table` with different meanings is a refusal that names both lanes — a door
    cannot walk one edge type two ways, and guessing which producer meant it is a name match."""
    data_home = tmp_path / "data"
    data_home.mkdir(parents=True)
    _census_lane(data_home, {"reads_table": ["depends"]})
    _write_graph(data_home / "other_graph", {
        "other://x/other.x": {"kind": "node", "node_type": "func", "id": "other://x/other.x", "dotted": "other.x"},
    }, [])
    (data_home / "other_graph" / "PROVENANCE.json").write_text(json.dumps({
        "counts": {"edge_types": {"reads_table": 1}},
        "vocabulary": {"producer": "other", "relations": {"reads_table": ["lexical"]}, "undeclared": []},
    }), encoding="utf-8")
    lanes = {"pg_schema_graph": (None, "static-dep"), "core_graph": (None, "static-dep"),
             "other_graph": (None, "static-dep")}
    join_keys = tmp_path / "registry.json"
    join_keys.write_text(json.dumps({"_meta": {}, "registered_joins": {"literal_joins": {}}}), encoding="utf-8")
    tenant = Tenant(root=tmp_path, data_home=data_home, adapters=(), build_lanes=lanes, join_keys=join_keys,
                    cursor="sha256:" + "0" * 64, policy="refuse", journal=tmp_path / "journal")
    with pytest.raises(fs.StoreError, match=r"relation vocabulary conflict on 'reads_table'"):
        fs.fold_relations(["core", "other"], tenant)


def test_GREEN_the_shipped_producers_declare_exactly_the_families_the_doors_hardcoded(tmp_path):
    """The equivalence that makes this landable: what python_ast and typescript_ast now DECLARE is
    what doors.py used to hardcode, so an eaten repo answers byte-identically before and after."""
    from graphy.adapters.typescript_ast import TYPESCRIPT_AST_VOCABULARY
    from graphy.ir import DEPENDS, PYTHON_AST_VOCABULARY, REACHES
    for vocab in (PYTHON_AST_VOCABULARY, TYPESCRIPT_AST_VOCABULARY):
        assert vocab.types_in(DEPENDS) == doors.BLAST_RELATIONS, vocab.producer
        assert vocab.types_in(REACHES) == doors.DESCEND_RELATIONS, vocab.producer


def test_GREEN_a_door_names_the_relations_it_declined_and_stays_silent_on_an_honest_zero(tmp_path):
    """A zero from a door is two very different statements — "nothing depends on this" and "I
    declined to read every edge that does" — and printing the same thing for both is the worst
    available answer for a tool whose contract is that no model decided an edge. The first client's
    table had 22 inbound edges and `blast` said dependents=0 (graphyos #69).

    The line appears only when unadmitted edges actually exist, so a genuinely unreferenced node
    still reads as a clean zero and the notice never becomes noise to scroll past."""
    silent = _census_store(tmp_path / "silent", declare=None)
    b = doors.blast(silent, TABLE, max_depth=3)
    assert [r for r in b.reached.values() if r.hop > 0] == []      # still zero dependents
    assert b.declined == {"reads_table": 1}                        # but it says why
    rendered = doors.render_blast(b)
    assert "NOT WALKED: reads_table 1" in rendered
    # nobody declared reads_table, so the notice is ACTIONABLE and says what to do
    assert "No producer declared what reads_table mean" in rendered and "re-mint that lane" in rendered

    # declared: walked, so nothing is declined and the notice is gone
    declared = _census_store(tmp_path / "declared", declare={"reads_table": ["depends"]})
    b2 = doors.blast(declared, TABLE, max_depth=3)
    assert b2.declined == {}
    assert "NOT WALKED" not in doors.render_blast(b2)

    # an honest zero: a node with no inbound edges at all reads clean
    b3 = doors.blast(silent, READER, max_depth=3)
    assert b3.declined == {} and "NOT WALKED" not in doors.render_blast(b3)


def test_GREEN_a_deliberate_classification_is_not_nagged_about_but_a_zero_still_explains_itself(tmp_path):
    """`contains` sits on nearly every node a code producer mints and is declared STRUCTURAL on
    purpose. Telling a reader to go declare it, on every healthy blast, would train them to scroll
    past the line that matters — so a DECLARED skip is silent while the answer is non-zero, and an
    UNDECLARED one speaks at any size. When the answer IS zero the notice always appears, because
    that is the case where silence and the graph disagree (graphyos #69)."""
    store = _census_store(tmp_path, declare={"reads_table": ["structural"]})
    b = doors.blast(store, TABLE, max_depth=3)
    assert b.declined == {"reads_table": 1} and b.declined_classes == {"reads_table": ["structural"]}
    line = doors.render_blast(b)
    assert "NOT WALKED" in line                                  # the answer was zero: always say so
    assert "declared and deliberate: reads_table=structural" in line
    assert "No producer declared" not in line                    # and never ask for what was given
    # the same declared skip, with a non-zero answer, is silent
    assert doors.render_declined({"contains": 1}, {"contains": ["structural"]}, answered=17) == ""
    assert doors.render_declined({"contains": 1}, {}, answered=17) != ""    # undeclared still speaks


def test_GREEN_descend_names_what_it_declined_on_the_way_out(tmp_path):
    """The same for the forward door: `reads_table` leaves the reader and `descend` walked past it."""
    silent = _census_store(tmp_path / "d-silent", declare=None)
    d = doors.descend(silent, READER, max_depth=2)
    assert TABLE not in d.reached
    assert d.declined == {"reads_table": 1}
    assert "NOT WALKED: reads_table 1" in doors.render_descend(d)
    reaching = _census_store(tmp_path / "d-declared", declare={"reads_table": ["depends", "reaches"]})
    d2 = doors.descend(reaching, READER, max_depth=2)
    assert TABLE in d2.reached and d2.declined == {}


def test_GREEN_the_notice_counts_every_unadmitted_relation_separately(tmp_path):
    """The first client's seed declined five relation types at once; the line is a census, not a
    flag, because which relations were skipped is what tells a reader what to declare."""
    data_home = tmp_path / "data"
    data_home.mkdir(parents=True)
    _write_graph(data_home / "pg_schema_graph", {
        TABLE: {"kind": "node", "node_type": "table", "id": TABLE, "dotted": "pg_schema.enterprise.credit_requests"},
    }, [])
    readers = {}
    edges = []
    for rel, n in (("reads_table", 3), ("indexes_on", 2), ("protects", 1)):
        for i in range(n):
            nid = f"core://func/core.{rel}_{i}"
            readers[nid] = {"kind": "node", "node_type": "func", "id": nid, "dotted": f"core.{rel}_{i}"}
            edges.append({"kind": "edge", "edge_type": rel, "src": nid, "dst": TABLE, "line": 1})
    _write_graph(data_home / "core_graph", readers, edges)
    (data_home / ".federation_scheme_index.json").write_text(json.dumps({
        "_meta": {}, "pg_schema": {"own": ["pg_schema"], "out": []}, "core": {"own": ["core"], "out": ["pg_schema"]}}),
        encoding="utf-8")
    join_keys = tmp_path / "registry.json"
    join_keys.write_text(json.dumps({"_meta": {}, "registered_joins": {"literal_joins": {}}}), encoding="utf-8")
    lanes = {"pg_schema_graph": (None, "static-dep"), "core_graph": (None, "static-dep")}
    tenant = Tenant(root=tmp_path, data_home=data_home, adapters=(), build_lanes=lanes, join_keys=join_keys,
                    cursor="sha256:" + "0" * 64, policy="refuse", journal=tmp_path / "journal")
    roster = ["pg_schema", "core"]
    fs.compile_store(roster, fs.store_path_for(roster, tenant=tenant), tenant=tenant, tenant_id="many")
    store = fs.open_for(roster, tenant=tenant, tenant_id="many")
    b = doors.blast(store, TABLE, max_depth=2)
    assert len(b.reached) == 1                                    # the confident zero
    assert b.declined == {"reads_table": 3, "indexes_on": 2, "protects": 1}   # ordered by count
    line = doors.render_declined(b.declined, b.declined_classes, answered=0)
    assert line.index("reads_table") < line.index("indexes_on") < line.index("protects")
    assert "6 edge(s) on this seed" in line


def test_GREEN_the_counting_proxy_forwards_what_the_doors_read_off_a_store(tmp_path):
    """The CLI wraps every door's store in `traversal.Counting`, which forwarded four methods by
    hand. The doors read their relation families off the store (graphyos #68), so the day that
    landed, every door run through the CLI silently fell back to the hardcoded defaults while this
    floor — which holds the store directly — stayed green. The declared vocabulary worked everywhere
    except the one path a user takes, and only the NOT WALKED line made it visible.

    Forwarding by default is the fix; this is the test that the proxy cannot go blind again."""
    from graphy import traversal
    store = _census_store(tmp_path, declare={"reads_table": ["depends"]})
    counted = traversal.Counting(store)
    assert counted.relations == store.relations
    assert doors.blast_relations(counted) == doors.blast_relations(store)
    assert "reads_table" in doors.blast_relations(counted)
    b = doors.blast(counted, TABLE, max_depth=3)
    assert [r.node for r in b.reached.values() if r.hop > 0] == [READER]
    assert counted.reads > 0                                   # still counting
