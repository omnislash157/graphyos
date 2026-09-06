
from __future__ import annotations

import re

from .models import CodeBlock

_ACCESS_RE = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2}[ T][0-9:.,]+)?[^"\n]*'
    r'"(?P<method>GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(?P<target>\S+)\s+HTTP/[\d.]+"\s+'
    r'(?P<status>\d{3})(?:[^\n]*?\b(?P<latency>\d+(?:\.\d+)?)\s*ms)?'
)

_NUM_SEG = re.compile(r"^\d+$")
_UUID_SEG = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def normalize_route(target: str) -> str:
    path = target.split("?", 1)[0]
    out = []
    for seg in path.split("/"):
        if not seg:
            out.append(seg)
            continue
        if _NUM_SEG.match(seg) or _UUID_SEG.match(seg) or "@" in seg or "%40" in seg:
            out.append("{}")
        else:
            out.append(seg)
    return "/".join(out) or "/"


def route_query_pattern(term: str) -> "re.Pattern":
    parts = [re.escape(p) for p in term.split("{}")]
    body = r'[^/\s"?]+'.join(parts)
    return re.compile(body + r"(?![\w./-])")


def find_log_blocks(source: str) -> list[CodeBlock]:
    blocks: list[CodeBlock] = []
    pos = 0
    for lineno, line in enumerate(source.split("\n"), start=1):
        m = _ACCESS_RE.match(line)
        if m:
            attrs: dict = {
                "method": m.group("method"),
                "status": int(m.group("status")),
            }
            if m.group("ts"):
                attrs["timestamp"] = m.group("ts")
            if m.group("latency"):
                attrs["latency_ms"] = float(m.group("latency"))
            blocks.append(CodeBlock(
                block_type="log_route",
                name=normalize_route(m.group("target")),
                start_line=lineno,
                end_line=lineno,
                start_char=pos,
                end_char=pos + len(line),
                attrs=attrs,
            ))
        pos += len(line) + 1
    return blocks
