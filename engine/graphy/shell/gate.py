"""The walk-before-edit gate. A PreToolUse hook: an edit to a symbol the store knows, with no
walk stored under the live generation that started at it or passed through it, is blocked (exit
2, the walk on stderr); the stored walk is the bypass. No tenant eaten here, no duckdb, or a file
the store never saw: the gate opens (exit 0) — it confines an agent to a substrate, never to
nothing."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_DEF = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", re.M)


def _module(root: Path, file_path: str) -> str | None:
    try:
        rel = Path(file_path).resolve().relative_to(root)
    except ValueError:
        return None
    if rel.suffix != ".py":
        return None
    parts = [p for p in rel.with_suffix("").parts if p != "src" or rel.parts[0] != "src"]
    return ".".join(parts[:-1] if parts and parts[-1] == "__init__" else parts) or None


def _symbols(store, module: str, text: str) -> list[str]:
    pats = [f"%://{k}/{module}.{'%.' if k == 'method' else ''}{n}"
            for n in dict.fromkeys(_DEF.findall(text)) for k in ("func", "class", "method")]
    return [r[0] for p in pats for r in store._db.execute("SELECT id FROM nodes WHERE id LIKE ?", (p,))]


def _cited(home: Path, generation: str, ids: list[str]) -> set[str]:
    import duckdb
    files = [f.as_posix() for f in sorted((home / generation).glob("*.parquet"))] if (home / generation).is_dir() else []
    if not files:
        return set()
    con = duckdb.connect()
    try:
        return {r[0] for r in con.execute("SELECT DISTINCT node FROM read_parquet(?) WHERE on_path AND node IN "
                                          "(SELECT unnest(?))", [files, ids]).fetchall()}
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    payload = json.loads(raw) if raw.strip() else {}
    tool, ti = payload.get("tool_name"), payload.get("tool_input") or {}
    if tool not in ("Edit", "Write", "MultiEdit") or not ti.get("file_path"):
        return 0
    text = ti.get("old_string") or ti.get("content") or "".join(e.get("old_string", "") for e in ti.get("edits", []))
    repo = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()).resolve()
    desc = Path(os.environ.get("GRAPHY_TENANT") or repo / ".graphy" / "tenant.json")
    ring = desc.parent / "substrate" / "ring.json"
    if not desc.is_file() or not ring.is_file():
        return 0
    from graphy import cli, traversal, federated_store as fstore
    tenant = cli._load_tenant(str(desc))
    tid = os.environ.get("GRAPHY_TENANT_ID") or json.loads(ring.read_text(encoding="utf-8"))["root"]
    module = _module(Path(tenant.root), ti["file_path"])
    if module is None or not traversal.have_duckdb():
        return 0
    store = fstore.open_for(cli._roster(tenant), tenant=tenant, tenant_id=tid, on_stale="warn")
    ids = _symbols(store, module, text)
    uncited = [i for i in ids if i not in _cited(traversal.home_for(tenant), store.generation(), ids)]
    if not uncited:
        return 0
    print(f"GATE BLOCKED: {ti['file_path']} edits {len(uncited)} symbol(s) the store knows with no walk cited "
          f"under generation {store.generation()[:12]}. Walk first, read the path, then edit:", file=sys.stderr)
    for i in uncited:
        print(f"  {sys.executable} -m graphy walk --tenant {desc} --tenant-id {tid} --seed {i} --target {tid}://module/{tid}",
              file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
