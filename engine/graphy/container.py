"""The container. Beside every shard, two parquet files — ``adjacency.parquet`` (one row per
edge) and ``nodes.parquet`` (one row per node) — so the whole estate is one
``read_parquet`` view. DuckDB is the only dependency and it is optional (``pip install
'graphyos[estate]'``): without it the JSON path is untouched and ``emit`` refuses with the
install line. The rows carry exactly what the shard carries — the loader's view, sidecar
included — plus the three forms a walk matches a literal against, derived from the id alone.
A receipt beside the parquets pins the shard input digest they were built from, so a
container older than its shard reads as stale, never as fresh."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from graphy.native_json_graph_ir import load_graph_ir

__all__ = ["ContainerError", "have_duckdb", "emit", "verify", "estate", "node_forms",
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
    """Rows go through one newline-delimited JSON file that DuckDB bulk-loads, never through a
    per-row insert (which costs seconds per ten thousand rows)."""
    names = list(columns)
    feed = out.with_name(f".{out.name}.{os.getpid()}.jsonl")
    with feed.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(dict(zip(names, row)), ensure_ascii=False) + "\n")
    spec = ", ".join(f"'{k}': '{v}'" for k, v in columns.items())
    tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    try:
        con.execute(f"CREATE TABLE {table} ({', '.join(f'{k} {v}' for k, v in columns.items())})")
        if rows:
            con.execute(f"INSERT INTO {table} SELECT {', '.join(names)} FROM read_json('{feed.as_posix()}', "
                        f"format='newline_delimited', columns={{{spec}}})")
        con.execute(f"COPY {table} TO '{tmp.as_posix()}' (FORMAT PARQUET)")
        os.replace(tmp, out)
        con.execute(f"DROP TABLE {table}")
    finally:
        if feed.exists():
            feed.unlink()
        if tmp.exists():
            tmp.unlink()
    return len(rows)


def emit(graph_dir: str | Path) -> dict:
    """Write both parquets and the receipt beside one shard. Returns the receipt."""
    duckdb = _duckdb()
    gd = Path(graph_dir)
    if not (gd / "nodes.json").is_file() or not (gd / "edges.json").is_file():
        raise ContainerError(f"no shard (nodes.json + edges.json) at {gd}")
    started = time.perf_counter()
    gir = load_graph_ir(gd)
    # every edge the shard carries: the resolved ones the store compiles, and the label-only ones
    # (dst_repr / src_repr) the loader parks as residuals — the parquet keeps both, as the host's did
    edges = list(gir.edges) + [r for r in gir.residuals if isinstance(r, dict) and r.get("kind") == "edge"]
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
        con.close()
    receipt = {
        "shard": gd.name, "input_digest": shard_digest(gd),
        "duckdb": duckdb.__version__,
        "emitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seconds": round(time.perf_counter() - started, 3),
        "files": {ADJACENCY: {"rows": n_edges, "bytes": (gd / ADJACENCY).stat().st_size},
                  NODES: {"rows": n_nodes, "bytes": (gd / NODES).stat().st_size}},
    }
    tmp = gd / f".{RECEIPT}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, gd / RECEIPT)
    return receipt


def verify(graph_dir: str | Path) -> str:
    """``fresh`` when both parquets and the receipt exist and the receipt's digest matches the
    shard as it stands now; ``stale`` when the shard moved under it; ``absent`` otherwise."""
    gd = Path(graph_dir)
    if not all((gd / name).is_file() for name in (ADJACENCY, NODES, RECEIPT)):
        return "absent"
    try:
        receipt = json.loads((gd / RECEIPT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "stale"
    return "fresh" if receipt.get("input_digest") == shard_digest(gd) else "stale"


def estate(graph_dirs: Sequence[str | Path], traversals: str | Path | None = None):
    """One connection with two views over every container named: ``adj`` and ``nodes``, each
    with a ``corpus`` column (the shard directory's name). A shard without a fresh container is
    refused by name — a view that quietly skipped a shard would lie about the estate. With a
    traversal home that holds walks, a third view ``walks`` (seed, hop, node, via_src, relation,
    direction, carrier, generation) reads every stored frontier."""
    duckdb = _duckdb()
    dirs = [Path(d) for d in graph_dirs]
    missing = [d.name for d in dirs if verify(d) != "fresh"]
    if missing:
        raise ContainerError(f"container absent or stale for {missing} — run graphy build (with "
                             f"duckdb installed) or graphy container --emit first")
    con = duckdb.connect()
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


def emit_all(graph_dirs: Sequence[str | Path]) -> list[dict]:
    return [emit(d) for d in graph_dirs]


def summarize(receipts: Sequence[dict]) -> str:
    rows = sum(r["files"][ADJACENCY]["rows"] for r in receipts)
    nodes = sum(r["files"][NODES]["rows"] for r in receipts)
    size = sum(r["files"][ADJACENCY]["bytes"] + r["files"][NODES]["bytes"] for r in receipts)
    secs = sum(r["seconds"] for r in receipts)
    return (f"{len(receipts)} shard(s) · {nodes} node row(s) · {rows} edge row(s) · "
            f"{size / 1e6:.2f} MB parquet · {secs:.2f} s")
