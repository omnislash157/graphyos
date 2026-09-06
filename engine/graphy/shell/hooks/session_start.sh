#!/usr/bin/env bash
# SessionStart: print the last session's tail as context.
#   Claude Code:   the hook JSON arrives on stdin
#   any harness:   session_start.sh now   (no stdin; injects the newest tail on disk)
if [ $# -ge 1 ] || [ -t 0 ]; then
    exec "{{python}}" -m graphy.reseed --project-dir "{{repo}}" inject < /dev/null
fi
exec "{{python}}" -m graphy.reseed --project-dir "{{repo}}" inject
