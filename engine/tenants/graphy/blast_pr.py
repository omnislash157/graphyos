#!/usr/bin/env python3
"""blast_pr — the blast radius of a diff, from the walk, before a human reads the diff.

    python3 blast_pr.py <base> <head> [--depth N] [--limit N]

Every changed line under engine/graphy/ is mapped to the symbol the store places there (the
record with that file and the greatest start line at or before the changed line), each symbol is
blasted against the compiled store (what depends on it, transitively), its tests are named
(explain), and the arm it lands in is read from the partition. One comment, plain text, the tool's
own words. Runs over the graphy tenant's store; rebuild it first.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent.parent
ROOT = ENGINE.parent
sys.path.insert(0, str(ENGINE))

from graphy import doors, fanout, federated_store as fs                      # noqa: E402
from graphy.cli import _load_tenant, _roster                                  # noqa: E402


def changed_lines(base: str, head: str) -> dict[str, set[int]]:
    """file (relative to engine/) -> the new-side line numbers the diff touches."""
    out = subprocess.run(["git", "diff", "-U0", f"{base}..{head}", "--", "engine/graphy"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    files: dict[str, set[int]] = collections.defaultdict(set)
    cur = None
    for line in out.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            cur = cur[len("engine/"):] if cur.startswith("engine/") else cur
        elif line.startswith("@@") and cur:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start, n = int(m.group(1)), int(m.group(2) or 1)
                files[cur].update(range(start, start + max(n, 1)))
    return dict(files)


def symbols_for(store, corpus: str, changed: dict[str, set[int]]) -> dict[str, set[str]]:
    """symbol id -> the changed lines inside it: the record with the same file whose start line
    is the greatest at or before the line (a def, a class, a method), else the module."""
    by_file: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    module_of_file: dict[str, str] = {}
    for nid, rec in store.owned(corpus):
        if not rec or not rec.get("file"):
            continue
        f = rec["file"]
        if rec.get("node_type") == "module":
            module_of_file[f] = nid
        elif isinstance(rec.get("line"), int):
            by_file[f].append((rec["line"], nid))
    hits: dict[str, set[str]] = collections.defaultdict(set)
    for f, lines in changed.items():
        starts = sorted(by_file.get(f, []))
        for ln in sorted(lines):
            owner = module_of_file.get(f)
            for start, nid in starts:
                if start <= ln:
                    owner = nid
                else:
                    break
            if owner:
                hits[owner].add(f"{f}:{ln}")
    return hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base"); ap.add_argument("head")
    ap.add_argument("--depth", type=int, default=3); ap.add_argument("--limit", type=int, default=8)
    args = ap.parse_args(argv)
    desc = HERE / "tenant.json"
    if not desc.is_file():
        print("BLAST_PR REFUSED: no graphy tenant — bash tenants/graphy/rebuild.sh first", file=sys.stderr)
        return 2
    tenant = _load_tenant(str(desc))
    store = fs.open_for(_roster(tenant), tenant=tenant, tenant_id="graphy", on_stale="warn")
    cut = fanout.load_partition(HERE / "partition.json")
    changed = changed_lines(args.base, args.head)
    if not changed:
        print(f"BLAST_PR: {args.base}..{args.head} touches nothing under engine/graphy/ — no radius")
        return 0
    hits = symbols_for(store, "graphy", changed)
    print(f"BLAST RADIUS of {args.base[:10]}..{args.head[:10]} — {sum(len(v) for v in changed.values())} changed line(s) "
          f"in {len(changed)} file(s) land in {len(hits)} symbol(s); store generation {store.generation()}")
    total_dep, seen_dep = 0, set()
    for nid in sorted(hits, key=lambda n: (-len(hits[n]), n)):
        rec = store.record(nid) or {}
        arm = cut.group_of(rec.get("module") or "")
        b = doors.blast(store, nid, args.depth)
        own = [n for n, r in b.reached.items() if r.hop > 0 and r.owner == "graphy"]
        other = [n for n, r in b.reached.items() if r.hop > 0 and r.owner != "graphy"]
        e = doors.explain(store, nid, args.depth, tenant=tenant)
        tests = [t.node.split("/", 3)[-1] for t in e.tests][: args.limit]
        seen_dep.update(own)
        print(f"\n  {nid}   [{arm}]   lines {', '.join(sorted(hits[nid], key=lambda s: int(s.rsplit(':', 1)[1])))[:80]}")
        print(f"    depends on it: {len(own)} in graphy" + (f", {len(other)} in the ring" if other else "") + f" (depth {args.depth})")
        for n in sorted(own, key=lambda n: b.reached[n].hop)[: args.limit]:
            print(f"      hop{b.reached[n].hop} {n.split('/', 3)[-1]}")
        if len(own) > args.limit:
            print(f"      … {len(own) - args.limit} more")
        print("    tests that reach it: " + (", ".join(tests) if tests else "none the store carries"))
    print(f"\n  in all: {len(seen_dep)} symbol(s) of graphy depend on what changed; the arms touched: "
          + ", ".join(sorted({cut.group_of((store.record(n) or {}).get('module') or '') for n in hits})))
    print("  (the walk decided every line above; no model did)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
