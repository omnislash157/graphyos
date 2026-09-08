#!/usr/bin/env bash
# hono tenant — the second language. Rebuild from scratch: pin the checkout, mint the package and
# its ring with the typescript_ast producer, init, converge, build, check, fan out, verify the arms.
# Idempotent. Every path is derived from this file's location; nothing is ambient.
#
#   HONO_RELEASE=<tag>                   the git tag to pin (default v4.13.7); the checkout lives at
#                                        staging/corpora/ts/hono and is fetched when absent or off-tag
#   HONO_NODE_MODULES=<abs>              the node_modules the ring is resolved from (default: a
#                                        node_modules beside the checkout holding zod, the one
#                                        devDependency that ships TypeScript source; the ring
#                                        receipt names every other specifier the corpus imports)
#   GRAPHY_CORPUS=<abs src dir>          mint from another TypeScript tree instead of the checkout
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-python3}"
"$PY" -c "import graphy" 2>/dev/null || export PYTHONPATH="$ENGINE${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -c "import tree_sitter, tree_sitter_typescript" 2>/dev/null \
    || { echo "REBUILD REFUSED: the typescript_ast producer needs tree-sitter — pip install 'graphyos[typescript]' (PYTHON=<an interpreter that has it>)" >&2; exit 2; }

SUB="$HERE/substrate"
DESC="$HERE/tenant.json"
RELEASE="${HONO_RELEASE:-v4.13.7}"
CHECKOUT="$ENGINE/../staging/corpora/ts/hono"
CORPUS="${GRAPHY_CORPUS:-}"

if [ -z "$CORPUS" ] && [ -z "${GRAPHY_SHARD_INDEX:-}" ]; then
    if [ ! -d "$CHECKOUT/.git" ]; then
        mkdir -p "$(dirname "$CHECKOUT")"
        git clone -q --depth 1 --branch "$RELEASE" https://github.com/honojs/hono.git "$CHECKOUT"
    fi
    have="$(git -C "$CHECKOUT" describe --tags --exact-match 2>/dev/null || true)"
    if [ "$have" != "$RELEASE" ]; then
        git -C "$CHECKOUT" fetch -q --depth 1 origin "refs/tags/$RELEASE:refs/tags/$RELEASE"
        git -C "$CHECKOUT" checkout -q "$RELEASE"
    fi
    echo "CHECKOUT: hono $RELEASE at $CHECKOUT ($(git -C "$CHECKOUT" rev-parse --short HEAD))" >&2
    CORPUS="$CHECKOUT/src"
fi
[ -n "${GRAPHY_SHARD_INDEX:-}" ] || [ -d "$CORPUS" ] || { echo "REBUILD REFUSED: no TypeScript corpus at $CORPUS" >&2; exit 2; }
# The ring. Hono declares no runtime dependency, so the checkout's own node_modules (when npm has
# run there) holds only devDependencies. One of them, zod, ships its TypeScript source, and the
# tests import it: provisioning that one package beside the checkout gives the tenant a real ring
# to cross — a sibling shard and the `hono -> zod` wormholes — without installing the toolchain.
NM="${HONO_NODE_MODULES:-}"
if [ -z "$NM" ] && [ -z "${GRAPHY_SHARD_INDEX:-}" ]; then
    RING="$ENGINE/../staging/corpora/ts/hono_ring"
    if [ ! -d "$RING/node_modules/zod/src" ]; then
        mkdir -p "$RING" && (cd "$RING" && npm install --no-audit --no-fund --silent --ignore-scripts "zod@${HONO_RING_ZOD:-4}")
        echo "RING: zod provisioned at $RING/node_modules" >&2
    fi
    NM="$RING/node_modules"
fi

KEEP="$HERE/.traversals.keep"
rm -rf "$KEEP"
[ -d "$SUB/traversals" ] && mv "$SUB/traversals" "$KEEP"
rm -rf "$SUB" "$DESC"
if [ -d "$KEEP" ]; then mkdir -p "$SUB" && mv "$KEEP" "$SUB/traversals"; fi

INDEX="${GRAPHY_SHARD_INDEX:-}"
if [ -n "$INDEX" ]; then
    # From an index instead of a mint: every name in GRAPHY_PULL pulled and declared as a `pulled`
    # lane whose command is the pull itself. The roster names one release per scheme.
    mkdir -p "$SUB"
    LANES="$("$PY" - "$SUB" "$INDEX" "${GRAPHY_PULL:-}" <<'PY'
import json, shlex, sys
from pathlib import Path
from graphy import index as shard_index
from graphy.smash import slug_for_specifier
sub, idx, names = Path(sys.argv[1]), sys.argv[2], sys.argv[3].split()
if not names:
    sys.exit("REBUILD REFUSED: GRAPHY_PULL must name the shards to pull (e.g. 'hono==4.13.7 zod==4.5.4')")
lanes = []
for name in names:
    tmp = sub / f".pull.{name}"
    m = shard_index.pull(name, idx, tmp)
    prov = json.loads((tmp / "PROVENANCE.json").read_text(encoding="utf-8"))
    slug = slug_for_specifier(prov["corpus"]["scheme"]) or prov["corpus"]["scheme"]
    tmp.rename(sub / f"{slug}_graph")
    lanes.append(f"--lane={slug}_graph:pulled=" + f"python3 -m graphy pull {name} --index {shlex.quote(idx)} --out {{out}}")
    print(f"PULL OK: {name} -> {slug}_graph ({m['address'][:12]}…)", file=sys.stderr)
print(" ".join(shlex.quote(l) for l in lanes))
PY
)"
    [ -f "$SUB/hono_graph/nodes.json" ] || { echo "REBUILD REFUSED: the pull brought no hono_graph" >&2; exit 2; }
else
    "$PY" -m graphy smash --package hono --site-packages "$NM" --corpus "$CORPUS" --out "$SUB" --producer typescript_ast
    LANES="$("$PY" - "$SUB/ring.json" <<'PY'
import json, sys
ring = json.load(open(sys.argv[1], encoding="utf-8"))
print(" ".join(f"--lane {m['slug']}_graph:static-dep" for m in ring["minted"].values()))
PY
)"
fi
CURSOR="sha256:$(sha256sum "$SUB/hono_graph/edges.json" | cut -c1-64)"   # a pinned checkout is content, never a working tree: a git cursor is read against the tenant root (graphyos #39)
eval "set -- $LANES"
"$PY" -m graphy init --tenant "$DESC" --root "$HERE" --data-home "$SUB" \
    --join-keys "$SUB/registry.json" --journal "$SUB/journal" --cursor "$CURSOR" \
    --policy refuse --adapter typescript_ast "$@"
"$PY" - "$SUB" <<'PY'
import json, sys
from pathlib import Path
from graphy.smash import _schemes
from graphy.adapters.typescript_ast import NODE_STANDARD
sub = Path(sys.argv[1])
ring = sub / "ring.json"
if ring.is_file():
    receipt = json.loads(ring.read_text(encoding="utf-8"))
    rows, standard, how = receipt["scheme_index"], receipt["standard"], "derived from ring.json by rebuild.sh"
else:                       # pulled: each shard's own edges say what it owns and reaches; the producer names the standard library
    rows, standard, how = {}, sorted(NODE_STANDARD), "derived from the pulled shards by rebuild.sh"
    for shard in sorted(sub.glob("*_graph")):
        own, dst = _schemes(json.loads((shard / "edges.json").read_text(encoding="utf-8")))
        rows[shard.name[:-len("_graph")]] = {"own": sorted(own), "out": sorted(dst - own)}
index = {"_meta": {"description": f"hono tenant scheme index — {how}", "standard": standard}, **rows}
(sub / ".federation_scheme_index.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n", encoding="utf-8")
PY
"$PY" -m graphy converge --tenant "$DESC" --tenant-id hono --resolve
"$PY" -m graphy build --tenant "$DESC" --tenant-id hono
"$PY" -m graphy check --tenant "$DESC" --tenant-id hono
"$PY" -m graphy fanout --graph-dir "$SUB/hono_graph" --out "$SUB/fanout" --partition "$HERE/partition.json"
"$PY" -m graphy fanout --verify --out "$SUB/fanout"
"$PY" -m graphy arms --tenant "$DESC" --tenant-id hono --corpus hono --partition "$HERE/partition.json" --dir "$HERE/arms" --verify
# The atlas: the pillars, the unit map and one drawing per arm, ascii and html, computed from the
# store — a build product under the substrate with a receipt.
"$PY" -m graphy draw --tenant "$DESC" --tenant-id hono --corpus hono --partition "$HERE/partition.json" --atlas "$SUB/atlas" --lr --min-weight 2
"$PY" -m graphy pillars --tenant "$DESC" --tenant-id hono --corpus hono --write "$SUB/pillars.json" > "$SUB/pillars.txt"
tail -n 2 "$SUB/pillars.txt"
echo "HONO_TENANT_OK"
