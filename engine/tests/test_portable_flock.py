"""graphy._portable_flock — one exclusive lock on every host (graphyos #122).

Before #122 the module was a named no-op wherever `fcntl` was absent, so on native Windows two
concurrent journal appends minted one seq. Now `fcntl` there is `MsvcrtFlock` over `msvcrt.locking`.
The Linux floor cannot import `msvcrt`, so it drives the class through a shim whose `locking` is a
real `fcntl.flock` on the same descriptor: what is proven here is the class's own contract — it
blocks while another descriptor holds the byte, it polls rather than gives up, `LOCK_NB` raises
`BlockingIOError` like `fcntl`, it locks the byte at `LOCK_OFFSET` and puts the descriptor's
position back. What `msvcrt.locking` itself does is proven by CI's `store-windows` job, which
runs the three concurrency tests #122 measured red on windows-latest.
"""
from __future__ import annotations

import errno
import os
import sys
import threading

import pytest

from graphy import _portable_flock as pf

try:
    import fcntl
except ImportError:  # native Windows: the shim tests skip, the host tests run
    fcntl = None

needs_shim = pytest.mark.skipif(fcntl is None, reason="the shim needs a real advisory lock to stand in for msvcrt")


class _ShimMsvcrt:
    """`msvcrt.locking`'s surface over `fcntl.flock`: LK_NBLCK refuses a held byte with EACCES,
    exactly the errno the real one raises; the position at each call is recorded."""
    LK_UNLCK = 0
    LK_LOCK = 1
    LK_NBLCK = 2

    def __init__(self) -> None:
        self.positions: list[int] = []
        self.calls: list[int] = []

    def locking(self, fd: int, mode: int, nbytes: int) -> None:
        assert nbytes == 1
        self.positions.append(os.lseek(fd, 0, os.SEEK_CUR))
        self.calls.append(mode)
        if mode == self.LK_UNLCK:
            fcntl.flock(fd, fcntl.LOCK_UN)
            return
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise OSError(errno.EACCES, "Permission denied") from exc


def test_the_host_holds_a_real_lock_and_says_which():
    assert pf.LOCKING in ("fcntl", "msvcrt")
    assert pf.HAVE_FCNTL is (pf.LOCKING == "fcntl")
    assert pf.HAVE_FCNTL is (sys.platform != "win32")
    assert hasattr(pf.fcntl, "flock") and hasattr(pf.fcntl, "LOCK_EX") and hasattr(pf.fcntl, "LOCK_UN")


@needs_shim
def test_RED_the_msvcrt_path_blocks_a_second_descriptor_until_release(tmp_path):
    """the pre-#122 module had no msvcrt path: this test could not even instantiate it"""
    shim = _ShimMsvcrt()
    lock = pf.MsvcrtFlock(shim)
    path = tmp_path / "x.lock"
    path.write_bytes(b"content the lock byte must sit past\n")
    fa = open(path, "r+b")
    fb = open(path, "r+b")
    try:
        lock.flock(fa.fileno(), lock.LOCK_EX)
        entered = threading.Event()
        released = threading.Event()

        def worker():
            lock.flock(fb.fileno(), lock.LOCK_EX)
            entered.set()
            assert released.is_set(), "B took the lock while A held it"
            lock.flock(fb.fileno(), lock.LOCK_UN)

        t = threading.Thread(target=worker)
        t.start()
        assert not entered.wait(timeout=0.2), "B must BLOCK on the held byte — a no-op admits it at once"
        assert shim.calls.count(shim.LK_NBLCK) >= 2, "a blocked acquire polls, it does not give up"
        released.set()
        lock.flock(fa.fileno(), lock.LOCK_UN)
        assert entered.wait(timeout=10), "B never got the lock after A released"
        t.join(timeout=10)
        assert not t.is_alive()
    finally:
        fa.close()
        fb.close()


@needs_shim
def test_the_lock_byte_is_past_the_content_and_the_position_is_put_back(tmp_path):
    shim = _ShimMsvcrt()
    lock = pf.MsvcrtFlock(shim)
    path = tmp_path / "j.jsonl"
    path.write_bytes(b"line one\nline two\n")
    with open(path, "a+b") as fh:
        fh.seek(3)
        before = os.lseek(fh.fileno(), 0, os.SEEK_CUR)
        lock.flock(fh.fileno(), lock.LOCK_EX)
        assert os.lseek(fh.fileno(), 0, os.SEEK_CUR) == before, "the descriptor moved under the caller"
        fh.seek(0)
        assert fh.read() == b"line one\nline two\n", "a locked file still reads whole on its own handle"
        lock.flock(fh.fileno(), lock.LOCK_UN)
    assert shim.positions and all(p == pf.LOCK_OFFSET for p in shim.positions), shim.positions
    assert pf.LOCK_OFFSET > 1 << 30 and pf.LOCK_OFFSET < 1 << 31
    assert path.stat().st_size == len(b"line one\nline two\n"), "locking past the end extended the file"


@needs_shim
def test_lock_nb_raises_blocking_io_error_like_fcntl(tmp_path):
    shim = _ShimMsvcrt()
    lock = pf.MsvcrtFlock(shim)
    path = tmp_path / "x.lock"
    path.touch()
    with open(path, "r+b") as fa, open(path, "r+b") as fb:
        lock.flock(fa.fileno(), lock.LOCK_EX)
        with pytest.raises(BlockingIOError):
            lock.flock(fb.fileno(), lock.LOCK_EX | lock.LOCK_NB)
        lock.flock(fa.fileno(), lock.LOCK_UN)
        lock.flock(fb.fileno(), lock.LOCK_EX | lock.LOCK_NB)
        lock.flock(fb.fileno(), lock.LOCK_UN)


def test_an_errno_that_is_not_a_held_byte_is_raised_not_polled(tmp_path):
    class _Broken:
        LK_UNLCK, LK_LOCK, LK_NBLCK = 0, 1, 2

        def locking(self, fd, mode, nbytes):
            raise OSError(errno.EBADF, "Bad file descriptor")

    lock = pf.MsvcrtFlock(_Broken())
    path = tmp_path / "x.lock"
    path.touch()
    with open(path, "r+b") as fh:
        with pytest.raises(OSError) as ei:
            lock.flock(fh.fileno(), lock.LOCK_EX)
        assert ei.value.errno == errno.EBADF
        with pytest.raises(ValueError):
            lock.flock(fh.fileno(), 0)


def test_every_lock_site_in_the_engine_reads_the_one_helper():
    """one copy: no engine module takes its own msvcrt or fcntl lock beside the helper"""
    import re
    from pathlib import Path
    import graphy
    root = Path(graphy.__file__).parent
    own = re.compile(r"^\s*(?:import\s+(?:msvcrt|fcntl)\b|from\s+(?:msvcrt|fcntl)\s+import\b)|msvcrt\.locking",
                     re.M)
    offenders = []
    for py in sorted(root.rglob("*.py")):
        if py.name == "_portable_flock.py":
            continue
        if own.search(py.read_text(encoding="utf-8")):
            offenders.append(py.relative_to(root).as_posix())
    assert offenders == [], offenders
