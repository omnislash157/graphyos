# graphy

[![ci](https://github.com/omnislash157/graphyos/actions/workflows/ci.yml/badge.svg)](https://github.com/omnislash157/graphyos/actions/workflows/ci.yml)


**Bolt it onto a repo and it eats the whole thing.** One command mints your package and every
package it imports into a walkable substrate, resolves who calls what through the code's own
scope, compiles it into a store, lays parquet beside every shard, and audits the result. Then you
ask it things: does A reach B, what crosses from my code into that dependency, who calls this
class across the whole ring. No model decides an edge. Every answer is a walk over structure,
and every walk is a query, never a load.

Created by Matt Hartigan, 2026. Apache 2.0.

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

A cold small model with graphy's five tools and nothing else names the same five functions, with
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

## Install

```bash
git clone https://github.com/omnislash157/graphyos.git && cd graphyos
python3 -m venv .venv && .venv/bin/pip install -e 'engine[estate]'   # graphyos + duckdb, nothing else
# after publish:  pip install 'graphyos[estate]'                      # not on PyPI yet — the release is built and checked by release.sh, published on the operator's word
```

The distribution is `graphyos`; everything you type after install is `graphy`. Python 3.10+.
`[estate]` is DuckDB for the parquet estate; without it every JSON door still works and the
build says `CONTAINER SKIPPED` instead of pretending. `[typescript]` is tree-sitter for the
TypeScript producer.

**What it reads today.** Python, through the standard library's own parser; TypeScript (with
TSX) and JavaScript (ESM and CommonJS), through tree-sitter. Nothing else yet: a language is a
producer, a resolver and a locator, and those are the ones that exist.

## Five commands

```bash
# 1. the repo's dependencies, in a venv of their own — the import ring is resolved from here
python3 -m venv /path/to/repo/.graphy/venv && /path/to/repo/.graphy/venv/bin/pip install /path/to/repo

# 2. eat it
.venv/bin/graphy eat --repo /path/to/repo \
    --site-packages /path/to/repo/.graphy/venv/lib/python3.12/site-packages
```

`eat` prints every step as it lands and ends with the two lines you need next:

```text
MINT OK: httpx 538 nodes / 2548 edges -> …/.graphy/substrate/httpx_graph
MINT OK: httpcore 539 nodes / 2251 edges -> …/.graphy/substrate/httpcore_graph
…
RING: 7 shard(s) · stdlib skipped 62 · unresolved brotli, click, h2, … -> …/.graphy/substrate/ring.json
RESOLVE OK: httpx 1658 label(s) -> … edge(s) (import … · local … · reexport … · self … · super …)
BUILD OK: compiled 2522 nodes / … edges -> …/.graphy/substrate/.mesh_store_….sqlite
CONTAINER OK: 7 shard(s) · 2522 node row(s) · … edge row(s) · 0.45 MB parquet · 0.28 s beside the shards
CHECK OK: descriptor valid; store fresh; journal readable for all declared graphs; container fresh for 7/7 shard(s)
EAT OK: httpx + 6 ring shard(s) -> /path/to/repo/.graphy
  the tenant:  --tenant /path/to/repo/.graphy/tenant.json --tenant-id httpx
  a walk:      graphy walk --tenant … --tenant-id httpx --seed httpx://module/httpx --target certifi://module/certifi
  the estate:  graphy estate --tenant … --tenant-id httpx
  the walks:   graphy traversals --tenant … --tenant-id httpx [--replay]
```

```bash
# 3. does A reach B — across packages, on the literal
.venv/bin/graphy walk --tenant /path/to/repo/.graphy/tenant.json --tenant-id httpx \
    --seed httpx://module/httpx --target certifi://module/certifi
#   WALK PATH: hops=2 steps=httpx://module/httpx -> httpx://module/httpx._config -> certifi://module/certifi
#   TRAVERSAL: source=live reads=15 stored=…/.graphy/substrate/traversals/<generation>/<seed>.parquet
# run it again: source=store reads=0 — the walk is kept as rows; a walk from another seed that
# crosses this one splices through it, and after the repo moves `graphy traversals --replay`
# names the hops that no longer hold

# 4. the whole ring as one SQL view: adj(corpus, src, dst, edge_type, attrs, dst_repr, src_repr) and nodes(corpus, id, …)
.venv/bin/graphy estate --tenant /path/to/repo/.graphy/tenant.json --tenant-id httpx \
    --sql "SELECT a.corpus, n.corpus, count(*) FROM adj a JOIN nodes n ON a.dst = n.id WHERE a.corpus <> n.corpus GROUP BY 1, 2 ORDER BY 3 DESC"
#   httpx_graph  httpcore_graph  …        ESTATE OK: 9 row(s) over 7 shard(s) in 5.8 ms

# 5. is it still true — the store against the repo's HEAD, the parquet against the shards
.venv/bin/graphy check --tenant /path/to/repo/.graphy/tenant.json --tenant-id httpx
```

Everything lands in `<repo>/.graphy/`, which `eat` marks ignored for your repo and rebuilds from
scratch every time. Node ids are `<package>://<module|class|func|method>/<dotted>`.

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
| draw it for the human: the pillars, the module map, one arm, a symbol's neighbourhood — computed from the store, ASCII in the terminal or one self-contained HTML+SVG page, no drawing by hand | `graphy draw --tenant … --tenant-id … --pillars --partition <json> --lr` · `--symbol get_request_handler --radius 2 --emit html --interactive -o page.html` — the MCP server has `draw` too |
| the doors: what a symbol calls down to the primitives, who depends on it, what explains it | `graphy descend\|blast\|explain <symbol> --tenant … --tenant-id …` — `descend get_request_handler` on the FastAPI tenant crosses fastapi → starlette → anyio |
| the MCP server over an eaten repo, for Claude Code / Cursor / any client | `graphy mcp --tenant … --tenant-id …` on stdio — `hunt` · `descend` · `blast` · `walk` · `draw` · `explain` |
| the hooks and the gate, bolted onto your repo | `graphy shell install --repo <abs>` — [`engine/graphy/shell/README.md`](engine/graphy/shell/README.md) |
| the pillars proposed from the walk, with the evidence per unit; a partition file the fan-out takes | `graphy pillars --tenant <descriptor> --tenant-id <name> [--corpus <slug>] [--write <partition.json>] [--against <partition.json>]` |
| the fan-out a cold agent reads; one package cut into named pillars | `graphy fanout --graph-dir <shard> --out <dir> [--depth N \| --partition <json>]` · `--verify` |
| two tenants in one process, and a walk from one into the other on a declared join — the hops printed, each tagged with its side | `graphy bridge --tenant <A> --tenant-id <a> --tenant <B> --tenant-id <b> --join typing_extensions --seed <id> --target <id>` — FastAPI → SQLAlchemy in [`engine/tenants/sqlalchemy/SQLALCHEMY.md`](engine/tenants/sqlalchemy/SQLALCHEMY.md) |
| the arm files' walk-derived half as a generated region, verified against the store on every rebuild | `graphy arms --tenant … --tenant-id … --corpus <slug> --partition <json> --dir <arms> [--verify]` — `ARMS DRIFT` names each arm the walk moved or a hand edited |
| a second language: TypeScript over tree-sitter onto the same nine words, the ring followed into node_modules | `pip install 'graphyos[typescript]'` · `graphy smash --package <slug> --site-packages <node_modules> --corpus <src> --out … --producer typescript_ast` · `bash quickstart.sh <ts repo>` — [`engine/tenants/hono/HONO.md`](engine/tenants/hono/HONO.md) |
| a worked tenant with four walk-derived arms | [`engine/tenants/fastapi/FASTAPI.md`](engine/tenants/fastapi/FASTAPI.md) |

Not here yet, by name: the shard index. The board is GitHub Issues on this repo.

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
