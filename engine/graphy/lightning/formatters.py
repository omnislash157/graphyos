
from typing import Any


def to_markdown(result) -> str:
    lines = [
        "# LIGHTNING SEARCH",
        f"**Term:** `{result.term}` | **{result.files_matched} files** | **{result.total_matches} matches** | {result.search_time_ms:.0f}ms",
        "",
    ]

    for hit in result.hits:
        lines.append(f"## {hit.relative_path}")
        lines.append(f"*{hit.total_matches} matches*")
        lines.append("")

        match_lines = {m.line_number for m in hit.matches}

        for chunk in hit.chunks:
            blocks = [b for b in chunk.blocks_included if b] or ["top-level"]
            header = f"**{' · '.join(blocks)}**"
            if chunk.is_merged:
                header += f"  [merged: {len(blocks)} blocks]"
            lines.append(header)

            if chunk.anchor_head:
                for ln, text_line in chunk.anchor_head:
                    lines.append(f"  L{ln}: {text_line}")
                lines.append("  ⋯")

            for offset, text_line in enumerate(chunk.text.split("\n")):
                i = chunk.start_line + offset
                if i in match_lines:
                    lines.append(f"  **L{i}:** `{text_line}`  <- MATCH")
                else:
                    lines.append(f"  L{i}: {text_line}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def to_json(result) -> dict[str, Any]:
    return {
        "term": result.term,
        "variations": result.variations,
        "files_searched": result.files_searched,
        "files_matched": result.files_matched,
        "total_matches": result.total_matches,
        "search_time_ms": result.search_time_ms,
        "hits": [
            {
                "filepath": hit.filepath,
                "relative_path": hit.relative_path,
                "language": hit.language,
                "total_matches": hit.total_matches,
                "chunks": [
                    {
                        "start_line": c.start_line,
                        "end_line": c.end_line,
                        "match_count": c.match_count,
                        "is_merged": c.is_merged,
                        "blocks_included": c.blocks_included,
                        "anchor_head": c.anchor_head,
                        "text": c.text,
                    }
                    for c in hit.chunks
                ],
            }
            for hit in result.hits
        ],
    }
