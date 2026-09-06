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

The hooks live in `.graphy/hooks/` (machine-local, ignored) and are wired in `.claude/settings.json`:
`session_start.sh` re-seeds the last session's tail, `session_end.sh` captures it, `before_edit.sh`
is the gate. Any harness that can run a shell command uses the same three scripts.
