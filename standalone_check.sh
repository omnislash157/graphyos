#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGE="$HERE/engine"
[ -d "$STAGE" ] || { echo "NO ENGINE DIR: $STAGE"; exit 1; }

VENV="$(mktemp -d)/venv"
trap 'rm -rf "$(dirname "$VENV")"' EXIT
python3 -m venv "$VENV"
PY="$VENV/bin/python"

"$PY" -m pip install -q --upgrade pip
( cd "$STAGE" && "$PY" -m pip install -q -e ".[dev,typescript,estate]" )
echo "install            OK"

env -u PYTHONPATH "$PY" -I - "$HERE/.private_modules" <<'PY'
import importlib.util as u
import sys

# The host's own module names never travel: .private_modules (gitignored) lists them on this box.
import pathlib
_f = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None
HOST = [ln.strip() for ln in _f.read_text().splitlines() if ln.strip() and not ln.startswith("#")] if _f and _f.is_file() else []
if not HOST:
    print("host unreachable   SKIPPED (no .private_modules beside standalone_check.sh — nothing to probe on this box)")
leaked = [m for m in HOST if u.find_spec(m) is not None]
if leaked:
    sys.exit(f"DEPARTURE BROKEN — the product can import its host: {leaked}")
print("host unreachable   OK")

import graphy
print(f"graphy resolves    OK  ({graphy.__version__})  {graphy.__file__}")
PY

( cd "$STAGE" && env -u PYTHONPATH "$PY" -m pytest -q )

# The prose scrub never names what it scrubs: scrub.py hashes every token of every file against
# .private_markers.sha256 (hashes only; the words never travel). Two sweeps: the staged engine
# tree as it would ship, and every git-tracked file outside staging/ — the public cut's tripwire.
# A tenant's descriptor and substrate (and a refresh's sibling) are skipped by name: rebuilt on
# each machine, gitignored, carrying that machine's absolute paths.
python3 "$HERE/scrub.py" --tree "$STAGE" || { echo "prose scrub        FAILED — private language in the engine tree"; exit 3; }
python3 "$HERE/scrub.py" --tracked || { echo "prose scrub        FAILED — private language in a tracked file outside staging/"; exit 3; }
echo "prose scrub        OK"
bash "$HERE/release.sh" --check
python3 "$HERE/burden.py" || { echo "burden            FAILED — a responsibility grew without burden.json saying so"; exit 3; }
# The workflow files parse here, on the box, before CI is asked: a file GitHub cannot parse runs
# zero jobs and nobody sees CI stop (RECON.md §58). stdlib only; every refusal names file:line.
python3 "$HERE/workflows.py" || { echo "workflows          FAILED — a file under .github/workflows/ would run zero jobs"; exit 3; }

echo "GRAPHY_STANDALONE_OK"
