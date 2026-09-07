# graphy — the constitution

You are a maximum truth-seeking agent. **Prose is context, code is law.** A doc stores no truth,
only how to walk it fresh; a count written in a doc is a lie waiting to happen. This file routes.
`RECON.md` measures. The walk answers.

## ⚖ THE FOUR PILLARS

```text
json : JSON is the cheapest machine currency
keys : we own the join keys — one central registry
ast  : AST is hierarchy, not magic — anything with rules becomes AST
lens : the whole world is traversable through our lens
```

## ⚖ THE LAWS — never relitigate

- **A walk is a query, never a load.** If a hop parses a file, it is not a traversal. The compiled
  store is the reader; the shard JSON is the input it was built from.
- **No ambient fallback. An absent tenant refuses.** Root, data home, join keys, journal — every one
  is a declared field on the descriptor, absolute, and an absent one is an error, never a guess.
  Two tenants run in one process without either reading the other's data.
- **No model ever decides an edge.** Every edge is structural (AST), a wormhole (the same literal is
  a node id in two or more graphs — free by construction), or an admitted weld (an exact,
  byte-identical literal carried by two or more rostered corpora, through the gate). A text label
  becomes an edge only through the scope that binds it — the module's own definitions and
  `imports` edges, `self`, `super` — never through a name match. Similarity parks forever and
  never graduates.
- **A node id is a name, never a version. The roster is the resolution.** `<scheme>://<node_type>/<dotted>`
  carries no release, which is what makes a wormhole free and what makes two releases of one package
  spell the same ids. A tenant names exactly one release per scheme; the shard's `PROVENANCE.json` is
  the only place a version lives; two releases of one scheme in a roster, or across a bridge's join,
  are a refusal at the seam (`build` · `check` · `bridge`) — never a guess, never a merge, never a
  version-qualified id.
- **The hops do not want agents.** One process holds the estate and expands a frontier per level.
  Spend agents on judgment, never on traversal.
- **One copy.** `engine/` is the only place engine work lands. Any other copy is a stale twin:
  read it for history, never edit it, never merge from it. Multiple live copies cost this project
  three weeks once (`RECON.md` §4).
- **A language is a producer, a resolver and a locator — never a consumer.** The nine words are
  the overlay; a new language maps onto them (tree-sitter parses, the producer maps) and nothing
  downstream of the IR learns its name. A producer says a node's `module` and `role` and names its
  ecosystem's standard library; the resolver's scope rules are per language; the ring's locator is
  per ecosystem. `pillars`, `arms`, the doors, the store, the walk and the bridge read only the vocabulary.
- **Arms are clusters, not inventions.** An arm is a pillar the walk already found. A new arm never
  spawns a subsystem; a symbol no arm routes to means the fan-out is stale — re-walk and fold it in.
- **Arm docs carry no numbers, no status, no history — only the tap.** Numbers live in `RECON.md`,
  each with the command that re-derives it.
- **Nothing private travels.** The public repo is `omnislash157/graphyos`, cut from this one (`RECON.md` §32, §39); this one is the private archive. Tenant material built from a private codebase,
  schema or data never reaches it; the gate's hashed scrub over `engine/` and every tracked file
  outside `staging/` is the tripwire, and `staging/` does not make the public cut (`RECON.md` §32).

## THE FOLDER

```text
CLAUDE.md             this file — the router
README.md             the public face: install, eat a repo, ask it things — every line run on this box
RECON.md              the cold-start record: measured, dated, every number with its re-derive command
standalone_check.sh   the departure gate. Run it after EVERY change to engine/. → GRAPHY_STANDALONE_OK
scrub.py              the prose scrub that never names what it scrubs: tokens hashed against .private_markers.sha256; --tree engine · --tracked (everything outside staging/)
census.sh             where the private language sits, per tracked directory → CENSUS OK is the public cut's tripwire
burden.py             the burden invariants (burden.json): zero runtime dependencies, the extras by name, the wheel under its cap, every host and every subprocess program on the list, every tracked engine doc declared or an arm region, the scrub — the gate refuses growth by name
workflows.py          every file under .github/workflows/ parsed (a stdlib subset parser, strict where GitHub is) and shaped — name · on · jobs, every step uses or runs; a file that would run zero jobs is refused in the gate with its line, before a push finds out
measure.py            the receipt: every RECON number re-derived into recon.json by `run` (--quick for CI); every lane's hottest functions and peak RSS from a second run under GRAPHY_PROFILE_DIR, and `pass.engine_hot_lanes` — the optimization pass ends when it reads 0; `diff OLD NEW` names every number that moved and exits 1 on a regression — the improvement gate's before and after
release.sh            the release made mechanical: wheel + sdist into dist/, twine check, CHANGELOG.md derived from RECON's section titles (--check in the gate); a `v<version>` tag on the public repo publishes to PyPI by trusted publishing (release.yml), no token
CHANGELOG.md          derived from RECON.md by release.sh — a build product the gate verifies, the one generated doc in git besides the arm regions
.private_markers.sha256  the hashes of the words that must not travel (the words live in no tracked file)
.mcp.json             Claude Code's pointer at the FastAPI tenant's MCP server (engine/tenants/fastapi/mcp.sh)
quickstart.sh         the production proof: clone a repo, eat it, query it, walk it → GRAPHY_QUICKSTART_OK
.github/workflows/    CI: the floor on 3.10 and 3.12, the gate, the census and the quick receipt on every push; on every PR the blast radius from the walk and the gate (burden + the receipt diffed against the base on the same runner); an opened issue naming a repo url gets its showcase posted back
.venv/                gitignored — the project's own interpreter: graphyos[estate] and nothing else
engine/               THE PRODUCT. pip-installable (`graphyos`), imports and runs as `graphy`, zero host reach
  graphy/             the package — see the map below
  tenants/            each compiled codebase is a tenant: a descriptor, a substrate, a fan-out — fastapi, sqlalchemy, hono, express, graphy
  tests/              the floor; tests/fixtures/fastapi_graph is the minted FastAPI shard (PROVENANCE.json)
staging/docs/         doctrine and prior audits — development input, never released
staging/tools/        the untriaged host tool folder — the census picks what travels
staging/skills/       the fan-out manifest
staging/containers/   gitignored — the compiled graph packages (adjacency.parquet beside every graph)
staging/brains/       gitignored — the cochange meshes
staging/corpora/      gitignored — the pinned venvs and checkouts the minting lane reads
```

## THE ENGINE MAP — `engine/graphy/`

```text
tenant.py               the Tenant descriptor: eight required fields, absolute paths, refuse|warn
ir.py                   the Graph IR — typed node/edge/provenance/evidence records; validate_graph
native_json_graph_ir.py load_graph_ir · validate_shard — a shard is nodes.json + edges.json (+ wormhole_edges.json beside them)
adapters/               producers, each with its own vocabulary: python_ast · typescript_ast (TypeScript and JavaScript, tree-sitter, `graphyos[typescript]`) · outline · native JSON — a producer says a node's `module` and `role`, and its ring receipt names the ecosystem's `standard` schemes; no consumer reads a file path or the running interpreter
smash.py                the minting lane: mint a package into a shard, follow its import ring, parity against a golden
index.py                the shard index: push · pull content-addressed shards, every byte verified against the PROVENANCE; a directory or an http base
converge.py             the seam: wormholes per shard pair; --resolve binds text labels through scope into wormhole_edges.json
container.py            adjacency.parquet + nodes.parquet + a receipt beside every shard, one duckdb connection per batch; a receipt may say pending (eat defers the ring) and estate() — one view over all of them — emits it on the first ask (duckdb, optional)
traversal.py            the traversal store: every walk lands as rows under <data_home>/traversals/<generation>/; walks compose (store · splice) and diff (replay)
shell/                  what bolts graphy onto a repo: gate.py (walk-before-edit, PreToolUse) · install.py · claude/ (settings.json, GRAPHY.md) · hooks/*.sh · README.md
federated_store.py      compile_store → the sqlite store; open_for · path_to · spread — the reader
cross_substrate.py      load_set · derive_roster · query_set · explanations — walk across substrates
bridge.py               open_sides · verify_joins · cross — two tenants in one process, each reading only its own data_home; the walk crosses only on a declared join scheme
query.py                activate · rank — spreading activation, pure; the `graphy.query` CLI
journal.py              born/died per graph; append_page · observe_publish · steward
augment_registry.py     a dirless augment self-registers; register · verify_registration
mesh_federation_gate.py roster · census · classify — membership is scanner-derived
cartograph.py           resolve_graph · freshness against the repo cursor · the build lane runner
fanout.py               compile_fanout · verify_fanout — TOC + sections + a sha receipt; the cut is a dotted depth or a partition file, and the receipt pins it
pillars.py              module_graph · propose · diff — a corpus's arms deduced from its module graph: crowns by fan-out, the floor by fan-in, every ruling with its evidence; the proposal is a partition file
arms.py                 render_all · generate · verify — the walk-derived half of an arm file as a marked generated region (inventory by module · inherits joins out · re-walk), stamped with the store generation; verify names drift
release.py              release_of · roster_releases · collisions — the version-identity law at the seam: one release per scheme in a roster (build · check refuse two), each side's release in the bridge's join receipt (skew refuses unless carried)
farm.py                 top_packages · select_release · farm_one · farm — many packages into one index: a venv per package (--no-deps; the ring is the index), every importable name minted and pushed by `<dist>==<version>[@import]`, resumable by the catalog, every refusal with its reason
index_estate.py         emit_index · verify_index_estate · estate_index — every named shard in an index as one duckdb view (adj · nodes with module · role · version), materialized beside the index with a receipt pinning the catalog; STALE when the catalog moves
session_tail.py         a transcript → its semantic tail: extract_turns · pair_turns · render_full — pure
reseed.py               the continuity hooks: capture · inject · render — fail-open
refresh.py              the refresh lane: PyPI (or --release) against the shard's PROVENANCE; a sibling substrate pinned to the newer release, minted · converged · built · checked beside the current one; born/died per shard stamped in the sibling's journal — never in place
lightning/              rg discovers, the AST walk-out anchors: the doors · bloodhound · reseed_graph
draw.py                 units · pillars · arm · neighbourhood · atlas — the codebase drawn from the store, never a shard: a query, laid out by sugiyama, ASCII for the terminal and a checked HTML+SVG page for a human
showcase.py             compose · showcase — one page of a stranger's codebase: clone when a url, eat, propose the pillars, draw, write index.html + showcase.txt (the MCP block, three questions, how to add a model), checked
provision.py            the repo's own dependencies provisioned by eat: a venv and pip install, or npm; a repo that will not install is minted alone and the reason named
sugiyama.py             the layered layout (cycle removal · layering · crossing-min · coordinates) on a wcwidth canvas; emit_html the two-theme self-contained page; check_artifact the done-token
inventory.py · parity.py · _shared.py
cli.py                  graphy eat | init | smash | push | pull | index | converge | build | container | estate | walk | bridge | arms | farm | draw | showcase | descend | blast | explain | pillars | refresh | mcp | traversals | shell | check | fanout — exit 0 healthy · 1 audit verdict · 2 never ran
```

## THE TAPS — from `engine/`

| move | the tap |
|---|---|
| prove the product stands alone | `bash ../standalone_check.sh` → `GRAPHY_STANDALONE_OK` |
| prove it works in production | `bash ../quickstart.sh <git-url-or-path> [package]` → `GRAPHY_QUICKSTART_OK` — the done token that matters |
| the floor | `python3 -m pytest -q` |
| the showcase page: one command, one page of the codebase — the drawing, the pillars, the ring, the MCP block, three questions | `python3 -m graphy showcase <git url \| path> [--out DIR]` → `SHOWCASE OK` · `index.html` checked + `showcase.txt` |
| eat a repo — the bolt-on in one verb | `../.venv/bin/graphy eat --repo <abs> --site-packages <its venv's site-packages \| its node_modules> [--package <name>] [--producer typescript_ast]` → `<repo>/.graphy/` — a repo with a `package.json` and no importable Python package is eaten as TypeScript |
| scaffold a tenant | `python3 -m graphy init --tenant <descriptor> --root <abs> --data-home <abs> --join-keys <path> --journal <path> --cursor <str> --policy refuse --lane <slug>_graph:<kind>` |
| when the package moves upstream: re-mint the ring at the newest release into a sibling substrate, prove it, and read what was born and died per shard | `python3 -m graphy refresh --tenant <descriptor> --tenant-id <name> --package <name> [--check \| --release <v> \| --site-packages <abs>] [--fixture <golden shard>] [--force]` → `substrate.<release>/` + `tenant.<release>.json` beside the current, `refresh.json` the receipt; exit 0 current or proven · 1 the sibling's check is red · 2 refused |
| mint a package and its import ring into shards | `python3 -m graphy smash --package <name> --site-packages <abs> --out <data_home> [--corpus <abs>] [--parity <golden shard>]` → `ring.json` |
| mint a TypeScript package and its ring from node_modules | the same verb with `--producer typescript_ast --corpus <src dir>` — a package that ships only `dist/` is named unresolved, never parsed |
| the farm: the top N PyPI or npm packages (or a file of specs) minted into one index in parallel, resumably | `python3 -m graphy farm --top N \| --packages <file> --index <abs> --work <abs> --jobs <cores> [--max-wheel-mb M] [--skip <dist>]…` → `FARM OK: minted · skipped · refused …`, `farm.json` the receipt; one venv per package with `--no-deps` (the ring is the index), a name the catalog holds is skipped, a wheel over the cap is refused; `--producer typescript_ast` farms npm: candidates ranked by last-month downloads, `npm install --prefix` per package, names as slugs |
| push shards into a content-addressed index; pull one back, byte-verified; what an index holds | `python3 -m graphy push <shard>… --index <abs> [--name <n>]` · `python3 -m graphy pull <name\|address> --index <abs\|url> --out <abs>` · `python3 -m graphy index --index <abs\|url> [--verify]` |
| the seam between a tenant's shards; resolve its text labels | `python3 -m graphy converge --tenant <descriptor> --tenant-id <name> [--resolve]` |
| compile a tenant's store | `python3 -m graphy build --tenant <descriptor> --tenant-id <name>` |
| audit a tenant, read-only | `python3 -m graphy check --tenant <descriptor> --tenant-id <name>` |
| does A reach B | `python3 -m graphy walk --tenant <descriptor> --tenant-id <name> --seed <id> --target <id>` |
| does A in one tenant reach B in another — two tenants in one process, the crossing only on a declared join | `python3 -m graphy bridge --tenant <A> --tenant-id <a> --tenant <B> --tenant-id <b> --join <scheme> --seed <id> --target <id>` — `BRIDGE PATH … crossings=N` with the hops, each tagged with its side; the join receipt prints each side's release; no `--join` refuses, two releases of the joined scheme refuse unless `--allow-release-skew` |
| draw it: the pillars, the unit map, one arm, a symbol's neighbourhood — from the store, ASCII in the terminal or a self-contained HTML+SVG page | `python3 -m graphy draw --tenant <descriptor> --tenant-id <name> [--corpus <slug>] [--pillars --partition <json> \| --arm NAME --partition <json> \| --symbol S --radius R] [--lr] [--emit html --interactive -o page.html]` · `--check page.html` · `--atlas <dir> --partition <json>` writes every picture with a receipt (the rebuilds land it at `substrate/atlas/`) |
| the doors: what a symbol calls down to the primitives · who depends on it · what explains it | `python3 -m graphy descend\|blast\|explain <symbol> --tenant <descriptor> --tenant-id <name> [--depth N]` — a symbol is an exact id or its dotted tail; two matches refuse |
| the MCP server for any client; the demo | `python3 -m graphy mcp --tenant <descriptor> --tenant-id <name>` · `bash tenants/fastapi/mcp.sh` (Claude Code: the repo's `.mcp.json`) · `../.venv/bin/python tenants/fastapi/demo.py --runner claude-code` → `DEMO OK` |
| a seed's neighbourhood | `python3 -m graphy.query <id> --mesh-set <slugs> --tenant-id <name> --data-home <abs> --join-keys <path>` |
| the generated region in each arm file: render it from the store, or verify it and name the drift | `python3 -m graphy arms --tenant <descriptor> --tenant-id <name> --corpus <slug> --partition <partition.json> --dir <arms dir> [--verify]` — `ARMS OK` or `ARMS DRIFT` naming each arm as moved (the walk), edited (a hand inside the markers), no-region or no-file; exit 1 on drift. The prose outside the markers is never touched |
| propose a corpus's arms from the walk; diff the proposal against the curated cut | `python3 -m graphy pillars --tenant <descriptor> --tenant-id <name> [--corpus <slug>] [--arms N] [--write <partition.json>] [--against <partition.json>]` — crowns by fan-out, the floor by fan-in, every unit with the numbers that placed it; `--against` exits 1 and names each unit cut differently |
| the mechanical fan-out of a shard; a single package cut into its pillars | `python3 -m graphy fanout --graph-dir <shard> --out <dir> [--depth N \| --partition <json>]` · `--verify` — a partition is `{"groups": {NAME: [dotted prefix, …]}, "rest": NAME}`, longest prefix wins |
| the whole index, one query — the knowledge graph asked across every release the farm minted | `python3 -m graphy estate --index <abs> --emit` once, then `--sql "<over adj(name, corpus, src, dst, edge_type, dst_repr, line) and nodes(name, corpus, id, kind, node_type, dotted, module, role, file, line, version)>"` — STALE refuses when the catalog moved |
| the whole estate, one query | `python3 -m graphy estate --tenant <descriptor> --tenant-id <name> --sql "<over adj(corpus, src, dst, edge_type, …) and nodes(corpus, id, …)>"` — `pip install 'graphyos[estate]'`; `graphy build` emits the parquet when duckdb is present and says SKIPPED when it is not |
| is the parquet as fresh as the shard | `python3 -m graphy container --tenant <descriptor> --tenant-id <name>` — fresh · pending · stale by name; `--emit` writes what is not fresh. `build --container <slug>_graph` writes one shard's now and leaves the rest pending until `graphy estate` asks, which is what `eat` does for the ring |
| the stored walks; the hops the live generation broke | `python3 -m graphy traversals --tenant <descriptor> --tenant-id <name>` · `--replay` — exit 1 when a stored walk no longer holds |
| bolt the hooks and the gate onto an eaten repo | `python3 -m graphy shell install --repo <abs>` → `.graphy/hooks/*.sh` · `.claude/settings.json` · `GRAPHY.md`; the gate: `echo <hook json> \| python3 -m graphy.shell.gate` — exit 2 blocks, the walk to run on stderr |

## MEMORY — the continuity lane, the dumb way

Three hooks in `.claude/settings.json` and two files under `.claude/recovery/` (gitignored):
`reseed_tail.md`, the last session as 1:1 user/assistant exchanges with tool use stripped, and
`sessions/`, every distinct tail archived in sequence. PreCompact and SessionEnd capture; SessionStart
on startup, clear or compact injects the newest bounded edge and names the file to read. A tail the
parser cannot trust is refused loud, never injected hollow. No summarizer, no embeddings.

| move | the tap (from `engine/`) |
|---|---|
| where is X, anchored to its function or class | `python3 -m graphy.lightning "<term>" --path <corpus>` |
| who reads X | `python3 -m graphy.lightning --containers "<term>" --path <corpus>` |
| does A live inside B | `python3 -m graphy.lightning --cooccur A --with B --path <corpus>` |
| the pipe, for what `--path` skips by name | `rg -li '<term>' <path> \| python3 -m graphy.lightning '<term>' --files-from -` |
| when did we say A and B together, with the spans | `python3 -m graphy.lightning.bloodhound "<A>" --with "<B>"` |
| the archive's topics · exchanges holding terms · the heat · one term across time | `python3 -m graphy.lightning.reseed_graph topics \| search <terms> \| heat <terms> \| chain <term>` |
| render any transcript by hand | `python3 -m graphy.reseed render --transcript <jsonl> [--budget-chars N]` |

The memory doors default to `.claude/recovery/sessions` under `CLAUDE_PROJECT_DIR` (or the cwd);
`--path` points them anywhere. ripgrep is required for the fast path (`apt install ripgrep`, a build
with PCRE2); without it lightning falls back to Python, correct and slower. `GRAPHY_RG` names a
binary that is not on PATH.

## THE TENANTS — the fan-out

`CLAUDE.md` → the tenant router → its arms → the walk. A place you cannot reach from here is stranded.

| tenant | router | what it proves |
|---|---|---|
| **FastAPI** | [`engine/tenants/fastapi/FASTAPI.md`](engine/tenants/fastapi/FASTAPI.md) | the public demo: a framework compiled, walked, and fanned out into four pillars a cold agent can operate from |
| **SQLAlchemy** | [`engine/tenants/sqlalchemy/SQLALCHEMY.md`](engine/tenants/sqlalchemy/SQLALCHEMY.md) | the second tenant: a heavy package eaten cold from a venv the rebuild provisions, and the bridge — a walk from a FastAPI symbol into a SQLAlchemy one on a declared literal, neither tenant reading the other's data |
| **Hono** | [`engine/tenants/hono/HONO.md`](engine/tenants/hono/HONO.md) | the second language: TypeScript minted by the tree-sitter producer onto the same nine words, its ring followed into zod, resolved · built · armed by the same verbs — no consumer knows the language |
| **Express** | [`engine/tenants/express/EXPRESS.md`](engine/tenants/express/EXPRESS.md) | JavaScript through the same producer: CommonJS `require` bound as imports, member-assigned functions as definitions, the runtime ring minted from node_modules — every dependency ships JavaScript and every one mints |
| **Graphy** | [`engine/tenants/graphy/GRAPHY.md`](engine/tenants/graphy/GRAPHY.md) | graphy eats graphy: the engine and its floor as one tenant, six arms from the engine map, and `blast_pr.py` — a diff's blast radius from the walk, posted on every PR |

A tenant is a directory under `engine/tenants/<name>/`: `rebuild.sh` (wipe → mint or place → init →
build → check, every path derived from the file's own location), `<NAME>.md` (the router), `arms/`
(one file per pillar: judgment prose around a generated region `graphy arms` renders and verifies), `partition.json` (the pillars as dotted prefixes — the one curated input; the
rebuild fans the shard out by it), `walk.py` (the tenant's taps). `tenant.json` and `substrate/` are rebuilt,
never tracked. A shard is producer output with a `PROVENANCE.json`, re-minted and never hand-edited.

## THE BOARD — where work lands

GitHub Issues on `omnislash157/graphyos` (the public repo; `MARCH_REPO` points there — this repo's board is closed history). Issue numbers are the sequence; `blocked` names a wait.
A finding mid-work becomes an issue, never a note in a doc.

```bash
gh issue list --repo omnislash157/graphyos          # the board
gh issue view <n> --repo omnislash157/graphyos      # an item: its evidence and its done check
```

## THE MARCH — the board loop

One issue is armed; the Stop hook holds the session on it until it closes on GitHub, then arms
the next, acks `/clear` into the session's own tmux pane, and kicks the fresh context every two
minutes until it acks. The skill: `.claude/skills/self-clear/SKILL.md`. The code: `.claude/hooks/march.py`.
The board law — the fork, the add gate, the close, and the optimization pass that runs when the board
drains: `.claude/skills/rung-discipline/SKILL.md`.

| move | the tap (repo root) |
|---|---|
| arm the lowest open unblocked issue · a named one | `python3 .claude/hooks/march.py arm --next` · `--issue N` |
| the fresh context reports in · a batch boundary on purpose | `python3 .claude/hooks/march.py ack` · `clear` |
| where it stands · stop it | `python3 .claude/hooks/march.py status` · `disarm`, or a closing message with a line that starts `MARCH HOLD` + the reason |

## THE RULES OF THIS REPO

This project is one thing, so the rules are few.

- Run `standalone_check.sh` after every change to `engine/`. Green or it did not land.
- The done token is the production run: a lane is done when `quickstart.sh` or the tenant's
  `rebuild.sh` proves it on a real repo, timed, in `RECON.md`. A test is a floor, never the proof.
- Commit to `main` when the operator rules or agrees; agreed is intent to commit and push.
- No auto-generated docs in git. A fan-out compiled by `graphy fanout` is a build product. The one
  exception is the marked region inside an arm file (`graphy arms`): the walk's inventory beside the
  operator's prose, verified on every ring-minted rebuild, so drift between the two is named and never absorbed.
- Ask before making the repo public or doing anything irreversible. Everything else, derive from
  the walk and march.
