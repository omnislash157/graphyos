
import bisect
import re
import time
from collections import defaultdict

from ..pattern_splinter import split_identifier

_MODULE = "<module>"
_TOK = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]{2,})\b")
_STOP = {
    "def", "class", "return", "import", "from", "self", "cls", "None", "True",
    "False", "async", "await", "const", "let", "var", "function", "export",
    "the", "and", "for", "not", "with", "this", "type", "value", "data", "name",
    "get", "set", "args", "kwargs", "result", "item", "key", "str", "int", "list",
    "dict", "bool", "path", "file", "line", "text", "count", "index",
}


def _footprint(
    lightning,
    term,
    file_pattern=None,
    max_files=500,
    *,
    regex=False,
    loose=False,
):
    res = lightning.hunt(
        term,
        regex=regex,
        file_pattern=file_pattern,
        max_files=max_files,
        loose=loose,
    )
    per_container: dict[tuple[str, str], list] = defaultdict(list)
    for fh in res.hits:
        for m in fh.matches:
            per_container[(fh.relative_path, m.containing_block or _MODULE)].append(m)
    return per_container, res.total_matches


def container_cooccur(lightning, terms, file_pattern=None, max_files=500):
    foot: dict[str, dict] = {}
    total: dict[str, int] = {}
    for t in terms:
        foot[t], total[t] = _footprint(lightning, t, file_pattern, max_files)
    containers = {t: set(foot[t].keys()) for t in terms}

    directed: dict[tuple[str, str], tuple[int, int, float]] = {}
    for a in terms:
        for b in terms:
            if a == b:
                continue
            inter = containers[a] & containers[b]
            denom = len(containers[a]) or 1
            directed[(a, b)] = (len(inter), len(containers[a]), len(inter) / denom)
    return {
        "terms": terms, "footprint": foot, "total": total,
        "containers": containers, "directed": directed,
    }


def _bar(pct: float, width: int = 10) -> str:
    filled = round(pct * width)
    return "█" * filled + "░" * (width - filled)


def _min_gap(ma: list, mb: list) -> tuple[int, int] | None:
    if not ma or not mb:
        return None
    b_starts = [m.start_char for m in mb]
    best: tuple[int, int] | None = None
    for a in ma:
        i = bisect.bisect_left(b_starts, a.start_char)
        for j in (i - 1, i):
            if not (0 <= j < len(mb)):
                continue
            b = mb[j]
            if a.end_char <= b.start_char:
                gap = b.start_char - a.end_char
            elif b.end_char <= a.start_char:
                gap = a.start_char - b.end_char
            else:
                gap = 0
            if best is None or gap < best[0]:
                best = (gap, min(a.line_number, b.line_number))
    return best


def container_cooccur_markdown(lightning, terms, file_pattern=None, max_files=500):
    start = time.perf_counter()
    r = container_cooccur(lightning, terms, file_pattern, max_files)
    terms, foot, total, containers, directed = (
        r["terms"], r["footprint"], r["total"], r["containers"], r["directed"])
    elapsed = (time.perf_counter() - start) * 1000

    tj = " × ".join(f"`{t}`" for t in terms)
    lines = [f"# CO-OCCURRENCE (container-level): {tj}", ""]
    lines.append(
        "  " + "   ".join(f"{t}: {total[t]} hits / {len(containers[t])} containers" for t in terms))
    lines.append("")

    lines.append("## DIRECTED CO-OCCURRENCE (asymmetric — which is inside which)")
    lines.append("")
    seen_pairs = set()
    for (a, b), (inter, denom, pct) in sorted(directed.items(), key=lambda kv: -kv[1][2]):
        lines.append(f"  {a:>16} → {b:<16} {_bar(pct)} {pct*100:5.1f}%   ({inter}/{denom} of {a}'s containers also hold {b})")
        if pct >= 0.999 and inter > 0 and (b, a) not in seen_pairs:
            rev = directed.get((b, a), (0, 1, 0.0))[2]
            if rev < 0.999:
                lines.append(f"      ⇒ `{a}` is CONTAINED in `{b}` (every {a} lives in a {b} container; reverse only {rev*100:.0f}%)")
        seen_pairs.add((a, b))
    lines.append("")

    shared_by_file: dict[str, dict] = defaultdict(dict)
    for t in terms:
        for (f, c), ms in foot[t].items():
            shared_by_file[f].setdefault(c, {})[t] = len(ms)
    files_with_share = []
    for f, conts in shared_by_file.items():
        if any(len(tm) >= 2 for tm in conts.values()):
            files_with_share.append(f)

    prox = []
    for f, conts in shared_by_file.items():
        for c, tm in conts.items():
            if len(tm) < 2:
                continue
            present = [t for t in terms if t in tm]
            best = None
            for i, a in enumerate(present):
                for b in present[i + 1:]:
                    g = _min_gap(foot[a].get((f, c), []), foot[b].get((f, c), []))
                    if g and (best is None or g[0] < best[0]):
                        best = (g[0], g[1], a, b)
            if best:
                prox.append((best[0], f, c, best[2], best[3], best[1]))
    if prox:
        prox.sort(key=lambda r: (r[0], r[1], r[2]))
        lines.append("## PROXIMITY — closest approach per container (a pointer, not a verdict)")
        lines.append("")
        lines.append("| gap (chars) | pair | container | file:line |")
        lines.append("|------------:|------|-----------|-----------|")
        for gap, f, c, a, b, ln in prox[:25]:
            lines.append(f"| {gap} | `{a}` × `{b}` | `{c}` | {f}:{ln} |")
        if len(prox) > 25:
            lines.append(f"\n_showing 25 of {len(prox)} co-occurring containers (ranked by distance)_")
        lines.append("")

    if files_with_share:
        lines.append("## SHARED CONTAINERS (≥2 terms in the same function/class)")
        lines.append("")
        for f in sorted(files_with_share):
            conts = shared_by_file[f]
            shared = {c: tm for c, tm in conts.items() if len(tm) >= 2}
            head = "  ·  ".join(f"{t}:{sum(1 for c in conts.values() if t in c)}" for t in terms)
            lines.append(f"### {f}   ({head}, shared:{len(shared)})")
            for c in sorted(shared):
                tm = shared[c]
                cells = "  ".join(f"{t}×{tm[t]}" for t in terms if t in tm)
                lines.append(f"    {c}   —   {cells}")
            lines.append("")

    lines.append(f"_{len(terms)} terms · {sum(len(containers[t]) for t in terms)} containers scanned · {elapsed:.0f}ms_")
    return "\n".join(lines)


def containers_of(
    lightning,
    term,
    file_pattern=None,
    max_files=500,
    *,
    regex=False,
    loose=False,
):
    per_container, total = _footprint(
        lightning,
        term,
        file_pattern,
        max_files,
        regex=regex,
        loose=loose,
    )
    rows = sorted(
        ((f, c, len(ms), min(m.line_number for m in ms)) for (f, c), ms in per_container.items()),
        key=lambda r: (-r[2], r[0]))
    return {"term": term, "total_matches": total, "containers": rows}


def containers_test_mode(
    lightning,
    term,
    file_pattern=None,
    max_files=500,
    *,
    regex=False,
    loose=False,
):
    from ..source_kind import classify_sources, liveness_verdict
    from ..hit_kind import PROSE, UNKNOWN, classify_file_lines
    from ..pattern_splinter import build_code_pattern
    r = containers_json(
        lightning,
        term,
        file_pattern,
        max_files,
        regex=regex,
        loose=loose,
    )
    kinds = classify_sources([c["file"] for c in r["containers"]], lightning.root_path)

    pattern = None if regex else build_code_pattern(term, case_insensitive=True, loose=loose)
    hit_kinds: dict = {}
    if pattern is not None:
        lines_by_file: dict = {}
        for c in r["containers"]:
            if c.get("line"):
                lines_by_file.setdefault(c["file"], []).append(c["line"])
        for f, lns in lines_by_file.items():
            hit_kinds[f] = classify_file_lines(lightning.root_path / f, lns, pattern)

    counts = {"live": 0, "test": 0, "slop": 0, "doc": 0, "prose": 0}
    for c in r["containers"]:
        sk = kinds[c["file"]]
        hk = hit_kinds.get(c["file"], {}).get(c.get("line"), UNKNOWN)
        c["source_kind"] = sk
        c["hit_kind"] = hk
        counts["prose" if (sk == "live" and hk == PROSE) else sk] += c["count"]
    r["liveness"] = {**counts, "verdict": liveness_verdict(counts)}
    return r


def containers_test_mode_markdown(
    lightning,
    term,
    file_pattern=None,
    max_files=500,
    *,
    regex=False,
    loose=False,
):
    r = containers_test_mode(
        lightning,
        term,
        file_pattern,
        max_files,
        regex=regex,
        loose=loose,
    )
    lv = r["liveness"]
    lines = [
        f"# LIVENESS of `{r['term']}` (test-mode: live-code referrers ONLY count)",
        f"**{lv['verdict']}**",
        f"live {lv['live']} · test {lv['test']} · slop {lv['slop']} · doc {lv['doc']}"
        f" · prose {lv.get('prose', 0)}  ({r['total_matches']} raw hits)",
        "",
    ]

    def _is_prose_row(c):
        return c["source_kind"] == "live" and c.get("hit_kind") == "prose"

    for kind, label in (("live", "LIVE-CODE referrers (proof-of-life)"),
                        ("prose", "PROSE referrers — live file, but the hit is a COMMENT or STRING "
                                  "(NOT proof-of-life: the fuzz matched text, not a call)"),
                        ("test", "TEST referrers (NOT proof-of-life)"),
                        ("slop", "SLOP referrers (gitignored / scratch — NOT proof-of-life)"),
                        ("doc", "DOC/EVIDENCE referrers (non-executable records — NOT proof-of-life)")):
        if kind == "prose":
            rows = [c for c in r["containers"] if _is_prose_row(c)]
        else:
            rows = [c for c in r["containers"]
                    if c["source_kind"] == kind and not _is_prose_row(c)]
        lines.append(f"## {label} — {len(rows)}")
        for c in rows:
            hk = c.get("hit_kind")
            tag = "" if hk in (None, "code") else f"  [hit:{hk}]"
            lines.append(f"  {c['count']:>3}  `{c['container']}`  {c['file']}:{c['line']}{tag}")
        lines.append("")
    return "\n".join(lines)


def containers_json(
    lightning,
    term,
    file_pattern=None,
    max_files=500,
    *,
    regex=False,
    loose=False,
):
    from ..block_blast import find_blocks
    r = containers_of(
        lightning,
        term,
        file_pattern,
        max_files,
        regex=regex,
        loose=loose,
    )
    attrs_by_file: dict = {}
    rows = []
    for f, c, n, ln in r["containers"]:
        container = c
        attrs: dict = {}
        if c and c.startswith("log_route:"):
            container = c.split(":", 1)[1]
            if f not in attrs_by_file:
                try:
                    src = (lightning.root_path / f).read_text(encoding="utf-8", errors="replace")
                    attrs_by_file[f] = {
                        b.name: b.attrs for b in reversed(find_blocks(src, "log"))
                    }
                except OSError:
                    attrs_by_file[f] = {}
            attrs = attrs_by_file[f].get(container, {})
        rows.append({"container": container, "count": n, "file": f, "line": ln, "attrs": attrs})
    return {"term": r["term"], "total_matches": r["total_matches"], "containers": rows}


def containers_markdown(
    lightning,
    term,
    file_pattern=None,
    max_files=500,
    *,
    regex=False,
    loose=False,
):
    r = containers_of(
        lightning,
        term,
        file_pattern,
        max_files,
        regex=regex,
        loose=loose,
    )
    lines = [
        f"# CONTAINERS of `{r['term']}`  —  {len(r['containers'])} functions/classes, {r['total_matches']} hits",
        "",
        "| hits | container | file:line |",
        "|-----:|-----------|-----------|",
    ]
    for f, c, n, ln in r["containers"]:
        lines.append(f"| {n} | `{c}` | {f}:{ln} |")
    return "\n".join(lines)


def container_neighbors(lightning, term, file_pattern=None, max_files=500, top_n=20):
    res = lightning.hunt(term, file_pattern=file_pattern, max_files=max_files)
    stop = set(_STOP) | {term.lower()} | {p.lower() for p in split_identifier(term)}
    counts: dict[str, int] = defaultdict(int)
    files: dict[str, set] = defaultdict(set)
    n_blocks = 0
    for fh in res.hits:
        for ch in fh.chunks:
            n_blocks += 1
            for tok in {m.group(1).lower() for m in _TOK.finditer(ch.text)}:
                if len(tok) < 3 or tok in stop:
                    continue
                counts[tok] += 1
                files[tok].add(fh.relative_path)
    top = sorted(((t, c) for t, c in counts.items() if c >= 2), key=lambda x: -x[1])[:top_n]
    return {"term": term, "blocks": n_blocks, "total_matches": res.total_matches,
            "neighbors": [{"term": t, "blocks": c, "files": len(files[t])} for t, c in top]}


def container_neighbors_markdown(lightning, term, file_pattern=None, max_files=500):
    r = container_neighbors(lightning, term, file_pattern, max_files)
    lines = [
        f"# NEIGHBORS of `{r['term']}`  —  shares {r['blocks']} functions/classes ({r['total_matches']} hits)",
        "", "_the identifiers that co-inhabit `" + term + "`'s containers (block-scoped, not a char window)_", "",
        "| co-inhabits | neighbor | files |",
        "|------------:|----------|-------|",
    ]
    for nb in r["neighbors"]:
        lines.append(f"| {nb['blocks']} | `{nb['term']}` | {nb['files']} |")
    return "\n".join(lines)


def storm_markdown(lightning, term, window=30, top_n=15, min_count=3,
                   file_pattern=None, max_files=None, search_path=".", with_terms=None):
    terms = [term] + list(with_terms or [])
    if len(terms) >= 2:
        return container_cooccur_markdown(lightning, terms, file_pattern, max_files or 500)
    return container_neighbors_markdown(lightning, term, file_pattern, max_files or 500)
