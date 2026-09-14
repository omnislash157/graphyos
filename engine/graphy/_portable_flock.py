"""One exclusive file lock on every host, behind `fcntl.flock`'s own signature.

POSIX has `fcntl`, and it is re-exported whole. Native Windows has no `fcntl`; it has
`msvcrt.locking`, a mandatory byte-range lock on the descriptor's current position, and
`fcntl` here is `MsvcrtFlock` — `flock(fd, LOCK_EX | LOCK_UN [| LOCK_NB])` over one byte of the
file. The byte is `LOCK_OFFSET`, far past any content a journal or a lock file will hold, so a
reader opening the same file through another handle is never refused a byte the writer holds
(a Windows lock is mandatory; `flock` is advisory, and the callers were written for advisory).
The descriptor's position is put back where it was, so a caller that reads after locking reads
what it expected. `LOCK_EX` waits by polling `LK_NBLCK` (`LK_LOCK` sleeps a whole second per
retry and gives up after ten); `LOCK_NB` tries once and raises `BlockingIOError`, as `fcntl` does.

Before graphyos #122 this was a named no-op off POSIX: two concurrent journal appends minted one
seq. `LOCKING` says which lock this process holds — `fcntl` or `msvcrt` — and there is no third value.
"""
from __future__ import annotations

import errno
import os
import time

__all__ = ["fcntl", "HAVE_FCNTL", "LOCKING", "LOCK_OFFSET", "MsvcrtFlock"]

# One byte, far past any content the locked file will ever hold, and below 2**31 so the CRT's
# own seek never truncates it.
LOCK_OFFSET = (1 << 31) - 2
_POLL_SECONDS = 0.005
# `msvcrt.locking` refuses a held byte with EACCES (LK_NBLCK) or EDEADLOCK (LK_LOCK, after its retries).
_HELD = frozenset(e for e in (
    errno.EACCES, getattr(errno, "EDEADLOCK", None), getattr(errno, "EDEADLK", None),
    errno.EAGAIN, errno.EWOULDBLOCK) if e is not None)


class MsvcrtFlock:
    """`fcntl.flock` over `msvcrt.locking`. The module is a parameter so the floor can drive the
    class on a host that has no `msvcrt`, through a shim backed by a real lock."""

    LOCK_SH = 1
    LOCK_EX = 2
    LOCK_NB = 4
    LOCK_UN = 8

    def __init__(self, msvcrt_module) -> None:
        self._m = msvcrt_module

    def _locking(self, fd: int, mode: int) -> None:
        # msvcrt locks from the descriptor's current position; move there, lock, move back.
        was = os.lseek(fd, 0, os.SEEK_CUR)
        os.lseek(fd, LOCK_OFFSET, os.SEEK_SET)
        try:
            self._m.locking(fd, mode, 1)
        finally:
            os.lseek(fd, was, os.SEEK_SET)

    def flock(self, fd: int, operation: int) -> None:
        if operation & self.LOCK_UN:
            self._locking(fd, self._m.LK_UNLCK)
            return
        if not operation & (self.LOCK_EX | self.LOCK_SH):
            raise ValueError(f"_portable_flock: unknown flock operation {operation!r}")
        # msvcrt has no shared lock; LOCK_SH is exclusive here, which is the safe direction.
        nonblocking = bool(operation & self.LOCK_NB)
        while True:
            try:
                self._locking(fd, self._m.LK_NBLCK)
                return
            except OSError as exc:
                if exc.errno not in _HELD:
                    raise
                if nonblocking:
                    raise BlockingIOError(errno.EWOULDBLOCK, os.strerror(errno.EWOULDBLOCK)) from exc
            time.sleep(_POLL_SECONDS)


try:
    import fcntl  # type: ignore  # noqa: F401  — re-exported on POSIX
    HAVE_FCNTL = True
    LOCKING = "fcntl"
except ImportError:
    HAVE_FCNTL = False
    import msvcrt  # native Windows: the standard library's own lock, no dependency

    fcntl = MsvcrtFlock(msvcrt)  # type: ignore
    LOCKING = "msvcrt"
