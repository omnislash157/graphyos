
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Collection, Mapping
from graphy._shared import source_sha

SOURCE_SHA = source_sha(__file__)   # the door rules this process runs (graphyos #111)

__all__ = [
    "SCHEMA_VERSION",
    "IRError",
    "Provenance",
    "Evidence",
    "Node",
    "Edge",
    "validate_graph",
    "NODE_TYPES",
    "EDGE_TYPES",
    "Vocabulary",
    "PYTHON_AST_VOCABULARY",
    "DEPENDS",
    "REACHES",
    "STRUCTURAL",
    "LEXICAL",
    "RELATION_CLASSES",
    "DEFAULT_RELATION_CLASS",
]

SCHEMA_VERSION = 1

NODE_TYPES = ("module", "func", "class", "method")
EDGE_TYPES = ("imports", "contains", "calls", "inherits", "decorates")

# WHAT A RELATION MEANS, declared by the producer that mints it (graphyos #68). A tenant could
# always declare what its edge types ARE and never what they MEAN, so every door was blind to any
# vocabulary but python_ast's: a first client minting 67 types across 32 lanes had 35 relation
# types no door would walk, and `blast` on a table with 22 inbound edges answered zero.
#
# Four classes, and the fourth is why there are not two. Measured over 547,767 real edges:
# 18.1% depend, 30.6% are containment, and 51.3% are LEXICAL co-occurrence — one type alone
# (`touched`, commit → file) is 129,044 edges. Admitting everything a tenant mints would make
# blast on a document node return a five-figure set that means nothing, which is a worse door than
# one that answers zero. The dense half of a real store IS the lexical class, so classifying it is
# not a nicety on top of the traversal — it is what keeps the traversal sparse.
DEPENDS = "depends"          # blast follows it, reversed: who is affected if this changes
REACHES = "reaches"          # descend follows it, forward: what this arrives at
STRUCTURAL = "structural"    # containment and scoping — real, and never impact
LEXICAL = "lexical"          # co-occurrence: a seed and a search, never either door
RELATION_CLASSES = frozenset({DEPENDS, REACHES, STRUCTURAL, LEXICAL})

# An undeclared type is LEXICAL, never DEPENDS. Fail quiet, not loud: a shard minted before any
# producer declared anything must degrade to the behaviour it already had, not silently widen
# every blast in the roster it joins.
DEFAULT_RELATION_CLASS = LEXICAL

NODE_KIND = "node"
EDGE_KIND = "edge"


class IRError(RuntimeError):
    pass


@dataclass(frozen=True)
class Vocabulary:

    node_types: Collection[str]
    edge_types: Collection[str]
    producer: str
    # edge_type -> the classes it belongs to. Optional and empty by default, so a producer that
    # declares nothing behaves exactly as it did before (graphyos #68). An edge type absent from
    # this mapping is DEFAULT_RELATION_CLASS.
    relations: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def classes_of(self, edge_type: str) -> tuple[str, ...]:
        """The classes declared for an edge type, or the default for one nobody declared."""
        return tuple(self.relations.get(edge_type, (DEFAULT_RELATION_CLASS,)))

    def types_in(self, relation_class: str) -> frozenset:
        """Every edge type this producer places in a class — the door's question."""
        return frozenset(t for t in self.edge_types if relation_class in self.classes_of(t))

    def __post_init__(self) -> None:
        if isinstance(self.node_types, str) or isinstance(self.edge_types, str):
            raise IRError(
                "Vocabulary.node_types and edge_types must be collections of "
                "strings, not strings themselves"
            )
        try:
            nt = tuple(self.node_types)
            et = tuple(self.edge_types)
        except TypeError as exc:
            raise IRError(
                "Vocabulary.node_types and edge_types must be iterable "
                "collections of strings"
            ) from exc
        if not nt:
            raise IRError(
                "Vocabulary.node_types must be a non-empty collection of strings "
                "— an empty vocabulary admits nothing and must not be treated "
                "as 'admit everything'"
            )
        if not et:
            raise IRError(
                "Vocabulary.edge_types must be a non-empty collection of strings "
                "— an empty vocabulary admits nothing and must not be treated "
                "as 'admit everything'"
            )
        if not all(type(t) is str and t.strip() for t in nt):
            raise IRError(
                "Vocabulary.node_types must contain only non-empty strings"
            )
        if not all(type(t) is str and t.strip() for t in et):
            raise IRError(
                "Vocabulary.edge_types must contain only non-empty strings"
            )
        if type(self.producer) is not str or not self.producer.strip():
            raise IRError("Vocabulary.producer must be a non-empty string")
        object.__setattr__(self, "node_types", nt)
        object.__setattr__(self, "edge_types", et)
        # The declaration is checked against this producer's own edge types: a class for a type it
        # cannot mint is a typo that would otherwise sit in a PROVENANCE forever, declaring meaning
        # for an edge that never arrives.
        try:
            rel = {str(k): tuple(v) if not isinstance(v, str) else (v,)
                   for k, v in dict(self.relations).items()}
        except (TypeError, ValueError) as exc:
            raise IRError(
                "Vocabulary.relations must be a mapping of edge_type -> a collection of "
                "relation classes"
            ) from exc
        unknown_type = sorted(k for k in rel if k not in et)
        if unknown_type:
            raise IRError(
                f"Vocabulary.relations declares {unknown_type} which producer "
                f"{self.producer!r} does not mint — its edge types are {sorted(et)}"
            )
        bad = sorted({c for cs in rel.values() for c in cs} - RELATION_CLASSES)
        if bad:
            raise IRError(
                f"Vocabulary.relations uses unknown relation class(es) {bad}; the classes are "
                f"{sorted(RELATION_CLASSES)}"
            )
        empty = sorted(k for k, cs in rel.items() if not cs)
        if empty:
            raise IRError(
                f"Vocabulary.relations declares {empty} with no class at all — say "
                f"{DEFAULT_RELATION_CLASS!r} to mean 'neither door walks it', never an empty list"
            )
        object.__setattr__(self, "relations", rel)


def _type_name(v: Any) -> str:
    return type(v).__name__


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _parse_optional(record_cls: type, raw: Mapping[str, Any], field: str, where: str):
    value = raw.get(field)
    if value is None:
        return None
    return record_cls.from_mapping(value, f"{where}.{field}")


def _parse_endpoint(
    raw: Mapping[str, Any], resolved_key: str, repr_key: str, where: str
) -> tuple[str | None, str | None]:
    has_resolved = resolved_key in raw
    has_repr = repr_key in raw
    if not has_resolved and not has_repr:
        raise IRError(
            f"{where}: carries NEITHER {resolved_key} nor {repr_key} — an "
            "endpoint needs a resolved or unresolved form"
        )
    resolved = raw.get(resolved_key) if has_resolved else None
    repr_value = raw.get(repr_key) if has_repr else None
    if has_resolved and (not isinstance(resolved, str) or not resolved):
        raise IRError(f"{where}: {resolved_key} must be a non-empty string")
    if has_repr and (not isinstance(repr_value, str) or not repr_value):
        raise IRError(f"{where}: {repr_key} must be a non-empty string")
    return resolved, repr_value


@dataclass(frozen=True)
class Provenance:

    producer: str
    source: str

    @classmethod
    def from_mapping(cls, raw: Any, where: str) -> "Provenance":
        if not isinstance(raw, Mapping):
            raise IRError(
                f"{where}: provenance must be a JSON object, got {_type_name(raw)}"
            )
        producer = raw.get("producer")
        source = raw.get("source")
        if not isinstance(producer, str) or not producer.strip():
            raise IRError(f"{where}: provenance.producer must be a non-empty string")
        if not isinstance(source, str) or not source.strip():
            raise IRError(f"{where}: provenance.source must be a non-empty string")
        return cls(producer=producer, source=source)


@dataclass(frozen=True)
class Evidence:

    kind: str
    ref: str

    @classmethod
    def from_mapping(cls, raw: Any, where: str) -> "Evidence":
        if not isinstance(raw, Mapping):
            raise IRError(
                f"{where}: evidence must be a JSON object, got {_type_name(raw)}"
            )
        kind = raw.get("kind")
        ref = raw.get("ref")
        if not isinstance(kind, str) or not kind.strip():
            raise IRError(f"{where}: evidence.kind must be a non-empty string")
        if not isinstance(ref, str) or not ref.strip():
            raise IRError(f"{where}: evidence.ref must be a non-empty string")
        return cls(kind=kind, ref=ref)


@dataclass(frozen=True)
class Node:

    id: str
    node_type: str
    dotted: str | None = None
    file: str | None = None
    docstring: str | None = None
    kind: str = NODE_KIND
    name: str | None = None
    line: int | None = None
    loc: int | None = None
    is_async: bool | None = None
    args: tuple[str, ...] | None = None
    annotations: tuple[tuple[str, str], ...] | None = None
    returns: str | None = None
    container_class: str | None = None
    provenance: Provenance | None = None
    evidence: Evidence | None = None

    @classmethod
    def from_mapping(cls, key: Any, raw: Any, vocabulary: Vocabulary) -> "Node":
        where = f"node {key!r}"
        if not isinstance(raw, Mapping):
            raise IRError(f"{where}: record must be a JSON object, got {_type_name(raw)}")
        if raw.get("kind") != cls.kind:
            raise IRError(f"{where}: expected kind {cls.kind!r}, got {raw.get('kind')!r}")

        node_type = raw.get("node_type")
        if node_type not in vocabulary.node_types:
            raise IRError(
                f"{where}: unknown node_type {node_type!r} — want one of "
                f"{vocabulary.node_types} under producer {vocabulary.producer!r}"
            )

        id_ = raw.get("id")
        if not isinstance(id_, str) or not id_:
            raise IRError(f"{where}: id must be a non-empty string")
        if id_ != key:
            raise IRError(
                f"{where}: record id {id_!r} disagrees with its dict key {key!r}"
            )

        dotted = raw.get("dotted")
        file = raw.get("file")
        docstring = raw.get("docstring")
        if dotted is not None and not isinstance(dotted, str):
            raise IRError(
                f"{where}: dotted must be a string or null, got {_type_name(dotted)}"
            )
        if file is not None and not isinstance(file, str):
            raise IRError(
                f"{where}: file must be a string or null, got {_type_name(file)}"
            )
        if docstring is not None and not isinstance(docstring, str):
            raise IRError(
                f"{where}: docstring must be a string or null, got "
                f"{_type_name(docstring)}"
            )

        name = raw.get("name")
        if name is not None and not isinstance(name, str):
            raise IRError(f"{where}: name must be a string, got {_type_name(name)}")
        line = raw.get("line")
        if line is not None and not _is_int(line):
            raise IRError(f"{where}: line must be an int, got {_type_name(line)}")
        loc = raw.get("loc")
        if loc is not None and not _is_int(loc):
            raise IRError(f"{where}: loc must be an int, got {_type_name(loc)}")
        is_async = raw.get("is_async")
        if is_async is not None and not isinstance(is_async, bool):
            raise IRError(
                f"{where}: is_async must be a bool, got {_type_name(is_async)}"
            )
        args = raw.get("args")
        if args is not None:
            if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
                raise IRError(f"{where}: args must be a list of strings")
            args_tuple = tuple(args)
        else:
            args_tuple = None
        annotations = raw.get("annotations")
        if annotations is not None:
            if not isinstance(annotations, Mapping) or not all(isinstance(k, str) and isinstance(v, str) for k, v in annotations.items()):
                raise IRError(f"{where}: annotations must be an object of parameter name to annotation text")
            if args_tuple is not None and not set(annotations) <= set(args_tuple):
                raise IRError(f"{where}: annotations name parameters that args does not: {sorted(set(annotations) - set(args_tuple))}")
            annotations_tuple = tuple(annotations.items())
        else:
            annotations_tuple = None
        returns = raw.get("returns")
        if returns is not None and not isinstance(returns, str):
            raise IRError(
                f"{where}: returns must be a string or null, got {_type_name(returns)}"
            )
        container_class = raw.get("container_class")
        if container_class is not None and not isinstance(container_class, str):
            raise IRError(
                f"{where}: container_class must be a string or null, got "
                f"{_type_name(container_class)}"
            )

        provenance = _parse_optional(Provenance, raw, "provenance", where)
        evidence = _parse_optional(Evidence, raw, "evidence", where)

        return cls(
            id=id_,
            node_type=node_type,
            dotted=dotted,
            # The path field is posix on every host, whoever minted the shard. graphy's own
            # producers normalise at the walk, but a tenant's foreign producer resolves a path
            # through pathlib and stores str() — on a first client's roster that was 21 of 23
            # file-bearing lanes, most of them emitters this engine never wrote. Normalising where
            # the TYPED record is built catches every one of them at the same cost, and it is the
            # last place a shard passes through before anything reads it (graphyos #88).
            file=file.replace("\\", "/") if isinstance(file, str) else file,
            docstring=docstring,
            kind=cls.kind,
            name=name,
            line=line,
            loc=loc,
            is_async=is_async,
            args=args_tuple,
            annotations=annotations_tuple,
            returns=returns,
            container_class=container_class,
            provenance=provenance,
            evidence=evidence,
        )


@dataclass(frozen=True)
class Edge:

    edge_type: str
    kind: str = EDGE_KIND
    src: str | None = None
    src_repr: str | None = None
    dst: str | None = None
    dst_repr: str | None = None
    line: int | None = None
    alias: str | None = None
    name: str | None = None
    provenance: Provenance | None = None
    evidence: Evidence | None = None

    @classmethod
    def from_mapping(cls, index: Any, raw: Any, vocabulary: Vocabulary) -> "Edge":
        where = f"edge {index}"
        if not isinstance(raw, Mapping):
            raise IRError(f"{where}: record must be a JSON object, got {_type_name(raw)}")
        if raw.get("kind") != cls.kind:
            raise IRError(f"{where}: expected kind {cls.kind!r}, got {raw.get('kind')!r}")

        edge_type = raw.get("edge_type")
        if edge_type not in vocabulary.edge_types:
            raise IRError(
                f"{where}: unknown edge_type {edge_type!r} — want one of "
                f"{vocabulary.edge_types} under producer {vocabulary.producer!r}"
            )

        src, src_repr = _parse_endpoint(raw, "src", "src_repr", where)
        dst, dst_repr = _parse_endpoint(raw, "dst", "dst_repr", where)

        line = raw.get("line")
        if line is not None and not _is_int(line):
            raise IRError(f"{where}: line must be an int, got {_type_name(line)}")
        alias = raw.get("alias")
        if alias is not None and not isinstance(alias, str):
            raise IRError(
                f"{where}: alias must be a string or null, got {_type_name(alias)}"
            )
        name = raw.get("name")
        if name is not None and not isinstance(name, str):
            raise IRError(f"{where}: name must be a string, got {_type_name(name)}")

        provenance = _parse_optional(Provenance, raw, "provenance", where)
        evidence = _parse_optional(Evidence, raw, "evidence", where)

        return cls(
            edge_type=edge_type,
            kind=cls.kind,
            src=src,
            src_repr=src_repr,
            dst=dst,
            dst_repr=dst_repr,
            line=line,
            alias=alias,
            name=name,
            provenance=provenance,
            evidence=evidence,
        )


def validate_graph(nodes: Any, edges: Any, vocabulary: Vocabulary) -> int:
    if not isinstance(nodes, Mapping):
        raise IRError(
            f"nodes must be a JSON object keyed by node id, got {_type_name(nodes)}"
        )
    if not isinstance(edges, list):
        raise IRError(f"edges must be a JSON list, got {_type_name(edges)}")
    if not isinstance(vocabulary, Vocabulary):
        raise IRError(
            "vocabulary must be a graphy.ir.Vocabulary record naming the producer "
            f"dialect to validate against, got {_type_name(vocabulary)}"
        )

    validated = 0
    for key, raw in nodes.items():
        Node.from_mapping(key, raw, vocabulary)
        validated += 1
    for index, raw in enumerate(edges):
        Edge.from_mapping(index, raw, vocabulary)
        validated += 1

    if validated == 0:
        raise IRError(
            "validate_graph validated 0 records — an empty validation run proves "
            "nothing and must not report success"
        )
    return validated


# Today's door behaviour, written down rather than hardcoded in doors.py. `calls` is the only type
# both doors walk; `contains` is real containment and was never in either door, which is exactly
# STRUCTURAL. A store built from these declarations answers byte-identically to the module
# constants it replaces — that equivalence is the floor's test, not a claim (graphyos #68).
PYTHON_AST_RELATIONS = {
    "calls": (DEPENDS, REACHES),
    "inherits": (DEPENDS,),
    "imports": (DEPENDS,),
    "decorates": (DEPENDS,),
    "contains": (STRUCTURAL,),
}

PYTHON_AST_VOCABULARY = Vocabulary(
    node_types=NODE_TYPES,
    edge_types=EDGE_TYPES,
    producer="python_ast",
    relations=PYTHON_AST_RELATIONS,
)
