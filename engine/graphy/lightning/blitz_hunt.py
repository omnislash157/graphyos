
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .pseudo_ast import find_brace_blocks_for_path as _find_brace_blocks_for_path

from .block_blast import find_blocks
from .context_strike import expand_and_merge, find_matches
from .models import CodeChunk, FileHit, LightningResult
from .pattern_splinter import build_code_pattern, get_identifier_variations
from .prose_blast import has_exchanges as _has_exchanges
from .ripgrep import RG_PATH, python_matching_files, rg_matching_files, searchable_files

logger = logging.getLogger(__name__)

TOKEN_RADIUS = 100
MERGE_GAP = 50
MAX_CHUNKS_PER_FILE = 5


class Lightning:

    LANGUAGE_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".svelte": "svelte",
        ".vue": "vue",
        ".rs": "rust",
        ".go": "go",
        ".rb": "ruby",
        ".java": "java",
        ".kt": "kotlin",
        ".swift": "swift",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".php": "php",
        ".sh": "bash",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".toml": "toml",
        ".md": "markdown",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".sql": "sql",
    }

    IGNORE_DIRS = {
        ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
        "node_modules", ".venv", "venv", "env",
        "dist", "build", ".next", ".nuxt", ".svelte-kit", "target",
        ".idea", ".vscode", "coverage",
        ".claude", "skills",
        "data", "docs", "Manuals", "archive",
        "vendor", ".env",
    }

    def __init__(self, root_path: str, extensions: set[str] | None = None,
                 files_override: list[Path] | list[str] | None = None):
        requested_root = Path(root_path).expanduser()
        if not requested_root.exists():
            raise FileNotFoundError(f"Lightning corpus does not exist: {root_path}")
        self.root_path = requested_root.resolve()
        self.extensions = extensions or set(self.LANGUAGE_EXTENSIONS.keys())
        self._files_cache: list[Path] | None = None
        self._files_override: list[Path] | None = None
        self.log_mode = False
        if self.root_path.is_file():
            target = self.root_path
            self.root_path = target.parent
            self._files_override = [target]
            self.log_mode = target.suffix == ".log"
        if files_override is not None:
            resolved: list[Path] = []
            for f in files_override:
                p = Path(f)
                if not p.is_absolute():
                    p = (self.root_path / p).resolve()
                if p.exists() and p.is_file() and p.suffix in self.extensions:
                    resolved.append(p)
            self._files_override = resolved

    @property
    def files(self) -> list[Path]:
        if self._files_override is not None:
            return self._files_override
        if self._files_cache is None:
            self._files_cache = searchable_files(self.root_path, self.extensions)
        return self._files_cache

    def list_files(self, pattern: str = None) -> list[Path]:
        if pattern:
            return [f for f in self.files if f.match(pattern)]
        return self.files

    def _process_file(
        self,
        filepath: Path,
        pattern: re.Pattern,
        context_lines: int,
    ) -> FileHit | None:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

        lang = self.LANGUAGE_EXTENSIONS.get(filepath.suffix) or (
            "log" if filepath.suffix == ".log" else "text"
        )
        if lang == "markdown" and _has_exchanges(content):
            lang = "prose"
        if lang in ("svelte", "typescript", "javascript"):
            blocks = _find_brace_blocks_for_path(content, filepath)
        else:
            blocks = find_blocks(content, lang)
        matches = find_matches(content, pattern, blocks)

        if not matches:
            return None

        if lang == "log":
            src_lines = content.split("\n")
            chunks = [
                CodeChunk(
                    start_token=m.start_token,
                    end_token=m.end_token,
                    start_line=m.line_number,
                    end_line=m.line_number,
                    text=src_lines[m.line_number - 1] if 0 < m.line_number <= len(src_lines) else m.matched_text,
                    match_count=1,
                )
                for m in matches[:MAX_CHUNKS_PER_FILE]
            ]
            return FileHit(
                filepath=str(filepath),
                relative_path=str(filepath.relative_to(self.root_path)),
                language=lang,
                chunks=chunks,
                total_matches=len(matches),
                total_tokens=sum(c.end_token - c.start_token for c in chunks),
                matches=matches,
            )

        chunks = expand_and_merge(
            content,
            matches,
            blocks,
            token_radius=TOKEN_RADIUS,
            merge_gap=MERGE_GAP,
            smart_expand=True,
            context_lines=context_lines,
        )

        if len(chunks) > MAX_CHUNKS_PER_FILE:
            chunks = chunks[:MAX_CHUNKS_PER_FILE]

        return FileHit(
            filepath=str(filepath),
            relative_path=str(filepath.relative_to(self.root_path)),
            language=lang,
            chunks=chunks,
            total_matches=len(matches),
            total_tokens=sum(c.end_token - c.start_token for c in chunks),
            matches=matches,
        )

    def hunt(
        self,
        term: str,
        *,
        regex: bool = False,
        file_pattern: str | None = None,
        max_files: int = 20,
        context_lines: int = 5,
        loose: bool = False,
    ) -> LightningResult:
        start = time.perf_counter()

        log_corpus = self.log_mode or bool(file_pattern and file_pattern.endswith(".log"))
        if regex:
            pattern = re.compile(term, re.IGNORECASE | re.MULTILINE)
            variations = [term]
        elif log_corpus:
            from .log_blast import route_query_pattern
            pattern = route_query_pattern(term)
            variations = [term]
        else:
            pattern = build_code_pattern(term, loose=loose)
            variations = get_identifier_variations(term)

        if self._files_override is not None:
            files_to_search = self._files_override
            if file_pattern:
                files_to_search = [f for f in files_to_search if f.match(file_pattern)]
            matching_files = python_matching_files(pattern, files_to_search)
        elif file_pattern and file_pattern.endswith(".log"):
            files_to_search = [
                p for p in sorted(self.root_path.rglob(file_pattern))
                if p.is_file() and not any(part in self.IGNORE_DIRS for part in p.parts)
            ]
            matching_files = python_matching_files(pattern, files_to_search)
        elif RG_PATH and not file_pattern:
            matching_files = rg_matching_files(pattern, self.root_path, self.extensions)
        else:
            files_to_search = self.files
            if file_pattern:
                files_to_search = [f for f in files_to_search if f.match(file_pattern)]
            matching_files = python_matching_files(pattern, files_to_search)

        files_searched = len(self.files)
        pass1_ms = (time.perf_counter() - start) * 1000
        logger.info(f"Pass 1: {len(matching_files)} files in {pass1_ms:.0f}ms")

        matching_files = sorted(matching_files)
        if max_files and len(matching_files) > max_files * 2:
            matching_files = matching_files[: max_files * 2]

        hits = []
        total_matches = 0

        workers = min(16, len(matching_files) or 1)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._process_file, fp, pattern, context_lines): fp
                for fp in matching_files
            }
            by_file = {}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    by_file[futures[future]] = result
        for fp in sorted(by_file):
            hits.append(by_file[fp])
            total_matches += by_file[fp].total_matches
            if max_files and len(hits) >= max_files:
                break

        elapsed_ms = (time.perf_counter() - start) * 1000

        return LightningResult(
            term=term,
            variations=variations,
            files_searched=files_searched,
            files_matched=len(hits),
            total_matches=total_matches,
            hits=hits,
            search_time_ms=elapsed_ms,
        )
