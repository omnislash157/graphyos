from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from graphy.cartograph import resolve_graph
from graphy.ir import IRError, validate_graph, Vocabulary



@dataclass(frozen=True)
class ResolvedShard:
    nodes: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    """Full node records in input order.  Each dict preserves the original fields
    (id, file, stub, dotted, source, …)."""

    edges: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    """Canonical directed edges in input order.  Every edge dict carries at least
    ``src``, ``dst``, and ``edge_type``."""

    residuals: tuple[Any, ...] = field(default_factory=tuple)
    """Malformed node or edge records that could not be parsed."""


@dataclass(frozen=True)
class OverrideRecord:
    record_kind: str
    tenant_id: str
    source_path: str
    payload: dict[str, Any] = field(default_factory=dict)
    source_evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.record_kind, str) or not self.record_kind:
            raise ValueError("record_kind must be a non-empty string")
        if not isinstance(self.tenant_id, str) or not self.tenant_id:
            raise ValueError("tenant_id must be a non-empty string")
        if not isinstance(self.source_path, str) or not self.source_path:
            raise ValueError("source_path must be a non-empty string")


@dataclass(frozen=True)
class OverrideIR:
    records: tuple[OverrideRecord, ...] = field(default_factory=tuple)
    covered_leaf_paths: frozenset[str] = field(default_factory=frozenset)
    literal_join_schemes: frozenset[str] = field(default_factory=frozenset)




def _escape_json_pointer_segment(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _json_pointer(*segments: str) -> str:
    return "/" + "/".join(_escape_json_pointer_segment(s) for s in segments)




def _scalar_leaves(
    obj: Any,
    path: list[str],
    metadata_prefix: str = "_",
    non_metadata_residual_paths: frozenset[tuple[str, ...]] = frozenset(),
) -> list[tuple[list[str], Any]]:
    leaves: list[tuple[list[str], Any]] = []

    def _walk(o: Any, segs: list[str]) -> None:
        if segs and segs[-1].startswith(metadata_prefix):
            t = tuple(segs)
            if t not in non_metadata_residual_paths:
                return
        if isinstance(o, dict):
            for k, v in o.items():
                _walk(v, segs + [str(k)])
        elif isinstance(o, list):
            for i, v in enumerate(o):
                _walk(v, segs + [str(i)])
        else:
            leaves.append((segs, o))

    _walk(obj, path)
    return leaves




_CLASSIFICATION_TABLE: tuple[tuple[tuple[str, ...], str], ...] = (
    (("alias_overrides",), "alias"),
    (("substrates", "frontend", "specifier_overrides"), "alias"),

    (("substrates", "frontend", "fetch_url_overrides"), "normalized_identity"),
    (("substrates", "bbx", "termtype_overrides"), "normalized_identity"),
    (("substrates", "telnet", "termtype_overrides"), "normalized_identity"),
    (("substrates", "sql_lex", "sql_fn_overrides"), "normalized_identity"),
    (("substrates", "sql_lex", "sql_dialect_equiv"), "normalized_identity"),

    (("substrates", "frontend", "component_slips"), "edge"),

    (("substrates", "frontend", "ws_type_overrides"), "conditional_overlay"),
    (("substrates", "rust", "impl_overrides"), "conditional_overlay"),


    (("registered_joins", "literal_joins"), "federation_policy"),
    (("registered_joins", "edge_joins"), "federation_policy"),

    (("substrate_roster", "grandfathered"), "substrate_admission"),
    (("substrate_roster", "admitted"), "substrate_admission"),

    (("projection_registry",), "projection"),
)


def _classify_path(segments: tuple[str, ...]) -> str | None:
    for prefix, kind in _CLASSIFICATION_TABLE:
        if len(segments) >= len(prefix) and segments[:len(prefix)] == prefix:
            return kind
    return None




def _detect_duplicate_json_keys(data: str) -> list[str]:
    dupes: list[str] = []
    path_stack: list[str] = []

    def _hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        result: dict[str, Any] = {}
        for k, v in pairs:
            if k in seen:
                ctx = "/".join(path_stack + [k]) if path_stack else k
                dupes.append(ctx)
            seen.add(k)
            result[k] = v
        return result

    decoder = json.JSONDecoder(object_pairs_hook=_hook)
    try:
        decoder.decode(data)
    except json.JSONDecodeError:
        pass
    return dupes


def _detect_alias_cycle(alias_section: dict[str, str]) -> list[str]:
    cycles: list[str] = []
    visited: set[str] = set()
    for key in alias_section:
        if key in visited:
            continue
        path: list[str] = []
        cur: str | None = key
        while cur is not None and cur in alias_section:
            if cur in path:
                cycle_start = path.index(cur)
                cycle_str = " -> ".join(path[cycle_start:] + [cur])
                cycles.append(cycle_str)
                break
            path.append(cur)
            visited.add(cur)
            cur = alias_section.get(cur)
    return cycles


def _canonical_payload(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))




WORMHOLE_SIDECAR = "wormhole_edges.json"


def _sidecar_edges(gd: Path) -> list:
    """Edges the resolver derived from the producer's text labels (`graphy converge --resolve`).
    They ride beside edges.json, never inside it: the producer's output stays verbatim."""
    path = gd / WORMHOLE_SIDECAR
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    edges = raw.get("edges") if isinstance(raw, dict) else raw
    return list(edges) if isinstance(edges, list) else []


def load_graph_ir(graph_dir: str | Path) -> ResolvedShard:
    gd = resolve_graph(Path(graph_dir))
    nodes_raw = json.loads((gd / "nodes.json").read_text(encoding="utf-8"))
    edges_raw = json.loads((gd / "edges.json").read_text(encoding="utf-8"))
    sidecar = _sidecar_edges(gd)
    if sidecar:
        edges_raw = (list(edges_raw.values()) if isinstance(edges_raw, dict) else list(edges_raw)) + sidecar

    nodes_list: list[Any] = []
    node_root_residuals: list[Any] = []
    if isinstance(nodes_raw, dict):
        nodes_list = list(nodes_raw.values())
    elif isinstance(nodes_raw, list):
        nodes_list = nodes_raw
    else:
        node_root_residuals.append(nodes_raw)

    edges_list: list[Any] = []
    edge_root_residuals: list[Any] = []
    if isinstance(edges_raw, dict):
        edges_list = list(edges_raw.values())
    elif isinstance(edges_raw, list):
        edges_list = edges_raw
    else:
        edge_root_residuals.append(edges_raw)

    valid_nodes: list[dict[str, Any]] = []
    node_residuals: list[Any] = []
    for n in nodes_list:
        if isinstance(n, dict) and isinstance(n.get("id"), str):
            valid_nodes.append(n)
        else:
            node_residuals.append(n)

    valid_edges: list[dict[str, Any]] = []
    edge_residuals: list[Any] = []
    for e in edges_list:
        if not isinstance(e, dict):
            edge_residuals.append(e)
            continue
        if "src" in e and "dst" in e and "edge_type" in e:
            if isinstance(e["src"], str) and isinstance(e["dst"], str) and isinstance(e["edge_type"], str):
                valid_edges.append({
                    "src": e["src"],
                    "dst": e["dst"],
                    "edge_type": e["edge_type"],
                    **{
                        k: v
                        for k, v in e.items()
                        if k not in (
                            "src", "dst", "edge_type",
                            "from", "to", "relation",
                        )
                    },
                })
            else:
                edge_residuals.append(e)
        elif "from" in e and "to" in e and "relation" in e:
            if isinstance(e["from"], str) and isinstance(e["to"], str) and isinstance(e["relation"], str):
                valid_edges.append({
                    "src": e["from"],
                    "dst": e["to"],
                    "edge_type": e["relation"],
                    **{k: v for k, v in e.items() if k not in ("from", "to", "relation")},
                })
            else:
                edge_residuals.append(e)
        else:
            edge_residuals.append(e)

    return ResolvedShard(
        nodes=tuple(valid_nodes),
        edges=tuple(valid_edges),
        residuals=tuple(
            node_root_residuals
            + node_residuals
            + edge_root_residuals
            + edge_residuals
        ),
    )


def validate_shard(graph_dir: str | Path, vocabulary: Vocabulary) -> int:
    shard = load_graph_ir(graph_dir)
    nodes: dict[str, Any] = {n["id"]: n for n in shard.nodes}
    edges: list[Any] = list(shard.edges)
    for res in shard.residuals:
        if isinstance(res, dict) and res.get("kind") == "node" and isinstance(res.get("id"), str):
            nodes.setdefault(res["id"], res)
        elif isinstance(res, dict) and res.get("kind") == "edge":
            edges.append(res)
    return validate_graph(nodes, edges, vocabulary)


def load_override_ir(
    registry_path: str | Path,
    *,
    tenant_id: str,
) -> OverrideIR:
    if not tenant_id:
        raise ValueError("tenant_id must be non-empty")

    path = Path(registry_path)
    raw = path.read_text(encoding="utf-8")

    dupes = _detect_duplicate_json_keys(raw)
    if dupes:
        raise ValueError(
            f"Duplicate JSON object key(s) detected: {dupes}"
        )

    try:
        registry = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed registry JSON: {exc}") from exc
    if not isinstance(registry, dict):
        raise ValueError("Registry root must be a JSON object")

    alias_ov = registry.get("alias_overrides", {})
    if isinstance(alias_ov, dict):
        alias_map: dict[str, str] = {}
        for k, v in alias_ov.items():
            if isinstance(k, str) and not k.startswith("_"):
                alias_map[k] = str(v) if not isinstance(v, str) else v
        cycles = _detect_alias_cycle(alias_map)
        if cycles:
            raise ValueError(
                f"Cycle(s) detected in alias_overrides: {cycles}"
            )

    residual_prefixes: frozenset[tuple[str, ...]] = frozenset()
    all_leaves = _scalar_leaves(
        registry, [],
        metadata_prefix="_",
        non_metadata_residual_paths=residual_prefixes,
    )

    records_list: list[OverrideRecord] = []
    covered_set: set[str] = set()

    for segs, val in all_leaves:
        sp = _json_pointer(*segs)
        kind = _classify_path(tuple(segs))
        if kind is None:
            raise ValueError(
                f"Non-metadata scalar leaf at {sp!r} has no locked classification. "
                f"Value: {val!r}"
            )
        covered_set.add(sp)
        evidence: dict[str, Any] = {}
        for prefix, *_ in _CLASSIFICATION_TABLE:
            if len(segs) >= len(prefix) and segs[:len(prefix)] == prefix:
                evidence["section"] = "/".join(prefix)
                break
        records_list.append(OverrideRecord(
            record_kind=kind,
            tenant_id=tenant_id,
            source_path=sp,
            payload={"value": val},
            source_evidence=evidence,
        ))

    lit_schemes: set[str] = set()
    reg_joins = registry.get("registered_joins", {})
    lj = reg_joins.get("literal_joins", {})
    if isinstance(lj, dict):
        for k in lj:
            if isinstance(k, str) and "://" in k and not k.startswith("_"):
                lit_schemes.add(k.split("://", 1)[0])
    literal_join_schemes = frozenset(lit_schemes)

    records_list.sort(key=lambda r: (
        r.record_kind,
        r.source_path,
        _canonical_payload(r.payload),
    ))

    return OverrideIR(
        records=tuple(records_list),
        covered_leaf_paths=frozenset(covered_set),
        literal_join_schemes=literal_join_schemes,
    )
