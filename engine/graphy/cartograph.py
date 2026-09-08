
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from graphy.tenant import Tenant

_NT_STALE_REFUSE_COMMITS = 100


def repo_head_sha(repo_root: Path | None = None) -> str | None:
    if repo_root is None:
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def working_tree_dirt(repo_root: Path, exclude: Iterable[Path] = ()) -> tuple[list[str], bytes] | None:
    """What the working tree holds past HEAD: the paths ``git status --porcelain -uall`` names (every
    untracked file spelled out, nothing under an ``exclude`` root — the data home the eat writes),
    and the bytes that identify them — the status line, then each named file's bytes, so a second
    edit to an already-modified file moves the digest. ``None`` when the status cannot be read."""
    try:
        out = subprocess.run(["git", "-C", str(repo_root), "status", "--porcelain", "-uall", "-z"],
                             capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    roots = [Path(e).resolve() for e in exclude]
    try:                                        # porcelain paths are relative to the repository's top level
        top = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if top.returncode != 0 or not top.stdout.strip():
        return None
    root = Path(top.stdout.strip()).resolve()
    paths: list[str] = []
    fields = out.stdout.split(b"\0")
    i = 0
    while i < len(fields):
        line = fields[i]
        i += 1
        if len(line) < 4:
            continue
        code, rel = line[:2], line[3:]
        if code[:1] in b"RC":                   # a rename carries its origin as the next field
            i += 1
        rel_s = rel.decode("utf-8", "surrogateescape")
        full = root / rel_s
        if any(r == full or r in full.parents for r in roots):
            continue
        paths.append(rel_s)
    h = hashlib.sha256()
    for rel_s in paths:
        h.update(rel_s.encode("utf-8", "surrogateescape") + b"\0")
        full = root / rel_s
        try:
            if full.is_file() and not full.is_symlink():
                h.update(full.read_bytes())
        except OSError:
            h.update(b"?")
        h.update(b"\0")
    return paths, h.digest()


def repo_cursor(repo_root: Path | None, exclude: Iterable[Path] = ()) -> tuple[str | None, int]:
    """The tenant cursor for a repo: ``git:<head>`` when the tree is clean, ``git:<head>+<digest>``
    when it is dirty — the digest over the working tree's dirt (graphyos #39), so a store built from
    uncommitted edits is named stale the moment they move, and a clean tree's cursor is unchanged.
    Returns ``(cursor, dirty file count)``; ``(None, 0)`` when the repo has no readable HEAD."""
    head = repo_head_sha(repo_root)
    if head is None:
        return None, 0
    dirt = working_tree_dirt(Path(repo_root), exclude)
    if not dirt or not dirt[0]:
        return f"git:{head}", 0
    paths, digest = dirt
    return f"git:{head}+{digest.hex()[:16]}", len(paths)


def tenant_exclude(descriptor: Path, tenant: Tenant) -> tuple[Path, ...]:
    """What the cursor never counts as dirt: the tenant's own products — its data home, journal,
    join keys, the descriptor, and the home the eat wrote when the data home sits inside it."""
    home = Path(descriptor).resolve().parent
    data_home = Path(tenant.data_home).resolve()
    out = [data_home, Path(tenant.journal), Path(tenant.join_keys), Path(descriptor)]
    if home == data_home.parent:
        out.append(home)
    return tuple(out)


def cursor_drift(cursor: str, repo_root: Path, exclude: Iterable[Path] = ()) -> str | None:
    """Has the repo moved past a ``git:`` cursor? ``None`` when it holds (or the cursor is not a git
    one); otherwise the reason — the working tree's dirt or the HEAD itself. A HEAD spelled short by
    one writer and long by another is the same HEAD."""
    if not cursor.startswith("git:"):
        return None
    built_head, _, built_dirt = cursor[4:].partition("+")
    live, count = repo_cursor(repo_root, exclude)
    if live is None:
        return "the repo's HEAD is unreadable (git unavailable or broken on this box?) — freshness is unmeasurable"
    live_head, _, live_dirt = live[4:].partition("+")
    if not (live_head.startswith(built_head) or built_head.startswith(live_head)):
        return f"HEAD moved past the store: built at {built_head}, HEAD is {live_head}"
    if live_dirt != built_dirt:
        if count:
            return f"the working tree moved past the store: {count} file(s) modified or untracked since the build"
        return "the working tree moved past the store: the edits it was built from are gone (the tree is clean)"
    return None


def _behind_commits(repo_root: Path, built: str, head: str) -> int | None:
    try:
        r = subprocess.run(["git", "rev-list", "--count", f"{built}..HEAD"],
                           capture_output=True, text=True, cwd=str(repo_root), timeout=10)
        out = r.stdout.strip()
        return int(out) if r.returncode == 0 and out.isdigit() else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def resolve_graph(graph_dir: Path) -> Path:
    p = Path(graph_dir)
    if p.is_symlink():
        try:
            target = os.readlink(p)
        except OSError:
            target = ""
        if target:
            resolved = (p.parent / target).resolve()
            escapes = p.parent.resolve() not in resolved.parents
            if escapes and p.exists():
                return p
    for _ in range(5):
        try:
            return p.resolve(strict=True)
        except (FileNotFoundError, OSError):
            time.sleep(0.05)
    return p.resolve()


def _shell_quote_out(p: Path) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline([str(p)])
    return shlex.quote(str(p))


def _build(graph_dir: Path, command: str, repo_root: Path, *, reason: str) -> None:
    resolved = command.replace("{out}", _shell_quote_out(graph_dir))
    print(f"[walk] {graph_dir.name} {reason} — running declared build lane: {resolved}", file=sys.stderr)
    rc = subprocess.run(
        resolved, shell=True, cwd=str(repo_root), check=False,
        env={**os.environ, "MEM_NO_AUTOREBUILD": "1"},
    ).returncode
    if rc != 0:
        raise RuntimeError(
            f"ensure_fresh: {graph_dir.name} build lane {command!r} failed (rc={rc}); "
            f"refusing to walk a stale/half-built graph")


def code_graph_publish_inplace(graph_key: str, live_dir: Path, *, tenant: Tenant | None = None) -> None:
    if tenant is None:
        raise ValueError("code_graph_publish_inplace: tenant is required — graphy resolves identity "
                         "only through a declared Tenant; absent tenant = refuse")
    lane = tenant.build_lanes.get(graph_key)
    if lane is None or lane[0] is None:
        raise RuntimeError(
            f"code_graph_publish_inplace: {graph_key} has no declared build lane — refusing to publish "
            f"(never an invented command)")
    command = lane[0]
    if "{out}" not in command:
        raise RuntimeError(
            f"code_graph_publish_inplace: {graph_key}'s declared lane command has no {{out}} "
            f"placeholder — the atomic publish builds into a sibling temp dir and the command "
            f"must accept that output route; without it the swap consumes a dir nothing created. "
            f"Declare the command with {{out}} where its output directory belongs.")
    from graphy._portable_flock import fcntl as _flock
    live = Path(live_dir)
    parent = live.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / f".{live.name}.build.{os.getpid()}"
    old = parent / f".{live.name}.old.{os.getpid()}"
    lockfile = parent / f".{live.name}.lock"
    with open(lockfile, "w", encoding="utf-8") as lf:
        _flock.flock(lf.fileno(), _flock.LOCK_EX)
        try:
            if tmp.exists():
                shutil.rmtree(tmp)
            _build(tmp, command, Path(tenant.root), reason="publish-inplace build (declared lane)")
            try:
                from graphy import journal as _journal
                _old_snap = _journal.snapshot_ids(live) if live.exists() \
                    else {"nodes": set(), "edges": set(), "absent": True, "cursor": None}
            except Exception as _exc:
                print(f"[journal-observer] pre-snapshot lost ({_exc!r}) — publish unaffected",
                      file=sys.stderr)
                _journal = None
                _old_snap = None
            moved_aside = False
            if live.exists() or live.is_symlink():
                os.replace(live, old)
                moved_aside = True
            try:
                os.replace(tmp, live)
            except BaseException:
                if moved_aside:
                    os.replace(old, live)
                raise
            if moved_aside:
                shutil.rmtree(old, ignore_errors=True)
            try:
                from graphy.mesh_federation_gate import observe as _fed_observe
                _member = graph_key[: -len("_graph")] if graph_key.endswith("_graph") else graph_key
                _fed_observe(_member, tenant)
            except Exception as _exc:
                print(f"[federation-observer] publish_inplace refresh lost ({_exc!r}) — publish unaffected",
                      file=sys.stderr)
            try:
                if _journal is not None:
                    _journal.observe_publish(live.name, _old_snap, live,
                                             seam="publish_inplace", tenant=tenant)
            except Exception as _exc:
                print(f"[journal-observer] publish page lost ({_exc!r}) — publish unaffected",
                      file=sys.stderr)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        finally:
            _flock.flock(lf.fileno(), _flock.LOCK_UN)


def ensure_fresh(graph_dir: Path, tenant: Tenant | None = None) -> None:
    if tenant is None:
        raise ValueError("ensure_fresh: tenant is required — graphy resolves identity only through a "
                         "declared Tenant; absent tenant = refuse")
    if os.environ.get("MEM_NO_AUTOREBUILD"):
        return
    lane = tenant.build_lanes.get(graph_dir.name)
    command = lane[0] if lane is not None else None

    stats_path = graph_dir / "stats.json"
    built = None
    if stats_path.exists():
        try:
            built = json.loads(stats_path.read_text(encoding="utf-8")).get("built_at_sha")
        except (OSError, json.JSONDecodeError):
            raise RuntimeError(
                f"ensure_fresh: {graph_dir.name} stats.json is unreadable at {stats_path} — refusing "
                f"to walk; the graph's freshness is unknowable")
    if built is None:
        if not stats_path.exists() and command is not None:
            _build(graph_dir, command, Path(tenant.root), reason="absent (gitignored — fresh box)")
            return
        raise RuntimeError(
            f"ensure_fresh: {graph_dir.name} is ABSENT or its cursor is unreadable — refusing to walk "
            f"(unmeasurable freshness; no declared build lane to bootstrap it)")

    head = repo_head_sha(Path(tenant.root))
    if head is not None and built == head:
        return
    if head is None:
        raise RuntimeError(
            f"ensure_fresh: {graph_dir.name} freshness is UNMEASURABLE — repo HEAD unreadable "
            f"(git unavailable/broken on this box?); walking could answer from a lie")

    if command is not None:
        _build(graph_dir, command, Path(tenant.root), reason=f"stale (built {built}, HEAD {head})")
        return
    behind = _behind_commits(Path(tenant.root), built, head)
    if behind is not None and behind <= _NT_STALE_REFUSE_COMMITS:
        print(f"[walk] ⚠ STALE GRAPH — {graph_dir.name} is {behind} commit(s) behind HEAD "
              f"(built {built}, HEAD {head}); no declared build lane — walking the AGING snapshot "
              f"anyway. Declare a build_lanes entry to rebuild instead.", file=sys.stderr)
        return
    detail = (f"{behind} commits behind HEAD" if behind is not None
              else f"cursor {built} unknown to local git (unmeasurable drift)")
    raise RuntimeError(
        f"ensure_fresh: {graph_dir.name} is GROSSLY stale — {detail}; walking it would answer from a "
        f"lie. Declare a build lane for {graph_dir.name} or rebuild it on demand.")


def cartograph(records: Iterable[dict]) -> dict[str, Any]:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    stat_counts: dict[str, int] = {}
    for rec in records:
        k = rec.get("kind")
        if k == "node":
            nodes[rec["id"]] = rec
        elif k == "edge":
            edges.append(rec)
        elif k == "stat":
            st = str(rec.get("stat_type", "unlabeled_stat"))
            stat_counts[st] = stat_counts.get(st, 0) + 1

    clusters: dict[str, list[str]] = collections.defaultdict(list)
    for nid, node in nodes.items():
        dotted = node.get("dotted", "")
        parts = dotted.split(".")
        cluster = ".".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else "(unknown)")
        clusters[cluster].append(nid)

    outgoing: dict[str, list[dict]] = collections.defaultdict(list)
    incoming: dict[str, list[dict]] = collections.defaultdict(list)
    for edge in edges:
        if "src" in edge:
            outgoing[edge["src"]].append(edge)
        if "dst" in edge:
            incoming[edge["dst"]].append(edge)

    return {
        "nodes": nodes,
        "edges": edges,
        "clusters": dict(clusters),
        "adjacency": {"outgoing": dict(outgoing), "incoming": dict(incoming)},
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "cluster_count": len(clusters),
            "node_types": dict(collections.Counter(n["node_type"] for n in nodes.values())),
            "edge_types": dict(collections.Counter(e["edge_type"] for e in edges)),
            **({"counters": dict(sorted(stat_counts.items()))} if stat_counts else {}),
        },
    }


def write_graph(graph: dict[str, Any], out_dir: Path, *, repo_root: Path | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = dict(graph["stats"])
    stats["built_at_sha"] = repo_head_sha(repo_root)
    # the records the machine reads are compact; stats.json is the one a human opens
    for name in ("nodes", "edges", "clusters", "adjacency"):
        (out_dir / f"{name}.json").write_text(json.dumps(graph[name], separators=(",", ":")), encoding="utf-8")
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")


def _cli_tenant(data_home: str, join_keys: str) -> Tenant:
    dh = Path(data_home).resolve()
    jk = Path(join_keys).resolve()
    return Tenant(
        root=dh.parent,
        data_home=dh,
        adapters=(),
        build_lanes={},
        join_keys=jk,
        cursor="declared-cli",
        policy="refuse",
        journal=dh / ".journal",
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="graphy cartographer — JSONL → adjacency graphs + clusters")
    ap.add_argument("input", help="JSONL file")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tenant-id", required=True,
                    help="the receipt-name — graphy resolves identity only through a declared Tenant.")
    ap.add_argument("--data-home", required=True, help="the tenant data_home (the out-dir's home context).")
    ap.add_argument("--join-keys", required=True, help="path to the tenant's substrate_override_registry.json.")
    args = ap.parse_args(argv)

    tenant = _cli_tenant(args.data_home, args.join_keys)

    records: list[dict] = []
    with open(args.input, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    graph = cartograph(records)
    write_graph(graph, Path(args.out_dir), repo_root=Path(tenant.root))
    s = graph["stats"]
    print(
        f"[cartograph] nodes={s['node_count']} edges={s['edge_count']} "
        f"clusters={s['cluster_count']} → {args.out_dir}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
