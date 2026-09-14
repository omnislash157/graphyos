#!/usr/bin/env python3
"""sweep — the box's repeat offenders, named before they are removed (graphyos #107).

    python3 sweep.py                  the census: every candidate with its size, age and why — deletes nothing
    python3 sweep.py --apply          the census, then every DEAD row removed → SWEEP OK: n removed · X freed
    python3 sweep.py --selftest       every rule proven on its own fixture → SWEEP SELFTEST OK

The offenders, and only these — each one a directory a run leaves behind and nothing reads again:

    /tmp/claude-<uid>/<project>/<session>/   a session's scratchpad and task outputs, dead when its
                                             transcript has not moved for --min-age hours
    /tmp/pytest-of-<user>/pytest-<n>/        a floor's tmp_path tree (pytest-current's target is kept)
    /tmp/graphy-gallery*/                    a gallery built by hand

Every root and candidate must be a real directory this user owns (lstat: no symlink, st_uid) or it is
not looked at. A candidate is KEPT, never swept, when its session's Claude Code process is still
registered and running (<home>/sessions/<pid>.json) or a live process names its id on its command line
(the config homes are ~/.claude*, $CLAUDE_CONFIG_DIR and every live process's own), or anything is younger than --min-age (its newest file, and for a
session its transcript) or any process on the box holds a file open under it or runs with its cwd there —
read from /proc, no lsof. A backup, an archive, a cache that needs a network to come back, a process:
never this file's to remove. It measures and says; --apply removes what it said. A session left idle
past --min-age with no process and then resumed has lost its scratchpad and task outputs: that is the
design, a scratchpad is temporary. A process /proc will not show this user (hidepid, another owner)
cannot hold a candidate; the scratchpad root is 0700 and this user's, so only this user's processes can.

Where it runs: the SessionEnd hook in .claude/settings.json (`--apply --quiet`), so every session that
ends takes the dead ones with it; the gate runs --selftest.
"""
from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path

SESSION_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
PYTEST_RUN = re.compile(r"^pytest-\d+$")
SESSION_IN_TEXT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def held_paths(proc: Path = Path("/proc")) -> list[str]:
    """Every path a process on the box holds open or runs in — the live set a sweep never touches."""
    held: list[str] = []
    for pid in proc.iterdir():
        if not pid.name.isdigit():
            continue
        try:
            held.append(os.readlink(pid / "cwd"))
        except OSError:
            pass
        try:
            fds = list((pid / "fd").iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                held.append(os.readlink(fd))
            except OSError:
                pass
    return held


def owned_dir(path: Path, uid: int) -> bool:
    """A real directory this user owns — never a symlink another user planted in a world-writable /tmp."""
    try:
        st = path.lstat()
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) and st.st_uid == uid


def tree_stats(root: Path) -> tuple[int, float]:
    """(bytes, newest mtime) over a tree, symlinks not followed."""
    size, newest = 0, root.lstat().st_mtime
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            try:
                st = os.lstat(os.path.join(dirpath, name))
            except OSError:
                continue
            newest = max(newest, st.st_mtime)
            if name in filenames:
                size += st.st_size
    return size, newest


def transcripts(homes: list[Path]) -> dict[str, float]:
    """session id → its transcript's mtime, over every Claude Code config home."""
    seen: dict[str, float] = {}
    for home in homes:
        for jsonl in home.glob("projects/*/*.jsonl"):
            try:
                seen[jsonl.stem] = max(seen.get(jsonl.stem, 0.0), jsonl.stat().st_mtime)
            except OSError:
                pass
    return seen


def live_sessions(homes: list[Path], proc: Path = Path("/proc")) -> set[str]:
    """Session ids a running Claude Code process registered (<home>/sessions/<pid>.json, pid alive)."""
    live: set[str] = set()
    for home in homes:
        for reg in home.glob("sessions/*.json"):
            if not reg.stem.isdigit() or not (proc / reg.stem).exists():
                continue
            try:
                sid = json.loads(reg.read_text()).get("sessionId")
            except (OSError, ValueError, AttributeError):
                continue
            if isinstance(sid, str):
                live.add(sid)
    for cmdline in proc.glob("[0-9]*/cmdline"):
        try:
            live.update(m.group(0) for m in SESSION_IN_TEXT.finditer(cmdline.read_bytes().decode("utf-8", "replace")))
        except OSError:
            pass
    return live


def config_homes(home: Path, proc: Path = Path("/proc")) -> list[Path]:
    """Every Claude Code config home: ~/.claude*, $CLAUDE_CONFIG_DIR, and the one each live process was started with."""
    found = set(home.glob(".claude*"))
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        found.add(Path(os.environ["CLAUDE_CONFIG_DIR"]))
    for environ in proc.glob("[0-9]*/environ"):
        try:
            for var in environ.read_bytes().split(b"\0"):
                if var.startswith(b"CLAUDE_CONFIG_DIR="):
                    found.add(Path(var.split(b"=", 1)[1].decode("utf-8", "replace")))
        except OSError:
            pass
    return sorted(p for p in found if (p / "projects").is_dir() or (p / "sessions").is_dir())


def candidates(tmp: Path, uid: int, user: str) -> list[tuple[str, Path]]:
    """(rule, path) for every directory an offender rule names."""
    out: list[tuple[str, Path]] = []
    claude = tmp / f"claude-{uid}"
    if owned_dir(claude, uid):
        for project in sorted(p for p in claude.iterdir() if owned_dir(p, uid)):
            for session in sorted(project.iterdir()):
                if SESSION_ID.match(session.name) and owned_dir(session, uid):
                    out.append(("scratchpad", session))
    pytest_root = tmp / f"pytest-of-{user}"
    if owned_dir(pytest_root, uid):
        for run in sorted(pytest_root.iterdir()):
            if PYTEST_RUN.match(run.name) and owned_dir(run, uid):
                out.append(("pytest", run))
    for gallery in sorted(tmp.glob("graphy-gallery*")):
        if owned_dir(gallery, uid):
            out.append(("gallery", gallery))
    return out


def census(tmp: Path, uid: int, user: str, homes: list[Path], held: list[str], now: float,
           min_age_h: float, live: set[str] = frozenset()) -> list[dict]:
    rows = []
    sessions = transcripts(homes)
    pytest_current = tmp / f"pytest-of-{user}" / "pytest-current"
    current = os.path.realpath(pytest_current) if pytest_current.is_symlink() else None
    horizon = now - min_age_h * 3600
    for rule, path in candidates(tmp, uid, user):
        try:
            size, newest = tree_stats(path)
        except OSError:  # another sweep removed it between the listing and the look
            continue
        spellings = {str(path), os.path.realpath(path)}
        holders = [h for h in held if any(h == sp or h.startswith(sp + os.sep) for sp in spellings)]
        why, dead = "", False
        if holders:
            why = f"held open by a live process ({holders[0]})"
        elif rule == "scratchpad" and path.name in live:
            why = "its session's Claude Code process is still running"
        elif rule == "pytest" and current in spellings:
            why = "pytest-current points here"
        elif newest > horizon:
            why = f"a file under it moved {(now - newest) / 3600:.1f}h ago"
        elif rule == "scratchpad" and sessions.get(path.name, 0.0) > horizon:
            why = f"its transcript moved {(now - sessions[path.name]) / 3600:.1f}h ago"
        else:
            dead = True
            why = {"scratchpad": "its session's transcript and files are quiet and no process holds it",
                   "pytest": "a finished floor's tmp tree no process holds",
                   "gallery": "a hand-built gallery no process holds"}[rule]
        rows.append({"rule": rule, "path": path, "bytes": size, "age_h": (now - newest) / 3600,
                     "dead": dead, "why": why})
    return rows


def human(n: float) -> str:
    for unit in ("B", "K", "M", "G"):
        if n < 1024 or unit == "G":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n}"


def sweep(rows: list[dict], apply: bool, quiet: bool) -> tuple[int, int]:
    removed = freed = 0
    for row in rows:
        verdict = "DEAD" if row["dead"] else "KEEP"
        if not quiet:
            print(f"{verdict} {human(row['bytes']):>7} {row['age_h']:7.1f}h  {row['rule']:<10} {row['path']} — {row['why']}")
        if apply and row["dead"]:
            shutil.rmtree(row["path"], ignore_errors=True)
            if not row["path"].exists():
                removed += 1
                freed += row["bytes"]
    return removed, freed


def selftest() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as scratch:
        scratch = os.path.realpath(scratch)  # /proc names real paths; so does the fixture
        tmp, home, proc = Path(scratch) / "tmp", Path(scratch) / "home", Path(scratch) / "proc"
        old, now, uid = time.time() - 48 * 3600, time.time(), os.getuid()
        sid = lambda n: f"{n:08x}-0000-0000-0000-000000000000"
        pad = tmp / f"claude-{uid}" / "proj"

        def make(path: Path, mtime: float) -> Path:
            path.mkdir(parents=True)
            (path / "f").write_text("x" * 10)
            for p in (path / "f", path):
                os.utime(p, (mtime, mtime))
            return path

        quiet_session = make(pad / sid(1), old)
        fresh_files = make(pad / sid(2), now)
        live_transcript = make(pad / sid(3), old)
        held_session = make(pad / sid(4), old)
        registered = make(pad / sid(5), old)
        old_files_fresh_dir = make(pad / sid(6), old)
        (old_files_fresh_dir / "sub").mkdir()
        os.utime(old_files_fresh_dir, (old, old))  # only the subdirectory is fresh
        named_on_a_cmdline = make(pad / sid(7), old)
        pytest_old = make(tmp / "pytest-of-u" / "pytest-1", old)
        pytest_cur = make(tmp / "pytest-of-u" / "pytest-2", old)
        (tmp / "pytest-of-u" / "pytest-current").symlink_to(pytest_cur)
        gallery = make(tmp / "graphy-gallery-58-before", old)
        expect = {quiet_session: True, fresh_files: False, live_transcript: False, held_session: False,
                  registered: False, old_files_fresh_dir: False, named_on_a_cmdline: False,
                  pytest_old: True, pytest_cur: False, gallery: True}

        # strays: nothing a rule names, or a link out of /tmp — never a candidate, never removed
        not_a_session = make(pad / "bundled-skills", old)
        not_a_run = make(tmp / "pytest-of-u" / "notarun", old)
        outside = make(tmp / "node_meta_dir", old)
        linked_session = make(Path(scratch) / "victim" / sid(8), old)
        (pad / sid(8)).symlink_to(linked_session)
        linked_root = make(Path(scratch) / "victim2" / "proj" / sid(9), old)
        (tmp / "pytest-of-v").symlink_to(Path(scratch) / "victim2")
        (Path(scratch) / "victim2" / "pytest-3").mkdir()
        other_tmp = Path(scratch) / "tmp2"
        other_tmp.mkdir()
        linked_claude_root = make(Path(scratch) / "victim3" / "proj" / sid(10), old)
        (other_tmp / f"claude-{uid}").symlink_to(Path(scratch) / "victim3")
        linked_project = make(Path(scratch) / "victim4" / sid(11), old)
        (pad.parent / "linkedproj").symlink_to(Path(scratch) / "victim4")
        strays = (not_a_session, not_a_run, outside, linked_session, linked_root, Path(scratch) / "victim2" / "pytest-3",
                  linked_claude_root, linked_project)

        (home / "projects" / "proj").mkdir(parents=True)
        for n, mtime in ((1, old), (3, now)):
            t = home / "projects" / "proj" / f"{sid(n)}.jsonl"
            t.write_text("{}")
            os.utime(t, (mtime, mtime))
        (home / "sessions").mkdir()
        (home / "sessions" / "4242.json").write_text(json.dumps({"pid": 4242, "sessionId": sid(5)}))
        (home / "sessions" / "4343.json").write_text(json.dumps({"pid": 4343, "sessionId": sid(1)}))
        (proc / "4242").mkdir(parents=True)
        (proc / "4444").mkdir()
        (proc / "4444" / "cmdline").write_bytes(b"claude\0--resume\0" + sid(7).encode() + b"\0")
        # a config home only a live process's environment names, and one only $CLAUDE_CONFIG_DIR names
        env_home, var_home = Path(scratch) / "envhome", Path(scratch) / "varhome"
        for h, n in ((env_home, 12), (var_home, 13)):
            (h / "sessions").mkdir(parents=True)
            (h / "sessions" / "4242.json").write_text(json.dumps({"pid": 4242, "sessionId": sid(n)}))
        (proc / "4444" / "environ").write_bytes(b"A=1\0CLAUDE_CONFIG_DIR=" + str(env_home).encode() + b"\0")
        saved = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = str(var_home)
        try:
            homes = config_homes(Path(scratch) / "nohome", proc)
        finally:
            os.environ.pop("CLAUDE_CONFIG_DIR") if saved is None else os.environ.__setitem__("CLAUDE_CONFIG_DIR", saved)
        env_kept, var_kept = make(pad / sid(12), old), make(pad / sid(13), old)
        live = live_sessions([home, *homes], proc)
        prefix_sibling = make(pad / (sid(14)[:-1] + "e"), old)  # a held path that only shares its prefix

        expect.update({env_kept: False, var_kept: False, prefix_sibling: True})
        if census(other_tmp, uid, "u", [home], [], now, 6.0, live):
            failures.append("a symlinked /tmp/claude-<uid> root was followed")
        if census(tmp, uid + 1, "u", [home], [], now, 6.0, live):
            failures.append("a tree another uid owns became a candidate")
        if any(r["rule"] == "pytest" for r in census(tmp, uid, "v", [home], [], now, 6.0, live)):
            failures.append("a symlinked pytest-of root was followed")
        (Path(scratch) / "tmplink").symlink_to(tmp)
        via_link = {r["path"].name: r["dead"] for r in census(Path(scratch) / "tmplink", uid, "u", [home],
                                                               [str(held_session / "f")], now, 6.0, live)}
        if via_link.get(held_session.name) is not False:
            failures.append("a file held under the real path did not keep a candidate reached through a linked /tmp")
        if via_link.get(pytest_cur.name) is not False:
            failures.append("pytest-current (a real path) did not keep its tree reached through a linked /tmp")
        rows = census(tmp, uid, "u", [home], [str(held_session / "f"), str(prefix_sibling)[:-1] + "ex/f"], now, 6.0, live)
        verdicts = {row["path"]: row["dead"] for row in rows}
        for path, dead in expect.items():
            if verdicts.get(path) is not dead:
                failures.append(f"{path.relative_to(scratch)}: expected {'DEAD' if dead else 'KEEP'}, got {verdicts.get(path)}")
        extra = set(verdicts) - set(expect)
        if extra:
            failures.append(f"no rule names {sorted(str(p.relative_to(scratch)) for p in extra)}, yet each is a candidate")

        removed, freed = sweep(rows, apply=True, quiet=True)
        if removed != 4 or freed != 40:
            failures.append(f"apply removed {removed} ({freed}B), expected 4 (40B)")
        for path, dead in expect.items():
            if path.exists() is dead:
                failures.append(f"{path.relative_to(scratch)}: after --apply exists={path.exists()}")
        if not all(p.exists() for p in strays):
            failures.append("--apply removed a stray: a directory no rule names, or one reached through a link")
    for failure in failures:
        print(f"SWEEP SELFTEST RED: {failure}")
    if failures:
        return 1
    print(f"SWEEP SELFTEST OK: {len(expect)} rule fixture(s) · {len(strays)} strays held (unnamed dirs · links to a session, a project, a claude root, a pytest root) · a foreign uid refused · a linked /tmp")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="remove every DEAD row after the census")
    ap.add_argument("--quiet", action="store_true", help="print only the closing line")
    ap.add_argument("--min-age", type=float, default=24.0, help="hours a candidate must be quiet (default 24)")
    ap.add_argument("--selftest", action="store_true", help="prove every rule on its own fixture")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    homes = config_homes(Path.home())
    user = pwd.getpwuid(os.getuid()).pw_name
    held, live, now = held_paths(), live_sessions(homes), time.time()
    roots = list(dict.fromkeys(os.path.realpath(t) for t in ("/tmp", tempfile.gettempdir())))
    rows = [row for root in roots
            for row in census(Path(root), os.getuid(), user, homes, held, now, args.min_age, live)]
    removed, freed = sweep(rows, args.apply, args.quiet)
    dead = [r for r in rows if r["dead"]]
    if args.apply:
        print(f"SWEEP OK: {removed} removed · {human(freed)} freed · {len(rows) - len(dead)} kept · under {' '.join(roots)}")
    else:
        print(f"SWEEP CENSUS: {len(dead)} dead · {human(sum(r['bytes'] for r in dead))} · "
              f"{len(rows) - len(dead)} kept under {' '.join(roots)} — nothing removed; --apply removes the dead")
    return 0


if __name__ == "__main__":
    sys.exit(main())
