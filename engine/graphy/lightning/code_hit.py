
from __future__ import annotations

from typing import Any

from .models import CodeChunk, FileHit

SNIPPET_MAX_CHARS = 500


def _code_hit_from_chunk(
    file_hit: FileHit,
    chunk: CodeChunk,
    term_variations: list[str],
    total_matches_in_result: int,
) -> dict[str, Any]:
    snippet = (chunk.text or "").strip()
    if len(snippet) > SNIPPET_MAX_CHARS:
        snippet = snippet[: SNIPPET_MAX_CHARS - 1] + "…"
    if total_matches_in_result > 0:
        density = chunk.match_count / total_matches_in_result
    else:
        density = 0.0
    score = min(1.0, density + (0.1 if chunk.is_merged else 0.0))
    return {
        "path": file_hit.relative_path or file_hit.filepath,
        "language": file_hit.language,
        "line_start": int(chunk.start_line),
        "line_end": int(chunk.end_line),
        "blocks_included": list(chunk.blocks_included or []),
        "match_count": int(chunk.match_count),
        "snippet": snippet,
        "score": round(float(score), 4),
        "term_variations": list(term_variations or []),
    }
