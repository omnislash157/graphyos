#!/usr/bin/env bash
# graphy tenant — graphy eats graphy. The engine's own package minted by its own producer, its ring
# followed into the interpreter's site-packages (the extras it imports: duckdb, tree-sitter), and
# every verb run over it: converge, build, check, fan out, arms, atlas. Every path is derived from
# this file's location; nothing is ambient.
#
#   GRAPHY_CORPUS_SITE_PACKAGES=<dir>   the site-packages the ring is resolved from (default: the
#                                       interpreter's own — PYTHON=<abs>, else the repo's .venv, else python3)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/../.." && pwd)"
ROOT="$(cd "$ENGINE/.." && pwd)"
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
    if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY=python3; fi
fi
"$PY" -c "import graphy" 2>/dev/null || export PYTHONPATH="$ENGINE${PYTHONPATH:+:$PYTHONPATH}"

SUB="$HERE/substrate"
DESC="$HERE/tenant.json"
CORPUS="$ENGINE/graphy"
SP="${GRAPHY_CORPUS_SITE_PACKAGES:-$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')}"

KEEP="$HERE/.traversals.keep"
rm -rf "$KEEP"
[ -d "$SUB/traversals" ] && mv "$SUB/traversals" "$KEEP"
rm -rf "$SUB" "$DESC"
if [ -d "$KEEP" ]; then mkdir -p "$SUB" && mv "$KEEP" "$SUB/traversals"; fi

"$PY" -m graphy smash --package graphy --site-packages "$SP" --corpus "$CORPUS" --out "$SUB"
# The floor as a sibling shard: engine/tests minted alone; its imports of graphy are wormholes into
# the package, so `explain` names the tests that reach a symbol and blast_pr prints them.
"$PY" -m graphy smash --package tests --site-packages "$SP" --corpus "$ENGINE/tests" --out "$SUB/.tests" --no-ring
mv "$SUB/.tests/tests_graph" "$SUB/tests_graph" && rm -rf "$SUB/.tests"
LANES="$("$PY" - "$SUB/ring.json" <<'PY'
import json, sys
ring = json.load(open(sys.argv[1], encoding="utf-8"))
print(" ".join(f"--lane {m['slug']}_graph:static-dep" for m in ring["minted"].values()) + " --lane tests_graph:static-dep")
PY
)"
CURSOR="$("$PY" -c 'import sys; from pathlib import Path; from graphy.cartograph import repo_cursor; print(repo_cursor(Path(sys.argv[1]), exclude=(Path(sys.argv[2]),))[0])' "$ROOT" "$(dirname "$DESC")")"   # the working tree's dirt joins the cursor (graphyos #39)
eval "set -- $LANES"
"$PY" -m graphy init --tenant "$DESC" --root "$HERE" --data-home "$SUB" \
    --join-keys "$SUB/registry.json" --journal "$SUB/journal" --cursor "$CURSOR" \
    --policy refuse --adapter python_ast "$@"
"$PY" - "$SUB" <<'PY'
import json, sys
from pathlib import Path
sub = Path(sys.argv[1])
from graphy.smash import _schemes
receipt = json.loads((sub / "ring.json").read_text(encoding="utf-8"))
own, dst = _schemes(json.loads((sub / "tests_graph" / "edges.json").read_text(encoding="utf-8")))
rows = {**receipt["scheme_index"], "tests": {"own": sorted(own), "out": sorted(dst - own)}}
index = {"_meta": {"description": "graphy tenant scheme index — derived from ring.json (+ the tests shard) by rebuild.sh",
                   "standard": receipt["standard"]}, **rows}
(sub / ".federation_scheme_index.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n", encoding="utf-8")
PY
"$PY" -m graphy converge --tenant "$DESC" --tenant-id graphy --resolve
"$PY" -m graphy build --tenant "$DESC" --tenant-id graphy
"$PY" -m graphy check --tenant "$DESC" --tenant-id graphy
"$PY" -m graphy fanout --graph-dir "$SUB/graphy_graph" --out "$SUB/fanout" --partition "$HERE/partition.json"
"$PY" -m graphy fanout --verify --out "$SUB/fanout"
"$PY" -m graphy arms --tenant "$DESC" --tenant-id graphy --corpus graphy --partition "$HERE/partition.json" --dir "$HERE/arms" --verify
"$PY" -m graphy draw --tenant "$DESC" --tenant-id graphy --corpus graphy --partition "$HERE/partition.json" --atlas "$SUB/atlas" --lr --min-weight 2
"$PY" -m graphy pillars --tenant "$DESC" --tenant-id graphy --corpus graphy --write "$SUB/pillars.json" > "$SUB/pillars.txt"
tail -n 2 "$SUB/pillars.txt"
echo "GRAPHY_TENANT_OK"
