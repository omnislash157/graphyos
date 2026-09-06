"""The traversal store. Every walk lands as rows — seed · hop · node · via edge · carrier ·
generation — in one parquet per (generation, seed) under ``<data_home>/traversals/``, with a
receipt beside it. Two properties make the rows an artifact and not a cache:

* walks **compose** — a repeat walk answers from its rows without one store read; a walk from a
  new seed that crosses a stored seed splices through that seed's rows instead of expanding it;
* walks **diff** — rows stored under generation N, replayed against the live store at N+1, name
  the hops that no longer hold (the src died, the node died, or the edge between them did).

DuckDB is the only dependency and it is optional: without it the walk runs live and nothing is
stored, and the CLI says so in one line. The store is never written by a query on the shard —
these rows are the walk's own output, beside the container, never inside the shard."""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from graphy.container import INSTALL_HINT, _duckdb, _write_parquet, have_duckdb
from graphy.cross_substrate import UNKNOWN, PathResult, Step

__all__ = ["TraversalError", "DIRNAME", "home_for", "walk", "store_walk", "load_walk", "stored",
           "replay", "Counting", "INSTALL_HINT"]

DIRNAME = "traversals"
COLUMNS = {"seed": "VARCHAR", "hop": "BIGINT", "node": "VARCHAR", "via_src": "VARCHAR",
           "relation": "VARCHAR", "direction": "VARCHAR", "carrier": "VARCHAR", "generation": "VARCHAR",
           "on_path": "BOOLEAN"}
RECEIPT_FORMAT = 1


class TraversalError(RuntimeError):
    pass


def home_for(tenant) -> Path:
    """The traversal home is a declared location under the tenant's data home, never ambient."""
    return Path(tenant.data_home) / DIRNAME


def _key(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


def _paths(home: Path, generation: str, seed: str) -> tuple[Path, Path]:
    d = home / generation
    return d / f"{_key(seed)}.parquet", d / f"{_key(seed)}.json"


class Counting:
    """A store whose reads are counted. ``reads`` is the number of frontier expansions the
    walk asked the compiled store for — the one number the done checks measure."""

    def __init__(self, store):
        self._store = store
        self.reads = 0

    def neighbours(self, node: str):
        self.reads += 1
        return self._store.neighbours(node)

    def membership(self, node: str):
        return self._store.membership(node)

    def record(self, node: str):
        return self._store.record(node)

    def generation(self) -> str:
        return self._store.generation()


@dataclass
class StoredWalk:
    seed: str
    target: str
    generation: str
    hops: int
    exhausted: bool          # the frontier ran dry — every reachable node is in ``prev``
    stopped_by: str | None
    prev: dict = field(default_factory=dict)   # node -> (via_src, relation, direction)
    path: Path | None = None

    def chain(self, node: str) -> list[str]:
        out, at = [], node
        while at is not None:
            out.append(at)
            at = self.prev[at][0]
        out.reverse()
        return out


def stored(home: Path, generation: str) -> dict[str, Path]:
    """seed -> receipt path, for every walk stored under this generation."""
    d = home / generation
    out: dict[str, Path] = {}
    if not d.is_dir():
        return out
    for rp in sorted(d.glob("*.json")):
        try:
            r = json.loads(rp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if r.get("format") == RECEIPT_FORMAT and rp.with_suffix(".parquet").is_file():
            out[r["seed"]] = rp
    return out


def load_walk(home: Path, generation: str, seed: str) -> StoredWalk | None:
    pq, rp = _paths(home, generation, seed)
    if not pq.is_file() or not rp.is_file():
        return None
    try:
        r = json.loads(rp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TraversalError(f"receipt unreadable at {rp} ({type(exc).__name__}) — delete it and re-walk") from exc
    if r.get("format") != RECEIPT_FORMAT or r.get("seed") != seed or r.get("generation") != generation:
        raise TraversalError(f"receipt at {rp} does not describe seed {seed!r} under generation {generation} "
                             f"— refusing to reinterpret it")
    duckdb = _duckdb()
    con = duckdb.connect()
    try:
        rows = con.execute(
            f"SELECT node, via_src, relation, direction FROM read_parquet('{pq.as_posix()}') ORDER BY hop"
        ).fetchall()
    finally:
        con.close()
    prev = {node: (via, rel, direction) for node, via, rel, direction in rows}
    if seed not in prev:
        raise TraversalError(f"stored walk at {pq} does not carry its own seed — refusing it")
    return StoredWalk(seed=seed, target=r["target"], generation=generation, hops=r["hops"],
                      exhausted=bool(r["exhausted"]), stopped_by=r.get("stopped_by"), prev=prev, path=pq)


def _steps(store, prev: dict, chain: list[str]) -> list[Step]:
    steps = []
    for a, b in zip(chain, chain[1:]):
        _via, rel, direction = prev[b]
        steps.append(Step(src=a, dst=b, relation=rel, direction=direction or UNKNOWN,
                          owner_src=store.membership(a) or "", owner_dst=store.membership(b) or ""))
    return steps


def _chain(prev: dict, node: str) -> list[str]:
    out, at = [], node
    while at is not None:
        out.append(at)
        at = prev[at][0]
    out.reverse()
    return out


def store_walk(home: Path, store, seed: str, target: str, prev: dict, hops: int,
               exhausted: bool, stopped_by: str | None, reads: int) -> dict:
    """Write one walk's rows and its receipt. Hop per node is the depth of its chain — ``prev``
    is in BFS insertion order, so a parent is always numbered before its children."""
    duckdb = _duckdb()
    generation = store.generation()
    pq, rp = _paths(home, generation, seed)
    pq.parent.mkdir(parents=True, exist_ok=True)
    hop: dict[str, int] = {}
    on_path = set(_chain(prev, target)) if target in prev else {seed}
    rows = []
    for node, (via, rel, direction) in prev.items():
        hop[node] = 0 if via is None else hop[via] + 1
        rows.append((seed, hop[node], node, via, rel, direction, store.membership(node), generation,
                     node in on_path))
    started = time.perf_counter()
    con = duckdb.connect()
    try:
        _write_parquet(con, "walk", COLUMNS, rows, pq)
    finally:
        con.close()
    receipt = {
        "format": RECEIPT_FORMAT, "seed": seed, "target": target, "generation": generation,
        "hops": hops, "rows": len(rows), "exhausted": exhausted, "stopped_by": stopped_by,
        "reads": reads, "duckdb": duckdb.__version__,
        "stored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seconds": round(time.perf_counter() - started, 3),
        "bytes": pq.stat().st_size,
    }
    tmp = rp.with_name(f".{rp.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, rp)
    return receipt


@dataclass
class WalkOutcome:
    result: PathResult
    source: str            # "store" | "live" | "spliced:<seed>"
    reads: int
    stored: Path | None
    note: str | None = None


def walk(store, home: Path, seed: str, target: str, max_depth: int = 6,
         max_nodes: int = 250_000, save: bool = True) -> WalkOutcome:
    """A walk that reads the traversal store first, splices through stored seeds it crosses, and
    lands its own rows when it is done. With no duckdb it is exactly ``federated_store.path_to``."""
    if not have_duckdb():
        from graphy.federated_store import path_to
        counted = Counting(store)
        return WalkOutcome(path_to(counted, seed, target, max_depth, max_nodes), "live", counted.reads,
                           None, note=INSTALL_HINT)
    if store.membership(seed) is None:
        return WalkOutcome(PathResult(seed=seed, target=target, found=False, stopped_by="seed-absent"),
                           "live", 0, None)
    if store.membership(target) is None:
        return WalkOutcome(PathResult(seed=seed, target=target, found=False, stopped_by="target-absent"),
                           "live", 0, None)
    generation = store.generation()
    counted = Counting(store)

    # 1. the same seed, stored under this generation: answer from the rows, zero reads
    own = load_walk(home, generation, seed)
    if own is not None:
        if target in own.prev:
            chain = own.chain(target)
            res = PathResult(seed=seed, target=target, found=True, steps=_steps(store, own.prev, chain),
                             visited=len(own.prev), stopped_by=None)
            return WalkOutcome(res, "store", 0, own.path)
        if own.exhausted:
            res = PathResult(seed=seed, target=target, found=False, visited=len(own.prev), stopped_by=None)
            return WalkOutcome(res, "store", 0, own.path)

    # 2. live BFS, splicing through any stored seed the frontier crosses
    index = stored(home, generation)
    index.pop(seed, None)
    prev: dict = {seed: (None, None, None)}
    frontier, hops, reached, stopped, spliced = [seed], 0, target == seed, None, None
    while not reached and stopped is None and frontier and hops < max_depth:
        hops += 1
        nxt: list[str] = []
        for node in frontier:
            if node in index:
                other = load_walk(home, generation, node)
                if other is not None and target in other.prev:
                    for b in other.chain(target)[1:]:
                        if b not in prev:
                            prev[b] = other.prev[b]
                    reached, spliced = True, node
                    hops += len(other.chain(target)) - 2
                    break
            for nb in counted.neighbours(node):
                if nb.node in prev:
                    continue
                prev[nb.node] = (node, nb.relation, nb.direction)
                if nb.node == target:
                    reached = True
                    break
                if len(prev) > max_nodes:
                    stopped = "max_nodes"
                    break
                nxt.append(nb.node)
            if reached or stopped:
                break
        frontier = nxt
    if not reached and stopped is None and hops >= max_depth and frontier:
        stopped = "max_depth"
    exhausted = not reached and stopped is None and not frontier
    if reached:
        chain = _chain(prev, target)
        res = PathResult(seed=seed, target=target, found=True, steps=_steps(store, prev, chain),
                         visited=len(prev), stopped_by=None)
    else:
        res = PathResult(seed=seed, target=target, found=False, visited=len(prev), stopped_by=stopped)
    saved = None
    if save:   # a spliced walk lands too: partial past the splice, never marked exhausted, every row a true path
        saved = _paths(home, generation, seed)[0]
        store_walk(home, store, seed, target, prev, hops, exhausted, stopped, counted.reads)
    return WalkOutcome(res, f"spliced:{spliced}" if spliced else "live", counted.reads, saved)


def replay(store, home: Path) -> list[dict]:
    """Every walk stored under a generation other than the live one, re-checked hop by hop
    against the live store. A hop holds when its src and node are both members and the store
    still carries that edge between them; otherwise it is named with why."""
    live = store.generation()
    out: list[dict] = []
    if not home.is_dir():
        return out
    nbr_cache: dict[str, set] = {}

    def edge_alive(src: str, node: str, rel: str) -> bool:
        s = nbr_cache.get(src)
        if s is None:
            s = {(n.node, n.relation) for n in store.neighbours(src)}
            nbr_cache[src] = s
        return (node, rel) in s

    for gen_dir in sorted(p for p in home.iterdir() if p.is_dir()):
        gen = gen_dir.name
        if gen == live:
            continue
        for seed in stored(home, gen):
            w = load_walk(home, gen, seed)
            if w is None:
                continue
            broken = []
            for node, (via, rel, direction) in w.prev.items():
                if via is None:
                    if store.membership(node) is None:
                        broken.append({"hop": 0, "via_src": None, "relation": None, "node": node,
                                       "why": "seed died"})
                    continue
                if store.membership(via) is None:
                    why = "src died"
                elif store.membership(node) is None:
                    why = "node died"
                elif not edge_alive(via, node, rel):
                    why = "edge died"
                else:
                    continue
                broken.append({"hop": len(_chain(w.prev, node)) - 1, "via_src": via, "relation": rel,
                               "node": node, "why": why})
            # the path to the stored target, if it was found, is the hop set that matters most
            path_broken = []
            if w.target in w.prev:
                on_path = set(w.chain(w.target))
                path_broken = [b for b in broken if b["node"] in on_path]
            out.append({"seed": seed, "target": w.target, "generation": gen, "live": live,
                        "hops_checked": len(w.prev) - 1, "broken": broken, "path_broken": path_broken})
    return out
