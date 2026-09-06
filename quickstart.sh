#!/usr/bin/env bash
# graphy quickstart — bolt graphy onto a repo and eat it, end to end, timed.
#
#   bash quickstart.sh <git-url-or-path> [package]
#
# Needs python3 (3.10+), git, and network for the clone and the repo's dependencies.
# Leaves <repo>/.graphy/: the repo's dependencies in a venv of their own, the tenant descriptor,
# one shard per package in the import ring, the resolver's sidecars, the compiled store, the
# parquet beside every shard. Everything under .graphy/ is rebuilt by `graphy eat` and ignored
# by the eaten repo. The done token is the last line.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${1:?usage: quickstart.sh <git-url-or-path> [package]}"
PKG="${2:-}"
T0="$(date +%s.%N)"

# 1. graphy's own interpreter: graphyos and duckdb, nothing else
if [ ! -x "$HERE/.venv/bin/graphy" ]; then
    python3 -m venv "$HERE/.venv"
    "$HERE/.venv/bin/pip" install -q --disable-pip-version-check -e "$HERE/engine[estate]"
fi
GRAPHY="$HERE/.venv/bin/graphy"

# 2. the repo: a path as it stands, or a shallow clone under staging/quickstart/
if [ -d "$SRC" ]; then
    REPO="$(cd "$SRC" && pwd)"
else
    NAME="$(basename "${SRC%.git}")"
    REPO="$HERE/staging/quickstart/$NAME"
    [ -d "$REPO/.git" ] || git clone -q --depth 1 "$SRC" "$REPO"
fi
echo "quickstart: $REPO"

# 3. the repo's dependencies — the import ring is resolved from where they are installed.
#    A Python repo: a venv of its own. A TypeScript repo (package.json, no importable Python
#    package): its node_modules, via npm; the typescript_ast producer needs graphyos[typescript].
mkdir -p "$REPO/.graphy"
if [ -f "$REPO/package.json" ] && ! ls "$REPO"/*/__init__.py "$REPO"/src/*/__init__.py >/dev/null 2>&1; then
    "$HERE/.venv/bin/python" -c "import tree_sitter_typescript" 2>/dev/null \
        || "$HERE/.venv/bin/pip" install -q --disable-pip-version-check -e "$HERE/engine[typescript]"
    (cd "$REPO" && npm install --ignore-scripts --no-audit --no-fund --silent) \
        || echo "quickstart: npm install failed; the ring is whatever node_modules already holds"
    SP="$REPO/node_modules"
else
    [ -x "$REPO/.graphy/venv/bin/python" ] || python3 -m venv "$REPO/.graphy/venv"
    "$REPO/.graphy/venv/bin/pip" install -q --disable-pip-version-check "$REPO" \
        || echo "quickstart: the repo did not pip-install; the ring will be the root shard alone"
    SP="$("$REPO/.graphy/venv/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
fi

# 4. eat it: mint the package and its ring, declare the tenant, resolve, build, container, audit
"$GRAPHY" eat --repo "$REPO" --site-packages "$SP" ${PKG:+--package "$PKG"}

# 5. ask it two things: the estate in SQL, and a walk from the package into its first dependency
DESC="$REPO/.graphy/tenant.json"
read -r TID SEED TARGET < <("$HERE/.venv/bin/python" - "$REPO/.graphy/substrate/ring.json" <<'PY'
import json, sys
ring = json.load(open(sys.argv[1]))
root = ring["root"]
deps = [s for s in ring["minted"] if s != root]
print(root, f"{root}://module/{root}", f"{deps[0]}://module/{deps[0]}" if deps else f"{root}://module/{root}")
PY
)
"$GRAPHY" estate --tenant "$DESC" --tenant-id "$TID" \
    --sql "SELECT a.corpus AS from_corpus, n.corpus AS into_corpus, count(*) AS edges FROM adj a JOIN nodes n ON a.dst = n.id WHERE a.corpus <> n.corpus GROUP BY 1, 2 ORDER BY 3 DESC"
"$GRAPHY" walk --tenant "$DESC" --tenant-id "$TID" --seed "$SEED" --target "$TARGET"

# 6. the done token, timed
SECS="$(python3 -c "import time; print(f'{time.time() - $T0:.1f}')")"
echo "GRAPHY_QUICKSTART_OK: $TID eaten in ${SECS}s -> $REPO/.graphy"
