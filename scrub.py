#!/usr/bin/env python3
"""scrub — the prose scrub that never names what it scrubs.

The private markers are words that must not travel. A tracked list of them would itself travel,
so the list is hashed: `.private_markers.sha256` holds sha256 of each marker, normalized to
lowercase alphanumerics with every space and underscore removed. A file is scanned as the same
normalized tokens, single and adjacent-pair, and a hit is a token whose hash is in the list. The
hashes name nothing; the local operator regenerates them with `scrub.py --hash <word>…`.

    scrub.py <file>…            print each hit as <file>:<line>; exit 3 when any
    scrub.py --tracked          every git-tracked file outside staging/ (the public cut's tripwire)
    scrub.py --tree <dir>       every file under a directory, skipping build and substrate dirs
    scrub.py --hash <word>…     print the normalized hashes for words (to write the list)
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIST = HERE / ".private_markers.sha256"
_TOKEN = re.compile(r"[a-z0-9]+")
_SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", "substrate", "venv", ".venv"}
_SKIP_FILE_PREFIX = ("tenant.",)


def norm_hash(word: str) -> str:
    w = re.sub(r"[\s_]+", "", word.lower())
    return hashlib.sha256(w.encode("utf-8")).hexdigest()


def load_list() -> frozenset[str]:
    if not LIST.is_file():
        sys.exit(f"SCRUB REFUSED: no marker list at {LIST} — the scrub cannot run without one; "
                 f"write it with `scrub.py --hash <word>…` (the words never travel, their hashes do)")
    return frozenset(ln.strip() for ln in LIST.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#"))


def hits_in(path: Path, hashes: frozenset[str]) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        toks = _TOKEN.findall(line.lower())
        cands = toks + [a + b for a, b in zip(toks, toks[1:])]
        for c in cands:
            if hashlib.sha256(c.encode()).hexdigest() in hashes:
                out.append((n, c))
                break
    return out


def tracked_outside_staging() -> list[Path]:
    files = subprocess.run(["git", "ls-files"], cwd=HERE, capture_output=True, text=True, check=True).stdout.split("\n")
    return [HERE / f for f in files if f and not f.startswith("staging/") and (HERE / f).is_file()]


def tree(root: Path) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        parts = set(p.relative_to(root).parts[:-1])
        if parts & _SKIP_DIRS or any(part.startswith("substrate.") or part.endswith(".egg-info") for part in parts):
            continue
        if p.name.startswith(_SKIP_FILE_PREFIX) and p.name.endswith(".json"):
            continue
        out.append(p)
    return out


def main(argv: list[str]) -> int:
    if argv[:1] == ["--hash"]:
        for w in argv[1:]:
            print(norm_hash(w))
        return 0
    hashes = load_list()
    if argv[:1] == ["--tracked"]:
        files = tracked_outside_staging()
    elif argv[:1] == ["--tree"]:
        files = tree(Path(argv[1]).resolve())
    else:
        files = [Path(a) for a in argv]
    n = 0
    for f in files:
        for line, tok in hits_in(f, hashes):
            print(f"{f}:{line}: private token")
            n += 1
    if n:
        print(f"SCRUB RED: {n} hit(s) in {len(files)} file(s)")
        return 3
    print(f"SCRUB OK: {len(files)} file(s), no private token")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
