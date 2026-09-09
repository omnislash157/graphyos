"""A pytest plugin that logs every real `os.fsync` the floor makes — caller and test, milliseconds — the
wall clock behind RECON §97's number. Run from engine/:

    FS_LOG=/tmp/fs.log python -m pytest -q -p tests.fsync_log -p no:cacheprovider
    python3 -c "import json; r=[json.loads(l) for l in open('/tmp/fs.log')]; print(len(r), 'fsync', round(sum(x['ms'] for x in r)), 'ms')"

Loaded before conftest's no-op, so it wraps the real call; a test the no-op covers logs nothing."""
from __future__ import annotations

import json
import os
import time
import traceback

LOG = os.environ.get("FS_LOG", "/tmp/graphy-fsync.log")
_real = os.fsync


def _logged(fd):
    t = time.perf_counter()
    r = _real(fd)
    who = next((f"{os.path.basename(x.filename)}:{x.name}" for x in reversed(traceback.extract_stack(limit=6)[:-1])
                if "graphy" in x.filename), "?")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ms": round((time.perf_counter() - t) * 1e3, 2), "who": who,
                            "test": os.environ.get("PYTEST_CURRENT_TEST", "")[:100]}) + "\n")
    return r


os.fsync = _logged
