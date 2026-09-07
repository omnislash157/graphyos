from __future__ import annotations

import base64
import hashlib
import json
import os
import shlex
import sqlite3
import sys
import zlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from graphy import cross_substrate as _cross_substrate
from graphy.cross_substrate import (
    AGAINST,
    BOTH,
    UNKNOWN,
    WIRE_BUCKET,
    WITH,
    PathResult,
    Step,
    load_set,
)
from graphy.query import activate, rank
from graphy._shared import _ast_edge_salience
from graphy.native_json_graph_ir import _detect_duplicate_json_keys, shard_input_digest
from graphy.tenant import Tenant

SCHEMA = """
CREATE TABLE nodes (
    id        TEXT PRIMARY KEY,
    owner     TEXT NOT NULL,
    node_type TEXT,
    dotted    TEXT,
    module    TEXT,
    role      TEXT,
    file      TEXT,
    line      INTEGER,
    record    TEXT
);
CREATE TABLE edges (
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    rel TEXT NOT NULL
);
CREATE INDEX idx_edges_src ON edges(src);
CREATE INDEX idx_edges_dst ON edges(dst);
CREATE INDEX idx_nodes_owner ON nodes(owner);
CREATE INDEX idx_nodes_owner_module ON nodes(owner, module);
CREATE INDEX idx_nodes_owner_type ON nodes(owner, node_type);
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
"""


class StoreError(RuntimeError):
    pass


class StaleCursorError(StoreError):

    def __init__(self, minted: str, live: str, seed: str):
        self.minted, self.live, self.seed = minted, live, seed
        super().__init__(
            f"cursor was minted on generation {minted} but this store serves {live} — "
            f"refusing to continue one walk across two graphs. Re-run from {seed!r}.")


@dataclass(frozen=True)
class Neighbour:
    node: str
    relation: str
    direction: str


GENERATION_FORMAT = 4

# The fields every aggregate reads (pillars · arms · draw): columns of the nodes table, so a
# whole-corpus read never decodes a record. The full record is decoded only by record().
COLUMNS = ("node_type", "dotted", "module", "role", "file", "line")


def _columns(record: dict | None) -> dict | None:
    """The aggregate view of a record: its COLUMNS and nothing else; None for an absent record."""
    if record is None:
        return None
    return {k: record.get(k) for k in COLUMNS}


def _generation_digest(mesh, substrates: list[str]) -> str:
    h = hashlib.sha256()
    h.update(b"gf\x00" + str(GENERATION_FORMAT).encode() + b"\x00")
    for s in sorted(substrates):
        h.update(b"s\x00" + s.encode() + b"\x00")
    for nid in sorted(mesh.node_owner):
        rec = mesh.node_records.get(nid)
        h.update(b"n\x00" + nid.encode() + b"\x00"
                 + (mesh.node_owner.get(nid) or "").encode() + b"\x00"
                 + (b"r\x00" + json.dumps(rec, sort_keys=True, default=str).encode()
                    if rec is not None else b"-")
                 + b"\x00")
    for (src, dst, rel) in sorted(mesh.directed):
        h.update(b"e\x00" + src.encode() + b"\x00" + dst.encode() + b"\x00"
                 + rel.encode() + b"\x00")
    return h.hexdigest()[:16]



_INDEX_INPUT_KEY = ".federation_scheme_index.json"
_REGISTRY_INPUT_KEY = "substrate_override_registry.json"
_ABSENT_SENTINEL = "<ABSENT>"


def _sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


INPUT_DIGEST_FORMAT = 2
_INPUT_DIGEST_FORMAT_KEY = ".input_digest_format"


def _shard_input_digest(graph_dir: Path) -> str:
    """The bytes of nodes.json, edges.json and the sidecar hashed — never parsed (a walk is a
    query, never a load). Format 1 parsed and re-serialized every shard per query."""
    return shard_input_digest(graph_dir)


def _scheme_index_input_digest(index_path: Path, loaded: list[str]) -> str:
    if not os.path.exists(index_path):
        return _ABSENT_SENTINEL
    try:
        with open(index_path, encoding="utf-8") as fh:
            index = json.load(fh)
    except (OSError, ValueError) as exc:
        raise StoreError(
            f"federation scheme index at {index_path} is present but unreadable "
            f"({type(exc).__name__}: {exc}) — refusing to call the store fresh; recompile "
            f"the store or repair the index") from exc
    proj: dict[str, list] = {}
    for slug in loaded:
        rec = index.get(slug)
        if isinstance(rec, dict):
            proj[slug] = sorted(str(s) for s in rec.get("own") or ())
        else:
            proj[slug] = []
    return _sha16(json.dumps(proj, sort_keys=True, separators=(",", ":")).encode())


def _registry_input_digest(registry_path: Path) -> str:
    if not os.path.exists(registry_path):
        raise StoreError(
            f"override registry at {registry_path} is MISSING — refusing to call the "
            f"store fresh. The override registry has no documented fallback (its loader "
            f"fails OPEN to an empty join-scheme set, which is the silent edge-admission "
            f"change this guard exists to expose); recompile the store or restore the "
            f"registry")
    try:
        raw = registry_path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        raise StoreError(
            f"override registry at {registry_path} is present but unreadable "
            f"({type(exc).__name__}: {exc}) — refusing to call the store fresh; recompile "
            f"the store or repair the registry") from exc
    dupes = _detect_duplicate_json_keys(raw)
    if dupes:
        raise StoreError(
            f"override registry at {registry_path} has duplicate JSON object key(s): "
            f"{', '.join(dupes)} — the consumed loader (load_override_ir) treats duplicate "
            f"keys as corruption and raises, so the digest refuses too; recompile the store "
            f"or repair the registry")
    try:
        registry = json.loads(raw)
    except ValueError as exc:
        raise StoreError(
            f"override registry at {registry_path} is present but unreadable "
            f"({type(exc).__name__}: {exc}) — refusing to call the store fresh; recompile "
            f"the store or repair the registry") from exc
    lit_schemes: set[str] = set()
    reg_joins = registry.get("registered_joins", {})
    if isinstance(reg_joins, dict):
        lj = reg_joins.get("literal_joins", {})
        if isinstance(lj, dict):
            for k in lj:
                if isinstance(k, str) and "://" in k and not k.startswith("_"):
                    lit_schemes.add(k.split("://", 1)[0])
    return _sha16(json.dumps(sorted(lit_schemes), separators=(",", ":")).encode())


def _compute_input_digest(substrates: list[str], *, tenant: Tenant | None = None) -> str:
    if tenant is None:
        raise ValueError(
            f"_compute_input_digest: tenant is required — graphy resolves identity only "
            f"through a declared Tenant; absent tenant = refuse"
        )
    data_home = Path(tenant.data_home)
    digests: dict[str, str] = {}
    for s in sorted(substrates):
        graph_dir = data_home / f"{s}_graph"
        try:
            digests[s] = _shard_input_digest(graph_dir)
        except (OSError, ValueError) as exc:
            raise StoreError(
                f"cannot measure shard input for {s!r} at {graph_dir} "
                f"({type(exc).__name__}: {exc}) — this is 'could not tell', not 'fresh'; "
                f"recompile the store or restore the graph") from exc
    digests[_INDEX_INPUT_KEY] = _scheme_index_input_digest(
        data_home / _INDEX_INPUT_KEY, sorted(substrates))
    digests[_REGISTRY_INPUT_KEY] = _registry_input_digest(Path(tenant.join_keys))
    digests[_INPUT_DIGEST_FORMAT_KEY] = INPUT_DIGEST_FORMAT
    return json.dumps(digests, sort_keys=True, separators=(",", ":"))


class ShardStore:

    def __init__(self, substrates: list[str], *,
                 tenant: Tenant | None = None, tenant_id: str | None = None):
        if tenant is None:
            raise ValueError(
                f"ShardStore: tenant is required — graphy resolves identity only "
                f"through a declared Tenant; absent tenant = refuse"
            )
        if not tenant_id or not tenant_id.strip():
            raise ValueError(
                f"ShardStore: tenant_id is required — graphy resolves identity only "
                f"through a declared Tenant; absent or empty tenant_id = refuse"
            )
        self._mesh = load_set(substrates, tenant=tenant, tenant_id=tenant_id)
        self._substrates = list(substrates)
        self._gen = _generation_digest(self._mesh, self._substrates)

    @classmethod
    def from_mesh(cls, mesh, substrates: list[str]) -> "ShardStore":
        self = cls.__new__(cls)
        self._mesh = mesh
        self._substrates = list(substrates)
        self._gen = _generation_digest(mesh, self._substrates)
        return self

    @property
    def mesh(self):
        return self._mesh

    def generation(self) -> str:
        return self._gen

    def membership(self, node_id: str) -> str | None:
        return self._mesh.node_owner.get(node_id)

    def record(self, node_id: str) -> dict | None:
        return self._mesh.node_records.get(node_id)

    def find(self, symbol: str) -> list[str]:
        tails = ("." + symbol, "/" + symbol)
        return [n for n in self._mesh.node_owner if n == symbol or n.endswith(tails)]

    def grep(self, needle: str) -> list[str]:
        return [n for n in self._mesh.node_owner if needle in n]

    def neighbours(self, node_id: str) -> list[Neighbour]:
        seen: dict[tuple, str] = {}
        for (nbr, _sal, _wit, rel) in self._mesh.adjacency.get(node_id, []):
            seen.setdefault((nbr, rel), self._mesh.orientation(node_id, nbr, rel))
        return [Neighbour(n, r, d) for (n, r), d in seen.items()]

    def owned(self, owner: str):
        """Every (id, columns) one corpus owns — the whole-corpus read an aggregate takes. The
        columns are COLUMNS; the full record is record()'s."""
        for nid, own in self._mesh.node_owner.items():
            if own == owner:
                yield nid, _columns(self._mesh.node_records.get(nid))

    def edges(self):
        """Every directed (src, dst, rel) the store carries."""
        yield from sorted(self._mesh.directed)


class SQLiteStore:

    def __init__(self, db_path: str | Path):
        p = Path(db_path)
        if not p.is_file():
            raise StoreError(f"no compiled store at {p} — build it with `compile_store`")
        self._db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        meta = dict(self._db.execute("SELECT k, v FROM meta"))
        if "generation" not in meta:
            raise StoreError(f"store at {p} carries no generation row — refusing to serve "
                             f"a snapshot that cannot be invalidated")
        got = meta.get("generation_format")
        if got != str(GENERATION_FORMAT):
            raise StoreError(
                f"store at {p} was compiled under generation format "
                f"{got or '<pre-versioning>'}; this build speaks {GENERATION_FORMAT}. Its "
                f"generations are not comparable with ours — recompile with `compile_store`")
        if "input_digest" not in meta:
            raise StoreError(f"store at {p} carries no input_digest row — refusing to "
                             f"serve a snapshot whose freshness cannot be measured; "
                             f"recompile with `compile_store`")
        self._input_digest = meta["input_digest"]
        try:
            fmt = json.loads(self._input_digest).get(_INPUT_DIGEST_FORMAT_KEY)
        except (ValueError, AttributeError):
            fmt = None
        if fmt != INPUT_DIGEST_FORMAT:
            raise StoreError(
                f"store at {p} measures its inputs under digest format "
                f"{fmt or '<pre-versioning>'}; this build speaks {INPUT_DIGEST_FORMAT} "
                f"(the bytes hashed, never parsed). Its freshness cannot be compared with "
                f"ours — recompile with `compile_store`")
        self._gen = meta["generation"]

    def generation(self) -> str:
        return self._gen

    def membership(self, node_id: str) -> str | None:
        r = self._db.execute("SELECT owner FROM nodes WHERE id=?", (node_id,)).fetchone()
        return r[0] if r else None

    def record(self, node_id: str) -> dict | None:
        r = self._db.execute("SELECT record FROM nodes WHERE id=?", (node_id,)).fetchone()
        return json.loads(r[0]) if r and r[0] is not None else None

    def find(self, symbol: str) -> list[str]:
        """The ids a bare symbol names: the exact id, or the nodes whose dotted tail is it."""
        esc = symbol.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = self._db.execute(
            "SELECT id FROM nodes WHERE id=? OR id LIKE ? ESCAPE '\\' OR id LIKE ? ESCAPE '\\'",
            (symbol, "%." + esc, "%/" + esc))
        return [r[0] for r in rows]

    def grep(self, needle: str) -> list[str]:
        """The ids that carry a substring — the hunt's second net, after the tail."""
        esc = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = self._db.execute("SELECT id FROM nodes WHERE id LIKE ? ESCAPE '\\'", ("%" + esc + "%",))
        return [r[0] for r in rows]

    def neighbours(self, node_id: str) -> list[Neighbour]:
        out: list[Neighbour] = []
        for dst, rel in self._db.execute(
                "SELECT dst, rel FROM edges WHERE src=?", (node_id,)):
            out.append(Neighbour(dst, rel, WITH))
        for src, rel in self._db.execute(
                "SELECT src, rel FROM edges WHERE dst=?", (node_id,)):
            out.append(Neighbour(src, rel, AGAINST))
        seen: dict[tuple, str] = {}
        for n in out:
            key = (n.node, n.relation)
            seen[key] = BOTH if key in seen and seen[key] != n.direction else \
                seen.get(key, n.direction)
        return [Neighbour(node, rel, d) for (node, rel), d in seen.items()]

    def owned(self, owner: str):
        """Every (id, columns) one corpus owns — the whole-corpus read an aggregate takes, straight
        off the columns: no record is decoded. The full record is record()'s."""
        for row in self._db.execute(
                "SELECT id, node_type, dotted, module, role, file, line, record IS NULL "
                "FROM nodes WHERE owner=? ORDER BY id", (owner,)):
            yield row[0], (None if row[7] else dict(zip(COLUMNS, row[1:7])))

    def edges(self):
        """Every directed (src, dst, rel) the store carries."""
        yield from self._db.execute("SELECT src, dst, rel FROM edges ORDER BY src, dst, rel")

    def close(self) -> None:
        self._db.close()


def store_path_for(substrates: list[str], *, tenant: Tenant | None = None) -> Path:
    if tenant is None:
        raise ValueError(
            f"store_path_for: tenant is required — graphy resolves identity only "
            f"through a declared Tenant; absent tenant = refuse"
        )
    key = hashlib.sha256("\x00".join(sorted(substrates)).encode()).hexdigest()[:12]
    return Path(tenant.data_home) / f".mesh_store_{key}.sqlite"


def compile_store(substrates: list[str], db_path: str | Path,
                  *, tenant: Tenant | None = None,
                  tenant_id: str | None = None) -> dict:
    if tenant is None:
        raise ValueError(
            f"compile_store: tenant is required — graphy resolves identity only "
            f"through a declared Tenant; absent tenant = refuse"
        )
    if not tenant_id or not tenant_id.strip():
        raise ValueError(
            f"compile_store: tenant_id is required — graphy resolves identity only "
            f"through a declared Tenant; absent or empty tenant_id = refuse"
        )
    shard = ShardStore(substrates, tenant=tenant, tenant_id=tenant_id)
    mesh = shard.mesh
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + f".tmp.{os.getpid()}")
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    try:
        db.executescript(SCHEMA)
        def _rows():
            for nid, owner in mesh.node_owner.items():
                rec = mesh.node_records.get(nid)
                cols = tuple(rec.get(k) for k in COLUMNS) if rec is not None else (None,) * len(COLUMNS)
                yield (nid, owner or "", *cols,
                       json.dumps(rec, default=str) if rec is not None else None)
        db.executemany(
            "INSERT OR REPLACE INTO nodes(id, owner, node_type, dotted, module, role, file, line, record) "
            "VALUES (?,?,?,?,?,?,?,?,?)", _rows())
        db.executemany("INSERT INTO edges(src, dst, rel) VALUES (?,?,?)",
                       ((s, d, r) for (s, d, r) in mesh.directed))
        db.executemany("INSERT INTO meta(k, v) VALUES (?,?)", [
            ("generation", shard.generation()),
            ("generation_format", str(GENERATION_FORMAT)),
            ("substrates", ",".join(sorted(substrates))),
            ("nodes", str(mesh.stats.nodes)),
            ("edges", str(len(mesh.directed))),
            ("input_digest", _compute_input_digest(substrates, tenant=tenant)),
        ])
        db.commit()
    finally:
        db.close()
    os.replace(tmp, p)
    return {"db": str(p), "generation": shard.generation(),
            "substrates": sorted(substrates),
            "nodes": mesh.stats.nodes, "edges": len(mesh.directed)}


CURSOR_FORMAT = 1


@dataclass
class WalkCursor:
    generation: str
    seed: str
    target: str
    prev: dict = field(default_factory=dict)
    frontier: list = field(default_factory=list)
    hops: int = 0
    stopped_by: str | None = None

    def visited(self) -> int:
        return len(self.prev)

    def encode(self) -> str:
        payload = {"v": CURSOR_FORMAT, "g": self.generation, "s": self.seed,
                   "t": self.target, "h": self.hops, "b": self.stopped_by,
                   "f": self.frontier,
                   "p": {k: list(v) for k, v in self.prev.items()}}
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(zlib.compress(raw, 6)).decode()

    @classmethod
    def decode(cls, token: str) -> "WalkCursor":
        try:
            payload = json.loads(zlib.decompress(base64.urlsafe_b64decode(token.encode())))
        except Exception as exc:                       # noqa: BLE001 — any corruption at all
            raise StoreError(
                f"cursor is unreadable ({type(exc).__name__}) — refusing to guess at walk "
                f"state; re-run the walk instead") from exc
        got = payload.get("v")
        if got != CURSOR_FORMAT:
            raise StoreError(
                f"cursor is format v{got}, this build speaks v{CURSOR_FORMAT} — refusing to "
                f"reinterpret a walk state written by a different contract")
        return cls(generation=payload["g"], seed=payload["s"], target=payload["t"],
                   prev={k: tuple(v) for k, v in payload["p"].items()},
                   frontier=payload["f"], hops=payload["h"], stopped_by=payload["b"])


def _as_cursor(cursor) -> WalkCursor:
    return cursor if isinstance(cursor, WalkCursor) else WalkCursor.decode(cursor)


def _require_same_generation(store, cur: WalkCursor) -> None:
    live = store.generation()
    if live != cur.generation:
        raise StaleCursorError(cur.generation, live, cur.seed)


def _advance(store, cur: WalkCursor, max_depth: int, max_nodes: int) -> tuple:
    prev, frontier, hops = cur.prev, list(cur.frontier), cur.hops
    reached = cur.target in prev
    stopped = None
    while not reached and stopped is None and frontier and hops < max_depth:
        hops += 1
        nxt: list[str] = []
        for node in frontier:
            for nb in store.neighbours(node):
                if nb.node in prev:
                    continue
                prev[nb.node] = (node, nb.relation, nb.direction)
                if nb.node == cur.target:
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
    return WalkCursor(generation=cur.generation, seed=cur.seed, target=cur.target,
                      prev=prev, frontier=frontier, hops=hops, stopped_by=stopped), reached


def _frames(store, cur: WalkCursor, node: str) -> list:
    chain: list[str] = []
    at: str | None = node
    while at is not None:
        chain.append(at)
        at = cur.prev[at][0]
    chain.reverse()
    steps = []
    for a, b in zip(chain, chain[1:]):
        _parent, rel, direction = cur.prev[b]
        steps.append(Step(src=a, dst=b, relation=rel, direction=direction or UNKNOWN,
                          owner_src=store.membership(a) or "",
                          owner_dst=store.membership(b) or ""))
    return steps


def _finish(store, advanced: tuple) -> PathResult:
    cur, reached = advanced
    if not reached:
        return PathResult(seed=cur.seed, target=cur.target, found=False,
                          visited=cur.visited(), stopped_by=cur.stopped_by, cursor=cur)
    return PathResult(seed=cur.seed, target=cur.target, found=True,
                      steps=_frames(store, cur, cur.target),
                      visited=cur.visited(), stopped_by=None, cursor=cur)


def path_to(store, seed: str, target: str, max_depth: int = 6,
            max_nodes: int = 250_000) -> PathResult:
    if store.membership(seed) is None:
        return PathResult(seed=seed, target=target, found=False, stopped_by="seed-absent")
    if store.membership(target) is None:
        return PathResult(seed=seed, target=target, found=False, stopped_by="target-absent")
    start = WalkCursor(generation=store.generation(), seed=seed, target=target,
                       prev={seed: (None, None, None)}, frontier=[seed], hops=0)
    return _finish(store, _advance(store, start, max_depth, max_nodes))


def resume(store, cursor, max_depth: int = 6, max_nodes: int = 250_000) -> PathResult:
    cur = _as_cursor(cursor)
    _require_same_generation(store, cur)
    replay = WalkCursor(generation=cur.generation, seed=cur.seed, target=cur.target,
                        prev=dict(cur.prev), frontier=list(cur.frontier), hops=cur.hops)
    return _finish(store, _advance(store, replay, max_depth, max_nodes))


def open_for(substrates: list[str], *, tenant: Tenant | None = None,
             tenant_id: str | None = None,
             db_path: str | Path | None = None,
             on_stale: str = "refuse") -> SQLiteStore:
    if on_stale not in ("refuse", "warn"):
        raise ValueError(
            f"on_stale must be exactly 'refuse' or 'warn', got {on_stale!r}. "
            f"'heal' was removed in R1 — a query never compiles; healing stays in "
            f"`compile_store`.")
    if tenant is None:
        raise ValueError(
            f"open_for: tenant is required — graphy resolves identity only "
            f"through a declared Tenant; absent tenant = refuse"
        )
    if not tenant_id or not tenant_id.strip():
        raise ValueError(
            f"open_for: tenant_id is required — graphy resolves identity only "
            f"through a declared Tenant; absent or empty tenant_id = refuse"
        )
    p = Path(db_path) if db_path else store_path_for(substrates, tenant=tenant)
    if not p.is_file():
        raise StoreError(
            f"no compiled store for roster {sorted(substrates)} at {p}.\n"
            f"    A query never builds one (walk-kernel Rung 4: no query-time writes).\n"
            f"    Build it:  {_repair_hint(substrates, tenant, tenant_id, p)}")
    store = SQLiteStore(p)

    live_input_digest = _compute_input_digest(substrates, tenant=tenant)
    if live_input_digest == store._input_digest:
        return store

    try:
        live_gen = ShardStore(substrates, tenant=tenant, tenant_id=tenant_id).generation()
    except (OSError, ValueError) as exc:
        raise StoreError(
            f"inputs for roster {sorted(substrates)} changed AND the live shards cannot "
            f"be materialized to compare generations ({type(exc).__name__}: {exc}) — "
            f"refusing to serve") from exc
    served_gen = store.generation()
    if live_gen == served_gen:
        return store

    if on_stale == "warn":
        print(f"graphy.federated_store: store for {sorted(substrates)} is STALE — serving generation "
              f"{served_gen} while the live shards digest to {live_gen}.\n"
              f"    Rebuild it:  {_repair_hint(substrates, tenant, tenant_id, p)}",
              file=sys.stderr)
        return store
    raise StoreError(
        f"compiled store for roster {sorted(substrates)} at {p} is STALE: it serves "
        f"generation {served_gen} but the live shards digest to {live_gen}.\n"
        f"    A query never rebuilds one (walk-kernel Rung 4: no query-time writes).\n"
        f"    Rebuild it:  {_repair_hint(substrates, tenant, tenant_id, p)}")


def _repair_hint(substrates, tenant, tenant_id: str, p) -> str:
    return shlex.join([
        "python", "-m", "graphy.federated_store",
        "--mesh-set", ",".join(sorted(substrates)),
        "--data-home", str(tenant.data_home),
        "--join-keys", str(tenant.join_keys),
        "--tenant-id", tenant_id,
        "--out", str(p),
    ])


def frames(store, cursor, node: str) -> list:
    cur = _as_cursor(cursor)
    _require_same_generation(store, cur)
    if node not in cur.prev:
        raise StoreError(
            f"{node!r} was not visited by this walk (seed {cur.seed!r}, {cur.visited()} "
            f"nodes visited) — it has no frame here; continue the walk with `resume` first")
    return _frames(store, cur, node)


class _StoreAdj:

    def __init__(self, store):
        self._store = store
        self._cache: dict[str, list] = {}

    def _nbrs(self, node: str) -> list:
        hit = self._cache.get(node)
        if hit is None:
            hit = [(n.node, _ast_edge_salience(n.relation), [])
                   for n in self._store.neighbours(node)]
            self._cache[node] = hit
        return hit

    def get(self, node: str, default=None):
        n = self._nbrs(node)
        return n if n else default

    def __contains__(self, node: str) -> bool:
        return bool(self._nbrs(node))


def spread(store, seed: str, depth: int, top: int,
           decay: float, min_salience: float) -> dict:
    adj = _StoreAdj(store)
    state = activate(adj, seed, depth, decay)
    by_owner: dict[str, dict] = defaultdict(dict)
    for nid, ns in state.items():
        by_owner[store.membership(nid) or WIRE_BUCKET][nid] = ns
    buckets: dict[str, list] = {}
    for owner, bstate in by_owner.items():
        ordered, _qualified, _truncated = rank(bstate, top, min_salience)
        buckets[owner] = [
            {"id": nid, "energy": ns.energy, "salience": ns.salience, "hops": ns.hops}
            for nid, ns in ordered
        ]
    return {
        "seed": seed,
        "seed_present": store.membership(seed) is not None,
        "seed_owner": store.membership(seed),
        "activated": len(state),
        "buckets": buckets,
    }


def main(argv=None) -> int:
    import argparse                                    # noqa: PLC0415 — CLI-only

    ap = argparse.ArgumentParser(
        prog="graphy.federated_store",
        description="compile a substrate roster into its queryable store")
    ap.add_argument("--mesh-set", default=None,
                    help="explicit comma-separated roster. Omit and pass --seed instead "
                         "to derive it from the federation index.")
    ap.add_argument("--seed", default=None,
                    help="derive the roster from this node id (a <scheme>://symbol).")
    ap.add_argument("--radius", type=int, default=1)
    ap.add_argument("--data-home", required=True,
                    help="the tenant data_home holding the `<slug>_graph` directories and "
                         "the federation scheme index.")
    ap.add_argument("--join-keys", required=True,
                    help="path to the tenant's substrate_override_registry.json.")
    ap.add_argument("--tenant-id", required=True,
                    help="the receipt-name for every OverrideRecord minted while compiling "
                         "this store — graphy resolves identity only through a declared "
                         "Tenant, and the receipt name is part of that declaration.")
    ap.add_argument("--out", default=None,
                    help="override the derived store path (default: store_path_for()).")
    a = ap.parse_args(argv)

    tenant = _cross_substrate._cli_tenant(a.data_home, a.join_keys)

    if (a.mesh_set is None) == (a.seed is None):
        print("pass exactly one of --mesh-set or --seed", file=sys.stderr)
        return 2
    if a.mesh_set is not None:
        substrates = [x.strip() for x in a.mesh_set.split(",") if x.strip()]
        if not substrates:
            print("--mesh-set was given but empty — pass real substrate names.",
                  file=sys.stderr)
            return 2
    else:
        from graphy.cross_substrate import (  # noqa: PLC0415
            RosterError, derive_roster,
        )
        try:
            substrates, dropped = derive_roster(a.seed, tenant=tenant,
                                                tenant_id=a.tenant_id,
                                                radius=a.radius)
        except RosterError as e:
            print(f"federated_store: {e}", file=sys.stderr)
            return 4
        print(f"roster (derived, radius={a.radius}): {','.join(substrates)}", file=sys.stderr)
        if dropped:
            print(f"  NOT LOADED (no graph on this box): {','.join(dropped)}", file=sys.stderr)

    out = Path(a.out) if a.out else store_path_for(substrates, tenant=tenant)
    info = compile_store(substrates, out, tenant=tenant, tenant_id=a.tenant_id)
    print(f"compiled {info['nodes']:,} nodes / {info['edges']:,} edges -> {info['db']}")
    print(f"generation {info['generation']} (format {GENERATION_FORMAT})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
