from __future__ import annotations

from pathlib import Path
from typing import Any

from .blitz_hunt import Lightning
from .models import LightningResult


def files_from_envelope(
    envelope: dict[str, Any],
    *,
    repo_root: Path,
    extensions: set[str] | None = None,
) -> list[Path]:
    if extensions is None:
        extensions = set(Lightning.LANGUAGE_EXTENSIONS.keys())
    seen: set[Path] = set()
    for rec in (envelope.get("commits") or {}).values():
        if not isinstance(rec, dict):
            continue
        for raw in rec.get("files") or []:
            if not raw or not isinstance(raw, str):
                continue
            p = Path(raw)
            if not p.is_absolute():
                p = (repo_root / p).resolve()
            if p.exists() and p.is_file() and p.suffix in extensions:
                seen.add(p)
    for hit in envelope.get("code_hits") or []:
        if not isinstance(hit, dict):
            continue
        raw = hit.get("path")
        if not raw or not isinstance(raw, str):
            continue
        p = Path(raw)
        if not p.is_absolute():
            p = (repo_root / p).resolve()
        if p.exists() and p.is_file() and p.suffix in extensions:
            seen.add(p)
    return sorted(seen)


def hunt_envelope_files(
    envelope: dict[str, Any],
    *,
    term: str,
    repo_root: Path,
    regex: bool = False,
    max_files: int = 50,
) -> LightningResult:
    files = files_from_envelope(envelope, repo_root=repo_root)
    bolt = Lightning(str(repo_root), files_override=files)
    return bolt.hunt(term, regex=regex, max_files=max_files)
