# SQLAlchemy — the tenant router

> The arm-doc law: no numbers, no status, no history — only the tap. Every symbol named here came
> out of the walk; re-walk before you trust it. Counts, with the commands that re-derive them, live
> in `RECON.md` at the working-repo root, never here.

**What this tenant is.** The second tenant, and the one that proves graphy is not a FastAPI tool:
a heavy package the engine had never seen, minted from a venv it provisions itself, its import
ring beside it (greenlet, typing_extensions), converged, built and audited by the same verbs the
FastAPI tenant runs — with no vendored fixture and no parity step, because the point is a package
eaten cold. `rebuild.sh` provisions `staging/corpora/sqlalchemy/venv` pinned to `SQLALCHEMY_RELEASE`
(or takes `GRAPHY_CORPUS_SITE_PACKAGES`), mints with `graphy smash`, declares the tenant over
exactly the shards the ring minted, and lands the fan-out and the walk's own pillar proposal under
the substrate. Nothing is hand-edited: a shard is producer output or it is not a shard.

**What it is for.** Two tenants in one process, neither reading the other's data, and a walk that
crosses from one into the other on a declared join: `graphy bridge`. Both rings minted
`typing_extensions`, so the same literal (`typing_extensions://module/typing_extensions`) is a node
id in both stores — a wormhole by construction. The bridge crosses on it only when the scheme is
declared with `--join`; an undeclared scheme that happens to be spelled the same on both sides is
two nodes, and the walk stays home. The rule is the docstring of `engine/graphy/bridge.py`.

## ⚖ THE FIVE PILLARS — cut by hand from the walk's evidence, marked as such; each arm file ends in the walk's own generated region

| pillar | router | modules | the choke point | joins out |
|---|---|---|---|---|
| **SQL** — the expression floor | [`arms/SQL.md`](arms/SQL.md) | `sql` · `schema` · `types` · `inspection` | `select` · `coercions.expect` · `inspect` | typing_extensions (`Protocol`, `TypedDict`, `Self`) |
| **ENGINE** — the connection and the shared floor | [`arms/ENGINE.md`](arms/ENGINE.md) | `engine` · `pool` · `connectors` · `event` · `events` · `exc` · `util` · `log` | `exc.InvalidRequestError` · `exc.ArgumentError` · `util.concurrency.greenlet_spawn` | greenlet (`util.concurrency`), typing_extensions |
| **ORM** — the mapper and its extensions | [`arms/ORM.md`](arms/ORM.md) | `orm` · `ext` | `orm.base.instance_state` · `orm.session.Session` | typing_extensions (`Protocol`, `TypedDict`, `deprecated`) |
| **DIALECTS** — the databases | [`arms/DIALECTS.md`](arms/DIALECTS.md) | `dialects` | the per-database `Dialect` subclasses | the DBAPI drivers the ring did not carry (`psycopg2`, `pymysql`, `oracledb`, …) — reported in `ring.json` as unresolved |
| **TESTING** — the harness the package ships | [`arms/TESTING.md`](arms/TESTING.md) | `testing` | `assertions.eq_` · `exclusions.closed` / `open` · `schema.Table` | `pytest` (unresolved in the ring) |

**Where the hand and the walk disagree.** `graphy pillars` skips every node the producer marks
`role: test` — and the Python producer marks `sqlalchemy/testing/` so — then crowns the arms by
fan-out and makes `sql` the floor with the shared foundations under it, because no single arm
takes two thirds of a foundation's fan-in. TESTING stays a curated arm because the harness ships
in the wheel and an agent lands in it. The curated file keeps the shared floor readable:
the exception, utility, engine, pool and event families are one arm (ENGINE) because a change to a
connection or an error class lands in all of them; `ext` rides with `orm` because nearly all of
it is ORM extensions; `types`, `schema` and `inspection` ride with `sql` because they are the
expression layer's own vocabulary, whatever the dialects consume. `graphy pillars --against
partition.json` names every unit cut differently, with the numbers — read it before trusting
either cut.

## THE EDGE — routed here, no arm

The package `__init__` (the facade every user imports from), `future` (a re-export shim) and
`cyextension` (the Cython accelerators, imported where present). A question that lands on the
facade continues in the pillar the re-exported symbol lives in.

## THE TAPS — run from `engine/`, the tenant dir is `T=tenants/sqlalchemy`

| move | the tap |
|---|---|
| rebuild the tenant: provision the venv, mint the ring, converge, build, check, fan out | `bash $T/rebuild.sh` → `SQLALCHEMY_TENANT_OK` — `SQLALCHEMY_RELEASE=<v>` pins another release; `GRAPHY_CORPUS_SITE_PACKAGES=<abs>` mints from a site-packages you already hold |
| rebuild the tenant from a shard index instead of minting — every shard a `pulled` lane whose command re-pulls it | `GRAPHY_SHARD_INDEX=<abs dir or https base> GRAPHY_PULL="sqlalchemy==2.0.52 typing_extensions==4.16.0 greenlet==3.5.5" bash $T/rebuild.sh` → `PULL OK` ×3 · `SQLALCHEMY_TENANT_OK` |
| the bridge: walk from a FastAPI symbol into a SQLAlchemy one on the declared literal, the hops printed | `python3 -m graphy bridge --tenant tenants/fastapi/tenant.json --tenant-id fastapi --tenant $T/tenant.json --tenant-id sqlalchemy --join typing_extensions --seed fastapi://func/fastapi.param_functions.Cookie --target sqlalchemy://class/sqlalchemy.orm.session.Session` → `JOIN typing_extensions: … at typing_extensions==<release> · … at typing_extensions==<release>` · `BRIDGE PATH … crossings=1` — two releases of the joined scheme refuse unless `--allow-release-skew` |
| the bridge the other way | the same command with the tenants and the seed/target swapped |
| the refusals: no join · a join one side does not carry · one tenant twice | drop `--join` → `BRIDGE REFUSED: no --join declared`; `--join pydantic` → `BRIDGE REFUSED: … no node under pydantic:// in tenant(s) sqlalchemy`; the same descriptor twice → `BRIDGE REFUSED: … share the data_home` |
| what the ring holds, and what it could not find | `python3 -c 'import json;r=json.load(open("$T/substrate/ring.json"));print(sorted(r["minted"]));print(r["unresolved"])'` |
| is the store fresh | `python3 -m graphy check --tenant $T/tenant.json --tenant-id sqlalchemy` |
| does A reach B inside this tenant | `python3 -m graphy walk --tenant $T/tenant.json --tenant-id sqlalchemy --seed <id> --target <id>` |
| draw it: the pillars, the unit map, one arm, a symbol's neighbourhood — the rebuild lands the atlas at `$T/substrate/atlas/` | `python3 -m graphy draw --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --pillars --partition $T/partition.json --lr` · `--symbol Session.execute --radius 2 --emit html --interactive -o page.html` · `--check page.html` |
| the doors | `python3 -m graphy descend\|blast\|explain <symbol> --tenant $T/tenant.json --tenant-id sqlalchemy` — e.g. `blast greenlet_spawn`, `descend Session.execute` |
| the generated region in each arm file, rendered from the store; verified on every rebuild, drift named per arm | `python3 -m graphy arms --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --partition $T/partition.json --dir $T/arms` · `--verify` → `ARMS OK` or `ARMS DRIFT` (exit 1) |
| the arms the walk proposes; the units it cuts differently from the curated five | `python3 -m graphy pillars --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy [--arms N]` · `--against $T/partition.json` (exit 1 names each move) — `rebuild.sh` lands the proposal at `$T/substrate/pillars.json` |
| the shard fanned out by the curated partition | `python3 -m graphy fanout --graph-dir $T/substrate/sqlalchemy_graph --out <dir> --partition $T/partition.json` · `--verify` — `rebuild.sh` lands it at `$T/substrate/fanout/` |
| the MCP server over this tenant | `python3 -m graphy mcp --tenant $T/tenant.json --tenant-id sqlalchemy` |
| has SQLAlchemy moved on PyPI since the shard was minted | `python3 -m graphy refresh --tenant $T/tenant.json --tenant-id sqlalchemy --package sqlalchemy --check` |

Node ids are `sqlalchemy://<node_type>/<dotted>` — `sqlalchemy://class/sqlalchemy.orm.session.Session`,
`sqlalchemy://func/sqlalchemy.sql._selectable_constructors.select`, `sqlalchemy://module/sqlalchemy.engine.base`.

## THE JOINS OUT — honest about the mechanism

The ring is small on purpose: SQLAlchemy's runtime imports reach `typing_extensions` everywhere
(`Protocol`, `TypedDict`, `Self`, `Literal`, `deprecated`) and `greenlet` in `util.concurrency`;
everything else it imports is the standard library or a driver it looks for at runtime
(`psycopg2`, `pymysql`, `oracledb`, `asyncpg`, …) and those are reported in `ring.json` as
unresolved, never guessed. The same `typing_extensions` literal is what the FastAPI tenant's ring
carries, and that shared literal is the bridge's only crossing. Labels the resolver cannot bind
through scope stay text in `wormhole_edges.json`'s tally; no name match is ever an edge.
