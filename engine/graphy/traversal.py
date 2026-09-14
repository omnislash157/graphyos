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
from graphy._shared import source_sha

SOURCE_SHA = source_sha(__file__)   # the door rules this process runs (graphyos #111)

__all__ = ["TraversalError", "DIRNAME", "home_for", "walk", "store_walk", "load_walk", "stored",
           "replay", "Counting", "INSTALL_HINT", "door", "load_door", "stored_doors", "recall", "vocabulary"]

DIRNAME = "traversals"
COLUMNS = {"seed": "VARCHAR", "hop": "BIGINT", "node": "VARCHAR", "via_src": "VARCHAR",
           "relation": "VARCHAR", "direction": "VARCHAR", "carrier": "VARCHAR", "generation": "VARCHAR",
           "on_path": "BOOLEAN"}
RECEIPT_FORMAT = 1
DOORS = ("descend", "blast")
DOOR_FORMAT = 1            # the receipt's shape; the rules themselves are keyed by rules_digest, never by a bump
DOOR_DIR = "doors"          # beside the walks, never in their glob: replay and `stored` read walks only
DOOR_COLUMNS = {"door": "VARCHAR", "seed": "VARCHAR", "depth": "BIGINT", "ord": "BIGINT", "hop": "BIGINT",
                "node": "VARCHAR", "via_src": "VARCHAR", "relation": "VARCHAR", "owner": "VARCHAR",
                "primitive": "BOOLEAN", "generation": "VARCHAR"}


# Every function that lands rows in the traversal store. The store is a cache: the review battery's
# `cache-write-guarded` refuses a call to one that is not inside a try catching OSError and the driver's
# Error, so a read-only or full home never costs an answer already computed (graphyos #111 review round 4).
CACHE_WRITERS = ("store_walk", "store_door")


class TraversalError(RuntimeError):
    pass


class StoredUnreadable(TraversalError):
    """A stored answer's parquet the driver cannot read — damage from outside, never a torn write."""


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

    def __getattr__(self, name: str):
        """Anything this proxy does not name itself comes from the store behind it.

        A hand-written proxy forwarding four methods silently drops the fifth thing anyone adds to a
        store. It dropped `relations` the day it existed: the doors read their relation families off
        the store (graphyos #68), the CLI wraps every door's store in this, and so every door run
        through the CLI fell back to the hardcoded defaults while the tests — which hold the store
        directly — passed. The declared vocabulary worked everywhere except the one path a user
        takes. Forwarding by default means the next field added to a store cannot repeat it."""
        return getattr(self._store, name)

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
        if isinstance(r, dict) and r.get("format") == RECEIPT_FORMAT and rp.with_suffix(".parquet").is_file():
            out[r["seed"]] = rp
    return out


def _cached_walk(home: Path, generation: str, seed: str) -> StoredWalk | None:
    """A stored walk as the walk reads its cache: a parquet damaged from outside is a miss, re-walked and
    rewritten (writes are atomic, so only outside damage lands here); a receipt that does not describe its key
    still refuses by name."""
    try:
        return load_walk(home, generation, seed)
    except StoredUnreadable:
        return None


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
            "SELECT node, via_src, relation, direction FROM read_parquet('" + pq.as_posix().replace("'", "''") + "') ORDER BY hop"
        ).fetchall()
    except duckdb.Error as exc:
        raise StoredUnreadable(f"stored walk at {pq} is unreadable ({type(exc).__name__})") from exc
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
    own = _cached_walk(home, generation, seed)
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
                other = _cached_walk(home, generation, node)
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
        duckdb = _duckdb()
        try:                   # the store is a cache: a failed write never costs the walk already answered
            store_walk(home, store, seed, target, prev, hops, exhausted, stopped, counted.reads)
        except (OSError, duckdb.Error) as exc:
            return WalkOutcome(res, f"spliced:{spliced}" if spliced else "live", counted.reads, None,
                               note=f"the traversal store could not be written ({type(exc).__name__}: {str(exc)[:160]})")
        saved = _paths(home, generation, seed)[0]
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


# ── the doors: descend and blast land rows too (graphyos #111) ─────────────────────────────────

# Where a door answer is computed, and every module its key hashes: the import closure of the roots. The
# review battery's `cache-key-closure` refuses a module the roots import that is not declared here, and a
# declared module that does not pin SOURCE_SHA at import; RULE_EXEMPT names what the roots can import that bears no rule.
RULE_ROOTS = ("graphy.doors", "graphy.traversal")
RULE_MODULES = ("graphy._shared", "graphy.cartograph", "graphy.container", "graphy.cross_substrate", "graphy.doors",
                "graphy.federated_store", "graphy.ir", "graphy.native_json_graph_ir", "graphy.query", "graphy.tenant",
                "graphy.traversal")
# importable from the roots and bearing no door rule — the check follows none of their imports
RULE_EXEMPT = {
    "graphy": "the package __init__ re-exports the IR, parity and tenant; it defines no door rule",
    "graphy.journal": "explain's HISTORY line reads it, and explain is never stored",
    "graphy.smash": "derive_doc_declaration reads shard schemes at compile; the result is the store's doc declaration, hashed into the generation",
}


def rules_digest() -> str | None:
    """The door rules as the engine that answers runs them: the source digests each module a door's answer
    is computed in pinned when it was imported (the walk, what it admits and declines, what a primitive is,
    how a neighbour is oriented). An upgraded engine over an unchanged store keeps the generation; it never
    keeps the old engine's answers — and a process whose files moved under it after import keys its answers
    by the code it executes, never by the bytes on disk. Combined from the pins on every call, so a reload
    moves it too. None when any source was unreadable."""
    import importlib
    pinned = [importlib.import_module(m).SOURCE_SHA for m in RULE_MODULES]
    if any(p is None for p in pinned):
        return None
    return hashlib.sha256("\x00".join(pinned).encode()).hexdigest()[:16]


def vocabulary(store) -> str | None:
    """What a door answer depends on beyond the nodes and edges the generation hashes: the folded relation
    vocabulary, the families each door admits, the receipt format and the engine's door rules. A lane that re-declares a
    relation over the same shards keeps its generation; it never keeps its stored door answers."""
    from graphy import doors
    rules = rules_digest()
    if rules is None:
        return None
    folded = {k: sorted(v) for k, v in (getattr(store, "relations", None) or {}).items()}
    basis = {"format": DOOR_FORMAT, "relations": folded, "descend": sorted(doors.descend_relations(store)),
             "blast": sorted(doors.blast_relations(store)), "seed": sorted(doors.SEED_RELATIONS), "rules": rules}
    return hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()[:16]


def _door_paths(home: Path, generation: str, which: str, seed: str, depth: int, vocab: str) -> tuple[Path, Path]:
    stem = f"{which}-{_key(seed)}-d{int(depth)}-v{vocab}"
    d = home / generation / DOOR_DIR
    return d / f"{stem}.parquet", d / f"{stem}.json"


@dataclass
class DoorOutcome:
    result: object         # doors.Descent | doors.Blast
    source: str            # "store" | "live"
    reads: int
    stored: Path | None
    note: str | None = None


def store_door(home: Path, generation: str, which: str, result, reads: int, vocab: str) -> dict:
    """One door answer's rows — every reached node in BFS order, its hop, the edge it came by, its
    owner — and a receipt carrying what the rows cannot: the declined counts and their classes."""
    duckdb = _duckdb()
    pq, rp = _door_paths(home, generation, which, result.seed, result.depth, vocab)
    pq.parent.mkdir(parents=True, exist_ok=True)
    prims = {r.node for r in getattr(result, "primitives", ())}
    rows = [(which, result.seed, result.depth, i, r.hop, r.node, r.via, r.relation, r.owner, r.node in prims, generation)
            for i, r in enumerate(result.reached.values())]
    started = time.perf_counter()
    con = duckdb.connect()
    try:
        _write_parquet(con, "door", DOOR_COLUMNS, rows, pq)
    finally:
        con.close()
    receipt = {
        "format": RECEIPT_FORMAT, "door": which, "seed": result.seed, "depth": result.depth, "generation": generation,
        "vocabulary": vocab, "rows": len(rows), "reads": reads, "declined": result.declined, "declined_classes": result.declined_classes,
        "duckdb": duckdb.__version__, "stored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seconds": round(time.perf_counter() - started, 3), "bytes": pq.stat().st_size,
    }
    tmp = rp.with_name(f".{rp.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, rp)
    return receipt


def load_door(home: Path, generation: str, which: str, seed: str, depth: int, vocab: str):
    """The stored answer of one door for (seed, depth) under this generation, rebuilt from its rows
    with zero store reads — or None when it was never stored under this vocabulary."""
    from graphy import doors
    pq, rp = _door_paths(home, generation, which, seed, depth, vocab)
    if not pq.is_file() or not rp.is_file():
        return None
    try:
        r = json.loads(rp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TraversalError(f"receipt unreadable at {rp} ({type(exc).__name__}) — delete it and re-ask") from exc
    if (r.get("format") != RECEIPT_FORMAT or r.get("door") != which or r.get("seed") != seed
            or r.get("generation") != generation or r.get("depth") != depth or r.get("vocabulary") != vocab):
        raise TraversalError(f"receipt at {rp} does not describe {which} {seed!r} depth {depth} under generation "
                             f"{generation} and vocabulary {vocab} — refusing to reinterpret it")
    duckdb = _duckdb()
    con = duckdb.connect()
    try:
        rows = con.execute("SELECT hop, node, via_src, relation, owner, primitive FROM read_parquet('"
                           + pq.as_posix().replace("'", "''") + "') ORDER BY ord").fetchall()
    except duckdb.Error as exc:
        raise StoredUnreadable(f"stored {which} at {pq} is unreadable ({type(exc).__name__})") from exc
    finally:
        con.close()
    if len(rows) != r.get("rows") or not rows or rows[0][1] != seed:
        raise TraversalError(f"stored {which} at {pq} holds {len(rows)} row(s) where its receipt says {r.get('rows')} "
                             f"and its first row must be the seed — refusing it")
    reached = {node: doors.Reach(node, hop, via, rel, owner) for hop, node, via, rel, owner, _p in rows}
    declined = {k: int(v) for k, v in (r.get("declined") or {}).items()}
    classes = {k: list(v) for k, v in (r.get("declined_classes") or {}).items()}
    if which == "descend":
        return doors.descent_of(seed, depth, reached, {row[1] for row in rows if row[5]}, declined, classes)
    return doors.blast_of(seed, depth, reached, declined, classes)


def door(store, home: Path, which: str, seed: str, depth: int, save: bool = True) -> DoorOutcome:
    """``descend`` or ``blast`` through the traversal store: the same (seed, depth) under the live
    generation answers from its rows with zero reads; otherwise the door runs live and lands its rows.
    With no duckdb it is exactly the live door, and says why nothing was stored."""
    from graphy import doors
    if which not in DOORS:
        raise TraversalError(f"{which!r} is not a recorded door — one of {', '.join(DOORS)}")
    fn = doors.descend if which == "descend" else doors.blast
    if not have_duckdb():
        counted = Counting(store)
        return DoorOutcome(fn(counted, seed, depth), "live", counted.reads, None, note=INSTALL_HINT)
    generation, vocab = store.generation(), vocabulary(store)
    if vocab is None:
        counted = Counting(store)
        return DoorOutcome(fn(counted, seed, depth), "live", counted.reads, None,
                           note="the door rules' source is unreadable, so no answer can be keyed by the code that computed it")
    try:
        hit = load_door(home, generation, which, seed, depth, vocab)
    except StoredUnreadable:   # damaged from outside (writes are atomic): a cache miss, re-asked live and rewritten
        hit = None
    if hit is not None:
        return DoorOutcome(hit, "store", 0, _door_paths(home, generation, which, seed, depth, vocab)[0])
    counted = Counting(store)
    result = fn(counted, seed, depth)
    saved = None
    if save:
        duckdb = _duckdb()
        try:               # the store is a cache: a failed write never costs the answer already computed
            store_door(home, generation, which, result, counted.reads, vocab)
        except (OSError, duckdb.Error) as exc:
            return DoorOutcome(result, "live", counted.reads, None,
                               note=f"the traversal store could not be written ({type(exc).__name__}: {str(exc)[:160]})")
        saved = _door_paths(home, generation, which, seed, depth, vocab)[0]
    return DoorOutcome(result, "live", counted.reads, saved)


def stored_doors(home: Path, generation: str) -> list[dict]:
    """Every door answer stored under this generation, as its receipt."""
    d = home / generation / DOOR_DIR
    out = []
    for rp in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            r = json.loads(rp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(r, dict) and r.get("format") == RECEIPT_FORMAT and r.get("door") in DOORS and rp.with_suffix(".parquet").is_file():
            out.append(r)
    return out


def recall(home: Path, generation: str, seed: str | None = None, target: str | None = None,
           vocab: str | None = None) -> list[dict]:
    """Every stored row under this generation — walks and doors alike — whose seed is ``seed`` or
    whose node is ``target``, in one parquet scan and zero store reads. A row names the traversal
    it belongs to (walk · descend · blast, and the door's depth), its hop and the edge it came by.
    ``vocab`` (the live store's ``vocabulary``) admits only the door answers stored under it; a walk
    row records edges, never an admission rule, so walks are read whatever it says."""
    if (seed is None) == (target is None):
        raise TraversalError("recall takes exactly one of seed or target")
    d = home / generation
    walks = sorted(d.glob("*.parquet")) if d.is_dir() else []
    doors_ = sorted((d / DOOR_DIR).glob("*.parquet" if vocab is None else f"*-v{vocab}.parquet")) \
        if (d / DOOR_DIR).is_dir() else []
    col, val = ("seed", seed) if seed is not None else ("node", target)

    def scan(files, kind_sql, depth_sql):
        listing = ", ".join("'" + p.as_posix().replace("'", "''") + "'" for p in files)
        return (f"SELECT {kind_sql} AS kind, seed, {depth_sql} AS depth, hop, node, via_src, relation "
                f"FROM read_parquet([{listing}]) WHERE {col} = ?")
    parts, params = [], []
    if walks:
        parts.append(scan(walks, "'walk'", "CAST(NULL AS BIGINT)")); params.append(val)
    if doors_:
        parts.append(scan(doors_, "door", "depth")); params.append(val)
    if not parts:
        return []
    con = _duckdb().connect()
    try:
        rows = con.execute(" UNION ALL ".join(parts) + " ORDER BY kind, seed, depth, hop, node", params).fetchall()
    finally:
        con.close()
    return [dict(zip(("kind", "seed", "depth", "hop", "node", "via_src", "relation"), row)) for row in rows]
