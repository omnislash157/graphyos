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


def test_GREEN_blast_and_descend_record_and_recall(tmp_path, capsys):
    """graphyos #111: only `walk` recorded, so every repeat of a blast or a descent paid the store again
    and `traversals` could list walks but query nothing. Both doors now land generation-keyed parquet;
    the repeat answers from the rows with zero reads and renders byte-identically; one door recalls
    the stored rows by seed or by target, walks and doors alike, without a store read."""
    import graphy.traversal as traversal
    if not traversal.have_duckdb():
        pytest.skip(traversal.INSTALL_HINT)
    store, tenant, desc = _store(tmp_path)
    argv = ["--tenant", str(desc), "--tenant-id", "doors"]
    home, gen = traversal.home_for(tenant), store.generation()

    def body(out: str) -> str:
        return out.split("DOOR:")[0]

    for door in ("blast", "descend"):
        assert cli.main([door, SEED, *argv, "--depth", "3"]) == 0
        first = capsys.readouterr().out
        assert "TRAVERSAL: source=live" in first and "reads=0" not in first.split("DOOR:")[1]
        assert cli.main([door, SEED, *argv, "--depth", "3"]) == 0
        again = capsys.readouterr().out
        assert f"DOOR: {door} reads=0" in again and "TRAVERSAL: source=store reads=0" in again
        assert body(again) == body(first)                                   # the recalled answer is the answer
    assert (home / gen / "doors").is_dir() and len(traversal.stored_doors(home, gen)) == 2

    # a different depth is a different question: live again, stored beside
    assert cli.main(["blast", SEED, *argv, "--depth", "1"]) == 0
    assert "source=live" in capsys.readouterr().out
    # --no-store runs live and lands nothing
    assert cli.main(["descend", "widgets.gadget", *argv, "--no-store"]) == 0
    assert "stored=no" in capsys.readouterr().out and len(traversal.stored_doors(home, gen)) == 3

    # the stored answer equals a fresh live door, field for field
    fresh = doors.blast(store, SEED, max_depth=3)
    recalled = traversal.load_door(home, gen, "blast", SEED, 3, store)
    assert doors.render_blast(recalled) == doors.render_blast(fresh) and recalled.declined == fresh.declined
    d_fresh, d_rec = doors.descend(store, SEED, max_depth=3), traversal.load_door(home, gen, "descend", SEED, 3, store)
    assert [r.node for r in d_rec.primitives] == [r.node for r in d_fresh.primitives] == ["widgets://func/widgets.prim"]

    # recall by target: every stored traversal that reached the test, one scan, zero reads
    test_it = "widgets://func/widgets.tests.test_gadget.test_it"
    assert cli.main(["traversals", *argv, "--target", test_it]) == 0
    out = capsys.readouterr().out
    assert f"RECALL target={test_it}" in out and f"blast {SEED} depth=3 rows=1" in out
    assert "TRAVERSALS RECALL OK: 1 stored traversal(s), 1 row(s), reads=0" in out
    # recall by seed: the blasts and the descent from the seed, and the walk rows beside them
    assert cli.main(["walk", *argv, "--seed", "widgets://func/widgets.gadget", "--target", "widgets://func/widgets.prim"]) == 0
    capsys.readouterr()
    rows = traversal.recall(home, gen, seed=SEED, store=store)
    assert {(r["kind"], r["depth"]) for r in rows} == {("blast", 3), ("blast", 1), ("descend", 3)}
    walked = traversal.recall(home, gen, target="widgets://func/widgets.prim", store=store)
    assert {(r["kind"], r["seed"]) for r in walked} == {("descend", SEED), ("walk", "widgets://func/widgets.gadget")}
    assert cli.main(["traversals", *argv]) == 0
    assert "TRAVERSALS OK: 4 stored traversal(s)" in capsys.readouterr().out
    # a torn receipt refuses by name, never reinterpreted
    rp = next((home / gen / "doors").glob("blast-*-d3.facts.json"))
    rp.write_text(json.dumps({**json.loads(rp.read_text()), "depth": 9}))
    assert cli.main(["blast", SEED, *argv, "--depth", "3"]) == 2
    assert "refusing to reinterpret it" in capsys.readouterr().err


def test_RED_a_redeclared_relation_is_never_recalled_stale(tmp_path):
    """graphyos #111 review round 1, kept by #117's design: the generation hashes nodes and edges, not the relation
    vocabulary, so a lane that re-declares `reads_table` over the same shards keeps its generation. The facts the
    first blast read are facts of that generation; the live rules re-run over them under the new declaration ask
    for a node the first blast never expanded, so the door runs live and answers what the live door answers."""
    import graphy.traversal as traversal
    if not traversal.have_duckdb():
        pytest.skip(traversal.INSTALL_HINT)
    undeclared = _census_store(tmp_path / "a", None)
    home = tmp_path / "traversals"
    stale = traversal.door(undeclared, home, "blast", TABLE, 3)
    assert stale.source == "live" and READER not in stale.result.reached
    declared = _census_store(tmp_path / "b", {"reads_table": ["depends"]})
    assert declared.generation() == undeclared.generation()           # the same shards: the generation cannot tell
    again = traversal.door(declared, home, "blast", TABLE, 3)
    assert again.source == "live" and READER in again.result.reached
    assert doors.render_blast(again.result) == doors.render_blast(doors.blast(declared, TABLE, max_depth=3))
    assert traversal.door(declared, home, "blast", TABLE, 3).source == "store"
    # recall re-derives under the live store's declaration: the reader is reached under it and not without it
    rows = traversal.recall(home, declared.generation(), target=READER, store=declared)
    assert {(r["kind"], r["seed"]) for r in rows} == {("blast", TABLE)}
    assert not traversal.recall(home, declared.generation(), target=READER, store=undeclared)
    assert traversal.recall(home, declared.generation(), seed=TABLE, store=undeclared)


def test_RED_a_door_records_the_facts_it_read_and_no_answer(tmp_path):
    """graphyos #117: the stored rows are what the door READ — every neighbour of each node it expanded and each
    owner it looked up — never what it computed; the key is the generation, the door, the seed and the depth."""
    import graphy.traversal as traversal
    if not traversal.have_duckdb():
        pytest.skip(traversal.INSTALL_HINT)
    store, tenant, _ = _store(tmp_path)
    home, gen = traversal.home_for(tenant), store.generation()
    o = traversal.door(store, home, "descend", SEED, 3)
    assert o.source == "live" and o.stored.name.endswith(".facts.parquet") and "-v" not in o.stored.name
    receipt = json.loads(o.stored.with_suffix(".json").read_text())
    assert set(receipt) >= {"generation", "door", "seed", "depth", "rows", "expanded", "owners", "reads"}
    assert "vocabulary" not in receipt and receipt["generation"] == gen
    nbs, owners = traversal.load_facts(home, gen, "descend", SEED, 3)
    for node in o.result.reached:                       # descend asks every reached node for its callees
        assert node in owners and node in nbs
        assert [(n.node, n.relation, n.direction) for n in nbs[node]] == \
               [(n.node, n.relation, n.direction) for n in store.neighbours(node)]   # unfiltered, as the store gave them


def test_RED_changed_rules_over_stored_facts_answer_as_the_changed_live_door(tmp_path, monkeypatch):
    """graphyos #117: an engine whose door rules moved, over facts an older rule recorded, answers what the new rule
    answers live — from the facts when they suffice, live when the new rule reads further. No key names the code."""
    import graphy.traversal as traversal
    if not traversal.have_duckdb():
        pytest.skip(traversal.INSTALL_HINT)
    store, tenant, _ = _store(tmp_path)
    home = traversal.home_for(tenant)
    wide = traversal.door(store, home, "blast", SEED, 3)
    assert wide.source == "live" and len(wide.result.reached) > 1
    monkeypatch.setattr(doors, "blast_relations", lambda s: frozenset())       # a rule that follows nothing
    monkeypatch.setattr(doors, "SEED_RELATIONS", frozenset())
    narrow = traversal.door(store, home, "blast", SEED, 3)
    assert narrow.source == "store" and list(narrow.result.reached) == [SEED]
    assert doors.render_blast(narrow.result) == doors.render_blast(doors.blast(store, SEED, max_depth=3))
    monkeypatch.undo()
    monkeypatch.setattr(doors, "SEED_RELATIONS", doors.SEED_RELATIONS | {"calls", "contains", "imports"})
    wider = traversal.door(store, home, "blast", SEED, 3)
    assert doors.render_blast(wider.result) == doors.render_blast(doors.blast(store, SEED, max_depth=3))


def test_RED_recall_rederives_each_stored_door_under_the_live_rules(tmp_path, monkeypatch):
    """graphyos #117: recall by target reads no answer rows; it re-runs each stored door over its facts, so a rule
    that stops reaching the target stops recalling it, with zero store reads."""
    import graphy.traversal as traversal
    if not traversal.have_duckdb():
        pytest.skip(traversal.INSTALL_HINT)
    store, tenant, _ = _store(tmp_path)
    home, gen = traversal.home_for(tenant), store.generation()
    reached = [n for n in traversal.door(store, home, "blast", SEED, 3).result.reached if n != SEED]
    assert reached and traversal.recall(home, gen, target=reached[0], store=store)
    counted = traversal.Counting(store)
    monkeypatch.setattr(doors, "blast_relations", lambda s: frozenset())
    monkeypatch.setattr(doors, "SEED_RELATIONS", frozenset())
    assert not traversal.recall(home, gen, target=reached[0], store=counted) and counted.reads == 0


def test_RED_a_released_door_layout_is_never_read_as_facts(tmp_path):
    """graphyos #117 · S7: 0.2.6 stored a door's ANSWER rows under `<door>-<key>-d<depth>-v<vocabulary>`. Those files
    are on users' disks; the repeat never reads them as facts — it runs live and records beside them."""
    import graphy.traversal as traversal
    if not traversal.have_duckdb():
        pytest.skip(traversal.INSTALL_HINT)
    store, tenant, _ = _store(tmp_path)
    home, gen = traversal.home_for(tenant), store.generation()
    d = home / gen / "doors"
    d.mkdir(parents=True)
    stem = f"blast-{traversal._key(SEED)}-d3-v0123456789abcdef"
    (d / f"{stem}.parquet").write_bytes(b"PAR1 an answer-rows parquet from 0.2.6")
    (d / f"{stem}.json").write_text(json.dumps({"format": 1, "door": "blast", "seed": SEED, "depth": 3,
                                                "generation": gen, "vocabulary": "0123456789abcdef", "rows": 1}))
    o = traversal.door(store, home, "blast", SEED, 3)
    assert o.source == "live" and o.stored.name == f"blast-{traversal._key(SEED)}-d3.facts.parquet"
    assert (d / f"{stem}.parquet").read_bytes().startswith(b"PAR1 an answer")
    assert traversal.door(store, home, "blast", SEED, 3).source == "store"
    assert [r["door"] for r in traversal.stored_doors(home, gen)] == ["blast"]


def test_RED_a_raise_mid_record_leaves_no_facts_and_the_answer_stands(tmp_path, monkeypatch):
    """graphyos #117 · E3: a write that fails half way lands no torn facts — the next ask is live, never a replay
    of a partial recording."""
    import graphy.traversal as traversal
    import graphy.container as container
    if not traversal.have_duckdb():
        pytest.skip(traversal.INSTALL_HINT)
    store, tenant, _ = _store(tmp_path)
    home = traversal.home_for(tenant)

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(traversal, "_write_parquet", boom)
    o = traversal.door(store, home, "descend", SEED, 3)
    assert o.source == "live" and o.stored is None and "disk full" in o.note
    assert not list(home.rglob("*.facts.*"))
    monkeypatch.undo()
    assert traversal.door(store, home, "descend", SEED, 3).source == "live"


def test_RED_a_door_answers_when_its_store_cannot_be_written(tmp_path, capsys):
    """graphyos #111 review round 4: the traversal store is a cache. A read-only (or full) home made the
    door compute its answer and then REFUSE with exit 2 — a verb that answered before it recorded. A
    failed write names TRAVERSAL SKIPPED and the answer stands, on the CLI and through the same `door`."""
    import os
    import graphy.traversal as traversal
    if not traversal.have_duckdb():
        pytest.skip(traversal.INSTALL_HINT)
    if os.geteuid() == 0:
        pytest.skip("root writes through a read-only directory")
    store, tenant, desc = _store(tmp_path)
    home = traversal.home_for(tenant)
    home.mkdir(parents=True, exist_ok=True)
    home.chmod(0o555)
    try:
        o = traversal.door(store, home, "blast", SEED, 3)
        assert o.source == "live" and o.stored is None and "could not be written" in o.note
        assert doors.render_blast(o.result) == doors.render_blast(doors.blast(store, SEED, max_depth=3))
        assert cli.main(["descend", SEED, "--tenant", str(desc), "--tenant-id", "doors"]) == 0
        out = capsys.readouterr().out
        assert "TRAVERSAL SKIPPED: the traversal store could not be written (PermissionError" in out
        # the walk is the same cache: it crashed with a traceback on a read-only home before this rung
        w = traversal.walk(store, home, "widgets://func/widgets.gadget", "widgets://func/widgets.prim")
        assert w.result.found and w.stored is None and "could not be written" in w.note
    finally:
        home.chmod(0o755)
    # a stored answer damaged from outside is a cache miss: answered live and rewritten, never REFUSED
    first = traversal.door(store, home, "blast", SEED, 3)
    assert first.stored is not None
    first.stored.write_bytes(b"not a parquet")
    again = traversal.door(store, home, "blast", SEED, 3)
    assert again.source == "live" and again.stored is not None
    assert traversal.door(store, home, "blast", SEED, 3).source == "store"
    # the walk's cache the same way (review round 6): a damaged stored walk is re-walked, never a traceback
    gadget, prim = "widgets://func/widgets.gadget", "widgets://func/widgets.prim"
    traversal.walk(store, home, gadget, prim)
    stored_walk = traversal.walk(store, home, gadget, prim)
    assert stored_walk.source == "store"
    stored_walk.stored.write_bytes(b"not a parquet")
    rewalked = traversal.walk(store, home, gadget, prim)
    assert rewalked.result.found and rewalked.source == "live" and rewalked.stored is not None
    # an interrupted write's leftover feed (a JSON list beside the receipts) never breaks a listing
    (home / store.generation() / "doors" / ".x.parquet.1.json").write_text("[1, 2]")
    (home / store.generation() / ".y.parquet.1.json").write_text("[1, 2]")
    assert traversal.stored_doors(home, store.generation()) and traversal.stored(home, store.generation())


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
    # Both producers declare one word past the doors' fallback, and only where they mint it: a function
    # or class used as a value is `references`, a dependency and never a reach (graphyos #94). The
    # fallback stays the #68 set: a shard minted before #94 carries no `references`, so it answers as
    # it did, and a shard nobody declared never walks a type its producer did not mean.
    assert PYTHON_AST_VOCABULARY.types_in(DEPENDS) == doors.BLAST_RELATIONS | {"references"}
    assert PYTHON_AST_VOCABULARY.types_in(REACHES) == doors.DESCEND_RELATIONS
    assert "references" not in doors.BLAST_RELATIONS
    # typescript_ast declares one more, and only where it mints it: a write to a rune's state (graphyos #85)
    assert TYPESCRIPT_AST_VOCABULARY.types_in(DEPENDS) == doors.BLAST_RELATIONS | {"writes", "references"}
    assert TYPESCRIPT_AST_VOCABULARY.types_in(REACHES) == doors.DESCEND_RELATIONS | {"writes"}


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


def test_GREEN_the_tests_line_states_the_mechanism_and_claims_a_wheel_only_where_one_is_proven(tmp_path):
    """`explain` printed ONE hardcoded sentence for every seed no test reached: "the ring is minted
    from wheels, which carry no test suite". It is a guess about WHY, it was unconditional, and it is
    only true for a ring shard minted from a wheel. It fired on a stranger's own untested function —
    telling them their code came from a wheel — and on a Postgres table in a foreign lane, where
    there is no wheel and no ring anywhere near the seed.

    A door that never guesses an edge must not guess a cause. The DOCS line one row above is the
    model: it names the mechanism that found nothing rather than inventing a reason (graphyos #72).

    The three seeds the done check names, in one test."""
    # 1 · a stranger's own untested function: the mechanism, and NO wheel claim
    store, tenant, _ = _store(tmp_path / "own")
    e = doors.explain(store, "widgets://func/widgets.prim", max_depth=2, tenant=tenant)
    assert e.tests == []
    assert e.tests_note.startswith("none reach it within depth 2 against the ")
    assert "calls" in e.tests_note and "wheel" not in e.tests_note
    assert "  TESTS: none reach it within depth 2 against the " in doors.render_explain(e)

    # 2 · a foreign producer's node: same, and still no wheel
    census = _census_store(tmp_path / "foreign", declare={"reads_table": ["depends"]})
    e2 = doors.explain(census, TABLE, max_depth=2, tenant=None)
    assert "wheel" not in e2.tests_note and "depth 2" in e2.tests_note

    # 3 · a lane whose provenance PROVES it came from an installed distribution
    site = tmp_path / "venv" / "site-packages"
    (site / "widgets").mkdir(parents=True)
    (Path(tenant.data_home) / "ring.json").write_text(
        json.dumps({"root": "widgets", "site_packages": str(site), "minted": {}}), encoding="utf-8")
    (Path(tenant.data_home) / "widgets_graph" / "PROVENANCE.json").write_text(json.dumps({
        "corpus": {"scheme": "widgets", "kind": "package", "path": str(site / "widgets"),
                   "distribution": "widgets", "version": "2.1.0"}}), encoding="utf-8")
    e3 = doors.explain(store, "widgets://func/widgets.prim", max_depth=2, tenant=tenant)
    assert "minted from the installed widgets 2.1.0" in e3.tests_note
    assert "a wheel carries no test suite" in e3.tests_note

    # …and the claim dies the moment the corpus is not under that site-packages
    (Path(tenant.data_home) / "widgets_graph" / "PROVENANCE.json").write_text(json.dumps({
        "corpus": {"scheme": "widgets", "kind": "package", "path": str(tmp_path / "elsewhere"),
                   "distribution": "widgets", "version": "2.1.0"}}), encoding="utf-8")
    assert "wheel" not in doors.explain(store, "widgets://func/widgets.prim",
                                        max_depth=2, tenant=tenant).tests_note


def test_GREEN_the_tests_line_names_the_family_the_declared_vocabulary_widened(tmp_path):
    """The mechanism sentence is not boilerplate: it names the relations this store actually walks,
    so a tenant that declared `reads_table` sees it in the reason no test was found."""
    store = _census_store(tmp_path, declare={"reads_table": ["depends"]})
    e = doors.explain(store, TABLE, max_depth=3, tenant=None)
    assert "reads_table" in e.tests_note, e.tests_note


# ── the declared doc vocabulary (graphyos #86) ─────────────────────────────────────────────────
SKILL = "skills://skill/skills.routing_rules"


SKILL2 = "skills://skill/skills.handler_rules"


def _skills_fixture(tmp_path: Path, meta: dict, prov_doc: list | None = None):
    """The doors fixture plus a skills shard whose `governs` edges bind a skill to the seed and one skill
    to another, a scheme index whose `_meta` is ``meta``, and — when ``prov_doc`` — the skills lane's
    PROVENANCE declaring those doc relations (graphyos #86)."""
    tenant, desc, roster = _fixture(tmp_path)
    data_home = Path(tenant.data_home)
    _write_graph(data_home / "skills_graph", {
        SKILL: {"kind": "node", "node_type": "skill", "id": SKILL, "dotted": "skills.routing_rules",
                "module": "skills", "role": "skill"},
        SKILL2: {"kind": "node", "node_type": "skill", "id": SKILL2, "dotted": "skills.handler_rules",
                 "module": "skills", "role": "skill"},
    }, [{"kind": "edge", "edge_type": "governs", "src": SKILL, "dst": SEED},
        {"kind": "edge", "edge_type": "governs", "src": SKILL2, "dst": SKILL}])
    if prov_doc is not None:
        (data_home / "skills_graph" / "PROVENANCE.json").write_text(json.dumps(
            {"vocabulary": {"producer": "skills_census", "doc_relations": prov_doc}}), encoding="utf-8")
    index_path = data_home / ".federation_scheme_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["_meta"] = meta
    index["skills"] = {"own": ["skills"], "out": ["fastapi"]}
    index_path.write_text(json.dumps(index), encoding="utf-8")
    lanes = dict(tenant.build_lanes, skills_graph=(None, "static-dep"))
    tenant = Tenant(root=tenant.root, data_home=data_home, adapters=(), build_lanes=lanes, join_keys=tenant.join_keys,
                    cursor=tenant.cursor, policy="refuse", journal=tenant.journal)
    roster = [*roster, "skills"]
    fs.compile_store(roster, fs.store_path_for(roster, tenant=tenant), tenant=tenant, tenant_id="doors")
    return tenant, roster


def test_GREEN_a_declared_doc_scheme_reaches_explain_and_the_defaults_still_stand(tmp_path):
    silent, roster = _skills_fixture(tmp_path / "silent", {})
    e = doors.explain(fs.open_for(roster, tenant=silent, tenant_id="doors"), SEED, max_depth=3)
    assert [d["id"] for d in e.docs] == [EXCHANGE]          # today's answer: the admitted skill is absent

    declared, roster = _skills_fixture(tmp_path / "declared",
                                       {"doc_schemes": ["skills"], "doc_relations": ["governs"]}, ["governs"])
    for store in (fs.open_for(roster, tenant=declared, tenant_id="doors"),
                  fs.ShardStore(roster, tenant=declared, tenant_id="doors")):
        assert store.doc_declaration == {"relations": ["governs"], "schemes": ["skills"]}
        e = doors.explain(store, SEED, max_depth=3)
        # the declaration widens the defaults, never replaces them: the history exchange still explains
        assert e.docs == [{"id": EXCHANGE, "relation": "mentions", "hops": 1, "owner": "history"},
                          {"id": SKILL, "relation": "governs", "hops": 1, "owner": "skills"},
                          {"id": SKILL2, "relation": "governs", "hops": 2, "owner": "skills"}]


def test_GREEN_the_doc_declaration_moves_the_input_digest_only_when_declared(tmp_path):
    tenant, roster = _skills_fixture(tmp_path, {"description": "x"})
    index_path = Path(tenant.data_home) / ".federation_scheme_index.json"
    bare = fs._scheme_index_input_digest(index_path, sorted(roster))
    # an index that declares nothing hashes exactly the rows it always did
    proj = {s: json.loads(index_path.read_text())[s]["own"] for s in sorted(roster)}
    assert bare == fs._sha16(json.dumps(proj, sort_keys=True, separators=(",", ":")).encode())
    index = json.loads(index_path.read_text())
    index["_meta"]["doc_schemes"], index["_meta"]["doc_relations"] = ["skills"], ["governs"]
    index_path.write_text(json.dumps(index), encoding="utf-8")
    assert fs._scheme_index_input_digest(index_path, sorted(roster)) != bare   # the store reads STALE


def test_GREEN_a_healed_scheme_index_keeps_what_its_writer_declared(tmp_path, monkeypatch):
    """The gate's heal rewrote `_meta` to its digest alone, dropping `standard` and the doc
    vocabulary the index's writer declared. The rows are the healer's; the declarations are not."""
    import graphy.mesh_federation_gate as gate
    monkeypatch.setattr(gate, "roster", lambda tenant: set())
    monkeypatch.setattr(gate, "_registry_digest", lambda tenant: "d")
    tenant, _ = _skills_fixture(tmp_path, {"standard": ["node"], "doc_schemes": ["skills"],
                                           "doc_relations": ["governs"]}, ["governs"])
    index_path = Path(tenant.data_home) / ".federation_scheme_index.json"
    healed = gate._heal_index(json.loads(index_path.read_text()), tenant)
    assert healed["_meta"]["standard"] == ["node"] and healed["_meta"]["doc_relations"] == ["governs"]
    assert "registry_digest" in healed["_meta"]


def test_RED_a_malformed_hand_declaration_refuses_the_build_and_a_seed_never_explains_itself(tmp_path):
    with pytest.raises(fs.StoreError, match=r"_meta.doc_schemes is 5"):
        _skills_fixture(tmp_path / "bad", {"doc_schemes": 5, "doc_relations": ["governs"]})
    # skill2 governs skill, skill governs the seed: from skill, hop 2 walks back to itself — never its own DOCS
    tenant, roster = _skills_fixture(tmp_path / "loop", {"doc_schemes": ["skills"], "doc_relations": ["governs"]},
                                     ["governs"])
    store = fs.open_for(roster, tenant=tenant, tenant_id="doors")
    for seed in (SKILL, SKILL2):
        docs = doors.explain(store, seed, max_depth=3).docs
        assert docs and seed not in {d["id"] for d in docs}


def test_RED_a_hand_written_doc_declaration_no_lane_declares_refuses_the_build(tmp_path):
    """Round 2 of #86's review: `_meta.doc_schemes: ["graphy"]` · `doc_relations: ["imports"]` written by
    hand built OK, checked OK, and listed 75 of the code lane's own modules under DOCS. The index only
    carries what a lane's PROVENANCE declares; the build proves the two agree."""
    with pytest.raises(fs.StoreError, match=r"carries doc vocabulary .*'widgets'.* but the PROVENANCE of the shards in .* declares none"):
        _skills_fixture(tmp_path / "code", {"doc_schemes": ["widgets"], "doc_relations": ["calls"]})
    with pytest.raises(fs.StoreError, match=r"declares \{'relations': \['governs'\], 'schemes': \['skills'\]\}"):
        _skills_fixture(tmp_path / "widened", {"doc_schemes": ["skills", "widgets"], "doc_relations": ["governs"]},
                        ["governs"])
    # a declaring lane with an index that says nothing: stale index, refused rather than silently undeclared
    with pytest.raises(fs.StoreError, match=r"carries doc vocabulary none"):
        _skills_fixture(tmp_path / "unstamped", {}, ["governs"])


def test_RED_a_declaration_changed_after_the_build_reads_stale_through_open_for(tmp_path):
    """Round 3 of #86's review: the declaration moved the input digest, but `open_for` fell back to the
    generation, which did not carry it — so `check` said fresh and explain served the old DOCS. Both
    directions: declared after an undeclared build, and withdrawn after a declared one."""
    tenant, roster = _skills_fixture(tmp_path / "declare_after", {})
    data_home = Path(tenant.data_home)
    (data_home / "skills_graph" / "PROVENANCE.json").write_text(json.dumps(
        {"vocabulary": {"doc_relations": ["governs"]}}), encoding="utf-8")
    index_path = data_home / ".federation_scheme_index.json"
    index = json.loads(index_path.read_text())
    index["_meta"] = {"doc_schemes": ["skills"], "doc_relations": ["governs"]}
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(fs.StoreError, match="STALE|stale"):
        fs.open_for(roster, tenant=tenant, tenant_id="doors")
    fs.compile_store(roster, fs.store_path_for(roster, tenant=tenant), tenant=tenant, tenant_id="doors")
    assert SKILL in {d["id"] for d in doors.explain(fs.open_for(roster, tenant=tenant, tenant_id="doors"), SEED).docs}

    tenant, roster = _skills_fixture(tmp_path / "withdraw_after",
                                     {"doc_schemes": ["skills"], "doc_relations": ["governs"]}, ["governs"])
    data_home = Path(tenant.data_home)
    (data_home / "skills_graph" / "PROVENANCE.json").unlink()
    index_path = data_home / ".federation_scheme_index.json"
    index = json.loads(index_path.read_text())
    index["_meta"] = {}
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(fs.StoreError, match="STALE|stale"):
        fs.open_for(roster, tenant=tenant, tenant_id="doors")


def test_RED_index_rows_edited_to_hand_a_code_scheme_to_the_doc_lane_refuse_the_build(tmp_path):
    """Round 3 of #86's review: the build's proof read ownership from the index rows, the same file a
    hand edits — `fastapi.own = []`, `skills.own = [fastapi, skills]` put code under DOCS. Ownership
    is read from the shards."""
    tenant, roster = _skills_fixture(tmp_path / "ok", {"doc_schemes": ["skills"], "doc_relations": ["governs"]},
                                     ["governs"])
    index_path = Path(tenant.data_home) / ".federation_scheme_index.json"
    index = json.loads(index_path.read_text())
    index["fastapi"]["own"], index["skills"]["own"] = [], ["fastapi", "skills"]
    index["_meta"]["doc_schemes"] = ["fastapi", "skills"]
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(fs.StoreError, match=r"carries doc vocabulary .*'fastapi'.* declares \{'relations': \['governs'\], 'schemes': \['skills'\]\}"):
        fs.compile_store(roster, fs.store_path_for(roster, tenant=tenant), tenant=tenant, tenant_id="doors")


def test_RED_an_index_row_removed_for_the_code_lane_does_not_hide_its_ownership_from_the_doc_proof(tmp_path):
    """Round 4 of #86's review: the proof compared the lanes the index's row KEYS named, so deleting the
    code lane's row hid it from the sole-owner check — a skills shard carrying stub `fastapi://` ids then
    put code under DOCS with CHECK OK. The lanes compared are the descriptor's declared lanes."""
    tenant, roster = _skills_fixture(tmp_path, {"doc_schemes": ["skills"], "doc_relations": ["governs"]}, ["governs"])
    data_home = Path(tenant.data_home)
    nodes = json.loads((data_home / "skills_graph" / "nodes.json").read_text())
    nodes[SEED] = {"kind": "node", "node_type": "func", "id": SEED, "dotted": "fastapi.routing.get_request_handler"}
    (data_home / "skills_graph" / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    index_path = data_home / ".federation_scheme_index.json"
    index = json.loads(index_path.read_text())
    del index["fastapi"]
    index["skills"]["own"] = ["fastapi", "skills"]
    index["_meta"]["doc_schemes"] = ["fastapi", "skills"]
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(fs.StoreError, match=r"lane 'skills' declares doc relations \['governs'\] but lane 'fastapi' also owns \['fastapi'\]"):
        fs.compile_store(roster, fs.store_path_for(roster, tenant=tenant), tenant=tenant, tenant_id="doors")


def test_RED_the_doc_proof_reads_every_shard_on_disk_not_a_door_or_a_descriptor_spelling(tmp_path):
    """Round 5 of #86's review. B7: a tenant built from flags (`graphy.query --mesh-set`,
    `python -m graphy.federated_store`) declares no lanes, so a proof over the descriptor's lanes found
    nothing and refused a legitimate declared tenant. B8: a descriptor key spelled `fastapi_graph/` was
    loaded by the store and skipped by the proof, so a dropped index row put code under DOCS again.
    The proof's lanes are the shards in the data home."""
    from graphy.tenant import cli_tenant
    tenant, roster = _skills_fixture(tmp_path / "flags", {"doc_schemes": ["skills"], "doc_relations": ["governs"]},
                                     ["governs"])
    flags = cli_tenant(str(tenant.data_home), str(tenant.join_keys), "doors")
    assert flags.build_lanes == {}
    shard = fs.ShardStore(roster, tenant=flags, tenant_id="doors")
    assert SKILL in {d["id"] for d in doors.explain(shard, SEED, max_depth=3).docs}
    assert fs.main(["--mesh-set", ",".join(roster), "--data-home", str(tenant.data_home),
                    "--join-keys", str(tenant.join_keys), "--tenant-id", "doors",
                    "--out", str(tmp_path / "flags.sqlite")]) == 0

    tenant, roster = _skills_fixture(tmp_path / "spelling", {"doc_schemes": ["skills"], "doc_relations": ["governs"]},
                                     ["governs"])
    data_home = Path(tenant.data_home)
    nodes = json.loads((data_home / "skills_graph" / "nodes.json").read_text())
    nodes[SEED] = {"kind": "node", "node_type": "func", "id": SEED, "dotted": "fastapi.routing.get_request_handler"}
    (data_home / "skills_graph" / "nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    index_path = data_home / ".federation_scheme_index.json"
    index = json.loads(index_path.read_text())
    del index["fastapi"]
    index["_meta"]["doc_schemes"] = ["fastapi", "skills"]
    index_path.write_text(json.dumps(index), encoding="utf-8")
    odd = Tenant(root=tenant.root, data_home=data_home, adapters=(), join_keys=tenant.join_keys, cursor=tenant.cursor,
                 policy="refuse", journal=tenant.journal,
                 build_lanes={"fastapi_graph/": (None, "static-dep"), "widgets_graph": (None, "static-dep"),
                              "history_graph": (None, "static-dep"), "skills_graph": (None, "static-dep")})
    with pytest.raises(fs.StoreError, match=r"lane 'skills' declares doc relations \['governs'\] but lane 'fastapi' also owns"):
        fs.compile_store(roster, fs.store_path_for(roster, tenant=odd), tenant=odd, tenant_id="doors")


def _declare_lane(data_home: Path, slug: str, nodes: dict, edges: list, doc_relations: list) -> None:
    _write_graph(data_home / f"{slug}_graph", nodes, edges)
    (data_home / f"{slug}_graph" / "PROVENANCE.json").write_text(json.dumps(
        {"vocabulary": {"producer": "skills_census", "doc_relations": doc_relations}}), encoding="utf-8")


def _recompile(tenant, roster, meta: dict, rows: dict, lanes: list[str]):
    index_path = Path(tenant.data_home) / ".federation_scheme_index.json"
    index = json.loads(index_path.read_text())
    index["_meta"] = meta
    index.update(rows)
    index_path.write_text(json.dumps(index), encoding="utf-8")
    tenant = Tenant(root=tenant.root, data_home=tenant.data_home, adapters=(), join_keys=tenant.join_keys,
                    cursor=tenant.cursor, policy="refuse", journal=tenant.journal,
                    build_lanes={**tenant.build_lanes, **{f"{l}_graph": (None, "static-dep") for l in lanes}})
    roster = [*roster, *lanes]
    fs.compile_store(roster, fs.store_path_for(roster, tenant=tenant), tenant=tenant, tenant_id="doors")
    return fs.open_for(roster, tenant=tenant, tenant_id="doors")


def test_GREEN_two_doc_lanes_that_both_declare_may_share_their_scheme(tmp_path):
    """Round 6 of #86's review (B9): the issue's own client rosters `manuals_ast` and
    `manuals_ast_restricted`, both owning scheme `manuals_ast`. Both declaring, the sole-owner proof
    refused them against each other. A scheme shared only by declaring lanes is documentation in all of
    them; a co-owner that declares nothing still refuses (the stub tests above)."""
    tenant, roster = _skills_fixture(tmp_path, {"doc_schemes": ["skills"], "doc_relations": ["governs"]}, ["governs"])
    restricted = "skills://skill/skills.restricted_rules"
    _declare_lane(Path(tenant.data_home), "skills_restricted",
                  {restricted: {"kind": "node", "node_type": "skill", "id": restricted, "dotted": "skills.restricted_rules"}},
                  [{"kind": "edge", "edge_type": "governs", "src": restricted, "dst": SEED}], ["governs"])
    store = _recompile(tenant, roster, {"doc_schemes": ["skills"], "doc_relations": ["governs"]},
                       {"skills_restricted": {"own": ["skills"], "out": ["fastapi"]}}, ["skills_restricted"])
    docs = {d["id"] for d in doors.explain(store, SEED, max_depth=3).docs}
    assert {SKILL, restricted} <= docs


def test_RED_a_declaring_shard_the_store_never_loads_changes_nothing(tmp_path):
    """Round 6 of #86's review (B10): reading every shard on disk for the vocabulary let an unrostered
    lane — a placed doc lane dropped from the rebuild, still on disk — declare `cites` and put a rostered
    lane's `cites` edge under DOCS. Ownership reads every shard; the answer counts only the loaded lanes."""
    tenant, roster = _skills_fixture(tmp_path, {"doc_schemes": ["skills"], "doc_relations": ["governs"]}, ["governs"])
    data_home = Path(tenant.data_home)
    edges = json.loads((data_home / "skills_graph" / "edges.json").read_text())
    edges.append({"kind": "edge", "edge_type": "cites", "src": SKILL2, "dst": SEED})
    (data_home / "skills_graph" / "edges.json").write_text(json.dumps(edges), encoding="utf-8")
    stray = "other://note/other.n"
    _declare_lane(data_home, "other", {stray: {"kind": "node", "node_type": "note", "id": stray, "dotted": "other.n"}},
                  [], ["cites"])
    # the index as eat/rebuild would derive it over the disk: the stray's declaration is carried
    store = _recompile(tenant, roster, {"doc_schemes": ["other", "skills"], "doc_relations": ["cites", "governs"]},
                       {"other": {"own": ["other"], "out": []}}, [])
    assert store.doc_declaration == {"relations": ["governs"], "schemes": ["skills"]}
    assert all(d["relation"] != "cites" for d in doors.explain(store, SEED, max_depth=3).docs)
