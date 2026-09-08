"""The keyed scrub (scrub.py at the repo root): a planted marker is caught by name under the key, the
tracked digests reverse by no wordlist without it, and a box with no key says SKIPPED, never a
hollow OK. A floor; the gate and the census run the real one over the tree."""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location("scrub", ROOT / "scrub.py")
scrub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scrub)


def _fixture(tmp_path, words=("acme widgets", "zorblax")):
    key = tmp_path / ".private_key"
    lst = tmp_path / ".private_markers.sha256"
    key.write_text("0123456789abcdef" * 4 + "\n")
    k = scrub.load_key(key)
    lst.write_text("\n".join(scrub.norm_hash(w, k) for w in words) + "\n")
    return key, lst, k


def test_a_planted_marker_is_caught_by_file_and_line_under_the_key(tmp_path):
    key, lst, k = _fixture(tmp_path)
    hashes = scrub.load_list(lst)
    f = tmp_path / "note.md"
    f.write_text("nothing here\nbuilt for Acme_Widgets last spring\nand Zorblax too\n")
    assert scrub.hits_in(f, hashes, k) == [(2, "acmewidgets"), (3, "zorblax")]
    clean = tmp_path / "clean.md"
    clean.write_text("a public sentence\n")
    assert scrub.hits_in(clean, hashes, k) == []


def test_RED_the_tracked_digests_reverse_by_no_wordlist_without_the_key(tmp_path):
    """The red team's attack: sha256 over a guess list. Under the key a plain hash matches nothing,
    and a different key gives a different list — the digest carries nothing a guess can hit."""
    key, lst, k = _fixture(tmp_path)
    lines = set(lst.read_text().split())
    for guess in ("acmewidgets", "zorblax", "acme widgets"):
        w = guess.replace(" ", "")
        assert hashlib.sha256(w.encode()).hexdigest() not in lines
    assert all(len(ln) == 64 for ln in lines)
    other = scrub.load_key(Path(tmp_path / "k2").write_text("another key\n") and tmp_path / "k2")
    assert scrub.norm_hash("zorblax", other) not in lines
    # and the real list beside the repo: the login name and its parts, the public facts the red team started from
    real = set((ROOT / ".private_markers.sha256").read_text().split())
    home = Path.home().name
    for w in ["graphy", home, *home.split("-"), home.replace("-", "")]:
        assert hashlib.sha256(w.lower().encode()).hexdigest() not in real, w


def _run(args, cwd, key_present: bool, tmp_path):
    """scrub.py run as a subprocess with HERE redirected: a copy of the script beside a list (and a key)."""
    box = tmp_path / ("keyed" if key_present else "bare")
    box.mkdir(exist_ok=True)
    (box / "scrub.py").write_text((ROOT / "scrub.py").read_text())
    (box / ".private_markers.sha256").write_text((tmp_path / ".private_markers.sha256").read_text())
    if key_present:
        (box / ".private_key").write_text((tmp_path / ".private_key").read_text())
    return subprocess.run([sys.executable, str(box / "scrub.py"), *args], cwd=cwd, capture_output=True, text=True), box


def test_a_box_with_no_key_says_SKIPPED_and_exits_0_and_hash_refuses(tmp_path):
    _fixture(tmp_path)
    f = tmp_path / "note.md"
    f.write_text("built for acme widgets\n")
    r, box = _run([str(f)], tmp_path, key_present=False, tmp_path=tmp_path)
    assert r.returncode == 0 and r.stdout.startswith("SCRUB SKIPPED: no key at ") and ".private_key" in r.stdout
    assert "private token" not in r.stdout and "SCRUB OK" not in r.stdout
    r, _ = _run(["--hash", "acme widgets"], tmp_path, key_present=False, tmp_path=tmp_path)
    assert r.returncode == 2 and r.stdout.startswith("SCRUB REFUSED: no key at ") and "--keygen" in r.stdout
    r, box = _run([str(f)], tmp_path, key_present=True, tmp_path=tmp_path)
    assert r.returncode == 3 and f"{f}:1: private token" in r.stdout and "SCRUB RED: 1 hit(s)" in r.stdout


def test_keygen_writes_once_and_refuses_to_overwrite(tmp_path):
    key = tmp_path / ".private_key"
    assert scrub.keygen(key) == 0
    first = key.read_text().strip()
    assert len(first) == 64 and (key.stat().st_mode & 0o777) == 0o600
    assert scrub.keygen(key) == 2 and key.read_text().strip() == first
    assert scrub.load_key(key) == first.encode()
    empty = tmp_path / "empty"
    empty.write_text("\n")
    assert scrub.load_key(empty) is None and scrub.load_key(tmp_path / "absent") is None


def test_key_by_path_scrubs_a_checkout_that_has_none(tmp_path):
    """sync_public.sh: the public checkout carries the list and no key; --key <path> reads this box's."""
    _fixture(tmp_path)
    f = tmp_path / "note.md"
    f.write_text("built for acme widgets\n")
    r, box = _run(["--key", str(tmp_path / ".private_key"), str(f)], tmp_path, key_present=False, tmp_path=tmp_path)
    assert r.returncode == 3 and f"{f}:1: private token" in r.stdout
    r, _ = _run(["--key", str(tmp_path / "absent"), str(f)], tmp_path, key_present=False, tmp_path=tmp_path)
    assert r.returncode == 0 and r.stdout.startswith("SCRUB SKIPPED: no key at ") and str(tmp_path / "absent") in r.stdout
