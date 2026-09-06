
from __future__ import annotations

import bisect
import re

from .models import CodeBlock

_EXCHANGE_RE = re.compile(r"^--- \[(\d+)\] (USER|ASSISTANT)$", re.MULTILINE)


def has_exchanges(source: str) -> bool:
    return _EXCHANGE_RE.search(source) is not None


def find_prose_blocks(source: str) -> list[CodeBlock]:
    marks = list(_EXCHANGE_RE.finditer(source))
    if not marks:
        return []

    line_starts = [0]
    for line in source.split("\n"):
        line_starts.append(line_starts[-1] + len(line) + 1)

    def _line_of(char_pos: int) -> int:
        return bisect.bisect_right(line_starts, char_pos)

    blocks: list[CodeBlock] = []
    for i, m in enumerate(marks):
        start = m.start()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(source)
        blocks.append(CodeBlock(
            block_type="exchange",
            name=f"[{m.group(1)}] {m.group(2)}",
            start_line=_line_of(start),
            end_line=_line_of(max(start, end - 1)),
            start_char=start,
            end_char=end,
            attrs={"exchange": int(m.group(1)), "speaker": m.group(2)},
        ))
    return blocks
