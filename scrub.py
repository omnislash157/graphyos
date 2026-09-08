#!/usr/bin/env python3
"""scrub — the prose scrub that never names what it scrubs.

The private markers are words that must not travel. A tracked list of them would itself travel,
so the list is keyed: `.private_markers.sha256` holds an HMAC-SHA256 of each marker, normalized
to lowercase alphanumerics with every space and underscore removed, under a key that lives only
in `.private_key` beside this file — gitignored, never tracked, written once by `--keygen`. A
plain hash of a word is reversible by a wordlist (a company name is a public fact); a keyed one
is not without the key. A file is scanned as the same normalized tokens, single and adjacent-pair,
and a hit is a token whose keyed digest is in the list. The digests name nothing; the local
operator regenerates them with `scrub.py --hash <word>…`.

A box without the key (CI) cannot run the hashed sweep and says so: `SCRUB SKIPPED`, exit 0 —
the words are absent from the tree, which the sweep proves on the operator's box, where the gate
and the census run before every cut.

    scrub.py <file>…            print each hit as <file>:<line>; exit 3 when any
    scrub.py --tracked          every git-tracked file outside staging/ (the public cut's tripwire)
    scrub.py --tree <dir>       every file under a directory, skipping build and substrate dirs
    scrub.py --hash <word>…     print the keyed digests for words (to write the list)
    scrub.py --keygen           write a fresh key to .private_key; refuses when one stands
    scrub.py --key <path> …     read the key from another path (first), for a checkout that has none
"""
from __future__ import annotations

import hmac
import re
import secrets
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIST = HERE / ".private_markers.sha256"
KEY = HERE / ".private_key"
_TOKEN = re.compile(r"[a-z0-9]+")
_SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", "substrate", "venv", ".venv"}
_SKIP_FILE_PREFIX = ("tenant.",)


def load_key(path: Path | None = None) -> bytes | None:
    """The key's bytes, or None when the box has no key file (or an empty one)."""
    path = KEY if path is None else path
    if not path.is_file():
        return None
    key = path.read_text(encoding="utf-8").strip()
    return key.encode("utf-8") or None


_PRIMED: dict[bytes, hmac.HMAC] = {}
_SEEN: dict[tuple[bytes, str], str] = {}


def keyed(word: str, key: bytes) -> str:
    """HMAC-SHA256 of a token under the key. The keyed state is primed once per key and copied per
    token, and a token's digest is remembered — a sweep sees the same few thousand tokens over and
    over, so the keyed sweep costs no more than the plain hash it replaced."""
    k = (key, word)
    d = _SEEN.get(k)
    if d is None:
        h = _PRIMED.get(key)
        if h is None:
            h = _PRIMED[key] = hmac.new(key, b"", "sha256")
        h = h.copy()
        h.update(word.encode("utf-8"))
        d = _SEEN[k] = h.hexdigest()
    return d


def norm_hash(word: str, key: bytes) -> str:
    w = re.sub(r"[\s_]+", "", word.lower())
    return keyed(w, key)


def load_list(path: Path | None = None) -> frozenset[str]:
    path = LIST if path is None else path
    if not path.is_file():
        sys.exit(f"SCRUB REFUSED: no marker list at {path} — the scrub cannot run without one; "
                 f"write it with `scrub.py --hash <word>…` (the words never travel, their keyed digests do)")
    return frozenset(ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#"))


def hits_in(path: Path, hashes: frozenset[str], key: bytes) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        toks = _TOKEN.findall(line.lower())
        cands = toks + [a + b for a, b in zip(toks, toks[1:])]
        for c in cands:
            if keyed(c, key) in hashes:
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


def keygen(path: Path | None = None) -> int:
    path = KEY if path is None else path
    if path.exists():
        print(f"SCRUB REFUSED: a key already stands at {path} — a new key makes every digest in "
              f"{LIST.name} stale; move it aside by hand and rewrite the list with --hash")
        return 2
    path.write_text(secrets.token_hex(32) + "\n", encoding="utf-8")
    path.chmod(0o600)
    print(f"SCRUB: key written to {path} (never tracked) — now `scrub.py --hash <word>…` writes the list")
    return 0


def main(argv: list[str]) -> int:
    key_path = None
    if argv[:1] == ["--key"]:          # another box's key file, by path — never copied (sync_public.sh scrubs the public checkout under this box's key)
        key_path, argv = Path(argv[1]).resolve(), argv[2:]
    if argv[:1] == ["--keygen"]:
        return keygen(key_path)
    key = load_key(key_path)
    if argv[:1] == ["--hash"]:
        if key is None:
            print(f"SCRUB REFUSED: no key at {key_path or KEY} — the digests are keyed; `scrub.py --keygen` writes one")
            return 2
        for w in argv[1:]:
            print(norm_hash(w, key))
        return 0
    hashes = load_list()
    if argv[:1] == ["--tracked"]:
        files = tracked_outside_staging()
    elif argv[:1] == ["--tree"]:
        files = tree(Path(argv[1]).resolve())
    else:
        files = [Path(a) for a in argv]
    if key is None:
        print(f"SCRUB SKIPPED: no key at {key_path or KEY} — the keyed sweep over {len(files)} file(s) needs the operator's key; "
              f"it runs on the operator's box, never here")
        return 0
    n = 0
    for f in files:
        for line, tok in hits_in(f, hashes, key):
            print(f"{f}:{line}: private token")
            n += 1
    if n:
        print(f"SCRUB RED: {n} hit(s) in {len(files)} file(s)")
        return 3
    print(f"SCRUB OK: {len(files)} file(s), no private token")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
