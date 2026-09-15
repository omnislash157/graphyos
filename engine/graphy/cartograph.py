
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from graphy.tenant import Tenant, TenantError, cli_tenant
from graphy._shared import POINTER_MARK, generation_of


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


def repo_toplevel(root: Path) -> Path | None:
    """The git checkout ``root`` stands in — its toplevel — or None when git or the checkout is absent.
    A tenant's root may be a directory inside the checkout (the graphy tenant's is ``engine/tenants/graphy``);
    the inputs the history shard reads (the archive, RECON, the receipts) sit at the toplevel (graphyos #66)."""
    try:
        proc = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return Path(proc.stdout.strip()).resolve()


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
        if any(_excluded(full, r) for r in roots):
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


# Every cursor's exclusion comes from one of these, so the store that is built and the check that audits it
# never disagree on what is dirt (review.py `cursor-exclude-by-tenant`, graphyos #98 round 2).
CURSOR_EXCLUDERS = ("cursor_exclude", "tenant_exclude")


def generation_base(path: Path) -> Path:
    """``<substrate>.gen-<token>`` → ``<substrate>``; any other path is its own base."""
    p = Path(path)
    base = generation_of(p.name)
    return p.with_name(base) if base else p


def _excluded(full: Path, root: Path) -> bool:
    """Under ``root``, or under a generation of it: excluding a substrate excludes every ``<substrate>.gen-*``
    beside it, the stage being built and a held one a platform could not remove included."""
    if root == full or root in full.parents:
        return True
    return any(a.parent == root.parent and generation_of(a.name) == root.name for a in (full, *full.parents))


# What `graphy shell install` writes into a checkout for its own wiring, relative to the tenant's root. The cursor
# never counts it as dirt: the README's `graphy eat . && graphy shell install` read CHECK RED on the two files the
# install had just written, and named `eat .` to absorb them (graphyos #143).
ENGINE_WIRING = ("GRAPHY.md", ".claude/settings.json", ".codex/hooks.json", ".cursor/hooks.json", ".graphy/hooks")
# The pointers `eat`'s harness writes at the root. Each is the engine's only while it carries the harness's mark —
# the same rule by which the harness replaces it — so a human CLAUDE.md the harness left alone is still dirt.
POINTER_FILES = ("CLAUDE.md", "AGENTS.md")


def _is_pointer(path: Path) -> bool:
    try:
        return path.is_file() and POINTER_MARK in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def cursor_exclude(descriptor: Path, data_home: Path, *, root: Path, journal=None, join_keys=None) -> tuple[Path, ...]:
    """What the cursor never counts as dirt: the tenant's own products — every generation of its data home,
    its journal and join keys, the descriptor and the staged one beside it, the home the eat wrote when the
    data home sits inside it, the wiring `shell install` writes under ``root`` (``ENGINE_WIRING``) and the harness's
    pointers while they are still its own (``POINTER_FILES``). `rebuild`,
    `eat`, `check` and `showcase` all ask here; ``root`` is required so no caller counts the wiring another skips."""
    desc = Path(descriptor).resolve()
    base = generation_base(Path(data_home).resolve())
    top = Path(root).resolve()
    out = [base, desc, desc.with_name(f".{desc.name}.next")]
    out += [top / rel for rel in ENGINE_WIRING]
    out += [p for p in (top / name for name in POINTER_FILES) if _is_pointer(p)]
    out += [Path(x) for x in (journal, join_keys) if x]
    if desc.parent == base.parent:
        out.append(desc.parent)
    return tuple(out)


def tenant_exclude(descriptor: Path, tenant: Tenant) -> tuple[Path, ...]:
    """`cursor_exclude` for a declared tenant."""
    return cursor_exclude(descriptor, tenant.data_home, root=tenant.root, journal=tenant.journal,
                          join_keys=tenant.join_keys)


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


def resolve_graph(graph_dir: Path) -> Path:
    p = Path(graph_dir)
    if p.is_symlink():
        try:
            target = os.readlink(p)
        except OSError:
            target = ""
        if target.startswith("\\\\?\\"):                 # Windows spells an absolute link target extended-length
            target = "\\\\" + target[8:] if target[4:8].upper() == "UNC\\" else target[4:]
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


_cli_tenant = cli_tenant


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="graphy cartographer — JSONL → adjacency graphs + clusters")
    ap.add_argument("input", help="JSONL file")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tenant-id", required=True,
                    help="the receipt-name — graphy resolves identity only through a declared Tenant.")
    ap.add_argument("--data-home", required=True, help="the tenant data_home (the out-dir's home context).")
    ap.add_argument("--join-keys", required=True, help="path to the tenant's substrate_override_registry.json.")
    args = ap.parse_args(argv)

    try:
        tenant = _cli_tenant(args.data_home, args.join_keys, args.tenant_id)
    except TenantError as exc:
        print(f"CARTOGRAPH REFUSED: {exc}", file=sys.stderr)
        return 2

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
