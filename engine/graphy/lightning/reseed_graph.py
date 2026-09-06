from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .archive import sessions_dir

SESSIONS = sessions_dir()

_EX_RE = re.compile(r"^---\s*\[(\d+)\]\s*(?:USER|ASSISTANT)\s*$", re.MULTILINE)
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]{2,}")
_SEG_RE = re.compile(r"[._\-]")
_HEAT = "░▒▓█"

STOP = {
    "the", "and", "for", "are", "was", "were", "been", "being", "have", "has",
    "had", "does", "did", "will", "would", "could", "should", "can", "may",
    "might", "must", "shall", "not", "with", "from", "this", "that", "these",
    "those", "there", "here", "then", "than", "them", "they", "their", "its",
    "it's", "into", "onto", "over", "under", "about", "after", "before",
    "between", "through", "during", "each", "every", "both", "other", "another",
    "such", "same", "some", "any", "all", "more", "most", "less", "many",
    "few", "now", "just", "only", "very", "really", "actually", "already",
    "still", "even", "ever", "never", "also", "too", "you", "your", "our",
    "what", "when", "where", "how", "why", "who", "which", "but", "out",
    "one", "two", "three", "new", "get", "got", "let", "lets", "like",
    "user", "assistant", "yes", "yeah", "okay", "don", "doesn", "isn",
    "want", "need", "make", "made", "use", "used", "using", "way", "thing",
    "things", "right", "good", "back", "see", "say", "said", "know",
}


@dataclass
class Box:
    fidx: int
    exchange: int
    start: int
    end: int


@dataclass
class Corpus:
    root: Path
    files: list[Path] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    boxes: list[Box] = field(default_factory=list)
    post: dict[str, dict[int, int]] = field(default_factory=dict)
    unreadable: list[str] = field(default_factory=list)
    on_disk: int = 0

    @property
    def shortfall(self) -> int:
        return self.on_disk - len(self.files)


_DATE_STAMP_RE = re.compile(r"__(\d{8})T\d{6}Z__")


def _date_of(path: Path) -> str:
    m = _DATE_STAMP_RE.search(path.name)
    if m:
        t = m.group(1)
        return f"{t[:4]}-{t[4:6]}-{t[6:8]}"
    return "????-??-??"


def _norm(tok: str) -> str:
    return tok.lower().strip(".-")


def build(root: Path, glob: str) -> Corpus:
    c = Corpus(root=root)
    paths = sorted(p for p in ([root] if root.is_file() else root.rglob(glob)) if p.is_file())
    c.on_disk = len(paths)
    post: dict[str, dict[int, int]] = defaultdict(dict)
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            c.unreadable.append(f"{path.name}: {exc}")
            continue
        fidx = len(c.files)
        c.files.append(path)
        c.dates.append(_date_of(path))
        c.texts.append(text)
        marks = [(m.start(), int(m.group(1))) for m in _EX_RE.finditer(text)]
        spans: list[tuple[int, int, int]] = []
        if not marks:
            spans.append((0, 0, len(text)))
        else:
            if marks[0][0] > 0:
                spans.append((0, 0, marks[0][0]))
            i = 0
            while i < len(marks):
                ex = marks[i][1]
                start = marks[i][0]
                j = i
                while j + 1 < len(marks) and marks[j + 1][1] == ex:
                    j += 1
                end = marks[j + 1][0] if j + 1 < len(marks) else len(text)
                spans.append((ex, start, end))
                i = j + 1
        for ex, start, end in spans:
            bid = len(c.boxes)
            c.boxes.append(Box(fidx=fidx, exchange=ex, start=start, end=end))
            for m in _TOKEN_RE.finditer(text, start, end):
                t = _norm(m.group(0))
                if len(t) < 3 or t in STOP:
                    continue
                bucket = post[t]
                bucket[bid] = bucket.get(bid, 0) + 1
    c.post = dict(post)
    return c


def _sessions_of(c: Corpus, bids: set[int]) -> set[int]:
    return {c.boxes[b].fidx for b in bids}


def _segments(sym: str) -> tuple[str, ...]:
    return tuple(s for s in _SEG_RE.split(sym)
                 if len(s) >= 3 and not s.isdigit() and s not in STOP)


def _subseq(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    n = len(a)
    if not n or n >= len(b):
        return False
    return any(b[i:i + n] == a for i in range(len(b) - n + 1))


@dataclass
class Forest:
    live: dict[str, set[int]]
    anchors: set[str]
    syms: dict[str, tuple[str, ...]]
    children: dict[str, list[str]]
    roots: list[str]


def topic_forest(c: Corpus, min_ex: int, max_sdf: float, min_family: int) -> Forest:
    ses_ceiling = max_sdf * max(1, len(c.files))
    live: dict[str, set[int]] = {}
    for t, p in c.post.items():
        if len(p) < min_ex:
            continue
        bids = set(p)
        if len(_sessions_of(c, bids)) > ses_ceiling:
            continue
        live[t] = bids
    syms = {t: segs for t in live if _SEG_RE.search(t) and (segs := _segments(t))}
    family: dict[str, set[str]] = defaultdict(set)
    for s, segs in syms.items():
        for seg in set(segs):
            family[seg].add(s)
    anchors = {w for w, fam in family.items()
               if w in live and w not in syms and len(fam) >= min_family}
    parent: dict[str, str] = {}
    for s, segs in syms.items():
        best = None
        for y in {cand for seg in set(segs) for cand in family[seg]}:
            ysegs = syms[y]
            if y == s or len(ysegs) >= len(segs):
                continue
            if _subseq(ysegs, segs) and (best is None or len(ysegs) > len(syms[best])):
                best = y
        if best is None:
            in_anchor = [w for w in set(segs) if w in anchors]
            if in_anchor:
                best = max(in_anchor, key=lambda w: len(live[w]))
        if best:
            parent[s] = best
    children: dict[str, list[str]] = defaultdict(list)
    for x, y in parent.items():
        children[y].append(x)
    roots = list(anchors) + [s for s in syms if s not in parent]
    return Forest(live=live, anchors=anchors, syms=syms, children=dict(children), roots=roots)


def _bar(frac: float, width: int = 14) -> str:
    filled = max(0.0, min(1.0, frac)) * width
    out = []
    for i in range(width):
        lvl = min(1.0, max(0.0, filled - i))
        out.append(_HEAT[min(3, int(lvl * 4))] if lvl > 0 else _HEAT[0])
    return "".join(out)


def header(c: Corpus, mode: str) -> None:
    print(f"# RESEED GRAPH · {mode}  ·  corpus {c.root}")
    cov = f"{len(c.files)}/{c.on_disk} files indexed"
    if c.shortfall:
        cov += f"  ⚠ {c.shortfall} INVISIBLE: " + "; ".join(c.unreadable)
    print(f"  COVERAGE {cov}  ·  {len(c.boxes)} exchange containers  ·  "
          f"{len(c.post)} terms")
    print("  NOMINATES exchanges — intensity is discussion, never closure; the walk settles it.\n")


def cmd_topics(c: Corpus, a: argparse.Namespace) -> int:
    f = topic_forest(c, a.min_ex, a.max_sdf, a.min_family)

    def mass(t: str) -> int:
        return len(f.live[t]) + sum(mass(k) for k in f.children.get(t, []))

    def show(term: str, depth: int, biggest: int) -> None:
        ex = f.live[term]
        ses = len(_sessions_of(c, ex))
        print(f"  {'    ' * depth}{_bar(len(ex) / biggest)} {len(ex):>5} ex · {ses:>3} ses  {term}")
        if depth < a.depth:
            kids = sorted(f.children.get(term, []), key=lambda t: len(f.live[t]), reverse=True)
            for kid in kids[: a.kids]:
                show(kid, depth + 1, biggest)
            if len(kids) > a.kids:
                print(f"  {'    ' * (depth + 1)}… {len(kids) - a.kids} more — "
                      f"topics --under {term}")

    if a.under:
        t = _norm(a.under)
        if t not in f.live:
            print(f"  `{a.under}` is not a topic at min-ex={a.min_ex} min-family={a.min_family}")
            return 1
        show(t, 0, max(1, len(f.live[t])))
        return 0
    roots = sorted(f.roots, key=mass, reverse=True)
    biggest = max(1, len(f.live[roots[0]])) if roots else 1
    for r in roots[: a.top]:
        show(r, 0, biggest)
    return 0


def _resolve(c: Corpus, terms: list[str]) -> tuple[list[str], list[set[int]], list[str]]:
    named, sets, missing = [], [], []
    for raw in terms:
        t = _norm(raw)
        p = c.post.get(t)
        if p:
            named.append(t)
            sets.append(set(p))
        else:
            missing.append(raw)
    return named, sets, missing


def _snippet(c: Corpus, bid: int, term: str, width: int) -> str:
    box = c.boxes[bid]
    text = c.texts[box.fidx]
    m = re.search(re.escape(term), text[box.start:box.end], re.I)
    at = box.start + (m.start() if m else 0)
    lo = max(box.start, at - width // 2)
    hi = min(box.end, at + width // 2)
    return re.sub(r"\s+", " ", text[lo:hi]).strip()


def cmd_search(c: Corpus, a: argparse.Namespace) -> int:
    named, sets, missing = _resolve(c, a.terms)
    for raw in missing:
        print(f"  ZERO `{raw}` — the term appears nowhere in the corpus.")
    if not named:
        return 1
    hits = set.union(*sets) if a.any else set.intersection(*sets)
    mode = "ANY" if a.any else "SAME EXCHANGE (all terms)"
    print(f"## `{'` + `'.join(named)}`  ·  {mode}  ·  {len(hits)} exchange(s) in "
          f"{len(_sessions_of(c, hits))} session(s)\n")
    if not hits:
        return 1
    scored = sorted(hits, key=lambda b: (sum(c.post[t].get(b, 0) for t in named), b), reverse=True)
    for bid in scored[: a.top]:
        box = c.boxes[bid]
        n = sum(c.post[t].get(bid, 0) for t in named)
        print(f"  {c.dates[box.fidx]}  ex {box.exchange:>3}  {n:>3} hits  {c.files[box.fidx].name}")
        if a.snippet:
            print(f"       … {_snippet(c, bid, named[0], a.snippet)}")
    return 0


def cmd_heat(c: Corpus, a: argparse.Namespace) -> int:
    named, sets, missing = _resolve(c, a.terms)
    for raw in missing:
        print(f"  ZERO `{raw}` — the term appears nowhere in the corpus.")
    if not named:
        return 1
    pool = set.union(*sets)
    joint = set.intersection(*sets) if len(sets) > 1 else None
    if joint is not None:
        print(f"## JOINT — {len(joint)} exchange(s) hold ALL of {named}\n")
        for bid in sorted(joint, key=lambda b: sum(c.post[t].get(b, 0) for t in named),
                          reverse=True)[:5]:
            box = c.boxes[bid]
            print(f"  {c.dates[box.fidx]}  ex {box.exchange:>3}  {c.files[box.fidx].name}")
        print()
    f = topic_forest(c, a.min_ex, a.max_sdf, a.min_family)
    fan = []
    for t, ex in f.live.items():
        if t in named or (t not in f.anchors and t not in f.syms):
            continue
        overlap = len(ex & pool)
        if overlap:
            fan.append((overlap, t, ex))
    fan.sort(reverse=True)
    fan = fan[: a.fanout]
    print(f"## FAN-OUT — top {len(fan)} topics riding the same exchanges  "
          f"(cell = % of seed's exchanges the topic shares)\n")
    head = "  ".join(f"{t[:14]:>14}" for t in named)
    print(f"  {'topic':<28}{head}" + ("   JOINT" if joint is not None else ""))
    for _, t, ex in fan:
        cells = []
        for s in sets:
            pct = len(ex & s) / len(s)
            cells.append(f"{_bar(pct, 8)} {100 * pct:3.0f}%")
        row = "  ".join(f"{cell:>14}" for cell in cells)
        tail = ""
        if joint is not None:
            jp = len(ex & joint) / len(joint) if joint else 0.0
            tail = f"   {100 * jp:3.0f}%"
        print(f"  {t:<28}{row}{tail}")
    return 0 if fan else 1


def cmd_chain(c: Corpus, a: argparse.Namespace) -> int:
    named, sets, _ = _resolve(c, [a.term])
    if not named:
        print(f"  ZERO `{a.term}` — the term appears nowhere in the corpus.")
        return 1
    term, bids = named[0], sets[0]
    by_file: dict[int, list[int]] = defaultdict(list)
    for bid in bids:
        by_file[c.boxes[bid].fidx].append(bid)
    print(f"## `{term}` across time — {len(by_file)} session(s), oldest first\n")
    for fidx in sorted(by_file):
        rows = sorted(by_file[fidx], key=lambda b: c.boxes[b].exchange)
        exs = [c.boxes[b].exchange for b in rows]
        hits = sum(c.post[term][b] for b in rows)
        span = f"ex {exs[0]}" if len(exs) == 1 else f"ex {exs[0]}-{exs[-1]} ({len(exs)} boxes)"
        print(f"  {c.dates[fidx]}  {hits:>4} hits  {span:<22}  {c.files[fidx].name}")
        if a.snippet:
            hot = max(rows, key=lambda b: c.post[term][b])
            print(f"       … {_snippet(c, hot, term, a.snippet)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="reseed_graph",
        description="Stateless topic graph over the /clear reseed session corpus — "
                    "symbol-segment (AST-shaped) hierarchy, exchange-grain co-occurrence, "
                    "session daisy-chain.")
    ap.add_argument("--path", type=Path, default=SESSIONS, help="corpus root")
    ap.add_argument("-g", "--glob", default="*.md")
    ap.add_argument("--min-ex", type=int, default=6, help="min exchanges for a topic term")
    ap.add_argument("--max-sdf", type=float, default=0.9,
                    help="drop terms in more than this fraction of sessions (format scaffold)")
    ap.add_argument("--min-family", type=int, default=2,
                    help="a plain word anchors a topic only if it segments >= this many symbols")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("topics", help="the symbol-segment hierarchy, discussion-weighted")
    t.add_argument("--under", help="show one subtree")
    t.add_argument("--depth", type=int, default=2)
    t.add_argument("--top", type=int, default=20, help="roots to print")
    t.add_argument("--kids", type=int, default=6, help="children shown per node")

    s = sub.add_parser("search", help="exchanges holding the term(s)")
    s.add_argument("terms", nargs="+")
    s.add_argument("--any", action="store_true", help="union instead of same-exchange AND")
    s.add_argument("--top", type=int, default=15)
    s.add_argument("--snippet", type=int, default=220)

    h = sub.add_parser("heat", help="co-occurrence fan-out intensity map")
    h.add_argument("terms", nargs="+")
    h.add_argument("--fanout", type=int, default=12)

    ch = sub.add_parser("chain", help="one term daisy-chained across sessions in time")
    ch.add_argument("term")
    ch.add_argument("--snippet", type=int, default=0)

    a = ap.parse_args(argv)
    if not a.path.exists():
        print(f"CORPUS ABSENT: {a.path} — nothing was searched, and that is not a miss.",
              file=sys.stderr)
        return 2
    c = build(a.path, a.glob)
    if not c.files:
        print(f"CORPUS EMPTY: no files matching {a.glob!r} under {a.path}", file=sys.stderr)
        return 2
    header(c, a.cmd)
    rc = {"topics": cmd_topics, "search": cmd_search, "heat": cmd_heat, "chain": cmd_chain}[a.cmd](c, a)
    if c.shortfall or c.unreadable:
        print(f"\n  ⚠ COVERAGE SHORTFALL — {c.shortfall} file(s) on disk were not indexed. Exit 3.",
              file=sys.stderr)
        return 3
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
