from __future__ import annotations

import argparse
import re
import sys
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path

from .archive import sessions_dir

SESSIONS = sessions_dir()

_WORD_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")
_EX_RE = re.compile(r"^---\s*\[(\d+)\]\s*(?:USER|ASSISTANT)\s*$", re.MULTILINE)

_HEAT_CHARS = "░▒▓█"


@dataclass
class Cluster:
    start_tok: int
    end_tok: int
    start_char: int
    end_char: int
    hits: int = 0
    partner_hits: int = 0
    window: int = 10
    exchanges: tuple[int, int] | None = None

    @property
    def span(self) -> int:
        return max(1, self.end_tok - self.start_tok + 1 + 2 * self.window)

    @property
    def density(self) -> float:
        return 100.0 * (self.hits + self.partner_hits) / self.span

    @property
    def both(self) -> bool:
        return self.hits > 0 and self.partner_hits > 0


@dataclass
class FileTrail:
    path: Path
    tokens: int
    hits: int
    partner_hits: int
    clusters: list[Cluster] = field(default_factory=list)

    @property
    def heat(self) -> float:
        return 1000.0 * (self.hits + self.partner_hits) / max(1, self.tokens)


def _matcher(term: str) -> re.Pattern[str]:
    t = term.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]+", t):
        return re.compile(rf"\b{re.escape(t)}\b", re.I)
    return re.compile(re.escape(t), re.I)


def _exchange_marks(text: str) -> tuple[list[int], list[int]]:
    offs, nums = [], []
    for m in _EX_RE.finditer(text):
        offs.append(m.start())
        nums.append(int(m.group(1)))
    return offs, nums


def trail_file(path: Path, term_rx: re.Pattern[str], window: int,
               partner_rx: re.Pattern[str] | None) -> FileTrail | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        print(f"  UNREADABLE {path.name}: {exc}", file=sys.stderr)
        return None

    toks = [(m.group(0), m.start()) for m in _WORD_RE.finditer(text)]
    if not toks:
        return None
    starts = [s for _, s in toks]

    def tok_index(char_off: int) -> int:
        return max(0, bisect_right(starts, char_off) - 1)

    hit_idx = [tok_index(m.start()) for m in term_rx.finditer(text)]
    partner_idx = [tok_index(m.start()) for m in partner_rx.finditer(text)] if partner_rx else []
    if not hit_idx:
        return None

    seeds = sorted((i, "t") for i in hit_idx)
    if partner_rx:
        seeds = sorted(seeds + [(i, "p") for i in partner_idx])

    clusters: list[Cluster] = []
    cur: Cluster | None = None
    for idx, kind in seeds:
        if cur is not None and idx - cur.end_tok <= window:
            cur.end_tok = idx
        else:
            if cur is not None:
                clusters.append(cur)
            cur = Cluster(start_tok=idx, end_tok=idx, start_char=0, end_char=0,
                          window=window)
        if kind == "t":
            cur.hits += 1
        else:
            cur.partner_hits += 1
    if cur is not None:
        clusters.append(cur)

    clusters = [c for c in clusters if c.hits > 0]
    if not clusters:
        return None

    offs, nums = _exchange_marks(text)
    for c in clusters:
        lo = max(0, c.start_tok - window)
        hi = min(len(toks) - 1, c.end_tok + window)
        c.start_char = toks[lo][1]
        c.end_char = toks[hi][1] + len(toks[hi][0])
        if offs:
            a = bisect_right(offs, toks[c.start_tok][1]) - 1
            b = bisect_right(offs, toks[c.end_tok][1]) - 1
            if a >= 0 and b >= 0:
                c.exchanges = (nums[a], nums[b])

    return FileTrail(path=path, tokens=len(toks), hits=len(hit_idx),
                     partner_hits=len(partner_idx), clusters=clusters)


def _bar(frac: float, width: int = 16) -> str:
    filled = frac * width
    out = []
    for i in range(width):
        lvl = min(1.0, max(0.0, filled - i))
        out.append(_HEAT_CHARS[min(3, int(lvl * 4))] if lvl > 0 else _HEAT_CHARS[0])
    return "".join(out)


def run(term: str, root: Path, *, window: int, partner: str | None,
        top: int, glob: str, show: int, snippet: int) -> int:
    if not root.exists():
        print(f"CORPUS ABSENT: {root} — nothing was searched, and that is not a miss.",
              file=sys.stderr)
        return 2
    files = sorted(p for p in ([root] if root.is_file() else root.rglob(glob)) if p.is_file())
    if not files:
        print(f"CORPUS EMPTY: no files matching {glob!r} under {root}", file=sys.stderr)
        return 2

    term_rx = _matcher(term)
    partner_rx = _matcher(partner) if partner else None
    trails = [t for t in (trail_file(p, term_rx, window, partner_rx) for p in files) if t]

    label = f"`{term}`" + (f" × `{partner}`" if partner else "")
    print(f"# BLOODHOUND — {label}  ·  window ±{window} tokens")
    print(f"  corpus: {root}  ·  {len(files)} files searched  ·  {len(trails)} with hits\n")
    if not trails:
        print(f"  NO HITS. {len(files)} files were read — this is a real miss, not an absent corpus.")
        return 1

    if partner_rx:
        both = [t for t in trails if any(c.both for c in t.clusters)]
        print(f"  co-occurrence: {len(both)} file(s) hold BOTH terms within ±{window} tokens\n")

    trails.sort(key=lambda t: t.heat, reverse=True)
    hottest = trails[0].heat or 1.0
    print(f"## HEAT — which files this term DOMINATES (hits per 1k tokens)\n")
    for t in trails[:top]:
        flag = " ←BOTH" if partner_rx and any(c.both for c in t.clusters) else ""
        print(f"  {_bar(t.heat / hottest)}  {t.heat:6.1f}  {t.hits:>4} hits  "
              f"{len(t.clusters):>3} clu  {t.path.name[:44]}{flag}")

    print(f"\n## CLUSTERS — the daisy-chained spans, hottest file first\n")
    for t in trails[:show]:
        print(f"### {t.path.name}   ({t.hits} hits · {t.tokens} tokens)")
        text = t.path.read_text(encoding="utf-8", errors="ignore")
        ranked = sorted(t.clusters, key=lambda c: (c.both, c.density, c.hits), reverse=True)
        for c in ranked[:top]:
            where = f"ex {c.exchanges[0]}-{c.exchanges[1]}" if c.exchanges else f"tok {c.start_tok}"
            mark = "BOTH" if c.both else f"{c.hits}x"
            print(f"  [{where:>12}]  {mark:>5}  density {c.density:5.1f}  span {c.span:>4} tok")
            if snippet:
                body = re.sub(r"\s+", " ", text[c.start_char:c.end_char]).strip()
                print(f"       … {body[:snippet]}{'…' if len(body) > snippet else ''}")
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="bloodhound",
        description="Proximity trail + heat map: keyword -> daisy-chained clusters -> heat.")
    ap.add_argument("term")
    ap.add_argument("--with", dest="partner", help="second term — co-occurrence WITHIN the window")
    ap.add_argument("-w", "--window", type=int, default=10,
                    help="token radius that daisy-chains two hits (default 10; try 20 or 50)")
    ap.add_argument("--path", type=Path, default=SESSIONS,
                    help="corpus (default: the /clear session archive)")
    ap.add_argument("-g", "--glob", default="*.md", help="file pattern (default *.md)")
    ap.add_argument("--top", type=int, default=12, help="rows per section")
    ap.add_argument("--show", type=int, default=3, help="files to expand into clusters")
    ap.add_argument("--snippet", type=int, default=200,
                    help="chars of cluster text to print (0 = coordinates only)")
    a = ap.parse_args(argv)
    if a.window < 1:
        print("--window must be >= 1", file=sys.stderr)
        return 2
    return run(a.term, a.path, window=a.window, partner=a.partner,
               top=a.top, glob=a.glob, show=a.show, snippet=a.snippet)


if __name__ == "__main__":
    raise SystemExit(main())
