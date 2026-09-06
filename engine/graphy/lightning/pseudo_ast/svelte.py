
from __future__ import annotations

import re
from pathlib import Path


_RE_SCRIPT_OPEN = re.compile(r"""<script(?:\s[^>]*)?>""", re.IGNORECASE)
_RE_SCRIPT_CLOSE = re.compile(r"""</script>""", re.IGNORECASE)
_RE_STYLE_OPEN = re.compile(r"""<style(?:\s[^>]*)?>""", re.IGNORECASE)
_RE_STYLE_CLOSE = re.compile(r"""</style>""", re.IGNORECASE)


def split_svelte(text: str) -> tuple[str, str, str, int, int]:
    script_match = _RE_SCRIPT_OPEN.search(text)
    if not script_match:
        return "", text, "", 0, 0
    script_start = script_match.end()
    script_close = _RE_SCRIPT_CLOSE.search(text, script_start)
    if not script_close:
        return "", text, "", 0, 0
    script_end = script_close.start()
    script_text = text[script_start:script_end]
    script_start_char = script_start
    script_start_line = text[:script_start].count("\n") + 1

    style_match = _RE_STYLE_OPEN.search(text)
    if style_match:
        style_close = _RE_STYLE_CLOSE.search(text, style_match.end())
        if style_close:
            style_text = text[style_match.end():style_close.start()]
            template_text = (
                text[:script_match.start()]
                + text[script_close.end():style_match.start()]
                + text[style_close.end():]
            )
        else:
            style_text = ""
            template_text = (
                text[:script_match.start()] + text[script_close.end():]
            )
    else:
        style_text = ""
        template_text = (
            text[:script_match.start()] + text[script_close.end():]
        )

    return script_text, template_text, style_text, script_start_char, script_start_line


def role_from_path(file: Path, src_root: Path) -> str:
    rel = file.relative_to(src_root)
    parts = rel.parts
    name = file.name

    if "routes" in parts and (
        name.startswith("+page")
        or name.startswith("+layout")
        or name.startswith("+server")
        or name.startswith("+error")
    ):
        return "route"

    if name.endswith(".svelte.ts") or name.endswith(".store.ts"):
        return "store"

    if file.suffix == ".svelte":
        return "component"

    return "module"
