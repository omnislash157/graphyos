@echo off
rem PreToolUse (Edit|Write|MultiEdit): the walk-before-edit gate (the .sh hook's twin for a host with no bash, graphyos #93).
rem Exit 2 blocks, the walk to run is on stderr; exit 0 passes.
rem   a harness:     the hook JSON arrives on stdin (tool_name, tool_input.file_path, old_string / content)
rem   any harness:   before_edit.cmd <file> < <the text being replaced>
setlocal
if not defined CLAUDE_PROJECT_DIR set "CLAUDE_PROJECT_DIR={{repo}}"
if "%~1"=="" goto stdin
set "GATE_FILE=%~1"
"{{python}}" -c "import json, os, sys; print(json.dumps({'tool_name': 'Edit', 'tool_input': {'file_path': os.environ['GATE_FILE'], 'old_string': sys.stdin.read()}}))" | "{{python}}" -m graphy.shell.gate
exit /b %errorlevel%
:stdin
"{{python}}" -m graphy.shell.gate
exit /b %errorlevel%
