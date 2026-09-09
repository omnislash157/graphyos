# Graphy — the tenant router (graphy eats graphy)

> The arm-doc law: no numbers, no status, no history — only the tap. Every symbol named here came
> out of the walk; re-walk before you trust it. Counts live in `RECON.md`, never here.

**What this tenant is.** The engine minted by its own producer from `engine/graphy/`, its ring
followed into the interpreter's site-packages (the extras it imports: duckdb, tree-sitter,
typing_extensions), converged, built, audited, fanned out, armed and drawn by the same verbs every
other tenant runs. It exists so a change to the engine has a blast radius from the walk before a
human reads the diff: `blast_pr.py <base> <head>` maps the changed lines to the symbols the store
places there, blasts each, and prints one comment — what depends on what changed, the tests that
reach it, the arms it lands in. The PR workflow posts it.

## ⚖ THE SIX PILLARS — the engine map as a cut; the walk says one crown

| pillar | router | what |
|---|---|---|
| **PRODUCE** | [`arms/PRODUCE.md`](arms/PRODUCE.md) | the producers, the mint, the ring, the index, the farm, provisioning, the release law |
| **SEAM** | [`arms/SEAM.md`](arms/SEAM.md) | the tenant, the resolver, the store, the journal, the container, the estate |
| **DOORS** | [`arms/DOORS.md`](arms/DOORS.md) | hunt · descend · blast · walk · explain · the bridge · the MCP server |
| **CUT** | [`arms/CUT.md`](arms/CUT.md) | the fan-out, the pillars, the arms, the drawings, the showcase |
| **MEMORY** | [`arms/MEMORY.md`](arms/MEMORY.md) | the continuity lane: the tail, the reseed, lightning |
| **CLI** | [`arms/CLI.md`](arms/CLI.md) | the verbs and the shell |

**Where the hand and the walk disagree.** `graphy pillars` crowns `cli` (fan-out 106) and owns
every other unit under it, with `session_tail` + `reseed` the one floor no arm consumes. That is
true and it is what a thin CLI over a library looks like; the curated cut names the lanes a
reader lands in. `graphy pillars --against partition.json` prints every unit with its numbers.

## THE TAPS — run from `engine/`, the tenant dir is `T=tenants/graphy`

| move | the tap |
|---|---|
| rebuild the tenant | `bash $T/rebuild.sh` → `GRAPHY_TENANT_OK` (PYTHON=<abs> for another interpreter's ring) |
| the blast radius of a diff | `python3 $T/blast_pr.py <base> <head>` — the symbols the changed lines land in, each blasted, the tests that reach them, the arms; the PR workflow posts it |
| the doors over the engine | `python3 -m graphy blast open_for --tenant $T/tenant.json --tenant-id graphy` · `descend _cmd_eat …` · `explain compile_store …` — `blast` and `explain` name the archive's exchanges that mentioned the symbol, from the history shard |
| what did we say about this symbol | `python3 -m graphy history --symbol showcase._clone --tenant $T/tenant.json --tenant-id graphy` — the exchanges that mention it, their sessions oldest first, the symbols each discussed, their commits |
| weld a literal the shards' own names cannot bind | `$T/aliases.json` — an exact literal on token boundaries → one code node id, read by the rebuild into `history_graph` as `mentions` tagged `via: alias`; a target that is not a node refuses at mint, a literal the shards' own names already bind refuses as redundant |
| draw it | `python3 -m graphy draw --tenant $T/tenant.json --tenant-id graphy --corpus graphy --pillars --partition $T/partition.json --lr` — the atlas lands at `$T/substrate/atlas/` |
| the arms the walk proposes | `python3 -m graphy pillars --tenant $T/tenant.json --tenant-id graphy --corpus graphy --against $T/partition.json` |
