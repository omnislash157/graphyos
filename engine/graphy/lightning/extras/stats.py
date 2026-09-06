
from typing import Any

from ..pattern_splinter import build_code_pattern


def quick_stats(lightning, term: str) -> dict[str, Any]:
    if getattr(lightning, "log_mode", False):
        from ..log_blast import route_query_pattern
        pattern = route_query_pattern(term)
    else:
        pattern = build_code_pattern(term)

    matches_by_file = {}
    total = 0

    for filepath in lightning.files:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        matches = pattern.findall(content)
        if matches:
            rel_path = str(filepath.relative_to(lightning.root_path))
            matches_by_file[rel_path] = len(matches)
            total += len(matches)

    return {
        "term": term,
        "total_matches": total,
        "files_with_matches": len(matches_by_file),
        "by_file": matches_by_file,
    }
