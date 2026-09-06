from __future__ import annotations

import io
import logging
import tokenize
from pathlib import Path

log = logging.getLogger(__name__)

CODE = "code"
PROSE = "prose"
UNKNOWN = "unknown"

UNTOKENIZABLE = object()

_EOL = 1 << 30


def _prose_spans(source: str, path: str) -> dict[int, list[tuple[int, int]]] | object:
    spans: dict[int, list[tuple[int, int]]] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type not in (tokenize.COMMENT, tokenize.STRING):
                continue
            (srow, scol), (erow, ecol) = tok.start, tok.end
            if srow == erow:
                spans.setdefault(srow, []).append((scol, ecol))
            else:
                spans.setdefault(srow, []).append((scol, _EOL))
                for row in range(srow + 1, erow):
                    spans.setdefault(row, []).append((0, _EOL))
                spans.setdefault(erow, []).append((0, ecol))
    except (tokenize.TokenError, IndentationError, SyntaxError) as exc:
        log.warning("hit_kind: cannot tokenize %s (%s: %s) — hits there stay UNKNOWN "
                    "and are counted LIVE", path, type(exc).__name__, exc)
        return UNTOKENIZABLE
    return spans


def classify_file_lines(path: Path | str, line_nos: list[int], pattern) -> dict[int, str]:
    p = Path(path)
    if p.suffix != ".py":
        return {ln: UNKNOWN for ln in line_nos}

    source = p.read_text(encoding="utf-8", errors="replace")
    spans = _prose_spans(source, str(p))
    if spans is UNTOKENIZABLE:
        return {ln: UNKNOWN for ln in line_nos}

    lines = source.splitlines()
    out: dict[int, str] = {}
    for ln in line_nos:
        if ln < 1 or ln > len(lines):
            out[ln] = UNKNOWN
            continue
        hits = list(pattern.finditer(lines[ln - 1]))
        if not hits:
            out[ln] = UNKNOWN
            continue
        line_spans = spans.get(ln, [])
        covered = sum(
            1 for m in hits
            if any(s <= m.start() and m.end() <= e for s, e in line_spans)
        )
        out[ln] = PROSE if covered == len(hits) else CODE
    return out


def is_prose_only(kinds: dict[int, str]) -> bool:
    return bool(kinds) and all(k == PROSE for k in kinds.values())
