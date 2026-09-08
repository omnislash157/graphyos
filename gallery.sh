#!/usr/bin/env bash
# gallery — ten showcases of repos people know into one directory that is the site (graphyos #47).
#   bash gallery.sh <out dir> <git url>…        e.g. bash gallery.sh gallery $(cat gallery.txt)
# The interpreter: PYTHON, else the project's .venv, else python3 (graphy must import there).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-}"
[ -n "$PY" ] || { [ -x "$HERE/.venv/bin/python" ] && PY="$HERE/.venv/bin/python" || PY="python3"; }
exec "$PY" "$HERE/gallery.py" "$@"
