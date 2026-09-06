#!/usr/bin/env bash
# fastapi tenant — rebuild from scratch: wipe, mint (or place), init, build the store, audit.
# Idempotent. Every path is derived from this file's location; nothing is ambient.
#
# Three ways in, all explicit:
#   GRAPHY_CORPUS_SITE_PACKAGES=<dir>   mint fastapi AND its import ring from a site-packages that
#                                       holds fastapi==0.139.0; the root shard is proven record-for-record
#                                       against the vendored fixture before anything is built on it
#   GRAPHY_SHARD_INDEX=<abs dir|url>    pull prebuilt shards from a content-addressed index instead of
#                                       minting: every name in GRAPHY_PULL (space-separated; default:
#                                       every name the index catalogs), each declared as a `pulled` lane
#                                       whose command is the pull itself, so a missing shard re-pulls
#   (unset)                             place the vendored fixture shard alone (GRAPHY_FASTAPI_SHARD
#                                       points at any other already-minted shard)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-python3}"
"$PY" -c "import graphy" 2>/dev/null || export PYTHONPATH="$ENGINE${PYTHONPATH:+:$PYTHONPATH}"

SUB="$HERE/substrate"
DESC="$HERE/tenant.json"
FIXTURE="$ENGINE/tests/fixtures/fastapi_graph"
CORPUS_SP="${GRAPHY_CORPUS_SITE_PACKAGES:-}"
INDEX="${GRAPHY_SHARD_INDEX:-}"

# The traversal store survives a rebuild: walks stored under the old generation are what --replay diffs.
KEEP="$HERE/.traversals.keep"
rm -rf "$KEEP"
[ -d "$SUB/traversals" ] && mv "$SUB/traversals" "$KEEP"
rm -rf "$SUB" "$DESC"
if [ -d "$KEEP" ]; then mkdir -p "$SUB" && mv "$KEEP" "$SUB/traversals"; fi

if [ -n "$CORPUS_SP" ]; then
    "$PY" -m graphy smash --package fastapi --site-packages "$CORPUS_SP" --out "$SUB" --parity "$FIXTURE"
    LANES="$("$PY" - "$SUB/ring.json" <<'PY'
import json, sys
ring = json.load(open(sys.argv[1], encoding="utf-8"))
print(" ".join(f"--lane {m['slug']}_graph:static-dep" for m in ring["minted"].values()))
PY
)"
elif [ -n "$INDEX" ]; then
    mkdir -p "$SUB"
    LANES="$("$PY" - "$SUB" "$INDEX" "${GRAPHY_PULL:-}" <<'PY'
import json, shlex, sys
from pathlib import Path
from graphy import index as shard_index
from graphy.smash import slug_for
sub, idx, names = Path(sys.argv[1]), sys.argv[2], sys.argv[3].split()
names = names or sorted(shard_index.catalog(idx))
if not names:
    sys.exit(f"REBUILD REFUSED: the index at {idx} names no shard")
lanes = []
for name in names:
    tmp = sub / f".pull.{name}"
    m = shard_index.pull(name, idx, tmp)
    prov = json.loads((tmp / "PROVENANCE.json").read_text(encoding="utf-8"))
    slug = slug_for(prov["corpus"]["scheme"])
    tmp.rename(sub / f"{slug}_graph")
    cmd = f"python3 -m graphy pull {name} --index {shlex.quote(idx)} --out {{out}}"
    lanes.append(f"--lane={slug}_graph:pulled={cmd}")
    print(f"PULL OK: {name} -> {slug}_graph ({m['address'][:12]}…)", file=sys.stderr)
print(" ".join(shlex.quote(l) for l in lanes))
PY
)"
    [ -f "$SUB/fastapi_graph/nodes.json" ] \
        || { echo "REBUILD REFUSED: the pull brought no fastapi_graph — name fastapi==<version> in GRAPHY_PULL" >&2; exit 2; }
else
    SHARD="${GRAPHY_FASTAPI_SHARD:-$FIXTURE}"
    [ -f "$SHARD/nodes.json" ] && [ -f "$SHARD/edges.json" ] \
        || { echo "REBUILD REFUSED: no shard (nodes.json + edges.json) at $SHARD" >&2; exit 2; }
    mkdir -p "$SUB"
    cp -r "$SHARD" "$SUB/fastapi_graph"
    LANES="--lane fastapi_graph:static-dep"
fi

CURSOR="sha256:$(sha256sum "$SUB/fastapi_graph/edges.json" | cut -c1-64)"
# $LANES is a list of shell-quoted --lane flags; eval splits it into argv on purpose
eval "set -- $LANES"
"$PY" -m graphy init --tenant "$DESC" --root "$HERE" --data-home "$SUB" \
    --join-keys "$SUB/registry.json" --journal "$SUB/journal" --cursor "$CURSOR" \
    --policy refuse --adapter python_ast "$@"

# The scheme index: every shard owns its scheme and names the schemes its edges reach out to.
# Minted, it is derived from the ring receipt; pulled, from each shard's own edges; placed, the
# fixture alone.
"$PY" - "$SUB" "$INDEX" <<'PY'
import json, sys
from pathlib import Path
from graphy.smash import _schemes, stdlib_names
sub, idx = Path(sys.argv[1]), sys.argv[2]
ring = sub / "ring.json"
standard = sorted(stdlib_names())     # the Python door, named by the tenant that knows its corpus is Python
if ring.is_file():
    receipt = json.loads(ring.read_text(encoding="utf-8"))
    rows, standard = receipt["scheme_index"], receipt["standard"]
    how = "derived from ring.json by rebuild.sh"
elif idx:
    rows = {}
    for shard in sorted(sub.glob("*_graph")):
        own, dst = _schemes(json.loads((shard / "edges.json").read_text(encoding="utf-8")))
        rows[shard.name[:-len("_graph")]] = {"own": sorted(own), "out": sorted(dst - own)}
    how = f"derived from the shards pulled from {idx} by rebuild.sh"
else:
    rows = {"fastapi": {"own": ["fastapi"], "out": []}}
    how = "the placed fixture shard alone"
index = {"_meta": {"description": f"fastapi tenant scheme index — {how}", "standard": standard}, **rows}
(sub / ".federation_scheme_index.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n",
                                                   encoding="utf-8")
PY

# The seam: resolve every text label the producer left (calls · inherits · decorates) through
# its module's own scope into <shard>/wormhole_edges.json, then compile the store over both.
"$PY" -m graphy converge --tenant "$DESC" --tenant-id fastapi --resolve
"$PY" -m graphy build --tenant "$DESC" --tenant-id fastapi
"$PY" -m graphy check --tenant "$DESC" --tenant-id fastapi
"$PY" "$HERE/walk.py" compile-labels
# The fan-out: the shard cut into the tenant's pillars by partition.json, a build product under
# the substrate, its receipt pinning the partition's sha; --verify proves it before the token.
"$PY" -m graphy fanout --graph-dir "$SUB/fastapi_graph" --out "$SUB/fanout" --partition "$HERE/partition.json"
"$PY" -m graphy fanout --verify --out "$SUB/fanout"
# The arms: the walk-derived half of each arm file is a marked generated region — the inventory by
# module, the inherits joins out, the re-walk — rendered from the store by `graphy arms`. The rebuild
# verifies it and refuses on drift: the walk moved, or a hand edited inside the markers.
# With the fixture placed alone there is no ring: every inherits edge into Starlette or pydantic is a
# literal with no node behind it, the store drops it, and the joins out are empty — so the arms are
# verified against the ring-minted store only, and the placement says so.
if [ -f "$SUB/ring.json" ] || [ -n "$INDEX" ]; then
    "$PY" -m graphy arms --tenant "$DESC" --tenant-id fastapi --corpus fastapi --partition "$HERE/partition.json" --dir "$HERE/arms" --verify
else
    echo "ARMS SKIPPED: the fixture placed alone carries no ring, so the joins out are unresolved — verify with GRAPHY_CORPUS_SITE_PACKAGES or GRAPHY_SHARD_INDEX set"
fi
# The proposal: the arms the walk deduces from the module graph, written as a partition beside the
# curated one and fanned out by it — a build product the operator diffs against partition.json with
# `graphy pillars --against` (exit 1 names every unit cut differently, with its evidence).
"$PY" -m graphy pillars --tenant "$DESC" --tenant-id fastapi --corpus fastapi --write "$SUB/pillars.json" > "$SUB/pillars.txt"
tail -n 2 "$SUB/pillars.txt"
"$PY" -m graphy fanout --graph-dir "$SUB/fastapi_graph" --out "$SUB/fanout.proposed" --partition "$SUB/pillars.json"
"$PY" -m graphy fanout --verify --out "$SUB/fanout.proposed"
echo "FASTAPI_TENANT_OK"
