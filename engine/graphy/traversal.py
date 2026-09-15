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
           "replay", "Counting", "INSTALL_HINT", "door", "load_door", "load_facts", "stored_doors", "recall"]

DIRNAME = "traversals"
COLUMNS = {"seed": "VARCHAR", "hop": "BIGINT", "node": "VARCHAR", "via_src": "VARCHAR",
           "relation": "VARCHAR", "direction": "VARCHAR", "carrier": "VARCHAR", "generation": "VARCHAR",
           "on_path": "BOOLEAN"}
RECEIPT_FORMAT = 1
DOORS = ("descend", "blast")
DOOR_DIR = "doors"          # beside the walks, never in their glob: replay and `stored` read walks only


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


def _make_under(home: Path, d: Path) -> None:
    """Create ``d`` under the traversal home, never the data home above it: a door still holding a
    generation a rebuild has since discarded must not recreate it to cache an answer (graphyos #98) —
    the OSError reaches the cache-write guard, which answers live and names TRAVERSAL SKIPPED."""
    if not Path(home).parent.is_dir():
        raise FileNotFoundError(f"the data home {Path(home).parent} is gone — a newer generation replaced it")
    d.mkdir(parents=True, exist_ok=True)


def store_walk(home: Path, store, seed: str, target: str, prev: dict, hops: int,
               exhausted: bool, stopped_by: str | None, reads: int) -> dict:
    """Write one walk's rows and its receipt. Hop per node is the depth of its chain — ``prev``
    is in BFS insertion order, so a parent is always numbered before its children."""
    duckdb = _duckdb()
    generation = store.generation()
    pq, rp = _paths(home, generation, seed)
    _make_under(home, pq.parent)
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


# ── the doors: descend and blast land the facts they read (graphyos #111, #117) ─────────────────────────────

# A stored door answer was the OUTPUT of the door rules, so its key had to hash every rule — four review rounds of
# #111 grew it from the relations to an import closure of source pins. A door now lands what it READ: every
# neighbour row of each node it expanded and each owner it looked up, which are facts of the generation. A repeat
# re-runs the live rules over those facts with zero store reads, so a changed rule or a re-declared relation needs no
# key at all; a node the new rules ask for and the facts never read runs the door live and records it again.


class FactsMissing(TraversalError):
    """The rules asked the recorded facts for something the recording door never read."""


class _Recording(Counting):
    """A counted store that keeps every answer it gave a door: the neighbour rows per node, the owner per node."""

    def __init__(self, store):
        super().__init__(store)
        self.nbs: dict[str, list] = {}
        self.owners: dict[str, str | None] = {}

    def neighbours(self, node: str):
        rows = self.nbs.get(node)
        if rows is None:
            rows = self.nbs[node] = list(super().neighbours(node))
        return rows

    def membership(self, node: str):
        if node not in self.owners:
            self.owners[node] = self._store.membership(node)
        return self.owners[node]


class _Facts:
    """The recorded facts as a store the door rules can run over: neighbours and owners from the rows, the relation
    fold from the live store (an attribute of the store, never a read), anything else the facts never saw."""

    def __init__(self, nbs: dict, owners: dict, live):
        self._nbs, self._owners, self._live = nbs, owners, live
        self.reads = 0

    @property
    def relations(self):
        return getattr(self._live, "relations", None) or {}

    def neighbours(self, node: str):
        if node not in self._nbs:
            raise FactsMissing(node)
        return self._nbs[node]

    def membership(self, node: str):
        if node not in self._owners:
            raise FactsMissing(node)
        return self._owners[node]

    def generation(self) -> str:
        return self._live.generation()

    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        raise FactsMissing(f"the door rules read store.{name}, which no door recorded")


FACT_FORMAT = "facts-1"
FACT_COLUMNS = {"door": "VARCHAR", "seed": "VARCHAR", "depth": "BIGINT", "ord": "BIGINT", "fact": "VARCHAR",
                "node": "VARCHAR", "other": "VARCHAR", "relation": "VARCHAR", "direction": "VARCHAR",
                "generation": "VARCHAR"}


def _door_paths(home: Path, generation: str, which: str, seed: str, depth: int) -> tuple[Path, Path]:
    """One stem per (door, seed, depth) under the generation; ``.facts`` keeps the 0.2.6 answer rows
    (``-v<vocabulary>`` stems) out of every glob here, so a released layout is never read as facts."""
    stem = f"{which}-{_key(seed)}-d{int(depth)}.facts"
    d = home / generation / DOOR_DIR
    return d / f"{stem}.parquet", d / f"{stem}.json"


@dataclass
class DoorOutcome:
    result: object         # doors.Descent | doors.Blast
    source: str            # "store" | "live"
    reads: int
    stored: Path | None
    note: str | None = None


def store_door(home: Path, generation: str, which: str, result, recording: _Recording) -> dict:
    """The facts one door read — a ``nb`` row per neighbour of each expanded node, a ``none`` row for a node that
    had none, an ``own`` row per owner looked up — and a receipt naming the question and how much was read."""
    duckdb = _duckdb()
    pq, rp = _door_paths(home, generation, which, result.seed, result.depth)
    _make_under(home, pq.parent)
    rows, head = [], (which, result.seed, result.depth)
    for node, nbs in recording.nbs.items():
        if not nbs:
            rows.append((*head, len(rows), "none", node, None, None, None, generation))
        for nb in nbs:
            rows.append((*head, len(rows), "nb", node, nb.node, nb.relation, nb.direction, generation))
    for node, owner in recording.owners.items():
        rows.append((*head, len(rows), "own", node, owner, None, None, generation))
    started = time.perf_counter()
    con = duckdb.connect()
    try:
        _write_parquet(con, "facts", FACT_COLUMNS, rows, pq)
    finally:
        con.close()
    receipt = {
        "format": FACT_FORMAT, "door": which, "seed": result.seed, "depth": result.depth, "generation": generation,
        "rows": len(rows), "expanded": len(recording.nbs), "owners": len(recording.owners), "reads": recording.reads,
        "reached": len(result.reached), "duckdb": duckdb.__version__,
        "stored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seconds": round(time.perf_counter() - started, 3), "bytes": pq.stat().st_size,
    }
    tmp = rp.with_name(f".{rp.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, rp)
    return receipt


def load_facts(home: Path, generation: str, which: str, seed: str, depth: int) -> tuple[dict, dict] | None:
    """The facts one door read for (seed, depth) under this generation, or None when none were stored."""
    from graphy.federated_store import Neighbour
    pq, rp = _door_paths(home, generation, which, seed, depth)
    if not pq.is_file() or not rp.is_file():
        return None
    try:
        r = json.loads(rp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TraversalError(f"receipt unreadable at {rp} ({type(exc).__name__}) — delete it and re-ask") from exc
    if (r.get("format") != FACT_FORMAT or r.get("door") != which or r.get("seed") != seed
            or r.get("generation") != generation or r.get("depth") != depth):
        raise TraversalError(f"receipt at {rp} does not describe {which} {seed!r} depth {depth} under generation "
                             f"{generation} — refusing to reinterpret it")
    duckdb = _duckdb()
    con = duckdb.connect()
    try:
        rows = con.execute("SELECT fact, node, other, relation, direction FROM read_parquet('"
                           + pq.as_posix().replace("'", "''") + "') ORDER BY ord").fetchall()
    except duckdb.Error as exc:
        raise StoredUnreadable(f"stored {which} at {pq} is unreadable ({type(exc).__name__})") from exc
    finally:
        con.close()
    if len(rows) != r.get("rows"):
        raise TraversalError(f"stored {which} at {pq} holds {len(rows)} row(s) where its receipt says {r.get('rows')} "
                             f"— refusing it")
    nbs: dict[str, list] = {}
    owners: dict[str, str | None] = {}
    for fact, node, other, relation, direction in rows:
        if fact == "nb":
            nbs.setdefault(node, []).append(Neighbour(other, relation, direction))
        elif fact == "none":
            nbs.setdefault(node, [])
        elif fact == "own":
            owners[node] = other
    return nbs, owners


def load_door(home: Path, generation: str, which: str, seed: str, depth: int, store):
    """The door's answer for (seed, depth), re-derived by the live rules over the stored facts with zero store
    reads — or None when no facts were stored, or the live rules ask for a fact the recording never read."""
    from graphy import doors
    facts = load_facts(home, generation, which, seed, depth)
    if facts is None:
        return None
    fn = doors.descend if which == "descend" else doors.blast
    try:
        return fn(_Facts(*facts, store), seed, depth)
    except FactsMissing:
        return None


def door(store, home: Path, which: str, seed: str, depth: int, save: bool = True) -> DoorOutcome:
    """``descend`` or ``blast`` through the traversal store: the same (seed, depth) under the live generation
    answers from the facts it read with zero reads; otherwise the door runs live and lands what it read.
    With no duckdb it is exactly the live door, and says why nothing was stored."""
    from graphy import doors
    if which not in DOORS:
        raise TraversalError(f"{which!r} is not a recorded door — one of {', '.join(DOORS)}")
    fn = doors.descend if which == "descend" else doors.blast
    if not have_duckdb():
        counted = Counting(store)
        return DoorOutcome(fn(counted, seed, depth), "live", counted.reads, None, note=INSTALL_HINT)
    generation = store.generation()
    try:
        hit = load_door(home, generation, which, seed, depth, store)
    except StoredUnreadable:   # damaged from outside (writes are atomic): a cache miss, re-asked live and rewritten
        hit = None
    if hit is not None:
        return DoorOutcome(hit, "store", 0, _door_paths(home, generation, which, seed, depth)[0])
    recording = _Recording(store)
    result = fn(recording, seed, depth)
    saved = None
    if save:
        duckdb = _duckdb()
        try:               # the store is a cache: a failed write never costs the answer already computed
            store_door(home, generation, which, result, recording)
        except (OSError, duckdb.Error) as exc:
            return DoorOutcome(result, "live", recording.reads, None,
                               note=f"the traversal store could not be written ({type(exc).__name__}: {str(exc)[:160]})")
        saved = _door_paths(home, generation, which, seed, depth)[0]
    return DoorOutcome(result, "live", recording.reads, saved)


def stored_doors(home: Path, generation: str) -> list[dict]:
    """Every door answer stored under this generation, as its receipt."""
    d = home / generation / DOOR_DIR
    out = []
    for rp in sorted(d.glob("*.facts.json")) if d.is_dir() else []:
        try:
            r = json.loads(rp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(r, dict) and r.get("format") == FACT_FORMAT and r.get("door") in DOORS and rp.with_suffix(".parquet").is_file():
            out.append(r)
    return out


def recall(home: Path, generation: str, seed: str | None = None, target: str | None = None,
           store=None) -> list[dict]:
    """Every stored row under this generation — walks and doors alike — whose seed is ``seed`` or whose node is
    ``target``, with zero store reads. A walk row records edges and is read from its parquet; a door's rows are its
    answer re-derived by the live rules over the facts it read, so ``store`` (the live store, whose relation fold the
    rules read) is required to recall doors, and a stored door whose facts the live rules outgrew is left out."""
    if (seed is None) == (target is None):
        raise TraversalError("recall takes exactly one of seed or target")
    d = home / generation
    walks = sorted(d.glob("*.parquet")) if d.is_dir() else []
    col, val = ("seed", seed) if seed is not None else ("node", target)
    out: list[dict] = []
    if walks:
        listing = ", ".join("'" + p.as_posix().replace("'", "''") + "'" for p in walks)
        con = _duckdb().connect()
        try:
            rows = con.execute(f"SELECT seed, hop, node, via_src, relation FROM read_parquet([{listing}]) "
                               f"WHERE {col} = ?", [val]).fetchall()
        finally:
            con.close()
        out += [{"kind": "walk", "seed": s_, "depth": None, "hop": h, "node": n, "via_src": v, "relation": r}
                for s_, h, n, v, r in rows]
    if store is not None:
        for r in stored_doors(home, generation):
            if seed is not None and r["seed"] != seed:
                continue
            try:
                answer = load_door(home, generation, r["door"], r["seed"], r["depth"], store)
            except StoredUnreadable:
                continue
            if answer is None:
                continue
            rows = [{"kind": r["door"], "seed": r["seed"], "depth": r["depth"], "hop": x.hop, "node": x.node,
                     "via_src": x.via, "relation": x.relation} for x in answer.reached.values()]
            out += [row for row in rows if seed is not None or row["node"] == target]
    return sorted(out, key=lambda row: (row["kind"], row["seed"], -1 if row["depth"] is None else row["depth"],
                                        row["hop"], row["node"]))
