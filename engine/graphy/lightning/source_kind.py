
from __future__ import annotations

import subprocess
from pathlib import Path

_TEST_DIR_PARTS = frozenset({"tests", "test", "__tests__", "testing", "fixtures", "conftest"})
_SLOP_DIR_PARTS = frozenset({"archive", "scp", "uploads", "bin", "logs", "migrations", "scratchpad"})
_DOC_SUFFIXES = frozenset(
    {".json", ".jsonl", ".md", ".rst", ".txt", ".yaml", ".yml"}
)
_DOC_DIR_PARTS = frozenset({"review", "reviews", "handoffs"})
_TEST_SUFFIX_MARKS = (".spec.", ".test.")


def _is_test_file(rel: str) -> bool:
    p = Path(rel)
    name = p.name.lower()
    if name.startswith("test_") or name == "conftest.py":
        return True
    stem = name.rsplit(".", 1)[0]
    if stem.endswith("_test"):
        return True
    if any(m in name for m in _TEST_SUFFIX_MARKS):
        return True
    return any(part.lower() in _TEST_DIR_PARTS for part in p.parts[:-1])


def _is_slop_dir(rel: str) -> bool:
    return any(part.lower() in _SLOP_DIR_PARTS for part in Path(rel).parts[:-1])


def gitignored_set(rel_paths: list[str], cwd: str | Path) -> set[str]:
    if not rel_paths:
        return set()
    try:
        r = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            input="\n".join(rel_paths), capture_output=True, text=True,
            cwd=str(cwd), timeout=30,
        )
        return {ln for ln in r.stdout.splitlines() if ln}
    except Exception:
        return set()


def _is_doc_file(rel: str) -> bool:
    p = Path(rel)
    if p.suffix.lower() in _DOC_SUFFIXES:
        return True
    return any(part.lower() in _DOC_DIR_PARTS for part in p.parts[:-1])


def classify_sources(rel_paths: list[str], cwd: str | Path) -> dict[str, str]:
    ignored = gitignored_set(sorted(set(rel_paths)), cwd)
    out = {}
    for rel in rel_paths:
        if _is_test_file(rel):
            out[rel] = "test"
        elif rel in ignored or _is_slop_dir(rel):
            out[rel] = "slop"
        elif _is_doc_file(rel):
            out[rel] = "doc"
        else:
            out[rel] = "live"
    return out


def liveness_verdict(kind_counts: dict[str, int]) -> str:
    live = kind_counts.get("live", 0)
    prose = kind_counts.get("prose", 0)
    others = kind_counts.get("test", 0) + kind_counts.get("slop", 0) + kind_counts.get("doc", 0)
    if live > 0:
        return f"LIVE — {live} live-code referrer(s); test/slop/doc/prose shown separately, not counted"
    if prose > 0 and others == 0:
        return (f"MENTION-ONLY — zero live-code referrers; all {prose} live-file hit(s) are "
                f"COMMENTS or STRINGS (the fuzz matched text, not a call)")
    if prose > 0:
        return (f"FALSE LIVENESS — zero live-code referrers; {prose} live-file hit(s) are "
                f"comments/strings and the rest are test/slop/doc")
    if others > 0:
        return "FALSE LIVENESS — zero live-code referrers; every reference is test/slop/doc (the purchasing_ssot class)"
    return "DARK — zero referrers of any kind"
