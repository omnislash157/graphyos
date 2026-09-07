"""The container. Beside every shard, two parquet files — ``adjacency.parquet`` (one row per
edge) and ``nodes.parquet`` (one row per node) — so the whole estate is one
``read_parquet`` view. DuckDB is the only dependency and it is optional (``pip install
'graphyos[estate]'``): without it the JSON path is untouched and ``emit`` refuses with the
install line. The rows carry exactly what the shard carries — the loader's view, sidecar
included — plus the three forms a walk matches a literal against, derived from the id alone.
A receipt beside the parquets pins the shard input digest they were built from, so a
container older than its shard reads as stale, never as fresh. A receipt may instead say
``pending``: the shard is declared, its parquet not yet written — ``estate`` writes it on the
first ask and ``emit_all`` writes the rest — so ``eat`` never pays for a ring nobody has queried.
One DuckDB connection serves a whole batch (``emit_all`` · ``estate``), never one per shard."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from graphy.native_json_graph_ir import load_graph_ir

__all__ = ["ContainerError", "have_duckdb", "emit", "emit_all", "defer", "verify", "estate", "node_forms",
           "ADJACENCY", "NODES", "RECEIPT", "INSTALL_HINT"]

ADJACENCY = "adjacency.parquet"
NODES = "nodes.parquet"
RECEIPT = "container.json"
INSTALL_HINT = "duckdb is not installed — pip install 'graphyos[estate]'"
_EDGE_CORE = frozenset({"kind", "src", "dst", "edge_type", "dst_repr", "src_repr"})
_NODE_CORE = frozenset({"kind", "id", "node_type", "dotted", "file", "loc"})


class ContainerError(RuntimeError):
    pass


def have_duckdb() -> bool:
    try:
        import duckdb  # noqa: F401
    except ImportError:
        return False
    return True


def _duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise ContainerError(INSTALL_HINT) from exc
    return duckdb


def node_forms(nid: str) -> tuple[str, str, str]:
    """(body, last, kind) from the id alone: ``t://class/pkg.Foo`` → ("pkg.Foo", "Foo", "class")."""
    kind, body = "", nid
    if "://" in nid:
        _, rest = nid.split("://", 1)
        kind, body = rest.split("/", 1) if "/" in rest else ("", rest)
    last = body.rsplit(".", 1)[-1] if "." in body else body
    return body, last, kind


def _attrs(rec: dict, core: frozenset) -> str | None:
    extra = {k: v for k, v in rec.items() if k not in core}
    return json.dumps(extra, sort_keys=True, default=str) if extra else None


def _edge_rows(edges: Sequence[dict]) -> list[tuple]:
    rows = []
    for e in edges:
        rows.append((e.get("src"), e.get("dst"), e.get("edge_type"), _attrs(e, _EDGE_CORE),
                     e.get("dst_repr") if isinstance(e.get("dst_repr"), str) else None,
                     e.get("src_repr") if isinstance(e.get("src_repr"), str) else None))
    return rows


def _node_rows(nodes: Sequence[dict]) -> list[tuple]:
    rows = []
    for n in nodes:
        nid = n["id"]
        body, last, kind = node_forms(nid)
        loc = n.get("loc")
        loc = loc if isinstance(loc, int) and not isinstance(loc, bool) else None
        rows.append((nid, kind, body, last, n.get("node_type"), n.get("dotted"), n.get("file"), loc,
                     _attrs(n, _NODE_CORE)))
    return rows


def shard_digest(graph_dir: Path) -> str:
    """Everything the container writes: the store's digest (nodes + resolved edges) and the
    residuals beside it — the label-only edges the store never compiles but the parquet keeps."""
    import hashlib
    from graphy.federated_store import _shard_input_digest
    gd = Path(graph_dir)
    gir = load_graph_ir(gd)
    h = hashlib.sha256(_shard_input_digest(gd).encode())
    h.update(b"\x00residuals\x00" + json.dumps(list(gir.residuals), sort_keys=True, default=str).encode())
    return h.hexdigest()[:16]


def _write_parquet(con, table: str, columns: dict[str, str], rows: list[tuple], out: Path) -> int:
    """Rows reach DuckDB as one JSON array — one ``json.dumps`` in C, one vectorized ``read_json``
    — never bound as parameters: binding a Python value costs about 50 µs each in duckdb 1.5, so a
    shard of 3,700 six-column edges takes a second through ``unnest($1)`` or ``VALUES (?, …)`` and
    three through ``executemany``, where the array feed takes 15 ms (RECON §57). The table is
    created fresh and dropped, so one connection serves any number of writes in a row."""
    names = list(columns)
    feed = out.with_name(f".{out.name}.{os.getpid()}.json")
    feed.write_text(json.dumps([dict(zip(names, row)) for row in rows], ensure_ascii=False), encoding="utf-8")
    spec = ", ".join(f"'{k}': '{v}'" for k, v in columns.items())
    tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    try:
        con.execute(f"CREATE OR REPLACE TABLE {table} ({', '.join(f'{k} {v}' for k, v in columns.items())})")
        if rows:
            con.execute(f"INSERT INTO {table} SELECT {', '.join(names)} FROM read_json('{feed.as_posix()}', "
                        f"format='array', columns={{{spec}}})")
        con.execute(f"COPY {table} TO '{tmp.as_posix()}' (FORMAT PARQUET)")
        os.replace(tmp, out)
        con.execute(f"DROP TABLE {table}")
    finally:
        if feed.exists():
            feed.unlink()
        if tmp.exists():
            tmp.unlink()
    return len(rows)


def emit(graph_dir: str | Path, *, con=None) -> dict:
    """Write both parquets and the receipt beside one shard. Returns the receipt. ``con`` is a
    connection the caller holds for a batch; without one, this shard gets its own."""
    duckdb = _duckdb()
    gd = Path(graph_dir)
    if not (gd / "nodes.json").is_file() or not (gd / "edges.json").is_file():
        raise ContainerError(f"no shard (nodes.json + edges.json) at {gd}")
    started = time.perf_counter()
    gir = load_graph_ir(gd)
    # every edge the shard carries: the resolved ones the store compiles, and the label-only ones
    # (dst_repr / src_repr) the loader parks as residuals — the parquet keeps both, as the host's did
    edges = list(gir.edges) + [r for r in gir.residuals if isinstance(r, dict) and r.get("kind") == "edge"]
    own = con is None
    if own:
        con = duckdb.connect()
    try:
        n_edges = _write_parquet(
            con, "adj",
            {"src": "VARCHAR", "dst": "VARCHAR", "edge_type": "VARCHAR", "attrs": "VARCHAR",
             "dst_repr": "VARCHAR", "src_repr": "VARCHAR"},
            _edge_rows(edges), gd / ADJACENCY)
        n_nodes = _write_parquet(
            con, "nodes",
            {"id": "VARCHAR", "kind": "VARCHAR", "body": "VARCHAR", "last": "VARCHAR", "node_type": "VARCHAR",
             "dotted": "VARCHAR", "file": "VARCHAR", "loc": "BIGINT", "attrs": "VARCHAR"},
            _node_rows(gir.nodes), gd / NODES)
    finally:
        if own:
            con.close()
    receipt = {
        "shard": gd.name, "input_digest": shard_digest(gd),
        "duckdb": duckdb.__version__,
        "emitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seconds": round(time.perf_counter() - started, 3),
        "files": {ADJACENCY: {"rows": n_edges, "bytes": (gd / ADJACENCY).stat().st_size},
                  NODES: {"rows": n_nodes, "bytes": (gd / NODES).stat().st_size}},
    }
    _write_receipt(gd, receipt)
    return receipt


def _write_receipt(gd: Path, receipt: dict) -> None:
    tmp = gd / f".{RECEIPT}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, gd / RECEIPT)


def defer(graph_dir: str | Path) -> dict:
    """Declare the container without writing it: a ``pending`` receipt beside the shard and no
    parquet (a stale pair from an earlier emit is removed, so pending means exactly no parquet).
    ``estate`` emits a pending shard on the first ask; ``emit_all`` over what is not fresh writes
    the rest. Needs no duckdb — the write that does is the one deferred."""
    gd = Path(graph_dir)
    if not (gd / "nodes.json").is_file() or not (gd / "edges.json").is_file():
        raise ContainerError(f"no shard (nodes.json + edges.json) at {gd}")
    for name in (ADJACENCY, NODES):
        if (gd / name).exists():
            (gd / name).unlink()
    receipt = {"shard": gd.name, "pending": True,
               "deferred_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "note": "graphy estate emits this container on the first ask; graphy container --emit writes it now"}
    _write_receipt(gd, receipt)
    return receipt


def verify(graph_dir: str | Path) -> str:
    """``fresh`` when both parquets and the receipt exist and the receipt's digest matches the
    shard as it stands now; ``stale`` when the shard moved under it; ``pending`` when the receipt
    declares a container not yet written; ``absent`` otherwise."""
    gd = Path(graph_dir)
    if not all((gd / name).is_file() for name in ("nodes.json", "edges.json")):
        return "absent"                  # no shard, no container to hold to it — the store lane names the missing file
    if not (gd / RECEIPT).is_file():
        return "absent"
    try:
        receipt = json.loads((gd / RECEIPT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "stale"
    if receipt.get("pending") is True:
        return "pending"
    if not all((gd / name).is_file() for name in (ADJACENCY, NODES)):
        return "absent"
    return "fresh" if receipt.get("input_digest") == shard_digest(gd) else "stale"


def estate(graph_dirs: Sequence[str | Path], traversals: str | Path | None = None, *, log=None):
    """One connection with two views over every container named: ``adj`` and ``nodes``, each
    with a ``corpus`` column (the shard directory's name). A pending container is emitted first,
    on this same connection, and ``log`` (when given) is told how many. A shard without a fresh
    container after that is refused by name — a view that quietly skipped a shard would lie about
    the estate. With a traversal home that holds walks, a third view ``walks`` (seed, hop, node,
    via_src, relation, direction, carrier, generation) reads every stored frontier."""
    duckdb = _duckdb()
    dirs = [Path(d) for d in graph_dirs]
    states = {d: verify(d) for d in dirs}
    missing = [d.name for d, st in states.items() if st not in ("fresh", "pending")]
    if missing:
        raise ContainerError(f"container absent or stale for {missing} — run graphy build (with "
                             f"duckdb installed) or graphy container --emit first")
    con = duckdb.connect()
    pending = [d for d, st in states.items() if st == "pending"]
    if pending:
        try:
            receipts = emit_all(pending, con=con)
        except Exception:
            con.close()
            raise
        if log is not None:
            log(f"ESTATE: emitted {len(pending)} pending container(s) on the first ask — {summarize(receipts)}")
    for view, name, cols in (
            ("adj", ADJACENCY, "src, dst, edge_type, attrs, dst_repr, src_repr"),
            ("nodes", NODES, "id, kind, body, last, node_type, dotted, file, loc, attrs")):
        files = ", ".join(f"'{(d / name).as_posix()}'" for d in dirs)
        con.execute(
            f"CREATE VIEW {view} AS SELECT regexp_extract(filename, '([^/]+)/{name}$', 1) AS corpus, "
            f"{cols} FROM read_parquet([{files}], filename=true, union_by_name=true)")
    if traversals is not None:
        th = Path(traversals)
        walks = sorted(th.glob("*/*.parquet")) if th.is_dir() else []
        if walks:
            files = ", ".join(f"'{w.as_posix()}'" for w in walks)
            con.execute(f"CREATE VIEW walks AS SELECT seed, hop, node, via_src, relation, direction, carrier, "
                        f"generation, on_path FROM read_parquet([{files}], union_by_name=true)")
    return con


def emit_all(graph_dirs: Sequence[str | Path], *, con=None) -> list[dict]:
    """Every shard named, through one connection — ``duckdb.connect`` costs 6 ms and a whole
    shard's write about the same, so a ring of 85 paid half its emit opening connections. The
    batch runs on one thread: a shard's write is too small to split, and every worker thread
    keeps an allocator arena that outlives the query — eight of them held 100 MB of RSS over a
    ten-shard build where one holds none (RECON §57). The caller's setting is put back after."""
    dirs = list(graph_dirs)
    if not dirs:
        return []
    duckdb = _duckdb()
    own = con is None
    if own:
        con = duckdb.connect()
    threads = con.execute("SELECT current_setting('threads')").fetchone()[0]
    con.execute("SET threads = 1")
    try:
        return [emit(d, con=con) for d in dirs]
    finally:
        if own:
            con.close()
        else:
            con.execute(f"SET threads = {int(threads)}")


def emit_missing(graph_dirs: Sequence[str | Path]) -> tuple[list[dict], int]:
    """Emit what is not fresh (pending · stale · absent); a fresh container is left as it stands
    (its content would come back byte-for-byte). Returns (receipts, the count left as fresh)."""
    dirs = [Path(d) for d in graph_dirs]
    todo = [d for d in dirs if verify(d) != "fresh"]
    return emit_all(todo), len(dirs) - len(todo)


def summarize(receipts: Sequence[dict]) -> str:
    rows = sum(r["files"][ADJACENCY]["rows"] for r in receipts)
    nodes = sum(r["files"][NODES]["rows"] for r in receipts)
    size = sum(r["files"][ADJACENCY]["bytes"] + r["files"][NODES]["bytes"] for r in receipts)
    secs = sum(r["seconds"] for r in receipts)
    return (f"{len(receipts)} shard(s) · {nodes} node row(s) · {rows} edge row(s) · "
            f"{size / 1e6:.2f} MB parquet · {secs:.2f} s")
