"""The floor's one convention (graphyos #62): a store a test builds under tmp_path is thrown away, so
the durability the product pays — one fsync of the finished store before the rename (RECON §59) — is
a counted no-op here: 107 fsyncs, 390 ms of a 10 s floor, the disk's answer every run and 7 s once.
The engine is untouched. A test that proves a sync is marked `durable` and gets the real call; it can
assert `os.fsync is not conftest.NO_FSYNC` to know it did. A new engine fsync written without the mark
is a no-op in the floor, by this convention and this docstring — the log plugin (`-p tests.fsync_log`)
shows what really reached the kernel."""
from __future__ import annotations

import os

import pytest

REAL_FSYNC = os.fsync
SKIPPED = {"calls": 0}


def NO_FSYNC(fd) -> None:
    SKIPPED["calls"] += 1


def pytest_configure(config):
    config.addinivalue_line("markers", "durable: the test proves the real fsync; the floor's no-op is not applied")


@pytest.fixture(autouse=True)
def _no_fsync_for_a_store_nobody_keeps(request, monkeypatch):
    if request.node.get_closest_marker("durable"):
        assert os.fsync is REAL_FSYNC or os.fsync is not NO_FSYNC
        return
    monkeypatch.setattr(os, "fsync", NO_FSYNC)
