#!/usr/bin/env bash
# graphy quickstart — the two lines, timed: install graphyos, then eat a repo.
#
#   bash quickstart.sh <git-url-or-path>
#
# Needs python3 (3.10+) and git; npm for a package.json repo. Leaves <repo>/.graphy/ — the
# repo's dependencies provisioned by eat itself, one shard per package in the ring, the resolver's
# sidecars, the compiled store — and prints the MCP block, the drawing and three questions. The
# done token is the last line.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${1:?usage: quickstart.sh <git-url-or-path>}"
T0="$(date +%s.%N)"

# line 1: pip install graphyos   (from this checkout until it is on PyPI; the extras are optional)
if [ ! -x "$HERE/.venv/bin/graphy" ]; then
    python3 -m venv "$HERE/.venv"
    "$HERE/.venv/bin/pip" install -q --disable-pip-version-check -e "$HERE/engine[estate,typescript]"
fi

# the repo: a path as it stands, or a shallow clone under staging/quickstart/
if [ -d "$SRC" ]; then
    REPO="$(cd "$SRC" && pwd)"
else
    NAME="$(basename "${SRC%.git}")"
    REPO="$HERE/staging/quickstart/$NAME"
    [ -d "$REPO/.git" ] || git clone -q --depth 1 "$SRC" "$REPO"
fi

# line 2: graphy eat .
( cd "$REPO" && "$HERE/.venv/bin/graphy" eat . )

# the done token, timed
SECS="$(python3 -c "import time; print(f'{time.time() - $T0:.1f}')")"
echo "GRAPHY_QUICKSTART_OK: $(basename "$REPO") eaten in ${SECS}s -> $REPO/.graphy"
