from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from graphy._portable_flock import fcntl as _flock
from graphy.tenant import Tenant, TenantError, cli_tenant

_GRAPH_DIR_NAME = re.compile(r"^[a-z0-9_]+_graph$")

NODE_CAP = 5000
EDGE_CAP = 2000


class TornJournalError(ValueError):
    pass


def _require_tenant(tenant: Tenant | None, who: str) -> Tenant:
    if tenant is None:
        raise ValueError(
            f"{who}: tenant is required — graphy resolves identity only through a "
            f"declared Tenant; absent tenant = refuse")
    return tenant


def _journal_root(tenant: Tenant) -> Path:
    return Path(tenant.journal)


def _contained(path: Path, tenant: Tenant, what: str) -> Path:
    root = _journal_root(tenant).resolve()
    resolved = path.resolve()
    if resolved.parent != root:
        raise ValueError(
            f"{what}: {path} resolves to {resolved}, escaping the tenant journal home "
            f"{root} — refuse")
    return path


def _manifest_path(tenant: Tenant) -> Path:
    return _contained(_journal_root(tenant) / "manifest.json", tenant, "manifest")


def _loss_log(tenant: Tenant) -> Path:
    return _contained(_journal_root(tenant) / "losses.jsonl", tenant, "loss log")


def _names(graph_name: str) -> tuple[str, str]:
    name = str(graph_name).strip().strip("/")
    base = name if name.endswith("_graph") else f"{name}_graph"
    return base, base[: -len("_graph")]


def journal_path(graph_name: str, tenant: Tenant | None = None) -> Path:
    tenant = _require_tenant(tenant, "journal_path")
    base, _ = _names(graph_name)
    if not _GRAPH_DIR_NAME.match(base):
        raise ValueError(
            f"journal_path: {graph_name!r} does not normalize to a valid graph name "
            f"({base!r} fails ^[a-z0-9_]+_graph$) — refusing a journal path outside the grammar")
    return _contained(_journal_root(tenant) / f"{base}.journal.jsonl", tenant, "journal_path")


def _location_ok(graph_dir: Path, tenant: Tenant) -> bool:
    p = Path(graph_dir)
    dh = Path(tenant.data_home).resolve()
    resolved: Path | None = None
    try:
        resolved = p.resolve()
    except OSError as exc:
        print(f"[graphy.journal] resolve unavailable for {p}: {exc!r} — "
              f"checking the unresolved path only", file=sys.stderr)
    candidates = [p] + ([resolved] if resolved is not None else [])
    return any(c == dh or c.is_relative_to(dh) for c in candidates)


def eligible_dir(graph_dir: Path, tenant: Tenant | None = None) -> bool:
    tenant = _require_tenant(tenant, "eligible_dir")
    p = Path(graph_dir)
    return bool(_GRAPH_DIR_NAME.match(p.name)) and _location_ok(p, tenant)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _edge_key(e: dict) -> str:
    dst = e.get("dst")
    if dst is None:
        for alt in ("dst_repr", "name", "alias"):
            val = e.get(alt)
            if val is not None:
                dst = f"~{alt}:{val}"
                break
    return json.dumps([e.get("src"), e.get("edge_type"), dst])


def _read_ids(graph_dir: Path) -> tuple[set[str], set[str]]:
    gd = Path(graph_dir)
    edges_file = gd / "edges.json"
    if edges_file.exists():
        from graphy.native_json_graph_ir import raw_shard   # the one parse per shard per process
        raw = raw_shard(gd)
        nodes_raw, edges_raw = raw["nodes"], raw["edges"]
    else:
        nodes_raw = json.loads((gd / "nodes.json").read_text(encoding="utf-8"))
        edges_raw = None
    if isinstance(nodes_raw, dict):
        node_ids = set(nodes_raw.keys())
    else:
        node_ids = {n["id"] for n in nodes_raw}
    edge_keys: set[str] = set()
    if edges_raw is not None:
        edge_keys = {_edge_key(e) for e in edges_raw}
    return node_ids, edge_keys


def snapshot_ids(graph_dir: Path) -> dict[str, Any] | None:
    gd = Path(graph_dir)
    try:
        if not (gd / "nodes.json").exists():
            return {"nodes": set(), "edges": set(), "absent": True, "cursor": None}
        nodes, edges = _read_ids(gd)
        cursor, _ = _cursor_from(gd)
        return {"nodes": nodes, "edges": edges, "absent": False, "cursor": cursor}
    except Exception as exc:
        print(f"[graphy.journal] snapshot unreadable for {gd}: {exc!r}", file=sys.stderr)
        return None


def _norm_cursor(cursor: str | None) -> str | None:
    if cursor and re.fullmatch(r"[0-9a-f]{8,40}", cursor):
        return cursor[:8]
    return cursor


def _cursor_from(graph_dir: Path) -> tuple[str | None, bool | None]:
    try:
        stats = json.loads((Path(graph_dir) / "stats.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None
    except Exception as exc:
        print(f"[graphy.journal] stats unreadable for {graph_dir}: {exc!r}", file=sys.stderr)
        return None, None
    cursor = stats.get("published_head") or stats.get("built_at_sha")
    worktree = stats.get("worktree")
    dirty = None if worktree is None else (worktree == "dirty")
    return _norm_cursor(cursor), dirty


def _bounded(ids: set[str], cap: int) -> tuple[list[str], bool]:
    orderly = sorted(ids)
    if len(orderly) <= cap:
        return orderly, False
    return orderly[:cap], True


def _tail_state(content: str) -> tuple[str | None, int]:
    head_cursor: str | None = None
    head_seq = 0
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            print("[graphy.journal] torn line under the append lock — "
                  "the read path refuses this journal until acknowledged", file=sys.stderr)
            continue
        if rec.get("kind") == "page":
            head_cursor = rec.get("cursor")
            seq = rec.get("seq")
            head_seq = int(seq) if isinstance(seq, int) else head_seq + 1
    return head_cursor, head_seq


def append_page(
    graph_name: str,
    old_node_ids: set[str],
    new_node_ids: set[str],
    old_edge_keys: set[str] | None = None,
    new_edge_keys: set[str] | None = None,
    cursor: str | None = None,
    prev_cursor: str | None = None,
    dirty: bool | None = None,
    bootstrap: bool = False,
    ts: str | None = None,
    tenant: Tenant | None = None,
) -> dict[str, Any]:
    tenant = _require_tenant(tenant, "append_page")
    base, slug = _names(graph_name)
    old_edge_keys = old_edge_keys or set()
    new_edge_keys = new_edge_keys or set()

    born, born_trunc = _bounded(new_node_ids - old_node_ids, NODE_CAP)
    died, died_trunc = _bounded(old_node_ids - new_node_ids, NODE_CAP)
    eborn, eborn_trunc = _bounded(new_edge_keys - old_edge_keys, EDGE_CAP)
    edied, edied_trunc = _bounded(old_edge_keys - new_edge_keys, EDGE_CAP)

    page: dict[str, Any] = {
        "kind": "page",
        "ts": ts or _now_iso(),
        "graph": slug,
        "cursor": _norm_cursor(cursor),
        "prev_cursor": _norm_cursor(prev_cursor),
        "n_born": len(new_node_ids - old_node_ids),
        "n_died": len(old_node_ids - new_node_ids),
        "n_eborn": len(new_edge_keys - old_edge_keys),
        "n_edied": len(old_edge_keys - new_edge_keys),
    }
    if dirty is not None:
        page["dirty"] = dirty
    if bootstrap:
        page["bootstrap"] = True
    else:
        if page["n_born"]:
            page["born"] = born
        if page["n_died"]:
            page["died"] = died
        if page["n_eborn"]:
            page["eborn"] = [json.loads(k) for k in eborn]
        if page["n_edied"]:
            page["edied"] = [json.loads(k) for k in edied]
        if born_trunc or died_trunc or eborn_trunc or edied_trunc:
            page["truncated"] = True

    jpath = journal_path(base, tenant)
    jpath.parent.mkdir(parents=True, exist_ok=True)
    with open(jpath, "a+", encoding="utf-8") as fh:
        _flock.flock(fh.fileno(), _flock.LOCK_EX)
        try:
            fh.seek(0)
            content = fh.read()
            fresh = not content.strip()
            head_cursor, head_seq = _tail_state(content)
            page["seq"] = head_seq + 1
            if not fresh and _norm_cursor(prev_cursor) != _norm_cursor(head_cursor):
                page["gap_after_seq"] = head_seq
            lines: list[str] = []
            if fresh:
                lines.append(json.dumps({
                    "kind": "journal",
                    "uuid": str(_uuid.uuid4()),
                    "graph": slug,
                    "file": jpath.name,
                    "opened_ts": page["ts"],
                }))
            lines.append(json.dumps(page, sort_keys=True))
            fh.seek(0, os.SEEK_END)
            fh.write("\n".join(lines) + "\n")
            fh.flush()
        finally:
            _flock.flock(fh.fileno(), _flock.LOCK_UN)
    return page


def _lose(graph_name: str, seam: str, why: str, tenant: Tenant | None = None, loud: bool = True) -> None:
    if loud:
        print(f"[graphy.journal] PAGE LOST ({graph_name} · {seam}): {why} — publish unaffected",
              file=sys.stderr)
    if tenant is None:
        return
    try:
        log = _loss_log(tenant)
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": _now_iso(), "graph": str(graph_name), "seam": seam, "why": why}) + "\n")
    except Exception as exc:
        print(f"[graphy.journal] loss-log write failed ({exc!r}) — the loud line above stands",
              file=sys.stderr)


def observe_publish(
    graph_name: str,
    old_snap: dict[str, Any] | None,
    new_dir: Path,
    cursor: str | None = None,
    seam: str = "publish",
    tenant: Tenant | None = None,
) -> dict[str, Any] | None:
    if tenant is None:
        print(f"[graphy.journal] PAGE LOST ({graph_name} · {seam}): tenant is required — "
              f"absent tenant = refuse; publish unaffected", file=sys.stderr)
        return None
    try:
        nd = Path(new_dir)
        base, _ = _names(graph_name)
        if not (_GRAPH_DIR_NAME.match(base) and _location_ok(nd, tenant)):
            print(f"[graphy.journal] skip {graph_name} @ {nd} (off-shelf dir or bad name) — no page",
                  file=sys.stderr)
            return None
        if old_snap is None:
            _lose(graph_name, seam, "old surface existed but was unreadable — a diff would lie", tenant)
            return None
        new_snap = snapshot_ids(nd)
        if new_snap is None or new_snap.get("absent"):
            _lose(graph_name, seam, f"published dir unreadable: {nd}", tenant)
            return None
        c, dirty = (cursor, None) if cursor else _cursor_from(nd)
        return append_page(
            graph_name,
            old_snap["nodes"], new_snap["nodes"],
            old_snap["edges"], new_snap["edges"],
            cursor=c, prev_cursor=old_snap.get("cursor"),
            dirty=dirty, bootstrap=bool(old_snap.get("absent")),
            tenant=tenant,
        )
    except Exception as exc:
        print(f"[graphy.journal] PAGE LOST ({graph_name} · {seam}): {exc!r} — publish unaffected",
              file=sys.stderr)
        _lose(graph_name, seam, repr(exc), tenant, loud=False)
        return None


def inplace_observer(out_dir: Path, tenant: Tenant | None = None) -> Callable[[dict, dict], dict | None] | None:
    if tenant is None:
        print(f"[graphy.journal] PAGE LOST ({out_dir} · inplace): tenant is required — "
              f"absent tenant = refuse; publish unaffected", file=sys.stderr)
        return None
    try:
        od = Path(out_dir)
        if not eligible_dir(od, tenant):
            return None
        if not (od / "nodes.json").exists():
            return None
        old_snap = snapshot_ids(od)

        def _page(graph: dict, stats: dict) -> dict | None:
            try:
                if old_snap is None:
                    _lose(od.name, "inplace", "old surface unreadable pre-overwrite", tenant)
                    return None
                new_nodes = set(graph["nodes"].keys()) if isinstance(graph["nodes"], dict) \
                    else {n["id"] for n in graph["nodes"]}
                new_edges = {_edge_key(e) for e in graph.get("edges", [])}
                return append_page(
                    od.name,
                    old_snap["nodes"], new_nodes,
                    old_snap["edges"], new_edges,
                    cursor=stats.get("built_at_sha"),
                    prev_cursor=old_snap.get("cursor"),
                    bootstrap=bool(old_snap.get("absent")),
                    tenant=tenant,
                )
            except Exception as exc:
                print(f"[graphy.journal] PAGE LOST ({od.name} · inplace): {exc!r} — publish unaffected",
                      file=sys.stderr)
                _lose(od.name, "inplace", repr(exc), tenant, loud=False)
                return None

        return _page
    except Exception as exc:
        print(f"[graphy.journal] PAGE LOST ({out_dir} · inplace): observer setup failed "
              f"({exc!r}) — publish unaffected", file=sys.stderr)
        _lose(str(out_dir), "inplace", f"observer setup failed: {exc!r}", tenant, loud=False)
        return None


def read_journal(graph_name: str, tenant: Tenant | None = None) -> tuple[dict | None, list[dict], int]:
    tenant = _require_tenant(tenant, "read_journal")
    jpath = journal_path(graph_name, tenant)
    header: dict | None = None
    pages: list[dict] = []
    skipped = 0
    if not jpath.exists():
        return None, [], 0
    for line in jpath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            print(f"[graphy.journal] torn line in {jpath.name} — counted, history answers "
                  f"refuse until acknowledged", file=sys.stderr)
            skipped += 1
            continue
        if rec.get("kind") == "journal" and header is None:
            header = rec
        elif rec.get("kind") == "page":
            pages.append(rec)
    return header, pages, skipped


def shelf_journals(tenant: Tenant | None = None) -> list[Path]:
    tenant = _require_tenant(tenant, "shelf_journals")
    return sorted(_journal_root(tenant).glob("*.journal.jsonl"))


def _page_matches(ids: list, needle: str, contains: bool) -> list[str]:
    out = []
    for i in ids:
        s = i if isinstance(i, str) else json.dumps(i)
        if (needle in s) if contains else (s == needle or s.endswith(needle)):
            out.append(s)
    return out


def find_events(
    field: str,
    needle: str,
    graph: str | None = None,
    contains: bool = False,
    tenant: Tenant | None = None,
    allow_torn: bool = False,
) -> list[dict]:
    tenant = _require_tenant(tenant, "find_events")
    hits: list[dict] = []
    paths = [journal_path(graph, tenant)] if graph else shelf_journals(tenant)
    for jp in paths:
        if not jp.exists():
            continue
        base = jp.name[: -len(".journal.jsonl")]
        _, pages, skipped = read_journal(base, tenant)
        if skipped:
            if not allow_torn:
                raise TornJournalError(
                    f"{jp.name}: {skipped} unparseable line(s) — damaged history cannot "
                    f"answer as if complete; pass allow_torn to answer anyway")
            print(f"[graphy.journal] WARNING {jp.name}: answering over a torn journal "
                  f"({skipped} unparseable line(s))", file=sys.stderr)
        for p in pages:
            matched = _page_matches(p.get(field, []), needle, contains)
            if matched:
                hits.append({"journal": jp.name, "ts": p.get("ts"), "cursor": p.get("cursor"),
                             "graph": p.get("graph"), "matched": matched})
    return hits


def find_graph_deaths(graph_name: str, tenant: Tenant | None = None, allow_torn: bool = False) -> list[dict]:
    tenant = _require_tenant(tenant, "find_graph_deaths")
    base, slug = _names(graph_name)
    header, pages, skipped = read_journal(base, tenant)
    if skipped:
        if not allow_torn:
            raise TornJournalError(
                f"{base}.journal.jsonl: {skipped} unparseable line(s) — damaged history "
                f"cannot answer as if complete; pass allow_torn to answer anyway")
        print(f"[graphy.journal] WARNING {base}.journal.jsonl: answering over a torn "
              f"journal ({skipped} unparseable line(s))", file=sys.stderr)
    if header is None or header.get("graph") != slug:
        return []

    live_nodes: int | None = None
    hits: list[dict] = []
    for page in pages:
        born = int(page.get("n_born", 0) or 0)
        died = int(page.get("n_died", 0) or 0)
        if page.get("bootstrap"):
            live_nodes = born
            continue
        if live_nodes is None:
            continue
        before = live_nodes
        live_nodes += born - died
        if live_nodes < 0:
            live_nodes = None
            continue
        if before > 0 and live_nodes == 0 and died:
            hits.append({
                "journal": journal_path(base, tenant).name,
                "ts": page.get("ts"),
                "cursor": page.get("cursor"),
                "graph": slug,
                "matched": [],
                "graph_death": True,
                "n_died": died,
                "n_edied": int(page.get("n_edied", 0) or 0),
            })
    return hits


def load_manifest(tenant: Tenant | None = None) -> dict:
    tenant = _require_tenant(tenant, "load_manifest")
    mpath = _manifest_path(tenant)
    if not mpath.exists():
        return {"_doc": "graphy.journal steward manifest — one row per journal (uuid·graph·file·opened). "
                        "A plain tenant-data file; adopt rows via `steward --adopt`; grandfather "
                        "deliberate exceptions by setting grandfathered:true.",
                "journals": []}
    return json.loads(mpath.read_text(encoding="utf-8"))


def _roster_slugs(tenant: Tenant) -> set[str]:
    slugs: set[str] = set()
    try:
        reg = json.loads(Path(tenant.join_keys).read_text(encoding="utf-8"))
        slugs |= set(reg.get("substrate_roster", {}).get("admitted", {}).keys())
        slugs |= set(reg.get("substrate_roster", {}).get("grandfathered", []))
    except Exception as exc:
        print(f"[graphy.journal] steward: roster unreadable ({exc!r})", file=sys.stderr)
    for key in tenant.build_lanes:
        slugs.add(_names(key)[1])
    return slugs


def steward(tenant: Tenant | None = None, adopt: bool = False) -> dict:
    tenant = _require_tenant(tenant, "steward")
    manifest = load_manifest(tenant)
    rows = {r.get("file"): r for r in manifest.get("journals", [])}
    admitted = _roster_slugs(tenant)
    report: dict[str, list] = {"healthy": [], "unregistered": [], "departed": [],
                               "absent_here": [], "headerless": [], "adopted": []}

    files_here = {jp.name: jp for jp in shelf_journals(tenant)}
    for fname, jp in files_here.items():
        base = fname[: -len(".journal.jsonl")]
        header, _, skipped = read_journal(base, tenant)
        if header is None:
            report["headerless"].append({"file": fname, "skipped_lines": skipped})
            continue
        row = rows.get(fname)
        if row is None:
            entry = {"uuid": header.get("uuid"), "graph": header.get("graph"),
                     "file": fname, "opened": header.get("opened_ts")}
            if adopt:
                manifest["journals"].append(entry)
                rows[fname] = entry
                report["adopted"].append(entry)
            else:
                report["unregistered"].append(entry)

    for fname, row in rows.items():
        slug = row.get("graph", "")
        here = fname in files_here
        if slug not in admitted and not row.get("grandfathered"):
            report["departed"].append(row)
        elif not here:
            report["absent_here"].append(row)
        elif row not in report["adopted"]:
            report["healthy"].append(row)

    if adopt and report["adopted"]:
        mpath = _manifest_path(tenant)
        mpath.parent.mkdir(parents=True, exist_ok=True)
        mpath.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return report


_cli_tenant = cli_tenant


def _cmd_diff_append(args: argparse.Namespace, tenant: Tenant) -> int:
    old = (args.old or "").strip()
    if old:
        old_snap = snapshot_ids(Path(old))
        if old_snap is not None and old_snap.get("absent"):
            _lose(args.graph, "diff-append",
                  f"named --old {old!r} has no readable nodes.json — refusing to fabricate a bootstrap",
                  tenant)
            return 1
    else:
        old_snap = {"nodes": set(), "edges": set(), "absent": True, "cursor": None}
    page = observe_publish(args.graph, old_snap, Path(args.new), cursor=args.cursor,
                           seam="diff-append", tenant=tenant)
    if page is None:
        return 1
    print(f"[graphy.journal] {args.graph} paged: +{page['n_born']}n/-{page['n_died']}n "
          f"+{page['n_eborn']}e/-{page['n_edied']}e seq={page.get('seq')} cursor={page.get('cursor')}"
          + (" (bootstrap)" if page.get("bootstrap") else "")
          + (f" GAP after seq {page['gap_after_seq']}" if "gap_after_seq" in page else ""))
    return 0


def _cmd_log(args: argparse.Namespace, tenant: Tenant) -> int:
    header, pages, skipped = read_journal(args.graph, tenant)
    if header is None and not pages:
        print(f"(no journal for {args.graph} at {journal_path(args.graph, tenant)})")
        return 1
    if args.since:
        pages = pages[-args.since:]
    if args.json:
        print(json.dumps({"header": header, "pages": pages, "skipped_lines": skipped}, indent=2))
        return 0
    if header:
        print(f"journal {header.get('file')} · uuid {header.get('uuid')} · opened {header.get('opened_ts')}")
    for p in pages:
        flags = "".join([" BOOTSTRAP" if p.get("bootstrap") else "",
                         " TRUNCATED" if p.get("truncated") else "",
                         " dirty" if p.get("dirty") else "",
                         f" GAP>{p['gap_after_seq']}" if "gap_after_seq" in p else ""])
        print(f"  {p.get('ts')}  seq={p.get('seq')}  cursor={p.get('cursor')}  "
              f"+{p.get('n_born',0)}n/-{p.get('n_died',0)}n +{p.get('n_eborn',0)}e/-{p.get('n_edied',0)}e{flags}")
        for field, mark in (("born", "+"), ("died", "-")):
            for nid in p.get(field, [])[:10]:
                print(f"      {mark} {nid}")
            extra = len(p.get(field, [])) - 10
            if extra > 0:
                print(f"      … {extra} more {field}")
    if skipped:
        print(f"  ⚠ {skipped} unparseable line(s) skipped (torn append?)", file=sys.stderr)
    return 0


def _cmd_event(field: str, args: argparse.Namespace, tenant: Tenant) -> int:
    try:
        hits = find_events(field, args.needle, graph=args.graph, contains=args.contains,
                           tenant=tenant, allow_torn=args.allow_torn)
        if not hits and field == "died" and args.graph is None and not args.contains:
            hits = find_graph_deaths(args.needle, tenant, allow_torn=args.allow_torn)
    except TornJournalError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(hits, indent=2))
        return 0 if hits else 1
    if not hits:
        scope = args.graph or "any journal"
        print(f"(no {field} event for {args.needle!r} in {scope} — pre-journal history is unknowable, "
              f"the journal starts at each header's opened_ts)")
        return 1
    for h in hits:
        if h.get("graph_death"):
            print(f"{h['ts']}  {h['graph']}  cursor={h['cursor']}  "
                  f"died graph: {h['graph']} (-{h['n_died']}n/-{h['n_edied']}e)")
            continue
        for m in h["matched"]:
            print(f"{h['ts']}  {h['graph']}  cursor={h['cursor']}  {field}: {m}")
    return 0


def _cmd_steward(args: argparse.Namespace, tenant: Tenant) -> int:
    report = steward(tenant, adopt=args.adopt)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for state in ("adopted", "unregistered", "departed", "headerless", "absent_here"):
            for row in report[state]:
                print(f"{state.upper():13s} {row.get('file', row)}"
                      + (f"  (graph={row.get('graph')})" if isinstance(row, dict) else ""))
        print(f"steward: {len(report['healthy'])} healthy · {len(report['unregistered'])} unregistered"
              f" · {len(report['departed'])} DEPARTED · {len(report['headerless'])} headerless"
              f" · {len(report['absent_here'])} absent-here"
              + (f" · {len(report['adopted'])} adopted" if args.adopt else ""))
    return 2 if (report["departed"] or report["headerless"]) else 0


def _cmd_losses(args: argparse.Namespace, tenant: Tenant) -> int:
    log = _loss_log(tenant)
    if not log.exists():
        print("(no losses recorded)")
        return 0
    lines = log.read_text(encoding="utf-8").splitlines()
    print(f"{len(lines)} lost page(s) recorded at {log}")
    for line in lines[-args.tail:]:
        print(f"  {line}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="graphy.journal",
        description="graph journal — append-only publish history, tenant-declared",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tenant-id", required=True,
                    help="the receipt-name of the declared identity — graphy resolves "
                         "identity only through a declared Tenant.")
    ap.add_argument("--data-home", required=True,
                    help="the tenant data_home holding the `<slug>_graph` directories; "
                         "the journal home is data_home/.journal (the constructor idiom).")
    ap.add_argument("--join-keys", required=True,
                    help="path to the tenant's substrate_override_registry.json.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    da = sub.add_parser("diff-append", help="diff old vs new graph dirs, append one page")
    da.add_argument("--graph", required=True)
    da.add_argument("--old", default="", help="outgoing dir ('' = bootstrap, no prior surface)")
    da.add_argument("--new", required=True, help="the published dir")
    da.add_argument("--cursor", default=None, help="override (default: new dir's stats.json sha)")

    lg = sub.add_parser("log", help="print a graph's pages")
    lg.add_argument("graph")
    lg.add_argument("--since", type=int, default=0, help="last N pages only")
    lg.add_argument("--json", action="store_true")

    for field in ("born", "died"):
        ev = sub.add_parser(field, help=f"find {field} events for a node id")
        ev.add_argument("needle", help="node id (exact or suffix)")
        ev.add_argument("--graph", default=None)
        ev.add_argument("--contains", action="store_true", help="substring match")
        ev.add_argument("--allow-torn", action="store_true",
                        help="answer over a torn journal (loud warning) instead of refusing")
        ev.add_argument("--json", action="store_true")

    st = sub.add_parser("steward", help="manifest↔shelf↔roster sweep (on-demand, never a hook)")
    st.add_argument("--adopt", action="store_true", help="register unregistered journals into the manifest")
    st.add_argument("--lane", action="append", default=[], metavar="KEY:KIND",
                    help="declare a build-lane membership key (repeatable); KIND must be a "
                         "kind the Tenant contract admits — the real constructor validates it")
    st.add_argument("--json", action="store_true")

    ls = sub.add_parser("losses", help="show the lost-page log")
    ls.add_argument("--tail", type=int, default=10)

    args = ap.parse_args(argv)
    lanes = tuple(args.lane) if getattr(args, "lane", None) else ()
    try:
        tenant = _cli_tenant(args.data_home, args.join_keys, args.tenant_id, lanes)
    except TenantError as exc:
        print(f"JOURNAL REFUSED: {exc}", file=sys.stderr)
        return 2

    if args.cmd == "diff-append":
        return _cmd_diff_append(args, tenant)
    if args.cmd == "log":
        return _cmd_log(args, tenant)
    if args.cmd in ("born", "died"):
        return _cmd_event(args.cmd, args, tenant)
    if args.cmd == "steward":
        return _cmd_steward(args, tenant)
    if args.cmd == "losses":
        return _cmd_losses(args, tenant)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
