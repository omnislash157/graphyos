@echo off
rem SessionStart: print the last session's tail as context (the .sh hook's twin for a host with no bash, graphyos #93).
rem   a harness:     the hook JSON arrives on stdin; the text on stdout is the context
rem   Cursor:        session_start.cmd --json  gives {"additional_context": ...}, the shape a sessionStart hook returns
rem   any harness:   session_start.cmd now   (stdin not read; injects the newest tail on disk)
setlocal
set "GRAPHY_JSON="
if /i "%~1"=="--json" set "GRAPHY_JSON=--json"
if /i "%~1"=="--json" shift
if not "%~1"=="" goto now
"{{python}}" -m graphy.reseed --project-dir "{{repo}}" inject %GRAPHY_JSON%
exit /b %errorlevel%
:now
"{{python}}" -m graphy.reseed --project-dir "{{repo}}" inject %GRAPHY_JSON% < nul
exit /b %errorlevel%
