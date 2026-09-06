#!/usr/bin/env python3
"""fastapi tenant taps.

    walk.py pillars [--module DOTTED]   recompute the arm partition and its weights from the shard
    walk.py edges NODE [--direction in|out|both]   one node's edges: resolved from the store, labels from the sidecar
    walk.py compile-labels              once, at rebuild: fold the shard's label-only edges into the sidecar

`pillars` is a whole-shard aggregate, so it reads the shard. `edges` is a hop, so it queries the
store and the sidecar and never opens the JSON. A label is a `calls`/`inherits` target the producer
left as text (`dst_repr`). `graphy converge --resolve` turns the ones scope can bind into edges the
store carries (wormhole_edges.json); the label sidecar keeps the rest, each with the qualified
literal the resolver derived, or a CANDIDATE node when exactly one node in the shard has that bare
name — a name match, never a resolved fact. The partition (`partition.json`, the same file
`graphy fanout --partition` cuts by) is the one curated input; every weight, fan-in, fan-out and
cross-pillar count is recomputed on each run. `graphy pillars --against partition.json` proposes the
cut from the store's module graph and names every unit the curated file places differently.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUB = HERE / "substrate"
SHARD = SUB / "fastapi_graph"
LABELS = SUB / ".labels.sqlite"
SIDECAR = SHARD / "wormhole_edges.json"

PARTITION = HERE / "partition.json"


def _cut():
    sys.path.insert(0, str(HERE.parent.parent))
    from graphy.fanout import load_partition
    return load_partition(PARTITION)


CUT = _cut()
ORDER = tuple(CUT.groups) + (CUT.rest,)


def pillar_of(module: str) -> str:
    return CUT.group_of(module)


def _load_shard() -> tuple[dict, list]:
    try:
        nodes = json.loads((SHARD / "nodes.json").read_text(encoding="utf-8"))
        edges = json.loads((SHARD / "edges.json").read_text(encoding="utf-8"))
    except OSError as exc:
        sys.exit(f"no shard at {SHARD} ({exc}) — run rebuild.sh")
    nodes = nodes if isinstance(nodes, dict) else {n["id"]: n for n in nodes}
    return nodes, edges


def _module_of(node: dict) -> str:
    if node.get("node_type") == "module":
        return node.get("dotted", "")
    file = node.get("file") or ""
    if file.endswith(".py"):
        dotted = file[:-3].replace("/", ".")
        return dotted[:-9] if dotted.endswith(".__init__") else dotted
    return (node.get("dotted") or "").rsplit(".", 1)[0]


def cmd_pillars(args: argparse.Namespace) -> int:
    nodes, edges = _load_shard()
    module_of = {nid: _module_of(n) for nid, n in nodes.items()}
    weight = collections.Counter()
    members: dict[str, set] = collections.defaultdict(set)
    for nid, mod in module_of.items():
        p = pillar_of(mod)
        weight[p] += 1
        members[p].add(mod)
    fan_in = collections.Counter()
    fan_out = collections.Counter()
    pair = collections.Counter()
    cross = collections.Counter()
    for e in edges:
        if e.get("edge_type") not in ("imports", "calls", "inherits", "decorates"):
            continue
        src, dst = e.get("src") or "", e.get("dst") or ""
        if src not in module_of or dst not in module_of:
            continue
        ms, md = module_of[src], module_of[dst]
        if ms == md:
            continue
        pair[(ms, md)] += 1
        fan_in[md] += 1
        fan_out[ms] += 1
        cross[(pillar_of(ms), pillar_of(md))] += 1

    if args.module:
        m = args.module
        print(f"{m}  pillar={pillar_of(m)}  fan_in={fan_in[m]}  fan_out={fan_out[m]}")
        print("  depends on:")
        for (a, b), c in sorted(pair.items(), key=lambda kv: -kv[1]):
            if a == m:
                print(f"    {c:4}  -> {b}  [{pillar_of(b)}]")
        print("  depended on by:")
        for (a, b), c in sorted(pair.items(), key=lambda kv: -kv[1]):
            if b == m:
                print(f"    {c:4}  <- {a}  [{pillar_of(a)}]")
        return 0

    print("pillar         nodes  modules")
    for p in ORDER:
        print(f"{p:13} {weight[p]:6}  {', '.join(sorted(members[p]))}")
    print("\ncross-pillar edges (imports+calls+inherits+decorates, module level)")
    print(f"{'from \\ to':13} " + " ".join(f"{p:>12}" for p in ORDER))
    for a in ORDER:
        print(f"{a:13} " + " ".join(f"{cross[(a, b)]:12}" for b in ORDER))
    print("\nmodule                                 fan_in  fan_out  pillar")
    for m in sorted(set().union(*members.values()), key=lambda m: (-fan_in[m], m)):
        if fan_in[m] or fan_out[m]:
            print(f"{m:38} {fan_in[m]:6} {fan_out[m]:8}  {pillar_of(m)}")
    return 0


def _store() -> sqlite3.Connection:
    stores = sorted(SUB.glob(".mesh_store_*.sqlite"))
    if not stores:
        sys.exit(f"no compiled store under {SUB} — run rebuild.sh")
    return sqlite3.connect(f"file:{stores[-1]}?mode=ro", uri=True)


def _resolve(db: sqlite3.Connection, query: str) -> str:
    row = db.execute("SELECT id FROM nodes WHERE id = ?", (query,)).fetchone()
    if row:
        return row[0]
    hits = [r[0] for r in db.execute(
        "SELECT id FROM nodes WHERE id LIKE ? ORDER BY id", (f"%{query}",))]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        sys.exit(f"no node matches {query!r} in the store")
    sys.exit(f"{query!r} is ambiguous in the store — one of:\n  " + "\n  ".join(hits[:20]))


def _sidecar() -> tuple[set, dict]:
    """What `graphy converge --resolve` settled: the (src, rel, label) triples that became edges,
    and the qualified literal it derived for the labels no node carries."""
    if not SIDECAR.is_file():
        return set(), {}
    raw = json.loads(SIDECAR.read_text(encoding="utf-8"))
    done = {(e["src"], e["edge_type"], e["label"]) for e in raw.get("edges", []) if e.get("side", "dst") == "dst"}
    qualified = {(q["src"], q["rel"], q["label"]): f"{q['qualified']} ({q['kind']})"
                 for q in raw.get("qualified", []) if q.get("side") == "dst"}
    return done, qualified


def cmd_compile_labels(args: argparse.Namespace) -> int:
    nodes, edges = _load_shard()
    done, qualified = _sidecar()
    by_name: dict[str, list] = collections.defaultdict(list)
    for nid, n in nodes.items():
        if n.get("node_type") != "module":
            by_name[(n.get("dotted") or "").rsplit(".", 1)[-1]].append(nid)
    rows = []
    resolved = 0
    for e in edges:
        if e.get("dst"):
            continue
        label = str(e.get("dst_repr") or "")
        if not label:
            continue
        key = (e.get("src") or "", e.get("edge_type") or "", label)
        if key in done:
            resolved += 1          # the resolver made it an edge; the store carries it
            continue
        if key in qualified:
            cand = "qualified " + qualified[key]
        else:
            last = label.split("(")[0].rsplit(".", 1)[-1]
            hits = by_name.get(last, [])
            cand = hits[0] if len(hits) == 1 else None
        rows.append((key[0], key[1], label, cand, e.get("line")))
    tmp = SUB / ".labels.sqlite.tmp"
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    db.executescript(
        "CREATE TABLE labels(src TEXT, rel TEXT, label TEXT, candidate TEXT, line INTEGER);"
        "CREATE INDEX i_src ON labels(src); CREATE INDEX i_cand ON labels(candidate);")
    db.executemany("INSERT INTO labels VALUES (?,?,?,?,?)", rows)
    db.commit()
    db.close()
    os.replace(tmp, LABELS)
    print(f"LABELS OK: {len(rows)} label edge(s) left as text"
          + (f" ({resolved} resolved into the store by the sidecar)" if resolved else "")
          + f", {sum(1 for r in rows if r[3] and not str(r[3]).startswith('qualified '))} with a unique-name candidate, "
          f"{sum(1 for r in rows if str(r[3] or '').startswith('qualified '))} qualified by scope -> {LABELS}")
    return 0


def _labels() -> sqlite3.Connection | None:
    if not LABELS.is_file():
        return None
    return sqlite3.connect(f"file:{LABELS}?mode=ro", uri=True)


def cmd_edges(args: argparse.Namespace) -> int:
    db = _store()
    lab = _labels()
    nid = _resolve(db, args.node)
    print(f"{nid}")
    if args.direction in ("out", "both"):
        rows = db.execute("SELECT rel, dst FROM edges WHERE src = ? ORDER BY rel, dst", (nid,)).fetchall()
        print(f"  out, resolved ({len(rows)})")
        for rel, dst in rows:
            print(f"    --{rel}--> {dst}")
        if lab is not None:
            lrows = lab.execute("SELECT rel, label, candidate FROM labels WHERE src = ? "
                                "GROUP BY rel, label, candidate ORDER BY rel, label", (nid,)).fetchall()
            print(f"  out, labels ({len(lrows)})")
            for rel, label, cand in lrows:
                note = ("   " + cand) if str(cand or "").startswith("qualified ") else (f"   candidate: {cand}" if cand else "")
                print(f"    ~~{rel}~~> {label}{note}")
    if args.direction in ("in", "both"):
        rows = db.execute("SELECT rel, src FROM edges WHERE dst = ? ORDER BY rel, src", (nid,)).fetchall()
        print(f"  in, resolved ({len(rows)})")
        for rel, src in rows:
            print(f"    <--{rel}-- {src}")
        if lab is not None:
            lrows = lab.execute("SELECT rel, src, label FROM labels WHERE candidate = ? "
                                "GROUP BY rel, src, label ORDER BY rel, src", (nid,)).fetchall()
            print(f"  in, by label candidate ({len(lrows)})")
            for rel, src, label in lrows:
                print(f"    <~~{rel}~~ {src}   (label {label!r})")
    if lab is None:
        print("  (no label sidecar — run rebuild.sh, or walk.py compile-labels)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="walk.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="verb", required=True)
    p = sub.add_parser("pillars", help="the arm partition and its weights, recomputed from the shard")
    p.add_argument("--module", default=None, help="one module's inter-module partners")
    p.set_defaults(handler=cmd_pillars)
    e = sub.add_parser("edges", help="one node's typed edges, from the compiled store")
    e.add_argument("node", help="a node id, or a unique suffix of one (e.g. routing.get_request_handler)")
    e.add_argument("--direction", choices=("in", "out", "both"), default="both")
    e.set_defaults(handler=cmd_edges)
    c = sub.add_parser("compile-labels", help="fold the shard's label-only edges into the sidecar (rebuild does this)")
    c.set_defaults(handler=cmd_compile_labels)
    args = ap.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
