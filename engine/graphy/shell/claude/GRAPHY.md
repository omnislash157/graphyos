# graphy — this repo is a substrate

This repo was eaten by graphy: its package and every package it imports are minted into shards
under `.graphy/substrate/`, resolved through the code's own scope, compiled into one store, with
parquet beside every shard. **Prose is context, code is law.** A walk answers; a doc stores no
truth. Walk before you edit: the gate blocks an edit to a symbol the store knows until a walk from
that symbol is stored under the live generation, and prints the walk to run.

| move | the tap |
|---|---|
| does A reach B | `{{graphy}} walk --tenant {{desc}} --tenant-id {{tid}} --seed <id> --target <id>` |
| the walk the gate asks for | `{{graphy}} walk --tenant {{desc}} --tenant-id {{tid}} --seed <symbol id> --target {{root_module}}` |
| the whole ring, one SQL query | `{{graphy}} estate --tenant {{desc}} --tenant-id {{tid}} --sql "SELECT … FROM adj / nodes / walks"` |
| the stored walks; the hops the last re-eat broke | `{{graphy}} traversals --tenant {{desc}} --tenant-id {{tid}} [--replay]` |
| is it still true | `{{graphy}} check --tenant {{desc}} --tenant-id {{tid}}` |
| the repo moved — eat it again | `{{graphy}} eat --repo {{repo}} --site-packages <its venv's site-packages>` |

Node ids are literals: `{{tid}}://module/{{tid}}.sub`, `{{tid}}://class/{{tid}}.sub.Name`,
`{{tid}}://func/{{tid}}.sub.name`, `{{tid}}://method/{{tid}}.sub.Class.name`. A dependency's
ids carry its own scheme (`starlette://…`). Find one with the estate:
`--sql "SELECT id FROM nodes WHERE last = 'Name'"`.

## MEMORY — every session, dead cold

The hooks are the continuity lane: PreCompact and SessionEnd capture the session as 1:1
user/assistant exchanges with tool use stripped into `.claude/recovery/reseed_tail.md`, every
distinct tail archived in sequence under `.claude/recovery/sessions/`; SessionStart on startup,
clear or compact injects the newest bounded edge and names the file to read. A tail the parser
cannot trust is refused loud, never injected hollow. No summarizer, no embeddings — the archive is
text, and these doors read it (ripgrep makes them fast; without it they fall back to Python).

| move | the tap |
|---|---|
| where is X, anchored to its function or class | `{{python}} -m graphy.lightning "<term>" --path {{sessions}}` |
| who reads X | `{{python}} -m graphy.lightning --containers "<term>" --path {{sessions}}` |
| does A live inside B | `{{python}} -m graphy.lightning --cooccur A --with B --path {{sessions}}` |
| the pipe, for what `--path` skips by name | `rg -li '<term>' {{sessions}} \| {{python}} -m graphy.lightning '<term>' --files-from -` |
| when did we say A and B together, with the spans | `{{python}} -m graphy.lightning.bloodhound "<A>" --with "<B>" --path {{sessions}}` |
| the archive's topics · exchanges holding terms · the heat · one term across time | `{{python}} -m graphy.lightning.reseed_graph --path {{sessions}} topics \| search <terms> \| heat <terms> \| chain <term>` |
| render any transcript by hand | `{{python}} -m graphy.reseed --project-dir {{repo}} render --transcript <jsonl> [--budget-chars N]` |

`--path` points the doors at any other archive; `GRAPHY_RG` names a ripgrep that is not on PATH.

The hooks live in `.graphy/hooks/` (machine-local, ignored) and are wired in `.claude/settings.json`:
`session_start.sh` re-seeds the last session's tail, `session_end.sh` captures it, `before_edit.sh`
is the gate. Any harness that can run a shell command uses the same three scripts.
