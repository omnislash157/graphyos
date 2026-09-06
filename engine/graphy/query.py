from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import NamedTuple, Optional

_PR_HINT = "#"
_HEX_SHA = re.compile(r"^[0-9a-f]{7,40}$")

METRICS_SUFFIX = ".metrics.jsonl"



@dataclass
class LoadStats:
    lines_read: int = 0
    edges_loaded: int = 0
    malformed: int = 0
    orphans: int = 0
    edge_file_present: bool = False


@dataclass
class Mesh:
    edges: list = field(default_factory=list)
    nodes: set = field(default_factory=set)
    load_stats: LoadStats = field(default_factory=LoadStats)


def classify(node_id: str) -> str:
    if _PR_HINT in node_id:
        return "pr"
    if _HEX_SHA.match(node_id):
        return "commit"
    return "file"


def _infer_edge_path(metrics_path: str) -> str:
    if not metrics_path.endswith(METRICS_SUFFIX):
        raise ValueError(
            f"--mesh path must end with {METRICS_SUFFIX!r}, got {metrics_path!r}")
    return metrics_path[: -len(METRICS_SUFFIX)]


def _required_edge_fields(row: dict) -> bool:
    return all(k in row for k in ("from", "to", "relation"))


def load(metrics_path: str) -> Mesh:
    edge_path = _infer_edge_path(metrics_path)
    stats = LoadStats()

    if not os.path.exists(metrics_path):
        raise FileNotFoundError(f"metrics sidecar not found: {metrics_path}")

    edges: list[dict] = []
    nodes: set[str] = set()

    with open(metrics_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            stats.lines_read += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                stats.malformed += 1
                continue
            if not isinstance(row, dict) or not _required_edge_fields(row):
                stats.malformed += 1
                continue
            edges.append(row)
            nodes.add(row["from"])
            nodes.add(row["to"])
    stats.edges_loaded = len(edges)

    stats.edge_file_present = os.path.exists(edge_path)
    if stats.edge_file_present:
        edge_keys: set[tuple] = set()
        with open(edge_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict) and _required_edge_fields(row):
                    edge_keys.add((row["from"], row["to"], row["relation"]))
        for e in edges:
            if (e["from"], e["to"], e["relation"]) not in edge_keys:
                stats.orphans += 1

    return Mesh(edges=edges, nodes=nodes, load_stats=stats)



def _coerce_salience(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _coerce_witnesses(value) -> list:
    if isinstance(value, list):
        return value
    return []


def adjacency(mesh: Mesh) -> dict:
    adj: dict[str, list] = {n: [] for n in mesh.nodes}
    for e in mesh.edges:
        a, b = e["from"], e["to"]
        sal = _coerce_salience(e.get("salience"))
        wit = _coerce_witnesses(e.get("witnesses"))
        adj[a].append((b, sal, wit))
        adj[b].append((a, sal, wit))
    return adj



class NodeState(NamedTuple):
    energy: float
    salience: Optional[float]
    hops: int
    witnesses: list


def activate(adj: dict, seed: str, depth: int, decay: float) -> dict:
    if seed not in adj:
        return {seed: NodeState(energy=1.0, salience=None, hops=0, witnesses=[])}

    state: dict[str, NodeState] = {
        seed: NodeState(energy=1.0, salience=None, hops=0, witnesses=[])
    }
    frontier: list = [seed]

    for hop in range(1, depth + 1):
        next_frontier: list = []
        for node in sorted(frontier, key=lambda n: (-state[n].energy, n)):
            nbrs = adj.get(node, [])
            total = sum(max(0.0, sal) for (_n, sal, _w) in nbrs)
            if total <= 0.0:
                total = 1.0
            parent_energy = state[node].energy
            for nbr, sal, wit in sorted(nbrs, key=lambda x: (-x[1], x[0])):
                if nbr in state:
                    continue
                e = parent_energy * decay * (max(0.0, sal) / total)
                if e <= 0.0:
                    continue
                state[nbr] = NodeState(
                    energy=e, salience=sal, hops=hop, witnesses=wit,
                )
                next_frontier.append(nbr)
        frontier = next_frontier
    return state



def rank(state: dict, top: int, min_salience: float):
    seed_entries = [(k, s) for k, s in state.items() if s.salience is None]
    non_seed = [(k, s) for k, s in state.items() if s.salience is not None]

    qualified = [(k, s) for k, s in non_seed if s.salience >= min_salience]
    qualified_count = len(qualified)

    qualified.sort(key=lambda ks: (-ks[1].energy, -ks[1].salience, ks[0]))

    truncated = qualified_count > top
    kept = qualified[:top]

    ordered_nodes = seed_entries + kept
    return ordered_nodes, qualified_count, truncated



DEFAULT_MESH = "data/substrates/fastapi/brain/git_anchors_cochange.jsonl.metrics.jsonl"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_SEED_NOT_FOUND = 3
EXIT_NO_STORE = 6


def query(seed: str, params: dict, mesh: Mesh) -> dict:
    adj = adjacency(mesh)
    state = activate(adj, seed, params["depth"], params["decay"])
    ordered_nodes, qualified, truncated = rank(state, params["top"], params["min_salience"])

    nodes_out: list[dict] = []
    for node_id, ns in ordered_nodes:
        nodes_out.append({
            "id": node_id,
            "kind": classify(node_id),
            "energy": ns.energy,
            "salience": ns.salience,
            "hops": ns.hops,
            "witnesses": list(ns.witnesses),
        })
    returned_ids = {n["id"] for n in nodes_out}

    induced: list[dict] = []
    for e in mesh.edges:
        a, b = e["from"], e["to"]
        if a in returned_ids and b in returned_ids:
            induced.append({
                "from": a,
                "to": b,
                "relation": e["relation"],
                "salience": _coerce_salience(e.get("salience")),
                "witnesses": _coerce_witnesses(e.get("witnesses")),
            })
    induced.sort(key=lambda x: (-x["salience"], x["from"], x["to"]))

    return {
        "seed": seed,
        "seed_kind": classify(seed),
        "seed_present": seed in mesh.nodes,
        "params": dict(params),
        "nodes": nodes_out,
        "edges": induced,
        "truncated": truncated,
        "counts": {
            "activated": len(state),
            "qualified": qualified,
            "returned": len(nodes_out),
            "edges": len(induced),
        },
    }


def _format_human(result: dict, mesh: Mesh) -> str:
    out: list[str] = []
    out.append(f"seed: {result['seed']}  ({result['seed_kind']}, "
               f"{'present' if result['seed_present'] else 'NOT FOUND'} in mesh)")
    out.append(f"params: {result['params']}")
    cnt = result["counts"]
    out.append(f"counts: activated={cnt['activated']} qualified={cnt['qualified']} "
               f"returned={cnt['returned']} edges={cnt['edges']}  "
               f"{'(truncated)' if result['truncated'] else ''}")
    out.append("")
    out.append("nodes (energy desc, seed first):")
    returned_ids = {n["id"] for n in result["nodes"]}
    for n in result["nodes"]:
        sal_str = "—" if n["salience"] is None else f"{n['salience']:.3f}"
        marker = ""
        if n["salience"] is not None:
            has_admit_edge = any(
                (e["from"] == n["id"] or e["to"] == n["id"])
                and ({e["from"], e["to"]} - {n["id"]}).pop() in returned_ids
                for e in result["edges"]
            )
            if not has_admit_edge:
                marker = "  (coupling parent below floor)"
        out.append(f"  [{n['kind']:<6}] {n['id']:<55} energy={n['energy']:.6g} "
                   f"sal={sal_str:<7} hops={n['hops']}{marker}")
    if result["edges"]:
        out.append("")
        out.append("edges (induced subgraph, salience desc):")
        for e in result["edges"]:
            out.append(f"  [{e['relation']:<8}] {e['from']:<35} ↔ {e['to']:<35} "
                       f"sal={e['salience']:.3f}  witnesses={len(e['witnesses'])}")
    s = mesh.load_stats
    out.append("")
    out.append(f"load_stats: lines_read={s.lines_read} edges_loaded={s.edges_loaded} "
               f"malformed={s.malformed} orphans={s.orphans} "
               f"edge_file_present={s.edge_file_present}")
    return "\n".join(out)


def _strict_decay(v) -> float:
    f = float(v)
    if not (0.0 < f < 1.0):
        raise argparse.ArgumentTypeError("--decay must be strictly between 0 and 1")
    return f


def _pos_int_min1(v) -> int:
    i = int(v)
    if i < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return i


def _nonneg_float(v) -> float:
    f = float(v)
    if f < 0.0:
        raise argparse.ArgumentTypeError("must be >= 0.0")
    return f


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cochange query",
        description="SERVE — coupling-oracle over the cochange mesh "
                    "(contract: serve_spec.md, in git history — see the module docstring).",
    )
    p.add_argument("seed", help="the query seed: a file path, a PR id (owner/repo#N), or a commit SHA")
    p.add_argument("--depth", type=_pos_int_min1, default=2, help="max BFS hops (default 2)")
    p.add_argument("--top", type=_pos_int_min1, default=25, help="cap on returned non-seed nodes (default 25)")
    p.add_argument("--min-salience", type=_nonneg_float, default=0.0,
                   help="floor on a node's admitting-edge salience (default 0.0)")
    p.add_argument("--decay", type=_strict_decay, default=0.5,
                   help="per-hop decay, strictly in (0,1) (default 0.5)")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--mesh", default=None,
                     help=f"path to the metrics sidecar (must end with {METRICS_SUFFIX!r}); "
                          f"default = {DEFAULT_MESH!r}")
    src.add_argument("--mesh-set", dest="mesh_set", metavar="A,B,C", default=None,
                     help="route through cochange.cross_substrate.load_set() — union N "
                          "substrate AST graphs on shared <owner>:// symbol ids and walk "
                          "across the package boundary (per git history). "
                          "Comma-separated substrate names, e.g. fastapi,python313_docs. "
                          "The seed is a <substrate>:// symbol id. Result is bucketed by owning substrate.")
    p.add_argument("--store", default=None,
                   help="with --mesh-set: path to the compiled store "
                        "(default: the roster's own, via federated_store.store_path_for).")
    p.add_argument("--materialize", action="store_true",
                   help="with --mesh-set: spread over a fully materialized mesh instead of "
                        "the store. The reference implementation — correct, and it loads the "
                        "WHOLE mesh to answer a bounded question. Opt-in on purpose: this is "
                        "never a silent fallback.")
    p.add_argument("--explains", action="store_true",
                   help="with --mesh-set: add an EXPLANATIONS section listing endpoints whose "
                        "admitting edge relation is in the DOC_EXPLAINS family "
                        "(governed_by ∪ documented_by) — 'what doc/doctrine explains this?'. "
                        "The full mesh is traversed; only DOC_EXPLAINS-admitted endpoints are reported.")
    p.add_argument("--tenant-id",
                   help="the receipt-name for every OverrideRecord minted on this walk — "
                        "graphy resolves identity only through a declared Tenant, and the "
                        "receipt name is part of that declaration.")
    p.add_argument("--data-home",
                   help="the tenant data_home holding the `<slug>_graph` directories and "
                        "the federation scheme index.")
    p.add_argument("--join-keys",
                   help="path to the tenant's substrate_override_registry.json.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--json", dest="emit_json", action="store_true",
                   help="emit the Result as JSON to stdout")
    g.add_argument("--human", dest="emit_json", action="store_false",
                   help="emit a human-readable summary (default)")
    p.set_defaults(emit_json=False)
    return p


def main(argv: Optional[list] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    params = {
        "depth": args.depth,
        "top": args.top,
        "min_salience": args.min_salience,
        "decay": args.decay,
    }

    if args.mesh_set is not None:
        substrates = [x.strip() for x in args.mesh_set.split(",") if x.strip()]
        if not substrates:
            print("cochange query: --mesh-set needs ≥1 comma-separated substrate name",
                  file=sys.stderr)
            return EXIT_USAGE
        missing = [flag for flag, val in (("--tenant-id", args.tenant_id),
                                          ("--data-home", args.data_home),
                                          ("--join-keys", args.join_keys)) if not val]
        if missing:
            parser.error("--mesh-set requires declared identity: missing "
                         + ", ".join(missing))
        from graphy.cross_substrate import _cli_tenant
        tenant = _cli_tenant(args.data_home, args.join_keys)

        if not args.materialize:
            from graphy import federated_store as fstore
            from graphy.cross_substrate import (
                _print_buckets, explanations_from_store,
            )
            try:
                store = fstore.open_for(substrates, db_path=args.store, on_stale="warn",
                                        tenant=tenant, tenant_id=args.tenant_id)
            except fstore.StoreError as e:
                print(f"cochange query: {e}", file=sys.stderr)
                print("    (or pass --materialize to spread over the mesh directly, "
                      "at full load cost)", file=sys.stderr)
                return EXIT_NO_STORE
            sresult = fstore.spread(store, args.seed, params["depth"], params["top"],
                                    params["decay"], params["min_salience"])
            if args.explains:
                sresult["explanations"] = explanations_from_store(
                    store, args.seed, params["depth"])
            if args.emit_json:
                print(json.dumps(sresult, indent=2, sort_keys=False))
            else:
                print(f"mesh-set (store {store.generation()}): "
                      f"{','.join(sorted(substrates))}", file=sys.stderr)
                _print_buckets(sresult)
                if args.explains:
                    _print_explanations(sresult["explanations"])
            if not sresult["seed_present"]:
                print(f"seed {args.seed!r} not found in store "
                      f"(generation {store.generation()})", file=sys.stderr)
                return EXIT_SEED_NOT_FOUND
            return EXIT_OK

        from graphy import federated_store as fstore
        from graphy.cross_substrate import (
            _print_buckets, explanations_from_store,
        )
        try:
            shard = fstore.ShardStore(substrates, tenant=tenant, tenant_id=args.tenant_id)
        except (FileNotFoundError, OSError) as e:
            print(f"cochange query: cannot load mesh-set {substrates!r}: {e}", file=sys.stderr)
            return EXIT_USAGE
        mresult = fstore.spread(shard, args.seed, params["depth"], params["top"],
                                params["decay"], params["min_salience"])
        if args.explains:
            mresult["explanations"] = explanations_from_store(
                shard, args.seed, params["depth"])
        if args.emit_json:
            print(json.dumps(mresult, indent=2, sort_keys=False))
        else:
            s = shard.mesh.stats
            print(f"mesh-set {s.substrates} (materialized): nodes={s.nodes} "
                  f"intra={s.intra_edges} cross={s.cross_edges} "
                  f"unresolved={s.unresolved_cross} malformed={s.malformed_endpoint}",
                  file=sys.stderr)
            _print_buckets(mresult)
            if args.explains:
                _print_explanations(mresult["explanations"])
        if not mresult["seed_present"]:
            print(f"seed {args.seed!r} not found in mesh-set "
                  f"({len(shard.mesh.nodes)} nodes)", file=sys.stderr)
            return EXIT_SEED_NOT_FOUND
        return EXIT_OK

    mesh_path = args.mesh or DEFAULT_MESH
    try:
        mesh = load(mesh_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"cochange query: {e}", file=sys.stderr)
        return EXIT_USAGE
    except OSError as e:
        print(f"cochange query: cannot read --mesh {mesh_path!r}: {e}", file=sys.stderr)
        return EXIT_USAGE

    result = query(args.seed, params, mesh)

    if args.emit_json:
        print(json.dumps(result, indent=2, sort_keys=False))
    else:
        print(_format_human(result, mesh))

    if not result["seed_present"]:
        print(f"seed {args.seed!r} not found in mesh ({len(mesh.nodes)} nodes)",
              file=sys.stderr)
        return EXIT_SEED_NOT_FOUND
    return EXIT_OK


def _print_mesh_set_human(mset, result: dict, explains: bool = False) -> None:
    from graphy.cross_substrate import _print_human
    _print_human(mset, result)
    if explains:
        _print_explanations(result.get("explanations", []))


def _print_explanations(exps: list) -> None:
    print()
    print(f"EXPLANATIONS (DOC_EXPLAINS endpoints — what doc/doctrine explains this seed): {len(exps)}")
    for e in exps:
        print(f"  --{e['relation']}--> [{e['owner']}] hops={e['hops']}  {e['id']}")


if __name__ == "__main__":
    sys.exit(main())
