"""index_estate — one SQL view across every shard a farm index holds.

A tenant's estate is its own shards' parquet. An index has no tenant: it is every release the
farm minted, hundreds of them, and the knowledge-graph questions run across all of it — who
imports what, which classes are inherited from most, which packages reach a given symbol. The
estate is materialized once beside the index (``<index>/estate/``: ``adj.parquet``,
``nodes.parquet``, ``receipt.json``) from every named shard in the catalog, the receipt pinning
the catalog's sha256, so a query is a read and never a load. When the catalog moves the estate
is STALE and says so; ``--emit`` rebuilds it. duckdb is the ``graphyos[estate]`` extra, and
without it every door here refuses by name.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from graphy.container import ContainerError, _duckdb, node_forms
from graphy.index import catalog as index_catalog

__all__ = ["ESTATE_DIR", "RECEIPT", "emit_index", "verify_index_estate", "estate_index", "catalog_digest"]

ESTATE_DIR = "estate"
ADJ, NODES, RECEIPT = "adj.parquet", "nodes.parquet", "receipt.json"
_ADJ_COLS = {"name": "VARCHAR", "corpus": "VARCHAR", "src": "VARCHAR", "dst": "VARCHAR", "edge_type": "VARCHAR",
             "dst_repr": "VARCHAR", "line": "BIGINT"}
_NODE_COLS = {"name": "VARCHAR", "corpus": "VARCHAR", "id": "VARCHAR", "kind": "VARCHAR", "node_type": "VARCHAR",
              "dotted": "VARCHAR", "module": "VARCHAR", "role": "VARCHAR", "file": "VARCHAR", "line": "BIGINT",
              "version": "VARCHAR"}


def catalog_digest(index: Path) -> str:
    p = Path(index) / "catalog.json"
    if not p.is_file():
        raise ContainerError(f"no catalog.json at {index} — not an index")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _shard_dirs(index: Path) -> list[tuple[str, Path]]:
    cat = index_catalog(str(index))
    return [(name, index / "shards" / addr) for name, addr in sorted(cat.items())]


def _load(index: Path, out: Path, con) -> dict:
    adj_feed = out / f".adj.{os.getpid()}.jsonl"
    node_feed = out / f".nodes.{os.getpid()}.jsonl"
    n_edges = n_nodes = 0
    shards = _shard_dirs(index)
    with adj_feed.open("w", encoding="utf-8") as fa, node_feed.open("w", encoding="utf-8") as fn:
        for name, d in shards:
            try:
                prov = json.loads((d / "PROVENANCE.json").read_text(encoding="utf-8"))
                nodes = json.loads((d / "nodes.json").read_text(encoding="utf-8"))
                edges = json.loads((d / "edges.json").read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ContainerError(f"{name}: shard unreadable at {d} ({exc})") from exc
            corpus = str((prov.get("corpus") or {}).get("scheme") or name.split("==")[0])
            version = (prov.get("corpus") or {}).get("version")
            recs = nodes.values() if isinstance(nodes, dict) else nodes
            for rec in recs:
                nid = rec.get("id")
                if not nid:
                    continue
                _body, _last, kind = node_forms(nid)
                fn.write(json.dumps({"name": name, "corpus": corpus, "id": nid, "kind": kind,
                                     "node_type": rec.get("node_type"), "dotted": rec.get("dotted"),
                                     "module": rec.get("module"), "role": rec.get("role"), "file": rec.get("file"),
                                     "line": rec.get("line") if isinstance(rec.get("line"), int) else None,
                                     "version": version}, ensure_ascii=False) + "\n")
                n_nodes += 1
            for e in edges:
                fa.write(json.dumps({"name": name, "corpus": corpus, "src": e.get("src"), "dst": e.get("dst"),
                                     "edge_type": e.get("edge_type"),
                                     "dst_repr": e.get("dst_repr") if isinstance(e.get("dst_repr"), str) else None,
                                     "line": e.get("line") if isinstance(e.get("line"), int) else None},
                                    ensure_ascii=False) + "\n")
                n_edges += 1
    try:
        for feed, cols, table, target in ((adj_feed, _ADJ_COLS, "adj_t", out / ADJ), (node_feed, _NODE_COLS, "nodes_t", out / NODES)):
            spec = ", ".join(f"'{k}': '{v}'" for k, v in cols.items())
            tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
            con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_json('{feed.as_posix()}', format='newline_delimited', columns={{{spec}}})")
            con.execute(f"COPY {table} TO '{tmp.as_posix()}' (FORMAT PARQUET)")
            os.replace(tmp, target)
            con.execute(f"DROP TABLE {table}")
    finally:
        for f in (adj_feed, node_feed):
            if f.exists():
                f.unlink()
    return {"shards": len(shards), "nodes": n_nodes, "edges": n_edges}


def emit_index(index: str | Path) -> dict:
    duckdb = _duckdb()
    index = Path(index)
    out = index / ESTATE_DIR
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    con = duckdb.connect()
    try:
        counts = _load(index, out, con)
    finally:
        con.close()
    receipt = {"catalog_sha256": catalog_digest(index), "index": str(index), **counts,
               "seconds": round(time.perf_counter() - t0, 1), "files": [ADJ, NODES]}
    (out / RECEIPT).write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def verify_index_estate(index: str | Path) -> tuple[str, dict | None]:
    """``fresh`` when the receipt pins the catalog as it stands; ``stale`` when the catalog moved;
    ``absent`` when nothing was emitted."""
    index = Path(index)
    out = index / ESTATE_DIR
    if not all((out / f).is_file() for f in (ADJ, NODES, RECEIPT)):
        return "absent", None
    try:
        receipt = json.loads((out / RECEIPT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "stale", None
    return ("fresh" if receipt.get("catalog_sha256") == catalog_digest(index) else "stale"), receipt


def estate_index(index: str | Path):
    """A duckdb connection with ``adj`` and ``nodes`` over the whole index. Refuses a stale or
    absent estate by name — a view over yesterday's catalog would lie about today's."""
    duckdb = _duckdb()
    index = Path(index)
    state, receipt = verify_index_estate(index)
    if state != "fresh":
        raise ContainerError(f"the index estate at {index / ESTATE_DIR} is {state.upper()}"
                             + (" — the catalog moved since it was emitted" if state == "stale" else "")
                             + "; run graphy estate --index … --emit")
    con = duckdb.connect()
    con.execute(f"CREATE VIEW adj AS SELECT * FROM read_parquet('{(index / ESTATE_DIR / ADJ).as_posix()}')")
    con.execute(f"CREATE VIEW nodes AS SELECT * FROM read_parquet('{(index / ESTATE_DIR / NODES).as_posix()}')")
    return con, receipt
