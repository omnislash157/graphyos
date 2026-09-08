"""draw — the codebase drawn mechanically from the store, no work for the model.

Three doors, every one a query over the compiled store and never a shard load: the module
graph (the pillars' unit rule — the first N dotted segments of every node's `module`, edges
weighted by the calls · imports · inherits · decorates between units), one arm of a partition
(its modules, module to module), and a symbol's neighbourhood (the doors' reach, both ways, to a
radius). Each yields (nodes, edges, labels, meta, title) and the sugiyama engine lays it out:
ASCII for the terminal, one self-contained HTML+SVG page for a human, the same routes in both.
The raster is the bandwidth adapter between the model-native 1-D form and the human eye; it is
computed from the walk, never hand-drawn, and the check refuses a page that lies about geometry.
"""
from __future__ import annotations

import collections
import json
from dataclasses import dataclass, field
from pathlib import Path

from graphy import sugiyama as S
from graphy.pillars import RELATIONS, _module_of

__all__ = ["DrawError", "Picture", "units", "pillars", "arm", "neighbourhood", "render", "atlas", "RECEIPT"]

RECEIPT = "atlas.json"


class DrawError(RuntimeError):
    pass


@dataclass
class Picture:
    title: str
    nodes: list
    edges: list                       # (src, dst) pairs, unique
    labels: dict
    meta: dict = field(default_factory=dict)      # node -> {file, line, owner}
    weights: dict = field(default_factory=dict)   # (src, dst) -> count
    dropped: int = 0                              # edges under --min-weight

    def summary(self) -> str:
        return f"{len(self.nodes)} node(s) · {len(self.edges)} edge(s)" + (f" · {self.dropped} under the weight floor" if self.dropped else "")


def _short(dotted: str, root: str) -> str:
    return dotted[len(root) + 1:] if dotted.startswith(root + ".") and len(dotted) > len(root) + 1 else dotted


def units(store, corpus: str, depth: int = 2, min_weight: int = 1) -> Picture:
    """The corpus's module graph collapsed to units of `depth` dotted segments; a unit is a node,
    an edge carries the count of cross-unit calls · imports · inherits · decorates. The test
    role is skipped, as pillars skip it."""
    module_of: dict[str, str] = {}
    for nid, rec in store.owned(corpus):
        if rec and rec.get("role") == "test":
            continue
        m = _module_of(rec, nid)
        if m:
            module_of[nid] = m
    if not module_of:
        raise DrawError(f"the store owns no module-bearing node for corpus {corpus!r}")
    root = min(module_of.values(), key=lambda m: (m.count("."), m)).split(".")[0]

    def unit(m: str) -> str:
        return ".".join(m.split(".")[:depth])

    weight: collections.Counter = collections.Counter()
    for src, dst, rel in store.edges():
        if rel not in RELATIONS:
            continue
        ms, md = module_of.get(src), module_of.get(dst)
        if ms is None or md is None:
            continue
        us, ud = unit(ms), unit(md)
        if us != ud:
            weight[(us, ud)] += 1
    edges = sorted(e for e, c in weight.items() if c >= min_weight)
    dropped = sum(1 for c in weight.values() if c < min_weight)
    nodes = sorted({u for e in edges for u in e} | ({unit(m) for m in module_of.values()} if min_weight <= 1 else set()))
    labels = {n: _short(n, root) or n for n in nodes}
    return Picture(title=f"{corpus} · units at depth {depth}" + (f" · edges ≥ {min_weight}" if min_weight > 1 else ""),
                   nodes=nodes, edges=edges, labels=labels, weights=dict(weight), dropped=dropped)


def pillars(store, corpus: str, cut, min_weight: int = 1) -> Picture:
    """The partition's groups as nodes — the pillars — and the cross-arm edge counts between them:
    the matrix `graphy pillars` prints, drawn. The rest group is drawn when anything reaches it."""
    if cut.groups is None:
        raise DrawError("--pillars needs a partition cut — a depth cut names no arm")
    module_of: dict[str, str] = {}
    for nid, rec in store.owned(corpus):
        if rec and rec.get("role") == "test":
            continue
        m = _module_of(rec, nid)
        if m:
            module_of[nid] = m
    if not module_of:
        raise DrawError(f"the store owns no module-bearing node for corpus {corpus!r}")
    weight: collections.Counter = collections.Counter()
    for src, dst, rel in store.edges():
        if rel not in RELATIONS:
            continue
        ms, md = module_of.get(src), module_of.get(dst)
        if ms is None or md is None:
            continue
        a, b = cut.group_of(ms), cut.group_of(md)
        if a != b:
            weight[(a, b)] += 1
    edges = sorted(e for e, c in weight.items() if c >= min_weight)
    dropped = sum(1 for c in weight.values() if c < min_weight)
    nodes = sorted(set(cut.groups) | {u for e in edges for u in e})
    labels = {n: f"{n} ({sum(c for (a, _b), c in weight.items() if a == n)}→ ·→{sum(c for (_a, b), c in weight.items() if b == n)})" for n in nodes}
    return Picture(title=f"{corpus} · the pillars", nodes=nodes, edges=edges, labels=labels, weights=dict(weight), dropped=dropped)


def arm(store, corpus: str, cut, name: str, min_weight: int = 1) -> Picture:
    """One arm of a partition, module to module: the modules the partition places in it, the
    edges among them, and every edge that leaves the arm drawn to the arm it lands in."""
    if cut.groups is None or name not in cut.groups:
        raise DrawError(f"{name!r} is not a group of the partition — one of {', '.join(cut.groups or ())}")
    module_of: dict[str, str] = {}
    for nid, rec in store.owned(corpus):
        if rec and rec.get("role") == "test":
            continue
        m = _module_of(rec, nid)
        if m:
            module_of[nid] = m
    inside = {m for m in set(module_of.values()) if cut.group_of(m) == name}
    if not inside:
        raise DrawError(f"the partition places no module of {corpus!r} in {name}")
    weight: collections.Counter = collections.Counter()
    for src, dst, rel in store.edges():
        if rel not in RELATIONS:
            continue
        ms, md = module_of.get(src), module_of.get(dst)
        if ms is None or md is None or ms == md:
            continue
        a = ms if ms in inside else None
        b = md if md in inside else None
        if a and b:
            weight[(a, b)] += 1
        elif a:
            weight[(a, f"[{cut.group_of(md)}]")] += 1
        elif b:
            weight[(f"[{cut.group_of(ms)}]", b)] += 1
    edges = sorted(e for e, c in weight.items() if c >= min_weight)
    dropped = sum(1 for c in weight.values() if c < min_weight)
    nodes = sorted(inside | {u for e in edges for u in e})
    root = corpus
    labels = {n: (n if n.startswith("[") else _short(n, root)) for n in nodes}
    return Picture(title=f"{corpus} · {name}", nodes=nodes, edges=edges, labels=labels, weights=dict(weight), dropped=dropped)


def neighbourhood(store, seed: str, radius: int = 2, max_nodes: int = 60) -> Picture:
    """A symbol's neighbourhood: every node within `radius` hops either way, the directed edges
    among them, each node labeled by its dotted tail and tagged with its owner; the store's
    records give file:line for the badges."""
    if store.membership(seed) is None:
        raise DrawError(f"{seed} is not a node in this store")
    seen = {seed: 0}
    frontier = [seed]
    edges: set = set()
    for hop in range(1, radius + 1):
        nxt = []
        for n in frontier:
            for nb in store.neighbours(n):
                if nb.direction in ("with", "both"):
                    edges.add((n, nb.node, nb.relation))
                if nb.direction in ("against", "both"):
                    edges.add((nb.node, n, nb.relation))
                if nb.node not in seen:
                    seen[nb.node] = hop
                    nxt.append(nb.node)
                    if len(seen) >= max_nodes:
                        break
            if len(seen) >= max_nodes:
                break
        frontier = nxt
        if len(seen) >= max_nodes:
            break
    nodes = sorted(seen, key=lambda n: (seen[n], n))
    pairs = sorted({(a, b) for a, b, _r in edges if a in seen and b in seen and a != b})
    labels, meta = {}, {}
    for n in nodes:
        tail = n.split("/", 3)[-1].rsplit(".", 1)[-1] if "://" in n else n
        owner = store.membership(n) or ""
        labels[n] = f"{tail}" if n == seed else f"{tail} ·{owner}"
        rec = store.record(n) or {}
        meta[n] = {"file": rec.get("file"), "line": rec.get("line"), "owner": owner}
    return Picture(title=f"{seed.split('/', 3)[-1] if '://' in seed else seed} · radius {radius}",
                   nodes=nodes, edges=pairs, labels=labels, meta=meta)


def render(pic: Picture, *, emit: str = "ascii", lr: bool = False, color: bool = False,
           interactive: bool = False, title: str | None = None, layout=None) -> str:
    """One emit of a picture. ``layout`` is the picture's layout when the caller already has it —
    the atlas lays each picture out once and emits it twice (RECON.md §66)."""
    orient = "LR" if lr else "TB"
    lo = layout if layout is not None else S.layout(pic.nodes, pic.edges, pic.labels)
    t = title or pic.title
    if emit == "html":
        return S.emit_html(lo, title=t, orient=orient, interactive=interactive, node_meta=pic.meta)
    if emit == "svg":
        return S.emit_svg_file(lo, title=t, orient=orient, node_meta=pic.meta)
    if emit == "json":
        return json.dumps(S.layout_json(lo, graph_id=t, adapter="graphy.draw", orient=orient), indent=1)
    return S.render(lo, color=color, title=t, orient=orient)


def atlas(store, corpus: str, cut, out_dir: str | Path, *, lr: bool = True, min_weight: int = 1) -> dict:
    """One drawing per arm of the partition plus the unit map, ASCII and HTML side by side under
    `out_dir`, with a receipt naming every file and its sha256. A build product."""
    import hashlib
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    pics = {"PILLARS": pillars(store, corpus, cut, min_weight=min_weight), "UNITS": units(store, corpus, min_weight=min_weight)}
    for name in cut.groups or ():
        try:
            pics[name] = arm(store, corpus, cut, name, min_weight=min_weight)
        except DrawError:
            continue
    for name, pic in pics.items():
        lo = S.layout(pic.nodes, pic.edges, pic.labels)          # once; both emits place it once more between them
        for emit, ext in (("ascii", ".txt"), ("html", ".html")):
            text = render(pic, emit=emit, lr=lr, interactive=(emit == "html"), layout=lo)
            p = out / f"{name}{ext}"
            p.write_text(text, encoding="utf-8")
            files[p.name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    receipt = {"corpus": corpus, "generation": store.generation(), "cut": cut.receipt(), "orient": "LR" if lr else "TB",
               "pictures": {k: {"nodes": len(v.nodes), "edges": len(v.edges)} for k, v in pics.items()}, "files": files}
    (out / RECEIPT).write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
