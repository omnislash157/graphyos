#!/usr/bin/env bash
# fastapi tenant — the MCP server over its compiled store, on stdio. Every path is derived from
# this file's location; the client just runs it. Rebuild first: bash engine/tenants/fastapi/rebuild.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/../.." && pwd)"
ROOT="$(cd "$ENGINE/.." && pwd)"
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
    if [ -x "$ROOT/.venv/bin/python3" ]; then PY="$ROOT/.venv/bin/python3"; else PY=python3; fi
fi
"$PY" -c "import graphy" 2>/dev/null || export PYTHONPATH="$ENGINE${PYTHONPATH:+:$PYTHONPATH}"
[ -f "$HERE/tenant.json" ] || { echo "MCP REFUSED: no tenant at $HERE/tenant.json — run bash $HERE/rebuild.sh first" >&2; exit 2; }
exec "$PY" -m graphy mcp --tenant "$HERE/tenant.json" --tenant-id fastapi "$@"
