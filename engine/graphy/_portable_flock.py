"""fcntl where POSIX has it. Where it does not (native Windows), `fcntl.flock` is a named no-op:
`HAVE_FCNTL` is False and no lock is taken — the supported hosts are Linux and macOS (README).
"""
from __future__ import annotations

try:
    import fcntl  # type: ignore  # noqa: F401  — re-exported on POSIX
    HAVE_FCNTL = True
except ImportError:
    HAVE_FCNTL = False

    class _NoFcntl:
        LOCK_EX = 2
        LOCK_SH = 1
        LOCK_UN = 8
        LOCK_NB = 4

        @staticmethod
        def flock(*_args, **_kwargs) -> None:
            return None

    fcntl = _NoFcntl()  # type: ignore
