# shell install writes hooks a harness runs on the host it was written for
issue: graphyos #93
host: linux, windows
scars: S1 S8 S2 S3 S7

## Contract
- C1 every file `shell install` writes carries the line ending it means: LF, and CRLF in a `.cmd`
- C2 on Windows each `.sh` hook has a `.cmd` twin, and the Codex and Cursor wiring runs the twin
- C3 on Windows with no bash from Git for Windows, the Claude wiring refuses by name before a byte is written
- C4 a wiring command is matched whole and its path quoted, so a repo under `josh.shaw/First Last` runs
- C5 an install over the 0.2.4 wiring leaves one entry per event, and no `.sh` in the Codex or Cursor wiring on Windows
- C6 the end hook captures the tail and the start hook injects it, through each harness's shell

## Scope
- IN: engine/graphy/shell/install.py
- IN: engine/graphy/shell/hooks/
- IN: engine/graphy/shell/cursor/hooks.json
- IN: engine/tests/test_shell.py
- OUT: engine/graphy/reseed.py

## Hazards
- W1 C1 P1,P4
- W3 C4 P2,P5
- W4 C6 P3
- W7 C2,C6 P4
- E1 C5 P5
- E2 C5 P5
- G1 C4 P2

## Probes
```bash
# P1 C1 W1
rm -rf /tmp/p93 && git clone -q https://github.com/pallets/itsdangerous /tmp/p93/repo
.venv/bin/graphy eat --repo /tmp/p93/repo --package itsdangerous --site-packages /tmp/p93/repo/src
.venv/bin/graphy shell install --repo /tmp/p93/repo --harness claude --harness codex --harness cursor
.venv/bin/python -c "import pathlib,sys; fs=list(pathlib.Path('/tmp/p93/repo/.graphy/hooks').glob('*.sh')); sys.exit(not fs or any(b'\r' in f.read_bytes() for f in fs))"
cd engine && ../.venv/bin/python -m pytest -q -o addopts="" tests/test_shell.py -k every_byte_the_install_writes
# P2 C4 G1 W3
.venv/bin/python -c "from graphy.shell import install as i; assert i._host_command('\"/r/josh.shaw/First Last/.graphy/hooks/session_end.sh\"', 'nt') == '\"/r/josh.shaw/First Last/.graphy/hooks/session_end.cmd\"'"
cd engine && ../.venv/bin/python -m pytest -q -o addopts="" "tests/test_shell.py::test_GREEN_the_wiring_captures_and_injects_on_the_host_it_was_written_for[cursor-josh.shaw/First Last]"
# P3 C6 W4
W=/tmp/p93/repo/.claude/settings.json; T=engine/tests/fixtures/transcript/session.jsonl
printf '{"session_id":"fx-session-0001","transcript_path":"%s","cwd":"/tmp/p93/repo"}' "$PWD/$T" | CLAUDE_PROJECT_DIR=/tmp/p93/repo sh -c "$(.venv/bin/python -c "import json,sys; print(json.load(open(sys.argv[1]))['hooks']['SessionEnd'][0]['hooks'][0]['command'])" "$W")"
CLAUDE_PROJECT_DIR=/tmp/p93/repo sh -c "$(.venv/bin/python -c "import json,sys; print(json.load(open(sys.argv[1]))['hooks']['SessionStart'][0]['hooks'][0]['command'])" "$W")" < /dev/null | grep -q fx-session-0001
# P4 C1 C2 C6 W7 W1
gh workflow run ci.yml --repo omnislash157/graphy --ref win-93
gh run watch "$(gh run list --repo omnislash157/graphy --branch win-93 --limit 1 --json databaseId --jq '.[0].databaseId')" --repo omnislash157/graphy --exit-status
# P5 C5 E1 E2
git fetch -q https://github.com/omnislash157/graphyos refs/tags/v0.2.4:refs/tags/v0.2.4
git show v0.2.4:engine/graphy/shell/cursor/hooks.json | sed 's#{{repo}}#/tmp/p93/repo#g' > /tmp/p93/repo/.cursor/hooks.json
for n in 1 2 3; do .venv/bin/graphy shell install --repo /tmp/p93/repo --harness cursor; done
.venv/bin/python -c "import json; h=json.load(open('/tmp/p93/repo/.cursor/hooks.json'))['hooks']; assert all(len(v) == 1 for v in h.values())"
cd engine && ../.venv/bin/python -m pytest -q -o addopts="" tests/test_shell.py -k released_wiring
# P6 C3
cd engine && ../.venv/bin/python -m pytest -q -o addopts="" tests/test_shell.py -k "no_git_bash_refuses"
```

## Production
```bash
# host: linux a clone of a real repo, a Claude Code session in it
.venv/bin/graphy shell install --repo /tmp/p93/repo --harness claude
rm -rf /tmp/p93/repo/.claude/recovery && cd /tmp/p93/repo && claude -p "reply ok" && claude -p "reply ok"
grep -q "inject ok source=startup" /tmp/p93/repo/.claude/recovery/reseed_diag.log
# host: windows the production Windows seat, a Claude Code session and a Cursor session
graphy shell install --repo "$TENANT_REPO" --harness claude --harness cursor
test -s "$TENANT_REPO/.claude/recovery/reseed_tail.md"
```
