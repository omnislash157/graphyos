#!/usr/bin/env bash
# PreToolUse (Edit|Write|MultiEdit): the walk-before-edit gate. Exit 2 blocks, the walk to run is on
# stderr; exit 0 passes.
#   Claude Code:   the hook JSON arrives on stdin (tool_name, tool_input.file_path, old_string / content)
#   any harness:   before_edit.sh <file> < <the text being replaced>
export CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-{{repo}}}"
if [ $# -ge 1 ]; then
    GATE_FILE="$1" "{{python}}" -c 'import json, os, sys; print(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": os.environ["GATE_FILE"], "old_string": sys.stdin.read()}}))' \
        | "{{python}}" -m graphy.shell.gate
    exit $?
fi
exec "{{python}}" -m graphy.shell.gate
