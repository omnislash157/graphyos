"""The keyed scrub (scrub.py at the repo root): a planted marker is caught by name under the key, the
tracked digests reverse by no wordlist without it, and a box with no key says SKIPPED, never a
hollow OK. A floor; the gate and the census run the real one over the tree."""
from __future__ import annotations

import hashlib
import importlib.util
import os
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
    assert len(first) == 64
    if os.name != "nt":                      # Windows has no mode bits: the key's secrecy there is the profile dir's ACL (graphyos #127)
        assert (key.stat().st_mode & 0o777) == 0o600
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


def test_RED_the_tracker_is_scrubbed_by_issue_and_line_and_a_failed_fetch_refuses(tmp_path, monkeypatch, capsys):
    """graphyos #91: the scrub walked files only, and the public tracker carried 22 marker hits across 14 issues.
    `--issues` reads every title, body and comment and names the hit by issue and line without the word; a fetch
    that fails is SCRUB REFUSED (exit 2), never a clean zero."""
    key, lst, k = _fixture(tmp_path)
    monkeypatch.setattr(scrub, "KEY", key)
    monkeypatch.setattr(scrub, "LIST", lst)
    monkeypatch.setattr(scrub, "load_list", lambda path=None: frozenset(lst.read_text().split()))
    monkeypatch.setattr(scrub, "fetch_surface", lambda repo: [("#7 title", "a finding"), ("#7 body", "measured\nat Zorblax\n"),
                                                               ("#7 comment 2", "for acme widgets")])
    assert scrub.main(["--issues", "o/r"]) == 3
    out = capsys.readouterr().out
    assert "#7 body:2: private token" in out and "#7 comment 2:1: private token" in out and "zorblax" not in out.lower()

    def broken(repo):
        raise scrub.FetchError("gh exited 1")
    monkeypatch.setattr(scrub, "fetch_surface", broken)
    assert scrub.main(["--issues", "o/r"]) == 2 and "SCRUB REFUSED" in capsys.readouterr().out


def test_RED_a_post_to_github_carrying_a_marker_is_blocked_before_it_posts(tmp_path, capsys):
    """#91's board law, made mechanical: the PreToolUse hook blocks `gh issue create|comment` (and pr, release) whose
    inline body, heredoc or body file carries a marker; anything else, or a box with no key, passes."""
    import json
    key, lst, k = _fixture(tmp_path)
    hashes = frozenset(lst.read_text().split())
    hook = lambda cmd, key=k: scrub.gh_hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}), hashes, key)
    assert hook('gh issue create --repo o/r --title x --body "measured at Zorblax"') == 2
    assert "SCRUB REFUSED" in capsys.readouterr().err
    assert hook("gh issue comment 9 --repo o/r --body \"$(cat <<'EOF'\nfine\nfor acme widgets\nEOF\n)\"") == 2
    body = tmp_path / "body.md"
    body.write_text("line one\nZorblax\n")
    assert hook(f"gh pr create --title t --body-file {body.as_posix()}") == 2     # a bash word: POSIX on every host
    assert "body.md line 2" in capsys.readouterr().err
    assert hook('gh issue create --repo o/r --title x --body "a public sentence"') == 0
    assert hook("grep Zorblax notes.md") == 0                                   # not a post
    assert hook('gh issue comment 9 --body "Zorblax"', key=None) == 0          # no key: nothing to scrub with

    # review round 1, B1: only the posted words are scrubbed — a path, a cd, a --repo never reach GitHub
    home = tmp_path / "Zorblax-home"
    home.mkdir()
    clean = home / "clean.md"
    clean.write_text("a public sentence\n")
    assert hook(f"gh issue create --repo o/r --title t --body-file {clean.as_posix()}") == 0
    assert hook(f"cd {home.as_posix()} && gh issue close 91 --repo o/r --comment done") == 0
    assert hook(f"gh issue create --title t --body-file {clean.as_posix()} && echo {home.as_posix()}") == 0
    # B2: a body the hook cannot read is refused, never passed
    planted = home / "body.md"
    planted.write_text("fine\nZorblax\n")
    pay = lambda cmd, cwd=None: scrub.gh_hook(json.dumps({"tool_name": "Bash", "cwd": str(cwd) if cwd else None,
                                                          "tool_input": {"command": cmd}}), hashes, k)
    assert hook(f"gh issue create --title t --body-file={planted.as_posix()}") == 2        # the = form
    assert pay("gh issue create --title t -F body.md", cwd=home) == 2           # relative to the payload's cwd
    assert hook(f"cd {home.as_posix()} && gh issue create --title t -F body.md") == 2      # relative to a cd before it
    assert hook(f"cat {planted.as_posix()} | gh issue create --title t --body-file -") == 2
    assert "pipe" in capsys.readouterr().err
    assert hook(f"gh issue create --title t --body-file {(home / 'absent.md').as_posix()}") == 2
    assert "cannot be read" in capsys.readouterr().err
    assert hook("gh issue create --title t --body-file - <<'EOF'\nfor acme widgets\nEOF") == 2
    assert hook("gh issue create --title t --body-file - <<'EOF'\na public sentence\nEOF") == 0
    # review round 2, B3: a post is recognised from the parsed words, wherever gh's own flags sit and however gh is named
    for cmd in ("gh -R o/r issue create -t x -b Zorblax", "gh issue --repo o/r comment 1 -b Zorblax",
                "gh issue \\\ncomment 1 -b Zorblax", "/usr/bin/gh issue comment 1 -b Zorblax",
                "\"gh\" issue comment 1 -b Zorblax", "gh issue comment 1 -bZorblax", "gh --repo=o/r pr create --title fix#3 --body Zorblax",
                "sh -c 'gh issue comment 1 --body Zorblax'"):
        assert hook(cmd) == 2, cmd
    # B4: a value the shell builds (a substitution, a variable) is posted unread — refused, by name
    for cmd in (f"gh issue create -t x -b \"$(cat {planted.as_posix()})\"", f"gh issue create -t x -b \"`cat {planted.as_posix()}`\"",
                f"B=$(cat {planted.as_posix()}); gh issue create -t x -b \"$B\"", "cat notes | xargs gh issue comment 1 -b"):
        assert hook(cmd) == 2, cmd
        assert "SCRUB REFUSED" in capsys.readouterr().err
    # a word the shell builds is read when it can be: a literal assignment, the environment, `$(cat F)`
    assert hook(f"gh issue create -t x -b \"$(cat {clean.as_posix()})\"") == 0
    assert hook(f"D={home.as_posix()}; gh issue create -t x --body-file \"$D/clean.md\"") == 0
    assert hook(f"D={home.as_posix()}; gh issue create -t x --body-file \"$D/body.md\"") == 2
    assert hook("gh issue comment 1 --body \"$(git log -1 --format=%s)\"") == 2              # another command's output
    assert "another command's output" in capsys.readouterr().err
    assert hook("gh issue comment 1 --body \"closed as $UNSET_IN_THIS_COMMAND_ZZ\"") == 2
    # review round 3 — B5: every word after the post head travels except its envelope (a repo, a body-file path)
    assert hook("gh pr review 7 --comment --body Zorblax") == 2 and hook("gh pr review 7 -c -b Zorblax") == 2
    assert hook("gh issue edit 3 --add-label Zorblax") == 2
    assert hook(f"gh issue close 3 --comment done > {home.as_posix()}/log 2>&1") == 0          # a redirect target never travels
    assert hook(f"gh issue close 3 --comment done >{home.as_posix()}/log") == 0
    assert hook(f"gh release create v1 --notes-file {clean.as_posix()}") == 0 and hook(f"gh release edit v1 --notes-file {planted.as_posix()}") == 2
    # B6: what the shell would expand is expanded or refused, never read as its spelling
    note = home / "note.md"
    note.write_text("Zorblax\n")
    assert pay(f"gh issue comment 1 --body-file - <<EOF\nsee $(cat {note})\nEOF", cwd=home) == 2
    assert hook("echo Zorblax | gh issue comment 1 --body-file /dev/stdin") == 2
    assert hook("set -- Zorblax; gh issue comment 1 -b \"$1\"") == 2
    assert hook("f(){ gh issue comment 1 -b \"$@\"; }; f Zorblax") == 2
    assert pay("gh issue create -t x --body-file \"$PWD/body.md\"", cwd=home) == 2
    assert hook("gh issue comment 1 -b \"$HOSTNAME_OR_ANY_PROFILE_VAR\"") == 2        # a name the command did not set
    # B7: every verb that posts, and a shell's combined flags
    assert hook("gh issue reopen 1 --comment Zorblax") == 2 and hook("gh pr reopen 2 --comment Zorblax") == 2
    assert hook("bash -ec 'gh issue comment 1 --body Zorblax'") == 2
    assert hook("cd \"$UNSET_ZZ\" && gh issue view 3") == 0                            # a read never refuses on a cd
    assert hook("gh -R o/r issue view 9") == 0 and hook("gh issue list --repo o/r") == 0     # reads pass
    # single quotes are literal in bash: a markdown body with backticks and a `$` posts exactly what it spells
    assert hook("gh issue create --title t --body '## What\n`scrub.py` costs $5 and '\"'\"'$(nothing)'\"'\"' runs'") == 0
    assert hook("gh issue create --title t --body '## What\n`scrub.py` is for Zorblax'") == 2
    # a heredoc that feeds something else is never posted: a script beside a post in one command passes
    assert hook(f"python3 - <<'PY'\nsp = '{home.as_posix()}'\nprint(\"gh issue comment 1 --body x\")\nPY\ngh issue close 3 --comment done") == 0
    assert hook("gh issue comment 9 --body \"$(cat <<'EOF'\nit's fine\nEOF\n)\"") == 0
    assert hook("gh issue create --title \"a (parenthesised) title\" --body \"$(cat <<'EOF'\nfor acme widgets\nEOF\n)\"") == 2
    assert hook("gh issue comment 9 --body \"$(cat <<'EOF'\n1) the first\n2) a :) face\nEOF\n)\"") == 0


def test_RED_a_bare_tilde_in_a_posted_word_is_the_home_bash_posts(tmp_path, monkeypatch):
    """#91 round 15: `-b ~/x` posts `<home>/x`; a home whose name carries a marker travels, and the hook must see it."""
    home = tmp_path / "zorblax-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    texts = scrub.posted_texts("gh issue comment 1 -b ~/notes", str(tmp_path))
    assert any(str(home) in text for _label, text in texts), texts
    texts = scrub.posted_texts('B=~/notes; gh issue comment 1 -b "$B"', str(tmp_path))
    assert any(str(home) in text for _label, text in texts), texts
    quoted = scrub.posted_texts("gh issue comment 1 -b '~/notes'", str(tmp_path))
    assert not any(str(home) in text for _label, text in quoted), quoted   # quoted, bash posts the literal
