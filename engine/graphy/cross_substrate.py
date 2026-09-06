from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from graphy.native_json_graph_ir import (
    load_graph_ir,
    load_override_ir,
)
from graphy.query import activate, rank
from graphy._shared import (
    _ast_edge_salience,
    _shim_adj_for_activate,
)
from graphy.tenant import Tenant

WIRE_BUCKET = "wire"
RESERVED_SCHEMES = {"fetch", "artifact", "impl", "doctrine", "scrape"}
DOC_SCHEMES = frozenset({"scrape"})
DOC_EXPLAINS = frozenset({"governed_by", "documented_by"})


def load_standard(index_path: str | os.PathLike) -> frozenset:
    """The schemes the scheme index names as the ecosystem's standard library (``_meta.standard``),
    written by the producer's ring receipt. Absent means none — never the running interpreter's."""
    try:
        with open(index_path, encoding="utf-8") as fh:
            meta = json.load(fh).get("_meta") or {}
    except (OSError, ValueError, AttributeError):
        return frozenset()
    std = meta.get("standard") or ()
    return frozenset(str(x) for x in std) if isinstance(std, (list, tuple)) else frozenset()

WITH = "with"
AGAINST = "against"
BOTH = "both"
UNKNOWN = "unknown"


def _scheme(node_id: str) -> str | None:
    if isinstance(node_id, str) and "://" in node_id:
        return node_id.split("://", 1)[0]
    return None


def _load_scheme_owners(index_path: str | os.PathLike) -> dict:
    if not os.path.exists(index_path):
        print(f"cross_substrate: NO scheme index at {index_path} — scheme/slug resolution "
              f"DISABLED, falling back to slug==scheme; edges of any substrate whose slug "
              f"differs from its scheme will read as unresolved. Build it with "
              f"`mesh_federation_gate --build-index`.", file=sys.stderr)
        return {}
    try:
        with open(index_path, encoding="utf-8") as fh:
            index = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"cross_substrate: scheme index at {index_path} UNREADABLE "
              f"({type(e).__name__}: {e}) — scheme/slug resolution DISABLED.", file=sys.stderr)
        return {}
    owners: dict[str, set] = defaultdict(set)
    for slug, rec in index.items():
        if slug.startswith("_") or not isinstance(rec, dict):
            continue
        for scheme in rec.get("own") or ():
            owners[str(scheme)].add(slug)
    return dict(owners)


def _load_literal_join_schemes(registry_path: str | os.PathLike,
                               tenant_id: str | None = None) -> frozenset:
    if not tenant_id or not tenant_id.strip():
        raise ValueError(
            f"_load_literal_join_schemes: tenant_id is required — graphy resolves "
            f"identity only through a declared Tenant; absent or empty tenant_id = refuse"
        )
    try:
        ir = load_override_ir(registry_path, tenant_id=tenant_id)
        return frozenset(ir.literal_join_schemes)
    except Exception:
        return frozenset()


class RosterError(RuntimeError):
    pass


def _index_rows(tenant: Tenant) -> dict:
    index_path = tenant.data_home / ".federation_scheme_index.json"
    if not os.path.exists(index_path):
        raise RosterError(
            f"no federation scheme index at {index_path} — cannot derive a roster. "
            f"Build it with `mesh_federation_gate --build-index`, or pass --mesh-set "
            f"explicitly.")
    try:
        with open(index_path, encoding="utf-8") as fh:
            index = json.load(fh)
    except (OSError, ValueError) as e:
        raise RosterError(f"federation scheme index at {index_path} is unreadable "
                          f"({type(e).__name__}: {e})") from e
    return {k: v for k, v in index.items()
            if not k.startswith("_") and isinstance(v, dict)}


def derive_roster(seed: str, *, tenant: Tenant | None = None,
                  tenant_id: str | None = None, radius: int = 1) -> tuple[list, list]:
    if tenant is None:
        raise ValueError(
            f"derive_roster: tenant is required — graphy resolves identity only "
            f"through a declared Tenant; absent tenant = refuse"
        )
    if not tenant_id or not tenant_id.strip():
        raise ValueError(
            f"derive_roster: tenant_id is required — graphy resolves identity only "
            f"through a declared Tenant; absent or empty tenant_id = refuse"
        )
    if radius < 0:
        raise RosterError(f"radius must be >= 0, got {radius}")
    index = _index_rows(tenant)
    own_by_scheme: dict[str, set] = defaultdict(set)
    for slug, rec in index.items():
        for sch in rec.get("own") or ():
            own_by_scheme[str(sch)].add(slug)

    seed_scheme = _scheme(seed)
    if seed_scheme is None:
        raise RosterError(
            f"seed {seed!r} has no `<scheme>://` prefix, so its owning substrate "
            f"cannot be derived — pass --mesh-set explicitly.")
    roots = own_by_scheme.get(seed_scheme, set())
    if not roots:
        raise RosterError(
            f"no indexed substrate OWNS scheme {seed_scheme!r} (seed {seed!r}). "
            f"Either the index is stale (`mesh_federation_gate --build-index`) or "
            f"that substrate is not on this box.")

    def _partners(slug: str) -> set:
        rec = index.get(slug) or {}
        found: set = set()
        for sch in rec.get("out") or ():
            found |= own_by_scheme.get(str(sch), set())
        mine = {str(s) for s in (rec.get("own") or ())}
        for other, orec in index.items():
            if mine & {str(s) for s in (orec.get("out") or ())}:
                found.add(other)
        found.discard(slug)
        return found

    roster, frontier = set(roots), set(roots)
    for _ in range(radius):
        nxt: set = set()
        for slug in frontier:
            nxt |= _partners(slug)
        nxt -= roster
        if not nxt:
            break
        roster |= nxt
        frontier = nxt

    present, dropped = [], []
    for slug in sorted(roster):
        graph_dir = tenant.data_home / f"{slug}_graph"
        (present if os.path.isdir(graph_dir) else dropped).append(slug)
    if not present:
        raise RosterError(
            f"derived roster {sorted(roster)} for seed {seed!r}, but NONE of them has "
            f"a graph on this box — nothing to load.")
    return present, dropped


@dataclass
class MeshSetStats:
    substrates: list = field(default_factory=list)
    nodes: int = 0
    intra_edges: int = 0
    cross_edges: int = 0
    unresolved_cross: int = 0
    malformed_endpoint: int = 0
    cross_pairs: dict = field(default_factory=dict)


@dataclass
class MeshSet:
    nodes: set
    adjacency: dict
    node_owner: dict
    node_index: dict
    stats: MeshSetStats
    node_records: dict = field(default_factory=dict)
    directed: set = field(default_factory=set)

    def orientation(self, a: str, b: str, relation: str) -> str:
        fwd = (a, b, relation) in self.directed
        rev = (b, a, relation) in self.directed
        if fwd and rev:
            return BOTH
        if fwd:
            return WITH
        if rev:
            return AGAINST
        return UNKNOWN


def load_set(substrates: list[str], *, tenant: Tenant | None = None,
             tenant_id: str | None = None) -> MeshSet:
    if tenant is None:
        raise ValueError(
            f"load_set: tenant is required — graphy resolves identity only through "
            f"a declared Tenant; absent tenant = refuse"
        )
    if not tenant_id or not tenant_id.strip():
        raise ValueError(
            f"load_set: tenant_id is required — graphy resolves identity only through "
            f"a declared Tenant; absent or empty tenant_id = refuse"
        )
    stats = MeshSetStats(substrates=list(substrates))
    adj: dict[str, list] = defaultdict(list)
    all_nodes: set[str] = set()
    node_owner: dict[str, str] = {}
    node_index: dict[str, set] = {s: set() for s in substrates}
    loaded = set(substrates)
    data_home = Path(tenant.data_home)
    scheme_index_path = data_home / ".federation_scheme_index.json"
    join_keys_path = Path(tenant.join_keys)
    literal_join_schemes = _load_literal_join_schemes(join_keys_path, tenant_id=tenant_id)
    standard = load_standard(scheme_index_path)
    scheme_owners = {sch: (slugs & loaded)
                     for sch, slugs in _load_scheme_owners(scheme_index_path).items()
                     if slugs & loaded}
    own_schemes = defaultdict(set)
    for sch, slugs in scheme_owners.items():
        for slug in slugs:
            own_schemes[slug].add(sch)
    graph_edges: dict[str, list] = {}
    directed: set = set()

    node_records: dict[str, dict] = {}
    for s in substrates:
        graph_dir = str(data_home / f"{s}_graph")
        gir = load_graph_ir(graph_dir)
        nodes = gir.nodes
        edges = gir.edges
        graph_edges[s] = edges
        for n in nodes:
            nid = n.get("id")
            if not nid:
                continue
            all_nodes.add(nid)
            node_index[s].add(nid)
            incumbent = node_records.get(nid)
            if incumbent is None:
                node_owner[nid] = s
                node_records[nid] = n
            elif incumbent.get("stub") and not n.get("stub"):
                node_owner[nid] = s
                node_records[nid] = n
    stats.nodes = len(all_nodes)

    def _endpoint(ep: object, cur: str) -> str:
        if not isinstance(ep, str):
            return "malformed"
        sch = _scheme(ep)
        if sch is None or sch in RESERVED_SCHEMES or sch in standard:
            return "ok"
        if sch == cur or sch in own_schemes.get(cur, ()):
            return "ok"
        if sch in loaded and ep in node_index[sch]:
            return "ok"
        for owner_slug in scheme_owners.get(sch, ()):
            if ep in node_index[owner_slug]:
                return "ok"
        if sch in literal_join_schemes and ep in node_index[cur]:
            return "ok"
        return "unresolved"

    for s in substrates:
        for e in graph_edges[s]:
            frm, to, rel = e.get("src"), e.get("dst"), e.get("edge_type")
            vf, vt = _endpoint(frm, s), _endpoint(to, s)
            if vf == "malformed" or vt == "malformed":
                stats.malformed_endpoint += 1
                continue
            if vf == "unresolved" or vt == "unresolved":
                stats.unresolved_cross += 1
                continue
            sal = _ast_edge_salience(rel)
            adj[frm].append((to, sal, [], rel))
            adj[to].append((frm, sal, [], rel))
            directed.add((frm, to, rel))
            all_nodes.add(frm)
            all_nodes.add(to)
            owner_f = node_owner.get(frm, s)
            owner_t = node_owner.get(to, s)
            if owner_f != owner_t and owner_f in loaded and owner_t in loaded:
                stats.cross_edges += 1
                key = frozenset((owner_f, owner_t))
                stats.cross_pairs[key] = stats.cross_pairs.get(key, 0) + 1
            else:
                stats.intra_edges += 1

    for nid in all_nodes:
        if nid not in node_owner:
            sch = _scheme(nid)
            node_owner[nid] = (WIRE_BUCKET if sch in RESERVED_SCHEMES or sch in standard
                               else sch if sch in loaded else (sch or WIRE_BUCKET))

    return MeshSet(nodes=all_nodes, adjacency=dict(adj),
                   node_owner=node_owner, node_index=node_index, stats=stats,
                   node_records=node_records, directed=directed)


def query_set(mesh: MeshSet, seed: str, depth: int, top: int,
              decay: float, min_salience: float) -> dict:
    state = activate(_shim_adj_for_activate(mesh.adjacency), seed, depth, decay)
    by_owner: dict[str, dict] = defaultdict(dict)
    for nid, ns in state.items():
        by_owner[mesh.node_owner.get(nid, WIRE_BUCKET)][nid] = ns
    buckets: dict[str, list] = {}
    for owner, bstate in by_owner.items():
        ordered, _qualified, _truncated = rank(bstate, top, min_salience)
        buckets[owner] = [
            {"id": nid, "energy": ns.energy, "salience": ns.salience, "hops": ns.hops}
            for nid, ns in ordered
        ]
    return {
        "seed": seed,
        "seed_present": seed in mesh.nodes,
        "seed_owner": mesh.node_owner.get(seed),
        "activated": len(state),
        "buckets": buckets,
    }


def explanations(mesh: MeshSet, seed: str, depth: int) -> list:
    return _explanations_core(
        lambda n: ((nbr, rel) for (nbr, _s, _w, rel) in mesh.adjacency.get(n, [])),
        lambda n: mesh.node_owner.get(n, WIRE_BUCKET), seed, depth)


def explanations_from_store(store, seed: str, depth: int) -> list:
    return _explanations_core(
        lambda n: ((x.node, x.relation) for x in store.neighbours(n)),
        lambda n: store.membership(n) or WIRE_BUCKET, seed, depth)


def _explanations_core(nbrs_of, owner_of, seed: str, depth: int) -> list:
    hop: dict[str, int] = {seed: 0}
    frontier = [seed]
    for h in range(1, depth + 1):
        nxt: list[str] = []
        for node in frontier:
            for (nbr, _rel) in nbrs_of(node):
                if nbr not in hop:
                    hop[nbr] = h
                    nxt.append(nbr)
        frontier = nxt

    best: dict[tuple, int] = {}
    for node, hn in hop.items():
        if hn >= depth:
            continue
        for (nbr, rel) in nbrs_of(node):
            if rel in DOC_EXPLAINS and _scheme(nbr) in DOC_SCHEMES:
                key = (nbr, rel)
                cand = hn + 1
                if key not in best or cand < best[key]:
                    best[key] = cand
    out = [{"id": k[0], "relation": k[1], "hops": v, "owner": owner_of(k[0])}
           for k, v in best.items()]
    out.sort(key=lambda r: (r["hops"], r["id"], r["relation"]))
    return out


@dataclass
class Step:
    src: str
    dst: str
    relation: str
    direction: str
    owner_src: str
    owner_dst: str


@dataclass
class PathResult:
    seed: str
    target: str
    found: bool
    steps: list = field(default_factory=list)
    visited: int = 0
    stopped_by: str | None = None
    cursor: object | None = None


def path_to(mesh: MeshSet, seed: str, target: str, max_depth: int = 6,
            max_nodes: int = 250_000) -> PathResult:
    if seed not in mesh.nodes:
        return PathResult(seed=seed, target=target, found=False, stopped_by="seed-absent")
    if target not in mesh.nodes:
        return PathResult(seed=seed, target=target, found=False, stopped_by="target-absent")

    prev: dict[str, tuple] = {seed: (None, None)}
    frontier = [seed]
    stopped = None
    reached = seed == target
    hops = 0
    while not reached and stopped is None and frontier and hops < max_depth:
        hops += 1
        nxt: list[str] = []
        for node in frontier:
            for (nbr, _sal, _wit, rel) in mesh.adjacency.get(node, []):
                if nbr in prev:
                    continue
                prev[nbr] = (node, rel)
                if nbr == target:
                    reached = True
                    break
                if len(prev) > max_nodes:
                    stopped = "max_nodes"
                    break
                nxt.append(nbr)
            if reached or stopped:
                break
        frontier = nxt
    if not reached and stopped is None and hops >= max_depth and frontier:
        stopped = "max_depth"

    if not reached:
        return PathResult(seed=seed, target=target, found=False,
                          visited=len(prev), stopped_by=stopped)

    chain: list[str] = []
    cur = target
    while cur is not None:
        chain.append(cur)
        cur = prev[cur][0]
    chain.reverse()

    steps = []
    for a, b in zip(chain, chain[1:]):
        rel = prev[b][1]
        steps.append(Step(src=a, dst=b, relation=rel,
                          direction=mesh.orientation(a, b, rel),
                          owner_src=mesh.node_owner.get(a, WIRE_BUCKET),
                          owner_dst=mesh.node_owner.get(b, WIRE_BUCKET)))
    return PathResult(seed=seed, target=target, found=True, steps=steps,
                      visited=len(prev), stopped_by=None)


SOURCE_ROOTS = {}

HYDRATE_MODES = ("none", "transitions", "all")


def _derive_source_root(src_file: str) -> tuple[str | None, str]:
    head = str(src_file).replace("\\", "/").split("/", 1)[0]
    if not head or not head.isidentifier():
        return None, f"leading path segment {head!r} is not a package name"
    try:
        spec = importlib.util.find_spec(head)
    except (ImportError, ValueError, AttributeError) as e:
        return None, f"find_spec({head!r}) raised {type(e).__name__}: {e}"
    if not spec or not spec.origin:
        return None, f"package {head!r} is not installed on this box"
    candidate = os.path.normpath(
        os.path.join(os.path.dirname(os.path.dirname(spec.origin)), str(src_file)))
    if not os.path.isfile(candidate):
        return None, f"package {head!r} resolves, but {candidate} is not on disk"
    return candidate, "derived from the installed package"


@dataclass
class Material:
    node_id: str
    owner: str | None = None
    kind: str = ""
    granularity: str = ""
    text: str | None = None
    origin: str | None = None
    truncated: bool = False
    error: str | None = None


def hydrate(mesh: MeshSet, node_id: str, max_bytes: int = 64_000) -> Material:
    return _hydrate(mesh.node_owner.get(node_id), mesh.node_records.get(node_id),
                    node_id, max_bytes=max_bytes)


def hydrate_from_store(store, node_id: str, max_bytes: int = 64_000) -> Material:
    return _hydrate(store.membership(node_id), store.record(node_id),
                    node_id, max_bytes=max_bytes)


def _hydrate(owner: str | None, rec: dict | None, node_id: str,
             max_bytes: int = 64_000) -> Material:
    if owner is None:
        return Material(node_id=node_id, error="not a node in this mesh")
    if rec is None:
        return Material(node_id=node_id, owner=owner,
                        error="no node record retained — this id was seen only as an edge "
                              "endpoint, so the owning shard was never loaded")

    src_file = rec.get("file")
    if not src_file:
        return Material(node_id=node_id, owner=owner, kind="node_record",
                        granularity="record",
                        text=json.dumps(rec, indent=2, sort_keys=True, default=str),
                        origin=f"{owner} graph node record")

    root = SOURCE_ROOTS.get(owner)
    if root is not None:
        path = os.path.normpath(os.path.join(root, str(src_file)))
    else:
        derived, why = _derive_source_root(str(src_file))
        if derived is None:
            return Material(node_id=node_id, owner=owner, kind="source_file",
                            error=f"substrate {owner!r} carries a `file` ({src_file!r}) but "
                                  f"its source root is not mapped in SOURCE_ROOTS and could "
                                  f"not be derived: {why}. Guessing a root would mis-resolve "
                                  f"silently, so this reports instead.")
        path = derived
    if not os.path.isfile(path):
        return Material(node_id=node_id, owner=owner, kind="source_file",
                        error=f"source not on this box: {path}")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            body = fh.read(max_bytes + 1)
    except OSError as e:
        return Material(node_id=node_id, owner=owner, kind="source_file",
                        error=f"unreadable ({type(e).__name__}: {e}): {path}")
    truncated = len(body) > max_bytes
    return Material(node_id=node_id, owner=owner, kind="source_file", granularity="file",
                    text=body[:max_bytes], origin=path, truncated=truncated)


_ARROW = {WITH: "──▶", AGAINST: "◀──", BOTH: "◀─▶", UNKNOWN: "─?─"}


def _print_material(m: Material, indent: str = "     ", head_lines: int = 12) -> None:
    if m.error:
        print(f"{indent}✗ NO MATERIAL — {m.error}")
        return
    trunc = " (truncated)" if m.truncated else ""
    print(f"{indent}▾ {m.kind}/{m.granularity} ← {m.origin}{trunc}")
    body = (m.text or "").splitlines()
    for line in body[:head_lines]:
        print(f"{indent}  │ {line[:100]}")
    if len(body) > head_lines:
        print(f"{indent}  │ … {len(body) - head_lines} more line(s)")


def _print_path(res: PathResult, hydrator=None, mode: str = "none",
                max_bytes: int = 64_000) -> None:
    if not res.found:
        why = {"seed-absent": "seed is not a node in this mesh",
               "target-absent": "target is not a node in this mesh",
               "max_depth": "DEPTH BUDGET EXHAUSTED — a path may still exist, raise --depth",
               "max_nodes": "NODE BUDGET EXHAUSTED — a path may still exist, raise --max-nodes",
               }.get(res.stopped_by or "", "no path within the bounded frontier")
        print(f"no path {res.seed} -> {res.target}  ({why}; visited={res.visited})")
        return
    print(f"\n═══ PATH  {res.seed}\n         → {res.target}   "
          f"({len(res.steps)} hop(s), visited={res.visited}) ═══")
    print("  arrow shows the STORED edge direction, not the direction walked:\n")
    if mode == "all" and hydrator is not None and res.steps:
        print(f"  0. [{res.steps[0].owner_src}] {res.seed}")
        _print_material(hydrator(res.seed))
    for i, s in enumerate(res.steps, 1):
        note = "  ⚠ no stored edge behind this adjacency entry" if s.direction == UNKNOWN else ""
        print(f"  {i}. [{s.owner_src}] {s.src}")
        print(f"     {_ARROW[s.direction]} {s.relation} ({s.direction}){note}")
        print(f"     [{s.owner_dst}] {s.dst}")
        if mode in ("transitions", "all") and hydrator is not None:
            _print_material(hydrator(s.dst))


def _print_human(mesh: MeshSet, result: dict) -> None:
    s = mesh.stats
    print(f"mesh-set {s.substrates}: nodes={s.nodes} intra={s.intra_edges} "
          f"cross={s.cross_edges} unresolved={s.unresolved_cross} malformed={s.malformed_endpoint}",
          file=sys.stderr)
    if s.cross_pairs:
        pairs = {" ↔ ".join(sorted(k)): v for k, v in s.cross_pairs.items()}
        print(f"  cross-pairs: {pairs}", file=sys.stderr)
    _print_buckets(result)


def _print_buckets(result: dict) -> None:
    print(f"\n═══ SEED: {result['seed']}  (owner={result['seed_owner']}, "
          f"{'present' if result['seed_present'] else 'NOT FOUND'}) ═══")
    print(f"activated={result['activated']} across {len(result['buckets'])} bucket(s)\n")
    for owner in sorted(result["buckets"]):
        rows = result["buckets"][owner]
        print(f"  ── bucket: {owner}  ({len(rows)}) ──")
        for n in rows[:8]:
            sal = "—" if n["salience"] is None else f"{n['salience']:.3f}"
            nid = n["id"] if len(n["id"]) <= 72 else "…" + n["id"][-71:]
            print(f"     hops={n['hops']} energy={n['energy']:.6g} sal={sal:<8} {nid}")


def _cli_tenant(data_home: str, join_keys: str) -> Tenant:
    dh = Path(data_home).resolve()
    jk = Path(join_keys).resolve()
    return Tenant(
        root=dh.parent,
        data_home=dh,
        adapters=(),
        build_lanes={},
        join_keys=jk,
        cursor="declared-cli",
        policy="refuse",
        journal=dh / ".journal",
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="graphy.cross_substrate",
                                 description="P4 v1 — the --mesh-set loader: walk across substrates on shared symbol ids.")
    ap.add_argument("seed", help="seed node id (a <substrate>://symbol)")
    ap.add_argument("--tenant-id", required=True,
                    help="the receipt-name for every OverrideRecord minted on this walk — "
                         "graphy resolves identity only through a declared Tenant, and the "
                         "receipt name is part of that declaration.")
    ap.add_argument("--data-home", required=True,
                    help="the tenant data_home holding the `<slug>_graph` directories and "
                         "the federation scheme index.")
    ap.add_argument("--join-keys", required=True,
                    help="path to the tenant's substrate_override_registry.json.")
    ap.add_argument("--mesh-set", default=None,
                    help="OVERRIDE the derived roster with explicit comma-separated "
                         "substrate names (e.g. fastapi,python313_docs). Omit it and the "
                         "roster is derived from the seed via the federation index — you "
                         "should not have to know the answer to ask the question.")
    ap.add_argument("--radius", type=int, default=1,
                    help="hops of partner closure when deriving the roster (default 1). "
                         "Ignored when --mesh-set is given.")
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--decay", type=float, default=0.5)
    ap.add_argument("--min-salience", type=float, default=0.0)
    ap.add_argument("--path-to", default=None,
                    help="instead of the salience spread, find the bounded path from the "
                         "seed to this node and print each hop with the STORED edge "
                         "direction (Rung 4 path frames).")
    ap.add_argument("--hydrate", choices=HYDRATE_MODES, default="none",
                    help="materialize destination evidence along a --path-to walk: "
                         "`transitions` hydrates each hop's destination, `all` also "
                         "hydrates the seed. Read-only — a walk never publishes.")
    ap.add_argument("--hydrate-bytes", type=int, default=64_000,
                    help="per-node byte ceiling for --hydrate (default 64000).")
    ap.add_argument("--max-nodes", type=int, default=250_000,
                    help="node budget for --path-to (default 250000). Exhausting it is "
                         "REPORTED, never returned as a bare 'no path'.")
    ap.add_argument("--store", default=None,
                    help="path to the compiled store for --path-to (default: the roster's "
                         "own, via federated_store.store_path_for).")
    ap.add_argument("--materialize", action="store_true",
                    help="run --path-to over a fully materialized mesh instead of the "
                         "store. The reference implementation — correct, and it loads the "
                         "WHOLE mesh to answer a bounded question. Opt-in on purpose: this "
                         "is never a silent fallback.")
    args = ap.parse_args(argv)
    tenant = _cli_tenant(args.data_home, args.join_keys)

    if args.mesh_set is not None:
        substrates = [x.strip() for x in args.mesh_set.split(",") if x.strip()]
        if not substrates:
            print("--mesh-set was given but empty — pass real substrate names, or omit "
                  "the flag entirely to derive the roster from the seed.", file=sys.stderr)
            return 2
    else:
        try:
            substrates, dropped = derive_roster(args.seed, tenant=tenant,
                                                tenant_id=args.tenant_id,
                                                radius=args.radius)
        except RosterError as e:
            print(f"cross_substrate: {e}", file=sys.stderr)
            return 4
        print(f"roster (derived, radius={args.radius}): {','.join(substrates)}",
              file=sys.stderr)
        if dropped:
            print(f"  NOT LOADED (no graph on this box): {','.join(dropped)} — the walk "
                  f"cannot reach them; edges into them will read as unresolved.",
                  file=sys.stderr)
    if args.path_to is not None and not args.materialize:
        from graphy import federated_store as fstore  # noqa: PLC0415
        try:
            store = fstore.open_for(substrates, db_path=args.store,
                                    tenant=tenant, tenant_id=args.tenant_id)
        except fstore.StoreError as e:
            print(f"cross_substrate: {e}", file=sys.stderr)
            print("    (or pass --materialize to walk the mesh directly, at full load cost)",
                  file=sys.stderr)
            return 6
        if store.membership(args.seed) is None:
            print(f"seed {args.seed!r} is not in this store (generation "
                  f"{store.generation()})", file=sys.stderr)
            return 3
        res = fstore.path_to(store, args.seed, args.path_to, max_depth=args.depth,
                             max_nodes=args.max_nodes)
        hyd = None if args.hydrate == "none" else (
            lambda nid: hydrate_from_store(store, nid,
                                           max_bytes=args.hydrate_bytes))
        _print_path(res, hydrator=hyd, mode=args.hydrate, max_bytes=args.hydrate_bytes)
        if res.cursor is not None and not res.found:
            print(f"\n  cursor (resume in generation {store.generation()}):\n"
                  f"    {res.cursor.encode()}")
        if res.found:
            return 0
        return 5 if res.stopped_by in ("max_depth", "max_nodes") else 1

    mesh = load_set(substrates, tenant=tenant, tenant_id=args.tenant_id)
    if args.seed not in mesh.nodes:
        print(f"seed {args.seed!r} not in mesh-set ({len(mesh.nodes)} nodes)", file=sys.stderr)
        return 3
    if args.path_to is not None:
        res = path_to(mesh, args.seed, args.path_to, max_depth=args.depth,
                      max_nodes=args.max_nodes)
        hyd = None if args.hydrate == "none" else (
            lambda nid: hydrate(mesh, nid, max_bytes=args.hydrate_bytes))
        _print_path(res, hydrator=hyd, mode=args.hydrate, max_bytes=args.hydrate_bytes)
        if res.found:
            return 0
        return 5 if res.stopped_by in ("max_depth", "max_nodes") else 1
    from graphy import federated_store as fstore  # noqa: PLC0415
    shard = fstore.ShardStore.from_mesh(mesh, substrates)
    result = fstore.spread(shard, args.seed, args.depth, args.top,
                           args.decay, args.min_salience)
    s = mesh.stats
    print(f"mesh-set {s.substrates}: nodes={s.nodes} intra={s.intra_edges} "
          f"cross={s.cross_edges} unresolved={s.unresolved_cross} "
          f"malformed={s.malformed_endpoint}", file=sys.stderr)
    if s.cross_pairs:
        pairs = {" ↔ ".join(sorted(k)): v for k, v in s.cross_pairs.items()}
        print(f"  cross-pairs: {pairs}", file=sys.stderr)
    _print_buckets(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
