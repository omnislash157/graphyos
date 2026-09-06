
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from graphy import (
    SCHEMA_VERSION,
    Evidence,
    IRError,
    Node,
    Provenance,
    Vocabulary,
    PYTHON_AST_VOCABULARY,
    validate_graph,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "fastapi_graph"


def _load():
    nodes = json.loads((FIXTURE_DIR / "nodes.json").read_text(encoding="utf-8"))
    edges = json.loads((FIXTURE_DIR / "edges.json").read_text(encoding="utf-8"))
    return nodes, edges


def _bad_node(mutator):
    nodes, edges = _load()
    nodes = copy.deepcopy(nodes)
    mutator(next(iter(nodes.values())))
    return nodes, edges


def _bad_edge(mutator):
    nodes, edges = _load()
    edges = copy.deepcopy(edges)
    mutator(edges[0])
    return nodes, edges



def test_schema_version_is_an_int():
    assert isinstance(SCHEMA_VERSION, int)


def test_corpus_counts_are_the_contract():
    nodes, edges = _load()
    assert len(nodes) == 507
    assert len(edges) == 3715


def test_records_are_typed_and_frozen():
    prov = Provenance(producer="graphy.factory.build", source="fastapi")
    ev = Evidence(kind="source", ref="fastapi/__init__.py")
    node = Node(
        id="x://module/x",
        node_type="module",
        dotted="x",
        file="x/__init__.py",
        docstring="",
        provenance=prov,
        evidence=ev,
    )
    assert node.kind == "node"
    assert node.provenance == prov
    assert node.evidence == ev
    with pytest.raises(AttributeError):
        node.id = "y://2"



def test_positive_all_507_nodes_and_3715_edges_validate():
    nodes, edges = _load()
    validated = validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)
    assert validated == 507 + 3715


def test_positive_every_node_id_matches_its_dict_key():
    nodes, _edges = _load()
    mismatched = [
        key for key, record in nodes.items() if record["id"] != key
    ]
    assert mismatched == []


def test_positive_cross_graph_dst_is_not_an_error():
    nodes, edges = _load()
    node_ids = set(nodes)
    cross_graph = [e for e in edges if "dst" in e and e["dst"] not in node_ids]
    assert cross_graph
    validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)


def test_positive_typed_provenance_and_evidence_are_attachable():
    nodes, edges = _load()
    nodes = copy.deepcopy(nodes)
    record = next(iter(nodes.values()))
    record["provenance"] = {"producer": "graphy.factory.build", "source": "fastapi"}
    record["evidence"] = {"kind": "source", "ref": "fastapi/__init__.py"}
    validated = validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)
    assert validated == 507 + 3715



def test_RED_node_missing_id_raises():
    nodes, edges = _bad_node(lambda r: r.pop("id", None))
    with pytest.raises(IRError, match="id"):
        validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)


def test_RED_node_dict_key_disagreeing_with_record_id_raises():
    nodes, edges = _load()
    nodes = copy.deepcopy(nodes)
    first_key = next(iter(nodes))
    nodes["fastapi://module/renamed"] = nodes.pop(first_key)
    with pytest.raises(IRError, match="dict key"):
        validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)


def test_RED_unknown_node_type_raises():
    nodes, edges = _bad_node(lambda r: r.__setitem__("node_type", "package"))
    with pytest.raises(IRError, match="node_type"):
        validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)


def test_RED_unknown_edge_type_raises():
    nodes, edges = _bad_edge(lambda r: r.__setitem__("edge_type", "teleports"))
    with pytest.raises(IRError, match="edge_type"):
        validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)


def test_positive_edge_carrying_both_dst_and_dst_repr_validates():
    nodes, edges = _load()
    edges = copy.deepcopy(edges)
    edges[0]["dst_repr"] = "starlette"
    validated = validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)
    assert validated == 507 + 3715


def test_RED_edge_carrying_neither_dst_nor_dst_repr_raises():
    nodes, edges = _bad_edge(lambda r: r.pop("dst", None))
    with pytest.raises(IRError, match="NEITHER"):
        validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)


def test_RED_edge_carrying_neither_src_nor_src_repr_raises():
    nodes, edges = _bad_edge(lambda r: r.pop("src", None))
    with pytest.raises(IRError, match="NEITHER"):
        validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)


def test_positive_edge_carrying_both_src_and_src_repr_validates():
    nodes, edges = _load()
    edges = copy.deepcopy(edges)
    edges[0]["src_repr"] = "fastapi"
    validated = validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)
    assert validated == 507 + 3715


def test_RED_endpoint_present_but_wrong_type_raises():
    for field, bad in (("dst", 42), ("dst_repr", 42)):
        nodes, edges = _bad_edge(
            lambda r, f=field, b=bad: r.__setitem__(f, b)
        )
        with pytest.raises(IRError, match=field):
            validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)


def test_RED_wrong_kind_raises():
    nodes, edges = _bad_edge(lambda r: r.__setitem__("kind", "node"))
    with pytest.raises(IRError, match="kind"):
        validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)


def test_RED_malformed_provenance_raises():
    nodes, edges = _bad_node(
        lambda r: r.__setitem__("provenance", {"producer": ""})
    )
    with pytest.raises(IRError, match="provenance"):
        validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)


def test_RED_malformed_evidence_raises():
    nodes, edges = _bad_node(
        lambda r: r.__setitem__("evidence", {"kind": "source"})
    )
    with pytest.raises(IRError, match="evidence"):
        validate_graph(nodes, edges, PYTHON_AST_VOCABULARY)


def test_RED_nodes_must_be_an_object_and_edges_a_list():
    nodes, _ = _load()
    with pytest.raises(IRError, match="object"):
        validate_graph([], [], PYTHON_AST_VOCABULARY)
    with pytest.raises(IRError, match="list"):
        validate_graph(nodes, {}, PYTHON_AST_VOCABULARY)


def test_RED_empty_graph_raises():
    with pytest.raises(IRError, match="nothing"):
        validate_graph({}, [], PYTHON_AST_VOCABULARY)



def test_positive_second_producer_validates_under_its_own_vocabulary():
    n = {
        "fe://component/App": {
            "kind": "node",
            "node_type": "rune",
            "id": "fe://component/App",
            "dotted": "App",
            "file": "src/App.svelte",
            "docstring": None,
        }
    }
    e = [
        {
            "kind": "edge",
            "edge_type": "mutates_state",
            "src": "fe://component/App",
            "dst_repr": "count",
            "line": 12,
        }
    ]
    fe = Vocabulary(
        node_types=["rune"],
        edge_types=["mutates_state"],
        producer="second_producer",
    )
    validated = validate_graph(n, e, fe)
    assert validated == 2


def test_RED_second_producer_refused_under_python_ast_vocabulary():
    n = {
        "fe://component/App": {
            "kind": "node",
            "node_type": "rune",
            "id": "fe://component/App",
            "dotted": "App",
            "file": "src/App.svelte",
            "docstring": None,
        }
    }
    e = [
        {
            "kind": "edge",
            "edge_type": "mutates_state",
            "src": "fe://component/App",
            "dst_repr": "count",
            "line": 12,
        }
    ]
    with pytest.raises(IRError, match="node_type"):
        validate_graph(n, e, PYTHON_AST_VOCABULARY)



def test_positive_wide_probe_all_three_nullable_fields_on_one_record():
    n = {
        "fe://component/App": {
            "kind": "node",
            "node_type": "rune",
            "id": "fe://component/App",
            "dotted": None,
            "file": None,
            "docstring": None,
        }
    }
    e = [
        {
            "kind": "edge",
            "edge_type": "mutates_state",
            "src": "fe://component/App",
            "dst_repr": "count",
            "line": 12,
        }
    ]
    fe = Vocabulary(
        node_types=["rune"],
        edge_types=["mutates_state"],
        producer="wide_probe",
    )
    validated = validate_graph(n, e, fe)
    assert validated == 2


def test_RED_wide_probe_record_refused_under_non_admitting_vocabulary():
    n = {
        "fe://component/App": {
            "kind": "node",
            "node_type": "rune",
            "id": "fe://component/App",
            "dotted": None,
            "file": None,
            "docstring": None,
        }
    }
    e = [
        {
            "kind": "edge",
            "edge_type": "mutates_state",
            "src": "fe://component/App",
            "dst_repr": "count",
            "line": 12,
        }
    ]
    with pytest.raises(IRError, match="node_type"):
        validate_graph(n, e, PYTHON_AST_VOCABULARY)


def test_RED_wrong_type_raises_but_null_does_not():
    base = {
        "kind": "node",
        "node_type": "rune",
        "id": "fe://component/App",
        "dotted": None,
        "file": None,
        "docstring": None,
    }
    e = [
        {
            "kind": "edge",
            "edge_type": "mutates_state",
            "src": "fe://component/App",
            "dst_repr": "count",
            "line": 12,
        }
    ]
    fe = Vocabulary(
        node_types=["rune"],
        edge_types=["mutates_state"],
        producer="wide_probe",
    )
    for field, bad in (("file", 42), ("dotted", 42), ("docstring", 42)):
        n = {"fe://component/App": dict(base)}
        n["fe://component/App"][field] = bad
        with pytest.raises(IRError, match=field):
            validate_graph(n, e, fe)


def test_RED_vocabulary_with_empty_node_types_raises():
    with pytest.raises(IRError, match="node_types"):
        Vocabulary(node_types=[], edge_types=["imports"], producer="empty")
    with pytest.raises(IRError, match="edge_types"):
        Vocabulary(node_types=["module"], edge_types=[], producer="empty")


def test_RED_vocabulary_whose_types_are_not_strings_raises():
    with pytest.raises(IRError, match="node_types"):
        Vocabulary(node_types=["module", 42], edge_types=["imports"], producer="bad")
    with pytest.raises(IRError, match="edge_types"):
        Vocabulary(node_types=["module"], edge_types=["imports", None], producer="bad")
    with pytest.raises(IRError, match="producer"):
        Vocabulary(node_types=["module"], edge_types=["imports"], producer="")


def test_RED_validate_graph_without_vocabulary_raises_typeerror():
    import inspect

    p = inspect.signature(validate_graph).parameters["vocabulary"]
    assert p.default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        validate_graph({}, [])
