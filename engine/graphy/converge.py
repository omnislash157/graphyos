"""The seam. ``converge`` measures where a ring's shards touch: for every ordered pair of shards,
the edges of one whose endpoint literal is a node id in the other — wormholes, free by
construction. ``resolve`` turns the producer's text labels (a ``calls`` target, an ``inherits``
base, a ``decorates`` decorator left as ``dst_repr``/``src_repr``) into edges by walking the
module's own scope: a definition in the same module, the module's ``imports`` edges (through
re-exports, one hop at a time), ``self``/``cls``/``this`` against the containing class, ``super`` against
a resolved base. Every step is structural; a name that no rule reaches stays text. The result is
a sidecar, ``wormhole_edges.json``, that the shard loader admits beside ``edges.json``."""
from __future__ import annotations

import builtins
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from graphy.ir import NODE_TYPES
from graphy.native_json_graph_ir import WORMHOLE_SIDECAR, load_graph_ir

__all__ = ["converge", "resolve", "load_ring", "Ring", "WORMHOLE_SIDECAR"]

_BUILTINS = frozenset(dir(builtins))
_REEXPORT_DEPTH = 6


class Ring:
    """Every shard under a data home, indexed once: node id → owning slug, dotted → node id,
    and per module the names its ``imports`` edges bind."""

    def __init__(self, data_home: Path, slugs: list[str]):
        self.data_home = Path(data_home)
        self.slugs = list(slugs)
        self.nodes: dict[str, dict] = {}
        self.owner: dict[str, str] = {}
        self.by_dotted: dict[str, str] = {}
        self.edges: dict[str, list[dict]] = {}
        self.imports: dict[str, dict[str, dict]] = defaultdict(dict)
        self.parent: dict[str, str] = {}
        self.stdlib = _standard_of(data_home)
        self.schemes: set[str] = set()
        for slug in self.slugs:
            gd = self.data_home / f"{slug}_graph"
            if not (gd / "edges.json").is_file():
                raise FileNotFoundError(f"no shard at {gd}")
            gir = load_graph_ir(gd)
            self.edges[slug] = [e for e in gir.edges] + [r for r in gir.residuals
                                                          if isinstance(r, dict) and r.get("kind") == "edge"]
            for n in gir.nodes:
                nid = n["id"]
                self.nodes[nid] = n
                self.owner.setdefault(nid, slug)
                if "://" in nid:
                    self.schemes.add(nid.split("://", 1)[0])
                dotted = n.get("dotted")
                if isinstance(dotted, str):
                    self.by_dotted.setdefault(dotted, nid)
            for e in self.edges[slug]:
                if e.get("edge_type") == "contains" and isinstance(e.get("dst"), str):
                    self.parent[e["dst"]] = e["src"]
                elif e.get("edge_type") == "imports" and isinstance(e.get("dst"), str) and e.get("via") is None:
                    self._bind_import(e)

    def _bind_import(self, e: dict) -> None:
        src, dst = e["src"], e["dst"]
        target_dotted = _dotted_of_id(dst)
        name, alias = e.get("name"), e.get("alias")
        if name:                                       # from X import name [as alias]
            key = alias or name
            self.imports[src].setdefault(key, {"module": target_dotted, "name": name})
        elif alias:                                    # import a.b.c as alias
            self.imports[src].setdefault(alias, {"module": target_dotted, "name": None})
        else:                                          # import a.b.c → binds `a`
            head = target_dotted.split(".", 1)[0]
            self.imports[src].setdefault(head, {"module": head, "name": None, "bare": True})

    def module_of(self, nid: str) -> str | None:
        cur = nid
        for _ in range(64):
            rec = self.nodes.get(cur)
            if rec is not None and rec.get("node_type") == "module":
                return cur
            nxt = self.parent.get(cur)
            if nxt is None:
                return None
            cur = nxt
        return None

    def container_of(self, nid: str) -> str | None:
        p = self.parent.get(nid)
        if p is not None and self.nodes.get(p, {}).get("node_type") == "class":
            return p
        return None

    def dotted(self, nid: str) -> str:
        rec = self.nodes.get(nid)
        if rec and isinstance(rec.get("dotted"), str):
            return rec["dotted"]
        return _dotted_of_id(nid)

    def scheme_of(self, dotted: str) -> str:
        return dotted.split(".", 1)[0]

    def classify_dotted(self, dotted: str) -> str:
        """What a qualified literal is once no node carries it: the standard library, a scheme
        the ring minted but that carries no such node (a def under `if`, a `.so`, a `.pyi`), or
        a scheme the ring never minted."""
        sch = self.scheme_of(dotted)
        if sch in self.stdlib:
            return "stdlib"
        return "missing" if sch in self.schemes else "unminted"


def _dotted_of_id(nid: str) -> str:
    """``scheme://kind/dotted`` → ``dotted``."""
    rest = nid.split("://", 1)[1] if "://" in nid else nid
    return rest.split("/", 1)[1] if "/" in rest else rest


def _standard_of(data_home: Path) -> frozenset[str]:
    """The ecosystem's standard library as the tenant's scheme index names it — written by the
    producer's ring receipt, never read off the running interpreter."""
    from graphy.cross_substrate import load_standard
    home = Path(data_home)
    std = load_standard(home / ".federation_scheme_index.json")
    if std:
        return std
    ring = home / "ring.json"           # the producer's own receipt, beside the shards it minted
    if ring.is_file():
        try:
            return frozenset(str(x) for x in (json.loads(ring.read_text(encoding="utf-8")).get("standard") or ()))
        except (OSError, ValueError, AttributeError):
            return frozenset()
    return frozenset()


def load_ring(data_home: str | Path, slugs: list[str]) -> Ring:
    return Ring(Path(data_home), slugs)


def _label_edges(edges: list[dict]) -> list[tuple[dict, str, str]]:
    """(edge, side, label) for every edge the producer left as text on one side."""
    out = []
    for e in edges:
        if e.get("via") is not None:
            continue
        if isinstance(e.get("dst_repr"), str) and not isinstance(e.get("dst"), str):
            out.append((e, "dst", e["dst_repr"]))
        elif isinstance(e.get("src_repr"), str) and not isinstance(e.get("src"), str):
            out.append((e, "src", e["src_repr"]))
    return out


def _qualify(ring: Ring, module_id: str, head: str, tail: list[str], depth: int = 0) -> tuple[str | None, str | None]:
    """Resolve ``head`` in a module's import scope to (qualified dotted, how). Follows a
    re-export one hop at a time: ``from pkg import X`` where pkg's own ``__init__`` imported X."""
    binding = ring.imports.get(module_id, {}).get(head)
    if binding is None:
        return None, None
    if binding.get("bare") or binding["name"] is None:
        # `import a.b.c` (the label carries the dotted path) or `import a.b.c as alias`
        qualified = ".".join(([head] if binding.get("bare") else [binding["module"]]) + tail)
        return _through_package(ring, qualified, depth)
    qualified = ".".join([binding["module"], binding["name"]] + tail)
    if qualified in ring.by_dotted:
        return qualified, "import" if depth == 0 else "reexport"
    # a re-export: the target module binds the name through its own imports
    target_mod = ring.by_dotted.get(binding["module"])
    if target_mod is not None and depth < _REEXPORT_DEPTH:
        q, how = _qualify(ring, target_mod, binding["name"], tail, depth + 1)
        if q is not None:
            return q, "reexport"
    return qualified, "import"


def _through_package(ring: Ring, qualified: str, depth: int) -> tuple[str, str]:
    """``pkg.Name`` where ``pkg`` is a package whose ``__init__`` imported ``Name`` from a
    submodule: no node carries ``pkg.Name``, but the package's own imports bind it. Walk the
    longest module prefix's imports for the next segment, one hop at a time."""
    if qualified in ring.by_dotted or depth >= _REEXPORT_DEPTH:
        return qualified, "import"
    parts = qualified.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        module_id = ring.by_dotted.get(".".join(parts[:cut]))
        if module_id is None or ring.nodes.get(module_id, {}).get("node_type") != "module":
            continue
        q, how = _qualify(ring, module_id, parts[cut], parts[cut + 1:], depth + 1)
        if q is not None and q in ring.by_dotted:
            return q, "reexport"
        break
    return qualified, "import"


def _resolve_one(ring: Ring, src_node: str, label: str, bases: dict[str, str]) -> dict:
    """One label against the scopes that can bind it. Returns a record with ``dst`` when a node
    carries the literal, else ``qualified``/``kind`` naming what it is."""
    base = label.replace("(...)", "")
    parts = [p for p in base.split(".") if p]
    if not parts:
        return {"kind": "unresolved"}
    head, tail = parts[0], parts[1:]
    module_id = ring.module_of(src_node)
    if module_id is None:
        return {"kind": "unresolved"}
    module_dotted = ring.dotted(module_id)

    if head in ("self", "cls", "this"):
        cls = ring.container_of(src_node)
        if cls is None or len(tail) != 1:
            return {"kind": "unresolved"}
        q = f"{ring.dotted(cls)}.{tail[0]}"
        nid = ring.by_dotted.get(q)
        return {"dst": nid, "via": "self"} if nid else {"kind": "unbound-attribute", "qualified": q}

    if head == "super":
        if not tail:
            return {"kind": "builtin"}          # the bare super() call itself
        cls = ring.container_of(src_node)
        if cls is None or len(tail) != 1:
            return {"kind": "unresolved"}
        base_id = bases.get(cls)
        if base_id is None:
            return {"kind": "unbound-super"}
        q = f"{ring.dotted(base_id)}.{tail[0]}"
        nid = ring.by_dotted.get(q)
        return {"dst": nid, "via": "super"} if nid else {"kind": "unbound-attribute", "qualified": q}

    local = ".".join([module_dotted] + parts)
    nid = ring.by_dotted.get(local)
    if nid:
        return {"dst": nid, "via": "local"}
    if ring.by_dotted.get(f"{module_dotted}.{head}") and tail:
        return {"kind": "unbound-attribute", "qualified": local}

    q, how = _qualify(ring, module_id, head, tail)
    if q is not None:
        nid = ring.by_dotted.get(q)
        if nid:
            return {"dst": nid, "via": how}
        return {"kind": ring.classify_dotted(q), "qualified": q}

    if not tail and head in _BUILTINS:
        return {"kind": "builtin"}
    return {"kind": "unresolved"}


def resolve(ring: Ring, slug: str, *, write: bool = True) -> dict:
    """Resolve every text label in one shard against the ring. Two passes: ``inherits`` first so
    ``super`` has a base to stand on. Writes ``<shard>/wormhole_edges.json`` when asked."""
    edges = ring.edges[slug]
    labels = _label_edges(edges)
    ordered = sorted(labels, key=lambda t: 0 if t[0].get("edge_type") == "inherits" else 1)
    bases: dict[str, str] = {}
    resolved: list[dict] = []
    qualified: list[dict] = []
    tally: Counter = Counter()
    by_via: Counter = Counter()
    for e, side, label in ordered:
        anchor = e["src"] if side == "dst" else e["dst"]
        r = _resolve_one(ring, anchor, label, bases)
        if r.get("dst"):
            rec = {"kind": "edge", "edge_type": e["edge_type"], "via": f"resolver:{r['via']}",
                   "label": label, "side": side}
            if side == "dst":
                rec["src"], rec["dst"] = e["src"], r["dst"]
            else:
                rec["src"], rec["dst"] = r["dst"], e["dst"]
            if e.get("line") is not None:
                rec["line"] = e["line"]
            resolved.append(rec)
            tally["resolved"] += 1
            by_via[r["via"]] += 1
            if e["edge_type"] == "inherits" and side == "dst":
                bases.setdefault(e["src"], r["dst"])
        else:
            tally[r["kind"]] += 1
            if r.get("qualified"):
                qualified.append({"src": anchor, "rel": e["edge_type"], "side": side, "label": label,
                                  "qualified": r["qualified"], "kind": r["kind"]})
    cross = sum(1 for rec in resolved if ring.owner.get(rec["dst"]) != slug or ring.owner.get(rec["src"]) != slug)
    summary = {
        "shard": slug, "labels": len(labels), "resolved": tally["resolved"], "cross_shard": cross,
        "via": dict(sorted(by_via.items())),
        "unresolved": {k: v for k, v in sorted(tally.items()) if k != "resolved"},
        "resolved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if write:
        path = ring.data_home / f"{slug}_graph" / WORMHOLE_SIDECAR
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps({"summary": summary, "edges": resolved, "qualified": qualified}, indent=1) + "\n",
                       encoding="utf-8")
        os.replace(tmp, path)
        summary["sidecar"] = str(path)
    return summary


def converge(ring: Ring) -> dict:
    """Per ordered shard pair: how many of A's edges land on a node B owns, and over how many
    distinct B nodes. Reads the sidecars when present, so it measures the seam after ``resolve``
    as readily as before."""
    pairs: dict[tuple[str, str], Counter] = defaultdict(Counter)
    targets: dict[tuple[str, str], set] = defaultdict(set)
    per_shard: dict[str, dict] = {}
    for slug in ring.slugs:
        edges = ring.edges[slug]
        labels = sum(1 for _ in _label_edges(edges))
        with_dst = 0
        out_of_shard = 0
        for e in edges:
            for ep in (e.get("src"), e.get("dst")):
                if not isinstance(ep, str):
                    continue
                owner = ring.owner.get(ep)
                if owner is None or owner == slug:
                    continue
                pairs[(slug, owner)][e.get("edge_type", "?")] += 1
                targets[(slug, owner)].add(ep)
            if isinstance(e.get("dst"), str):
                with_dst += 1
                if ring.owner.get(e["dst"]) not in (None, slug):
                    out_of_shard += 1
        per_shard[slug] = {"edges": len(edges), "with_dst": with_dst, "labels": labels,
                           "into_other_shards": out_of_shard}
    rows = []
    for (a, b), kinds in sorted(pairs.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])):
        rows.append({"from": a, "to": b, "edges": sum(kinds.values()), "nodes": len(targets[(a, b)]),
                     "by_type": dict(sorted(kinds.items()))})
    return {"shards": per_shard, "pairs": rows,
            "wormholes": sum(r["edges"] for r in rows),
            "wormhole_nodes": len({ep for s in targets.values() for ep in s})}
