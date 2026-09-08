
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Collection, Mapping

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
]

SCHEMA_VERSION = 1

NODE_TYPES = ("module", "func", "class", "method")
EDGE_TYPES = ("imports", "contains", "calls", "inherits", "decorates")

NODE_KIND = "node"
EDGE_KIND = "edge"


class IRError(RuntimeError):
    pass


@dataclass(frozen=True)
class Vocabulary:

    node_types: Collection[str]
    edge_types: Collection[str]
    producer: str

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
            file=file,
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


PYTHON_AST_VOCABULARY = Vocabulary(
    node_types=NODE_TYPES,
    edge_types=EDGE_TYPES,
    producer="python_ast",
)
