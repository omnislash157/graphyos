#!/usr/bin/env bash
# sqlalchemy tenant — rebuild from scratch: wipe, mint the package and its ring, init, converge,
# build the store, audit, fan out. Idempotent. Every path is derived from this file's location.
#
# The corpus, explicit or provisioned:
#   GRAPHY_CORPUS_SITE_PACKAGES=<dir>   mint sqlalchemy AND its import ring from a site-packages
#                                       that holds it (any release — the shard's PROVENANCE says which)
#   (unset)                             provision a venv under staging/corpora/sqlalchemy/venv pinned
#                                       to SQLALCHEMY_RELEASE (reused when it already holds that
#                                       release), and mint from its site-packages
#
# There is no vendored fixture for this tenant, so there is no parity step: the second tenant is
# proof that graphy eats a package it has never seen, not a golden the engine is held to.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-python3}"
"$PY" -c "import graphy" 2>/dev/null || export PYTHONPATH="$ENGINE${PYTHONPATH:+:$PYTHONPATH}"

SUB="$HERE/substrate"
DESC="$HERE/tenant.json"
RELEASE="${SQLALCHEMY_RELEASE:-2.0.52}"
CORPUS_SP="${GRAPHY_CORPUS_SITE_PACKAGES:-}"

if [ -z "$CORPUS_SP" ] && [ -z "${GRAPHY_SHARD_INDEX:-}" ]; then
    VENV="$ENGINE/../staging/corpora/sqlalchemy/venv"
    have="$("$VENV/bin/python" -c 'import sqlalchemy; print(sqlalchemy.__version__)' 2>/dev/null || true)"
    if [ "$have" != "$RELEASE" ]; then
        rm -rf "$VENV"
        "$PY" -m venv "$VENV"
        "$VENV/bin/pip" install --quiet --disable-pip-version-check "sqlalchemy==$RELEASE"
        echo "VENV: sqlalchemy==$RELEASE provisioned at $VENV" >&2
    else
        echo "VENV: sqlalchemy==$RELEASE already at $VENV" >&2
    fi
    CORPUS_SP="$(ls -d "$VENV"/lib/python*/site-packages | head -n 1)"
fi
[ -n "${GRAPHY_SHARD_INDEX:-}" ] || [ -d "$CORPUS_SP/sqlalchemy" ] \
    || { echo "REBUILD REFUSED: no sqlalchemy package under $CORPUS_SP" >&2; exit 2; }

# The traversal store survives a rebuild: walks stored under the old generation are what --replay diffs.
KEEP="$HERE/.traversals.keep"
rm -rf "$KEEP"
[ -d "$SUB/traversals" ] && mv "$SUB/traversals" "$KEEP"
rm -rf "$SUB" "$DESC"
if [ -d "$KEEP" ]; then mkdir -p "$SUB" && mv "$KEEP" "$SUB/traversals"; fi

INDEX="${GRAPHY_SHARD_INDEX:-}"
if [ -n "$INDEX" ]; then
    # From an index instead of a mint: every name in GRAPHY_PULL (space-separated) pulled and declared
    # as a `pulled` lane whose command is the pull itself. The roster names one release per scheme.
    mkdir -p "$SUB"
    LANES="$("$PY" - "$SUB" "$INDEX" "${GRAPHY_PULL:-}" <<'PY'
import json, shlex, sys
from pathlib import Path
from graphy import index as shard_index
from graphy.smash import slug_for
sub, idx, names = Path(sys.argv[1]), sys.argv[2], sys.argv[3].split()
if not names:
    sys.exit("REBUILD REFUSED: GRAPHY_PULL must name the shards to pull (e.g. 'sqlalchemy==2.0.52 typing_extensions==4.16.0 greenlet==3.5.5')")
lanes = []
for name in names:
    tmp = sub / f".pull.{name}"
    m = shard_index.pull(name, idx, tmp)
    prov = json.loads((tmp / "PROVENANCE.json").read_text(encoding="utf-8"))
    slug = slug_for(prov["corpus"]["scheme"])
    tmp.rename(sub / f"{slug}_graph")
    lanes.append(f"--lane={slug}_graph:pulled=" + f"python3 -m graphy pull {name} --index {shlex.quote(idx)} --out {{out}}")
    print(f"PULL OK: {name} -> {slug}_graph ({m['address'][:12]}…)", file=sys.stderr)
print(" ".join(shlex.quote(l) for l in lanes))
PY
)"
    [ -f "$SUB/sqlalchemy_graph/nodes.json" ] || { echo "REBUILD REFUSED: the pull brought no sqlalchemy_graph" >&2; exit 2; }
else
    "$PY" -m graphy smash --package sqlalchemy --site-packages "$CORPUS_SP" --out "$SUB"
    LANES="$("$PY" - "$SUB/ring.json" <<'PY'
import json, sys
ring = json.load(open(sys.argv[1], encoding="utf-8"))
print(" ".join(f"--lane {m['slug']}_graph:static-dep" for m in ring["minted"].values()))
PY
)"
fi

CURSOR="sha256:$(sha256sum "$SUB/sqlalchemy_graph/edges.json" | cut -c1-64)"
# $LANES is a list of --lane flags; eval splits it into argv on purpose
eval "set -- $LANES"
"$PY" -m graphy init --tenant "$DESC" --root "$HERE" --data-home "$SUB" \
    --join-keys "$SUB/registry.json" --journal "$SUB/journal" --cursor "$CURSOR" \
    --policy refuse --adapter python_ast "$@"

# The scheme index: every shard owns its scheme and names the schemes its edges reach out to,
# derived from the ring receipt.
"$PY" - "$SUB" <<'PY'
import json, sys
from pathlib import Path
from graphy.smash import _schemes, stdlib_names
sub = Path(sys.argv[1])
ring = sub / "ring.json"
if ring.is_file():
    receipt = json.loads(ring.read_text(encoding="utf-8"))
    rows, standard, how = receipt["scheme_index"], receipt["standard"], "derived from ring.json by rebuild.sh"
else:                       # pulled: each shard's own edges say what it owns and reaches; the Python door names the standard library
    rows, standard, how = {}, sorted(stdlib_names()), "derived from the pulled shards by rebuild.sh"
    for shard in sorted(sub.glob("*_graph")):
        own, dst = _schemes(json.loads((shard / "edges.json").read_text(encoding="utf-8")))
        rows[shard.name[:-len("_graph")]] = {"own": sorted(own), "out": sorted(dst - own)}
index = {"_meta": {"description": f"sqlalchemy tenant scheme index — {how}", "standard": standard}, **rows}
(sub / ".federation_scheme_index.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n",
                                                   encoding="utf-8")
PY

"$PY" -m graphy converge --tenant "$DESC" --tenant-id sqlalchemy --resolve
"$PY" -m graphy build --tenant "$DESC" --tenant-id sqlalchemy
"$PY" -m graphy check --tenant "$DESC" --tenant-id sqlalchemy
# The fan-out: the shard cut into the tenant's pillars by partition.json, a build product under the
# substrate; --verify proves it. The proposal the walk itself makes lands beside it.
"$PY" -m graphy fanout --graph-dir "$SUB/sqlalchemy_graph" --out "$SUB/fanout" --partition "$HERE/partition.json"
"$PY" -m graphy fanout --verify --out "$SUB/fanout"
# The arms: the generated region in each arm file, verified against the store; drift refuses.
"$PY" -m graphy arms --tenant "$DESC" --tenant-id sqlalchemy --corpus sqlalchemy --partition "$HERE/partition.json" --dir "$HERE/arms" --verify
# The atlas: the pillars, the unit map and one drawing per arm, ascii and html, computed from the
# store — a build product under the substrate with a receipt.
"$PY" -m graphy draw --tenant "$DESC" --tenant-id sqlalchemy --corpus sqlalchemy --partition "$HERE/partition.json" --atlas "$SUB/atlas" --lr --min-weight 2
"$PY" -m graphy pillars --tenant "$DESC" --tenant-id sqlalchemy --corpus sqlalchemy --write "$SUB/pillars.json" > "$SUB/pillars.txt"
tail -n 2 "$SUB/pillars.txt"
echo "SQLALCHEMY_TENANT_OK"
