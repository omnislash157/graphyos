@echo off
rem PreCompact / SessionEnd: capture the session's tail and archive it (the .sh hook's twin for a host with no bash, graphyos #93).
rem   a harness:     the hook JSON arrives on stdin (session_id, transcript_path)
rem   any harness:   session_end.cmd <transcript.jsonl> <session-id>
setlocal
if "%~2"=="" goto stdin
"{{python}}" -c "import json, sys; print(json.dumps({'session_id': sys.argv[2], 'transcript_path': sys.argv[1], 'cwd': sys.argv[3]}))" "%~1" "%~2" "{{repo}}" | "{{python}}" -m graphy.reseed --project-dir "{{repo}}" capture
exit /b %errorlevel%
:stdin
"{{python}}" -m graphy.reseed --project-dir "{{repo}}" capture
exit /b %errorlevel%
