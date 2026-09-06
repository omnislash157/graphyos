#!/usr/bin/env bash
# express tenant — JavaScript through the typescript_ast producer: CommonJS, a real ring. Rebuild from scratch: pin the checkout, mint the package and
# its ring with the typescript_ast producer, init, converge, build, check, fan out, verify the arms.
# Idempotent. Every path is derived from this file's location; nothing is ambient.
#
#   EXPRESS_RELEASE=<tag>                   the git tag to pin (default v5.2.1); the checkout lives at
#                                        staging/corpora/ts/express and is fetched when absent or off-tag
#   EXPRESS_NODE_MODULES=<abs>           the node_modules the ring is resolved from (default: the
#                                        checkout's own, `npm install --omit=dev` when absent — the
#                                        runtime ring, every package of it JavaScript)
#   GRAPHY_CORPUS=<abs dir>              mint from another JavaScript tree instead of the checkout's lib/
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-python3}"
"$PY" -c "import graphy" 2>/dev/null || export PYTHONPATH="$ENGINE${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -c "import tree_sitter, tree_sitter_typescript" 2>/dev/null \
    || { echo "REBUILD REFUSED: the typescript_ast producer needs tree-sitter — pip install 'graphyos[typescript]' (PYTHON=<an interpreter that has it>)" >&2; exit 2; }

SUB="$HERE/substrate"
DESC="$HERE/tenant.json"
RELEASE="${EXPRESS_RELEASE:-v5.2.1}"
CHECKOUT="$ENGINE/../staging/corpora/ts/express"
CORPUS="${GRAPHY_CORPUS:-}"

if [ -z "$CORPUS" ]; then
    if [ ! -d "$CHECKOUT/.git" ]; then
        mkdir -p "$(dirname "$CHECKOUT")"
        git clone -q --depth 1 --branch "$RELEASE" https://github.com/expressjs/express.git "$CHECKOUT"
    fi
    have="$(git -C "$CHECKOUT" describe --tags --exact-match 2>/dev/null || true)"
    if [ "$have" != "$RELEASE" ]; then
        git -C "$CHECKOUT" fetch -q --depth 1 origin "refs/tags/$RELEASE:refs/tags/$RELEASE"
        git -C "$CHECKOUT" checkout -q "$RELEASE"
    fi
    echo "CHECKOUT: express $RELEASE at $CHECKOUT ($(git -C "$CHECKOUT" rev-parse --short HEAD))" >&2
    CORPUS="$CHECKOUT/lib"
fi
[ -d "$CORPUS" ] || { echo "REBUILD REFUSED: no TypeScript corpus at $CORPUS" >&2; exit 2; }
# The ring: express's runtime dependencies, installed into the checkout's own node_modules
# (`npm install --omit=dev`) when absent — every one ships JavaScript, and every one mints.
NM="${EXPRESS_NODE_MODULES:-}"
if [ -z "$NM" ]; then
    NM="$(dirname "$CORPUS")/node_modules"
    if [ ! -d "$NM" ]; then
        (cd "$(dirname "$CORPUS")" && npm install --omit=dev --ignore-scripts --no-audit --no-fund --silent)
        echo "RING: runtime dependencies installed at $NM" >&2
    fi
fi

KEEP="$HERE/.traversals.keep"
rm -rf "$KEEP"
[ -d "$SUB/traversals" ] && mv "$SUB/traversals" "$KEEP"
rm -rf "$SUB" "$DESC"
if [ -d "$KEEP" ]; then mkdir -p "$SUB" && mv "$KEEP" "$SUB/traversals"; fi

"$PY" -m graphy smash --package express --site-packages "$NM" --corpus "$CORPUS" --out "$SUB" --producer typescript_ast
LANES="$("$PY" - "$SUB/ring.json" <<'PY'
import json, sys
ring = json.load(open(sys.argv[1], encoding="utf-8"))
print(" ".join(f"--lane {m['slug']}_graph:static-dep" for m in ring["minted"].values()))
PY
)"
CURSOR="git:$(git -C "$(dirname "$CORPUS")" rev-parse HEAD 2>/dev/null || sha256sum "$SUB/express_graph/edges.json" | cut -c1-64)"
eval "set -- $LANES"
"$PY" -m graphy init --tenant "$DESC" --root "$HERE" --data-home "$SUB" \
    --join-keys "$SUB/registry.json" --journal "$SUB/journal" --cursor "$CURSOR" \
    --policy refuse --adapter typescript_ast "$@"
"$PY" - "$SUB" <<'PY'
import json, sys
from pathlib import Path
sub = Path(sys.argv[1])
receipt = json.loads((sub / "ring.json").read_text(encoding="utf-8"))
index = {"_meta": {"description": "express tenant scheme index — derived from ring.json by rebuild.sh",
                   "standard": receipt["standard"]}, **receipt["scheme_index"]}
(sub / ".federation_scheme_index.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n", encoding="utf-8")
PY
"$PY" -m graphy converge --tenant "$DESC" --tenant-id express --resolve
"$PY" -m graphy build --tenant "$DESC" --tenant-id express
"$PY" -m graphy check --tenant "$DESC" --tenant-id express
"$PY" -m graphy fanout --graph-dir "$SUB/express_graph" --out "$SUB/fanout" --partition "$HERE/partition.json"
"$PY" -m graphy fanout --verify --out "$SUB/fanout"
"$PY" -m graphy arms --tenant "$DESC" --tenant-id express --corpus express --partition "$HERE/partition.json" --dir "$HERE/arms" --verify
# The atlas: the pillars, the unit map and one drawing per arm, ascii and html, computed from the
# store — a build product under the substrate with a receipt.
"$PY" -m graphy draw --tenant "$DESC" --tenant-id express --corpus express --partition "$HERE/partition.json" --atlas "$SUB/atlas" --lr --min-weight 2
# The walk says express is one pillar (five modules, every one consumed more than it consumes):
# the proposal is that sentence, and the curated partition cuts by module instead.
"$PY" -m graphy pillars --tenant "$DESC" --tenant-id express --corpus express > "$SUB/pillars.txt" 2>&1 || true
tail -n 1 "$SUB/pillars.txt"
echo "EXPRESS_TENANT_OK"
