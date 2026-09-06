#!/usr/bin/env bash
# PreCompact / SessionEnd: capture the session's tail and archive it.
#   Claude Code:   the hook JSON arrives on stdin (session_id, transcript_path)
#   any harness:   session_end.sh <transcript.jsonl> <session-id>
if [ $# -ge 2 ]; then
    printf '{"session_id": "%s", "transcript_path": "%s", "cwd": "%s"}' "$2" "$1" "{{repo}}" \
        | exec "{{python}}" -m graphy.reseed --project-dir "{{repo}}" capture
fi
exec "{{python}}" -m graphy.reseed --project-dir "{{repo}}" capture
