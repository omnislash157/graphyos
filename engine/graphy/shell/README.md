# The shell — bolt graphy onto your repo

Three hooks and one gate. Stdlib Python and bash; the contract is exit codes and stdout. Claude
Code is the reference harness; any agent that can run a shell command and read a file uses the
same entry points. Every path is declared at install time, never guessed.

## Wire it into a repo, from its root

```bash
python3 -m venv .graphy/venv                                       # 1. one venv: the repo's deps and graphy
.graphy/venv/bin/pip install -e . 'graphyos[estate]'               # 2. (until PyPI: pip install -e /path/to/graphy/engine[estate])
SP="$(.graphy/venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
.graphy/venv/bin/graphy eat --repo "$PWD" --site-packages "$SP"    # 3. mint, resolve, build, container, audit
.graphy/venv/bin/graphy shell install --repo "$PWD"                # 4. hooks + settings.json + GRAPHY.md
echo 'Read GRAPHY.md first.' >> CLAUDE.md                          # 5. route the agent (Claude Code); any harness: point it at GRAPHY.md
```

`eat` writes `.graphy/.gitignore` as `*`, so the substrate, the store, the venv and the hooks stay
machine-local. `.claude/settings.json` and `GRAPHY.md` are yours to track: the settings name only
`$CLAUDE_PROJECT_DIR`, the router names the interpreter that installed it.

## What fires

| event | script | what it does |
|---|---|---|
| SessionStart (startup, clear, compact) | `.graphy/hooks/session_start.sh` | prints the last session's tail as context and names the file holding the whole record |
| PreCompact, SessionEnd | `.graphy/hooks/session_end.sh` | captures the session as 1:1 user/assistant exchanges under `.claude/recovery/`, archived in sequence |
| PreToolUse on Edit, Write, MultiEdit | `.graphy/hooks/before_edit.sh` | the gate: an edit to a symbol the store knows, with no walk from it stored under the live generation, exits 2 with the walk to run |

The gate opens (exit 0) when the repo is not eaten, the file is not in the store, or duckdb is
absent — it confines an agent to a substrate, never to nothing.

## Prove it by hand, any harness

```bash
printf 'def get_request_handler(' | .graphy/hooks/before_edit.sh fastapi/routing.py ; echo "exit $?"
#   GATE BLOCKED: fastapi/routing.py edits 1 symbol(s) the store knows with no walk cited … exit 2
#     <python> -m graphy walk --tenant … --seed fastapi://func/fastapi.routing.get_request_handler --target fastapi://module/fastapi
<that walk>                                                       # WALK PATH … TRAVERSAL: … stored=…
printf 'def get_request_handler(' | .graphy/hooks/before_edit.sh fastapi/routing.py ; echo "exit $?"   # exit 0
.graphy/hooks/session_end.sh <transcript.jsonl> <session-id>     # capture from any harness that keeps a transcript
.graphy/hooks/session_start.sh                                    # the re-seed, to stdout
```

Claude Code sends each hook its JSON on stdin; the scripts take that as-is. The two-argument
forms build the same JSON for a harness that has none.
