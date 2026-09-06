
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from graphy.ir import Vocabulary

__all__ = ["build_ir", "OUTLINE_VOCABULARY"]

OUTLINE_VOCABULARY = Vocabulary(
    node_types=("outline_line",),
    edge_types=("contains",),
    producer="outline",
)

_BULLET = re.compile(r"^[-*+]\s+(.*)$")
_SLUG = re.compile(r"[^a-z0-9]+")


class _NodeRecords(dict):

    def __iter__(self):  # type: ignore[override]
        return iter(self.values())


def _slugify(label: str) -> str:
    return (_SLUG.sub("_", label.lower()).strip("_")[:60]) or "line"


def parse_outline(text: str, doc: str) -> list[dict]:
    records: list[dict] = []
    stack: list[tuple[int, str]] = []
    seen: dict[str, int] = {}
    for raw in text.splitlines():
        if not raw.strip():
            continue
        body = raw.lstrip(" \t")
        indent = len(raw[: len(raw) - len(body)].replace("\t", "    "))
        label = body.rstrip()
        m = _BULLET.match(label)
        if m:
            label = m.group(1)
        slug = _slugify(label)
        n = seen.get(slug, 0) + 1
        seen[slug] = n
        if n > 1:
            slug = f"{slug}~{n}"
        nid = f"outline://{doc}/{slug}"
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1] if stack else None
        stack.append((indent, nid))
        records.append({
            "kind": "node", "node_type": "outline_line", "id": nid,
            "label": label, "doc": doc,
            "dotted": f"outline.{doc}.{slug}",
        })
        if parent:
            records.append({"kind": "edge", "edge_type": "contains", "src": parent, "dst": nid})
    return records


def build_ir(outline_file: str | Path) -> tuple[_NodeRecords, list[dict]]:
    path = Path(outline_file)
    text = path.read_text(encoding="utf-8")
    doc = _slugify(path.stem)
    nodes: _NodeRecords = _NodeRecords()
    edges: list[dict] = []
    for rec in parse_outline(text, doc):
        if rec.get("kind") == "node":
            nodes[rec["id"]] = rec
        else:
            edges.append(rec)
    return nodes, edges
