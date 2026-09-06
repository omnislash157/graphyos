from __future__ import annotations

import json
import re
from collections import deque, namedtuple
from pathlib import Path


try:                                     # pragma: no cover - environment-dependent
    from wcwidth import wcswidth as _wcswidth
except ModuleNotFoundError:
    import unicodedata

    def _wcswidth(s: str) -> int:
        total = 0
        for ch in s:
            if unicodedata.combining(ch):
                continue
            total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        return total


def wcswidth(s: str) -> int:
    return _wcswidth(s)



N, E, S, W = 1, 2, 4, 8

_LIGHT = {
    E | W: "─", E: "─", W: "─",
    N | S: "│", N: "│", S: "│",
    S | E: "┌", S | W: "┐", N | E: "└", N | W: "┘",
    N | S | E: "├", N | S | W: "┤", E | W | S: "┬", E | W | N: "┴",
    N | E | S | W: "┼",
}
_HEAVY = {
    E | W: "━", E: "━", W: "━",
    N | S: "┃", N: "┃", S: "┃",
    S | E: "┏", S | W: "┓", N | E: "┗", N | W: "┛",
    N | S | E: "┣", N | S | W: "┫", E | W | S: "┳", E | W | N: "┻",
    N | E | S | W: "╋",
}
THEMES = {"light": _LIGHT, "heavy": _HEAVY}

PALETTE = {
    "write": 203,
    "read": 75,
    "cache": 114,
    "throttle": 221,
    "minor": 244,
    "queue": 141,
}

NODE_EMOJI = {
    "store": "💾", "service": "🔌", "client": "💻", "report": "📊",
    "auth": "🔐", "external": "🌐", "cron": "⏰", "queue": "📥",
}
DECOR_EMOJI = {"bridge": "🌉", "throttle": "🚧", "gate": "🛑", "cache": "⚡"}


def _ansi(code: int | None) -> str:
    return f"\033[38;5;{code}m" if code is not None else ""


class Canvas:

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.glyph = [[" "] * w for _ in range(h)]
        self.bits = [[0] * w for _ in range(h)]
        self.weight = [[1] * w for _ in range(h)]
        self.color = [[None] * w for _ in range(h)]
        self.cont = [[False] * w for _ in range(h)]

    def tile(self, r: int, c: int, s: str, color: int | None = None) -> None:
        col = c
        for ch in s:
            cw = max(1, wcswidth(ch))
            if 0 <= r < self.h and 0 <= col < self.w:
                self.glyph[r][col] = ch
                self.color[r][col] = color
                for k in range(1, cw):
                    if col + k < self.w:
                        self.cont[r][col + k] = True
                        self.glyph[r][col + k] = ""
            col += cw

    def hroad(self, r: int, c0: int, c1: int, weight: int = 1,
              color: int | None = None) -> None:
        for c in range(c0, c1 + 1):
            self.bits[r][c] |= E | W
            self.weight[r][c] = weight
            self.color[r][c] = color
        self.bits[r][c0] &= ~W
        self.bits[r][c1] &= ~E

    def vroad(self, c: int, r0: int, r1: int, weight: int = 1,
              color: int | None = None) -> None:
        for r in range(r0, r1 + 1):
            self.bits[r][c] |= N | S
            self.weight[r][c] = weight
            self.color[r][c] = color
        self.bits[r0][c] &= ~N
        self.bits[r1][c] &= ~S

    def cross(self, r: int, c: int, color: int | None = None) -> None:
        self.glyph[r][c] = "╪"
        self.color[r][c] = color

    def bridge(self, r: int, c: int, color: int | None = None) -> None:
        self.tile(r, c, "🌉", color)

    def render(self) -> str:
        rows = []
        for r in range(self.h):
            out, last = [], None
            for c in range(self.w):
                if self.cont[r][c]:
                    continue
                g = self.glyph[r][c]
                if g == " " and self.bits[r][c]:
                    table = THEMES["heavy" if self.weight[r][c] == 2 else "light"]
                    g = table.get(self.bits[r][c], " ")
                col = self.color[r][c]
                if col != last:
                    out.append("\033[0m" + _ansi(col))
                    last = col
                out.append(g)
            out.append("\033[0m")
            rows.append("".join(out).rstrip())
        return "\n".join(rows)




BOX_H = 3
ROW_PITCH = 5
COL_GAP = 3
_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

def _all_nodes(adj: dict) -> set:
    nodes = set(adj.keys())
    for vs in adj.values():
        nodes |= set(vs)
    return nodes


def _tarjan_sccs(adj: dict) -> list:
    index = {}
    low = {}
    on_stack = {}
    stack = []
    sccs = []
    counter = [0]

    for root in sorted(_all_nodes(adj), key=str):
        if root in index:
            continue
        work = [(root, iter(adj.get(root, ())))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on_stack[root] = True
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter[0]
                    counter[0] += 1
                    stack.append(w)
                    on_stack[w] = True
                    work.append((w, iter(adj.get(w, ()))))
                    advanced = True
                    break
                if on_stack.get(w):
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            if low[v] == index[v]:
                comp = set()
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    comp.add(w)
                    if w == v:
                        break
                sccs.append(frozenset(comp))
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
    return sccs


def _greedy_fas(adj: dict) -> set:
    nodes = _all_nodes(adj)
    out_deg = {v: len(set(adj.get(v, ()))) for v in nodes}
    in_deg = {v: 0 for v in nodes}
    for u, vs in adj.items():
        for v in vs:
            in_deg[v] += 1
    preds = {v: set() for v in nodes}
    for u, vs in adj.items():
        for v in vs:
            preds[v].add(u)

    remaining = set(nodes)
    left, right = [], []
    while remaining:
        moved = True
        while moved:
            moved = False
            for s in sorted((v for v in remaining if out_deg[v] == 0), key=str):
                right.append(s)
                remaining.discard(s)
                for p in preds[s]:
                    if p in remaining:
                        out_deg[p] -= 1
                moved = True
            for s in sorted((v for v in remaining if in_deg[v] == 0 and v in remaining), key=str):
                left.append(s)
                remaining.discard(s)
                for w in adj.get(s, ()):
                    if w in remaining:
                        in_deg[w] -= 1
                moved = True
        if remaining:
            u = max(sorted(remaining, key=str), key=lambda v: out_deg[v] - in_deg[v])
            left.append(u)
            remaining.discard(u)
            for w in adj.get(u, ()):
                if w in remaining:
                    in_deg[w] -= 1
            for p in preds[u]:
                if p in remaining:
                    out_deg[p] -= 1

    order = left + list(reversed(right))
    pos = {v: i for i, v in enumerate(order)}
    fas = set()
    for u, vs in adj.items():
        for v in vs:
            if pos.get(u, 0) > pos.get(v, 0):
                fas.add((u, v))
    return fas


def _fas(adj: dict) -> set:
    fas = set()
    for scc in _tarjan_sccs(adj):
        if len(scc) <= 1:
            continue
        sub = {u: {v for v in adj.get(u, ()) if v in scc} for u in scc}
        fas |= _greedy_fas(sub)
    return fas


def _apply_fas(adj: dict, fas: set) -> dict:
    new = {u: set(vs) for u, vs in adj.items()}
    for u, v in fas:
        new.setdefault(u, set()).discard(v)
        new.setdefault(v, set()).add(u)
    return new


def _longest_path_layering(adj: dict) -> dict:
    nodes = _all_nodes(adj)
    in_deg = {v: 0 for v in nodes}
    for u, vs in adj.items():
        for v in vs:
            in_deg[v] += 1
    queue = deque(v for v in nodes if in_deg[v] == 0)
    topo = []
    while queue:
        u = queue.popleft()
        topo.append(u)
        for v in adj.get(u, ()):
            in_deg[v] -= 1
            if in_deg[v] == 0:
                queue.append(v)
    layer = {v: 0 for v in nodes}
    for u in topo:
        for v in adj.get(u, ()):
            layer[v] = max(layer[v], layer[u] + 1)
    return layer


def _insert_dummies(adj: dict, layer: dict):
    new = {u: set(vs) for u, vs in adj.items()}
    dummies = {}
    counter = [0]
    for u in list(adj.keys()):
        for v in sorted(adj.get(u, ()), key=str):
            span = layer[v] - layer[u]
            if span > 1:
                new[u].discard(v)
                chain, prev = [], u
                for k in range(1, span):
                    d = f"\x00dummy{counter[0]}"
                    counter[0] += 1
                    chain.append(d)
                    layer[d] = layer[u] + k
                    new.setdefault(prev, set()).add(d)
                    new[d] = set()
                    prev = d
                new[prev].add(v)
                dummies[(u, v)] = chain
    return new, layer, dummies


def _build_layers(layer: dict) -> list:
    if not layer:
        return []
    layers = [[] for _ in range(max(layer.values()) + 1)]
    for node, l in layer.items():
        layers[l].append(node)
    return [sorted(lyr, key=str) for lyr in layers]


def _median_order(nodes: list, neigh_pos: dict) -> list:
    def key(v):
        ps = sorted(neigh_pos.get(v, []))
        if not ps:
            return float("inf")
        n = len(ps)
        return ps[n // 2] if n % 2 else (ps[n // 2 - 1] + ps[n // 2]) / 2.0
    return sorted(nodes, key=key)


def _count_crossings(a: list, b: list, adj: dict) -> int:
    pos_a = {v: i for i, v in enumerate(a)}
    pos_b = {v: i for i, v in enumerate(b)}
    seq = []
    for u in a:
        for v in adj.get(u, ()):
            if v in pos_b:
                seq.append((pos_a[u], pos_b[v]))
    crossings = 0
    for i in range(len(seq)):
        for j in range(i + 1, len(seq)):
            if (seq[i][0] - seq[j][0]) * (seq[i][1] - seq[j][1]) < 0:
                crossings += 1
    return crossings


def _total_crossings(layers: list, adj: dict) -> int:
    return sum(_count_crossings(layers[i], layers[i + 1], adj)
               for i in range(len(layers) - 1))


def _minimize_crossings(layers: list, adj: dict, iters: int = 24) -> list:
    pred = {}
    for u, vs in adj.items():
        for v in vs:
            pred.setdefault(v, set()).add(u)

    def sweep_down(ls):
        for i in range(1, len(ls)):
            up = {n: j for j, n in enumerate(ls[i - 1])}
            np_ = {v: [up[p] for p in pred.get(v, ()) if p in up] for v in ls[i]}
            ls[i] = _median_order(ls[i], np_)
        return ls

    def sweep_up(ls):
        for i in range(len(ls) - 2, -1, -1):
            low = {n: j for j, n in enumerate(ls[i + 1])}
            np_ = {v: [low[s] for s in adj.get(v, ()) if s in low] for v in ls[i]}
            ls[i] = _median_order(ls[i], np_)
        return ls

    best = [list(l) for l in layers]
    best_c = _total_crossings(layers, adj)
    for it in range(iters):
        layers = sweep_down(layers) if it % 2 == 0 else sweep_up(layers)
        c = _total_crossings(layers, adj)
        if c < best_c:
            best_c, best = c, [list(l) for l in layers]
        if best_c == 0:
            break
    return best


def _assign_cross(layers: list, adj: dict, size: dict, gap: int) -> dict:
    pred = {}
    for u, vs in adj.items():
        for v in vs:
            pred.setdefault(v, set()).add(u)

    x, x0 = {}, {}
    for layer in layers:
        cur = 0.0
        for n in layer:
            x[n] = x0[n] = cur
            cur += size[n] + gap

    def med_center(n, src):
        cs = sorted(x[m] + size[m] / 2 for m in src.get(n, ()) if m in x)
        if not cs:
            return None
        k = len(cs)
        return cs[k // 2] if k % 2 else (cs[k // 2 - 1] + cs[k // 2]) / 2.0

    for it in range(16):
        down = it % 2 == 0
        src = pred if down else adj
        order = range(len(layers)) if down else range(len(layers) - 1, -1, -1)
        for li in order:
            layer = layers[li]
            for i, n in enumerate(layer):
                tgt = med_center(n, src)
                if tgt is None:
                    continue
                desired = tgt - size[n] / 2
                lb = (x[layer[i - 1]] + size[layer[i - 1]] + gap) if i > 0 else x0[n]
                rb = (x[layer[i + 1]] - gap - size[n]) if i + 1 < len(layer) else x0[n]
                x[n] = min(max(desired, lb), rb) if lb <= rb else lb
    return x


class Layout:
    __slots__ = ("layers", "layer_of", "adj", "dummies", "reversed_edges",
                 "width", "labels", "isolated", "edges")

    def is_dummy(self, n) -> bool:
        return isinstance(n, str) and n.startswith("\x00dummy")


_Placed = namedtuple("_Placed",
                     "rc_of W H TB n_layers cpos routes layer_thick layer_along")


def layout(nodes, edges, labels=None) -> Layout:
    labels = dict(labels or {})
    adj = {}
    node_set = set(nodes)
    deg = {}
    edge_pairs = set()
    for e in edges:
        u, v = e[0], e[1]
        node_set.add(u)
        node_set.add(v)
        if u != v:
            adj.setdefault(u, set()).add(v)
            deg[u] = deg.get(u, 0) + 1
            deg[v] = deg.get(v, 0) + 1
            edge_pairs.add((u, v))

    isolated = sorted((n for n in node_set if not deg.get(n)), key=str)
    node_set -= set(isolated)
    adj = {u: {v for v in vs if v in node_set} for u, vs in adj.items() if u in node_set}
    for n in sorted(node_set, key=str):
        adj.setdefault(n, set())

    fas = _fas(adj)
    dag = _apply_fas(adj, fas)
    layer = _longest_path_layering(dag)
    dag, layer, dummies = _insert_dummies(dag, layer)
    layers = _build_layers(layer)
    layers = _minimize_crossings(layers, dag)

    width = {}
    for n in _all_nodes(dag):
        if isinstance(n, str) and n.startswith("\x00dummy"):
            width[n] = 1
        else:
            lbl = labels.get(n, str(n))
            width[n] = max(3, _disp_w(lbl) + 4)

    lo = Layout()
    lo.layers = layers
    lo.layer_of = layer
    lo.adj = dag
    lo.dummies = dummies
    lo.reversed_edges = fas
    lo.width = width
    lo.labels = labels
    lo.isolated = isolated
    lo.edges = sorted(edge_pairs)
    return lo


def _disp_w(s: str) -> int:
    w = wcswidth(s)
    return w if w and w > 0 else len(s)


def _placed(lo: Layout, orient: str = "TB") -> _Placed:
    from collections import defaultdict
    TB = orient.upper() != "LR"
    width, layer_of, layers = lo.width, lo.layer_of, lo.layers
    n_layers = len(layers)
    cross_gap = COL_GAP if TB else 1

    def along_thick(n):
        return 1 if lo.is_dummy(n) else (BOX_H if TB else width[n])

    def cross_size(n):
        return 1 if lo.is_dummy(n) else (width[n] if TB else BOX_H)

    xf = _assign_cross(layers, lo.adj, {n: cross_size(n) for n in layer_of}, cross_gap)
    minc = min(xf.values()) if xf else 0
    cpos = {n: int(round(xf[n] - minc)) for n in xf}

    def cxc(n):
        return cpos[n] + cross_size(n) // 2

    segments = []
    eid = 0
    for u in lo.adj:
        if lo.is_dummy(u):
            continue
        for v in sorted(lo.adj[u], key=str):
            chain, cur, guard = [u], v, 0
            while lo.is_dummy(cur) and guard < 100_000:
                chain.append(cur)
                cur = next(iter(lo.adj.get(cur, ())), None)
                if cur is None:
                    break
                guard += 1
            chain.append(cur)
            is_rev = (u, cur) in lo.reversed_edges or (cur, u) in lo.reversed_edges
            eid += 1
            for a, b in zip(chain, chain[1:]):
                segments.append({"gap": layer_of[a], "src": a, "ca": cxc(a),
                                 "cb": cxc(b), "eid": eid, "rev": is_rev,
                                 "b_dummy": lo.is_dummy(b)})

    by_src = defaultdict(list)
    for s in segments:
        by_src[(s["gap"], s["src"])].append(s)
    routes = []
    for (g, _src), segs in by_src.items():
        if len(segs) >= 2:
            cc = [x for s in segs for x in (s["ca"], s["cb"])]
            routes.append({"gap": g, "kind": "fan", "segs": segs, "iv": (min(cc), max(cc)), "chan": None})
        elif segs[0]["ca"] == segs[0]["cb"]:
            routes.append({"gap": g, "kind": "straight", "segs": segs, "iv": None, "chan": None})
        else:
            s = segs[0]
            routes.append({"gap": g, "kind": "jog", "segs": segs,
                           "iv": (min(s["ca"], s["cb"]), max(s["ca"], s["cb"])), "chan": None})

    gap_channels = {}
    for g in range(max(n_layers - 1, 0)):
        rs = sorted((r for r in routes if r["gap"] == g and r["iv"]), key=lambda r: r["iv"][0])
        channels = []
        for r in rs:
            lo_, hi_ = r["iv"]
            for ci, ch in enumerate(channels):
                if all(hi_ < clo or lo_ > chi for clo, chi in ch):
                    ch.append((lo_, hi_)); r["chan"] = ci; break
            else:
                r["chan"] = len(channels); channels.append([(lo_, hi_)])
        gap_channels[g] = len(channels)

    layer_thick = [max((along_thick(n) for n in layers[L]), default=1) for L in range(n_layers)]
    layer_along = [0] * n_layers
    for L in range(1, n_layers):
        layer_along[L] = layer_along[L - 1] + layer_thick[L - 1] + gap_channels.get(L - 1, 0) + 1

    max_cross = max((cpos[n] + cross_size(n) for n in cpos), default=1)
    max_along = (layer_along[-1] + layer_thick[-1]) if n_layers else 1
    W = (max_cross if TB else max_along) + 2
    H = (max_along if TB else max_cross) + 2

    def to_rc(along, cross):
        return (along, cross) if TB else (cross, along)

    rc_of = {n: to_rc(layer_along[layer_of[n]], cpos[n]) for n in layer_of}
    return _Placed(rc_of=rc_of, W=W, H=H, TB=TB, n_layers=n_layers,
                   cpos=cpos, routes=routes, layer_thick=layer_thick,
                   layer_along=layer_along)


def render(lo: Layout, *, color: bool = True, title: str | None = None,
           orient: str = "TB") -> str:
    pl = _placed(lo, orient)
    TB = pl.TB
    width, layer_of, layers = lo.width, lo.layer_of, lo.layers
    n_layers = pl.n_layers
    cpos, routes = pl.cpos, pl.routes
    layer_thick, layer_along = pl.layer_thick, pl.layer_along
    edge_color = PALETTE["read"] if color else None
    rev_color = PALETTE["write"] if color else None

    def along_thick(n):
        return 1 if lo.is_dummy(n) else (BOX_H if TB else width[n])

    cv = Canvas(pl.W, pl.H)

    def to_rc(along, cross):
        return (along, cross) if TB else (cross, along)

    vcells, hcells, crossings, arrowheads = {}, {}, set(), []

    def vseg(c, r0, r1, eid, clr):
        if r1 < r0:
            r0, r1 = r1, r0
        cv.vroad(c, r0, r1, color=clr)
        for r in range(r0, r1 + 1):
            if r0 < r < r1 and hcells.get((r, c), eid) != eid:
                crossings.add((r, c))
            vcells[(r, c)] = eid

    def hseg(r, c0, c1, eid, clr):
        if c1 < c0:
            c0, c1 = c1, c0
        cv.hroad(r, c0, c1, color=clr)
        for c in range(c0, c1 + 1):
            if c0 < c < c1 and vcells.get((r, c), eid) != eid:
                crossings.add((r, c))
            hcells[(r, c)] = eid

    def along_seg(cross, a0, a1, eid, clr):
        (vseg if TB else hseg)(cross, a0, a1, eid, clr)

    def cross_seg(along, c0, c1, eid, clr):
        (hseg if TB else vseg)(along, c0, c1, eid, clr)

    def exit_along(n):
        L = layer_of[n]
        t = layer_thick[L] if lo.is_dummy(n) else along_thick(n)
        return layer_along[L] + t - 1

    fwd, bwd = ("▼", "▲") if TB else ("▶", "◀")

    for n in layer_of:
        if lo.is_dummy(n):
            L = layer_of[n]
            along_seg(cpos[n], layer_along[L], layer_along[L] + layer_thick[L] - 1, -1, edge_color)

    def _arrow(s, arrow_along, clr):
        if not s["b_dummy"]:
            r, c = to_rc(arrow_along, s["cb"])
            arrowheads.append((r, c, bwd if s["rev"] else fwd, clr))

    for r in routes:
        g = r["gap"]
        arrow_along = layer_along[g + 1] - 1
        bus_along = layer_along[g] + layer_thick[g] + (r["chan"] or 0)
        if r["kind"] == "straight":
            s = r["segs"][0]
            clr = rev_color if s["rev"] else edge_color
            end = layer_along[g + 1] if s["b_dummy"] else arrow_along
            along_seg(s["ca"], exit_along(s["src"]), end, s["eid"], clr)
            _arrow(s, arrow_along, clr)
        elif r["kind"] == "jog":
            s = r["segs"][0]
            clr = rev_color if s["rev"] else edge_color
            end = layer_along[g + 1] if s["b_dummy"] else arrow_along
            along_seg(s["ca"], exit_along(s["src"]), bus_along, s["eid"], clr)
            cross_seg(bus_along, s["ca"], s["cb"], s["eid"], clr)
            along_seg(s["cb"], bus_along, end, s["eid"], clr)
            _arrow(s, arrow_along, clr)
        else:
            segs = r["segs"]
            sc, eid = segs[0]["ca"], segs[0]["eid"]
            along_seg(sc, exit_along(segs[0]["src"]), bus_along, eid, edge_color)
            cc = [s["cb"] for s in segs]
            cross_seg(bus_along, min(cc + [sc]), max(cc + [sc]), eid, edge_color)
            for s in segs:
                clr = rev_color if s["rev"] else edge_color
                end = layer_along[g + 1] if s["b_dummy"] else arrow_along
                along_seg(s["cb"], bus_along, end, eid, clr)
                _arrow(s, arrow_along, clr)

    for n in layer_of:
        if lo.is_dummy(n):
            continue
        r0, c0 = to_rc(layer_along[layer_of[n]], cpos[n])
        r2, c1 = r0 + BOX_H - 1, c0 + width[n] - 1
        cv.hroad(r0, c0, c1)
        cv.hroad(r2, c0, c1)
        cv.vroad(c0, r0, r2)
        cv.vroad(c1, r0, r2)

    for (rr, cc) in crossings:
        cv.cross(rr, cc, color=edge_color)
    for n in layer_of:
        if lo.is_dummy(n):
            continue
        r0, c0 = to_rc(layer_along[layer_of[n]], cpos[n])
        cv.tile(r0 + 1, c0 + 1, _center(lo.labels.get(n, str(n)), width[n] - 2))
    for (rr, cc, glyph, clr) in arrowheads:
        cv.tile(rr, cc, glyph, clr)

    body = cv.render()
    if not color:
        body = _ANSI_RE.sub("", body)
    head = ""
    if title:
        n_real = sum(1 for n in layer_of if not lo.is_dummy(n))
        n_edges = sum(1 for u in lo.adj if not lo.is_dummy(u) for _ in lo.adj[u])
        bo, rst = ("\033[1m", "\033[0m") if color else ("", "")
        head = (f"{bo}  {title}{rst}   {n_layers} layers · {n_real} nodes · {n_edges} edges"
                f" · {len(lo.isolated)} unconnected · [{'TB' if TB else 'LR'}]\n\n")
    return head + body + _render_iso(lo.isolated, color) + "\n"


def _render_iso(items, color, max_w=116) -> str:
    if not items:
        return ""
    boxes = [(s, max(3, _disp_w(s) + 4)) for s in items]
    rows, cur, w = [], [], 0
    for s, bw in boxes:
        if cur and w + bw + 1 > max_w:
            rows.append(cur)
            cur, w = [], 0
        cur.append((s, bw))
        w += bw + 1
    if cur:
        rows.append(cur)
    cv = Canvas(max(sum(bw + 1 for _, bw in r) for r in rows) + 1, len(rows) * 4)
    rr = 0
    for row in rows:
        cc = 0
        for s, bw in row:
            cv.hroad(rr, cc, cc + bw - 1)
            cv.hroad(rr + 2, cc, cc + bw - 1)
            cv.vroad(cc, rr, rr + 2)
            cv.vroad(cc + bw - 1, rr, rr + 2)
            cv.tile(rr + 1, cc + 1, _center(s, bw - 2))
            cc += bw + 1
        rr += 4
    body = cv.render()
    if not color:
        body = _ANSI_RE.sub("", body)
    return f"\n  unconnected ({len(items)}):\n{body}\n"


def _center(s: str, width: int) -> str:
    pad = width - _disp_w(s)
    if pad <= 0:
        out = ""
        for ch in s:
            if _disp_w(out + ch) > width:
                break
            out += ch
        return out + " " * (width - _disp_w(out))
    left = pad // 2
    return " " * left + s + " " * (pad - left)


def draw(nodes, edges, labels=None, *, color=True, title=None, orient="TB") -> str:
    return render(layout(nodes, edges, labels), color=color, title=title, orient=orient)


def layout_json(lo: Layout, *, graph_id: str, adapter: str, orient: str = "TB") -> dict:
    TB = orient.upper() != "LR"
    o = "LR" if not TB else "TB"
    pl = _placed(lo, orient)
    rc_of = pl.rc_of
    nodes = []
    for n in sorted((m for m in lo.layer_of if not lo.is_dummy(m)), key=str):
        row, col = rc_of[n]
        nodes.append({
            "id": n,
            "label": lo.labels.get(n, str(n)),
            "layer": lo.layer_of[n],
            "x": col, "y": row,
            "group": None, "kind": None,
            "portal": False,
        })
    edges = [{"from": u, "to": v, "reversed": (u, v) in lo.reversed_edges}
             for (u, v) in lo.edges]
    return {
        "id": f"visual://{graph_id}",
        "orient": o,
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "adapter": adapter,
            "orient": o,
            "n_layers": len(lo.layers),
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "isolated": list(lo.isolated),
        },
    }



def from_graph(graph_dir: str, *, node_type=None, contains=None, limit=400):
    import json
    import pathlib
    from .cartograph import resolve_graph
    g = resolve_graph(pathlib.Path(graph_dir))
    nodes_raw = json.loads((g / "nodes.json").read_text())
    edges_raw = json.loads((g / "edges.json").read_text())

    def nid(n):
        return n.get("id") if isinstance(n, dict) else n

    keep = {}
    for n in nodes_raw:
        i = nid(n)
        if node_type and isinstance(n, dict) and n.get("node_type") != node_type:
            continue
        if contains and contains not in str(i):
            continue
        short = str(i).split("/")[-1].split("::")[-1]
        short = short.rsplit(".", 1)[-1] if "." in short else short
        keep[i] = short[:28]
        if len(keep) >= limit:
            break

    edges = []
    for e in edges_raw:
        s = e.get("src") if isinstance(e, dict) else e[0]
        d = e.get("dst") if isinstance(e, dict) else e[1]
        if s in keep and d in keep:
            edges.append((s, d))
    return list(keep.keys()), edges, keep



def from_dsl(text: str):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("visual_dsl: empty DSL — no header, no body")
    header = lines[0].lstrip()
    if " · " not in header:
        raise ValueError(
            f"visual_dsl: line 1 must be the header '<title> · <TB|LR>'; got {header.strip()!r}")
    title, _, orient_raw = header.rpartition(" · ")
    title = title.strip()
    orient = orient_raw.strip()
    if orient not in ("TB", "LR"):
        raise ValueError(f"visual_dsl: orient must be exactly TB or LR; got {orient!r}")

    edges = []
    labels = {}
    order = []

    def _seen(n):
        if n not in order:
            order.append(n)

    for ln in lines[1:]:
        if " -> " in ln:
            segs = [[p.strip() for p in seg.split(",") if p.strip()]
                    for seg in ln.split(" -> ")]
            if any(not seg for seg in segs):
                raise ValueError(
                    f"visual_dsl: edge line has an empty segment (dangling '->'): {ln.strip()!r}")
            for a, b in zip(segs, segs[1:]):
                for u in a:
                    for v in b:
                        edges.append((u, v))
                        _seen(u)
                        _seen(v)
        elif " : " in ln:
            ident, _, lab = ln.strip().partition(" : ")
            labels[ident.strip()] = lab
        else:
            raise ValueError(
                f"visual_dsl: unrecognized body line (need a ' -> ' edge or a ' : ' label): {ln.strip()!r}")

    nodes = list(dict.fromkeys(order + [k for k in labels if k not in order]))
    if not edges and not labels:
        raise ValueError("visual_dsl: graph has no edges and no labels — nothing to draw")
    return nodes, edges, labels, title, orient



