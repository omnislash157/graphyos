
from __future__ import annotations

import re
from pathlib import Path

from ..models import CodeBlock
from .brace import brace_block
from .svelte import split_svelte



_RE_FUNCTION = re.compile(
    r"""^\s*(?P<exp>export\s+)?(?:default\s+)?(?P<async>async\s+)?function\s+(?P<name>\w+)\s*\(""",
    re.MULTILINE,
)

_RE_ARROW_CONST = re.compile(
    r"""^\s*(?P<exp>export\s+)?const\s+(?P<name>\w+)\s*(?::\s*[^=]+)?\s*=\s*(?P<async>async\s+)?\(""",
    re.MULTILINE,
)

_RE_CLASS = re.compile(
    r"""^\s*(?P<exp>export\s+)?(?:default\s+)?class\s+(?P<name>\w+)(?:\s+extends\s+(?P<base>\w+))?\s*\{""",
    re.MULTILINE,
)

_BRACE_DECL_LANGS = frozenset({"ts", "tsx", "js", "jsx", "svelte", "typescript", "javascript"})

_BRACE_DECL_LANGS_RS_GO = frozenset({"rs", "rust", "go", "golang"})


_RE_RUST_FN = re.compile(
    r"""^\s*(?:pub(?:\([^)]*\))?\s+)?(?:const\s+)?(?:async\s+)?(?:unsafe\s+)?(?:extern\s+"[^"]*"\s+)?fn\s+(?P<name>\w+)""",
    re.MULTILINE,
)
_RE_RUST_IMPL = re.compile(
    r"""^\s*impl(?:\s*<[^>]*>)?\s+(?:[\w:]+(?:<[^>]*>)?\s+for\s+)?(?P<name>[\w:]+)""",
    re.MULTILINE,
)
_RE_RUST_TYPE = re.compile(
    r"""^\s*(?:pub(?:\([^)]*\))?\s+)?(?:struct|enum|trait|union)\s+(?P<name>\w+)""",
    re.MULTILINE,
)
_RE_GO_FUNC = re.compile(
    r"""^\s*func\s+(?:\([^)]*\)\s*)?(?P<name>\w+)""",
    re.MULTILINE,
)
_RE_GO_TYPE = re.compile(
    r"""^\s*type\s+(?P<name>\w+)(?:\[[^\]]*\])?\s+(?:struct|interface)\s*\{""",
    re.MULTILINE,
)


def _find_body_brace(text: str, start: int) -> int:
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0:
            if ch == "{":
                return i
            if ch == ";":
                return -1
    return -1


def _find_blocks_rust_go(source: str, lang: str) -> list[CodeBlock]:
    if lang in ("rs", "rust"):
        decl_patterns = [
            ("function", _RE_RUST_FN, False),
            ("class", _RE_RUST_IMPL, False),
            ("class", _RE_RUST_TYPE, False),
        ]
    else:
        decl_patterns = [
            ("function", _RE_GO_FUNC, False),
            ("class", _RE_GO_TYPE, True),
        ]

    blocks: list[CodeBlock] = []
    seen_spans: set[tuple[int, int]] = set()
    for block_type, pattern, brace_in_match in decl_patterns:
        for m in pattern.finditer(source):
            if brace_in_match:
                open_brace_pos = m.end() - 1
            else:
                open_brace_pos = _find_body_brace(source, m.end())
                if open_brace_pos == -1:
                    continue
            _body, close_pos = brace_block(source, open_brace_pos)

            leading_ws = len(m.group()) - len(m.group().lstrip())
            start = m.start() + leading_ws
            span = (start, close_pos)
            if span in seen_spans:
                continue
            seen_spans.add(span)

            blocks.append(CodeBlock(
                block_type=block_type,
                name=m.group("name"),
                start_char=start,
                end_char=close_pos + 1,
                start_line=_line_of(source, start),
                end_line=_line_of(source, close_pos),
            ))
    return blocks


def _line_of(text: str, pos: int, base: int = 1) -> int:
    return text[:pos].count("\n") + base


def _find_blocks_in_script(
    script_text: str,
    script_start_char: int,
    script_start_line: int,
) -> list[CodeBlock]:
    blocks: list[CodeBlock] = []
    decl_patterns = [
        ("function", _RE_FUNCTION),
        ("function", _RE_ARROW_CONST),
        ("class", _RE_CLASS),
    ]

    for block_type, pattern in decl_patterns:
        for m in pattern.finditer(script_text):
            name = m.group("name")
            if pattern is _RE_CLASS:
                open_brace_pos = m.end() - 1
            else:
                search_from = m.end() - 1
                open_brace_pos = _find_open_brace(
                    script_text, search_from, is_arrow=(pattern is _RE_ARROW_CONST)
                )
                if open_brace_pos == -1:
                    continue

            clean_body, close_pos = brace_block(script_text, open_brace_pos)

            local_start_raw = m.start()
            leading_ws = len(m.group()) - len(m.group().lstrip())
            local_start = local_start_raw + leading_ws
            local_end = close_pos

            abs_start_char = script_start_char + local_start
            abs_end_char = script_start_char + local_end + 1

            abs_start_line = script_start_line + script_text[:local_start].count("\n")
            abs_end_line = script_start_line + script_text[:local_end].count("\n")

            blocks.append(CodeBlock(
                block_type=block_type,
                name=name,
                start_char=abs_start_char,
                end_char=abs_end_char,
                start_line=abs_start_line,
                end_line=abs_end_line,
            ))

    return blocks


def _find_open_brace(text: str, paren_pos: int, is_arrow: bool = False) -> int:
    n = len(text)
    i = paren_pos

    def skip(i: int):
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = i + 2
            while j < n and text[j] != "\n":
                j += 1
            return j, True
        if c == "/" and nxt == "*":
            j = i + 2
            while j < n and not (text[j] == "*" and j + 1 < n and text[j + 1] == "/"):
                j += 1
            return (j + 2 if j < n else n), True
        if c in "'\"`":
            quote = c
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == quote:
                    j += 1
                    break
                j += 1
            return j, True
        return i, False

    def balance(i: int, open_ch: str, close_ch: str) -> int:
        d = 0
        while i < n:
            i, sk = skip(i)
            if sk:
                continue
            c = text[i]
            if c == open_ch:
                d += 1
            elif c == close_ch:
                d -= 1
                i += 1
                if d == 0:
                    return i
                continue
            i += 1
        return i

    depth = 0
    started = False
    while i < n:
        i, sk = skip(i)
        if sk:
            continue
        c = text[i]
        if c in "([{":
            depth += 1
            started = True
        elif c in ")]}":
            depth -= 1
            i += 1
            if started and depth == 0:
                break
            continue
        i += 1

    if is_arrow:
        k = i
        has_anno = False
        while k < n:
            k, sk = skip(k)
            if sk:
                continue
            if text[k].isspace():
                k += 1
                continue
            has_anno = text[k] == ":"
            break
        arrows: list[int] = []
        j = i
        while j < n:
            j, sk = skip(j)
            if sk:
                continue
            c = text[j]
            nxt = text[j + 1] if j + 1 < n else ""
            if c == "(":
                j = balance(j, "(", ")")
                continue
            if c == "[":
                j = balance(j, "[", "]")
                continue
            if c == "{":
                j = balance(j, "{", "}")
                continue
            if c == "=" and nxt == ">":
                j += 2
                arrows.append(j)
                continue
            if c == ";":
                break
            j += 1
        if not arrows:
            return -1
        i = arrows[-1] if has_anno else arrows[0]
        while i < n:
            i, sk = skip(i)
            if sk:
                continue
            c = text[i]
            if c.isspace():
                i += 1
                continue
            return i if c == "{" else -1
        return -1

    expect_type = False
    while i < n:
        i, sk = skip(i)
        if sk:
            continue
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "{":
            if expect_type:
                i = balance(i, "{", "}")
                expect_type = False
                continue
            return i
        if c == ";":
            return -1
        if c == "=" and nxt == ">":
            expect_type = True
            i += 2
            continue
        if c in ":|&<(,[":
            expect_type = True
            i += 1
            continue
        if c.isspace():
            i += 1
            continue
        expect_type = False
        i += 1
    return -1


def find_brace_blocks(source: str, language: str) -> list[CodeBlock]:
    lang = language.lower()
    if lang in _BRACE_DECL_LANGS_RS_GO:
        return sorted(_find_blocks_rust_go(source, lang), key=lambda b: b.start_char)
    if lang not in _BRACE_DECL_LANGS:
        return []

    if lang == "svelte":
        return _find_blocks_svelte(source)

    blocks = _find_blocks_in_script(
        script_text=source,
        script_start_char=0,
        script_start_line=1,
    )
    return sorted(blocks, key=lambda b: b.start_char)


def _find_blocks_svelte(source: str) -> list[CodeBlock]:
    loc = source.count("\n") + 1

    stem_hint = "component"
    component_block = CodeBlock(
        block_type="component",
        name=stem_hint,
        start_char=0,
        end_char=len(source),
        start_line=1,
        end_line=loc,
    )

    script_text, _template, _style, script_start_char, script_start_line = split_svelte(source)
    if not script_text:
        return [component_block]

    script_blocks = _find_blocks_in_script(
        script_text=script_text,
        script_start_char=script_start_char,
        script_start_line=script_start_line,
    )

    return [component_block] + sorted(script_blocks, key=lambda b: b.start_char)


def find_brace_blocks_for_path(source: str, path: "str | Path") -> list[CodeBlock]:
    p = Path(path)
    suffix = p.suffix.lstrip(".").lower()
    if p.name.endswith(".svelte.ts"):
        suffix = "ts"
    if suffix == "svelte":
        return _find_blocks_svelte_with_stem(source, p.stem)
    return find_brace_blocks(source, suffix)


def _find_blocks_svelte_with_stem(source: str, stem: str) -> list[CodeBlock]:
    loc = source.count("\n") + 1

    component_block = CodeBlock(
        block_type="component",
        name=stem,
        start_char=0,
        end_char=len(source),
        start_line=1,
        end_line=loc,
    )

    script_text, _template, _style, script_start_char, script_start_line = split_svelte(source)
    if not script_text:
        return [component_block]

    script_blocks = _find_blocks_in_script(
        script_text=script_text,
        script_start_char=script_start_char,
        script_start_line=script_start_line,
    )

    return [component_block] + sorted(script_blocks, key=lambda b: b.start_char)
