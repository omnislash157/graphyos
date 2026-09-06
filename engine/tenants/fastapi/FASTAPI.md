# FastAPI — the tenant router

> The arm-doc law: no numbers, no status, no history — only the tap. Every symbol named here came
> out of the walk; re-walk before you trust it. Counts, with the commands that re-derive them, live
> in `RECON.md` at the working-repo root, never here.

**What this tenant is.** FastAPI's own package minted into one shard (`substrate/fastapi_graph`)
and walked from its compiled store. `rebuild.sh` mints the shard from the pinned wheel with
`graphy smash`, proves it record-for-record against the vendored fixture, and then mints the
framework's import ring beside it as sibling shards (Starlette, pydantic, anyio, and the rest of
what the wheel resolves), builds one store over all of them and audits it. Without a corpus named,
it places the vendored fixture alone. Nothing is hand-edited: a shard is producer output or it is
not a shard. The framework's dependencies are joins OUT of the root shard, named where they bind,
and with the ring minted the walk crosses them.

## ⚖ THE FOUR PILLARS — derived from the walk, not invented

| pillar | router | modules | the choke point | joins out |
|---|---|---|---|---|
| **ROUTING** — the spine | [`arms/ROUTING.md`](arms/ROUTING.md) | `routing` · `applications` · `sse` | `get_request_handler` | Starlette (`Router`, `Route`, `Starlette`, `StreamingResponse`) |
| **DEPENDENCIES** — the engine | [`arms/DEPENDENCIES.md`](arms/DEPENDENCIES.md) | `dependencies` · `params` · `param_functions` · `security` | `solve_dependencies`, built by `get_dependant` | pydantic `FieldInfo` (the param markers), Starlette `Request` |
| **COMPAT** — the pydantic boundary | [`arms/COMPAT.md`](arms/COMPAT.md) | `_compat` · `encoders` · `utils` · `types` · `exceptions` · `exception_handlers` · `datastructures` | `lenient_issubclass` · `jsonable_encoder` | pydantic + pydantic_core, Starlette exceptions |
| **OPENAPI** — the mirror | [`arms/OPENAPI.md`](arms/OPENAPI.md) | `openapi.utils` · `openapi.models` · `openapi.docs` · `openapi.constants` | `get_openapi` → `get_openapi_path` | pydantic `BaseModel` (the spec models) |

```text
how the four stand (the cross-pillar edges, module level — `walk.py pillars` prints the matrix)

   ROUTING ──calls──▶ DEPENDENCIES ──calls──▶ COMPAT
      │                                          ▲
      └──────────────calls───────────────────────┘
   OPENAPI ──reads──▶ ROUTING · DEPENDENCIES · COMPAT      nothing calls OPENAPI except the app's openapi() door
```

**The walk proposes the cut itself.** `graphy pillars` reads the store's module graph and rules each
first-level unit by its numbers: fan-out crowns an arm (routing, dependencies, openapi), the greatest
fan-in no arm owns crowns the floor (`_compat`), a unit another arm consumes is orchestrated by it
(security, param_functions and params under dependencies), and a unit with too few cross-unit edges
is the edge. Where the proposal differs from `partition.json` — `applications` stands alone on the
walk's evidence, and the curated file folds it into ROUTING because it delegates to its router and
both inherit Starlette — `--against` names the unit and the numbers. The curated file stays the
input the fan-out cuts by; the proposal is the evidence beside it.


**Why four, and why these four.** The walk ranks modules two ways. By fan-out, `routing` orchestrates
and `applications` delegates every verb to its `APIRouter` — both inherit Starlette, so they are one
spine. By fan-in, the `_compat` family is the most depended-on cluster in the package, followed by
`exceptions` and `types` — the pydantic boundary is load-bearing and earns an arm. `params` are
`FieldInfo` markers that exist to be read by `analyze_param`, and every security scheme is a
`Depends` callable resolved by `solve_dependencies` — inputs to the engine, not parallel systems.
`openapi` is called by nobody but the app's `openapi()` and reads all three others. An earlier cut of
this tenant carried six arms (routing · applications · dependencies · params · security · openapi)
and no arm for the boundary everything depends on; the walk folds the six into four and adds the one
it missed.

## THE EDGE — routed here, no arm

`responses` · `middleware/*` · `websockets` · `requests` · `staticfiles` · `templating` · `testclient`
· `logger` · `cli` · the package `__init__` — thin re-exports over Starlette, and the public surface
that re-exports the pillars. Three edge modules do real work and are read by the pillars:
`middleware.asyncexitstack.AsyncExitStackMiddleware` (wraps the router app), `background.BackgroundTasks`
and `concurrency` (`contextmanager_in_threadpool` · `iterate_in_threadpool`, used by the solver and the
handler). A question that lands on an edge module continues in Starlette.

## THE TAPS — run from `engine/`, the tenant dir is `T=tenants/fastapi`

| move | the tap |
|---|---|
| rebuild the tenant with the ring minted from the pinned corpus | `GRAPHY_CORPUS_SITE_PACKAGES=<site-packages holding fastapi==0.139.0 and nothing else> bash $T/rebuild.sh` → `PARITY OK` · `FASTAPI_TENANT_OK` — `PYTHON=<an interpreter with duckdb>` to get the parquet beside every shard |
| rebuild the tenant from a shard index instead of minting — every shard a `pulled` lane whose command re-pulls it | `GRAPHY_SHARD_INDEX=<abs dir or https base> [GRAPHY_PULL="fastapi==0.139.0 …"] bash $T/rebuild.sh` → `PULL OK` ×n · `FASTAPI_TENANT_OK` |
| push this tenant's shards into an index | `python3 -m graphy push $T/substrate/*_graph --index <abs>` |
| rebuild the tenant from the vendored fixture alone | `bash $T/rebuild.sh` → `FASTAPI_TENANT_OK` |
| has FastAPI moved on PyPI since the shard was minted | `python3 -m graphy refresh --tenant $T/tenant.json --tenant-id fastapi --package fastapi --check` → `REFRESH CURRENT` or `REFRESH NEWER` |
| the refresh lane: the newest release minted with its ring into `$T/substrate.<release>/`, declared as `$T/tenant.<release>.json`, converged · built · checked there, and the journal's born/died per shard against the current substrate | `python3 -m graphy refresh --tenant $T/tenant.json --tenant-id fastapi --package fastapi` → `DIFF <old> -> <new>` · `REFRESH OK` — the current substrate is untouched; `--fixture ../tests/fixtures/fastapi_graph` also re-mints the golden shard so the next rebuild's parity holds |
| promote a proven sibling | `GRAPHY_CORPUS_SITE_PACKAGES=$T/substrate.<release>/venv/lib/python3.12/site-packages bash $T/rebuild.sh` — after the fixture is re-minted (`--fixture`), or parity refuses by design |
| walk the sibling before promoting it | any door with `--tenant $T/tenant.<release>.json` — e.g. `python3 -m graphy blast Dependant --tenant $T/tenant.<release>.json --tenant-id fastapi` |
| mint any package and its ring, anywhere | `python3 -m graphy smash --package <name> --site-packages <abs> --out <abs> [--corpus <abs>] [--parity <golden shard>]` → `ring.json` |
| what the ring holds, and what it could not find | `python3 -c 'import json;r=json.load(open("$T/substrate/ring.json"));print(sorted(r["minted"]));print(r["unresolved"])'` |
| the seam: wormhole edges per shard pair, labels left as text per shard | `python3 -m graphy converge --tenant $T/tenant.json --tenant-id fastapi` |
| resolve the text labels through scope and rebuild the store on them | `python3 -m graphy converge --tenant $T/tenant.json --tenant-id fastapi --resolve && python3 -m graphy build --tenant $T/tenant.json --tenant-id fastapi` (rebuild.sh does this) |
| is the store fresh, and the parquet beside it | `python3 -m graphy check --tenant $T/tenant.json --tenant-id fastapi` |
| the whole ring as one SQL view (duckdb: `pip install 'graphyos[estate]'`) | `python3 -m graphy estate --tenant $T/tenant.json --tenant-id fastapi --sql "SELECT a.corpus, n.corpus, count(*) FROM adj a JOIN nodes n ON a.dst = n.id WHERE a.corpus <> n.corpus GROUP BY 1, 2"` |
| does A reach B, across packages when the ring is minted | `python3 -m graphy walk --tenant $T/tenant.json --tenant-id fastapi --seed <id> --target <id>` — e.g. seed `fastapi://module/fastapi.routing`, target `starlette://class/starlette.routing.Router` |
| the bridge: from a FastAPI symbol into the SQLAlchemy tenant on the declared literal, two tenants in one process, the hops printed | `python3 -m graphy bridge --tenant $T/tenant.json --tenant-id fastapi --tenant tenants/sqlalchemy/tenant.json --tenant-id sqlalchemy --join typing_extensions --seed fastapi://func/fastapi.param_functions.Cookie --target sqlalchemy://class/sqlalchemy.orm.session.Session` → `JOIN typing_extensions: … at typing_extensions==<release> · … at typing_extensions==<release>` · `BRIDGE PATH … crossings=1` — two releases of the joined scheme refuse unless `--allow-release-skew` — the second tenant: [`../sqlalchemy/SQLALCHEMY.md`](../sqlalchemy/SQLALCHEMY.md) |
| the doors: down to the primitives · who depends on it · what explains it | `python3 -m graphy descend\|blast\|explain <symbol> --tenant $T/tenant.json --tenant-id fastapi` — `descend get_request_handler` names the chain into Starlette and anyio |
| the MCP server over this tenant, for any client | `bash $T/mcp.sh` on stdio — Claude Code reads it from the repo's `.mcp.json` |
| the demo: one blast-radius question, three ways, scored against the store | `../.venv/bin/python $T/demo.py --runner claude-code` (or `ANTHROPIC_API_KEY=…` for the SDK) → `DEMO OK: three ways` |
| a symbol's neighbourhood | `python3 -m graphy.query <id> --mesh-set fastapi --tenant-id fastapi --data-home $T/substrate --join-keys $T/substrate/registry.json --depth 2 --top 25` |
| a symbol's edges — resolved from the store, then the call labels with their candidates | `python3 $T/walk.py edges <id-or-unique-suffix> [--direction in\|out]` |
| the pillar partition, recomputed | `python3 $T/walk.py pillars [--module <dotted>]` — the rule is `$T/partition.json` |
| the generated region in each arm file — the walk's inventory by module, the inherits joins out, the re-walk — rendered from the store; verified on every ring-minted rebuild, drift named per arm | `python3 -m graphy arms --tenant $T/tenant.json --tenant-id fastapi --corpus fastapi --partition $T/partition.json --dir $T/arms` · `--verify` → `ARMS OK` or `ARMS DRIFT` (exit 1) — with the fixture placed alone the joins out are unresolved and `rebuild.sh` says `ARMS SKIPPED` |
| what a newer release moves, per arm | `python3 -m graphy arms --tenant $T/tenant.<release>.json --tenant-id fastapi --corpus fastapi --partition $T/partition.json --dir $T/arms --verify --on-stale warn` — after a `graphy refresh`, every born and died symbol lands in the arm that owns it |
| the arms the walk itself proposes, every unit with the numbers that placed it; the units it cuts differently from the curated four | `python3 -m graphy pillars --tenant $T/tenant.json --tenant-id fastapi --corpus fastapi` · `--against $T/partition.json` (exit 1 names each move) · `--write <json>` — `rebuild.sh` lands the proposal at `$T/substrate/pillars.json` and fans the shard out by it at `$T/substrate/fanout.proposed/` |
| the shard fanned out by that partition, one section per pillar, a receipt pinning the rule | `python3 -m graphy fanout --graph-dir $T/substrate/fastapi_graph --out <dir> --partition $T/partition.json` · `--verify` — `rebuild.sh` lands it at `$T/substrate/fanout/` |

Node ids are `fastapi://<node_type>/<dotted>` — `fastapi://func/fastapi.routing.get_request_handler`,
`fastapi://class/fastapi.applications.FastAPI`, `fastapi://module/fastapi.openapi.utils`. The `edges`
door accepts a unique suffix.

## THE ROUTINE — the refresh, on a clock (documented, not armed)

The lane is a cron line; nothing in it is silent, nothing is in place. It asks PyPI, and when the
release is newer it mints, proves and diffs into the sibling, leaving the current substrate for
the operator to promote by hand after reading the diff. Exit 0 both when current and when a
sibling is proven; exit 1 is a red check on the sibling (it stays on disk); exit 2 is a refusal.

```cron
# every Monday 06:00 UTC — from the repo root; the log is the evidence
0 6 * * 1  cd /abs/path/to/graphy/engine && python3 -m graphy refresh --tenant tenants/fastapi/tenant.json --tenant-id fastapi --package fastapi >> tenants/fastapi/refresh.log 2>&1
```

A Claude Code routine is the same command with the log read afterwards: `/schedule` a weekly run of
that line, and the wake reads `refresh.log`'s last `DIFF` block and `REFRESH` verdict. The sibling
substrate and descriptor are gitignored (`substrate.*/`, `tenant.*.json`), so a routine never
dirties the tree.

## THE JOINS OUT — honest about the mechanism

Starlette is the spine under ROUTING (the router, the route, the app, the responses) and under the
exceptions and `UploadFile` in COMPAT. Pydantic is the boundary: `FieldInfo` under the params,
`BaseModel` under the OpenAPI models and the security credential models, the schema generator and
`ModelField` under `_compat`. `anyio` carries the SSE stream and the threadpool; `python-multipart`
the form body; `email_validator` the OpenAPI email type; `fastapi_cli` the CLI.

An `imports`, `contains` or `inherits` edge with a resolved target is in the store and walkable. A
`calls`, `inherits` or `decorates` edge whose target the producer left as text (`dst_repr`) is
resolved by `graphy converge --resolve` through the scope that binds the name — a definition in
the same module, the module's own `imports` edges (through re-exports, one hop at a time),
`self`/`cls` against the containing class, `super` against a resolved base — into
`substrate/fastapi_graph/wormhole_edges.json`, which the store compiles beside `edges.json`. Every
step is structural; no name match ever becomes an edge. The handler's `Response` resolves to
Starlette's class because `routing` imports it from `starlette.responses`, not because something
is called `Response`. What no rule reaches stays text: `rebuild.sh` folds those labels into a
sidecar, and `walk.py edges` prints them after the resolved edges, each with the qualified literal
the resolver derived (a standard-library name, a symbol the ring did not mint) or, failing that,
a CANDIDATE when exactly one node in the shard carries that bare name. A candidate is a name
match, never a resolved fact — and a missing reverse edge is never evidence that nothing calls a
symbol. Re-walk before you act on any of it.

An `imports` edge whose target is another package is a wormhole once that package is minted: the
same literal (`starlette://module/starlette.routing`) is a node id in both shards, so the walk
crosses on it with no resolver and no model. With the fixture placed alone, the same edge is a
resolved fact with no node behind it and the walk stops at the boundary. `ring.json` in the
substrate says which schemes were minted, which are the standard library, and which the corpus
did not carry — those are reported, never guessed.
