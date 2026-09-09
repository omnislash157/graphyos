# graphy

**Give your coding agent a memory it can grep. Give it a codebase it can walk.**

[![ci](https://github.com/omnislash157/graphyos/actions/workflows/ci.yml/badge.svg)](https://github.com/omnislash157/graphyos/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/graphyos)](https://pypi.org/project/graphyos/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://pypi.org/project/graphyos/)
[![MCP registry](https://img.shields.io/badge/MCP-io.github.omnislash157%2Fgraphyos-black)](https://registry.modelcontextprotocol.io/v0/servers?search=graphyos)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

Every `/clear` wipes your agent's mind. Every compaction throws away the three hours it just spent
learning your code with you. graphy fixes that with a text file and a grep, then goes one step
further: it compiles the whole codebase, dependencies included, into a graph the agent walks
instead of reads.

```bash
pip install graphyos
cd /path/to/your/repo && graphy eat . && graphy shell install --repo "$PWD"
```

Two commands. After that:

- **Sessions carry over.** The next session opens by reading the end of the last one, verbatim.
  Not a summary. The actual exchanges, tool noise stripped, a sha on every tail.
- **Every conversation is searchable at grep speed.** The archive is plain markdown under
  `.claude/recovery/sessions/`. Two words give you every session where they were discussed
  together, as a heat map with the passages, in a tenth of a second.
- **The code is a graph, not a pile of files.** Does A reach B. What breaks if this changes. Who
  calls this class across every package in the ring. Answered from structure in milliseconds,
  served over MCP to Claude Code, Cursor or anything else that speaks it.
- **The memory is welded to the code.** Ask `blast` what depends on a function and it lists the
  conversations that discussed it beside the callers. Ask `graphy history --symbol <name>` and it
  walks from the symbol into every session that mentioned it, oldest first, with the commits.

No summarizer. No embeddings. No model ever decides an edge or picks what mattered. The core is
the Python standard library, ripgrep and three shell hooks, with zero runtime dependencies.

Created by Matt Hartigan, 2026. Apache 2.0.

## How the memory works

Three Claude Code hooks. `PreCompact` and `SessionEnd` write the session as 1:1 user/assistant
exchanges to `.claude/recovery/reseed_tail.md` and archive every distinct tail in sequence.
`SessionStart` on startup, clear or compact prints the newest tail as context and names the file
holding the whole record. A tail the parser cannot trust is refused loud, never injected hollow; a
hook that cannot help never wedges the session.

```bash
python3 -m graphy.lightning.bloodhound "gallery" --with "showcase"
#   co-occurrence: 5 file(s) hold BOTH terms within ±10 tokens
#   HEAT — which files this term DOMINATES … the daisy-chained spans, hottest file first
```

`lightning` is the search half: ripgrep discovers the files, lightning walks each hit out to the
function, class or exchange that holds it. `bloodhound` maps two terms across the archive over
time. Every exchange is also a node in the code graph, bound to the symbols it names, so the walk
verbs answer "what did we say about this" with no archive read. The lane in full:
[`engine/graphy/shell/README.md`](engine/graphy/shell/README.md).

## How the graph works

One command mints your package and every package it imports into a walkable substrate, resolves who
calls what through the code's own scope, compiles it into a store, and audits the result. Every edge
is structural, a wormhole between shards on a shared literal, or a label bound through real scope.
A name match is never an edge. Every answer is a walk over structure, and every walk is a query,
never a load.

## The thirty-second demo

One blast-radius question on FastAPI, three ways, every answer scored against the store's own
list of dependents. Run on this box; the full output is in `RECON.md` §20.

```text
`iterate_in_threadpool` in Starlette is about to change its signature. What in FastAPI breaks, and through which call chain?

┌────────────────────────────────┬──────────┬───────────┬──────────┬────────────┐
│ way                            │ seconds  │ tokens in │ tok out  │ dependents │
├────────────────────────────────┼──────────┼───────────┼──────────┼────────────┤
│ graphy alone, no model         │     0.00 │         0 │        0 │   5/5      │
│ claude-haiku-4-5 + graphy MCP  │     14.8 │     48266 │     1286 │   5/5      │
│ claude-opus-5 + 270 KB source  │     26.5 │    103171 │     2108 │   5/5      │
└────────────────────────────────┴──────────┴───────────┴──────────┴────────────┘
```

A cold small model with graphy's five walk tools (`draw` came after this run) and nothing else names the same five functions, with
the chain, as a frontier model handed the three right source files by hand. The store alone does
it in a millisecond.

```bash
bash engine/tenants/fastapi/rebuild.sh                                   # the FastAPI tenant, from the vendored shard
.venv/bin/python engine/tenants/fastapi/demo.py --runner claude-code     # on your Claude Code login
ANTHROPIC_API_KEY=… .venv/bin/python engine/tenants/fastapi/demo.py      # or the SDK (pip install anthropic)
```

Point any MCP client at the same server: Claude Code reads it from this repo's `.mcp.json`;
anywhere else, `bash engine/tenants/fastapi/mcp.sh` on stdio, or `graphy mcp --tenant … --tenant-id …`
over any eaten repo. Six tools: `hunt` · `descend` · `blast` · `walk` · `draw` · `explain`.

Over your own repo, no pointer to write: `graphy eat .` once, then the Claude Code plugin at
[`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) runs `graphy mcp --repo "${CLAUDE_PROJECT_DIR}"` —
the server reads `.graphy/tenant.json` under the project root and the package name from the ring
receipt eat left, and refuses by name when the repo has not been eaten. The same argv is the MCP
registry's entry, [`server.json`](server.json) (`uvx graphyos mcp --repo <repo>`).

```bash
claude plugin marketplace add omnislash157/graphyos    # the repo is the marketplace (.claude-plugin/marketplace.json) …
claude plugin install graphy@graphyos                  # … and the plugin; inside Claude Code the same two as /plugin …
claude --plugin-dir /path/to/graphyos                   # or a checkout, no marketplace: the checkout is the plugin
```

## The page, one line

```bash
uvx --from 'graphyos[typescript]' graphy showcase .     # no venv, no install — the page at .graphy/showcase/index.html
```

`uvx` is [uv](https://github.com/astral-sh/uv)'s runner: it makes the venv, installs `graphyos`
into it and runs `graphy showcase` over the repo you are in — the modules drawn, the pillars the
walk proposes, the ring, the MCP block, three questions. Run on this box from a scratch venv
holding nothing but `uv` (`RECON.md` §86). This is the drawing it makes of graphy itself, from
graphy's own store — [`docs/pillars.svg`](docs/pillars.svg), written by the graphy tenant's rebuild,
re-rendered and compared byte for byte in the gate, never drawn by hand:

![graphy's pillars, drawn by graphy from its own store](docs/pillars.svg)

## Install, then eat — two lines

```bash
pip install 'graphyos[estate,typescript]'     # PyPI: graphyos 0.2.3 — the extras are optional
cd /path/to/your/repo && graphy eat .        # a repo with several packages: graphy eat . --package <name>
graphy showcase .                            # the page: .graphy/showcase/index.html — open it in a browser
```

The distribution is `graphyos`; everything you type after install is `graphy`. Python 3.10+ on
Linux and macOS; on Windows, through WSL — `eat` resolves a venv on either layout by `sysconfig`,
but the hooks, `shell install` and the MCP pointer are bash, and the store lock is a named no-op
without `fcntl`.
`[estate]` is DuckDB for the parquet estate; without it every JSON door still works and the build
says `CONTAINER SKIPPED` instead of pretending. `[typescript]` is tree-sitter for the TypeScript
and JavaScript producer.

`eat` provisions the repo's own dependencies beside it (a venv with `pip install <repo>`, or
`npm install` for a `package.json` repo — printed, and a repo that will not install is minted
alone and the line says so), mints the package and every package it imports, resolves the labels
through scope, compiles the store, audits it, and ends with the three things you do next: the
MCP block to paste into Claude Code or Cursor, the drawing, three questions.

**Eating a repo you do not trust runs its build.** `pip install <repo>` runs that repo's build
backend on your machine, and `npm install` its dependencies' installs (scripts off). For a
stranger's repo, `graphy eat . --no-provision` (and `graphy showcase <url> --no-provision`)
runs nothing of theirs: the package is minted from its source with an empty ring, every import
left unresolved by name, no venv, no pip, no npm. `--site-packages` names an install you
already have and skips the provisioning.

**What it reads today.** Python, through the standard library's own parser; TypeScript (with
TSX) and JavaScript (ESM and CommonJS), through tree-sitter. Nothing else yet: a language is a
producer, a resolver and a locator, and those are the ones that exist.

`eat` prints every step as it lands and ends with what you do next:

```text
MINT OK: httpx 538 nodes / 2548 edges -> …/.graphy/substrate/httpx_graph
MINT OK: httpcore 539 nodes / 2251 edges -> …/.graphy/substrate/httpcore_graph
…
RING: 7 shard(s) · stdlib skipped 62 · unresolved brotli, click, h2, … -> …/.graphy/substrate/ring.json
RESOLVE OK: httpx 1658 label(s) -> … edge(s) (import … · local … · reexport … · self … · super …)
BUILD OK: compiled 2522 nodes / … edges -> …/.graphy/substrate/.mesh_store_….sqlite
CONTAINER PENDING: 7 shard(s) — graphy estate emits them on the first ask, graphy container --emit writes them now
CHECK OK: descriptor valid; store fresh; journal readable for all declared graphs; container fresh for 0/7 shard(s), 7 pending until the estate asks
EAT OK: httpx + 6 ring shard(s) -> /path/to/repo/.graphy
  the tenant:  --tenant /path/to/repo/.graphy/tenant.json --tenant-id httpx
  a walk:      graphy walk --tenant … --tenant-id httpx --seed httpx://module/httpx --target certifi://module/certifi
  the estate:  graphy estate --tenant … --tenant-id httpx
  the walks:   graphy traversals --tenant … --tenant-id httpx [--replay]
```

```bash
# 3. does A reach B — across packages, on the literal
graphy walk --tenant /path/to/repo/.graphy/tenant.json --tenant-id httpx \
    --seed httpx://module/httpx --target certifi://module/certifi
#   WALK PATH: hops=2 steps=httpx://module/httpx -> httpx://module/httpx._config -> certifi://module/certifi
#   TRAVERSAL: source=live reads=15 stored=…/.graphy/substrate/traversals/<generation>/<seed>.parquet
# run it again: source=store reads=0 — the walk is kept as rows; a walk from another seed that
# crosses this one splices through it, and after the repo moves `graphy traversals --replay`
# names the hops that no longer hold

# 4. the whole ring as one SQL view: adj(corpus, src, dst, edge_type, attrs, dst_repr, src_repr) and nodes(corpus, id, …)
graphy estate --tenant /path/to/repo/.graphy/tenant.json --tenant-id httpx \
    --sql "SELECT a.corpus, n.corpus, count(*) FROM adj a JOIN nodes n ON a.dst = n.id WHERE a.corpus <> n.corpus GROUP BY 1, 2 ORDER BY 3 DESC"
#   httpx_graph  httpcore_graph  …        ESTATE OK: 9 row(s) over 7 shard(s) in 5.8 ms

# 5. is it still true — the store against the repo's HEAD, the parquet against the shards
graphy check --tenant /path/to/repo/.graphy/tenant.json --tenant-id httpx
```

Everything lands in `<repo>/.graphy/`, which ignores itself (your `git status` stays clean) and
is rebuilt from the previous shards every time. It holds a shard per package in the ring, so a
big application eats big: a company repo with numpy, networkx and livekit in its ring lands 165
shards and about a gigabyte beside the repo, in a hundred seconds (15,456 files parsed). A repo with several importable packages
is refused by name before anything is installed — `graphy eat . --package <name>` picks one.
Node ids are `<package>://<module|class|func|method>/<dotted>`.

## Or let the script do all five

```bash
bash quickstart.sh https://github.com/encode/httpx.git
#   … GRAPHY_QUICKSTART_OK: httpx eaten in 5.9s -> staging/quickstart/httpx/.graphy
```

Clones the repo, installs its dependencies into a venv of their own, eats it, runs the estate
query and the walk, and prints the done token with the time. That line is the proof this README
is true on the machine it ran on; `RECON.md` §16 records the last run.

## What an edge is, and is not

Every edge is one of three things: **structural** (from the syntax tree — imports, contains,
inherits, decorates, calls), a **wormhole** (the same literal is a node id in two shards, free by
construction: `starlette://module/starlette.routing` is an edge target in FastAPI's shard and a
node in Starlette's), or a **resolved label** — a call target the producer left as text, bound
through the scope that actually binds it: a definition in the same module, the module's own
`imports` edges (through re-exports, one hop at a time), `self` against the containing class,
`super` against a resolved base. A name that no rule reaches stays text, with the qualified
literal it would need and the reason no node carries it. No name match is ever an edge.

## Beyond the five

| move | the door |
|---|---|
| mint one package and its ring anywhere | `graphy smash --package <name> --site-packages <abs> --out <abs> [--corpus <checkout>] [--parity <golden shard>]` |
| upstream moved: the newest release minted into a sibling substrate, proven, and the born/died diff per shard | `graphy refresh --tenant … --tenant-id … --package <name> [--check]` — the current substrate is never touched |
| one question across all of it: who imports what, the most-inherited classes, who shells out — over every release in the index, in milliseconds | `graphy estate --index <abs> --emit` then `graphy estate --index <abs> --sql "SELECT name, count(*) FROM adj WHERE edge_type='imports' AND dst LIKE 'typing_extensions://%' GROUP BY 1"` |
| the open index: the top N PyPI packages minted into one content-addressed index, in parallel, resumably | `graphy farm --top 500 --index <abs> --work <abs> --jobs 12` — then `graphy pull requests==2.32.5 --index <abs\|https://…> --out <abs>` from any box |
| push a shard into an index; pull one back, every byte verified | `graphy push <shard>… --index <abs>` · `graphy pull pydantic==2.13.5 --index <abs\|https://…> --out <abs>` · `graphy index --index … --verify` |
| the seam between shards, and the resolver | `graphy converge --tenant … --tenant-id … [--resolve]` |
| the parquet: fresh or stale, by digest | `graphy container --tenant … --tenant-id … [--emit]` |
| the stored walks; the hops a new generation broke | `graphy traversals --tenant … --tenant-id … [--replay]` |
| the showcase: one page of your codebase, made by one command — the modules drawn (click to light what reaches what), the pillars the walk proposes, the ring, the MCP block, three questions, how to add a model | `graphy showcase .` · `graphy showcase https://github.com/encode/httpx.git` → `.graphy/showcase/index.html` + `showcase.txt` |
| the gallery: the same page over ten repos people know, one index, one receipt — the site at graphy-os.com, built inside the Dockerfile at the root so every deploy is a fresh gallery on the current engine | `bash gallery.sh gallery $(cat gallery.txt)` → `gallery/index.html` + `gallery.json`; `docker build -t graphy-gallery .` |
| draw it for the human: the pillars, the module map, one arm, a symbol's neighbourhood — computed from the store, ASCII in the terminal or one self-contained HTML+SVG page, no drawing by hand | `graphy draw --tenant … --tenant-id … --pillars --partition <json> --lr` · `--symbol get_request_handler --radius 2 --emit html --interactive -o page.html` — the MCP server has `draw` too |
| the doors: what a symbol calls down to the primitives, who depends on it, what explains it | `graphy descend\|blast\|explain <symbol> --tenant … --tenant-id …` — `descend get_request_handler` on the FastAPI tenant crosses fastapi → starlette → anyio |
| the MCP server over an eaten repo, for Claude Code / Cursor / any client | `graphy mcp --tenant … --tenant-id …` on stdio — `hunt` · `descend` · `blast` · `walk` · `draw` · `explain` |
| the hooks and the gate, bolted onto your repo — and the memory lane with them: every session captured as 1:1 exchanges under `.claude/recovery/`, re-seeded on the next start, and the seven doors that read the archive (`lightning` · `bloodhound` · `reseed_graph`) named in the installed `GRAPHY.md` | `graphy shell install --repo <abs>` — [`engine/graphy/shell/README.md`](engine/graphy/shell/README.md) |
| the pillars proposed from the walk, with the evidence per unit; a partition file the fan-out takes | `graphy pillars --tenant <descriptor> --tenant-id <name> [--corpus <slug>] [--write <partition.json>] [--against <partition.json>]` |
| the fan-out a cold agent reads; one package cut into named pillars | `graphy fanout --graph-dir <shard> --out <dir> [--depth N \| --partition <json>]` · `--verify` |
| two tenants in one process, and a walk from one into the other on a declared join — the hops printed, each tagged with its side | `graphy bridge --tenant <A> --tenant-id <a> --tenant <B> --tenant-id <b> --join typing_extensions --seed <id> --target <id>` — FastAPI → SQLAlchemy in [`engine/tenants/sqlalchemy/SQLALCHEMY.md`](engine/tenants/sqlalchemy/SQLALCHEMY.md) |
| the arm files' walk-derived half as a generated region, verified against the store on every rebuild | `graphy arms --tenant … --tenant-id … --corpus <slug> --partition <json> --dir <arms> [--verify]` — `ARMS DRIFT` names each arm the walk moved or a hand edited |
| a second language: TypeScript over tree-sitter onto the same nine words, the ring followed into node_modules | `pip install 'graphyos[typescript]'` · `graphy smash --package <slug> --site-packages <node_modules> --corpus <src> --out … --producer typescript_ast` · `bash quickstart.sh <ts repo>` — [`engine/tenants/hono/HONO.md`](engine/tenants/hono/HONO.md) |
| a worked tenant with four walk-derived arms | [`engine/tenants/fastapi/FASTAPI.md`](engine/tenants/fastapi/FASTAPI.md) |

Not here yet, by name: the shard index. The board is GitHub Issues on this repo.

<!-- mcp-name: io.github.omnislash157/graphyos -->

## The working repo

```text
engine/               THE PRODUCT — pip-installable, imports and runs as graphy, zero host reach
CLAUDE.md             the router an agent in this repo works from
RECON.md              the cold-start record: measured, dated, every number with its re-derive command
standalone_check.sh   the departure gate: a fresh venv installs engine/ alone → GRAPHY_STANDALONE_OK
quickstart.sh         the production proof → GRAPHY_QUICKSTART_OK
staging/              development input, never released; corpora/, containers/, quickstart/ are gitignored data
```

`engine/` is the only place engine work lands. Run `standalone_check.sh` after every change to it.
