#!/usr/bin/env bash
# SessionStart: print the last session's tail as context.
#   Claude Code / Codex:  the hook JSON arrives on stdin; the text on stdout is the context
#   Cursor:               session_start.sh --json  → {"additional_context": …}, the shape a sessionStart hook returns
#   any harness:          session_start.sh now   (no stdin; injects the newest tail on disk)
JSON=""
if [ "${1:-}" = "--json" ]; then JSON="--json"; shift; fi
if [ $# -ge 1 ] || [ -t 0 ]; then
    exec "{{python}}" -m graphy.reseed --project-dir "{{repo}}" inject $JSON < /dev/null
fi
exec "{{python}}" -m graphy.reseed --project-dir "{{repo}}" inject $JSON
