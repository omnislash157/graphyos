
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CodeBlock:

    block_type: str
    name: str | None
    start_line: int
    end_line: int
    start_char: int
    end_char: int
    docstring: str | None = None
    attrs: dict = field(default_factory=dict)


@dataclass
class CodeMatch:

    start_char: int
    end_char: int
    start_token: int
    end_token: int
    matched_text: str
    line_number: int
    containing_block: str | None = None


@dataclass
class CodeChunk:

    start_token: int
    end_token: int
    start_line: int
    end_line: int
    text: str
    match_count: int
    is_merged: bool = False
    blocks_included: list[str] = field(default_factory=list)
    anchor_head: list = field(default_factory=list)


@dataclass
class FileHit:

    filepath: str
    relative_path: str
    language: str
    chunks: list[CodeChunk]
    total_matches: int
    total_tokens: int
    matches: list[CodeMatch] = field(default_factory=list)


@dataclass
class SessionSegment:

    topic: str
    summary: str
    exchange_range: list[int] = field(default_factory=list)
    date: str = ""
    session_id: str = ""
    hits: int = 0


@dataclass
class SessionHit:

    filepath: str
    session_id: str
    date: str
    title: str
    segments: list[SessionSegment]
    total_hits: int
    cooccur_terms: list[str] = field(default_factory=list)


@dataclass
class SessionSearchResult:

    term: str
    keywords: list[str]
    files_searched: int
    sessions_matched: int
    total_segments: int
    hits: list[SessionHit]
    search_time_ms: float
    cooccurrence: dict[str, int] = field(default_factory=dict)

    def to_markdown(self) -> str:
        lines = [f"# SESSION INDEX SEARCH", f"**Query:** `{self.term}` | **{self.sessions_matched} sessions** | **{self.total_segments} segments** | {self.search_time_ms:.0f}ms\n"]
        for hit in self.hits[:10]:
            lines.append(f"## [{hit.date}] {hit.title or hit.session_id[:20]}")
            for seg in hit.segments[:5]:
                ex = f" (ex {seg.exchange_range[0]}-{seg.exchange_range[1]})" if len(seg.exchange_range) == 2 else ""
                lines.append(f"  **{seg.topic}**{ex}")
                if seg.summary:
                    lines.append(f"    {seg.summary[:200]}")
            lines.append("")
        if self.cooccurrence:
            lines.append("## Co-occurrence")
            for term, count in sorted(self.cooccurrence.items(), key=lambda x: x[1], reverse=True)[:15]:
                lines.append(f"  {term}: {count}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "term": self.term,
            "keywords": self.keywords,
            "files_searched": self.files_searched,
            "sessions_matched": self.sessions_matched,
            "total_segments": self.total_segments,
            "search_time_ms": self.search_time_ms,
            "cooccurrence": self.cooccurrence,
            "hits": [
                {
                    "session_id": h.session_id,
                    "date": h.date,
                    "title": h.title,
                    "total_hits": h.total_hits,
                    "segments": [
                        {"topic": s.topic, "summary": s.summary,
                         "exchange_range": s.exchange_range, "hits": s.hits}
                        for s in h.segments
                    ],
                }
                for h in self.hits
            ],
        }


@dataclass
class LightningResult:

    term: str
    variations: list[str]
    files_searched: int
    files_matched: int
    total_matches: int
    hits: list[FileHit]
    search_time_ms: float

    def to_markdown(self, context_lines: int | None = None) -> str:
        from .formatters import to_markdown
        return to_markdown(self)

    def to_dict(self) -> dict[str, Any]:
        from .formatters import to_json
        return to_json(self)


CodeHoundResult = LightningResult
