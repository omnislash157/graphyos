
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

IGNORE_DIRS = [
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
    "node_modules", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", ".svelte-kit", "target",
    ".idea", ".vscode", "coverage",
    ".claude", "skills",
    "data", "docs", "Manuals", "archive",
    "vendor", ".env",
]

def resolve_rg() -> str | None:
    override = os.environ.get("GRAPHY_RG", "").strip()
    if override:
        return override if Path(override).is_file() and os.access(override, os.X_OK) else None
    bindir = "Scripts" if os.name == "nt" else "bin"
    exe = "rg.exe" if os.name == "nt" else "rg"

    candidates = [
        Path(sys.prefix) / bindir / exe,
    ]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which(exe)


RG_PATH = resolve_rg()
GIT_PATH = shutil.which("git")

if RG_PATH is None:
    logger.warning(
        "ripgrep not found in the venv or on PATH — Lightning is running on the "
        "slow Python fallback. Fix: install ripgrep (rg) on PATH, or set GRAPHY_RG to the binary."
    )


def _relative_is_ignored(path: Path) -> bool:
    return any(part in IGNORE_DIRS or part.startswith(".") for part in path.parts)


def _git_searchable_files(
    root_path: Path,
    file_extensions: set[str],
) -> list[Path] | None:
    if GIT_PATH is None:
        return None
    probe = root_path if root_path.is_dir() else root_path.parent
    top_result = subprocess.run(
        [GIT_PATH, "-C", str(probe), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=3,
    )
    if top_result.returncode != 0 or not top_result.stdout.strip():
        return None

    git_root = Path(top_result.stdout.strip()).resolve()
    resolved_root = root_path.resolve()
    if not resolved_root.is_relative_to(git_root):
        return None
    scope = resolved_root.relative_to(git_root)

    if scope.parts:
        ignored = subprocess.run(
            [GIT_PATH, "-C", str(git_root), "check-ignore", "-q", "--", str(scope)],
            capture_output=True,
            timeout=3,
        )
        if ignored.returncode == 0:
            return None

    result = subprocess.run(
        [
            GIT_PATH, "-C", str(git_root), "ls-files", "-z",
            "--cached", "--others", "--exclude-standard", "--",
            str(scope) if scope.parts else ".",
        ],
        capture_output=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git file inventory failed for {root_path} (exit {result.returncode})"
        )

    files: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        candidate = (git_root / os.fsdecode(raw)).resolve()
        if not candidate.is_relative_to(resolved_root):
            continue
        relative = candidate.relative_to(resolved_root)
        if _relative_is_ignored(relative):
            continue
        if candidate.is_file() and candidate.suffix in file_extensions:
            files.append(candidate)
    return sorted(set(files))


def _bounded_filesystem_inventory(
    root_path: Path,
    file_extensions: set[str],
) -> list[Path]:
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(root_path, followlinks=False):
        current_path = Path(current)
        relative_dir = current_path.relative_to(root_path)
        dirnames[:] = sorted(
            name for name in dirnames
            if not _relative_is_ignored(relative_dir / name)
        )
        for name in sorted(filenames):
            candidate = current_path / name
            relative = candidate.relative_to(root_path)
            if _relative_is_ignored(relative):
                continue
            if candidate.is_file() and candidate.suffix in file_extensions:
                files.append(candidate.resolve())
    return files


def searchable_files(
    root_path: Path,
    file_extensions: set[str],
) -> list[Path]:
    git_files = _git_searchable_files(root_path, file_extensions)
    if git_files is not None:
        return git_files
    return _bounded_filesystem_inventory(root_path, file_extensions)


def rg_matching_files(
    pattern: re.Pattern | str,
    root_path: Path,
    file_extensions: set[str] | None = None,
) -> list[Path]:
    if not RG_PATH:
        raise RuntimeError(
            "rg_matching_files called with no ripgrep binary resolved. Callers must "
            "check RG_PATH and take the python_matching_files fallback (see "
            "blitz_hunt.hunt). Returning [] here would be indistinguishable from a "
            "genuine no-match. Fix: install ripgrep (rg) on PATH."
        )

    if isinstance(pattern, re.Pattern):
        pat_str = pattern.pattern
    else:
        pat_str = pattern

    cmd = [
        RG_PATH,
        "--files-with-matches",
        "--pcre2",
        "-i",
        "--no-messages",
    ]

    if file_extensions:
        for ext in file_extensions:
            ext_clean = ext.lstrip(".")
            cmd.extend(["--glob", f"*.{ext_clean}"])

    for d in IGNORE_DIRS:
        cmd.extend(["--glob", f"!{d}/**", "--glob", f"!**/{d}/**"])

    cmd.append(pat_str)
    cmd.append(str(root_path))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            return [Path(line) for line in result.stdout.strip().split("\n") if line]
        if result.returncode == 1:
            return []

        raise RuntimeError(
            f"ripgrep failed (exit {result.returncode}) — this is an INSTRUMENT "
            f"failure, not an empty result.\n"
            f"  binary: {RG_PATH}\n"
            f"  stderr: {result.stderr.strip()[:400]}\n"
            f"  If that mentions PCRE2, the resolved rg lacks lookaround support "
            f"(some builds lack it). Fix: install a ripgrep built with PCRE2."
        )

    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"ripgrep timed out after 10s on {root_path} — this is an INSTRUMENT "
            f"failure, not an empty result. Scope the search to a narrower path."
        ) from exc


def python_matching_files(
    pattern: re.Pattern,
    files: list[Path],
) -> list[Path]:
    matching = []
    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            if pattern.search(content):
                matching.append(filepath)
        except Exception:
            pass
    return matching
