
from __future__ import annotations

import pytest

from graphy._shared import (
    AST_STRUCT_SALIENCE,
    AST_WIRE_RELATIONS,
    AST_WIRE_SALIENCE,
    _ast_edge_salience,
)
from graphy.query import NodeState, activate, rank



def test_wire_relations_rank_at_wire_salience():
    for rel in ("serves", "fetches", "fetches_static", "navigates"):
        assert _ast_edge_salience(rel) == AST_WIRE_SALIENCE == 5.0


def test_struct_relations_rank_at_struct_salience():
    for rel in ("imports", "contains", "calls", "inherits", "decorates"):
        assert _ast_edge_salience(rel) == AST_STRUCT_SALIENCE == 1.0


def test_the_wire_relation_set_is_the_exact_literal():
    assert AST_WIRE_RELATIONS == {"serves", "fetches", "fetches_static", "navigates"}



def _fixture_adj():
    return {
        "seed.py": [("a.py", 0.9, ["c1"]), ("b.py", 0.5, ["c1"])],
        "a.py": [("seed.py", 0.9, ["c1"]), ("c.py", 0.7, ["c2"])],
        "b.py": [("seed.py", 0.5, ["c1"])],
        "c.py": [("a.py", 0.7, ["c2"])],
    }


def test_activate_seed_is_always_admitted_at_energy_one():
    state = activate(_fixture_adj(), "seed.py", depth=2, decay=0.5)
    seed = state["seed.py"]
    assert seed.energy == 1.0
    assert seed.salience is None
    assert seed.hops == 0
    assert seed.witnesses == []


def test_activate_energy_strictly_decreases_with_hops():
    state = activate(_fixture_adj(), "seed.py", depth=2, decay=0.5)
    assert state["a.py"].hops == 1
    assert state["b.py"].hops == 1
    assert state["c.py"].hops == 2
    assert state["a.py"].energy == pytest.approx(0.5 * (0.9 / 1.4))
    assert state["b.py"].energy == pytest.approx(0.5 * (0.5 / 1.4))
    assert state["c.py"].energy == pytest.approx(
        state["a.py"].energy * 0.5 * (0.7 / 1.6))
    for nid, ns in state.items():
        if nid != "seed.py":
            assert 0.0 < ns.energy < 1.0


def test_activate_witnesses_and_salience_are_carried_per_edge():
    state = activate(_fixture_adj(), "seed.py", depth=2, decay=0.5)
    assert state["a.py"].salience == 0.9
    assert state["a.py"].witnesses == ["c1"]
    assert state["c.py"].salience == 0.7
    assert state["c.py"].witnesses == ["c2"]


def test_activate_seed_not_in_mesh_returns_seed_only_state():
    state = activate({}, "missing.py", depth=2, decay=0.5)
    assert state == {"missing.py": NodeState(energy=1.0, salience=None, hops=0, witnesses=[])}
    assert "missing.py" in state


def test_activate_zero_energy_edges_admit_nothing():
    adj = {"seed.py": [("zero.py", 0.0, [])], "zero.py": [("seed.py", 0.0, [])]}
    state = activate(adj, "seed.py", depth=2, decay=0.5)
    assert set(state) == {"seed.py"}
    assert "zero.py" not in state


def test_activate_terminates_on_cycles():
    adj = {
        "seed.py": [("a.py", 1.0, ["c1"])],
        "a.py": [("seed.py", 1.0, ["c1"]), ("b.py", 1.0, ["c1"])],
        "b.py": [("a.py", 1.0, ["c1"])],
    }
    state = activate(adj, "seed.py", depth=3, decay=0.5)
    assert set(state) == {"seed.py", "a.py", "b.py"}
    assert state["a.py"].hops == 1
    assert state["b.py"].hops == 2


def test_activate_higher_energy_same_hop_parent_claims_the_child():
    adj = {
        "seed.py": [("pa.py", 1.0, ["c1"]), ("pb.py", 0.4, ["c1"])],
        "pa.py": [("seed.py", 1.0, ["c1"]), ("child.py", 0.8, ["c2"])],
        "pb.py": [("seed.py", 0.4, ["c1"]), ("child.py", 0.8, ["c3"])],
        "child.py": [],
    }
    state = activate(adj, "seed.py", depth=2, decay=0.5)
    assert state["pa.py"].energy > state["pb.py"].energy
    assert state["child.py"].hops == 2
    assert state["child.py"].witnesses == ["c2"]


def test_activate_is_deterministic():
    a = activate(_fixture_adj(), "seed.py", depth=2, decay=0.5)
    b = activate(_fixture_adj(), "seed.py", depth=2, decay=0.5)
    assert a == b



def _fixture_state():
    return activate(_fixture_adj(), "seed.py", depth=2, decay=0.5)


def test_rank_keeps_the_seed_first_regardless_of_energy():
    ordered, qualified, truncated = rank(_fixture_state(), top=10, min_salience=0.0)
    assert ordered[0][0] == "seed.py"
    assert ordered[0][1].salience is None
    assert qualified == 3
    assert truncated is False


def test_rank_sorts_by_energy_desc_then_salience_desc_then_id():
    ordered, _, _ = rank(_fixture_state(), top=10, min_salience=0.0)
    ids = [nid for nid, _ in ordered]
    assert ids == ["seed.py", "a.py", "b.py", "c.py"]


def test_rank_truncation_is_reported_from_the_pre_cap_count():
    ordered, qualified, truncated = rank(_fixture_state(), top=2, min_salience=0.0)
    assert qualified == 3
    assert truncated is True
    assert [nid for nid, _ in ordered] == ["seed.py", "a.py", "b.py"]


def test_rank_min_salience_floor_drops_nodes_node_wise():
    ordered, qualified, truncated = rank(_fixture_state(), top=10, min_salience=0.6)
    assert qualified == 2
    assert truncated is False
    assert [nid for nid, _ in ordered] == ["seed.py", "a.py", "c.py"]
