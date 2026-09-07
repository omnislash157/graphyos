# graphy — phase 1 recon, the cold-start record for the standalone folder

> Measured 2026-09-05 on the host VM against `~/<the host codebase>` @ `c003f6dc8`.
> Every number carries the command that re-derives it. Re-run before you trust it.
> Phase 1 = fill this folder by COPY. the host codebase is never modified.

---

## 0 · WHAT THIS PROJECT IS

Compile any codebase — plus its dependencies, its live DB schema, its frontend and its docs —
into one addressable estate, and generate the fan-out that makes a cold agent competent in it.
Open source, Apache 2.0, optimized for reputation not revenue (operator decision 2026-07-27,
authorized by the operator). Model-agnostic. The claim is cheap omniscience over a project,
not another agentic coding framework.

**The four pillars** (unchanged, ruled):

```
json : JSON is the cheapest machine currency
keys : we own the join keys — one central registry
ast  : AST is hierarchy, not magic — anything with rules becomes AST
lens : the whole world is traversable through our lens
```

---

## 1 · THE SCARCE THING IS THE HOP, AND THAT IS THE WHOLE THESIS

Traversal used to be a CONTEXT problem: a frontier model holding the architecture in its head,
paying MB per simulated hop. Making the hop a QUERY flips it — per-hop intelligence becomes
small and COVERAGE becomes the scarce good.

Measured live, whole estate, one query:

```bash
python3 -c "import duckdb;print(duckdb.connect().execute(\"select count(*) from read_parquet('<vault>/*_graph/adjacency.parquet')\").fetchall())"
#   901,121 edges · 478,433 nodes · 118 graphs · 93 ms cold
#   37 MB of parquet standing against a 1.8 GB JSON vault
```

**The law:** A WALK IS A QUERY, NEVER A LOAD. If a hop parses a file, it is not a traversal.
**The corollary:** THE HOPS DO NOT WANT AGENTS. One process holds the estate as one view and
expands a frontier per level. An agent per hop buys a second copy of the engine and nothing
else. Spend agents on JUDGMENT — candidate connections a deterministic recompute then admits
or kills — never on traversal.

---

## 2 · THE STATE OF THE ENGINE — better than "stubbed", and the gap is precise

`graphy_os/` in the host codebase is a working standalone package:

```bash
bash scripts/graphy_standalone_check.sh
#   install OK · host unreachable OK · graphy resolves OK (0.0.1)
#   324 tests passed · prose scrub OK · GRAPHY_STANDALONE_OK
#   24 modules · 7,387 LOC · fresh venv, no host package importable
```

Landed: the floor, the Graph IR, the tenant descriptor, the federated store, the adapters
(python_ast · outline · native JSON), sugiyama, the journal, the CLI
(`init|build|walk|check|fanout`), and the fan-out compiler with a receipt.

### THE GAP, and it is the single most important line in this file — closed by §15 (issue 4, 2026-09-05)

```bash
grep -i 'duckdb\|parquet\|arrow' -r graphy_os/    # → zero hits
grep dependencies graphy_os/pyproject.toml        # → dependencies = []
```

**The container never crossed.** `graphy_os` reads JSON. The parquet/DuckDB estate that does
901K edges in 93ms lives only host-side:

```
host_sdk/tools/repo_substrate/adjacency_container.py   678 LOC
  imports: argparse, json, sys, pathlib, typing              ← stdlib only
  duckdb imported LAZILY inside _connect()                   ← optional dep, not core
  surface: build · build_nodes · emit · hops · walk · estate_connect · edge_records
```

**One host coupling**, and it is the exact defect the product law already names
(NO AMBIENT FALLBACK — an absent tenant refuses):

```python
_DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
```

Under the engine that becomes `tenant.data_home`; the descriptor already carries the field.
**The port is a re-home, not a rewrite.**

Two things that make it a rung and not a copy:

```bash
rg -l 'adjacency_container' --glob '!*__pycache__*' .   # → 20 live host consumers
find . -path '*test*' -name '*.py' | xargs grep -l adjacency_container   # → NOTHING
```

The most-depended-on module in the walk path has **zero tests**, and it is the piece that
has to travel.

---

## 3 · THE TRAVERSAL STORE IS UNBUILT — this is phase 2's substance

Searched specifically. Across the whole tool estate and the engine, **nothing memoizes a walk**:
no hop-path store, no traversal cache, no materialized frontier. `walk()` expands one query per
level and discards the result.

The container solved the READ. It did not solve the REMEMBERING.

**Prior attempt, and it failed:** `recall.py` — recalling exact traversal paths on hops — was
excised 2026-08-14 (`7da532b5a`, board 857): zero live invokers, its one cache entry 19 days
cold. **What survived was deliberately preserved and is the reusable half:**

```
query.py:138  def activate(adj, seed, depth, decay)   # spreading activation
query.py:170  def rank(state, top, min_salience)      # PURE — no IO, no CLI
```

Recall failed as a *cache*. The traversal math it stood on is intact, pure, and portable.
The open design question phase 2 answers: **what is the durable shape of a remembered
traversal, and does it live as another parquet beside `adjacency.parquet`.**

---

## 4 · THE MULTI-COPY PATHOLOGY — the thing that stopped this project

Graphy existed as several partial copies, none importable under the name they claimed. Every
improvement pass landed in one copy while the others kept their defects, so the same findings
got re-derived every few days by a cold model that could not see the earlier pass. Three weeks
of circle-builds is what that topology produces mechanically.

**This folder exists to end that.** One copy, one name, one place work lands.

Standing trap while the window is open: root `graphy/` inside the host codebase shadows
`graphy_os/graphy` on import from the repo root. That is BY DESIGN there until the host's copy
is deleted — do not "fix" it, and do not read it as a defect.

---

## 5 · THE COCHANGE BRAINS — half the record is gone, and what survives is a different set

The commit-wormhole mesh: file co-change pairs ranked by `lift · credibility · recency`, plus
PR⟂commit wormholes joining WHY to WHAT. Static analysis says what calls what; this says what
has been historically inseparable.

```
salience    = lift · credibility(support) · recency
lift        = P(X,Y) / (P(X)·P(Y))          statistical surprise
credibility = support / (support + 5)       empirical-Bayes shrinkage
recency     = exp(-age_days / 180)
```

**The five brains the README advertises are DELETED** — fastapi (34,935 edges, "the proven
pilot"), starlette, pydantic, sqlalchemy, host_codebase. The README's inventory table is a
lie by staleness; treat it as history.

**Ten survive, a different generation, 69,135 edges, ~32 MB:**

```bash
for d in <vault>/substrates/*/brain; do wc -l $d/*.metrics.jsonl; done
#   svelte 16,064 · sveltekit 12,538 · maplibre_gl 12,933 · pyo3_rs 10,513
#   vite 7,402 · leaflet 3,710 · serde_rs 2,963 · playwright 1,794
#   lucide_svelte 1,189 · googlemaps_loader 29
```

Rebuilding a brain is mechanical and needs only a git checkout:
`emit → cursor → wormholes → compact → query`.

---

## 6 · WHAT THE FASTAPI SUBSTRATE ACTUALLY IS

Two different artifacts wear the name. Keep them apart:

```
fastapi_graph/          the package AST — 499 nodes · 3,696 edges · 28 clusters   (before issue 12; §23: 507 · 3,715)
                        modules 48 · classes 110 · funcs 135 · methods 206      (§23: 48 · 113 · 135 · 211)
                        3 welds, all to starlette/pydantic (module-path canonicalization)
substrates/fastapi/     the cochange brain — 34,935 edges — DELETED, rebuildable
```

The AST graph is small. It is a fine demo corpus and a poor scale proof.

---

## 7 · THE HONEST NOVELTY LINE

Not checked against prior art. State it that way until someone does.

- **Not novel:** compiling a codebase into a queryable database. CodeQL, Glean, SCIP/Sourcegraph
  and Stack Graphs all do this, some at far larger scale.
- **Plausibly novel, unverified:** one addressable estate spanning code + deps + live DB schema
  + frontend + docs, joined on exact shared literals, with an admission gate that refuses fuzzy.
  The named systems are per-language and per-repo.
- **The differentiator regardless:** shipping the fan-out. The engine compiles a repo; the
  fan-out makes a cold agent competent in it. That is a product claim, not a research claim,
  and it does not need to be novel to be worth building.

---

## 8 · THE EDGE-TRUST MODEL — never relitigate this

Every edge is one of exactly three things:

```
structural   AST, built at ingest
wormhole     the same literal is a node-id in >= 2 graphs — free by construction
weld         ADMITTED: exact byte-identical literal, >= 2 rostered carriers, through the gate
```

Fuzzy is a threshold and an antipattern: similarity-only PARKS FOREVER and never graduates.
**No model ever decides an edge.** A weld is a suggestion the graph verifies, never an
invented edge. Speed was the only thing ever missing — do not re-litigate whether the mesh is
real, and never let a faster SUGGEST become an ADMIT.

---

## 9 · WHAT MUST NEVER TRAVEL PUBLIC

Tenant data isolation is architectural, not policy. The graphs built from the host's own
source, schema and data — `host_codebase` · `frontend` · `pg_schema` · `drm` · `sql_census`
· `call_census` · `customer_book` · `product_match` · `alpha*` · `session_memory` · the arm
docs, the board, the registries — are tenant material. They are useful locally as the largest
real test corpus and must not reach a public remote.

---

## 10 · THE FOLDER, AND WHAT LANDED (2026-09-05)

```
graphy/
  RECON.md                this file
  standalone_check.sh     the departure gate, re-homed — run it after every change
  engine/                 the package. GREEN here: install OK · host unreachable OK ·
                          graphy resolves to engine/graphy · 324 passed · prose scrub OK
  staging/tools/          590 files — the whole host tool folder, untriaged by design
  staging/skills/         17 skills — the fan-out manifest plus the walk/registration set
  staging/brains/         10 cochange meshes · 69,135 edges
  staging/containers/     121 graph packages · 812 MB · symlinks dereferenced
  staging/docs/           28 doctrine files + the two host scripts
```

**Proven from here, independent of the host:**

```bash
read_parquet('staging/containers/*_graph/adjacency.parquet')
#   901,116 edges · 478,431 nodes · 118 graphs · 89 ms
bash standalone_check.sh   #  GRAPHY_STANDALONE_OK
```

### THE FORK POINT IS NOW, AND IT HAS ONE RULE

`engine/` has diverged from the host's `graphy_os/` as of this copy. **This folder is the
only place engine work lands.** The host copy is a stale twin from here on — read it for
history, never edit it, never merge from it. The multi-copy pathology in §4 is exactly what
starts if that rule slips, and it is what cost this project three weeks once already.

### TWO DEFECTS FOUND BY MOVING — the move is what exposed them

1. **The departure gate had a hole, and it was in the gate's own suite.**
   `tests/test_adapters.py:54` read `HERE.parents[1] / "CLAUDE.md"` — a reach OUT of the
   staging dir into the host repo root. It passed for months only because the host was
   always there. The gate exists to prove the host is unreachable, and one of its tests
   depended on the host being reachable.
   **Fixed here:** a `doctrine.md` fixture landed in `lightning_corpus/` and the test now
   reads it. Zero host reaches remain (`grep -rn 'parents\[1\]' tests/`).

2. **`pyproject.toml` declares files that do not exist** — `readme = "README.md"` and
   `license = { file = "LICENSE" }`. Editable install tolerates it; a real build or a
   publish will not. The LICENSE is Apache 2.0 and is the operator's act to place.

### THE FIRST RUNG OF PHASE 2

Port the container (§2). It is a re-home, not a rewrite: `_DATA_ROOT` becomes
`tenant.data_home`, duckdb becomes a declared optional dependency, and the module gets the
tests it has never had. When it lands, the engine reads the estate at query speed instead of
parsing JSON — and only then is the traversal store (§3) worth designing, because a store
for remembered walks is meaningless until the walk itself is a query.

---

## 11 · THE FASTAPI TENANT — walked, partitioned, fanned out (2026-09-05)

The shard is `engine/tests/fixtures/fastapi_graph` (byte-identical to
`staging/containers/fastapi_graph`; `PROVENANCE.json` names the oracle commit `f218112d6`). The
tenant lives at `engine/tenants/fastapi/`; `rebuild.sh` runs init → shard → build → check and
prints `FASTAPI_TENANT_OK`.

### The lifecycle runs on this engine, from a cold scratch dir

```bash
cd engine && bash tenants/fastapi/rebuild.sh
#   INIT OK · BUILD OK: compiled 499 nodes / 664 edges · CHECK OK · FASTAPI_TENANT_OK     (before issue 12 — §23)
python3 -m graphy walk --tenant tenants/fastapi/tenant.json --tenant-id fastapi \
    --seed fastapi://func/fastapi.routing.get_request_handler \
    --target fastapi://func/fastapi.dependencies.utils.solve_dependencies
#   WALK PATH: hops=3 visited=229
```

**The store carries 664 of the shard's 3,696 edges.** The rest are `calls` edges whose target is a
text label (`dst_repr`, 2,551 of them) — unresolved by the producer, so not walkable. A walk over
the store is a walk over structure (`contains`, `imports`, resolved `inherits`) plus the few
resolved calls. `rebuild.sh` folds the label edges into a sidecar once
(`substrate/.labels.sqlite`; `walk.py compile-labels`), and `walk.py edges` queries the store for
resolved edges and the sidecar for labels, marking a label's unique-name match as a CANDIDATE.

```bash
cd engine && python3 tenants/fastapi/walk.py compile-labels
#   LABELS OK: 2551 label edge(s), 622 with a unique-name candidate
python3 tenants/fastapi/walk.py edges routing.get_request_handler | grep 'Response '
#   ~~calls~~> Response   candidate: fastapi://class/fastapi.openapi.models.Response
```

**A candidate can be wrong, and that is why it is a candidate.** The handler's `Response` is
Starlette's; the only node named `Response` in the shard is the OpenAPI model, so the unique-name
match points at the wrong class. No model decides an edge, and no name match does either — a
candidate is a suggestion the walk verifies (an `imports` edge into `starlette://` is the resolved
fact here).

### The four pillars, measured

```bash
cd engine && python3 tenants/fastapi/walk.py pillars
#   ROUTING        168   applications · routing · sse
#   DEPENDENCIES   135   dependencies · dependencies.models · dependencies.utils · param_functions · params · security.*
#   COMPAT         103   _compat · _compat.shared · _compat.v2 · datastructures · encoders · exception_handlers · exceptions · types · utils
#   OPENAPI         59   openapi · constants · docs · models · utils
#   EDGE            34   __init__ · __main__ · background · cli · concurrency · logger · middleware.* · requests · responses · staticfiles · templating · testclient · websockets
```

Module-level fan-in (who depends on me) and fan-out (whom I orchestrate), over
`imports+calls+inherits+decorates` between modules — the two rankings that produce the cut:

```text
fan-in   _compat 42 (from 10 modules) · exceptions 20 (12) · _compat.v2 18 · _compat.shared 13 ·
         types 13 (8) · dependencies.utils 12 · datastructures 11 · openapi.models 11 · utils 11
fan-out  routing 32 · dependencies.utils 32 · _compat 30 · openapi.utils 27 · applications 18 · security 15
```

Top inter-module edges: `dependencies.utils → _compat` 20 · `routing → dependencies.utils` 8 ·
`openapi.utils → _compat` 6 · `openapi.utils → dependencies.utils` 4 · `routing → exceptions` 5 ·
`applications → openapi.docs` 3. Starlette is reached from `routing` (30) and `applications` (18)
first; pydantic from `_compat.v2` (14), `encoders` (6), `openapi.models` (5).

**The ruling the walk supports:** the earlier public cut of this tenant (July, six arms: routing ·
applications · dependencies · params · security · openapi, by cluster node-weight) had no arm for
the cluster everything depends on. Fan-in crowns the pydantic boundary; fan-out crowns routing;
`applications` delegates to its router and both inherit Starlette; `params` are `FieldInfo` markers
read by `analyze_param`; every security scheme is a `Depends` callable. Six folds to four:
**ROUTING · DEPENDENCIES · COMPAT · OPENAPI.** The partition rule is the one curated input
(`tenants/fastapi/partition.json`, read by `walk.py:pillar_of` and by `graphy fanout --partition` since §22);
every weight above is recomputed on each run.

### Two engine gaps the tenant exposed

1. ~~**`graphy fanout` cannot cut a single-package tenant.**~~ Closed by §22 (issue 9,
   2026-09-05): `--depth N` and `--partition <json>` are the cut, the tenant's `partition.json` is
   the rule `walk.py pillars` and the fan-out share, and the receipt pins its sha.
2. ~~**This engine walks the FastAPI shard; it does not mint it.**~~ Closed by §13 (issue 2,
   2026-09-05): `graphy smash` mints the shard and its import ring, and `rebuild.sh` proves the
   minted root against the fixture before building on it.

### What landed

```text
CLAUDE.md                              the router for this repo — pillars · laws · folder · engine map · taps · tenants
engine/tenants/fastapi/FASTAPI.md      the tenant router — the four pillars, the edge, the taps, the joins out
engine/tenants/fastapi/arms/           ROUTING.md · DEPENDENCIES.md · COMPAT.md · OPENAPI.md — no numbers, only the tap
engine/tenants/fastapi/rebuild.sh      wipe → init → shard → build → check → FASTAPI_TENANT_OK
engine/tenants/fastapi/walk.py         pillars (the partition, recomputed) · edges (store + label sidecar) · compile-labels
engine/.gitignore                      tenants/*/substrate/ · tenants/*/tenant.json — rebuilt, never tracked
standalone_check.sh                    the prose scrub skips exactly those two rebuilt artifacts (the descriptor carries this
                                       machine's absolute paths, which carry its username)
```

---

## 12 · THE CONTINUITY LANE LANDED (2026-09-05 · issue 1)

Persistent memory the dumb way, re-homed into the engine with zero new dependencies.

```text
engine/graphy/lightning/        the port: 21 modules + extras/{storm_cooccurrence,stats} + pseudo_ast/{blocks,brace,svelte}
                                 doors kept: bare hunt · --containers · --cooccur/--with · --stats · --files-from
                                 doors cut:  --cross --reach (host import extractor; the walk's job here) · --oracle · --diffset ·
                                             --footprint · --sessions (a built index that rots — 41 sessions invisible, measured)
engine/graphy/session_tail.py   the transcript parser + renderer, pure; the pane ledger and identity stamping cut
engine/graphy/reseed.py         capture (PreCompact · SessionEnd) · inject (SessionStart startup|clear|compact) · render
.claude/settings.json           the three hooks, tracked; PYTHONPATH=engine, no venv, fail-open
.claude/recovery/               reseed_tail.md · sessions/NNNNN__<utc>__<session8>.md · reseed_diag.log — gitignored
```

### Proven on this box, against this session's own transcript

```bash
cd engine && printf '{"session_id":"<sid>","transcript_path":"<jsonl>","hook_event_name":"SessionEnd","reason":"clear"}' \
    | PYTHONPATH=. python3 -m graphy.reseed capture
#   tail 10 exchange(s) -> .claude/recovery/reseed_tail.md · archived sessions/00001__20260905T185038Z__643b3cc3.md
printf '{"session_id":"new","source":"clear"}' | PYTHONPATH=. python3 -m graphy.reseed inject --inline-chars 2500
#   # SESSION RE-SEED (clear) · Read <tail> · 22,998 bytes · captured 0 min ago · newest 2,500 chars inline
PYTHONPATH=. python3 -m graphy.lightning.bloodhound pillars --with fastapi
#   1 file holds BOTH within ±10 tokens · 5 clusters, the exchange that ruled the four pillars first
```

The hook firing itself (Claude Code calling `capture` on /clear) is proven the first time this
repo is cleared; the mechanism under it is proven above.

### The coupling that can move, and its tripwire

`session_tail` parses Claude Code's transcript jsonl. The row grammar observed on 2.1.261 is
frozen in `tests/fixtures/transcript/session.jsonl` (`PROVENANCE.json` lists the row types). Two
floor tests fail RED and name the cause when the format drifts: undecodable lines, and rows whose
content shape the discriminator no longer recognizes. A hollow tail is refused, never injected.

### Two measured facts a cold read will get wrong

- Inside a Claude Code shell, `rg` is the harness's own shell function, not a binary; `shutil.which`
  sees only PATH. This box now carries the system package (`ripgrep 14.1.0`, PCRE2 10.42, lookbehind
  smoke-tested), so lightning resolves `/usr/bin/rg` and answers the fixture corpus in ~10 ms and
  bloodhound the archive in ~50 ms. Without it the Python fallback is correct and slower;
  `GRAPHY_RG=<path>` names any other binary, and PCRE2 is required for the fast path.
- The archive lives under `CLAUDE_PROJECT_DIR/.claude/recovery/sessions`, resolved at import by
  `lightning/archive.py`, never by a repo-relative `parents[3]`.

---

## 13 · THE MINTING LANE LANDED (2026-09-05 · issue 2)

`graphy smash` mints a package into a `<slug>_graph` shard with the python_ast producer, then
follows the shard's resolved `imports` edges through a site-packages until the ring closes: every
dependency found there is minted beside the root, the standard library is skipped by name, and
what is not installed is reported in `ring.json`, never guessed. Engine gap 2 of §11 is closed.

```text
engine/graphy/smash.py            smash · mint · parity · locate · distributions · corpus_digest · git_head
engine/graphy/cli.py              graphy smash --package --site-packages --out [--corpus] [--no-ring] [--parity]
engine/graphy/adapters/python_ast.py   walk_files · is_package_dir · a .py file is a one-module corpus
engine/tenants/fastapi/rebuild.sh GRAPHY_CORPUS_SITE_PACKAGES=<dir> mints the ring; unset places the fixture
engine/tests/test_smash.py        a synthetic site-packages; the FastAPI parity proof is opt-in by that env var
staging/corpora/                  gitignored: venv/ with fastapi==0.139.0, fastapi/ at 0.139.2 (kept for history)
```

### The fixture's provenance, re-derived

The vendored shard's `oracle_commit` (`f218112d6`) is the **host repo's** commit at mint time
(`git -C ../the host codebase log -1 f218112d6` → 2026-07-16), not a FastAPI commit — GitHub has no
such SHA in `fastapi/fastapi`. The host's checkout no longer exists on this box. The fixture's
`file` paths (`fastapi/routing.py`) and the absent `in_namespace` key say the host minted in pip
mode over an installed FastAPI; the host venv holds `fastapi 0.139.0`, and the producer restored to
its oracle-commit semantics reproduces the fixture from it record for record. The reproducible
corpus is the wheel, not a checkout:

```bash
cd staging/corpora && python3 -m venv venv && venv/bin/pip install fastapi==0.139.0
diff -rq venv/lib/python3.12/site-packages/fastapi ../../../the host codebase/.venv/lib/python3.12/site-packages/fastapi -x __pycache__
#   (no output — identical)
cd ../../engine && GRAPHY_CORPUS_SITE_PACKAGES=$PWD/../staging/corpora/venv/lib/python3.12/site-packages \
    python3 -m pytest -q tests/test_smash.py -k fastapi
#   1 passed — 499 nodes / 3696 edges identical to tests/fixtures/fastapi_graph     (before issue 12; §23: 507 / 3715)
```

Three things the engine's producer had lost against the oracle-commit producer, each now a floor
test in `tests/test_adapters.py`:

- **Docstrings.** The host's 2026-08-14 commit "refactor: delete every docstring in the codebase"
  sed-scrubbed `ast.get_docstring(stmt)` to `None` inside the producer itself
  (`git -C ../the host codebase log -S get_docstring -- host_sdk/tools/repo_substrate/ingest.py`).
  The fixture carries 88 docstrings, so the engine could never have reproduced it. Restored.
- **`file` is relative to the corpus's parent** (`fastapi/routing.py`), not to the corpus.
- **A package corpus has no "local packages".** `import types` inside a package that ships its own
  `types.py` is the standard library (`types://module/types`), as the fixture says; only a repo root
  (no `__init__.py`) prefixes its top-level directories. The engine's producer had been resolving it
  to `fastapi.types` — a wrong edge the fixture would have caught, and now does.

### The ring, measured

```bash
cd engine && GRAPHY_CORPUS_SITE_PACKAGES=$PWD/../staging/corpora/venv/lib/python3.12/site-packages bash tenants/fastapi/rebuild.sh
#   MINT OK ×10 · RING: 10 shard(s) · stdlib skipped 72 · unresolved 30 · PARITY OK · BUILD OK: compiled 4688 nodes / 6746 edges
#   CHECK OK · LABELS OK · FASTAPI_TENANT_OK      (1.8 s wall, the mint itself 1.0 s)
```

Counts as minted on 2026-09-05 before issue 12; the producer's walk-out changed every shard that
guards a def with a module-level `if`/`try` — the re-minted table is in §23.

| shard | version | nodes | edges | corpus |
|---|---|---|---|---|
| fastapi | 0.139.0 | 499 | 3,696 | package |
| pydantic | 2.13.5 | 2,021 | 12,624 | package |
| anyio | 4.15.1 | 1,210 | 5,656 | package |
| starlette | 1.6.0 | 619 | 2,931 | package |
| pydantic_core | 2.46.5 | 189 | 469 | package (the .so is invisible; its `.pyi` is not walked) |
| idna | 3.19 | 58 | 395 | package |
| annotated_types | 0.8.0 | 37 | 262 | package |
| typing_extensions | 4.16.0 | 29 | 102 | one file |
| typing_inspection | 0.4.4 | 19 | 134 | package |
| annotated_doc | 0.0.5 | 7 | 8 | package |

**The store: 499 nodes / 664 edges with the fixture alone → 4,688 / 6,746 with the ring.** The
extra edges are the wormholes: an `imports` edge whose target literal is now a node id in a sibling
shard. Three walks that stop at the boundary without the ring and cross with it:

```bash
T=tenants/fastapi
python3 -m graphy walk --tenant $T/tenant.json --tenant-id fastapi --seed fastapi://module/fastapi.routing --target starlette://class/starlette.routing.Router
#   WALK PATH: hops=2  fastapi.routing -> starlette://module/starlette.routing -> starlette://class/starlette.routing.Router
python3 -m graphy walk --tenant $T/tenant.json --tenant-id fastapi --seed fastapi://module/fastapi.params --target pydantic://class/pydantic.fields.FieldInfo
#   WALK PATH: hops=2  fastapi.params -> pydantic://module/pydantic.fields -> pydantic://class/pydantic.fields.FieldInfo
python3 -m graphy walk --tenant $T/tenant.json --tenant-id fastapi --seed fastapi://module/fastapi.concurrency --target anyio://module/anyio
#   WALK PATH: hops=1
```

**The seam, previewed (issue 3 measures it properly).** Of FastAPI's 3,696 edges, 1,145 carry a
resolved `dst`; 413 of those leave the package; 198 are now a node in the ring, and **every** target
in a minted scheme resolves (starlette 118/118 · pydantic 49/49 · annotated_doc 13/13). The other
215 are the standard library (typing 81 · collections 45 · dataclasses 11 · contextlib 10 …), which
is not minted by design. Ring-wide, 8,099 of 10,704 `dst` edges land on a node. The `imports`
layer is not thin; whether the 2,551 `calls` labels cross is issue 3's question.

```bash
cd engine && python3 - <<'PY'
import json; from pathlib import Path
S = Path("tenants/fastapi/substrate"); ring = json.load(open(S/"ring.json"))
nodes = {k for m in ring["minted"].values() for k in json.load(open(Path(m["shard"])/"nodes.json"))}
fe = json.load(open(S/"fastapi_graph/edges.json")); ext = [e for e in fe if "dst" in e and not e["dst"].startswith("fastapi://")]
print(len(fe), sum("dst" in e for e in fe), len(ext), sum(e["dst"] in nodes for e in ext))
PY
#   3696 1145 413 198
```

**Unresolved: 30, and the list is honest.** What pip did not install — optional extras and test
dependencies imported under `try`/`TYPE_CHECKING` (`httpx`, `jinja2`, `pytest`, `trio`, `uvloop`,
`email_validator`, `python_multipart` …) — plus three names that are stdlib on 3.13+ and absent from
3.12's `sys.stdlib_module_names` (`_interpqueues`, `_interpreters`, `annotationlib`). `sniffio` is
imported by anyio under `try` and no longer a pinned dependency. Reported in `ring.json`, never
guessed at.

### A producer blind spot the ring exposed — closed by issue 12 (§23)

`typing_extensions.py` is 4,422 lines and mints 29 nodes. The producer walks `tree.body` and
descends into classes and functions only; a `def` or `class` under a module-level `if`/`try` is
invisible. Measured: 15 top-level defs, 236 under `if`/`try`. Parity with the fixture requires this
behaviour today (the fixture was minted with it), so the walk-out is a board item, not a quiet fix.

```bash
python3 - <<'PY'
import ast; src = open("../staging/corpora/venv/lib/python3.12/site-packages/typing_extensions.py").read(); t = ast.parse(src)
D = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
print(sum(isinstance(s, D) for s in t.body), sum(isinstance(n, D) for s in t.body if isinstance(s, (ast.If, ast.Try)) for n in ast.walk(s)))
PY
#   15 236
```

---

## 14 · THE SEAM MEASURED, AND THE RESOLVER (2026-09-05 · issue 3)

`graphy converge` counts, per ordered shard pair, the edges of one shard whose endpoint literal is
a node id in the other — wormholes, free by construction. `--resolve` turns the producer's text
labels (`calls` · `inherits` · `decorates`) into edges through the scope that binds the name, and
writes them to `<shard>/wormhole_edges.json`, which the loader admits beside `edges.json` and the
store's freshness digest covers. The producer's output stays verbatim; parity is untouched.

```text
engine/graphy/converge.py           Ring · converge · resolve — local · import · reexport · self · super; the rest stays text
engine/graphy/native_json_graph_ir.py   load_graph_ir reads wormhole_edges.json when present (WORMHOLE_SIDECAR)
engine/graphy/cli.py                graphy converge --tenant --tenant-id [--resolve]
engine/tenants/fastapi/rebuild.sh   converge --resolve runs between init and build, on both paths
engine/tenants/fastapi/walk.py      compile-labels skips what the sidecar resolved; edges prints the qualified literal for the rest
engine/tests/test_converge.py       a synthetic ring where every asserted resolution is one a rule reaches
```

### The resolution rules, in the order they fire

1. `self.x` / `cls.x` → the containing class's `x`. `super().x` → the first resolved base's `x`
   (`inherits` labels resolve first so `super` has a base to stand on); a bare `super()` is the builtin.
2. `name` / `Name.attr` → a definition in the same module (`<module>.<name>`).
3. `name` → the module's own `imports` edges: `from m import name [as alias]` → `m.name`;
   `import m.n as alias` → `m.n`; `import m` → the label's own dotted path. When the qualified
   literal is no node but its longest module prefix is a module the ring holds, follow that
   module's imports for the next segment — a re-export, one hop at a time, six deep at most.
   (`httpcore.ConnectionPool` through `import httpcore` lands on
   `httpcore._sync.connection_pool.ConnectionPool` this way; added under issue 17, where the httpx
   ring showed the gap: httpx → httpcore went from 6 wormhole edges to 20.)
4. A bare name in `builtins` is the builtin. Everything else stays text.

A qualified literal that lands on no node is kept with its reason: `stdlib` (never minted by
design), `missing` (the scheme is minted but carries no such node — a def under `if`/`try`, issue 12,
or a `.so`/`.pyi` symbol), `unminted` (the ring never reached that package).

### The done check

```bash
cd engine && python3 tenants/fastapi/walk.py edges routing.get_request_handler | grep -i 'response'
#   --calls--> starlette://class/starlette.responses.Response          ← through `from starlette.responses import Response` in routing
#   --calls--> starlette://class/starlette.responses.StreamingResponse
#   --calls--> fastapi://class/fastapi.exceptions.ResponseValidationError
#   ~~calls~~> actual_response_class                                    ← a local: no rule reaches it, so it stays text
```

The name-match candidate that pointed at `fastapi.openapi.models.Response` (§11) is gone from the
sidecar: the label is an edge now, and the edge is Starlette's.

### The seam, measured on the ten-shard ring

```bash
cd engine && GRAPHY_CORPUS_SITE_PACKAGES=$PWD/../staging/corpora/venv/lib/python3.12/site-packages bash tenants/fastapi/rebuild.sh
python3 -m graphy converge --tenant tenants/fastapi/tenant.json --tenant-id fastapi
```

| | before `--resolve` | after |
|---|---|---|
| wormhole edges across the ring | 532 over 52 nodes | 1,725 over 206 nodes |
| store (10 shards) | 4,688 nodes / 6,746 edges | 4,688 / 10,789 |
| fastapi → starlette | 118 (imports) | 217 over 74 nodes (imports 118 · calls 84 · inherits 15) |
| fastapi → pydantic | 49 | 62 (imports 49 · calls 9 · inherits 3 · decorates 1) |
| fastapi → annotated_doc | 13 | 780 (`Doc(...)` 767 times, through the re-export) |

**fastapi's 2,596 labels → 1,529 edges** (re-export 834 · import 316 · local 286 · self 61 ·
super 32; 888 of them cross a shard). Left as text: builtin 338 · stdlib 193 (`typing.cast`,
`inspect.isclass` … qualified, never minted) · missing 68 · unminted 1 · attribute chains on
locals 472. **pydantic: 8,131 → 2,588. starlette: 1,773 → 407.** The 0.2 s the resolve takes is
the whole cost; the 1,023 fastapi labels still text are in `.labels.sqlite` with their qualified
literal where one exists (259) and a bare-name candidate only for the 38 nobody could qualify.

**The ruling:** the seam is not thin. At the `imports` layer every literal into a minted scheme
resolves (§13); at the `calls` layer the module's own scope binds three of every five labels
without a model or a name match. What remains is locals and attribute chains — a type question,
which no structural rule answers and this engine does not guess at.

---

## 15 · THE CONTAINER CROSSED (2026-09-05 · issue 4)

Beside every shard: `adjacency.parquet` (one row per edge, label-only edges included with a
NULL `dst` and their `dst_repr`), `nodes.parquet` (one row per node plus the three forms a walk
matches a literal against — body, last, kind — derived from the id alone), and `container.json`,
a receipt pinning the shard input digest the parquets were built from. DuckDB is the only
dependency and it is optional: `pip install 'graphyos[estate]'`. Without it `graphy build` prints
`CONTAINER SKIPPED` and the JSON path is the reader, as before; `estate` refuses with the install
line. §2's gap — `dependencies = []`, no parquet, the estate host-side only — is closed.

```text
engine/graphy/container.py     emit · verify (fresh|stale|absent by digest, never mtime) · estate (views adj, nodes with a corpus column)
engine/graphy/cli.py           build emits when duckdb is present · check reports freshness, RED when stale · container [--emit] · estate --sql
engine/pyproject.toml          [project.optional-dependencies] estate = ["duckdb>=1.0"]
engine/tests/test_container.py the no-duckdb path (runs in the gate) and the duckdb path (skips loudly without it)
staging/corpora/venv-estate/   gitignored: duckdb + pytest, the interpreter that runs the engine WITH the extra
```

The column schema is the host's (`adjacency_container.py`, RECON §2), so the estate under
`staging/containers/*_graph` and the engine's union into one view by name.

### Measured on the ten-shard ring

```bash
cd engine && E=../staging/corpora/venv-estate/bin/python
PYTHON=$E GRAPHY_CORPUS_SITE_PACKAGES=$PWD/../staging/corpora/venv/lib/python3.12/site-packages bash tenants/fastapi/rebuild.sh
#   CONTAINER OK: 10 shard(s) · 4688 node row(s) · 31925 edge row(s) · 0.98 MB parquet · 0.57 s beside the shards
#   CHECK OK: … container fresh for 10/10 shard(s)
du -ch tenants/fastapi/substrate/*_graph/*.parquet | tail -1            # 992K   (the JSON: 7.2M)
PYTHONPATH=. $E -m graphy estate --tenant tenants/fastapi/tenant.json --tenant-id fastapi
#   ESTATE OK: 10 row(s) over 10 shard(s) in 2.2 ms
PYTHONPATH=. $E -m graphy estate --tenant tenants/fastapi/tenant.json --tenant-id fastapi --sql \
  "SELECT a.corpus, n.corpus, count(*) FROM adj a JOIN nodes n ON a.dst = n.id WHERE a.corpus <> n.corpus GROUP BY 1, 2 ORDER BY 3 DESC"
#   fastapi_graph → annotated_doc_graph 780 · pydantic_graph → pydantic_core_graph 344 · fastapi_graph → starlette_graph 217 …   8.2 ms
PYTHONPATH=. $E -m graphy estate --tenant tenants/fastapi/tenant.json --tenant-id fastapi --sql \
  "SELECT corpus, count(*) FROM adj WHERE dst = 'starlette://class/starlette.responses.Response' AND edge_type = 'calls' GROUP BY corpus"
#   fastapi_graph 3 · starlette_graph 1          1.8 ms — the §14 resolution, asked of the whole estate in SQL
```

A resolved label rides twice in `adj`: the producer's row (`dst` NULL, `dst_repr` the label) and
the resolver's (`dst` set, `attrs` carrying `via` and `label`). `WHERE dst IS NOT NULL` is the
walkable estate; `WHERE dst IS NULL` is what stayed text (fastapi 2,551 · pydantic 7,687).

### Two things this lane found, both re-derivable

- **A per-row insert costs 28 s; a bulk load costs 0.6 s.** DuckDB's `executemany` over 30k rows
  took 28.56 s for the ring. The rows now go through one newline-delimited JSON file that
  `read_json` bulk-loads: 0.57 s. Same parquet.
- **The ring mints what is installed — so the corpus venv must hold only the corpus.** With
  `pytest` and `duckdb` installed into the pinned corpus venv for testing, the ring grew from 10
  shards to 17 (`_pytest`, `pygments`, `packaging`, `pluggy`, `iniconfig`, `pytest`, `py`): anyio and
  pydantic import pytest under `try`, and `smash` honestly followed them. The corpus venv was
  rebuilt pure (`rm -rf venv && python3 -m venv venv && venv/bin/pip install fastapi==0.139.0`) and
  the engine-with-extras interpreter lives in its own venv. `ring.json` is the tripwire: the
  `minted` list is the ring, and anything in it you did not mean is a corpus that is not pure.

---

## 16 · THE BOLT-ON, PROVEN IN PRODUCTION (2026-09-05 · issue 17)

`graphy eat --repo <abs> --site-packages <abs>` is the product in one verb: find the repo's
importable package (or take `--package`), mint it and its import ring into `<repo>/.graphy/`,
declare the tenant with the repo's git HEAD as the cursor, derive the scheme index from the
ring receipt, resolve the labels, compile the store, emit the parquet, audit. `quickstart.sh`
wraps it for a stranger: clone, install the repo's dependencies into a venv of their own, eat,
one estate query, one walk, the done token with the time. The README at the repo root is those
five commands with what they print; every line of it ran here.

```text
engine/graphy/cli.py     graphy eat — orchestrates smash · init · converge --resolve · build · check; <repo>/.graphy/.gitignore is `*`
quickstart.sh            bash quickstart.sh <git-url-or-path> [package] → GRAPHY_QUICKSTART_OK: <pkg> eaten in <s>s
README.md                the public face; engine/README.md is the packaged one (the PyPI install line is aspirational until published)
.venv/                   the project's own interpreter: `pip install -e 'engine[estate]'` — graphyos + duckdb, no pytest, nothing else
staging/quickstart/      gitignored: the eaten clones
```

### The run

```bash
rm -rf staging/quickstart && time bash quickstart.sh https://github.com/encode/httpx.git
#   MINT OK ×7 (httpx 538 nodes / 2548 edges · httpcore 539 / 2251 · anyio 1210 / 5656 · h11 138 / 658 · idna · certifi · typing_extensions)
#   RING: 7 shard(s) · stdlib skipped 62 · unresolved brotli, click, h2, pytest, rich, socksio, trio, … (extras pip did not install)
#   BUILD OK: compiled 2522 nodes / 5216 edges · CONTAINER OK: 7 shard(s) · 13655 edge row(s) · 0.45 MB parquet · 0.29 s
#   CHECK OK: … container fresh for 7/7 shard(s)
#   ESTATE OK: 9 row(s) over 7 shard(s) in 7.1 ms
#   WALK PATH: hops=2  httpx://module/httpx -> httpx://module/httpx._config -> certifi://module/certifi
#   GRAPHY_QUICKSTART_OK: httpx eaten in 5.9s          ← cold: the clone and pip install of the dependencies included
bash quickstart.sh https://github.com/encode/httpx.git   # again, clone and venv in place
#   GRAPHY_QUICKSTART_OK: httpx eaten in 3.0s          ← warm: eat + estate + walk
```

| the httpx ring, after resolve | edges | of which calls |
|---|---|---|
| httpx → httpcore | 20 over 9 nodes | 14 |
| httpcore → anyio | 16 over 10 nodes | 14 |
| httpcore → h11 | 10 over 5 nodes | 8 |

Before the bare-import re-export follow (§14 rule 3) those rows read 6 · 3 · 2, all `imports`:
`httpcore.ConnectionPool(...)` through `import httpcore` was classified *missing* because no node
carries `httpcore.ConnectionPool`; the package's `__init__` binds it. 95 wormhole edges over 29
nodes now, from 57 over 7.

### The done token, ruled

The done token for a lane is the production run — `quickstart.sh` on a real repo, or the tenant's
`rebuild.sh` — timed, in this file. The pytest floor stays as the departure gate's substance and
is not the proof of anything; no test was added under this issue, and none will be added where a
production run can carry the claim instead. The interpreter that runs the product is `.venv/`,
isolated from every development environment on this box; the pinned corpus venv holds the corpus
and nothing else (§15).

### What is not there, by name

The MCP server (#7), the shard index (#8), the shell and its gate (#13), the pillar door (#14).
The README says so in one line rather than implying otherwise. The traversal store landed under
#5 (§17).

## 17 · THE TRAVERSAL STORE LANDED (2026-09-05 · issue 5)

Every `graphy walk` lands its rows — seed · hop · node · via_src · relation · direction · carrier ·
generation — as one parquet per (generation, seed) under `<data_home>/traversals/<generation>/`,
with a receipt beside it (seed, target, hops, rows, `exhausted`, `reads`). DuckDB is the only
dependency and it is optional: without it the walk runs live and prints `TRAVERSAL SKIPPED`.
The rows are the walk's own output, beside the container and never inside the shard; a query
still never writes the shard. `graphy eat` and the tenant's `rebuild.sh` carry the traversals
across a wipe, because a stored walk is what the next generation diffs against.

```text
engine/graphy/traversal.py   walk · store_walk · load_walk · stored · replay; Counting counts the store reads
engine/graphy/cli.py         graphy walk (through the store; --no-store) · graphy traversals [--replay]
engine/graphy/container.py   estate() gains a third view, walks(seed, hop, node, via_src, relation, direction, carrier, generation)
```

### The three done checks, run on this box

**A second identical walk answers from the store without one read** — the FastAPI tenant:

```bash
cd engine && D=tenants/fastapi/tenant.json
../.venv/bin/graphy walk --tenant $D --tenant-id fastapi --seed fastapi://module/fastapi.routing --target starlette://class/starlette.routing.Router
#   WALK PATH: hops=2 visited=313 …      TRAVERSAL: source=live reads=12 stored=…/traversals/2dae16bb79a9f6f9/4d943616d2c4f2d4.parquet
../.venv/bin/graphy walk … (the same line)
#   WALK PATH: hops=2 visited=313 …      TRAVERSAL: source=store reads=0
../.venv/bin/graphy walk … --target pydantic_core://module/pydantic_core        # a different target the stored frontier already covers
#   WALK PATH: hops=2 …                  TRAVERSAL: source=store reads=0
```

**A walk from a new seed reuses a stored frontier it crosses, measured in store reads:**

```bash
T=anyio://class/anyio._core._synchronization.Semaphore
../.venv/bin/graphy walk … --seed fastapi://module/fastapi.routing --target $T --no-store
#   WALK PATH: hops=3 visited=1087 steps=fastapi.routing -> types://module/types -> anyio._core._synchronization -> Semaphore
#   TRAVERSAL: source=live reads=154
../.venv/bin/graphy walk … --seed types://module/types --target $T             # store the frontier of the node the path crosses
#   TRAVERSAL: source=live reads=3 stored=…
../.venv/bin/graphy walk … --seed fastapi://module/fastapi.routing --target $T
#   WALK PATH: hops=3 visited=369 (the same steps)
#   TRAVERSAL: source=spliced:types://module/types reads=29
```

| the walk fastapi.routing → Semaphore | store reads | visited |
|---|---|---|
| live | 154 | 1087 |
| spliced through the stored walk from `types` | 29 | 369 |

`reads` counts frontier expansions, and a level stops the moment it hits the target, so the count
depends on the store's row order: the same walk read 249 before the tenant was re-minted and 154
after, on an identical generation. The ratio is the measurement; the absolute number is not stable
across a recompile and is not claimed to be.

A spliced walk lands too: its rows are partial past the splice and it is never marked `exhausted`,
but every row is a true path, and the gate (§18) reads a stored walk as the citation.

**A walk stored under generation N, re-run under N+1, names the broken hops** — httpx, a real
upstream move, from the head the quickstart clones to tag 0.23.0:

```bash
bash quickstart.sh staging/quickstart/httpx                                    # head b5addb6: 7 shards, generation bae62afa213c
D=staging/quickstart/httpx/.graphy/tenant.json
.venv/bin/graphy walk --tenant $D --tenant-id httpx --seed httpx://module/httpx._client --target httpcore://class/httpcore._sync.connection_pool.ConnectionPool
#   WALK PATH: hops=3 visited=464 steps=httpx._client -> ssl://module/ssl -> httpcore._sync.connection_pool -> ConnectionPool   TRAVERSAL: source=live reads=86 stored=…
( cd staging/quickstart/httpx && git fetch --depth 1 origin tag 0.23.0 && git checkout 0.23.0 )
bash quickstart.sh staging/quickstart/httpx                                    # 0.23.0: 9 shards, generation 981a7f0801ef; the traversals survive the re-eat
.venv/bin/graphy traversals --tenant $D --tenant-id httpx --replay --limit 6   # 0.15 s
#   BROKEN bae62afa213c -> 981a7f0801ef  httpx://module/httpx -> certifi://module/certifi  hops_checked=184 broken=42 on_path=0
#       hop 1: httpx://module/httpx -[imports]-> httpx://module/httpx._transports  (edge died)
#   BROKEN bae62afa213c -> 981a7f0801ef  httpx://module/httpx._client -> …ConnectionPool  hops_checked=463 broken=99 on_path=1
#       hop 1: httpx://module/httpx._client -[imports]-> ssl://module/ssl  (edge died)
#       hop 1: httpx://module/httpx._client -[contains]-> httpx://func/httpx._client._same_origin  (node died)
#   TRAVERSALS REPLAY BROKEN: 2 past walk(s), 141 broken hop(s) against live generation 981a7f0801ef      exit 1
```

`why` is one of `seed died` · `src died` · `node died` · `edge died`, checked against the live
store's membership and neighbours. `on_path` counts the broken hops on the stored path itself:
the walk into `ConnectionPool` went through `httpx._client → ssl`, and 0.23.0's `_client` does
not import `ssl`, so that path no longer holds. The exit code is the verdict: 1 when any stored
walk broke.

Returning the clone to head did **not** replay clean, and the store was right: `pip install`
of 0.23.0 had downgraded anyio in the clone's venv, and the head re-install left it there, so
the ring at head is a third generation (`7dc96ed8bd62`). Against it every stored path still
holds (`on_path=0` for all three walks); the 50 broken hops are anyio nodes and edges in the
frontier past the path — `anyio._lazyimport`, `anyio.to_interpreter` died with the downgrade.
The ring diffs against the venv, not the repo alone; `ring.json` names what was minted.

```bash
( cd staging/quickstart/httpx && git checkout b5addb6 ) && bash quickstart.sh staging/quickstart/httpx
.venv/bin/graphy traversals --tenant staging/quickstart/httpx/.graphy/tenant.json --tenant-id httpx --replay --limit 3
#   BROKEN bae62afa213c -> 7dc96ed8bd62  httpx://module/httpx._client -> …ConnectionPool  hops_checked=463 broken=29 on_path=0
#       hop 2: typing://module/typing -[imports]-> anyio://module/anyio.to_interpreter  (node died)
#   TRAVERSALS REPLAY BROKEN: 3 past walk(s), 50 broken hop(s) against live generation 7dc96ed8bd62
```

The FastAPI tenant's `rebuild.sh` keeps its traversals across the wipe: after a full re-mint the
three stored walks list under the same generation `2dae16bb79a9` and the repeat walk answers
`source=store reads=0`. `rebuild.sh` runs on `python3` unless `PYTHON` names the project venv, so
it emits no parquet; `../.venv/bin/graphy container --tenant tenants/fastapi/tenant.json --tenant-id fastapi --emit` restores the estate.

### Not an energy column

The issue named energy and generation. Generation is a column; energy is not: a path walk
carries no decay, and a number invented for the row would be a lie. `spread` (spreading
activation with decay) is the door that owns energy, and it does not land rows yet.

## 18 · THE SHELL LANDED (2026-09-05 · issue 13)

`engine/graphy/shell/` ships with the package: three hooks and one gate, stdlib Python and bash,
the contract exit codes and stdout. `graphy shell install --repo <abs>` writes them into an eaten
repo with every path declared — the installing interpreter's absolute path baked into
`<repo>/.graphy/hooks/*.sh` (machine-local, ignored like everything under `.graphy/`), the three
events merged into `<repo>/.claude/settings.json` (portable: it names only `$CLAUDE_PROJECT_DIR`),
`<repo>/GRAPHY.md` (the router, this tenant's taps filled in), and `.claude/recovery/.gitignore`
so the operator's sessions never reach the repo. Claude Code sends each hook its JSON on stdin and
the scripts take it as-is; the two-argument forms build the same JSON for a harness that has none.

```text
engine/graphy/shell/gate.py           python3 -m graphy.shell.gate — PreToolUse on Edit|Write|MultiEdit; 79 lines with its docstring
engine/graphy/shell/install.py        graphy shell install --repo <abs> [--python <abs>]
engine/graphy/shell/claude/           settings.json (the four events) · GRAPHY.md (the router template)
engine/graphy/shell/hooks/            session_start.sh · session_end.sh · before_edit.sh — the entry points, {{python}} and {{repo}} filled at install
engine/graphy/shell/README.md         the stranger's ten commands, and the by-hand proof
```

### The gate's rule

An edit to a symbol the store knows — a `def` or `class` in the replaced text, matched to
`<pkg>://func|class|method/<module>.<name>` under the file's module — is blocked (exit 2) unless a
walk stored under the live generation *started at* that symbol or *passed through it on its path*
(`on_path` in the traversal rows, §17). A node merely visited in a frontier is not a citation: the
agent saw the path, not the frontier. The block prints the exact walk to run; the stored walk is
the bypass. The gate opens (exit 0) when the repo is not eaten, duckdb is absent, or the file is not
in the store — it confines an agent to a substrate, never to nothing.

### Proven on a fresh clone, from the README's commands

```bash
git clone --depth 1 https://github.com/encode/httpx.git staging/quickstart/httpx-shell && cd staging/quickstart/httpx-shell
python3 -m venv .graphy/venv && .graphy/venv/bin/pip install -e . -e '/abs/graphy/engine[estate]'
SP="$(.graphy/venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
.graphy/venv/bin/graphy eat --repo "$PWD" --site-packages "$SP"          # EAT OK: httpx + 6 ring shard(s)
.graphy/venv/bin/graphy shell install --repo "$PWD"                      # SHELL OK: hooks for tenant httpx … run on …/.graphy/venv/bin/python3
echo 'Read GRAPHY.md first.' >> CLAUDE.md                                # 8.6 s from the clone to here, the pip install included
# the edit loop the gate lives on (§53): after an edit, `graphy eat .` again splices the previous shards — parses the one
# file whose bytes moved, skips the pip install — re-derive: `time .graphy/venv/bin/graphy eat .` twice, the second line's EAT OK

printf 'def _same_origin(' | .graphy/hooks/before_edit.sh httpx/_client.py
#   GATE BLOCKED: httpx/_client.py edits 1 symbol(s) the store knows with no walk cited under generation bae62afa213c. Walk first, read the path, then edit:
#     …/.graphy/venv/bin/python3 -m graphy walk --tenant …/.graphy/tenant.json --tenant-id httpx --seed httpx://func/httpx._client._same_origin --target httpx://module/httpx
#   exit 2
<that walk>
#   WALK PATH: hops=2 visited=38 steps=httpx://func/httpx._client._same_origin -> httpx://module/httpx._client -> httpx://module/httpx
#   TRAVERSAL: source=live reads=4 stored=…/traversals/bae62afa213c3031/ab7a1636c631ec32.parquet
printf 'def _same_origin(' | .graphy/hooks/before_edit.sh httpx/_client.py     # exit 0
# as Claude Code sends it:
printf '{"tool_name":"Write","cwd":"…","tool_input":{"file_path":"…/README.md","content":"x"}}' | .graphy/hooks/before_edit.sh              # exit 0 — not in the store
printf '{"tool_name":"Edit","cwd":"…","tool_input":{"file_path":"…/httpx/_client.py","old_string":"class Client(BaseClient):",…}}' | .graphy/hooks/before_edit.sh
#   GATE BLOCKED … --seed httpx://class/httpx._client.Client …   exit 2 — the same module, visited by the walk above, not on its path
.graphy/hooks/session_end.sh <transcript.jsonl> <session-id>
#   [graphy.reseed] tail 4 exchange(s) -> …/.claude/recovery/reseed_tail.md · archived …/sessions/00001__…__d655c636.md
.graphy/hooks/session_start.sh now | head -3
#   # SESSION RE-SEED (startup) …
```

No test was added: the run above is the proof, and the issue's "floor test each way" is the two
`before_edit.sh` lines. Two things the run found, both fixed in place: a heredoc fed to `python -`
steals the pipe that carried the edit text (the two-argument form now builds its JSON with `-c`),
and a hook that reads stdin hangs a harness that leaves it open — `session_start.sh now` reads
none. The gate is 79 lines against the issue's 60; the docstring and the four open conditions are
the difference, and neither is padding.

## 19 · THE DOORS OPENED (2026-09-05 · issue 6)

Three doors over the compiled store, each one verb from `engine/`, each a bounded walk answered
through `neighbours` · `membership` · `record` and nothing else — a door never opens a shard. A
symbol is an exact id or its dotted tail; two matches refuse and list them, because a name match is
never a fact. `reads` is the count of frontier expansions the door asked the store for.

```text
engine/graphy/doors.py            resolve · descend · blast · explain, and their renderers
engine/graphy/federated_store.py  find(symbol) on both stores — the resolver's one query
engine/graphy/cli.py              graphy descend | blast | explain <symbol> --tenant … --tenant-id … [--depth N] [--limit N]
engine/tests/test_doors.py        the floor: a resolved chain laid beside the fixture shard, whose own calls are text labels
```

| door | walks | over | answers |
|---|---|---|---|
| `descend` | with the edges | `calls` | the callees down to the primitives, and every package crossing with the chain that made it |
| `blast` | against the edges | `calls` `inherits` `imports` `decorates` | the dependents, split into the seed's own shard and the ring |
| `explain` | against, plus the DOC_EXPLAINS family | the record · docs · tests · journal | where it lives and its docstring, the docs that bind it, the test modules that reach it, the page that birthed its shard |

### The done check, run on the FastAPI tenant

```bash
cd engine && D=tenants/fastapi/tenant.json
../.venv/bin/graphy descend get_request_handler --tenant $D --tenant-id fastapi
#   DESCEND seed=fastapi://func/fastapi.routing.get_request_handler owner=fastapi depth=4 reached=75 packages=fastapi → anyio → starlette → annotated_doc
#     BY OWNER: fastapi=60  anyio=10  starlette=5  annotated_doc=1
#     CROSSING fastapi → anyio @hop1 ×4: …get_request_handler ─calls▶ anyio://func/anyio._core._tasks.create_task_group
#     CROSSING fastapi → starlette @hop1 ×5: …get_request_handler ─calls▶ starlette://func/starlette.concurrency.iterate_in_threadpool
#     CROSSING starlette → anyio @hop2 ×1: …get_request_handler ─calls▶ starlette://func/starlette.concurrency.iterate_in_threadpool ─calls▶ anyio://func/anyio.to_thread.run_sync
#     PRIMITIVES (callees that call nothing the store carries, deepest first, 37): hop4 anyio CapacityLimiter · hop4 fastapi ParamDetails · …
#   DOOR: descend reads=128 generation=2dae16bb79a9f6f9          0.16 s wall
../.venv/bin/graphy blast get_request_handler --tenant $D --tenant-id fastapi
#   BLAST … dependents=3 own=3 ring=0 — APIRoute.get_route_handler at hop1, APIRoute.__init__ and APIRoute.handle at hop2
#   DOOR: blast reads=4                                           0.14 s
../.venv/bin/graphy explain get_request_handler --tenant $D --tenant-id fastapi
#   RECORD: func fastapi.routing.get_request_handler at fastapi/routing.py:367 (dependant, body_field, …) -> Callable[[Request], Coroutine[Any, Any, Response]]
#   DOCS: none — no rostered doc substrate · TESTS: none — the ring is minted from wheels · HISTORY: no journal page for fastapi_graph
#   DOOR: explain reads=454                                       0.15 s
../.venv/bin/graphy explain annotated_types.Interval --tenant $D --tenant-id fastapi
#   RECORD: class annotated_types.Interval at annotated_types/__init__.py:196  │ Interval can express inclusive or exclusive bounds …
#   TESTS (test modules that reach it against the edges, 1): hop1 annotated_types://func/annotated_types.test_cases.cases
../.venv/bin/graphy descend __init__ --tenant $D --tenant-id fastapi
#   DESCEND UNANSWERABLE: '__init__' names 306 nodes; a door never guesses. Pick one: …    exit 1
```

`descend get_request_handler` crosses fastapi → starlette → anyio, on the chain the issue named:
the handler calls Starlette's `iterate_in_threadpool`, which calls anyio's `to_thread.run_sync`.
The direct fastapi → anyio crossing at hop 1 is real too (`create_task_group`, `fail_after`,
`sleep`), and the door reports both because both are edges.

### What the run says that a cold read would miss

- **`explain` on a wheel-minted ring answers three absences honestly.** No docs, because no doc
  substrate is rostered; no tests, because wheels carry no suite; no journal page, because `build`
  writes none for a placed shard. Each line names its cause. The one shard in the ring that ships
  its test cases (`annotated_types.test_cases`) shows the TESTS section working on a real store.
- **The fixture shard's calls are text.** `tests/fixtures/fastapi_graph` carries `calls` edges with
  `dst_repr` labels and no resolved `dst`; only `converge --resolve` binds them. The floor test lays
  its own resolved chain beside the fixture; the tenant's store, minted with the ring and resolved,
  is where the descent is real.
- **`explain` reads more than it walks** (454 against `blast`'s 4) because it hydrates the record of
  every dependent to read its file path. The count is the price of the TESTS section, re-derivable
  with the command above.

## 20 · THE MCP SERVER, AND THE DEMO (2026-09-05 · issue 7)

`graphy mcp --tenant … --tenant-id …` serves the doors on stdio to any client that speaks the
Model Context Protocol. Zero dependencies: newline-delimited JSON-RPC 2.0, three methods
(`initialize` · `tools/list` · `tools/call`) plus `ping`; the store is opened once and its
generation pinned for the session, and every answer carries it. Five tools — `hunt` · `descend` ·
`blast` · `walk` · `explain` — each the same walk the CLI verb runs, returning the same text.

```text
engine/graphy/mcp.py              TOOLS · Doors (the five over one opened store) · handle · serve
engine/graphy/federated_store.py  grep(needle) on both stores — the hunt's second net, after the tail
engine/graphy/cli.py              graphy mcp
engine/tenants/fastapi/mcp.sh     the launcher: every path derived from its own location; a client just runs it
.mcp.json                         Claude Code picks the FastAPI server up from the repo root
engine/tenants/fastapi/demo.py    the thirty-second demo, three ways, two runners (sdk · claude-code)
engine/tests/test_mcp.py          the floor: the protocol over a pipe, the five tools over the fixture store
```

### The done check: a stranger's client, a cross-package answer, no operator

The demo is the check. It asks one blast-radius question three ways and scores every answer
against the store's own list of dependents:

```bash
bash engine/tenants/fastapi/rebuild.sh          # the tenant (GRAPHY_CORPUS_SITE_PACKAGES=… mints the ring)
.venv/bin/python engine/tenants/fastapi/demo.py --runner claude-code    # or ANTHROPIC_API_KEY=… for --runner sdk
```

```text
QUESTION: `iterate_in_threadpool` in Starlette is about to change its signature. What in FastAPI breaks,
          and through which call chain? Name the exact functions and methods, nearest first.

── 1 · graphy alone, no model (1 ms, store generation 2dae16bb79a9f6f9)
BLAST seed=starlette://func/starlette.concurrency.iterate_in_threadpool … dependents=5 own=1 ring=4
  RING: hop1 fastapi.routing.get_request_handler ◀─calls─ iterate_in_threadpool
        hop2 APIRoute.get_route_handler · hop3 APIRoute.__init__ · hop3 APIRoute.handle
── 2 · claude-haiku-4-5 + the graphy MCP server, no other tools (14.8 s · 48266 in / 1286 out)
   … the same five, with the chain, nearest first                       SCORE: 5/5
── 3 · claude-opus-5 + 3 source files stuffed (26.5 s · 103171 in / 2108 out · 270 KB of source · no tools)
   … the same five, plus the SSE branch and the StreamingResponse path  SCORE: 5/5

┌────────────────────────────────┬──────────┬───────────┬──────────┬────────────┐
│ way                            │ seconds  │ tokens in │ tok out  │ dependents │
├────────────────────────────────┼──────────┼───────────┼──────────┼────────────┤
│ graphy alone                   │     0.00 │         0 │        0 │   5/5      │
│ claude-haiku-4-5 + graphy      │     14.8 │     48266 │     1286 │   5/5      │
│ claude-opus-5 + source         │     26.5 │    103171 │     2108 │   5/5      │
└────────────────────────────────┴──────────┴───────────┴──────────┴────────────┘
DEMO OK: three ways                                                         41 s wall, this box
```

Way 2 is the stranger's path exactly: `claude -p --model haiku` with `--mcp-config` naming
`engine/tenants/fastapi/mcp.sh`, `--strict-mcp-config`, every built-in tool disallowed, and the
question on stdin. The small model reached the answer through the server in four turns. Its token
count includes Claude Code's own cached system prompt; the server's replies are a few hundred
tokens each.

### What the run says

- **The cold small model with graphy matched the frontier model with the source stuffed, at half
  the tokens and half the time, and the store alone answered in a millisecond with none.** The
  frontier model's answer is richer (it read the SSE branch and the `StreamingResponse` path the
  blast door reports as the one Starlette-side dependent) and it is the answer a reviewer would
  want; it also cost 103k input tokens and the three right files chosen by hand. The small model
  needed no choosing: `hunt` then `blast`.
- **The SDK runner is written and unproven on this box.** The key in reach has no credit
  (`credit balance is too low`, request `req_011Cem7FPENegQ2oqk9tYX4f`); the demo prints that as
  `MODELS FAILED` and ends on way 1. `--runner claude-code` is the one that ran.
- **A nested `claude -p` inside this repo hangs on this repo's own Stop hook** — the march loop
  refuses to let it stop while the armed issue is open. The demo runs its `claude -p` from a
  scratch directory that carries no hooks; `--bare` was not the answer (it also skips the login).

## 21 · THE SHARD INDEX (2026-09-05 · issue 8)

A shard is content-addressed: sha256 over its three files (`nodes.json` · `edges.json` ·
`PROVENANCE.json`), and the PROVENANCE already carries the sha256 of the two payload files. The
index is a directory — `shards/<address>/` holds the three files plus a `NOTICE` and a
`MANIFEST.json`; `names/<name>.json` points a name at an address; `catalog.json` lists every
name — so it publishes as whatever hosts a directory. Push is local. Pull reads a directory or an
`http(s)://` base with the same layout, and verifies every byte before anything lands: each file
against the manifest, the payload against the PROVENANCE, the whole against the address.

```text
engine/graphy/index.py              push · pull · catalog · verify_index · address_of · verify_shard
engine/graphy/cli.py                graphy push <shards…> --index <abs> [--name] · graphy pull <name|address> --index <abs|url> --out <abs> · graphy index --index … [--verify]
engine/graphy/tenant.py             the `pulled` lane kind; `init --lane KEY:KIND=COMMAND` carries a command
engine/tenants/fastapi/rebuild.sh   GRAPHY_SHARD_INDEX=<abs|url> [GRAPHY_PULL="name …"]: pull instead of mint, every shard a `pulled` lane
engine/tests/test_index.py          the floor: round trip, tamper refusal, name and address, http, the lane grammar
```

### The done check, run on this box

**Byte-identical round trip, verified by the PROVENANCE sha.** The FastAPI tenant's ten minted
shards pushed into `staging/index/` (gitignored), pulled back into a scratch directory, and
compared with `cmp`:

```bash
cd engine
python3 -m graphy push tenants/fastapi/substrate/*_graph --index $PWD/../staging/index   # 0.09 s, 10 shards, 7.4 MB
python3 -m graphy index --index $PWD/../staging/index                                    # 10 named shards
for n in $(python3 -c "import json;print(' '.join(json.load(open('../staging/index/catalog.json'))))"); do
  python3 -m graphy pull "$n" --index $PWD/../staging/index --out $SCRATCH/$n; done       # 0.7 s for ten
# cmp every nodes.json · edges.json · PROVENANCE.json against the substrate: 30 IDENTICAL, 0 DIFFER
```

Over http, the same bytes: `python3 -m http.server` on the index directory, then
`graphy pull pydantic==2.13.5 --index http://127.0.0.1:8765 --out …` in 0.10 s, `cmp` identical on
all three files. A missing name refuses with the verb that lists what exists. One byte flipped in
an indexed `edges.json`: the pull refuses (`does not match the manifest`), nothing lands, and
`graphy index --verify` reports `INDEX BROKEN: 10 named shard(s), 1 broken`. A manifest rewritten
to fit the tampered bytes still refuses: the address is the content.

**A rebuild that declares pulled shards in build lanes instead of minting.**

```bash
GRAPHY_SHARD_INDEX=$PWD/staging/index bash engine/tenants/fastapi/rebuild.sh   # 1.44 s wall → FASTAPI_TENANT_OK
```

Ten `PULL OK` lines, then init, resolve, build, check as before. The descriptor's ten lanes are
`["python3 -m graphy pull fastapi==0.139.0 --index <abs> --out {out}", "pulled"]` and so on; the
lane command, run by hand with `{out}` filled after deleting `idna_graph`, re-pulls it verified.
The store compiled from the pulled shards is generation `2dae16bb79a9f6f9` — the same generation
the minted rebuild produced, since the bytes are the same — and `descend get_request_handler`
crosses into starlette and anyio from it as in §19.

### What the run says

- **The index is a directory and the reader is `urllib`.** No registry service, no auth, no
  dependency. A git repo of shards, a static site, or a bucket is an index; `graphy pull` over
  `https://` is the stranger's path. Publishing one is the operator's call and is not done here.
- **The address is the three files, not the payload alone.** Two mints of the same corpus differ
  in `minted_at` and the corpus path, so they are two entries; the name pointer moves to the
  latest push and the old address stays reachable. A pull by address is exact forever.
- **Attribution rides in the entry.** The `NOTICE` names the distribution, version, license and
  oracle commit from the PROVENANCE; the derived-work line for MIT/BSD source is the index's, not
  the operator's, to remember.
- **The novelty line stands as the issue stated it:** plausibly novel against Sourcegraph, Glean and
  Kythe, which are centralized; not checked further.

---

## 22 · THE CUT — a single package fanned out into its pillars (2026-09-05 · issue 9)

Engine gap 1 of §11: `graphy fanout` grouped by the first dotted segment, so a single-package
tenant compiled to one group. The fix is a `Cut` (`engine/graphy/fanout.py`): a **depth cut**
keeps the first N dotted segments, a **partition** names groups and the dotted prefixes each
claims (matched at segment boundaries, longest prefix wins, the unclaimed rest in one named
group). The receipt gains a `cut` field — `{"kind": "depth", "depth": N}` or
`{"kind": "partition", "sha256": <the file's bytes>, "groups": N, "rest": NAME}` — and
`verify_fanout` refuses a receipt without one. Every section of a partitioned fan-out opens with
the prefixes it carries.

The FastAPI tenant's rule moved out of `walk.py` into `tenants/fastapi/partition.json`; `walk.py
pillars` and `graphy fanout --partition` read the same file, so the walk's weights and the fan-out's
group counts are one derivation.

### Measured on this box

```bash
cd engine && python3 -m graphy fanout --graph-dir tests/fixtures/fastapi_graph --out /tmp/fo \
    --partition tenants/fastapi/partition.json                                       # 0.095 s wall
#   FANOUT OK: 5 group(s) by partition 1b374eca2713… (4 named, rest=EDGE) -> /tmp/fo
cat /tmp/fo/TOC.md
#   - COMPAT: 103 nodes / 596 edges -> COMPAT.md
#   - DEPENDENCIES: 135 nodes / 1085 edges -> DEPENDENCIES.md
#   - EDGE: 34 nodes / 111 edges -> EDGE.md
#   - OPENAPI: 59 nodes / 333 edges -> OPENAPI.md
#   - ROUTING: 168 nodes / 1571 edges -> ROUTING.md
python3 -m graphy fanout --verify --out /tmp/fo
#   FANOUT VERIFY: COHERENT — 6 read record(s) match the pinned receipt
python3 -m graphy fanout --graph-dir tests/fixtures/fastapi_graph --out /tmp/fo2 --depth 2
#   FANOUT OK: 28 group(s) by depth 2 -> /tmp/fo2
python3 -m graphy fanout --graph-dir tests/fixtures/fastapi_graph --out /tmp/fo1
#   FANOUT OK: 1 group(s) by depth 1 -> /tmp/fo1        (the default is unchanged)
```

The node counts per pillar — 168 · 135 · 103 · 59 · 34 — are the ones `walk.py pillars` printed
in §11, now from one file. The edge sums equal the shard's 3,696; a group's edges are the ones
whose source it holds. (Before issue 12; since the re-mint, §23: 168 · 135 · 105 · 65 · 34 over 3,715.)

```bash
cd engine && bash tenants/fastapi/rebuild.sh                                          # 0.82 s wall
#   … LABELS OK · FANOUT OK: 5 group(s) by partition 1b374eca2713… · FANOUT VERIFY: COHERENT · FASTAPI_TENANT_OK
ls tenants/fastapi/substrate/fanout
#   COMPAT.md  DEPENDENCIES.md  EDGE.md  OPENAPI.md  ROUTING.md  TOC.md  receipt.json
```

Under the rebuild the per-pillar edge counts are higher (ROUTING 1,838 against 1,571 above)
because the shard carries the `wormhole_edges.json` that `converge --resolve` wrote beside it.

### The floor

`tests/test_fanout.py` gained six tests: the FastAPI fixture cut into its five groups with the
receipt's sha equal to the partition file's; the depth-2 cut; the **outline producer** (a second
producer, `outline.<doc>.<slug>` dotted paths over two fixture documents) cut by depth and by a
partition to the same counts, byte-identical on rerun; longest-prefix at segment boundaries
(`pkg.routingx` is not under `pkg.routing`); the partition refusals (a prefix claimed twice, the
rest name colliding with a group, an empty group, a non-dotted prefix, bad JSON, both cuts named
at once, depth 0); and `verify_fanout` refusing a receipt whose cut is missing or malformed.

### What is not here

The partition is curated. Deducing it — the fan-in/fan-out cut that produced FastAPI's four — is
issue 14; regenerating the arm files' walk-derived half from this fan-out is issue 10.

---

## 23 · THE GUARDED DEF — the producer walks into module-level if/try/with/for (2026-09-05 · issue 12)

The python_ast producer walked `tree.body` and descended into `ClassDef` and `FunctionDef` bodies
only, so a `def` or `class` under a module-level `if`, `try`, `with` or `for` — the whole
version-gated backport pattern, `if hasattr(typing, X): ... else: class X` — was never a node.
`_defs_in(body)` now yields the defs a body defines, descending through `if`/`else`,
`try`/`except`/`else`/`finally` (and `try*`), `with`, `for`/`else`, `while`/`else`, at module level
and inside a class body, and never into a function body. The dotted path is unchanged: the module
(or the class) is still the parent. A name defined in both branches of an `if`/`else` lands as one
node with two `contains` edges — the shape the `@overload` pattern already produced; unchanged.

```text
engine/graphy/adapters/python_ast.py   _defs_in · the class body and the module body walk through it
engine/graphy/smash.py                 portable(): a shard records paths relative to the mint's cwd when under it or its parent
engine/tests/fixtures/fastapi_graph    re-minted by `graphy smash` from the pinned wheel — PROVENANCE names the mint command
engine/tests/test_adapters.py          the guarded-def floor: if/else · try/except/finally · with · for · while · a class-level if · a def inside a function is still not a node
engine/tests/test_ir.py · test_ir_json_layer.py · test_index.py · test_smash.py   the fixture's counts, re-pinned
```

### The fixture, re-minted

The constraint was the parity gate: the vendored fixture was minted with the blind spot, and
`graphy smash --parity` proves the producer against it record for record. So the fix landed with the
fixture re-minted from the pinned wheel, by the engine, and the golden's provenance now names that
command — before, `python -m graphy.factory build fastapi` on a host repo that no longer exists (§13).
The first re-mint failed the gate's prose scrub: the PROVENANCE carried this box's absolute home
path in `mint_command` and `corpus.path`. `smash.portable()` now records a path relative to the
directory the mint ran from when it lies under that directory or its parent, absolute otherwise —
so the fixture's re-derive runs from `engine/` on any checkout that holds the pinned venv.

```bash
cd engine && python3 -m graphy smash --package fastapi --site-packages ../staging/corpora/venv/lib/python3.12/site-packages \
    --out tests/fixtures --no-ring && rm tests/fixtures/ring.json
#   MINT OK: fastapi 507 nodes / 3715 edges -> …/engine/tests/fixtures/fastapi_graph
python3 -c "import json; p=json.load(open('tests/fixtures/fastapi_graph/PROVENANCE.json')); print(p['mint_command']); print(p['oracle_commit'], p['counts'])"
#   python3 -m graphy smash --package fastapi --site-packages ../staging/corpora/venv/lib/python3.12/site-packages --out tests/fixtures --no-ring
#   sha256:21ed3ce1ca24e531f68f036679f69134d1aa8ae6132bdf822aa86b207fb84427
#   nodes 507 (class 113 · func 135 · method 211 · module 48) · edges 3715 (calls 2460 · contains 459 · decorates 50 · imports 649 · inherits 97)
```

The eight FastAPI nodes the old producer missed, and where they hid:

```bash
cd engine && git show 1e13b4f:engine/tests/fixtures/fastapi_graph/nodes.json > /tmp/old_nodes.json && python3 -c "
import json; old = json.load(open('/tmp/old_nodes.json')); new = json.load(open('tests/fixtures/fastapi_graph/nodes.json'))
print(*sorted(set(new) - set(old)), sep='\n'); print('removed:', sorted(set(old) - set(new)))"
#   fastapi://class/fastapi.encoders.Color · fastapi://class/fastapi.encoders.PyExtraColor       (fastapi/encoders.py: try: from pydantic.color import Color / except ImportError: class Color)
#   fastapi://class/fastapi.openapi.models.EmailStr                                              (fastapi/openapi/models.py: try: from email_validator … / except ImportError: class EmailStr)
#   fastapi://method/fastapi.openapi.models.EmailStr.{__get_validators__, validate, _validate, __get_pydantic_json_schema__, __get_pydantic_core_schema__}
#   removed: []
```

### typing_extensions, re-derived

The issue's re-derive (`ast.walk` over every `if`/`try` body) counts 15 + 236 = 251, but that walk
also enters function bodies and counts a name defined in both branches twice. The count the
producer's semantics give — defs reachable through compound statements, never through a function,
distinct by dotted id — is 240, plus the module:

```bash
cd engine && python3 -c "
import ast
from graphy.adapters import python_ast as pa
t = ast.parse(open('../staging/corpora/venv/lib/python3.12/site-packages/typing_extensions.py').read())
def count(body, prefix, acc):
    for d in pa._defs_in(body):
        acc.add(prefix + '.' + d.name)
        if isinstance(d, ast.ClassDef): count(d.body, prefix + '.' + d.name, acc)
acc = set(); count(t.body, 'typing_extensions', acc); print(len(acc) + 1)"
#   241
```

### The ring, re-minted

```bash
cd engine && GRAPHY_CORPUS_SITE_PACKAGES=$PWD/../staging/corpora/venv/lib/python3.12/site-packages bash tenants/fastapi/rebuild.sh
#   MINT OK ×10 · RING: 10 shard(s) · stdlib skipped 72 · unresolved 30
#   PARITY OK: fastapi_graph.records@sha256:21ed3ce1… — 507 nodes / 3715 edges identical to tests/fixtures/fastapi_graph
#   BUILD OK: compiled 5126 nodes / 11809 edges · CHECK OK · LABELS OK · FANOUT OK: 5 group(s) · FANOUT VERIFY: COHERENT · FASTAPI_TENANT_OK
#   2.48 s wall (the mint alone 1.07 s)
bash tenants/fastapi/rebuild.sh
#   BUILD OK: compiled 507 nodes / 1139 edges · … · FASTAPI_TENANT_OK              0.77 s wall — the placed fixture, with the resolver's sidecar
```

| shard | version | nodes | edges | before issue 12 |
|---|---|---|---|---|
| fastapi | 0.139.0 | 507 | 3,715 | 499 · 3,696 |
| pydantic | 2.13.5 | 2,194 | 13,203 | 2,021 · 12,624 |
| anyio | 4.15.1 | 1,249 | 5,868 | 1,210 · 5,656 |
| starlette | 1.6.0 | 620 | 2,933 | 619 · 2,931 |
| typing_extensions | 4.16.0 | 241 | 1,058 | 29 · 102 |
| pydantic_core | 2.46.5 | 189 | 469 | unchanged |
| idna | 3.19 | 58 | 395 | unchanged |
| annotated_types | 0.8.0 | 39 | 269 | 37 · 262 |
| typing_inspection | 0.4.4 | 22 | 145 | 19 · 134 |
| annotated_doc | 0.0.5 | 7 | 8 | unchanged |

The fan-out by `partition.json` over the re-minted fixture alone: ROUTING 168 · DEPENDENCIES 135 ·
COMPAT 105 · OPENAPI 65 · EDGE 34, edges summing to 3,715 — the six new `openapi.models` nodes
land in OPENAPI, the two `encoders` classes in COMPAT:

```bash
cd engine && python3 -m graphy fanout --graph-dir tests/fixtures/fastapi_graph --out /tmp/fo --partition tenants/fastapi/partition.json && cat /tmp/fo/TOC.md
```

The staging index at `staging/index` holds the re-minted ring under the same ten names
(`python3 -m graphy index --index $PWD/../staging/index --verify` → `INDEX OK: 10 named shard(s), 0 broken`);
the `fastapi==0.139.0` pointer resolves to the fixture's bytes (`eb5326ee…`).

### The floor and the gate

```bash
cd engine && python3 -m pytest             # 392 passed, 5 skipped (the FastAPI parity proof among them, opt-in by GRAPHY_CORPUS_SITE_PACKAGES)
GRAPHY_CORPUS_SITE_PACKAGES=$PWD/../staging/corpora/venv/lib/python3.12/site-packages python3 -m pytest   # 393 passed, 4 skipped
bash ../standalone_check.sh                # prose scrub OK · GRAPHY_STANDALONE_OK
```

---

## 24 · THE PILLARS DOOR — the cut deduced from the walk (2026-09-05 · issue 14)

The four FastAPI pillars were ruled by hand from two rankings (§11); the rule lived in
`walk.py:pillar_of`, curated. `graphy pillars` now proposes the partition from the compiled store's
module graph and prints, beside every unit, the numbers that placed it. The curated
`partition.json` stays the input the fan-out cuts by; `--against` diffs the proposal against it and
exits 1 naming every unit cut differently. The rule is the docstring of `engine/graphy/pillars.py`:
units at a dotted depth (default 2), the root a facade, units under a floor of cross-unit edges the
edge, fan-out over fan-in an orchestrator, fan-out in the leader's league a crown, an orchestrator
another arm consumes orchestrated by it, an orchestrator nobody orchestrates that spreads its
spending a crown of its own, a foundation one arm takes two thirds of owned, the rest shared — the
floor, named after the greatest fan-in no arm owns.

### The FastAPI tenant: four crowns reproduced, three units named

```bash
cd engine && GRAPHY_CORPUS_SITE_PACKAGES=$PWD/../staging/corpora/venv/lib/python3.12/site-packages bash tenants/fastapi/rebuild.sh
#   … PILLARS WROTE: …/substrate/pillars.json — 5 group(s), rest=EDGE · FANOUT VERIFY: COHERENT — 7 read record(s) · FASTAPI_TENANT_OK   real 2.84 s (placed path: 1.03 s)
python3 -m graphy pillars --tenant tenants/fastapi/tenant.json --tenant-id fastapi --corpus fastapi --against tenants/fastapi/partition.json
#   PILLARS: fastapi at depth 2 — 5 arm(s) over 251 cross-unit edges (imports · calls · inherits · decorates); floor 5 edges, owned 0.67, client 0.33
#     ROUTING        crown: fastapi.routing            routing 59 out
#     DEPENDENCIES   crown: fastapi.dependencies       dependencies 48 out · security (orchestrated, 3 of 3) · param_functions (3 of 4) · params (owned, 13 of 15)
#     OPENAPI        crown: fastapi.openapi            openapi 39 out
#     APPLICATIONS   crown: fastapi.applications       stands alone: nothing orchestrates it; the most it spends on one arm is 6 of 28 (OPENAPI)
#     COMPAT         the floor: fastapi._compat        _compat 48 in (DEPENDENCIES 28 · OPENAPI 10 · ROUTING 3) · datastructures · exceptions · utils · encoders · types
#     EDGE           14 units — the facade and every unit under 5 cross-unit edges
#   PILLARS DIFFER: 3 unit(s) cut differently from tenants/fastapi/partition.json
#     fastapi.applications        proposed APPLICATIONS  curated ROUTING   — stands alone (6 of 28 to OPENAPI; 1 resolved edge to routing)
#     fastapi.exception_handlers  proposed APPLICATIONS  curated COMPAT    — orchestrated by APPLICATIONS (1 of 1 consuming edges)
#     fastapi.sse                 proposed EDGE          curated ROUTING   — 4 cross-unit edges, under the floor of 5
#   exit 1
```

**The ruling.** The three crowns and the floor the hand cut named are the ones the walk finds, and
so is every membership under DEPENDENCIES (security, param_functions, params) and under COMPAT. The
walk cuts `applications` differently, and the evidence is exact: the store carries one resolved edge
from `applications` to `routing` (the router is a `calls` label the resolver cannot bind through
scope) and six to `openapi` (the docs wiring). §11 folded it into ROUTING because it delegates to its
router and both inherit Starlette — a reading of the code, which is what the door does not do. The
curated file keeps that ruling; the door keeps the evidence beside it. `sse` is four edges, under
the floor. Every count above is in the store the mint path builds (labels resolved by `converge
--resolve`); over the placed fixture alone the traffic is smaller and the same crowns hold
(`tests/test_pillars.py`).

### The same door on the ring: arms an operator can read cold

```bash
python3 -m graphy pillars --tenant tenants/fastapi/tenant.json --tenant-id fastapi        # 10 corpora — refuses: name one with --corpus
python3 -m graphy pillars --tenant tenants/fastapi/tenant.json --tenant-id fastapi --corpus starlette
#   3 arm(s) over 247 edges:  MIDDLEWARE (middleware 79 out; applications a client, authentication orchestrated)
#                             ROUTING (routing 38 out, stands alone; _exception_handler orchestrated)
#                             DATASTRUCTURES the floor (datastructures 47 in; responses · _utils · requests · types · exceptions · concurrency · websockets shared; endpoints · staticfiles · templating · testclient lean only on the floor)
python3 -m graphy pillars --tenant tenants/fastapi/tenant.json --tenant-id fastapi --corpus pydantic
#   6 arm(s) over 494 edges:  DEPRECATED · MAIN · JSON_SCHEMA · FIELDS crowns in the league · DATACLASSES stands alone · INTERNAL the floor (_internal 172 in)
python3 -m graphy pillars --tenant tenants/fastapi/tenant.json --tenant-id fastapi --corpus anyio
#   4 arm(s) over 383 edges:  BACKENDS · STREAMS · TO_PROCESS crowns · CORE the floor (_core 180 in)
```

### The floor and the gate

```bash
cd engine && python3 -m pytest             # 401 passed, 5 skipped (9 new in tests/test_pillars.py; the parity proof skips without the corpus env)
bash ../standalone_check.sh                # prose scrub OK · GRAPHY_STANDALONE_OK
```

### What landed

```text
engine/graphy/pillars.py              module_graph (the store's owned() + edges() → units) · propose · to_partition · diff · render
engine/graphy/federated_store.py      owned(corpus) and edges() on both stores — the whole-corpus read an aggregate takes
engine/graphy/cli.py                  graphy pillars --tenant --tenant-id [--corpus] [--depth] [--arms] [--floor] [--owned] [--client] [--write] [--against]
engine/tenants/fastapi/rebuild.sh     writes substrate/pillars.json + pillars.txt and fans the shard out by the proposal at substrate/fanout.proposed/, verified
engine/tenants/fastapi/FASTAPI.md     the proposal beside the four, the tap
engine/tests/test_pillars.py          the rule on a page-sized graph; the fixture's crowns; --write → fanout --partition; --against; the refusals
```

## 25 · THE REFRESH LANE — upstream moved, the tenant follows into a sibling (2026-09-06 · issue 15)

`graphy refresh` keeps a tenant current with its package's upstream without ever touching the
substrate it runs on. It reads the release off the current shard's `PROVENANCE.json`, asks PyPI
for the newest final release (or takes `--release`, or reads the version off an already-provisioned
`--site-packages`), provisions a venv pinned to exactly that release beside a *sibling* substrate,
mints the package and its ring there with `smash`, declares a sibling descriptor over exactly the
shards the ring minted, runs `converge --resolve` · `build` · `check` on it, and only then stamps
one journal page per shard into the sibling's journal — old the current shard's ids, new the
sibling's, `prev_cursor` the old version, `cursor` the new — and prints what the journal says was
born and died. A red check is exit 1 and the sibling stays for reading. Promotion is a printed
command, never taken. The rule is the docstring of `engine/graphy/refresh.py`.

### The run on this box — FastAPI 0.139.0 → 0.141.1

```bash
cd engine
python3 -m graphy refresh --tenant tenants/fastapi/tenant.json --tenant-id fastapi --package fastapi --check
#   UPSTREAM: fastapi 0.139.0 -> 0.141.1 (https://pypi.org/pypi/fastapi/json)
#   REFRESH NEWER: fastapi 0.139.0 -> 0.141.1; run without --check to mint
time python3 -m graphy refresh --tenant tenants/fastapi/tenant.json --tenant-id fastapi --package fastapi
#   VENV: /usr/bin/python3 -m venv …/tenants/fastapi/substrate.0.141.1/venv      PIP: fastapi==0.141.1
#   MINT OK ×10: fastapi 518/3812 · annotated_doc · anyio · pydantic · pydantic_core · starlette · typing_extensions · typing_inspection · idna · annotated_types
#   DECLARED: …/tenants/fastapi/tenant.0.141.1.json over 10 shard(s)
#   CONVERGE: 10 shard(s) · 2101 wormhole edge(s) over 219 node(s)
#   BUILD OK: compiled 5137 nodes / 11858 edges       CHECK OK: descriptor valid; store fresh; journal readable
#   DIFF 0.139.0 -> 0.141.1: 10 shard(s), what the journal says
#     fastapi_graph: nodes +24 -13 · edges +158 -90        every ring shard: +0 -0 (the same latest deps resolved)
#   REFRESH OK: fastapi 0.139.0 -> 0.141.1 proven at …/substrate.0.141.1; the current substrate is untouched.
#   real 0m5.8s  (pip from its cache; the venv, ten mints, the resolver, the store, the audit, the diff)
```

What FastAPI moved between the two releases, as the shard's journal records it — the `Dependant`
class shed its methods into module-level helpers, and the openapi security walk became a helper
with its own data class:

```text
died 13   Dependant.{cache_key, computed_scope, oauth_scopes, is_async_gen_callable, is_coroutine_callable,
          is_gen_callable, _is_security_scheme, _security_dependencies, _security_scheme, _uses_scopes}
          dependencies.utils.{get_body_field, get_flat_dependant}   openapi.utils.get_openapi_security_definitions
born 24   dependencies.models.{_CallIdentity (+__init__ __eq__ __hash__), _get_cache_key, _get_computed_scope,
          _get_oauth_scopes, _get_security_scheme, _is_*_callable ×3, _is_*_callable_cached ×3, _is_security_scheme, _uses_scopes}
          dependencies.utils.{_get_body_field, _get_flat_body_params}
          openapi.utils.{_OpenAPIDependencyData, _get_openapi_dependency_data, _get_openapi_security_definitions}
          routing.{_resolve_frontend_check_dir, _FrontendStaticFiles.get_response_for_scope}   sse._split_sse_lines
```

```bash
python3 - <<'PY'   # re-derive the lists from the sibling's journal
import json; pg=[json.loads(l) for l in open("tenants/fastapi/substrate.0.141.1/journal/fastapi_graph.journal.jsonl")][-1]
print(pg["n_born"], pg["n_died"], pg["n_eborn"], pg["n_edied"], pg["prev_cursor"], "->", pg["cursor"]); print(*pg["died"], sep="\n")
PY
python3 -c "import json;r=json.load(open('tenants/fastapi/substrate.0.141.1/refresh.json'));print(r['verdict'], r['release_source'], [d for d in r['diff'] if d['n_born'] or d['n_died']])"
python3 -m graphy blast Dependant --tenant tenants/fastapi/tenant.0.141.1.json --tenant-id fastapi    # the sibling walks
```

The tenant stays pinned to 0.139.0: the vendored fixture is the parity golden, and a newer release
fails parity by design. The lane closes that loop on request — `--fixture ../tests/fixtures/fastapi_graph`
re-mints the golden shard from the sibling's site-packages with the engine's own `--no-ring` mint
command after the check is green (proven on the synthetic tenant in `tests/test_refresh.py`: the
new ring then passes parity against the re-minted fixture). Promoting FastAPI to 0.141.1 is the
operator's call, not this issue's: it re-pins every fixture-bound test and the arm docs' symbols.

### The floor and the gate

```bash
cd engine && python3 -m pytest             # 409 passed, 5 skipped (8 new in tests/test_refresh.py; 414 collected)
bash ../standalone_check.sh                # prose scrub OK · GRAPHY_STANDALONE_OK — the scrub now skips substrate.*/ and tenant.*.json like their siblings
```

### What landed

```text
engine/graphy/refresh.py              current_provenance · latest_release (PyPI JSON; finals only, yanked skipped) · parse_version/is_newer · plan_for · provision · diff_shards (journal.append_page per shard) · render_pages · refresh
engine/graphy/cli.py                  graphy refresh --tenant --tenant-id --package [--check] [--release] [--site-packages] [--python] [--fixture] [--force]
engine/.gitignore                     tenants/*/substrate.*/ · tenants/*/tenant.*.json — the sibling never travels
standalone_check.sh                   the prose scrub excludes the sibling like the substrate
engine/tenants/fastapi/FASTAPI.md     the taps; THE ROUTINE — the cron line, documented, not armed
engine/tests/test_refresh.py          a synthetic tenant refreshed against a second site-packages: the sibling, the journal's born/died, the untouched current, CURRENT/NEWER, the refusals, the fixture re-mint closing parity
```

## 26 · THE SECOND TENANT, AND THE BRIDGE — two tenants in one process, a walk between them on a declared literal (2026-09-06 · issue 16)

`engine/tenants/sqlalchemy/` is the second tenant: SQLAlchemy minted cold from a venv `rebuild.sh`
provisions itself (pinned to `SQLALCHEMY_RELEASE`, default 2.0.52), its ring beside it (greenlet,
typing_extensions), converged · built · checked · fanned out by the same verbs as FastAPI, with no
fixture and no parity step. `graphy bridge` opens two tenants through their own descriptors —
`open_for` takes one tenant and reads only under it — and walks a frontier of (side, id) pairs. A
crossing is the identity of one string: the same literal is a node id in both stores because both
rings minted the same package, and the bridge crosses on it only when its scheme is declared with
`--join`. No join refuses; a join one side does not carry refuses; the same data_home twice
refuses. The rule is the docstring of `engine/graphy/bridge.py`; the floor is `tests/test_bridge.py`,
which records every `open()` and `sqlite3.connect()` while each side opens and proves each set lies
under that side's data_home alone.

### The run on this box

```bash
cd engine
time bash tenants/sqlalchemy/rebuild.sh
#   VENV: sqlalchemy==2.0.52 already at …/staging/corpora/sqlalchemy/venv   (first run: python3 -m venv + pip, ~10 s)
#   MINT OK: sqlalchemy 11959 nodes / 56604 edges · greenlet 356 / 2339 · typing_extensions 241 / 1058
#   RING: 3 shard(s) · stdlib skipped 62 · unresolved annotationlib, asyncmy, asyncpg, cx_Oracle, …, psycopg2, pymysql, pytest, sqlcipher3
#   RESOLVE OK: sqlalchemy 35687 label(s) -> 11123 edge(s) (import 4353 · local 2230 · reexport 1655 · self 2701 · super 184; 85 cross-shard)
#   CONVERGE: 3 shard(s) · 111 wormhole edge(s) over 7 node(s)   sqlalchemy -> typing_extensions 106 · sqlalchemy -> greenlet 5
#   BUILD OK: compiled 12556 nodes / 24948 edges       CHECK OK: descriptor valid; store fresh; journal readable
#   FANOUT OK: 6 group(s) by partition (5 named, rest=EDGE)   FANOUT VERIFY: COHERENT
#   SQLALCHEMY_TENANT_OK
#   real 0m5.2s

F=tenants/fastapi/tenant.json; S=tenants/sqlalchemy/tenant.json
time python3 -m graphy bridge --tenant $F --tenant-id fastapi --tenant $S --tenant-id sqlalchemy --join typing_extensions \
    --seed fastapi://func/fastapi.param_functions.Cookie --target sqlalchemy://class/sqlalchemy.orm.session.Session
#   JOIN typing_extensions: fastapi holds 241 node(s) · sqlalchemy holds 241 node(s)
#   BRIDGE PATH: seed=fastapi://func/fastapi.param_functions.Cookie target=sqlalchemy://class/sqlalchemy.orm.session.Session hops=6 crossings=1 visited=6385
#     [fastapi] fastapi://func/fastapi.param_functions.Cookie
#       --calls--> [fastapi] typing_extensions://class/typing_extensions.deprecated
#       <--contains-- [fastapi] typing_extensions://module/typing_extensions
#       ==join typing_extensions==> [sqlalchemy] typing_extensions://module/typing_extensions
#       --imports--> [sqlalchemy] sys://module/sys
#       <--imports-- [sqlalchemy] sqlalchemy://module/sqlalchemy.orm.session
#       --contains--> [sqlalchemy] sqlalchemy://class/sqlalchemy.orm.session.Session
#   BRIDGE: fastapi reads=4521 generation=98a23a7b377422b0 · sqlalchemy reads=375 generation=3a9f8a3a4b15a939
#   real 0m0.47s   exit 0

python3 -m graphy bridge --tenant $S --tenant-id sqlalchemy --tenant $F --tenant-id fastapi --join typing_extensions \
    --seed sqlalchemy://class/sqlalchemy.orm.session.Session --target fastapi://class/fastapi.applications.FastAPI
#   BRIDGE PATH: … hops=6 crossings=1 visited=13932
#     Session <--contains-- orm.session --imports--> util.typing --imports--> typing_extensions ==join==> [fastapi] typing_extensions <--imports-- fastapi.applications --contains--> FastAPI

python3 -m graphy bridge --tenant $F --tenant-id fastapi --tenant $S --tenant-id sqlalchemy --seed … --target …
#   BRIDGE REFUSED: no --join declared — a bridge crosses only on a declared scheme …            exit 2
python3 -m graphy bridge … --join pydantic …
#   BRIDGE REFUSED: --join pydantic: no node under pydantic:// in tenant(s) sqlalchemy …          exit 2
python3 -m graphy bridge --tenant $F --tenant-id fastapi --tenant $F --tenant-id fastapi2 --join typing_extensions …
#   BRIDGE REFUSED: 'fastapi2' and 'fastapi' share the data_home …/tenants/fastapi/substrate …    exit 2
```

Honest about the path: the forward walk's shortest route runs through `sys://module/sys`, a
standard-library wire node the SQLAlchemy store carries because `typing_extensions` and
`orm.session` both import `sys`. It is a real edge on both ends and the walk reports it as such;
a reader wanting a route through package code raises nothing and reads the reverse walk, which
crosses on the module literal and continues through `util.typing`. Both crossings are the one
declared literal.

### The cut, and where the walk disagrees

```bash
python3 -m graphy pillars --tenant $S --tenant-id sqlalchemy --corpus sqlalchemy --arms 6
#   crowns by fan-out: testing (out 801) · dialects (799) · orm (793) · ext (319) · pool (18); the floor: sql (in 1510)
#   shared under the floor (no arm takes 2/3 of fan-in): exc 507 · util 355 · engine 288 · inspection 180 · schema 11
python3 -m graphy pillars --tenant $S --tenant-id sqlalchemy --corpus sqlalchemy --against tenants/sqlalchemy/partition.json
#   PILLARS DIFFER: 11 unit(s) cut differently — ext, pool, schema, events (→TESTING) · connectors, types (→DIALECTS) · event, log (→ORM) · engine, exc, util (→SQL, shared)
#   exit 1
```

The curated `partition.json` keeps five arms (SQL · ENGINE · ORM · DIALECTS · TESTING) and says why in
`SQLALCHEMY.md`; the diff is the evidence beside it, re-derived on every rebuild into
`substrate/pillars.json`.

| check | result |
|---|---|
| the tenant token | `SQLALCHEMY_TENANT_OK` in 5.2 s (venv warm) |
| the bridge, forward | hops 6, crossings 1, 0.47 s, exit 0 |
| the bridge, reverse | hops 6, crossings 1, exit 0 |
| the three refusals | exit 2, each naming its reason |
| the floor | `python3 -m pytest -q tests/test_bridge.py` → 5 passed |

## 27 · THE ARMS DOOR — the walk-derived half of an arm file as a generated region (2026-09-06 · issue 10)

Every arm file under `engine/tenants/<name>/arms/` is now judgment prose around a region the walk
writes: the symbols the partition places in the arm, by module, each class with its method count;
every `inherits` edge that leaves the arm, tagged with the pillar or the scheme it lands in; and
the re-walk taps. `graphy arms` renders the region from the compiled store (never the shard) and
writes it between two HTML-comment markers, replacing an existing region in place, appending when
the file has none, creating a stub when the file is absent, and never touching a byte outside the
markers. The opening marker stamps the store generation, the partition's sha and the sha of the
region's own body. `--verify` re-renders from the live store and names each arm as `moved` (the
walk changed, with the differing lines), `edited` (the bytes inside the markers no longer match
their own stamp), `no-region` or `no-file` — exit 1 on any. Both tenants' `rebuild.sh` verify the
arms after the fan-out; the FastAPI one only when the ring is minted, because a fixture placed
alone has no Starlette or pydantic node behind its `inherits` literals, the store drops them, and
the joins out are truthfully empty — it prints `ARMS SKIPPED` and says why. The rule is the
docstring of `engine/graphy/arms.py`; the floor is `tests/test_arms.py`.

### The run on this box

```bash
cd engine; T=tenants/fastapi
python3 -m graphy arms --tenant $T/tenant.json --tenant-id fastapi --corpus fastapi --partition $T/partition.json --dir $T/arms
#   ARMS OK: ROUTING appended · DEPENDENCIES appended · COMPAT appended · OPENAPI appended -> tenants/fastapi/arms (store 98a23a7b377422b0, cut sha256:1b374eca2713…)
python3 -m graphy arms … --dir $T/arms --verify
#   ARMS OK: 4 arm(s) match the walk (store 98a23a7b377422b0)                                   exit 0
sed -i 's/`APIRouter` (32)/`APIRouter` (31)/' <a copy of ROUTING.md>; … --verify
#   ARMS DRIFT: 1 of 4 arm(s) differ … ROUTING  edited  the region's bytes do not match its own content stamp — a hand edited inside the markers     exit 1
rm <copy>/COMPAT.md; … --verify
#   ARMS DRIFT: … COMPAT  no-file                                                               exit 1

# what 0.141.1 moves, per arm — the sibling the refresh lane (§25) left beside the current substrate
python3 -m graphy arms --tenant $T/tenant.0.141.1.json --tenant-id fastapi --corpus fastapi --partition $T/partition.json --dir $T/arms --verify --on-stale warn
#   ARMS DRIFT: 3 of 4 arm(s) differ from the walk
#     ROUTING       moved  store 98a23a7b377422b0 -> 9d611f2a615d5a90; 4 line(s): `_FrontendStaticFiles` (9) -> (10) · sse gains `_split_sse_lines`
#     DEPENDENCIES  moved  4 line(s): `Dependant` (10) -> `Dependant` · `_CallIdentity` (3) + the eleven module-level helpers; utils gains `_get_body_field` · `_get_flat_body_params`
#     OPENAPI       moved  2 line(s): utils gains `_OpenAPIDependencyData` · `_get_openapi_dependency_data` · `_get_openapi_security_definitions`
#     COMPAT        match
#   exit 1 — the same born/died §25 read off the journal, now landed in the arm that owns each symbol

GRAPHY_CORPUS_SITE_PACKAGES=<site-packages holding fastapi==0.139.0> bash $T/rebuild.sh
#   PARITY OK … ARMS OK: 4 arm(s) match the walk (store 98a23a7b377422b0) … FASTAPI_TENANT_OK      real 0m3.0s
bash $T/rebuild.sh                                   # the fixture placed alone
#   ARMS SKIPPED: the fixture placed alone carries no ring, so the joins out are unresolved — verify with GRAPHY_CORPUS_SITE_PACKAGES or GRAPHY_SHARD_INDEX set
#   FASTAPI_TENANT_OK
bash tenants/sqlalchemy/rebuild.sh
#   ARMS OK: 5 arm(s) match the walk (store 3a9f8a3a4b15a939) … SQLALCHEMY_TENANT_OK              real 0m5.6s
```

| check | result |
|---|---|
| the regions rendered | FastAPI 4 arms, SQLAlchemy 5 arms, appended below the prose |
| verify, current store | ARMS OK both tenants, exit 0 |
| the three drift kinds | edited · moved · no-file, each named, exit 1 |
| against the 0.141.1 sibling | 3 of 4 arms moved, the born/died of §25 per arm |
| the floor | `python3 -m pytest -q tests/test_arms.py` → 5 passed |

## 28 · THE FOUR LEAKS BEHIND THE IR — no consumer reads a `.py` path or the interpreter (2026-09-06 · issue 18)

Four places downstream of the IR assumed Python. Each now reads a field the producer wrote:

| leak | before | now |
|---|---|---|
| `pillars._module_of` (arms through it) | derived a node's module from its `.py` path and `__init__` | reads `record["module"]`; a record without it is skipped, never derived |
| `doors.TEST_FILE` | a Python filename regex decided what a test is | reads `record["role"] == "test"`; the regex moved into `adapters/python_ast.py`, the producer that owns the rule |
| `cross_substrate.STDLIB_SCHEMES` · `converge._stdlib_schemes` · `mesh_federation_gate._stdlib` | `sys.stdlib_module_names` of the running interpreter | the scheme index's `_meta.standard` (converge falls back to `ring.json`'s `standard`, the producer's own receipt beside the shards); absent means none |
| `smash.stdlib_names` / `locate` / `distributions` | the same | unchanged — the one Python-ecosystem door, and it now writes `standard` into the ring receipt so every index writer (`eat`, `refresh`, both `rebuild.sh`) carries it |

The producer emits `module` on every node and `role: test` where its own rule says so. The FastAPI
fixture was re-minted by the engine from the pinned wheel (`PROVENANCE.json` carries the command);
node and edge counts are unchanged, every node gained `module`.

```bash
cd engine
grep -rn '\.py\b\|stdlib_module_names' graphy/*.py | grep -v '^graphy/\(adapters\|smash\|refresh\|cli\|reseed\|session_tail\|lightning\)\|#\|"""'
#   (nothing)
python3 -m graphy smash --package fastapi --site-packages ../staging/corpora/venv/lib/python3.12/site-packages --out tests/fixtures --no-ring
#   MINT OK: fastapi 507 nodes / 3715 edges
GRAPHY_CORPUS_SITE_PACKAGES=… bash tenants/fastapi/rebuild.sh      # PARITY OK · ARMS OK: 4 arm(s) match · FASTAPI_TENANT_OK
bash tenants/sqlalchemy/rebuild.sh                                   # ARMS OK: 5 arm(s) match · SQLALCHEMY_TENANT_OK
python3 -c 'import json;print(json.load(open("tenants/fastapi/substrate/.federation_scheme_index.json"))["_meta"]["standard"][:3])'
#   ['__future__', '__main__', '_abc']
python3 -m pytest -q tests/test_ir_neutral.py    # a `src/*.ts` twin of a `pkg/*.py` shard: the same module graph, byte-identical arm regions, the same tests named, the bridge crosses — 2 passed
```

| check | result |
|---|---|
| the grep for the leaks | returns nothing outside the producer and the Python-ecosystem door |
| both tenants | rebuilt green, every arm region byte-identical to before (`module` reproduces the old derivation) |
| the neutral-shard floor | 2 passed; the whole floor green; `GRAPHY_STANDALONE_OK` |

## 29 · THE VERSION-IDENTITY LAW — a node id is a name, the roster is the resolution (2026-09-06 · issue 19)

The ruling, now in CLAUDE.md under THE LAWS: `<scheme>://<node_type>/<dotted>` carries no release.
That is what makes a wormhole free and what makes two releases of one package spell the same ids.
A tenant names exactly one release per scheme; the shard's `PROVENANCE.json` is the only place a
version lives; two releases of one scheme in a roster, or across a bridge's join, refuse at the
seam — never a guess, never a merge, never a version-qualified id. The alternative (a release in
the scheme) was rejected because it would break the wormhole every tenant already stands on and
turn every cross-shard edge into a resolver problem. The rule is the docstring of
`engine/graphy/release.py`; the floor is `tests/test_release.py`.

Where it is enforced: `graphy build` refuses a roster whose shards own one scheme under two pins
(an unpinned shard beside a pinned one is a collision too); `graphy check` reports it RED; the
bridge's join receipt prints each side's release for the joined scheme and refuses a skew unless
`--allow-release-skew` carries it, and then the skew is printed on its own line.

### The run on this box — a real skew, made and unmade

```bash
cd engine
B="python3 -m graphy bridge --tenant tenants/fastapi/tenant.json --tenant-id fastapi --tenant tenants/sqlalchemy/tenant.json --tenant-id sqlalchemy --join typing_extensions --seed fastapi://func/fastapi.param_functions.Cookie --target sqlalchemy://class/sqlalchemy.orm.session.Session"
$B | head -1
#   JOIN typing_extensions: fastapi holds 241 node(s) at typing_extensions==4.16.0 · sqlalchemy holds 241 node(s) at typing_extensions==4.16.0
../staging/corpora/sqlalchemy/venv/bin/pip install typing_extensions==4.12.2 && bash tenants/sqlalchemy/rebuild.sh
#   MINT OK: typing_extensions 222 nodes / 846 edges … ARMS OK … SQLALCHEMY_TENANT_OK
$B
#   BRIDGE REFUSED: --join typing_extensions: the two sides pin different releases (fastapi typing_extensions==4.16.0 · sqlalchemy typing_extensions==4.12.2) — a node id is a name, and the same literal would mean two things; re-mint one ring at the other's release, or carry the skew with --allow-release-skew
#   exit 2
$B --allow-release-skew
#   JOIN typing_extensions: fastapi holds 241 node(s) at typing_extensions==4.16.0 · sqlalchemy holds 222 node(s) at typing_extensions==4.12.2
#   JOIN typing_extensions SKEW: the sides pin different releases and the operator carries it — the crossing literal names two releases of one package
#   BRIDGE PATH: … hops=6 crossings=1 visited=7458        exit 0
../staging/corpora/sqlalchemy/venv/bin/pip install typing_extensions==4.16.0 && bash tenants/sqlalchemy/rebuild.sh   # restored; $B prints 4.16.0 on both sides again
```

| check | result |
|---|---|
| the law | one paragraph in CLAUDE.md THE LAWS |
| build · check over two releases of one scheme | BUILD REFUSED exit 2 · CHECK RED exit 1 (floor) |
| the bridge on a real skew | refused, exit 2; carried on request with the skew printed, exit 0 |
| the floor | `tests/test_release.py` 5 passed; whole floor green; `GRAPHY_STANDALONE_OK` |

## 30 · THE SECOND LANGUAGE — TypeScript onto the nine words, Hono as the tenant (2026-09-06 · issue 20)

`engine/graphy/adapters/typescript_ast.py`: tree-sitter parses, the producer maps onto the same
vocabulary the Python producer emits — module · func · class · method; imports · contains · calls
· inherits · decorates — and says each node's `module` and `role`, and names Node's built-ins as
the ecosystem's standard library. `smash` gained a producer table (`PRODUCERS`): one door per
ecosystem for how a corpus becomes records, where a scheme's source lives beside its dependencies
(`node_modules/<pkg>`: its `source` entry or a `src/` carrying `.ts`; a package shipping only
`dist/` is named unresolved, never parsed), and what the standard library is. The resolver needed
one word: `this` binds like `self`. Nothing downstream of the IR changed — the store, the walk,
the doors, pillars, arms and the bridge read the vocabulary and nothing else, which is what
issue 18 was for. tree-sitter is the `graphyos[typescript]` extra; the core stays dependency-free
and the producer refuses by name without it. `pillars` now skips every node the producer marks
`role: test` (Hono's tests sit beside its sources; SQLAlchemy's `testing/` package is marked the
same way), so a harness never crowns an arm. The rule is the docstring of the producer; the floor
is `tests/test_typescript.py`.

### The run on this box — Hono 4.13.7

```bash
cd engine; T=tenants/hono
time PYTHON=../.venv/bin/python bash $T/rebuild.sh
#   CHECKOUT: hono v4.13.7 at …/staging/corpora/ts/hono (eebdf7b)
#   RING: zod provisioned at …/staging/corpora/ts/hono_ring/node_modules     (npm install zod@4 — the one devDependency that ships TypeScript source; hono declares no runtime dependency)
#   MINT OK: hono 1174 nodes / 4596 edges          (310 files, 0.4 s)
#   MINT OK: zod 2250 nodes / 7154 edges
#   RING: 2 shard(s) · stdlib skipped 7 · unresolved benchmark, esbuild, jsdom, msw, recheck, seriousme__openapi_schema_validator, vitest, web_std__file
#   RESOLVE OK: hono 1983 label(s) -> 622 edge(s) (import 221 · local 341 · reexport 24 · self 36) · left as text: builtin 29 · missing 28 · unbound-attribute 21 · unminted 2 · unresolved 1281
#   RESOLVE OK: zod 3719 label(s) -> 1608 edge(s) (import 396 · local 1140 · self 72)
#   CONVERGE: 2 shard(s) · 1 wormhole edge(s) over 1 node(s)      hono -> zod  imports=1
#   BUILD OK: compiled 3424 nodes / 6239 edges      CHECK OK … container fresh for 2/2 shard(s)
#   FANOUT OK: 6 group(s) by partition (5 named, rest=EDGE)   FANOUT VERIFY: COHERENT
#   ARMS OK: 5 arm(s) match the walk
#   HONO_TENANT_OK        real 0m3.0s

python3 -m graphy walk --tenant $T/tenant.json --tenant-id hono --seed hono://class/hono.hono.Hono --target zod://module/zod --no-store
#   WALK PATH: … hops=3 … Hono -> hono.hono -> hono.validator.validator_test -> zod://module/zod     (the wormhole: the test imports zod)
python3 -m graphy walk … --seed hono://class/hono.hono.Hono --target hono://class/hono.router.trie_router.router.TrieRouter
#   WALK PATH: hops=2 … Hono -> Hono.constructor -> TrieRouter                                       (the resolver bound `new TrieRouter()` in the constructor)
python3 -m graphy bridge --tenant $T/tenant.json --tenant-id hono --tenant tenants/fastapi/tenant.json --tenant-id fastapi --join typing_extensions --seed … --target …
#   BRIDGE REFUSED: --join typing_extensions: no node under typing_extensions:// in tenant(s) hono — a join is a literal both sides carry …   exit 2
#   (no scheme is minted on both a Python and a TypeScript side today; the refusal is the evidence)

cd ..; rm -rf staging/quickstart/hono && time bash quickstart.sh https://github.com/honojs/hono.git
#   quickstart: npm install failed; the ring is whatever node_modules already holds     (hono's devDependency tree does not npm-install on this box; the message is printed, not hidden)
#   EAT: hono at …/hono/src -> …/hono/.graphy      (the producer chosen from package.json: no importable Python package)
#   MINT OK: hono 1174 nodes / 4596 edges · RING: 1 shard(s) · unresolved esbuild, jsdom, msw, vitest, zod
#   BUILD OK · CHECK OK · EAT OK · ESTATE OK · WALK PATH
#   GRAPHY_QUICKSTART_OK: hono eaten in 14.5s
```

The dist-only branch, on a scratch node_modules holding zod 4.5.4 from npm: `locate_node` finds
`node_modules/zod/src` (zod ships its source) and the floor's synthetic `dist-only` package is
named `… ships no TypeScript source (dist only)` in the ring receipt.

| check | result |
|---|---|
| the producer over hono's `src/` | 1174 nodes / 4596 edges in 0.4 s, valid against the vocabulary |
| the ring | zod minted beside it from node_modules; one `hono -> zod` wormhole; eight devDependencies named unresolved |
| the resolver on TypeScript | 622 labels bound (import · local · reexport · this); 1281 left as text, by reason |
| the tenant | HONO_TENANT_OK in 3.0 s; arms verified; five hand-cut arms with the walk's diff beside them |
| quickstart on the repo | GRAPHY_QUICKSTART_OK in 14.5 s cold |
| the bridge into Python | refused by name: no shared literal |
| the other tenants | FastAPI and SQLAlchemy rebuilt green, arms unchanged; SQLAlchemy's proposal no longer crowned by its test harness |
| the floor | `tests/test_typescript.py` 3 passed under `graphyos[typescript]`; whole floor green; `GRAPHY_STANDALONE_OK` |

## 31 · THE FARM — the top 500 PyPI packages in one content-addressed index (2026-09-06 · issue 21)

`graphy farm` is the loop around the proven pieces: for each package, a fresh venv holding exactly
one release and nothing else (`pip --no-deps --no-cache-dir`; the ring is the index, every dependency
its own entry, a tenant's roster naming one release per scheme by the law of §29), every importable
name the distribution's RECORD says it installed minted by `smash`, every shard pushed under
`<distribution>==<version>` (a second import name under `…@<import>`), the venv deleted. The index
is the state: a name the catalog holds is skipped, so a farm that stops resumes. A package that
cannot be minted is refused with its reason — no importable name (type stubs, extension-only or data
distributions), no final un-yanked release on PyPI, a smallest file over the wheel cap, pip's own
failure — and the farm goes on; `farm.json` carries every verdict. The rule is the docstring of
`engine/graphy/farm.py`; the floor is `tests/test_farm.py` with PyPI and pip injected.

### The run on this box — 8 cores, 32 GB, 6.7 GB of disk to start

```bash
cd engine
time python3 -m graphy farm --top 500 --index /abs/staging/index/farm --work /abs/staging/farm/top500 --jobs 8 --max-wheel-mb 100
#   FARM: 500 package(s) -> …/staging/index/farm with 8 job(s), producer python_ast, wheel cap 100.0 MB
#   FARM: six==1.17.0 minted 1 shard(s) in 0.6s -> six==1.17.0 (pushed)
#   FARM: attrs==26.1.0 minted 2 shard(s) in 0.6s -> attrs==26.1.0 (pushed), attrs==26.1.0@attr (pushed)
#   FARM REFUSED: torch==2.14.0: the smallest file is 124 MB, over the 100 MB cap
#   FARM REFUSED: types-requests==2.33.0.20260712: installs no importable package the producer reads (an extension-only, namespace or data distribution)
#   FARM REFUSED: opentelemetry-instrumentation: PyPI lists no final, un-yanked release   (its releases are all 0.NNbN betas — refused by the same rule refresh uses, never guessed)
#   …
#   FARM OK: minted 479 · skipped 0 · refused 21 · shards new 518 / already there 0 in 111.3s -> …/staging/index/farm (518 name(s))
#   refusals: 11 no importable package (types-* stubs, librt, ruamel-yaml-clib, …) · 8 no final release (the opentelemetry betas) · 2 over the cap (torch, and one more)
python3 -m graphy index --index /abs/staging/index/farm --verify
#   INDEX OK: 518 named shard(s), 0 broken            (2.3 s; the index is 1.7 GB of JSON)

# served, pulled, and two tenants rebuilt from it alone — then bridged
(cd staging/index/farm && python3 -m http.server 8765 --bind 127.0.0.1 &)
python3 -m graphy pull requests==2.34.2 --index http://127.0.0.1:8765 --out /abs/tmp/pulled     # PULL OK: requests==2.34.2 (verified ac262454d475…; 310 nodes / 1776 edges)
python3 -m graphy push tenants/fastapi/substrate/*_graph --index /abs/staging/index/farm                               # the tenant's own 0.139.0 ring beside the farm's 0.141.1: two names, one release each
GRAPHY_SHARD_INDEX=http://127.0.0.1:8765 GRAPHY_PULL="fastapi==0.139.0 starlette==1.6.0 pydantic==2.13.5 pydantic_core==2.46.5 anyio==4.15.1 typing_extensions==4.16.0 typing-inspection==0.4.4 idna==3.19 annotated-types==0.8.0 annotated-doc==0.0.5" bash tenants/fastapi/rebuild.sh
#   PULL OK ×10 · ARMS OK: 4 arm(s) match the walk · FASTAPI_TENANT_OK        real 0m2.1s
GRAPHY_SHARD_INDEX=http://127.0.0.1:8765 GRAPHY_PULL="sqlalchemy==2.0.52 typing-extensions==4.16.0 greenlet==3.5.5" bash tenants/sqlalchemy/rebuild.sh
#   PULL OK ×3 · ARMS OK: 5 arm(s) match the walk · SQLALCHEMY_TENANT_OK      real 0m3.7s   (sqlalchemy and greenlet are the farm's own shards)
python3 -m graphy bridge --tenant tenants/fastapi/tenant.json --tenant-id fastapi --tenant tenants/sqlalchemy/tenant.json --tenant-id sqlalchemy --join typing_extensions --seed fastapi://func/fastapi.param_functions.Cookie --target sqlalchemy://class/sqlalchemy.orm.session.Session
#   JOIN typing_extensions: fastapi holds 241 node(s) at typing_extensions==4.16.0 · sqlalchemy holds 241 node(s) at typing_extensions==4.16.0
#   BRIDGE PATH: … hops=6 crossings=1        (the two sides pulled the literal under two catalog names — the tenant's push and the farm's — and the law reads the release, not the name)
```

The "another machine" clause: the pull and both rebuilds went through `http://127.0.0.1:8765`, a
`python3 -m http.server` over the index directory — the http lane end to end on one box. The
12-core box the operator has coming runs the same command with `--jobs 12`; the receipt and the
catalog say what it did.

| check | result |
|---|---|
| the top 500 | 479 minted · 21 refused with reasons · 518 shards · 111 s with 8 jobs |
| the index | `INDEX OK: 518 named shard(s), 0 broken`; 1.7 GB |
| pulled over http | PULL OK, byte-verified |
| FastAPI rebuilt from the index alone | FASTAPI_TENANT_OK in 2.1 s, arms match |
| SQLAlchemy rebuilt from the index alone | SQLALCHEMY_TENANT_OK in 3.7 s, arms match |
| the bridge across two index-built tenants | crossings 1, both sides at typing_extensions 4.16.0 |
| the floor | `tests/test_farm.py` 2 passed; whole floor green; `GRAPHY_STANDALONE_OK` |

## 32 · THE PUBLIC CUT — the census, the hashed scrub, and the split the operator runs (2026-09-06 · issue 22)

The scrub used to carry its own marker list, which is the one thing a scrub must not do: the
list is the leak. `scrub.py` hashes instead — every token of every file, single and adjacent-pair,
lowercased with spaces and underscores removed, against `.private_markers.sha256`; the words live
in no tracked file and the operator regenerates the hashes with `scrub.py --hash <word>…`. The
departure gate now sweeps twice: the staged engine tree, and every git-tracked file outside
`staging/`. The host-module probe reads its names from `.private_modules`, gitignored, and says
SKIPPED on a box without one. The early sections of this file, written against the private host
during the cold start, had the host's names in them; they now say "the host codebase", "the host
VM", "the operator" — the numbers are untouched. Four tests that spelled private names by
concatenation to assert their absence now spell neutral ones.

```bash
bash census.sh
#   directory               tracked  flagged
#   (root)                        9        0
#   .claude                       4        0
#   engine                      150        0
#   staging                     636     1910          ← the whole of the private language, and it does not travel
#   CENSUS OK: nothing tracked outside staging/ carries a private marker
python3 scrub.py --tracked          # SCRUB OK: 163 file(s), no private token
bash standalone_check.sh            # … prose scrub OK · GRAPHY_STANDALONE_OK
```

### The split — written here, run by the operator (issue 28)

`staging/` is the host tool folder, the cold-start docs and the manifest: development input,
never released, and 1910 lines of it are private. It does not make the cut, and neither does
this repository's history, which carried it. The public repo is a fresh one seeded from the
product and its record:

```bash
# from a clean checkout of this repo, at the commit the gate proved
bash census.sh && bash standalone_check.sh                     # both green, or stop
git init /tmp/graphy-public && cd /tmp/graphy-public
cp -r /path/to/graphy/{engine,README.md,CLAUDE.md,RECON.md,LICENSE,NOTICE,standalone_check.sh,quickstart.sh,scrub.py,census.sh,.private_markers.sha256,.gitignore} .
mkdir -p .claude && cp -r /path/to/graphy/.claude/hooks .claude/            # the march; skills and recovery stay behind
sed -i '/^staging\//d' .gitignore                                         # nothing under staging/ exists here
python3 scrub.py --tree . && bash standalone_check.sh                     # the gate on the cut itself
git add -A && git commit -m "graphy: the public cut" && gh repo create omnislash157/graphyos --public --source . --push
```

What stays behind: `staging/` (tools, docs, skills, the corpora and indexes), `.claude/recovery`,
`.claude/skills`, `.private_modules`, and this repo's history. What the cut needs from the
operator afterwards: the board's open issues re-filed on the public repo, `MARCH_REPO` pointed
at it, and the private repo kept as the archive it is.

| check | result |
|---|---|
| the census | 0 flagged outside `staging/`; 1910 inside it |
| the scrub over everything tracked outside `staging/` | SCRUB OK, 163 files |
| the gate | GRAPHY_STANDALONE_OK with the hashed scrub and the local module probe |

## 33 · CI — the floor and the gate on a machine that has never seen the host (2026-09-06 · issue 23)

The workflow lived at `engine/.github/workflows/ci.yml`, where GitHub does not read it, so no run
had ever existed. It now lives at the repo root: the floor on 3.10 and 3.12 with the `dev` and
`typescript` extras, and a third job that runs `standalone_check.sh` and `census.sh` — the same
two commands the constitution names, on a runner with no `.private_modules` (the host probe says
SKIPPED there, by design) and no host to reach.

```text
https://github.com/omnislash157/graphyos/actions/runs/34007625366   commit 07206ff   success
  floor (3.12)  success   23 s
  floor (3.10)  success   27 s
  gate          success   32 s   (the venv, the install, the floor again, the hashed scrub, the census)
```

| check | result |
|---|---|
| a run exists | the first, green on the first push |
| the matrix | 3.10 and 3.12 both green |
| the gate as CI | GRAPHY_STANDALONE_OK and CENSUS OK on the runner |

## 34 · RELEASE READINESS — 0.1.0 built and checked, the changelog derived, publishing left to the operator (2026-09-06 · issue 24)

`graphyos` is 0.1.0 in `pyproject.toml` and `graphy.__version__`. `release.sh` builds the wheel
and the sdist into `dist/` with the project's interpreter, runs `twine check` on both, and derives
`CHANGELOG.md` from this file's section titles — one line per section, the number re-deriving it
and the issue carrying the evidence. `release.sh --check` refuses when the changelog differs from
what RECON derives, and the departure gate runs it, so the one generated doc in git besides the
arm regions cannot drift. The README says what the product reads today (Python through the
standard library's parser, TypeScript with TSX through tree-sitter) and carries the PyPI install
line marked "after publish". Publishing is the one command `release.sh` prints last and never
runs (issue 29).

```bash
bash release.sh
#   Checking dist/graphyos-0.1.0-py3-none-any.whl: PASSED
#   Checking dist/graphyos-0.1.0.tar.gz: PASSED
#   RELEASE OK: graphyos 0.1.0 built and checked in dist/; CHANGELOG.md regenerated
#     publish (the operator's call, never run here):  .venv/bin/python -m twine upload dist/*
bash release.sh --check             # changelog OK   (also inside standalone_check.sh)
```

| check | result |
|---|---|
| the wheel and the sdist | built, `twine check` PASSED on both |
| CHANGELOG.md | 25 entries derived from RECON (every dated section; the cold-start sections carry no date); the gate refuses drift |
| the README's scope | Python + TypeScript, nothing more; the PyPI line marked after publish |

## 35 · THE ESTATE OVER THE INDEX — one question across every release the farm minted (2026-09-06 · issue 25)

`graphy estate --index <abs>`: every named shard in the catalog materialized once beside the
index as two parquets (`adj`: name · corpus · src · dst · edge_type · dst_repr · line; `nodes`:
name · corpus · id · kind · node_type · dotted · module · role · file · line · version) with a
receipt pinning the catalog's sha256, so a query is a read and never a load. The catalog moving
makes the estate STALE and every query refuses by name until `--emit` runs again. duckdb is the
`graphyos[estate]` extra. The rule is the docstring of `engine/graphy/index_estate.py`; the floor
is `tests/test_index_estate.py`.

```bash
cd engine; I=/abs/staging/index/farm
time ../.venv/bin/python -m graphy estate --index $I --emit
#   ESTATE EMITTED: 521 shard(s) · 848596 nodes · 5476524 edges in 28.2s -> …/farm/estate (catalog 61d6ce948470…)     83 MB of parquet from 1.7 GB of JSON
E="../.venv/bin/python -m graphy estate --index $I --sql"

$E "SELECT count(DISTINCT name) AS packages, count(*) AS import_edges FROM adj WHERE edge_type='imports' AND dst LIKE 'typing_extensions://%'"
#   156 packages · 7667 import edges                                             21 ms   (pydantic-ai-slim 152 · pydantic 113 · langchain-core 99 lead)
$E "SELECT coalesce(dst, dst_repr) AS base, count(DISTINCT name) AS packages, count(*) AS subclasses FROM adj WHERE edge_type='inherits' GROUP BY 1 ORDER BY packages DESC"
#   Exception 269 pkgs/1453 · Protocol 121/1172 · Enum 120/1322 · ValueError 112/344 · NamedTuple 107/672 · object 105/4709 · TypedDict 104/6318 · type 97/418      18377 rows, 44 ms
$E "SELECT name, count(*) AS calls FROM adj WHERE edge_type='calls' AND (dst_repr LIKE 'os.system(%' OR dst_repr LIKE 'subprocess.Popen(%' OR dst_repr LIKE 'subprocess.run(%') GROUP BY name ORDER BY calls DESC"
#   sentry-sdk 3 · sglang 2 · typer 2 · nodeenv 1 · click 1 · websockets 1     (six packages of 479 name those callees by their bare label)      24 ms
$E "SELECT name, count(*) AS nodes, sum(CASE WHEN role='test' THEN 1 ELSE 0 END) AS test_nodes FROM nodes GROUP BY name ORDER BY nodes DESC"
#   pandas 29983 (22868 tests) · litellm==1.101.0.dev1 29601 · scipy 24754 (15283 tests) · kubernetes 23733     6 ms

# the catalog moves (a name added), the estate refuses
#   ESTATE STALE: … 521 shard(s) …; run with --emit        exit 1
#   ESTATE REFUSED: the index estate … is STALE — the catalog moved since it was emitted   exit 2
```

Honest about the labels: `inherits` and `calls` targets across the index are the producers'
text labels (`dst_repr`), not resolved nodes — the farm mints, it does not converge, because the
ring is the index and resolution is a tenant's roster. So "Exception" counts every class that
spells `Exception` as its base, and "os.system(...)" counts the bare label; a package that
does `from os import system; system(…)` is not in that row. The resolved answer is a tenant
question: pull the shards, `converge --resolve`, `estate --tenant`. And the litellm row found a
defect: `1.101.0.dev1` passed the newest-final rule — issue 30.

| check | result |
|---|---|
| the emit | 521 shards · 848,596 nodes · 5,476,524 edges in 28.2 s, 83 MB |
| three questions | 21 ms · 44 ms · 24 ms, rows and leaders above |
| the catalog moving | STALE (exit 1) and REFUSED (exit 2) by name |
| the floor | `tests/test_index_estate.py` 2 passed under `graphyos[estate]` |

## 36 · JAVASCRIPT — the same producer reads CommonJS, and the ring reaches node_modules (2026-09-06 · issue 26)

The `typescript_ast` producer walks `.js/.jsx/.mjs/.cjs` beside the TypeScript suffixes (the TSX
grammar, JSX-safe), binds CommonJS the way it binds `import`: `const x = require('y')` is x bound
to the module, `const { a, b: c } = require('y')` binds names, `exports.X = require('y')` re-exports,
`require('debug')('express')` binds through the outer call; and reads the idiom that defines
Express — a function assigned to a member at module level (`app.listen = function …`,
`exports.query = function …`, `module.exports = function name …`) is a definition. A checkout
is read from its source with the build output skipped; a shipped package under node_modules,
which has no `src/`, is read from what it ships, `lib/` and `dist/` included. So the locator's
"dist only" refusal is gone: a package is refused only when it ships no TypeScript or JavaScript
at all. `require(...)` is a binding, never a call label. The rule is the producer's docstring;
the floor is `tests/test_typescript.py` (4 passed).

```bash
cd engine; T=tenants/express
time PYTHON=../.venv/bin/python bash $T/rebuild.sh
#   CHECKOUT: express v5.2.1 at …/staging/corpora/ts/express (dbac741)      RING: runtime dependencies installed at …/express/node_modules (npm install --omit=dev)
#   MINT OK: express 69 nodes / 398 edges          (lib/: app.* · req.* · res.* · utils · View — the member-assigned functions)
#   RING: 63 shard(s) · stdlib skipped 12 · unresolved error_cause, es_abstract, … (the dependencies' own devDependencies, not installed)
#   RESOLVE OK: express 290 label(s) -> 40 edge(s) (import 33 · local 7; 32 cross-shard)
#   CONVERGE: 63 shard(s) · 269 wormhole edge(s) over 62 node(s)
#   BUILD OK: compiled 774 nodes / 1268 edges     CHECK OK … container fresh for 63/63 shard(s)
#   ARMS OK: 4 arm(s) match the walk
#   PILLARS UNANSWERABLE: corpus 'express' has no orchestrator at depth 2 — … or it is one pillar     (it is; the curated partition cuts by module)
#   EXPRESS_TENANT_OK          real 0m2.5s
python3 -m graphy walk --tenant $T/tenant.json --tenant-id express --seed express://func/express.application.app.handle --target router://module/router --no-store
#   WALK PATH: hops=2 … app.handle -> express.application -> router://module/router        (the require binding, a wormhole into the ring)
python3 -m graphy descend app.handle --tenant $T/tenant.json --tenant-id express --depth 3
#   CROSSING express → finalhandler @hop1: app.handle ─calls▶ finalhandler://module/finalhandler     (`finalhandler(req, res, …)` resolved through the require binding)

cd ..; rm -rf staging/quickstart/express && time bash quickstart.sh https://github.com/expressjs/express.git
#   EAT: express at …/quickstart/express -> …/.graphy       (a package.json repo with no importable Python package: the producer chosen by the repo)
#   MINT OK: express 276 nodes / 922 edges  (the checkout root: index.js, lib/, examples/, test/ — tests marked role: test)
#   RING: 103 shard(s) · stdlib skipped 20 · unresolved benchmark, clone, … (devDependencies' devDependencies)
#   BUILD OK: compiled 2829 nodes / 4760 edges · EAT OK: express + 102 ring shard(s) · WALK PATH hops=3 into accepts
#   GRAPHY_QUICKSTART_OK: express eaten in 8.2s
```

The hono clause of the done check is unchanged by construction: hono's devDependencies do not
npm-install on this box (§30), so its ring receipt still names them "not under node_modules" —
the refusal that remains is the honest one, not the dist-only one, which no longer exists.

| check | result |
|---|---|
| the express tenant | 63 shards from node_modules, 269 wormholes, EXPRESS_TENANT_OK in 2.5 s, arms verified |
| the doors across the ring | walk into `router` in 2 hops; descend crosses into `finalhandler` |
| quickstart on the repo | GRAPHY_QUICKSTART_OK in 8.2 s, 103 shards |
| the floor | `tests/test_typescript.py` 4 passed (require · destructuring · re-export · member-assigned functions · a package with no source refused by name) |

## 37 · THE NPM FARM — the same verb over the other ecosystem (2026-09-06 · issue 27)

`graphy farm --producer typescript_ast`: npm has no top-N endpoint, so the candidates are the
"most dependent upon" sections of npmrank's sample lists (two files, 152 unique names) ranked by
npm's own last-month download counts fetched in bulk, and the top N is today's downloads over
that set. Per package: `npm install --prefix <job> --omit=dev --ignore-scripts` of exactly
`name@version` (the registry's `latest` dist-tag, or the one named; the unpacked size against the
cap), the package minted from what it ships (§36), pushed under its slug (`left_pad==1.3.0`; a
scoped name has a `/` the index name cannot carry, the PROVENANCE keeps the real name), the job
directory deleted. The same receipt, the same resume, the same refusals with reasons.

```bash
cd engine
time ../.venv/bin/python -m graphy farm --producer typescript_ast --top 200 --index /abs/staging/index/farm --work /abs/staging/farm/npm200 --jobs 8 --max-wheel-mb 50
#   FARM: ansi_styles==7.0.0 minted 1 shard(s) in 0.5s · chalk==6.0.0 · ms==2.1.3 · semver==7.8.5 · debug==4.4.3 · strip_ansi==7.2.0 · minimatch==10.2.6 · …
#   FARM REFUSED: aws_sdk==2.1693.0: unpacked size 98 MB, over the 50 MB cap
#   FARM REFUSED: wix_gruntfile==1.1.0: npm install exited 1 (four more like it: packages whose install fails on the registry today, named and skipped)
#   FARM OK: minted 194 · skipped 0 · refused 6 · shards new 194 in 224.6s -> …/staging/index/farm (715 name(s))     real 3m46s
../.venv/bin/python -m graphy index --index /abs/staging/index/farm --verify
#   INDEX OK: 715 named shard(s), 0 broken                                    (521 Python + 194 npm)

# hono rebuilt from the index alone, over http
python3 -m graphy push tenants/hono/substrate/*_graph --index /abs/staging/index/farm            # hono==4.13.7 · zod==4.5.4 beside the farm's names → 717
GRAPHY_SHARD_INDEX=http://127.0.0.1:8765 GRAPHY_PULL="hono==4.13.7 zod==4.5.4" PYTHON=../.venv/bin/python bash tenants/hono/rebuild.sh
#   PULL OK ×2 · ARMS OK: 5 arm(s) match the walk · HONO_TENANT_OK       real 0m1.7s
```

Honest about the first run: the parser took every numbered entry of npmrank's `dependencies.md`,
and that file goes on past the "most dependent upon" section to list the packages *with* the
most dependencies — so the tail of the 200 was that opposite ranking (`sagemathcloud`,
`wix-gruntfile`, gulp-task bundles), minted legitimately and refused honestly where npm refused
them. The parser now reads only the "most dependent upon" sections of both sample files (152
candidates: semver, minimatch, debug, chalk, commander, glob, … at the top), and the floor pins
that. Those 194 entries stay in the index — every one a real release at a real address — and the
next run skips what it holds. The candidate set is still a 2016 sample ranked by 2026 downloads;
a maintained top-N source for npm is the operator's to name.

| check | result |
|---|---|
| the run | 194 minted · 6 refused with reasons · 224.6 s with 8 jobs, ~0.5 s a package after the install |
| the index | 717 names, INDEX OK, 0 broken |
| hono from the index alone | HONO_TENANT_OK in 1.7 s over http, arms match |
| the floor | `tests/test_farm.py` 3 passed (the npm ranking, the cap, the registry refusal, the slug name) |

## 38 · THE FINAL-RELEASE RULE — a .dev release is not final (2026-09-06 · issue 30)

`latest_release` filtered PyPI's releases by the pre-release field alone, so `1.101.0.dev1` — no
a/b/rc segment, a `.dev1` suffix — read as final and the farm minted it (§35 found it). The rule
is now `is_final`: PEP 440's final release has no a/b/rc segment and no `.devN`; a post-release
of a final is final; garbage is not. `latest_release` picks the newest of those, and refuses by
name when a distribution has only pre-releases (the opentelemetry betas of §31, unchanged).

```bash
cd engine
printf 'litellm\n' > /abs/staging/farm/litellm.txt
../.venv/bin/python -m graphy farm --packages /abs/staging/farm/litellm.txt --index /abs/staging/index/farm --work /abs/staging/farm/litellm --jobs 1
#   FARM: litellm==1.100.0 minted 1 shard(s) in 12.0s -> litellm==1.100.0 (pushed)         (PyPI's finals: 1.100.0; 1.101.0.dev1, .dev2 and rc1 are not)
#   FARM OK: minted 1 … -> …/staging/index/farm (718 name(s))
```

The old name `litellm==1.101.0.dev1` stays in the catalog: the index has no delete verb, an
entry is a real release at a real address, and the version-identity law makes it harmless — a
roster names one release per scheme, and this one names 1.100.0. Removing it is the operator's
call; the receipt names it.

| check | result |
|---|---|
| `is_final` | dev · a · b · rc refused, post admitted; the floor pins it (`tests/test_refresh.py`) |
| litellm re-farmed | 1.100.0 minted and pushed; 718 names |

## 39 · THE SPLIT RAN — graphyos is public; PyPI waits on a token (2026-09-06 · operator's word)

The operator said the word, and §32's split ran as written: every tracked file outside
`staging/` (and the skills) copied into a fresh tree, the repo URLs repointed to `graphyos`,
the scrub swept every file of the cut, the departure gate ran inside it, one commit, and
`gh repo create omnislash157/graphyos --public --push`. The public repo's first CI run was green
on all three jobs. This repository stays private as the archive; its board is closed and the
march points at the public one (`MARCH_REPO`).

```text
https://github.com/omnislash157/graphyos            PUBLIC · 176 files · SCRUB OK · GRAPHY_STANDALONE_OK inside the cut
first CI run: floor (3.10) · floor (3.12) · gate — success
```

PyPI did not run: no token on this box (no `~/.pypirc`, no `TWINE_*`, no keyring backend). The
wheel and the sdist are built and checked; the publish is one command with a credential, and it
is issue 1 on the public board.

## 40 · DRAW — the codebase drawn mechanically from the store (2026-09-06 · graphyos issue 2)

`graphy draw` is the visual half of the product: the pillars, the unit map, one arm of the
partition, or a symbol's neighbourhood, computed from the compiled store (a query — `owned`,
`edges`, `neighbours` — never a shard load), laid out by the sugiyama engine (cycle removal →
layering → crossing minimization → coordinates), and rendered two ways from the same routes:
ASCII on a wcwidth canvas for the terminal, and one self-contained two-theme HTML+SVG page for a
human, with click-focus reachability, zoom and pan, no library, no external resource, no brand.
`--check` is the done-token over a written page (one svg with a viewBox, both themes, nothing
fetched, no overlapping cards, no colliding labels) and `-o page.html` runs it on the way out.
`--atlas` writes every picture with a receipt; the four rebuilds land it at `substrate/atlas/`.
The MCP server gained `draw`, so a model hands the human the picture with no work of its own
(the demo enumerates the tool list, so it carries it). The engine's `sugiyama.py` gained the
host's html emitter and check, ported with a neutral skin; its layout core was already the same.
The rule is the docstring of `engine/graphy/draw.py`; the floor is `tests/test_draw.py`.

```bash
cd engine; T=tenants/fastapi
python3 -m graphy draw --tenant $T/tenant.json --tenant-id fastapi --corpus fastapi --pillars --partition $T/partition.json --lr
```
```text
  fastapi · the pillars   5 layers · 5 nodes · 10 edges · 0 unconnected · [LR]

┌────────────────────┐┌─────────────────────────────────────────────────────────────────────────────┐    ┌────────────────┐
│ OPENAPI (39→ ·→24) ├┤                                                                             └╪╪┌◀│ EDGE (7→ ·→17) │
└────────────────────┘├──────────────────────┐  ┌─────────────────────────┐┌─────────────────────────╪┘│ └────────────────┘
                      │                      └┌▶│ DEPENDENCIES (68→ ·→23) ├┤                         │ │
                      ├──────────────────────┐│ └─────────────────────────┘│   ┌───────────────────┐ │ │
                      │                      ││                            └┌┌◀│ COMPAT (5→ ·→132) ├─┘ │
                      │ ┌───────────────────┐└╪─────────────────────────────┘│ └───────────────────┘   │
                      └◀│ ROUTING (84→ ·→7) ├─┤                              │                         │
                        └───────────────────┘ ├────────────────────────────┌─╪─────────────────────────┘
                                              │                            │
                                              └────────────────────────────┘
```
The numbers on each pillar are its cross-arm edges out and in; COMPAT is the floor everything
reaches (132 in, 5 out), ROUTING orchestrates (84 out). The same command over hono and express
draws their pillars the same way — the language is not in the drawing.

```bash
python3 -m graphy draw … --arm ROUTING --partition $T/partition.json --lr --min-weight 2        # routing · applications · sse and the arms they reach, 7 nodes
python3 -m graphy draw … --symbol get_request_handler --radius 1 --lr                          # 23 nodes: the callers on the left, the callees on the right, each ·owner
python3 -m graphy draw … --corpus fastapi --lr --min-weight 3 --emit html --interactive -o page.html
#   DRAW OK: 13 node(s) · 23 edge(s) · 60 under the weight floor -> page.html · CHECK GREEN       21 KB, no private token
bash $T/rebuild.sh   # … ATLAS OK: 6 picture(s) × ascii+html -> $T/substrate/atlas · FASTAPI_TENANT_OK
```

| check | result |
|---|---|
| the pillars drawn | FastAPI's four (and EDGE) from the store; hono's five; express's four |
| the html page | CHECK GREEN, 21 KB, self-contained, no private token |
| the atlas in every rebuild | fastapi 6 · sqlalchemy 6 · hono 7 · express 6 pictures, ascii+html, receipted |
| the MCP tool | `draw` answers with the ASCII and its read count |
| the floor | `tests/test_draw.py` 3 passed; `test_sugiyama.py` and `test_mcp.py` green |

## 41 · THE ONE-LINER — pip install graphyos, then graphy eat . (2026-09-06 · graphyos issue 3)

`graphy eat .` is the whole of the stranger's second line. With no `--site-packages`, eat
provisions the repo's own dependencies beside it and says what it did: a Python repo gets
`<repo>/.graphy/venv` with `pip install <repo>` — the repo's own metadata is the declaration of
its ring; a `package.json` repo gets `npm install --ignore-scripts` into its node_modules. A repo
that will not install is minted alone and the line names why (`PROVISION PARTIAL: …`), never
silently. `--site-packages` still wins when named. The repo is a positional (`.` for the one you
stand in), resolved and printed. Eat ends with what a stranger does next: the MCP block for
Claude Code or Cursor (the model is theirs, the walk is graphy's), the drawing, three questions.
`quickstart.sh` is now the two lines. The rule is the docstring of `engine/graphy/provision.py`;
the floor is `tests/test_provision.py` with pip and npm injected.

### The cold run — a fresh venv, the wheel, three fresh clones, on this box

```bash
python3 -m venv cold/venv && cold/venv/bin/pip install dist/graphyos-0.1.0-py3-none-any.whl tree-sitter tree-sitter-typescript
git clone --depth 1 https://github.com/encode/httpx.git cold/httpx && cd cold/httpx && graphy eat .
#   EAT: repo …/cold/httpx
#   PROVISION: …/cold/venv/bin/python3 -m venv …/httpx/.graphy/venv · PROVISION: …/.graphy/venv/bin/python -m pip install … …/cold/httpx
#   PROVISION OK: pip install httpx into …/httpx/.graphy/venv
#   RING: 7 shard(s) · stdlib skipped 62 · unresolved _pytest, brotli, click, …          EAT OK: httpx + 6 ring shard(s)
#   ADD YOUR MODEL — paste this into .mcp.json … {"mcpServers": {"graphy": {"command": "…/venv/bin/graphy", "args": ["mcp", "--tenant", "…/.graphy/tenant.json", "--tenant-id", "httpx"]}}}
#   SEE IT   graphy pillars … --write .graphy/partition.json · graphy draw … --pillars … --lr · graphy draw … --emit html --interactive -o .graphy/map.html
#   ASK IT   graphy blast <symbol> … · graphy descend <symbol> … · graphy walk … --seed httpx://module/httpx --target certifi://module/certifi
#   4.3 s
… hono:    PROVISION PARTIAL: npm install failed (npm error Cannot read properties of null (reading 'edgesOut') …) — the ring is whatever node_modules already holds
#          EAT OK: hono + 0 ring shard(s)        12.6 s   (an npm defect on this box against hono's lockfile, named, not hidden)
… express: PROVISION OK: npm install into …/express/node_modules · RING: 103 shard(s) · EAT OK: express + 102 ring shard(s)        6.6 s
bash quickstart.sh https://github.com/expressjs/express.git     # the two lines → GRAPHY_QUICKSTART_OK: express eaten in 8.4s
```

| check | result |
|---|---|
| the wheel in a fresh venv, `graphy eat .` in fresh clones | httpx 4.3 s · express 6.6 s (103 shards) · hono 12.6 s with the npm failure named |
| what eat prints last | the MCP block, three SEE IT commands, three ASK IT commands |
| the quickstart | two lines, GRAPHY_QUICKSTART_OK in 8.4 s |
| the floor | `tests/test_provision.py` 3 passed |

## 42 · THE SHOWCASE — one page of a stranger's codebase, made by one command (2026-09-06 · graphyos issue 4)

`graphy showcase <git url | path>` is the marketing asset generated per repo, and it is computed:
clone shallow when a url, eat when no `.graphy/` stands (the one-liner's path), propose the
pillars from the walk (a stranger's repo has no curated partition, so the proposal is the cut,
written to `.graphy/partition.json`), draw the module map and the pillars, and write
`.graphy/showcase/index.html` — the interactive modules drawing (click a module, what reaches it
and what it reaches light up), the pillars in ASCII with each arm's crown and the evidence that
placed it, the ring and what it could not carry, the MCP block to paste into Claude Code or
Cursor, three questions chosen from the crowns, and how it was made — plus `showcase.txt`, the
same as plain text for a README or a post. The page passes the draw check and fetches nothing.
A package the walk rules one pillar gets a page that says so. For a TypeScript or JavaScript
checkout, the producer now skips `examples/`, `benchmarks/` and `docs/` (a checkout is read from
its source; a shipped package from what it ships), which is what put express's examples at the
top of its first page. `quickstart.sh` runs it as its last line. The rule is the docstring of
`engine/graphy/showcase.py`; the floor is `tests/test_showcase.py`.

```bash
cd cold/httpx && graphy showcase .
#   SHOWCASE OK: httpx · 3 arm(s) (MODELS, CLIENT, EXCEPTIONS) · 6 ring shard(s) · CHECK GREEN · 0.1s
#     the page:  …/httpx/.graphy/showcase/index.html      33 KB, self-contained
#     the text:  …/httpx/.graphy/showcase/showcase.txt    12 KB
#   THE ARMS
#     MODELS       crown httpx._models       5 unit(s) — crown — fan-out at least half the leader's (56)
#     CLIENT       crown httpx._client       8 unit(s) — crown — fan-out at least half the leader's (56)
#     EXCEPTIONS   crown httpx._exceptions   3 unit(s) — the floor's crown — the greatest fan-in (50) no arm owns (MODELS 33, CLIENT 16)
cd ../hono && graphy showcase .        # SHOWCASE OK: hono · 6 arm(s) (MIDDLEWARE, HELPER, ADAPTER, PRESET, VALIDATOR, UTILS) · CHECK GREEN · 0.0s
cd ../express && graphy showcase .     # SHOWCASE OK: express · 1 arm(s) (EXPRESS) · 85 ring shard(s) · CHECK GREEN — "one pillar", said on the page
bash quickstart.sh https://github.com/encode/httpx.git
#   GRAPHY_QUICKSTART_OK: httpx eaten in 5.2s -> …/httpx/.graphy  (the page: …/httpx/.graphy/showcase/index.html)
```

| check | result |
|---|---|
| three showcases, cold | httpx 3 arms · hono 6 arms · express one pillar; every page CHECK GREEN in ~0.1 s after the eat |
| what a stranger reads | the drawing, the arms with evidence, the ring, the MCP block, three questions, the two-line recipe |
| the quickstart | ends at the page, 5.2 s for httpx |
| the floor | `tests/test_showcase.py` 2 passed; `test_typescript.py` green with the checkout excludes |

## 43 · THE RECEIPT — every number, one command, a before and an after (2026-09-06 · graphyos issue 5)

`python3 measure.py run` re-derives what this file carries into `recon.json`: the floor (passed ·
failed · skipped · seconds), the gate (verdict · seconds), the wheel and the sdist (bytes), every
tenant's rebuild (verdict · seconds · shards · nodes · edges · arms · atlas), the two pinned
quickstarts (verdict · seconds · ring), the index (names · broken · verify seconds). `--quick` is
the floor, the gate and the wheel — what CI runs on every push to main and stores as an artifact.
`measure.py diff OLD NEW` prints every number that moved with its direction, and exits 1 on a
regression: a time past 15%, a count moved the wrong way, a verdict flipped to false. That is the
improvement gate's before-and-after; the burden invariants are issue 6.

Building it found two defects the gate had never run, because the gate's venv had no duckdb:
`graphy check` crashed on an unreadable shard when a container stood beside it (now a
COULD-NOT-TELL finding, and a missing shard is "no container"), and the container's row test
predated the producer's `module` field. The gate now installs `[dev,typescript,estate]`, so the
duckdb paths are on the floor.

```bash
time python3 measure.py run --out recon.json
#   MEASURE OK: floor 449 passed / 0 failed in 14.7s · gate OK 20.4s · wheel 260270 B
#     · tenants fastapi=OK/4.2s sqlalchemy=OK/8.7s hono=OK/3.0s express=OK/2.6s · quickstart httpx=OK/5.3s express=OK/9.3s · 73.8s -> recon.json
python3 measure.py diff recon.first.json recon.json
#   … wheel.seconds: 2.7 -> 3.1 ↑+15% · wheel.wheel_bytes: 260154 -> 260270 ↑+0%
#   MEASURE DIFF OK: 13 number(s) moved, none the wrong way past tolerance
#   (the run before the fixes said: MEASURE REGRESSION — floor.failed 0 -> 1; gate.ok flipped to false — the receipt named it before a human did)
```

| check | result |
|---|---|
| the receipt | 74 s for everything on this box; the floor 449 passed with duckdb on |
| the diff | names movement and direction; a doctored regression exits 1 (`tests/test_measure.py`) |
| CI | `measure.py run --quick` on every push, recon.json an artifact per commit |
| what it found | two duckdb-path defects, fixed |

## 44 · THE BURDEN INVARIANTS — what the engine may lean on, refused by name when it grows (2026-09-06 · graphyos issue 6)

`burden.json` is the list; `burden.py` is the refusal; the gate runs it. Runtime dependencies stay
at zero and the extras carry only their declared names (`dev`: pytest · `estate`: duckdb ·
`typescript`: tree-sitter, tree-sitter-typescript); the wheel stays under 400 KB; every network
host the engine names is one of six (pypi.org, the two npm hosts, the top-packages list, raw
github, github); every program the engine runs is one of six (git · npm · rg · python · pip ·
venv) — a direct call names it, a local list is resolved to its head, a function whose command is
a parameter is a runner and every call of it is checked, and the one function that runs a
tenant's *declared* build lane as declared is named a delegate, the tenant's responsibility;
every tracked document under `engine/` is an arm file carrying its generated region or on the
list; the hashed scrub over everything tracked. A change that adds a responsibility adds it to
`burden.json` in the same commit, where a human reads it. With the receipt (§43) this is the
improvement gate the operator asked for: a change may not add a burden, and it must move a number.

```bash
python3 burden.py
#   BURDEN OK: runtime deps 0 · extras 3 · wheel: 260270 B (cap 400000) · hosts 7 on the list of 6 · subprocess sites 24 over 6 program(s) · docs 27 tracked · scrub OK
# a doctored growth (the floor, tests/test_burden.py):
#   BURDEN RED graphy/a.py:3: host evil.example is not in burden.json
#   BURDEN RED graphy/a.py:15: subprocess target 'curl' is not in burden.json
#   BURDEN RED pyproject.toml: runtime dependency 'requests>=2' — the engine leans on nothing; burden.json says which
```

| check | result |
|---|---|
| on main | BURDEN OK: 0 runtime deps · 24 subprocess sites over 6 programs · 7 host literals on the list · 27 tracked docs declared |
| the refusals | a dependency, an extra, a host, a program, an oversized wheel — each named with its file and line |
| the gate | runs it after the changelog check; CI runs the gate |

## 45 · GRAPHY EATS GRAPHY — the engine as its own tenant, a diff's blast radius from the walk (2026-09-06 · graphyos issue 7)

`engine/tenants/graphy/`: the engine minted by its own producer from `engine/graphy/`, the ring
followed into the interpreter's site-packages (duckdb, tree-sitter, tree-sitter-typescript,
typing_extensions), and the floor minted beside it as a sibling shard (`tests_graph`) whose
imports of graphy are wormholes into the package — so `explain` names the tests that reach a
symbol. Six arms cut from the engine map; the walk crowns `cli` over everything (fan-out 106,
every other unit its foundation) with the memory lane the one floor no arm consumes, and the
router says so. `blast_pr.py <base> <head>` maps every changed line under `engine/graphy/` to the
symbol the store places there, blasts each (what depends on it, transitively), names the tests
that reach it and the arm it lands in, and prints one comment; `.github/workflows/blast-on-pr.yml`
posts it on every pull request. The walk decides every line of it.

```bash
cd engine; time bash tenants/graphy/rebuild.sh
#   MINT OK: graphy 922 nodes / 10063 edges · duckdb 792 · tree_sitter 3 · tree_sitter_typescript 3 · typing_extensions 241 · tests 610 nodes / 5001 edges
#   RESOLVE OK: graphy 8535 label(s) -> 1573 edge(s) (import 363 · local 1197 · reexport 2 · self 11)
#   CONVERGE: 6 shard(s) · 1149 wormhole edge(s) over 209 node(s)        (the floor's imports into the package)
#   BUILD OK: compiled 2571 nodes / 6358 edges · CHECK OK · ARMS OK: 6 arm(s) · ATLAS OK: 8 picture(s)
#   GRAPHY_TENANT_OK        real 0m2.3s
../.venv/bin/python tenants/graphy/blast_pr.py HEAD~3 HEAD --limit 3
#   BLAST RADIUS of HEAD~3..HEAD — 254 changed line(s) in 5 file(s) land in 14 symbol(s)
#     graphy://func/graphy.sugiyama.emit_svg   [CUT]   lines graphy/sugiyama.py:1064, …
#       depends on it: 8 in graphy (depth 3)   hop1 sugiyama.emit_html · hop1 showcase.compose · hop2 draw.render …
#       tests that reach it: tests.test_showcase.test_GREEN_compose_writes_a_checked_page_and_text, tests.test_draw.test_GREEN_html_page_checks_green_and_a_doctored_one_red, …
#     graphy://func/graphy.cli._cmd_showcase   [CLI]   depends on it: 0 in graphy   tests that reach it: none the store carries      ← a gap the radius names
#   in all: N symbol(s) of graphy depend on what changed; the arms touched: CLI, CUT
```

| check | result |
|---|---|
| the tenant | GRAPHY_TENANT_OK in 2.3 s; 6 shards; 6 arms verified; 8 pictures |
| the radius of the last three commits | 14 symbols, each with its dependents, its tests and its arm; two symbols with no test the store carries, named |
| the PR workflow | https://github.com/omnislash157/graphyos/pull/9 — a one-line docstring on `draw._short`; the runner rebuilt the tenant and posted: 7 dependents in graphy, 2 in the ring, 2 tests that reach it, the CUT arm (run 34038018450, success) |

## 46 · INBOUND IN THE BACKGROUND — the issue lane and the PR gate (2026-09-06 · graphyos issue 8)

Two workflows on the public repo, no model in either. `showcase-on-issue.yml`: an opened issue
that names exactly one https git url (github.com or gitlab.com) gets its repo showcased on the
runner — clone, eat, propose, draw, capped at fifteen minutes — and `showcase.txt` posted back
with the two-line recipe; a refusal posts the tool's line, never a stack; an issue with no url or
two is left alone. `gate-on-pr.yml`: every pull request runs the burden invariants and the quick
receipt on the head and on the base, measured on the same runner, and posts the verdict and the
diff; a red burden or a regression past tolerance fails the check. With `blast-on-pr.yml` (§45)
a pull request now arrives with its radius, its burden and its numbers before a human reads it.

```text
issue 10  "showcase test: httpx"            run 34038104838 success — the comment: httpx's pillars in ASCII (MODELS · CLIENT · EXCEPTIONS), the arms with evidence, the ring, the MCP block, three questions, the recipe
pr 11     "dry run: the gate on a pull request"  run 34038105991 success — BURDEN OK · receipt base → head: floor.seconds 17.4 -> 19.6 ↑+13% (within tolerance) … wheel.seconds ↓-11% better · MEASURE DIFF OK: 6 number(s) moved, none the wrong way
```

| check | result |
|---|---|
| the issue lane | https://github.com/omnislash157/graphyos/issues/10 — the showcase posted from a fresh runner |
| the PR gate | https://github.com/omnislash157/graphyos/pull/11 — burden and receipt posted; the check green |
| what a PR carries now | the blast radius, the burden verdict, the receipt diff — three comments from the tool |

## 47 · PUBLISHED — graphyos 0.1.0 on PyPI by trusted publishing (2026-09-07 · graphyos issue 1)

The operator registered a pending publisher on pypi.org (owner `omnislash157`, repository
`graphyos`, workflow `release.yml`, environment `pypi`); `release.yml` builds the wheel and the
sdist from `engine/` on a `v<version>` tag, refuses a tag that is not the version in
`pyproject.toml`, checks both with twine, and publishes by OIDC — no token exists anywhere.
The tag `v0.1.0` on the public repo ran it: build success, publish success, the project created.

```bash
python3 -m venv venv && venv/bin/pip install 'graphyos[estate,typescript]'      # from PyPI, 1.1 s
git clone --depth 1 https://github.com/encode/httpx.git && cd httpx && graphy eat . && graphy showcase .
#   PROVISION OK: pip install httpx into …/.graphy/venv · EAT OK: httpx + 6 ring shard(s)        5.2 s
#   SHOWCASE OK: httpx · 3 arm(s) (MODELS, CLIENT, EXCEPTIONS) · 6 ring shard(s) · CHECK GREEN
```

| check | result |
|---|---|
| the run | https://github.com/omnislash157/graphyos/actions/runs/34068845540 — build · publish, success |
| PyPI | `graphyos 0.1.0`, the wheel listed |
| a stranger's two lines | install from PyPI 1.1 s; eat a fresh httpx clone 5.2 s; the showcase page green |

## 48 · THE OPTIMIZATION PASS — the contract, the instrument, the first profile table (2026-09-07 · graphyos issue 12)

**The contract.** An `optimization` issue lands only when `burden.json` is unchanged or smaller
(`python3 burden.py`), `measure.py diff BEFORE AFTER` exits 0 and names the mover, every pinned
receipt (fixture parity · `graphy arms --verify` · the fanout and atlas receipts · the index verify)
reads identical unless the issue says which bytes move and why, and the floor's count holds on both
interpreters. **The termination** is mechanical: the pass ends when `pass.engine_hot_lanes` reads 0 —
no lane's top self-time frame lives under `graphy/`.

**The instrument.** `GRAPHY_PROFILE_DIR=<dir>` makes every `graphy` verb run under `cProfile` and
leave `<verb>-<pid>.prof` + `.json` (verb · argv · seconds · `rss_kb`, its own peak resident set)
there; unset, nothing is imported for it. A process under the profiler names itself in
`GRAPHY_PROFILE_PID`, so a verb called in-process by another (eat → smash; a test under the floor's
profiler) is not profiled twice — cProfile does not nest and the nested stats came back empty — while
a child process still is. `measure.py run` runs every timed lane a second time under it (the timed
run is never the profiled one; `profile_seconds` is carried and never judged) and lands per lane:
`hot` (the three top self-time frames, engine-owned ones marked), `rss_kb` + `rss_verb`,
`stdlib_hot`. `rss_kb` regresses like a time. `--no-profile` skips the second runs.

**One caveat the table carries.** cProfile sees a compiled extension's method as its Python caller's
self-time: `container._write_parquet` owns the seconds duckdb spends inside `con.execute`. That is
still the engine's lane to answer for — the writer chose one connection, one JSON feed and one COPY
per shard — so the rule stands as written and the caller is the target.

```bash
python3 measure.py run --out recon.json
#   MEASURE OK: floor 455 passed / 0 failed in 14.9s · gate OK 24.4s · wheel 261058 B
#     · tenants fastapi=OK/4.7s sqlalchemy=OK/8.8s hono=OK/2.9s express=OK/2.5s graphy=OK/2.9s
#     · quickstart httpx=OK/5.9s express=OK/6.4s · engine-hot lanes 5 · 79.0s -> recon.json   (profile_seconds 77.1)
python3 -c "import json;r=json.load(open('recon.json'));print(r['pass']);[print(k,v['hot'],v['rss_kb']) for k,v in r['tenants'].items()]"
GRAPHY_PROFILE_DIR=/tmp/p python3 -m graphy explain sqlalchemy.orm.session.Session --tenant engine/tenants/sqlalchemy/tenant.json --tenant-id sqlalchemy; ls /tmp/p
```

The first profile table — the board for the pass, re-derived by the first command above:

| lane | seconds | peak RSS (verb) | hottest frame | engine hot |
|---|---|---|---|---|
| floor | 14.9 | 156 MB (build) | `container._write_parquet` 4.83 s · `sqlite3.executescript` 4.53 s · `_thread.lock.acquire` 2.70 s | yes |
| fastapi | 4.7 | 165 MB (build) | `container._write_parquet` 0.67 s · `ast.iter_child_nodes` 0.51 s · `isinstance` 0.50 s | yes |
| sqlalchemy | 8.8 | 298 MB (build) | `json.raw_decode` 1.48 s · `container._write_parquet` 1.19 s · `ast.iter_child_nodes` 1.02 s | no |
| hono | 2.9 | 148 MB (build) | `tree_sitter.Parser.parse` 0.50 s · `container._write_parquet` 0.38 s · `json.raw_decode` 0.22 s | no |
| express | 2.5 | 129 MB (build) | `duckdb.connect` 0.36 s · `container._write_parquet` 0.22 s | no |
| graphy | 2.9 | 155 MB (build) | `container._write_parquet` 0.38 s · `ast.iter_child_nodes` 0.34 s · `json.raw_decode` 0.31 s | yes |
| quickstart httpx | 5.9 | 154 MB (eat) | `container._write_parquet` 2.81 s · `select.poll` 1.20 s (pip) | yes |
| quickstart express | 6.4 | 146 MB (eat) | `container._write_parquet` 6.58 s over 85 ring shards | yes |
| index verify | 2.5 | 175 MB | `sha256` 2.08 s | no |

What it says: the parquet emit beside every shard is the engine's hottest frame in five of nine lanes
and costs the express quickstart more than the mint did (graphyos issue 21, filed from this table);
`json.raw_decode` in the sqlalchemy and graphy lanes is the freshness digest's parse (issue 13);
`ast.iter_child_nodes` + `isinstance` is the producer's repeated walk (issue 14); the floor's
`executescript` is the store's schema per test store and its `lock.acquire` is the seat-lock wait
(issue 19). The gate's number spans 21.4–25.0 s across five runs this session with no code change
between them: its `pip install` into a fresh venv is network-bound, so its 15% tolerance sits inside
that noise on this box; on CI the base and the head run on one runner back to back, which is the
diff that gates.

| check | result |
|---|---|
| the hook | one `.prof` + `.json` per verb; two in-process calls under one profiler leave one; unset leaves nothing (`tests/test_measure.py`) |
| the summarizer | the hot frames, the heaviest verb's RSS, engine-owned marked; an empty stats file is named under `unreadable`, never a crash |
| the pass number | `pass.engine_hot_lanes` 5 of 9 lanes, with the lanes named; `stdlib_hot` flipping to false is a regression |
| the receipt | 79.0 s timed + 77.1 s profiled; the graphy tenant's CLI arm re-rendered (the walk moved: `_main` · `_profiled`), ARMS OK |
| found on the way | `CHANGELOG.md` had stopped at §38: every section since the split says `graphyos issue N` and `release.sh` read only `issue N`; the pattern widened, 38 entries, the public board's sections tagged `graphyos #N` |

## 49 · THE FRESHNESS CHECK IS A HASH — the bytes, never a parse; one parse per shard per process (2026-09-07 · graphyos issue 13)

**What it was.** `open_for` measured the store's freshness by loading every shard's JSON and
re-serializing it with `sort_keys=True` to hash — a full load per question, 0.26 s of a 0.30 s
`explain` on SQLAlchemy and the `json.raw_decode` line in §48's table. The law's own words say
a walk is a query, never a load.

**What it is.** `native_json_graph_ir.shard_input_digest` hashes the BYTES of `nodes.json`,
`edges.json` and `wormhole_edges.json` (its absence hashed as absent) — `hashlib`, a 1 MB chunk at
a time, nothing parsed. The store's input digest carries `.input_digest_format: 2`; a store compiled
under the old form refuses with the recompile hint (never silently served, never silently slow).
The verdict is as strict as it was and stricter where it counts: a byte moved in any of the three
inputs reads STALE. Beside it, `raw_shard` / `load_graph_ir` parse each shard ONCE per digest per
process — the memo is keyed by the resolved directory and served only when the bytes hash to the
same digest, so a rewritten shard re-parses and an untouched one never does; it is bounded to the
16 most recently loaded directories (`MEMO_SHARDS`), because unbounded it held every fixture copy
the floor loads and the floor's peak RSS read +31% — and the journal's
`_read_ids` and `check`'s store lane read the same parse. `check` still parses (it is an audit: a
malformed shard is COULD-NOT-TELL there), once.

```bash
cd engine && T=tenants/sqlalchemy/tenant.json
for v in "explain sqlalchemy.orm.session.Session" check build; do /usr/bin/time -f "$v %es %MKB" ../.venv/bin/python -m graphy $v --tenant $T --tenant-id sqlalchemy >/dev/null; done
../.venv/bin/python -m cProfile -s tottime -m graphy explain sqlalchemy.orm.session.Session --tenant $T --tenant-id sqlalchemy | head -12
python3 -m pytest -q tests/test_federated_store.py -k "hashes_shard_bytes or one_parse or older_input_digest"
cd .. && python3 measure.py run --out recon.json && python3 measure.py diff recon.before13.json recon.json
python3 -c "import json;r=json.load(open('recon.json'));[print(k,v['doors']) for k,v in r['tenants'].items()]"
```

| verb on the SQLAlchemy tenant (24 MB of shard) | before | after |
|---|---|---|
| `explain sqlalchemy.orm.session.Session` | 0.31 s · 106 MB | 0.12 s · 28 MB |
| `check` | 1.02 s · 161 MB | 0.47 s · 124 MB |
| `build` | 2.12 s · 288 MB | 1.53 s · 291 MB |
| of an `explain`: the freshness digest | 0.26 s (`json.raw_decode` + `json.dumps`) | 0.013 s (`_hashlib.HASH.update`, 40 calls) |

What is left in an `explain` after the hash: ~60 ms importing `graphy.cli` (the http stack rides in
through `graphy.index` — issue 20) and ~45 ms of the walk itself (`SQLiteStore.neighbours`, 296
calls). The engine's hottest frame in a door is now the walk, which is the shape the law wants.

**The receipt grew a lane.** `measure.py` now times the three doors on every rebuilt tenant, one
process each, on the tenant's first pillar's module id (`tenants.<name>.doors.{explain,blast,descend}.seconds`,
`doors.seconds` the slowest); the numbers regress like any time.

| check | result |
|---|---|
| the floor test | every file opened during `open_for` recorded: the shard payloads opened `rb` only, `json.loads` never handed their bytes; a byte mutated reads STALE (`test_GREEN_open_for_hashes_shard_bytes_and_never_parses_them`) |
| one parse | a second `load_graph_ir` of an untouched shard returns the same object with zero `json.loads`; a rewrite re-parses and moves `input_digest` |
| the old store | a digest without the format key refuses naming `compile_store` |
| the isolation test | the bridge's each-side-reads-only-its-own-data_home floor holds (`test_bridge.py::test_GREEN_two_tenants_open_in_one_process_and_neither_reads_the_other`) |
| burden | unchanged: runtime deps 0 · wheel under cap · scrub OK |
| the receipt | five full runs this session; the last: floor 459 passed in 16.5 s (the direct floor 15.2–15.8 s on three runs, `before` 14.9), gate OK 22.8 s, `pass.engine_hot_lanes` 5 → 4 (the graphy and sqlalchemy lanes' hottest frame is now the producer's `ast.iter_child_nodes` — issue 14), fastapi 4.7 → 3.7 s, sqlalchemy 8.8 → 7.4 s, hono 2.9 → 2.7 s, graphy 2.9 → 2.6 s |
| the doors lane | `tenants.<name>.doors.seconds` on the last run: express 0.085 · fastapi 0.098 · graphy 0.084 · hono 0.085 · sqlalchemy 0.136 (its `explain`; `descend` 0.091) — the SQLAlchemy `explain` sits above the issue's 0.1 s line by the `graphy.cli` import (~60 ms, issue 20), not by any load |
| noise, named | `quickstart.express.seconds` read 6.2 · 6.5 · 9.1 · 9.7 · 9.8 across the five runs with the engine's own frames identical in every profile (`container.emit` 6.5 s): its clone and `npm install` are network-bound, like the gate's pip in §48; `tenants.express.seconds` 2.5 → 2.6 on four runs and 2.9 on the fifth at load average 1.5 — the diff on this box names them, CI's back-to-back diff on one runner is the gate |

## 50 · THE PRODUCER WALKS ONCE — one level-order pass per file, byte-identical shard (2026-09-07 · graphyos issue 14)

**What it was.** `python_ast` read every file about twice: `_emit_import_edges` walked the whole
tree with `ast.walk` for the import statements, then `_calls_in` walked each tracked definition's
subtree again for its calls — on SQLAlchemy (256 files, 735,877 AST nodes) 1,384,656 visits over
10,747 `ast.walk` calls, and every visit through `ast.iter_child_nodes`, a generator over a
generator (`iter_fields`) per node — §49's hottest frame in the graphy and sqlalchemy lanes.

**What it is.** `_scan` is ONE level-order pass per file — the order `ast.walk` yields, so every
record lands where it did. It collects the import statements wherever they sit and, keyed by the
tracked definition that owns them, every call: a definition is tracked when `_defs_in` reaches it
(a module, a class body, a compound statement, never a function body), and a call belongs to the
outermost tracked function around it — the one whose subtree the old per-definition walk read. The
children come straight off each class's `_fields`; the generator `iter_child_nodes` builds cost
three times the walk. `_walk_stmt` reads its calls from the map. Nothing else moved: the record
order, the ids, the dialect. The TypeScript producer already walks once (its `_calls_in` skips
nested definitions; on hono the tree-sitter parse is 0.24 s of a 0.42 s `build_ir`) — no change.

```bash
cd engine && SP=$(ls -d ../staging/corpora/sqlalchemy/venv/lib/python*/site-packages)
../.venv/bin/python - "$SP" <<'PY'
import sys, time, ast
from pathlib import Path
from graphy.adapters import python_ast as P
trees = [ast.parse(f.read_text()) for f in P.walk_files(Path(sys.argv[1]) / "sqlalchemy")]
print("nodes", sum(1 for t in trees for _ in ast.walk(t)))
t = time.perf_counter(); [P._scan(tr) for tr in trees]; print("_scan %.2fs" % (time.perf_counter() - t))
t = time.perf_counter(); [ast.parse(f.read_text()) for f in P.walk_files(Path(sys.argv[1]) / "sqlalchemy")]; print("parse %.2fs" % (time.perf_counter() - t))
t = time.perf_counter(); P.build_ir(Path(sys.argv[1]) / "sqlalchemy"); print("build_ir %.2fs" % (time.perf_counter() - t))
PY
../.venv/bin/python -m graphy smash --package fastapi --site-packages ../staging/corpora/venv/lib/python3.12/site-packages --out /tmp/fa --parity tests/fixtures/fastapi_graph | grep PARITY
python3 -m pytest -q tests/test_adapters.py -k visits_every_node
cd .. && python3 measure.py run --out recon.json && python3 measure.py diff recon.before14.json recon.json
```

| on SQLAlchemy (256 files · 735,877 nodes) | before | after |
|---|---|---|
| node visits per mint | 1,384,656 (1.9 per node) | 735,877 (1 per node; the floor test counts the pops) |
| the traversal alone (`_scan` vs the two walks) | 0.94 s | 0.29 s |
| `build_ir` | 1.39 s | 1.05 s — `ast.parse` is 0.80 s of it, the stdlib's floor |
| `graphy smash` wall (mint + ring) | 2.06–2.24 s · 129 MB (the old producer run from a scratch copy of the package) | 1.68–1.71 s · 130 MB — the ring's shards byte-identical (`cmp` on nodes.json · edges.json) |

| check | result |
|---|---|
| parity | `PARITY OK: fastapi_graph.records@sha256:21ed3ce1…` — 507 nodes / 3715 edges identical to the fixture; the old producer (from `git show HEAD~1`) and the new one produce byte-identical records on sqlalchemy (11,959 nodes / 56,604 edges) and on graphy itself |
| the floor test | `test_python_ast_visits_every_node_of_a_file_exactly_once`: pops == `ast.walk`'s node count on a sample file; an import in a function body is the module's, a nested def's calls are the outer function's, a class body's own calls are nobody's, a def under `match` is not a node and its calls are not edges — the old attribution, pinned |
| hono · express | rebuilt `ARMS OK`, `atlas.json` byte-identical before and after (`cmp`) |
| the receipt | two full runs this session; the clean one: floor 460 passed in 14.6 s (16.5 before), gate OK 23.4 s, fastapi 3.7 → 3.5 s, sqlalchemy 7.4 → 6.8 s (RSS 301 → 288 MB), graphy 2.6 → 2.5 s, express 2.9 → 2.6 s, hono 2.7 → 2.7, quickstart httpx 5.7 → 5.1 s, express 9.8 → 6.3 s, the whole receipt 81.3 → 74.7 s. `pass.engine_hot_lanes` reads 4 → 6, which is the metric telling the truth: the producer's stdlib frame (`ast.iter_child_nodes`) no longer sits on top of the graphy and sqlalchemy lanes, so their hottest frame is the engine's `container._write_parquet` (0.32 s · 1.06 s), and the floor's hottest frame is the same `_write_parquet` at 4.89 s over `sqlite3.executescript` 4.09 s — the parquet writer is the next lane, the producer is done: its share of a sqlalchemy mint is `_scan` 0.76 s under the profiler against `ast.parse`, the stdlib's floor |
| noise, named | `floor.seconds` read 20.1 in the first receipt of this session against 16.5 before; the direct floor read 14.5 and 15.2 on two runs straight after — the same network- and load-bound noise §49 names |

## 51 · THE RECORDS ARE COMPACT — separators for the machine files, indent for what a human opens (2026-09-07 · graphyos issue 15)

**What it was.** Every shard file went through one `smash._write_json`, `indent=2` — the same
call for `PROVENANCE.json` (1.5 KB, a human reads it) and for `nodes.json` (7.4 MB, nothing but
the loader ever reads it). On the SQLAlchemy tenant the three record files held 24.5 MB where the
same records compact to 16.0 MB; the index's 718 releases held 1.9 GB of it; and every pull,
`sha256`, freshness digest and parse downstream paid for the whitespace.

**What it is.** Two writers, named for who reads the file. `smash._write_records` — `separators=(",", ":")`,
no indent, one line — writes `nodes.json` and `edges.json`; `converge --resolve` writes
`wormhole_edges.json` the same way; `cartograph.write_graph` writes its `nodes` · `edges` ·
`clusters` · `adjacency` the same way and keeps `stats.json` indented. `_write_json` (`indent=2`)
still writes `PROVENANCE.json`, `ring.json`, `refresh.json` and every receipt. Still JSON, still
the stdlib's `json`: `load_graph_ir`, `validate_shard`, the journal, the estate and the gate's
scheme scan (`"src":\s*"` — the regex already allowed no space) read either form, so every shard
already in an index stays valid, and a golden in the old form still proves a compact re-mint
record for record — the parity compares records, never bytes. The FastAPI fixture is re-minted by
its own `mint_command` (its `PROVENANCE.json` receipts moved: 938,496 → 755,397 bytes over the
two files; 507 nodes / 3715 edges equal to the previous fixture's records, checked against
`git show HEAD~1`).

```bash
cd engine && SP=../staging/corpora/sqlalchemy/venv/lib/python3.12/site-packages
wc -c tenants/sqlalchemy/substrate/sqlalchemy_graph/{nodes,edges,wormhole_edges}.json
/usr/bin/time -f "smash %es %MKB" ../.venv/bin/python -m graphy smash --package sqlalchemy --site-packages $SP --out /tmp/sa
../.venv/bin/python - <<'PY'
import json, time
d = "/tmp/sa/sqlalchemy_graph/"; n = json.load(open(d + "nodes.json")); e = json.load(open(d + "edges.json"))
for label, kw in (("indent=2", dict(indent=2)), ("compact", dict(separators=(",", ":")))):
    t = time.perf_counter(); a = json.dumps(n, **kw); b = json.dumps(e, **kw); print(label, "encode %.2fs" % (time.perf_counter() - t), "bytes", len(a) + len(b))
PY
../.venv/bin/python -m graphy smash --package fastapi --site-packages ../staging/corpora/venv/lib/python3.12/site-packages --out tests/fixtures --no-ring   # the fixture, re-minted
python3 -m pytest -q tests/test_smash.py -k "compact_and_the_receipts"
echo "six==1.17.0" > /tmp/one.txt && ../.venv/bin/python -m graphy farm --packages /tmp/one.txt --index /abs/staging/index/farm --work /tmp/farm1 --force
../.venv/bin/python -m graphy index --index /abs/staging/index/farm --verify | tail -1
cd .. && python3 measure.py run --out recon.json && python3 measure.py diff recon.before15.json recon.json
```

| bytes | indented | compact |
|---|---|---|
| SQLAlchemy `nodes.json` · `edges.json` · `wormhole_edges.json` | 7,437,288 · 11,842,493 · 5,214,566 = 24.5 MB | 6,258,357 · 9,777,286 · 4,463,686 (it was `indent=1`) = 20.5 MB |
| the five tenants' record files | fastapi 10.59 · sqlalchemy 25.91 · hono 4.30 · express 1.01 · graphy 6.45 MB | fastapi 8.70 · sqlalchemy 21.68 · hono 3.46 · express 0.81 · graphy 5.25 MB — 48.3 → 39.9 MB over the five (`cat tenants/<t>/substrate/*_graph/{nodes,edges,wormhole_edges}.json | wc -c`) |
| the fixture (`tests/fixtures/fastapi_graph`, two files) | 938,496 | 755,397 |
| `six==1.17.0` in the index (nodes + edges) | 62,849 | 48,167 — the records equal, the old shard beside it under its own address |

| on SQLAlchemy | before | after |
|---|---|---|
| the encode of nodes + edges (`json.dumps`, unprofiled) | 0.22 s → 19.3 MB | 0.05 s → 16.0 MB |
| `graphy smash` wall (mint + ring, two runs) | 1.68–1.71 s · 130 MB | 1.54–1.59 s · 86 MB |
| the decode (`json.loads`) | 0.06 s | 0.06 s — the whitespace was never the parser's cost, only the disk's, the hash's and the encoder's |

| check | result |
|---|---|
| the floor test | `test_GREEN_the_records_are_compact_and_the_receipts_are_indented_and_parity_reads_both`: nodes.json and edges.json one line with no `": "`, under 0.8 of their indented bytes; PROVENANCE.json and ring.json indented; a golden rewritten in the old indented form validates to the same count and proves the compact re-mint `PARITY OK` |
| the index | `INDEX OK: 718 named shard(s), 0 broken` with the compact six pushed by `--force` (address `471e49c8…`) beside the indented one (`0bc16aee…`); verify 2.6 s before and after — one shard of 718 moved, and the verify's cost is the hash (`_hashlib.openssl_sha256` 2.08 s in both profiles), which is what fewer bytes will cut when the farm is re-run (issue 15's own done line names that run; it is a `--force` farm of 718 releases, hours, not this lane) |
| the fixture parity | fastapi rebuild `PARITY OK: fastapi_graph.records@sha256:21ed3ce1…` against the re-minted fixture |
| the receipt | one full run: floor 461 passed in 14.4 s (14.6 before), gate OK 22.4 s (23.4), fastapi 3.5 → 3.3 s, sqlalchemy 6.8 → 6.5 s (RSS 288 → 277 MB), graphy 2.5 → 2.1 s (RED on the run — `ARMS DRIFT` naming `_write_records` in PRODUCE, the region re-rendered, `GRAPHY_TENANT_OK` straight after), hono 2.7 → 2.7, express 2.6 → 2.6, index verify 2.6 → 2.6 with 0 broken, `pass.engine_hot_lanes` 6 → 6 (`container._write_parquet` still on top of the graphy · sqlalchemy · fastapi lanes — the next lane), the whole receipt 74.7 → 75.1 s; `quickstart.express.seconds` 6.3 → 8.8 and httpx 5.1 → 5.5 are the clone-and-install noise §49 names (express read 6.2–9.8 across five runs there), the engine frames identical. The estate re-emitted over the moved catalog: 718 shards, the compact six read beside 717 indented ones, 51.2 s |

## 52 · THE AGGREGATE FIELDS ARE COLUMNS — owned() reads the table, never a record (2026-09-07 · graphyos issue 16)

**What it was.** The store's `nodes` table was `(id, owner, record)`: one JSON blob per node, and
`SQLiteStore.owned()` — the whole-corpus read every aggregate takes — decoded every blob to hand
`pillars` · `arms` · `draw` the four fields they read (`module` · `role` · `node_type` · `dotted`).
Drawing the SQLAlchemy atlas decoded 83,719 records: `json.loads` 0.27 s of `owned()`'s 0.46 s
under the profiler, for a `.get("module")`.

**What it is.** The `nodes` table carries the aggregate fields as columns — `COLUMNS =
(node_type, dotted, module, role, file, line)` — beside the blob, with indexes on `(owner, module)`
and `(owner, node_type)`. `owned()` yields `(id, {the six columns})` straight off the row and decodes
nothing; `record()` is the one decode, and only `explain` · the doors · `draw --symbol` ask for it.
`ShardStore.owned()` projects the mesh record to the same six, so both readers speak one shape.
The schema is an input, so `GENERATION_FORMAT` is 4: a store compiled under 3 refuses to serve,
naming recompile, and every tenant rebuilt once — the arms, the atlas and the fanout receipts read
identical after (the generation moved; the pictures did not). `sqlite3` only.

```bash
cd engine && T=tenants/sqlalchemy
python3 -m cProfile -s cumtime -m graphy draw --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --partition $T/partition.json --atlas /tmp/atlas --lr --min-weight 2 | grep -E "owned|decoder"
/usr/bin/time -f "atlas %es %MKB" python3 -m graphy draw --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --partition $T/partition.json --atlas /tmp/atlas --lr --min-weight 2
python3 -m pytest -q tests/test_federated_store.py -k "owned_reads or same_columns or blob_only"
for t in fastapi sqlalchemy hono express graphy; do bash tenants/$t/rebuild.sh 2>&1 | grep -E "ARMS OK|ATLAS OK|_OK$"; done
python3 - <<'PY'   # the atlas receipts, before against after: the file hashes are the pictures
import json; a = json.load(open("/tmp/atlas.sqlalchemy.before.json")); b = json.load(open("tenants/sqlalchemy/substrate/atlas/atlas.json"))
print("identical" if a["files"] == b["files"] else "moved", a["generation"], "->", b["generation"])
PY
cd .. && python3 measure.py run --out recon.json && python3 measure.py diff recon.before16.json recon.json
```

| on SQLAlchemy (11,964 owned nodes) | before | after |
|---|---|---|
| `json.loads` under `owned()` drawing the atlas (profiled) | 83,719 calls · 0.27 s | 0 (six decodes in the run: the meta rows and the receipts) |
| `owned()` cumulative (profiled) | 0.46 s | 0.17 s — what is left is the 83,755 row tuples and the dict per row |
| `graphy draw --atlas` wall, six pictures (two runs) | 1.22–1.23 s · 43.8 MB | 1.08 s · 43.8 MB — `sugiyama._count_crossings` is the top frame now (0.39 s), the store's `edges()` second (0.19 s) |
| `graphy pillars --against` wall | 0.18 s | 0.17 s |
| `graphy arms --verify` wall | 0.21 s | 0.19 s |

| check | result |
|---|---|
| the floor tests | `test_GREEN_owned_reads_the_columns_and_decodes_no_record` (`json.loads` patched, `owned()` over the fixture calls it zero times, each row is exactly `COLUMNS` and equals the full record's projection, both indexes present) · `test_GREEN_shard_store_owned_yields_the_same_columns` (the two readers' `owned()` equal) · `test_RED_store_under_the_blob_only_schema_refuses_naming_recompile` (a format-3 meta row refuses naming the generation format) |
| the five rebuilds | `ARMS OK` fastapi 4 · sqlalchemy 5 · hono 5 · express 4 · graphy 6 (the receipt's first run named `ARMS DRIFT` in SEAM — `_columns` is a new function of `federated_store`; the region re-rendered, `GRAPHY_TENANT_OK`); `ATLAS OK` on all five, and every atlas receipt's `files` map identical before and after on all five tenants (the sqlalchemy atlas drawn before and after: 13 files byte-identical by `sha256sum`) |
| the receipt | the first run with the floor and the gate running beside it read floor 19.2 s and graphy RED (the drift); the clean run: floor 464 passed (461) in 16.2 s (14.4 — three store-compiling tests added, and `executescript` — the schema's two new indexes — 4.2 → 6.3 s profiled, now the floor's top frame ahead of `_write_parquet`), gate OK 24.6 s (22.4), fastapi 3.3 → 3.3 s, sqlalchemy 6.5 → 6.4 s (RSS 277 → 277 MB; the store file 19.9 MB), hono 2.7 → 2.6, express 2.6 → 2.6, graphy 2.1 → 2.4 with `ARMS OK` and every door green, index verify 2.6 → 2.5 with 0 broken, `pass.engine_hot_lanes` 6 → 5 (the floor's hottest frame is sqlite's now; `container._write_parquet` still on top of the graphy · sqlalchemy · fastapi lanes — the next lane), the whole receipt 75.1 → 76.5 s, `measure.py diff` exit 0; quickstart express 8.8 → 6.3 and httpx 5.5 → 5.1, the network noise §49 names |

## 53 · EAT AGAIN SPLICES — a per-file receipt in PROVENANCE, a re-mint parses only what moved, byte-identical to a full mint (2026-09-07 · graphyos issue 17)

**What it was.** `graphy eat` on a repo eaten a minute ago wiped `.graphy/substrate/` and did
everything again: pip-installed the repo into its venv, parsed every file of the package and its
ring, converged, built, checked. The shell's walk-before-edit gate (§18) lives on a repo that
changes one file at a time, and every edit was followed by the full eat — on httpx, 2.3 s with
the pip re-run, 127 files parsed, none of which had changed.

**What it is.** The mint keeps a per-file receipt in the shard's `PROVENANCE.json` under `sources`:
`file → sha256 of bytes → the node slots and edge records it produced`, in mint order, with the
`pin` the records also depend on (python_ast: the package name and the repo root's local package
set; typescript_ast: the package name and the file list, since a relative specifier resolves
against the files that exist). A re-mint over the same shard directory hashes every file, parses
the ones whose bytes moved, and takes the rest's records off the previous `nodes.json` and
`edges.json` — each file's records are a contiguous span of both, because the producer emits file
by file in walk order. An id two files spell (`pkg/x.py` beside `pkg/x/__init__.py`; `index.js`
beside `index.mjs`) is the one thing a span cannot recover, so the receipt stores exactly those
records and their slots (`extra` · `own`; one record in `async`, two in `is-promise`, none in
SQLAlchemy, hono or httpx) and the replay is the full mint's, record for record. A receipt that
does not fit — the pin moved, the producer (adapter · graphy · python) is not this one, the records
beside it disagree with its counts — is discarded and the full mint runs. No daemon, no watcher,
no cache outside the shard's own directory; the corpus digest and the parity are what they were,
the digest now reading the receipt's hashes instead of every file a second time.

`graphy eat` keeps each previous `<slug>_graph/` as exactly `nodes.json` · `edges.json` ·
`PROVENANCE.json` (every build product beside them wiped, the stored walks kept as before), prunes
a shard the new ring no longer names, and its `EAT OK` line says `(N of M files parsed, S s)`.
`provision` writes `provision.json` beside the venv pinning the sha256 of `pyproject.toml` ·
`setup.py` · `setup.cfg` · `requirements.txt`; a re-eat under the same declaration skips the pip
install and says so (delete the receipt to force). `measure.py` runs `graphy eat .` once more on
each quickstart clone: `eat_seconds` (the first eat's own line, provision included) beside
`eat_again_seconds` and `eat_again_parsed`.

```bash
cd staging/quickstart && git clone -q --depth 1 https://github.com/encode/httpx.git httpx-cold && cd httpx-cold
time ../../../.venv/bin/graphy eat . | grep '^EAT OK'      # (127 of 127 files parsed, 4.3s) — the venv, the pip install, the mint, the build
time ../../../.venv/bin/graphy eat . | grep '^EAT OK'      # (0 of 127 files parsed, 0.7s)
printf '\n\ndef _added():\n    return 1\n' >> httpx/_models.py && time ../../../.venv/bin/graphy eat . | grep '^EAT OK'   # (1 of 127 files parsed, 0.7s)
python3 -c "import json; s = json.load(open('.graphy/substrate/httpx_graph/PROVENANCE.json'))['sources']; print(s['pin'], s['parsed'], s['reused'], s['cross_file'], list(s['files'])[:2])"
cd ../express && for i in 1 2; do time ../../../.venv/bin/graphy eat . | grep '^EAT OK'; done   # (0 of 581 files parsed) the second time; the seconds are the parquet over 86 shards
cd ../../../engine && python3 -m pytest -q tests/test_smash.py -k "remint or receipt or eat_again or two_files"
cd .. && python3 measure.py run --out recon.json && python3 measure.py diff recon.before17.json recon.json
```

| httpx | before | after |
|---|---|---|
| `graphy eat .` cold on a fresh clone (venv · pip · mint · converge · build · check) | 4.3 s | 4.3 s — 127 of 127 files parsed |
| `graphy eat .` again, nothing changed | 2.3 s (pip re-run, 127 parsed) · 3.4 s with the venv's pip cache cold | 0.7 s eat, 0.8 s wall — 0 of 127 parsed, pip skipped |
| `graphy eat .` after one edit — the gate's loop | 2.3 s, 127 parsed | 0.7 s — 1 of 127 parsed |
| the second eat against the first | the same seconds | 16 % — under the issue's quarter |
| express (86 shards, 581 files), eat again | 133 parsed the first time under the new code (`async` and `is-promise` were not spliceable before the stored records) | 0 of 581 parsed, 3.6 s — `container._write_parquet` over 86 shards is the whole of it |

| check | result |
|---|---|
| byte-identical | `test_GREEN_a_remint_parses_only_the_files_whose_bytes_moved_and_equals_a_full_mint` — `ast.parse` patched: a re-mint with nothing moved parses 0, one touched file parses exactly 1 against the full mint's 2, an added file 1, a deleted file 0; after each, `nodes.json` and `edges.json` equal a fresh full mint's bytes. `test_GREEN_an_id_two_files_emit_is_stored_by_the_receipt_and_the_splice_stays_byte_identical` — the cross-file id under both producers' semantics: touched, deleted, restored, each equal to a full mint |
| the receipt refuses to guess | `test_RED_a_receipt_that_does_not_fit_is_discarded_and_the_full_mint_runs` — a hand inside `nodes.json`, a producer version that is not this one, a repo root that gains a local package (the pin moves and every file's imports re-resolve): each parses everything and equals a fresh mint |
| eat twice | `test_GREEN_eat_again_keeps_the_shards_parses_nothing_and_prunes_a_shard_the_ring_dropped` — the second eat parses 0 with every shard's bytes unchanged and the resolver's sidecar rewritten; a root that stops importing a ring package sees that shard pruned. `test_provision`: the second provision under the same declaration skips pip, a moved `pyproject.toml` runs it, a failed install leaves no receipt |
| the five rebuilds | `ARMS OK` on all five (the graphy tenant named `ARMS DRIFT` twice on the way — `_reuse_from` · `_clear_substrate`, then the `_receipt` module — the regions re-rendered) |
| the receipt | four full runs this session, the last two clean: floor 467 passed (464, three tests added), gate OK 24.0 · 37.4 s (24.6 — its pip is the network), fastapi 3.3 → 3.3–3.5 s, sqlalchemy 6.4 → 6.4–6.6 s, hono 2.6 → 2.7, express 2.6 → 2.6, graphy 2.4 → 2.4–2.5 with `ARMS OK`, index verify 2.5 → 2.6 with 0 broken, `pass.engine_hot_lanes` 5 → 5 (`container._write_parquet` on top of the same lanes — the next lane), wheel 263,903 → 268,759 B under the cap; **quickstart httpx `eat_seconds` 4.3 · `eat_again_seconds` 0.8 · `eat_again_parsed` 0; express 5.8 · 3.6 · 0** — the done check, in the receipt. `floor.seconds` under `measure.py run` read 18.2 · 17.5 · 29.1 · 33.5 · 30.3 across the five runs with `sqlite3.executescript` the frame that swelled and no engine frame moving; the floor run directly read 17.0 · 17.6 · 17.6 · 17.8 · 19.1 s with the change and 18.3 s at the previous commit with the change stashed (`git stash -u && python3 -m pytest -q && git stash pop`), `measure.measure_floor` alone 17.8 s — the box's own noise this session, the kind §49 names, and the diff's three named regressions (`floor.seconds`, `gate.seconds`, the whole receipt's `seconds`) are those times and nothing else |

## 54 · THE CROSSING COUNT IS AN INVERSION COUNT — same integer, same layout, every atlas byte-identical (2026-09-07 · graphyos issue 18)

**What it was.** `sugiyama._count_crossings` counted a bilayer's crossings pairwise: every edge
against every later edge, a product of position differences per pair. `_minimize_crossings`
asks for the total after every median sweep, so drawing the SQLAlchemy atlas called it 2,650
times through 300 `_total_crossings` — 0.41 s of the atlas's 1.17 s under the profiler, the top
frame once §52 took `json.loads` off the store.

**What it is.** The same count as an inversion count. Two edges cross exactly when their
endpoints sit in opposite order on the two layers, so the edges sorted by (upper position, lower
position) cross exactly where the lower positions are inverted, and a Fenwick tree over the lower
layer's positions counts those in `O(E log E)` — a parallel edge or two edges from one upper node
sort adjacent and count nothing, as before. The count is exact, so every sweep makes the decision
it made and the layout does not move. The pairwise count stays as `_count_crossings_pairwise`, the
floor's oracle, called by no layout. stdlib only.

```bash
cd engine && T=tenants/sqlalchemy
python3 -m cProfile -s tottime -m graphy draw --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --partition $T/partition.json --atlas /tmp/atlas --lr --min-weight 2 | grep -E "ncalls|crossings"
/usr/bin/time -f "atlas %es %MKB" python3 -m graphy draw --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --partition $T/partition.json --atlas /tmp/atlas --lr --min-weight 2
python3 -m pytest -q tests/test_sugiyama.py -k inversion
for t in fastapi sqlalchemy hono express graphy; do bash tenants/$t/rebuild.sh 2>&1 | grep -E "ARMS OK|ATLAS OK|_OK$"; done   # hono · express under PYTHON=../.venv/bin/python, fastapi under GRAPHY_CORPUS_SITE_PACKAGES
python3 - <<'PY'   # the atlas receipts, before against after, per tenant: the file hashes are the pictures
import json; a = json.load(open("/tmp/atlas.sqlalchemy.before.json")); b = json.load(open("tenants/sqlalchemy/substrate/atlas/atlas.json"))
print("identical" if a["files"] == b["files"] else "moved", a["generation"], "->", b["generation"])
PY
cd .. && python3 measure.py run --out recon.json && python3 measure.py diff recon.before18.json recon.json
```

| on the SQLAlchemy atlas (six pictures, 2,650 bilayer counts) | before | after |
|---|---|---|
| `_count_crossings` self time (profiled) | 0.411 s | 0.092 s (0.165 s cumulative with the edge list's build) |
| `_minimize_crossings` cumulative (profiled) | 0.60 s | 0.31 s |
| `graphy draw --atlas` wall (two runs) | 1.17 · 1.16 s · 43.7 MB | 0.83 · 0.82 s · 43.7 MB — the store's `edges()` is the top frame now (0.19 s), `owned()` second (0.12 s) |

| check | result |
|---|---|
| the floor test | `test_GREEN_inversion_crossing_count_equals_the_pairwise_count_on_random_bilayers` — 400 random bilayers (0–14 nodes a side, three densities, parallel edges, targets outside the lower layer, upper nodes absent from `adj`), the two counters equal on every one, and the textbook three by hand |
| the layout does not move | the sqlalchemy atlas drawn before and after: 12 files byte-identical by `cmp`; every tenant's `atlas.json` `files` map identical before and after the rebuild — fastapi 12 · sqlalchemy 12 · hono 14 · express 12 · graphy 16 |
| the five rebuilds | `ARMS OK` fastapi 4 · sqlalchemy 5 · hono 5 · express 4 · graphy 6 (the graphy tenant named `ARMS DRIFT` once — `_count_crossings_pairwise` is a new function of `sugiyama`; the CUT region re-rendered); `ATLAS OK` on all five |
| the receipt | two full runs: the first read gate RED — its changelog check ran in the minute between this section's append and the gate's own regenerate, `standalone_check.sh` run directly after is `GRAPHY_STANDALONE_OK` with `changelog OK`; the clean run: floor 468 passed (467, the one test added) in 18.2 s (30.3 — the §53 box noise gone), gate OK 24.6 s (37.4), fastapi 3.5 → 3.3 s, sqlalchemy 6.6 → 6.1 s, hono 2.7 → 2.6, express 2.6 → 2.5, graphy 2.5 → 2.4 with `ARMS OK` and every door green, index verify 2.6 → 2.5 with 0 broken, wheel 268,759 → 269,249 B under the cap, the whole receipt 108.3 → 84.9 s; the diff names three regressions and none is this lane's — `pass.engine_hot_lanes` 5 → 6 because the floor's two top frames swapped places (`container._write_parquet` 7.3 s ahead of `sqlite3.executescript` 6.7 s, both there before at 13.8 and 14.8 s; no `sugiyama` frame in any lane's hot three), and quickstart express `eat_seconds` 5.8 → 8.3 with its profiled frames unchanged (`container.emit` 5.86 → 5.81 s) — the eat run directly on two fresh clones after the receipt read 5.8 · 5.7 s, the delta is `npm install` under the receipt; `container._write_parquet` is the top engine frame of every lane that emits parquet — the next lane |

## 55 · THE FLOOR WAITS FOR EVENTS, NEVER SLEEPS — the same tests, the same RED proofs, 3 s less (2026-09-07 · graphyos issue 19)

**What it was.** The floor is most of the gate, and the slowest test was a fixed wait:
`test_fanout_windows_seat_lock_serializes` held `tb.join(timeout=2.0)` twice to prove writer B
stays blocked while writer A holds the publish lock — 2.0 s of a 15–18 s floor, on every run, on
both interpreters in CI. Two more tests proved a lock the same way with a 0.4 s and a 0.3 s join.
The issue named the next eleven as subprocess round trips; the profiler disagrees — only one
floor test spawns `python -m graphy` (the entry-point proof, `test_python_m_graphy_wire_subprocess`)
and the three `refresh` tests pay the refresh lane's own design (it proves the sibling by running
`converge · build · check` as processes). What the eleven actually paid: `test_pull_over_http_is_byte_identical`
0.5 s in `serve_forever`'s default 0.5 s poll interval, which `shutdown()` waits out; and two tests
that delete a shard directory on purpose then walk it (`test_check_could_not_tell_absent_roster_dir`,
`test_RED_unmeasurable_input_raises_never_serves`) paid `cartograph.resolve_graph`'s transient-ENOENT
retry — five sleeps of 0.05 s per resolve, ten resolves, 0.75 s of nothing.

**What it is.** The three lock tests prove "still blocked" by an event the blocked side sets the
moment it is past the lock — the seat-lock test wraps `_acquire_publish_lock` so writer B says when
it holds it; the journal test's B sets it when it reaches the (already trapped) tail; the mesh
worker sets it inside `_index_lock`. The wait is `event.wait(timeout=0.2)`, the ceiling on "still
blocked", and the seat-lock control (the no-op lock) joins B the moment it holds the lock so its
publish lands inside A's window, exactly the overlap the control wants. The http test serves with
`poll_interval=0.01`. The two deleting tests stub `cartograph.time.sleep`, and
`test_transient_enoint_retry_materializes_on_first_sleep` still counts the retry's one sleep.
No engine line moved; no xdist; no extra; 468 tests before and after.

```bash
cd engine
../.venv/bin/python -m pytest -q --durations=12                       # the twelve slowest, after
git stash; for i in 1 2; do /usr/bin/time -f "%e s" ../.venv/bin/python -m pytest -q -p no:cacheprovider; done; git stash pop
# the RED proofs: each lock removed, its test fails
sed -i 's/_f.flock(fd, _f.LOCK_EX if mode == self.LK_LOCK else _f.LOCK_UN)/pass/' tests/test_fanout.py && ../.venv/bin/python -m pytest -q tests/test_fanout.py::test_fanout_windows_seat_lock_serializes; git checkout tests/test_fanout.py
sed -i '239s/_flock.flock(fh.fileno(), _flock.LOCK_EX)/pass/' graphy/journal.py && ../.venv/bin/python -m pytest -q tests/test_journal.py::test_concurrent_appends_never_mint_duplicate_seq; git checkout graphy/journal.py
sed -i '183s/fcntl.flock(lf.fileno(), fcntl.LOCK_EX)/pass/' graphy/mesh_federation_gate.py && ../.venv/bin/python -m pytest -q tests/test_mesh_federation.py::test_one_lock_build_index_concurrent_observer_loses_no_row; git checkout graphy/mesh_federation_gate.py
cd .. && python3 measure.py run && python3 measure.py diff recon.before19.json recon.json
```

| test | before | after |
|---|---|---|
| `test_fanout_windows_seat_lock_serializes` | 2.00 s | 0.21 s (the real-lock window's 0.2 s ceiling; the control returns at once) |
| `test_pull_over_http_is_byte_identical` | 0.52 s | 0.02 s |
| `test_check_could_not_tell_absent_roster_dir` | 0.60 s | 0.11 s |
| `test_RED_unmeasurable_input_raises_never_serves` | 0.34 s | 0.09 s |
| `test_concurrent_appends_never_mint_duplicate_seq` | 0.40 s | 0.20 s |
| `test_one_lock_build_index_concurrent_observer_loses_no_row` | 0.30 s | 0.20 s |
| the floor, direct, two runs each (`pytest -q -p no:cacheprovider`) | 18.5 · 17.8 s | 15.5 · 15.0 s |
| the slowest after | `test_GREEN_fixture_is_re_minted_by_the_engine_after_a_green_check` 0.85 s — the refresh lane's three `python -m graphy` processes, by design; the three refresh tests are the top three now |

| check | result |
|---|---|
| the RED proofs | the shim's real lock removed → `writer B published inside writer A's locked window`; the journal's flock removed → `worker B must BLOCK at the journal lock while A holds it`; the mesh gate's flock removed → `the worker must BLOCK at the index lock while it is held`; the no-op control still fails the seat-lock test when B's publish does not land inside A's window (found while landing: the event alone let A resume before B published, the control read a truthful receipt; B is joined once it holds the lock) |
| the floor | 468 passed · 3 skipped on 3.12, before and after |
| the receipt | `measure.py run` then `diff recon.before19.json recon.json`: `MEASURE DIFF OK: 37 number(s) moved, none the wrong way past tolerance` — floor 468 passed · 3 skipped before and after, 18.2 → 17.7 s under the receipt (the direct runs above read 18.5 · 17.8 → 15.5 · 15.0 s; the receipt's floor ran beside a stale watcher loop from the previous session), gate OK 24.6 → 21.9 s, the whole receipt 84.9 → 82.3 s; every tenant's doors green within the tolerance |
| CI | red on every push since 6e47127 (30 pushes) with zero jobs: the receipt step's name `the receipt (quick: the floor, the gate, the wheel)` held an unquoted `: ` and the file did not parse (`yaml.safe_load`: line 43, column 33) — quoted here, every file under `.github/workflows/` parses; the floor on 3.10 and 3.12 reads from the push of this section; the gate reads no workflow file → graphyos issue 22 |
| CI, the first run with jobs | 34079133673: gate green (the receipt step ran, 1 m 29 s) · floor (3.12) green in 23 s · floor (3.10) red at collection — `burden.py` imported `tomllib` (3.11+) at module level and `test_burden.py` loads it; hidden by the same silent CI since the burden landed. `tomllib` is imported inside `check_dependencies` now (the gate's interpreter is 3.12; a 3.10 caller is refused by name) and the one test that needs it does `pytest.importorskip("tomllib")` — proven with `sys.modules["tomllib"] = None` after pytest's own config: `s..` and the skip named |
| CI, the second run | 34079362498: gate and floor (3.12) green; floor (3.10) one red — `test_GREEN_open_for_hashes_shard_bytes_and_never_parses_them` saw no shard open: the engine hashes through `Path.open("rb")`, and 3.10's pathlib opens through an accessor bound to `io.open` at import, past the test's spy on `io.open`. The spy covers `Path.open` too; the engine did not move |
