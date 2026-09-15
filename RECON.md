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
in no tracked file and the operator regenerates the hashes with `scrub.py --hash <word>…`. (§80:
the hashes are keyed now — HMAC-SHA256 under `.private_key`, gitignored, this box only — because a
plain hash of a company name reverses by a wordlist; `--keygen` writes the key once, and a box
without one says `SCRUB SKIPPED`.) The
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
python3 scrub.py --key /path/to/graphy/.private_key --tree .              # the keyed sweep on the cut itself, under the key that stays behind (§80)
bash standalone_check.sh                                                  # the gate on the cut: its scrub says SKIPPED here (no key), the line above is the sweep
git add -A && git commit -m "graphy: the public cut" && gh repo create omnislash157/graphyos --public --source . --push
```

What stays behind: `staging/` (tools, docs, skills, the corpora and indexes), `.claude/recovery`,
`.claude/skills`, `.private_modules`, `.private_key` (§80), and this repo's history. Kept current
afterwards by `sync_public.sh`, which scrubs the public checkout under this box's key by path. What the cut needs from the
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
| CI, green | 34079577664: gate · floor (3.10) · floor (3.12) all green — the first green push since 34036590127 on 2026-09-06 13:36. The floor step on the runner: 3.10 13.2 s, 3.12 11.7 s (`Run cd engine && pytest -q` to its last line); the floor jobs whole, checkout and install included, 3.10 24 → 23 s and 3.12 25 → 22 s against that last green run (its step log has expired; the job spans are what GitHub still holds). Re-derive: `gh run view <id> --repo omnislash157/graphyos --json jobs` and `--log` for the step's first and last timestamp |

## 56 · EVERY VERB PAYS FOR ITSELF — the verb modules import inside their handlers, `--help` 78 → 45 ms, the surface untouched (2026-09-07 · graphyos issue 20)

**What it was.** `graphy/cli.py` imported fourteen verb modules at the top — `fanout` ·
`federated_store` · `journal` · `container` · `doors` · `index` · `mcp` · `pillars` · `refresh` ·
`release` · `traversal` · `converge` · `smash` · `parity.ParityError` — so `python -m graphy --help`
loaded 29 `graphy.*` modules and 192 modules in all, `graphy.index` dragging `urllib.request` →
`http.client` → `email.parser` (10 ms of import time) for a verb that never fetches. Every
`python -m graphy` a rebuild spawns (about twelve) and every farm worker paid the same.

**What it is.** Each handler (and each helper that reaches a verb module: `_roster`,
`_descriptor_dict`, `_clear_substrate`, `_eat_run`, `_scheme_index_from_ring`, `_eat_typescript`)
imports what it uses on its first line; `_build_parser` imports only `pillars` (its five
`DEFAULT_*` values, 1.4 ms) and lists the producers from `_PRODUCER_NAMES`, a tuple the floor pins
to `smash.PRODUCERS` so the parser never loads the minting lane (12 ms: `email.parser` ·
`subprocess` · the adapters). `index._Source.read` imports `urllib` under `if self.remote:` — a
directory index never loads it. Importing `graphy.cli` now loads exactly the surface —
`graphy` · `graphy.ir` · `graphy.parity` · `graphy.tenant` · `graphy.cli` — 113 modules, none of
`urllib.request` · `http.client` · `email.parser`. `import graphy` and every documented
`from graphy import X` are untouched (`test_exports_the_parity_surface`). Stdlib only, nothing added.

**Why not 30 ms.** The issue's target was `--help` under 30 ms. The floor is the import surface
the issue pins: `import graphy` alone is 32 ms wall on this box (the bare interpreter 11 ms;
`graphy.ir` 13 ms of import time, 8.7 of it `dataclasses` → `inspect` → `ast`, and `parity`'s
`pathlib` → `urllib.parse`). `--help` is 13 ms above that: `argparse` 3.5 ms and the parser's
own construction. Under 30 needs the surface to move — `ir` without `dataclasses`, or a package
`__init__` that resolves its names lazily — which is a different change with a different blast
radius; it is not this one.

```bash
cd engine
python3 - <<'PY'                                                       # the medians (n=25 each)
import subprocess, sys, time, statistics
def med(cmd):
    ts = []
    for _ in range(25):
        t = time.perf_counter(); subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); ts.append((time.perf_counter() - t) * 1000)
    return statistics.median(ts)
for label, cmd in [("bare", [sys.executable, "-c", "pass"]), ("import graphy", [sys.executable, "-c", "import graphy"]),
                   ("import graphy.cli", [sys.executable, "-c", "import graphy.cli"]), ("--help", [sys.executable, "-m", "graphy", "--help"]),
                   ("check, no args", [sys.executable, "-m", "graphy", "check"])]:
    print(f"{label}: {med(cmd):.1f} ms")
PY
python3 -X importtime -m graphy --help 2>&1 >/dev/null | sort -t'|' -k2 -rn | head          # what --help still loads, by cost
python3 -c "import sys, graphy.cli; print(len(sys.modules), sorted(m for m in sys.modules if m.startswith('graphy')))"
# the RED proofs
sed -i '4i import urllib.request' graphy/cli.py && python3 -m pytest -q tests/test_cli.py -k loads_no_verb; sed -i '4d' graphy/cli.py
sed -i '4i from graphy import smash as smash_lane' graphy/cli.py && python3 -m pytest -q tests/test_cli.py -k loads_no_verb; sed -i '4d' graphy/cli.py
sed -i 's/^_PRODUCER_NAMES = ("python_ast", "typescript_ast")/_PRODUCER_NAMES = ("python_ast",)/' graphy/cli.py && python3 -m pytest -q tests/test_cli.py -k producer_names; git checkout graphy/cli.py
cd .. && python3 measure.py run && python3 measure.py diff recon.before20.json recon.json
```

| measure | before | after |
|---|---|---|
| `python -m graphy --help`, median of 25 | 78.3 · 78.2 ms | 46.0 · 44.0 ms |
| the bare interpreter · `import graphy` · `import graphy.cli` · `--help` · `check` with no args | — | 11.1 · 32.4 · 37.9 · 45.2 · 63.4 ms |
| modules loaded by `import graphy.cli` · of them `graphy.*` | 192 · 29 | 113 · 5 (the surface and `cli`) |
| the costliest import under `--help` (`-X importtime`, cumulative) | `graphy.cli` 35.1 ms: `graphy.ir` 13.0 · `graphy.index` 11.2 (`urllib.request` 9.9) · `federated_store` 5.6 · `fanout` 4.5 · `parity` 4.4 | `graphy` 18.7 ms: `graphy.ir` 13.3 · `parity` 4.3; `graphy.cli` itself 5.1 (`argparse`) |

| check | result |
|---|---|
| the floor | 470 passed · 3 skipped (468 + the two below) |
| the RED proofs | `urllib.request` at cli's top → `test_GREEN_cli_loads_no_verb_module_and_no_http_client` fails naming `email.parser …`; `from graphy import smash` at the top → fails naming the adapters; a producer dropped from `_PRODUCER_NAMES` → `test_GREEN_parser_producer_names_pin_the_minting_registry` fails naming `typescript_ast` |
| the gate | `GRAPHY_STANDALONE_OK` — burden: wheel 269,249 B under the cap, 0 runtime deps |
| the receipt | `measure.py run` then `diff recon.before20.json recon.json`: `MEASURE REGRESSION: 1 number(s) moved the wrong way — tenants.express.seconds 2.5 -> 2.9 (+16%)`, 45 others moved and every door on every tenant faster (fastapi · sqlalchemy · hono · express · graphy, 16–25 % off each `descend` · `blast` · `explain`, one process each), the floor 17.7 → 14.0 s under the receipt, the whole receipt 82.3 → 79.8 s, fastapi's rebuild RSS 183 → 166 MB, the wheel 269,605 B. The express number is noise: `bash tenants/express/rebuild.sh` timed directly, three runs each with the receipt's interpreter, reads before 2.61 · 2.58 · 2.60 s and after 2.39 · 2.36 · 2.37 s — faster, as every other tenant. Re-derive: `PYTHON=../.venv/bin/python; for i in 1 2 3; do /usr/bin/time -f %e bash tenants/express/rebuild.sh >/dev/null; done` on each side of `git stash` |

## 57 · THE RING'S PARQUET WAITS FOR THE FIRST ASK — one connection per batch, one JSON array per table, `eat` of an 85-shard ring 3.8 → 2.5 s (2026-09-07 · graphyos issue 21)

**What it was.** `graphy eat` emitted `adjacency.parquet` + `nodes.parquet` beside every shard of
the ring, each shard through its own `duckdb.connect()` (6 ms — as much as a whole shard's write)
and each table through a newline-JSON feed written one `json.dumps` per row. Over express's 86
shards the emit was 1.28 s of a 3.8 s eat: 0.49 s opening connections, 0.59 s writing, the rest
loading and digesting — for 85 ring parquets nobody had queried.

**What the profiler said, and why it was wrong by 5×.** The receipt read `container.emit` and
`_write_parquet` as the hottest engine frames in five of nine lanes — 6.0 s of tottime each in the
express quickstart. cProfile cannot see duckdb's pybind11 methods: no `execute` frame appears among
`_write_parquet`'s callees, its `ncalls` reads 2 for 86 calls, and the pybind11 time lands in the
caller's self time. The profiled eat took 7.6 s wall and reported 18.6 s of frames. The wall clock
says 1.28 s, and that is the number this section moves. The hot-frame rule (§48) still reads the
attribution, so `pass.engine_hot_lanes` is what it is until duckdb's calls are visible.

**What it is.**
- **One connection per batch.** `emit_all` and `estate` open one `duckdb.connect()` and pass it
  to every `emit`; `_write_parquet` creates its table `OR REPLACE` and drops it, so any number of
  writes run in a row on one connection. `emit` alone still opens its own.
- **One JSON array per table, never parameters.** The issue asked for rows bound as columns (a
  relation over Python lists, or `executemany`) and to measure both. Measured on the FastAPI
  fixture (3,715 edges · 507 nodes, both tables): the old per-row newline feed 22.0 ms; one
  `json.dumps` of the rows as an array + `read_json(format='array')` 14.7 ms; `INSERT … SELECT
  unnest($1), unnest($2), …` 958 ms (chunks of 64 · 256 · 1024 rows: 815 · 756 · 740 ms);
  `INSERT … VALUES (?, …)` in chunks of 100 · 500: 849 · 833 ms; `executemany` 3,038 ms; a dict of
  lists registered as a relation: refused by duckdb 1.5.5 (`not suitable for replacement scans`).
  Binding one list of 10 · 100 · 1,000 · 3,715 strings costs 1.5 · 5.6 · 52 · 190 ms — about 50 µs
  a value, so six columns of a shard cost a second where the array feed costs 15 ms (4.4 ms of it
  the dump, 4.1 ms the `COPY`). The file is the fast path; the round trip the issue named was not
  the cost, the connection and the per-row loop were. Under cProfile the array feed's hottest frame
  is `json/encoder.py:iterencode` — the stdlib's — where the per-row loop's was `_write_parquet`.
  A 60,000-row feed of 27 MB loads in 0.23 s (past `read_json`'s 16 MB per-object cap, since an
  array's elements are the objects).
- **The ring is pending until the estate asks.** `graphy build --container <slug>_graph` emits
  that shard's parquet now and writes a `pending` receipt (`container.json` with `"pending": true`,
  no parquet, a stale pair from an earlier emit removed) beside every other lane; `eat` passes the
  eaten package's own shard. `verify` reads `pending` as its own state — never stale, never a
  fault: `check` says `container fresh for 1/86 shard(s), 85 pending until the estate asks` and is
  green; `graphy container` says `CONTAINER PENDING: 1/86 fresh · 85 pending` and exits 0.
  `graphy estate` emits every pending container first, on the connection it queries with, and
  says so: `ESTATE: emitted 85 pending container(s) on the first ask — … 0.50 s`. `graphy
  container --emit` writes what is not fresh (pending · stale · absent) and names what it left:
  `CONTAINER OK: 85 shard(s) … · 1 already fresh`. `build` without `--container` emits all, as
  every tenant's `rebuild.sh` does; a shard the roster does not hold refuses by name.
- **Byte-identical content.** The parquet's rows and schema are compared equal (`ORDER BY ALL`)
  between the old feed and the array feed on both tables; the container receipt's row counts are
  the same integers; the index estate (`index_estate.py`, its own feed) is untouched, and the three
  questions of §35 over the farm index re-emitted with this code (718 shards · 967,530 nodes ·
  6,071,008 edges, 55.0 s) answer the same rows as before the re-emit: 157 packages · 8,041
  import edges of `typing_extensions`; `Exception` 270/1,529 · `Protocol` 122/1,519 · `Enum`
  121/1,440 over 18,960 rows; `sentry-sdk` 3 · `typer` 2 · `sglang` 2 over 6 rows.
- **One thread for the batch.** The first receipt of the shared connection read every tenant's
  peak RSS up 20–55 % (fastapi's `build` 177 → 237 MB, timed directly). Each of duckdb's eight
  worker threads keeps an allocator arena that outlives the query; per-shard connections had freed
  them ten times over. Measured on the fastapi tenant's ten shards, two passes: defaults 253 MB ·
  `memory_limit='64MB'` 256 · `allocator_flush_threshold='4MB'` 243 · `threads=2` 172 · `threads=1`
  150 MB and 0.61 s against 0.67 — a shard's write is too small to split. `emit_all` sets
  `threads = 1` on the connection for the batch and puts the caller's value back after; the build's
  RSS now reads 149 MB, under what it was.
- The graphy tenant eats graphy, so the walk moved: six arm regions re-rendered by `graphy arms`
  (five stamps, SEAM's inventory by two lines), `ARMS OK` on the rebuild.
- duckdb stays the optional extra; `build` still says `CONTAINER SKIPPED` without it. Nothing added.

```bash
cd engine
../.venv/bin/python - <<'PY'                     # the writer, measured: feed vs parameters (FastAPI fixture)
import sys, time, json, os; sys.path.insert(0, "."); import duckdb
from pathlib import Path; from graphy import container; from graphy.native_json_graph_ir import load_graph_ir
gd = Path("tests/fixtures/fastapi_graph"); gir = load_graph_ir(gd)
rows = container._edge_rows(list(gir.edges) + [r for r in gir.residuals if isinstance(r, dict) and r.get("kind") == "edge"])
cols = {"src": "VARCHAR", "dst": "VARCHAR", "edge_type": "VARCHAR", "attrs": "VARCHAR", "dst_repr": "VARCHAR", "src_repr": "VARCHAR"}
con = duckdb.connect(); out = Path("/tmp/adj.parquet")
def t(label, fn):
    ts = [];
    for _ in range(3): t0 = time.perf_counter(); fn(); ts.append(time.perf_counter() - t0)
    print(f"{label:24} {min(ts)*1000:8.1f} ms")
t("array feed", lambda: container._write_parquet(con, "adj", cols, rows, out))
def unnest():
    con.execute(f"CREATE OR REPLACE TABLE adj ({', '.join(f'{k} {v}' for k, v in cols.items())})")
    con.execute(f"INSERT INTO adj SELECT {', '.join(f'unnest(${i+1})' for i in range(len(cols)))}", [list(c) for c in zip(*rows)])
    con.execute(f"COPY adj TO '{out}' (FORMAT PARQUET)")
t("unnest($1..$6)", unnest)
for n in (10, 100, 1000, len(rows)):
    t(f"bind a list of {n}", lambda n=n: con.execute("SELECT count(*) FROM (SELECT unnest($1))", [[r[0] for r in rows[:n]]]).fetchall())
PY
# the eat, three each side (the express clone, 86 shards); the estate's first ask writes the ring
cd ../staging/quickstart/express; for i in 1 2 3; do /usr/bin/time -f "eat %e s" ../../../.venv/bin/graphy eat . 2>&1 | grep -E "^eat |CONTAINER"; done
/usr/bin/time -f "estate %e s" ../../../.venv/bin/graphy estate --tenant .graphy/tenant.json --tenant-id express --sql "SELECT count(*) FROM adj"
../../../.venv/bin/graphy container --tenant .graphy/tenant.json --tenant-id express | tail -1
cd ../../../engine
# the profiler's blind spot: no execute frame under _write_parquet, ncalls 2 for 86 calls
P=/tmp/p; rm -rf $P; (cd ../staging/quickstart/express && GRAPHY_PROFILE_DIR=$P ../../../.venv/bin/graphy eat . >/dev/null)
../.venv/bin/python -c "import pstats, glob; s = pstats.Stats(*glob.glob('$P/*.prof')); s.sort_stats('tottime').print_stats(3); s.print_callees('_write_parquet')"
# the RED proofs (each edit reverted after)
sed -i 's/        return \[emit(d, con=con) for d in dirs\]/        return [emit(d) for d in dirs]/' graphy/container.py && python3 -m pytest -q tests/test_container.py -k one_connection      # 4 connection(s) for 3 shards
python3 - <<'P'
from pathlib import Path; p = Path("graphy/container.py"); p.write_text(p.read_text().replace('    if receipt.get("pending") is True:\n        return "pending"\n', ''))
P
python3 -m pytest -q tests/test_container.py -k leaves_the_rest_pending                                                            # assert 'absent' == 'pending'
sed -i 's/receipts = emit_all(pending, con=con)/receipts = emit_all(pending)/' graphy/container.py && python3 -m pytest -q tests/test_container.py -k leaves_the_rest_pending   # 2 connection(s) to emit two and query three
sed -i 's/receipts, kept = container.emit_missing(dirs)/receipts, kept = container.emit_all(dirs), 0/' graphy/cli.py && python3 -m pytest -q tests/test_container.py -k leaves_the_fresh_alone   # 'CONTAINER OK: 2 shard(s)' not in 'CONTAINER OK: 3 shard(s) …'
git checkout graphy/container.py graphy/cli.py
# the farm's three questions, before and after a re-emit (§35's commands)
cd .. && python3 measure.py run && python3 measure.py diff recon.before21.json recon.json
```

| measure | before | after |
|---|---|---|
| `graphy eat .` on the express clone (86 shards, no provisioning), three runs | 3.86 · 3.76 · 3.82 s | 2.49 · 2.69 · 2.47 s |
| the container inside that eat | `86 shard(s) … 1.28 s beside the shards` | `1 shard(s) … 0.02 s beside express_graph; 85 pending` |
| the 86 shards' emit, direct: connect · load · rows · write · digest | 1.28 s: 0.49 · 0.04 · 0.03 · 0.59 · 0.04 | the estate's first ask writes 85 in 0.50 s (0.66 s wall); the second ask 0.16 s |
| the writer on the FastAPI fixture, both tables | per-row newline feed 22.0 ms | array feed 14.7 ms — `unnest` 958 · `VALUES` 833 · `executemany` 3,038 ms rejected by measurement |
| `duckdb.connect` calls in `emit_all` over N shards · in `estate` emitting P pending and querying N | N · 1 + P | 1 · 1 |
| the farm estate's three questions (718 shards) | 157 · 8,041 / 18,960 rows / 6 rows | the same rows |
| `graphy build` on the fastapi tenant, peak RSS | 177 MB | 237 MB with eight threads on the shared connection; 149 MB with one |

| check | result |
|---|---|
| the floor | 473 passed · 3 skipped (470 + 3: one connection per batch; `--container <shard>` leaves the rest pending, `check` green naming it, `container` PENDING exit 0, the estate emits on one connection and answers over all, a shard outside the roster refuses; `--emit` writes only what is not fresh) |
| the RED proofs | a connection per shard → `4 connection(s) for 3 shards`; `verify` blind to pending → `'absent' == 'pending'`; the estate emitting on a second connection → `2 connection(s) to emit two and query three`; `--emit` rewriting the fresh one → `'CONTAINER OK: 2 shard(s)' not in 'CONTAINER OK: 3 shard(s) …'` |
| the gate | `GRAPHY_STANDALONE_OK` — burden: wheel 269,605 B under the cap, 0 runtime deps |
| the receipt | `measure.py run` then `diff recon.before21.json recon.json`: `MEASURE DIFF OK: 49 number(s) moved, none the wrong way past tolerance` — `quickstart.express.seconds` 9.0 → 8.2 (`eat_again` 4.2 → 2.4), `quickstart.httpx.seconds` 5.7 → 4.7, every `tenants.*.seconds` down (express 2.9 → 2.5 · fastapi 3.1 → 2.9 · hono 2.6 → 2.4 · graphy 2.3 → 2.1 · sqlalchemy 6.1 → 5.8), every lane's RSS down 8–27 %, the floor 470 → 473 in 14.7 s, the whole receipt 79.8 → 74.3 s. `pass.engine_hot_lanes` 6 → 5: the express quickstart's hottest frame is now `pathlib`, the httpx quickstart's and the five tenants' still read `_write_parquet` — the pybind11 attribution above, which one lane fewer does not cure. The issue asked for two quickstart lanes off the count; one came off. The first receipt of this change, before the thread setting, read RSS up on four tenants and the graphy tenant RED on arms drift — both named above, both fixed before this row |

## 58 · THE GATE PARSES THE WORKFLOWS — a stdlib subset parser, strict where GitHub is, refuses the file that ran zero jobs with its line (2026-09-07 · graphyos issue 22)

**What it was.** The step name `the receipt (quick: the floor, the gate, the wheel)` carried an
unquoted `: ` — a mapping value inside a plain scalar — so `ci.yml` did not parse and every push
from that commit ran zero jobs: the run reads `failure` with no job to open and GitHub's summary
says *This run likely failed because of a workflow file issue*. The floor and the gate ran green on
this box each time; nothing on the box read the workflow files. §55 found it by hand while reading
the run list for the first CI timing.

**What it is.** `workflows.py` at the repo root, stdlib only, and the gate runs it after the
burden: every `*.yml` under `.github/workflows/` parsed by a parser for the YAML that workflows are
written in — block mappings and sequences, plain and quoted scalars, flow `[a, b]` and `{k: v}`,
block scalars `|` and `>`, comments — and shaped: the top level carries `name` · `on` · `jobs` and
only keys GitHub knows, every job `runs-on` and `steps` (or `uses`), `needs` names a job that
exists, every step exactly one of `uses` and `run` and only keys GitHub knows. Every refusal names
`file:line`. The parser is strict where GitHub is strict and stricter where being stricter costs
nothing at the gate: a plain scalar carrying `: ` refuses (the fault), a tab in the indentation
refuses, a duplicate key refuses, a sequence item indented past its siblings refuses, an empty key
refuses, a plain scalar continuing on the next line refuses (quote it or use `|`). No `yaml`, no
`actionlint`: `burden.json` still says zero runtime dependencies and the extras by name; the
census admits no new program.

**What proves the parser.** PyYAML is on the box's system interpreter (never the gate's): the
five workflow files parse to the same structure under both (every key, every value, every block
scalar byte-identical, PyYAML's `on` → `True` mapped back), and a sweep of 2,838 single-line
mutations of the five files (a quote dropped, a line dedented, indented, tabbed, deleted,
duplicated, a colon appended or dropped, a bracket or a quote left open) reads: 2,641 agree, 197
mine refuses and PyYAML accepts (duplicate keys, a bare scalar where a block is expected, a
multi-line quoted scalar — each a refusal GitHub or this gate wants), 0 mine accepts and PyYAML
refuses. The first sweep read 25 accepted-bad — an empty key `: x`, and `- uses:` read as a key
when a step was indented past its siblings — both refused now and both on the floor.

```bash
# from the repo root
python3 workflows.py                                       # WORKFLOWS OK: 5 file(s) … parse and carry name · on · jobs, every step uses or runs
git show 6e47127:.github/workflows/ci.yml > /tmp/broken/ci.yml && python3 workflows.py /tmp/broken   # …/ci.yml:43: mapping values are not allowed here — the plain scalar 'the receipt (quick: …)' carries ': '; quote it — exit 3
bash standalone_check.sh                                   # the gate: … WORKFLOWS OK … GRAPHY_STANDALONE_OK; with the broken ci.yml in place: workflows FAILED, exit 3
# the run list the issue read (the public repo, ci.yml): 31 runs, 21 failure — 18 of them with zero jobs
gh run list --repo omnislash157/graphyos --workflow ci.yml --limit 100 --json conclusion,databaseId -q '.[] | select(.conclusion=="failure") | .databaseId' | while read id; do gh run view $id --repo omnislash157/graphyos --json jobs -q '.jobs | length'; done | sort | uniq -c
# the cross-check and the sweep (PyYAML on the system interpreter, never the gate's)
python3 - <<'P'                                            # five True: every key, value and block scalar the same, leaves compared as strings
import yaml, glob, importlib.util as u
s = u.spec_from_file_location("wf", "workflows.py"); wf = u.module_from_spec(s); s.loader.exec_module(wf)
norm = lambda x: {("on" if k is True else str(k)): norm(v) for k, v in x.items()} if isinstance(x, dict) else [norm(v) for v in x] if isinstance(x, list) else None if x is None else str(x).lower() if isinstance(x, bool) else str(x)
for f in sorted(glob.glob(".github/workflows/*.yml")): print(f, norm(wf.parse(open(f).read())) == norm(yaml.safe_load(open(f))))
P
cd engine && python3 -m pytest -q tests/test_workflows.py   # 10 passed
```

| check | result |
|---|---|
| the floor | 483 passed · 3 skipped (473 + 10: the subset parses as PyYAML does on a workflow with every construct the five files use; the unquoted colon refused at line 19; six faults each naming its line — a deeper-indented step, a duplicate key, an empty key, a tab, an open bracket, a continued scalar; the shape naming what GitHub would refuse; the repo's own directory green and a directory holding the fault red by `file:line`) |
| the gate | `GRAPHY_STANDALONE_OK` with `WORKFLOWS OK: 5 file(s)` after `BURDEN OK`; the step costs 23 ms |
| the fault, re-run | `ci.yml` at 6e47127 through `workflows.py`: `ci.yml:43: mapping values are not allowed here — the plain scalar 'the receipt (quick: the floor, the gate, the wheel)' carries ': '; quote it`, exit 3 — the same line and column-33 fault PyYAML names |
| the burden | unchanged: 0 runtime deps, 3 extras, 6 programs — the parser is 471 lines of stdlib |

## 59 · THE STORE'S TMP FILE PAYS NO DURABILITY UNTIL IT IS THE STORE — the schema script 65 → 0.3 ms, the floor 13.9 → 7.5 s, one fsync where there were dozens (2026-09-07 · graphyos issue 23)

**What it was.** `compile_store` fills a `.tmp.<pid>` sqlite file and renames it over the store.
That tmp file paid full durability on every statement: `SCHEMA` is eight DDL statements, each its own
journaled transaction — create the journal, write, sync, delete — so `executescript(SCHEMA)` took
**65 ms wall on disk and 0.2 ms in `:memory:`**, under 1 ms of it CPU (`getrusage` around the call:
user 0.0–0.6 ms, sys 0.9–1.2 ms). Then a journaled `commit` at the end, ~30 ms more. Every build,
every eat, every rebuild, every refresh sibling, and the floor's 90 `compile_store`s paid it: the
profiled floor read `executescript` 90 calls · 14.7 s and `commit` 93 · 2.9 s as its top two frames,
called from `compile_store` only. `strace -c` attributed 1.5 ms to 38 `fdatasync`s — the wait is
inside sqlite's journal cycle, not in a syscall strace times, which is why no earlier profile named
it and the receipt read this lane as engine-hot on `_write_parquet` instead (the pybind11 attribution
of §57, again).

**What it is.** The tmp connection runs `PRAGMA journal_mode=OFF` and `PRAGMA synchronous=OFF`
before the schema — the file is garbage until the rename, and a crash mid-build leaves a `.tmp.<pid>`
the next build unlinks, exactly as before — and after `close()` the finished file is fsynced once,
then renamed. What lands under the store's name is complete, never torn: the durability the
per-statement journal bought, paid once. The directory is not synced; the old compile never synced
it either, and a rename lost to a crash leaves the previous store whole. The first cut synced the
directory too and the floor read 8.8–9.0 s; dropping it read 7.1–8.1. The pragmas live on the tmp
connection only: the landed store answers `PRAGMA journal_mode` → `delete`, and `open_for` opens it
read-only as before. The schema, the rows, the meta, the digest, the generation: unchanged —
`check` green on every tenant, the doors' answers on every tenant byte-identical before and after.
`compile_store` is the only sqlite writer in the engine (`rg 'sqlite3.connect' engine/graphy`: it and
`open_for`'s `mode=ro`).

```bash
# from engine/
../.venv/bin/python - <<'P'
import sqlite3, tempfile, time; from pathlib import Path; from graphy.federated_store import SCHEMA, TMP_STORE_PRAGMAS
for label, path, pre in [("file, as before", None, []), (":memory:", ":memory:", []), ("file, as it fills now", None, list(TMP_STORE_PRAGMAS))]:
    db = sqlite3.connect(path or str(Path(tempfile.mkdtemp())/"s.sqlite")); [db.execute(p) for p in pre]
    t0 = time.perf_counter(); db.executescript(SCHEMA); print(f"{label:24} {(time.perf_counter()-t0)*1000:6.1f} ms")
P
for i in 1 2 3; do /usr/bin/time -f "floor %e s" ../.venv/bin/python -m pytest -q -q -p no:cacheprovider 2>&1 | grep floor; done
for i in 1 2 3; do /usr/bin/time -f "build %e s" ../.venv/bin/graphy build --tenant tenants/fastapi/tenant.json --tenant-id fastapi 2>&1 | grep '^build'; done
../.venv/bin/python -m pytest -q tests/test_federated_store.py -k tmp_store_syncs_once
# the RED proofs (each edit reverted after)
python3 - <<'P'
from pathlib import Path; p = Path("graphy/federated_store.py"); p.write_text(p.read_text().replace("        for pragma in TMP_STORE_PRAGMAS:\n            db.execute(pragma)\n", ""))
P
../.venv/bin/python -m pytest -q tests/test_federated_store.py -k tmp_store_syncs_once      # assert [] == ['PRAGMA journal_mode=OFF', 'PRAGMA synchronous=OFF']
sed -i 's/    _sync_then_replace(tmp, p)/    os.replace(tmp, p)/' graphy/federated_store.py
../.venv/bin/python -m pytest -q tests/test_federated_store.py -k tmp_store_syncs_once      # assert [('replace', …tmp…)] == [('fsync', …tmp…), ('replace', …)]
# the same answer: every door on every tenant, before and after
for t in fastapi sqlalchemy hono express graphy; do seed=$(python3 -c "import json; p=json.load(open('tenants/$t/partition.json')); print('$t://module/'+next(iter(p['groups'].values()))[0])"); for v in explain blast descend; do ../.venv/bin/graphy $v "$seed" --tenant tenants/$t/tenant.json --tenant-id $t --depth 2 | grep -v '^DOOR:'; done; ../.venv/bin/graphy check --tenant tenants/$t/tenant.json --tenant-id $t | tail -1; done > /tmp/doors.after.txt; diff /tmp/doors.before.txt /tmp/doors.after.txt
cd .. && python3 measure.py run && python3 measure.py diff recon.before23.json recon.json
```

| measure | before | after |
|---|---|---|
| `executescript(SCHEMA)` on the tmp file | 65 ms (70.9 in the same run as the after) | 0.3 ms |
| the floor, three runs, `/usr/bin/time` | 13.3 · 13.9 · 14.1 s | 7.9 · 8.1 · 7.1 s (the experiment before the change, file fsync only: 7.2 · 7.3 · 7.4; with a directory fsync too: 8.8 · 9.0 · 8.8) |
| `graphy build` on the fastapi tenant, three runs | 0.74 · 0.93 · 0.75 s | 0.97 · 0.65 · 0.64 s |
| syncs per `compile_store` | one per DDL statement and per commit (the journal cycle) | one `fsync` of the finished file |

| check | result |
|---|---|
| the floor | 484 passed · 3 skipped (483 + 1: the two pragmas run on the tmp connection before the schema, the finished file is fsynced then renamed, the landed store's `journal_mode` reads `delete`) |
| the RED proofs | the pragmas removed → `assert [] == ['PRAGMA journal_mode=OFF', 'PRAGMA synchronous=OFF']`; the rename without the sync → `assert [('replace', …)] == [('fsync', …), ('replace', …)]` |
| the same answer | every door on every tenant and every `check`: `diff` empty, and with old code and new code on the same shards under `PYTHONHASHSEED=0`, 131 lines, `diff` empty. Without the seed pinned one hop-2 parent on the fastapi blast differs between two builds of one shard — old code or new, the same: the mesh's edge set iterates in hash order and the store's rowids follow it (issue 26, found here, filed) |
| the gate | `GRAPHY_STANDALONE_OK` — the receipt's gate 21.0 → 17.4 s; the graphy tenant's six arm regions re-rendered (`_sync_then_replace` and the test moved the walk: 2619 → 2627 nodes, 6526 → 6540 edges) |
| the receipt | `measure.py run` then `diff recon.before23.json recon.json`, three times. The first read the gate RED (CHANGELOG drift — §59 appended before the wheel step regenerated it) and the graphy tenant RED (the arm drift above), both fixed before this row. The second, under the operator's browser at 30 % CPU: `floor.seconds` 14.7 → 7.9, `gate.seconds` 21.0 → 16.8, `quickstart.express.seconds` 8.2 → 5.5, `tenants.express.seconds` 2.5 → 1.8, the whole receipt 74.3 → 62.7 s; eight numbers the wrong way, every one a door at 60–120 ms moving by 10 ms or the httpx quickstart — the doors timed direct on the old and the new store read 0.07 s five times each, the httpx eat direct 0.52 · 0.54 · 0.52 s. The third, same load: `floor.seconds` 14.7 → 9.1, `gate.seconds` → 17.4, `pass.engine_hot_lanes` 5 → 4 (the floor lane came off the count: its hottest frame is no longer the engine's), the receipt 74.3 → 66.4 s, one number the wrong way — `quickstart.httpx.seconds` 4.7 → 5.7, the cold quickstart's clone and pip provisioning: run cold three times by hand it reads 4.82 · 5.36 · 5.40 s, and `eat_again_seconds` in the same lane 0.6 → 0.5. A fourth, the browser still on the box (load 2.3): `floor.seconds` → 11.0, `gate.seconds` → 18.0, three the wrong way — the httpx quickstart's clone-and-provision again (4.2 → 5.3 · 4.7 → 5.9) and `tenants.fastapi.seconds` 2.9 → 3.4, which the same rebuild timed 3.0 twice in the runs before. `MEASURE DIFF` exits 1 on those; the done block's diff line reads red on a network lane and a loaded box, the engine lines read green, and the issue stays open for the operator's ruling — the march holds on it rather than closing over a red line |

## 60 · THE SCAN NEVER QUEUES A LEAF — one set lookup per child, `_scan` 210 → 95 ms over 400 files, the mint's hottest frame is the parse (2026-09-07 · graphyos issue 24)

**What it was.** `python_ast._scan` — one level-order pass per file (§53) — pushed and popped every
node, and on sqlalchemy 56 % of every node is a leaf that carries no import, no call and no scope:
546,810 nodes over 400 files, `Constant` 173,181 (32 %) and `Load`/`Store`/`Del` 131,239 (24 %).
Each leaf paid the `_fields` loop, a `getattr` and two `isinstance`s to discover it had no children,
and every node paid four class tests (`is Call` · `in Imports` · `in Func` · `issubclass(Scope)`).
The sqlalchemy mint's profile read `_scan` 286 calls · 0.826 s self · 1.388 s cumulative, with
`isinstance` 2.35 M calls · 0.18 s, `getattr` 1.36 M · 0.14 s, `issubclass` 0.79 M · 0.10 s beneath
it — above `compile` (the parse) at 0.51 s, so three of the receipt's lanes (fastapi · graphy ·
sqlalchemy) read the engine as hottest on this frame.

**What it is.** `_VISITED` is every AST class minus the leaves (`expr_context` · `operator` ·
`boolop` · `unaryop` · `cmpop` · `Constant`): a child is queued when `type(child) in _VISITED`,
one set lookup, no `isinstance` — a string child (`MatchClass.kwd_attrs`) fails the lookup the
same way a leaf does. `_class_info(cls)` is computed once per class: what the scan does at a node
of that class (call · import · function · scope · other) and which of its fields can hold a visited
node — the identifiers and ints of the grammar (`id` · `arg` · `attr` · `name` · `asname` ·
`module` · `level` · `is_async` · `conversion` · `kind` · `simple`) and `ctx` · `op` · `ops` ·
`type_comment` are left out. The loop reads the node's `__dict__` once. The records are the same
bytes: the walk order over the visited nodes is `ast.walk`'s minus the nodes that produce nothing.
Three cuts, each measured on the 400 files (best of 7): the leaf skip alone 210 → 128 ms, the
per-class kind and the string fields dropped 107, the single set lookup 95–99.

**What proves it.** Old scanner (the parent commit's module, loaded beside the new) and new over the
graphy corpus in one process: 113 files, 113 identical record streams. fastapi (ten shards, minted
from the corpus venv) and sqlalchemy (three) rebuilt: every `nodes.json` and `edges.json` the same
sha256 as before, 26 files. The graphy tenant's own shards move because its corpus moved (this
change is in it) — the in-process proof above covers it. `wormhole_edges.json` differs on every
rebuild, old code or new: `converge` stamps `resolved_at` into the sidecar, so no rebuild is
byte-identical there (a finding, filed). The visit-count test (§53, graphyos #14) now pins pops to
nodes minus leaves and refuses when a leaf is queued: with the leaves put back in `_VISITED` it reads
`(41, 52, 13)` — 41 pops against 39.

```bash
# from engine/
P=/tmp/prof-sa; rm -rf $P; PYTHON=$(pwd)/../.venv/bin/python GRAPHY_PROFILE_DIR=$P bash tenants/sqlalchemy/rebuild.sh > /dev/null
../.venv/bin/python -c "import pstats, glob; s = pstats.Stats(*glob.glob('$P/smash-*.prof')); s.sort_stats('tottime').print_stats(6)"
../.venv/bin/python - <<'P'
import ast, glob, timeit; from graphy.adapters import python_ast as pa
files = sorted(glob.glob("../staging/corpora/**/sqlalchemy/**/*.py", recursive=True))[:400]; trees = [ast.parse(open(f, "rb").read()) for f in files]
print(f"_scan {min(timeit.repeat(lambda: [pa._scan(t) for t in trees], number=1, repeat=7))*1000:.0f} ms over {len(files)} files")
P
git show HEAD~1:engine/graphy/adapters/python_ast.py > /tmp/python_ast_old.py    # the parent commit's scanner
../.venv/bin/python - <<'P'
import importlib.util; from pathlib import Path; from graphy.adapters import python_ast as new
s = importlib.util.spec_from_file_location("graphy.adapters.python_ast_old", "/tmp/python_ast_old.py"); old = importlib.util.module_from_spec(s); s.loader.exec_module(old)
root = Path(".").resolve(); pairs = [(list(old._emit_records_for_file(f, root, pkg)), list(new._emit_records_for_file(f, root, pkg))) for pkg in ("graphy", "tests") for f in sorted((root / pkg).rglob("*.py"))]
print(len(pairs), "files,", sum(a == b for a, b in pairs), "identical")
P
for t in fastapi sqlalchemy; do sha256sum tenants/$t/substrate/*_graph/nodes.json tenants/$t/substrate/*_graph/edges.json; done > /tmp/before.sha   # on the parent commit
# … rebuild both on this commit (fastapi with GRAPHY_CORPUS_SITE_PACKAGES=<the corpus venv's site-packages>) …
for t in fastapi sqlalchemy; do sha256sum tenants/$t/substrate/*_graph/nodes.json tenants/$t/substrate/*_graph/edges.json; done > /tmp/after.sha && diff /tmp/before.sha /tmp/after.sha
python3 -m pytest -q tests/test_adapters.py tests/test_smash.py tests/test_parity.py
# the RED proof (reverted after): the leaves queued again
sed -i 's/ and issubclass(c, ast.AST)) - _LEAF$/ and issubclass(c, ast.AST))/' graphy/adapters/python_ast.py && python3 -m pytest -q tests/test_adapters.py -k visits_every_node   # (41, 52, 13)
cd .. && python3 measure.py run && python3 measure.py diff recon.before24.json recon.json
```

| measure | before | after |
|---|---|---|
| `_scan` self · cumulative, sqlalchemy mint, 286 files (profiled) | 0.826 · 1.388 s | 0.367 · 0.567 s |
| the mint's hottest frame | `_scan` | `compile` (0.52 s) — the lane off the engine-hot count |
| the sqlalchemy `smash`, profiled total | 3.61 s | 2.85 s |
| `_scan` over 400 sqlalchemy files, best of 7 | 210 ms | 95 ms |
| `isinstance` · `getattr` · `issubclass` calls beneath the mint | 2.35 M · 1.36 M · 0.79 M | 1.12 M · — · — (`dict.get` 2.40 M, 0.23 s, is now the loop's own lookups) |

| check | result |
|---|---|
| the floor | 484 passed · 3 skipped — the visit-count test re-pinned: pops = nodes − leaves, refusing a queued leaf |
| the RED proof | the leaves put back in `_VISITED` → `AssertionError: (41, 52, 13)` |
| the same answer | 113 of 113 graphy files identical old vs new in one process; 26 `nodes.json` · `edges.json` over fastapi and sqlalchemy the same sha256 after a rebuild; parity against the golden fixture green |
| the gate | `GRAPHY_STANDALONE_OK`; the receipt's gate 18.0 → 15.7 s; the graphy tenant's six arm regions re-rendered (`_class_info` moved the walk: 2627 → 2628 nodes) |
| the receipt | `measure.py run` then `diff recon.before24.json recon.json`: **`pass.engine_hot_lanes` 5 → 2** — `tenants.fastapi` · `tenants.graphy` · `tenants.sqlalchemy` off the count, their hottest frame now `compile`; `floor.seconds` 11.0 → 8.2, `gate.seconds` 18.0 → 15.7, `tenants.fastapi.seconds` 3.4 → 3.0, `quickstart.httpx.seconds` 5.9 → 5.3; three numbers the wrong way and none the engine's — `quickstart.express.seconds` 5.1 → 8.4 (the cold quickstart's `npm install` over the network: the lane read 8.2 · 8.1 · 7.7 · 5.5 · 5.1 · 8.4 across the last six receipts), `wheel.seconds` 2.9 → 3.9 (pip and build), `tenants.fastapi.doors.seconds` 0.079 → 0.091 (12 ms on a 60–120 ms door). `MEASURE DIFF` exits 1 on those three; closed on the engine lines by the operator's standing ruling (§59) |

## 61 · EAT WRITES NO PARQUET — every shard pending until the first ask, duckdb off eat's import surface, the httpx eat 0.53 → 0.41 s (2026-09-07 · graphyos issue 25)

**What it was.** §57 deferred the ring's parquet to the first ask and kept the package's own,
written at eat through `build --container <slug>_graph`. That one write was the only reason eat
imported duckdb: on the httpx clone the container's own clock read `0.03 s beside httpx_graph`,
`import duckdb` 41–48 ms and `connect` 6–7 ms in a fresh process — about 55 ms of a 550 ms eat —
for a file nobody had asked for (`showcase` never opens the estate; the six ring receipts still read
pending after it). The receipt read the lane engine-hot on `_write_parquet`, 0.30 s self of a
1.06 s profiled eat with no duckdb frame beneath it: the pybind11 attribution of §57, a frame that
costs 30 ms on the wall clock.

**What it is.** `build --container none`: a pending receipt beside every shard, no parquet, no
duckdb imported — `container.defer` needs none, and the branch returns before `have_duckdb` is
asked. `eat` passes it. `graphy estate` writes every pending shard on the first ask, on the
connection it queries with, and says how many; `graphy container --emit` writes them now; `check`
reads `container fresh for 0/7 shard(s), 7 pending until the estate asks` and is green. The one
shard written at eat cost 30 ms; the first ask writes it beside the ring's in the same 0.28 s
(httpx, 7 shards) or 0.55 s (express, 86).

```bash
# in an eaten clone (staging/quickstart/httpx)
for i in 1 2 3; do /usr/bin/time -f "eat %e s" ../../../.venv/bin/graphy eat . 2>&1 | grep -E '^eat |CONTAINER'; done
../../../.venv/bin/python -X importtime -m graphy eat . 2>&1 >/dev/null | grep -c ' duckdb'          # 0 (was 6 lines, duckdb 30.5 ms cumulative)
grep -c '"pending": true' .graphy/substrate/*/container.json | grep -c ':1'                        # 7
/usr/bin/time -f "estate first ask %e s" ../../../.venv/bin/graphy estate --tenant .graphy/tenant.json --tenant-id httpx --sql "SELECT count(DISTINCT corpus) FROM adj"
../../../.venv/bin/graphy container --tenant .graphy/tenant.json --tenant-id httpx | tail -1        # CONTAINER OK: 7/7 fresh
cd ../../../engine && python3 -m pytest -q tests/test_container.py -k container_none
# the RED proof (reverted after): the none branch removed — `none` names no shard, build exits 2
cd .. && python3 measure.py run && python3 measure.py diff recon.before25.json recon.json
```

| measure | before | after |
|---|---|---|
| `graphy eat .` on the httpx clone (7 shards), three runs | 0.52 · 0.54 · 0.52 s | 0.42 · 0.40 · 0.42 s |
| `graphy eat .` on the express clone (86 shards), three runs, old code vs new in the same minute | 2.29 · 2.28 · 2.35 s | 2.24 · 2.25 · 2.21 s |
| `import duckdb` on eat's import surface (`-X importtime`) | 6 lines, 30.5 ms cumulative | none |
| the container at eat | `1 shard(s) … 0.03 s beside httpx_graph; 6 pending` | `CONTAINER PENDING: 7 shard(s)` |
| the estate's first ask | writes 6 | writes 7 in 0.28 s (httpx) · 86 in 0.55 s (express), answers over all |

| check | result |
|---|---|
| the floor | 485 passed · 3 skipped (484 + 1: `--container none` with duckdb made unimportable exits 0 naming three pending, `check` green naming them, the estate's first ask writes and answers over three, all fresh after) |
| the RED proof | the branch removed → `assert 2 == 0` — `none` names no shard in the roster |
| the gate | `GRAPHY_STANDALONE_OK` |
| the receipt | `measure.py run` then `diff recon.before25.json recon.json`: **`pass.engine_hot_lanes` 2 → 1** — `quickstart.httpx` off the count (`stdlib_hot` False → True), the floor the one lane left; `quickstart.httpx.rss_kb` 121,732 → 54,384 (−55 %) and `quickstart.express.rss_kb` 109,756 → 45,844 (−58 %) — duckdb no longer lives in the eat process; `quickstart.httpx.eat_seconds` 4.3 → 4.0, `eat_again_seconds` 0.5 → 0.4 (httpx) · 2.5 → 2.3 (express), `gate.seconds` 15.7 → 14.5, every tenant's doors faster; two numbers the wrong way and neither the engine's — `tenants.fastapi.seconds` 3.0 → 3.5 (the same rebuild timed by hand right after: 2.85 · 3.32 · 6.89 s, the box's noise), `wheel.seconds` 3.9 → 8.9 (pip, build and twine). `MEASURE DIFF` exits 1 on those two; closed on the engine lines by the standing ruling (§59) |

## 62 · THE STORE'S ROWS LAND IN ONE ORDER — the mesh's edge set inserted sorted, three seeds one rowid order, every tie a door breaks stays broken the same way (2026-09-07 · graphyos issue 26)

**What it was.** `MeshSet.directed` is a set of `(src, dst, rel)` tuples (`cross_substrate.py:195`,
filled at line 294), and `compile_store` inserted it in iteration order. A set of string tuples
iterates in hash order and the hash is salted per process, so three `graphy build`s of the fastapi
tenant from the same shards landed the same rows at three rowid orders (md5 of the rows by rowid:
`e1be29a77185` · `c8ec0fea5ae9` · `cf3e5b336e6b`; the rows as a set `ffaf9be63993` every time), and
`SELECT … WHERE dst=?` through `idx_edges_dst` returns index order `(dst, rowid)` — so every tie a
door breaks by row order broke differently: found under §59 when `blast fastapi://module/fastapi.routing`
on two builds of one shard printed a hop-2 node under two parents and `BY OWNER: tests=2 graphy=2`
in the other order. A store built twice on one box, or once on two, spelled one set in two orders.

**What it is.** `compile_store` inserts `sorted(mesh.directed)`. The node rows already came from
`node_owner`, a dict filled in shard order. Nothing else changes: the generation is a digest of the
inputs, the rows are the same set, `check` is green on every tenant. The ties move once — the
graphy tenant's six arm regions re-rendered (six lines), the atlas re-drawn — and then hold on any
seed, on any box. `PYTHONHASHSEED=0`, the workaround §59's proof needed, is not needed.

```bash
# from engine/
for i in 1 2 3; do PYTHONHASHSEED=$i ../.venv/bin/graphy build --tenant tenants/fastapi/tenant.json --tenant-id fastapi >/dev/null; ../.venv/bin/python -c "import sqlite3, glob, hashlib; p = sorted(glob.glob('tenants/fastapi/substrate/.mesh_store_*.sqlite'))[-1]; print(hashlib.md5(repr(sqlite3.connect(p).execute('SELECT src,dst,rel FROM edges ORDER BY rowid').fetchall()).encode()).hexdigest()[:12])"; done | sort -u | wc -l    # 1 (was 3)
python3 -m pytest -q tests/test_federated_store.py -k two_hash_seeds      # three subprocess builds under seeds 1 · 2 · 3, one row order, sorted
# the RED proof (reverted after): the parent commit's compile_store
git show HEAD~1:engine/graphy/federated_store.py > graphy/federated_store.py && python3 -m pytest -q tests/test_federated_store.py -k two_hash_seeds   # AssertionError: the row order followed the hash seed
cd .. && python3 measure.py run && python3 measure.py diff recon.before26.json recon.json
```

| check | result |
|---|---|
| three seeds, one row order | `1` distinct md5 over seeds 1 · 2 · 3 (was 3 over three unseeded builds) |
| the floor | 486 passed · 3 skipped (485 + 1); the RED proof against the parent's code: `the row order followed the hash seed` |
| the same answer | the rows as a set unchanged; `check` green on every tenant; the graphy tenant's arms re-rendered once and verify; the atlas 8 pictures checked |
| the gate | `GRAPHY_STANDALONE_OK` |
| the receipt | `measure.py run` then `diff recon.before26.json recon.json`: every tenant faster or flat (fastapi 3.5 → 2.7 · sqlalchemy 6.0 → 5.5 · hono 2.4 → 2.3 · graphy 2.0), the receipt 68.2 → 60.4 s, `pass.engine_hot_lanes` 1 (the floor); one number the wrong way — `quickstart.httpx.eat_seconds` 4.0 → 4.7, the cold eat's venv and pip over the network (§59: 4.2 · 4.5 · 5.3 · 4.3 · 4.0 · 4.7 across the last receipts), the eat itself untouched by a sort of the edge rows at build. `MEASURE DIFF` exits 1 on it; closed on the engine lines by the standing ruling (§59) |

## 63 · THE SIDECAR CARRIES THE RING'S DIGEST, NEVER A CLOCK — two rebuilds of one commit are the same bytes on every shard (2026-09-07 · graphyos issue 27)

**What it was.** `converge.resolve` stamped `"resolved_at": datetime.now(...)` into every
`wormhole_edges.json`, so two rebuilds of the fastapi tenant on one commit — every `nodes.json` and
`edges.json` the same sha256 — differed on all ten sidecars. Found under §60 while proving a scanner
change byte-identical: the proof had to fall back to `nodes.json` · `edges.json` and an in-process
comparison, and eat-again's splice (§53) could never compare a sidecar.

**What it is.** `ring_source_digest(data_home, slugs)` — sha256 (16 hex) over the bytes of every
ring shard's `nodes.json` and `edges.json`, never a sidecar, folded in slug order; `Ring` computes it
once and every sidecar's summary carries it as `resolved_over`: what the resolve is a function of,
so a reader can tell which shards a sidecar was resolved against — the freshness the clock was
standing in for, mechanically — and two resolves over the same shards are the same bytes. On the
express ring (86 shards, 2.1 MB of sources) the digest costs 4 ms once. `rg resolved_at engine/graphy`
finds nothing; nothing read it.

```bash
# from engine/
SP=$(ls -d ../staging/corpora/venv/lib/python*/site-packages | head -1)
PYTHON=$(pwd)/../.venv/bin/python GRAPHY_CORPUS_SITE_PACKAGES=$SP bash tenants/fastapi/rebuild.sh >/dev/null && sha256sum tenants/fastapi/substrate/*_graph/wormhole_edges.json > /tmp/w1.sha
PYTHON=$(pwd)/../.venv/bin/python GRAPHY_CORPUS_SITE_PACKAGES=$SP bash tenants/fastapi/rebuild.sh >/dev/null && sha256sum tenants/fastapi/substrate/*_graph/wormhole_edges.json > /tmp/w2.sha && diff /tmp/w1.sha /tmp/w2.sha   # empty (was: all ten differ)
rg -c resolved_at graphy/ | wc -l                                          # 0
python3 -m pytest -q tests/test_converge.py -k ring_digest                 # two resolves the same bytes; the stamp is the ring digest; a byte moved in a ring shard moves it
git show HEAD~1:engine/graphy/converge.py > graphy/converge.py && python3 -m pytest -q tests/test_converge.py -k ring_digest    # RED: 'resolved_at' in the summary (reverted after)
cd .. && python3 measure.py run && python3 measure.py diff recon.before27.json recon.json
```

| check | result |
|---|---|
| two rebuilds, ten sidecars | `diff` empty (was ten of ten different) |
| the floor | 487 passed · 3 skipped (486 + 1); the RED proof against the parent's code names `resolved_at` in the summary |
| the same answer | the sidecar's edges and counts unchanged — only the stamp's key and value; `check` green on every tenant; the graphy tenant's arms re-rendered (`ring_source_digest` · `source_digest` moved the walk) and verify |
| the gate | `GRAPHY_STANDALONE_OK` |
| the receipt | `measure.py run` then `diff recon.before27.json recon.json`: every engine number flat or better (the receipt 60.4 → 60.3 s, `quickstart.httpx.seconds` 5.3 → 4.5, `pass.engine_hot_lanes` 1 — the floor); one number the wrong way, `wheel.seconds` 2.8 → 3.5 (pip, build and twine). `MEASURE DIFF` exits 1 on it; closed on the engine lines by the standing ruling (§59) |

## 64 · INDEX VERIFY FANS OUT — 2 GB hashed over eight cores instead of one, the farm index 2.6 → 0.72 s, the same rows (2026-09-07 · graphyos issue 28)

**What it was.** `verify_index` fetched and re-hashed each catalog entry in a `for` loop: on the farm
index (718 named shards, 3,624 files, 1,956 MB) `graphy index --verify` took 2.65 · 2.62 · 2.58 s,
its profile `_hashlib.openssl_sha256` 2.17 s and `BufferedReader.read` 0.35 s — hashing is the
work, on one core of eight, and `hashlib` releases the GIL, as do the reads.

**What it is.** The same per-entry verify mapped over a `concurrent.futures.ThreadPoolExecutor`
of `VERIFY_THREADS` — one per core, capped at eight — with the rows returned in catalog order;
`threads=1` (or a catalog of one) runs the loop as before. `pull` and `push` verify one shard and
are untouched. Every refusal message is the same string from the same place. Stdlib only.

**The first cut tripled the lane's RSS, and the second cut it to a quarter of the original.** The
pooled loop still ran `_fetch_entry`, which reads a shard's three files whole, so eight threads
held eight shards: the receipt read `index.rss_kb` 169,256 → 560,060. `_verify_entry_streaming`
holds the manifest and the PROVENANCE only and hashes each payload file by chunks from the source
(`_Source.digest`: a local file streams from disk, a remote one from the response), then runs the
same manifest, address and PROVENANCE checks over the receipts (`_check_entry` · `_check_payload`,
which `verify_shard` and `_verify_entry` — the pull's path, bytes in hand — now share). Eight
threads hold eight 1 MB chunks: 40 MB peak, 0.53 s. The test reads the source through a spy and
refuses if a payload file is ever read whole.

```bash
# from engine/
for i in 1 2 3; do /usr/bin/time -f "index verify %e s" ../.venv/bin/graphy index --index $(pwd)/../staging/index/farm --verify 2>&1 | grep -E 'index verify|INDEX'; done
python3 -m pytest -q tests/test_index.py -k fans_out       # twelve shards, one with a flipped byte: the pooled rows equal the serial rows, more than one thread seen, alpha==7 named by edges.json
git show HEAD~1:engine/graphy/index.py > graphy/index.py && python3 -m pytest -q tests/test_index.py -k fans_out    # RED: verify_index() got an unexpected keyword argument 'threads' (reverted after)
cd .. && python3 measure.py run && python3 measure.py diff recon.before28.json recon.json
```

| measure | before | after |
|---|---|---|
| `graphy index --verify`, the farm index, three runs | 2.65 · 2.62 · 2.58 s | 0.72 · 0.72 · 0.72 s pooled over whole reads; 0.53 · 0.54 · 0.53 s pooled over chunked digests |
| the verb's peak RSS (`/usr/bin/time %M`) | 169 MB (one shard held whole) | 560 MB pooled over whole reads; 40 MB over chunked digests |
| `verify_index` in-process, the prototype | serial 2,578 ms | 4 threads 789 · 8 threads 663 ms, the same 718 rows |
| hashing 1,956 MB alone | 1,351 ms | 409 ms on 4 or 8 threads |

| check | result |
|---|---|
| the floor | 488 passed · 3 skipped (487 + 1: twelve shards, one with a flipped byte — the pooled rows equal the serial rows, more than one thread seen, `alpha==7` named by `edges.json`, no payload read whole); the RED proof against the parent's code names the missing `threads` |
| the same answer | the same 718 rows in the same order; the flipped byte named by file and address |
| the gate | `GRAPHY_STANDALONE_OK`; the graphy tenant's arms re-rendered (`_verify_one` moved the walk) |
| the receipt | `measure.py run` then `diff recon.before28.json recon.json`: **`index.verify_seconds` 2.6 → 0.5 (−81 %) · `index.rss_kb` 169,256 → 40,120 (−76 %)**, the receipt 57.4 → 54.5 s; the first receipt of the pooled loop over whole reads read `index.rss_kb` → 560,060 (+231 %) — the streaming digest above is what that number bought; one number the wrong way, `quickstart.httpx.seconds` 4.5 → 5.2 (the cold clone and pip over the network, §59). `MEASURE DIFF` exits 1 on it; closed on the engine lines by the standing ruling (§59) |

## 65 · THE NODE_MODULES SLUG MAP IS READ ONCE — 86 × 343 entry visits become one pass, the express eat 2.2 → 1.2 s, every shard byte-identical (2026-09-07 · graphyos issue 29)

**What it was.** `smash.node_dir_for(scheme, node_modules)` answered one scheme by scanning every
entry of node_modules — `sorted(glob("*")) + sorted(glob("@*/*"))`, an `is_dir()` and a
`relative_to(node_modules).as_posix()` per entry, then `slug_for_specifier` — and the ring asked it
once per scheme: on express 86 schemes × 343 entries, 26,402 `relative_to` calls from this one
function (on 3.12 `relative_to` walks `self.parents`, a Path per ancestor: 519,325 `Path.__init__`
calls in one eat). `typescript_ast.walk_files` paid `f.relative_to(root).parts` per file, where
`f.parts[len(root.parts):]` is the same tuple. The profiled eat read `relative_to` 3.01 s cumulative
of 6.01; in-process on the wall clock, `locate_node` over the 86 schemes cost 432 ms of a 2.2 s eat.

**What it is.** `node_dirs_of(node_modules)` builds the slug → directory map in one pass over the
entries — the specifier is `d.name`, or `f"{d.parent.name}/{d.name}"` under a scope — and caches it
by resolved path; `node_dir_for` is a dict lookup. The first directory in sorted order wins a slug,
as the scan did; a dotfile and a name with no slug are not entries. `walk_files` cuts the prefix by
parts. The same 85 directories, the same files in the same order: express's 86 shards re-minted
cold — 581 of 581 files parsed — carry the same `nodes.json` and `edges.json` sha256 as before,
172 files; hono's four the same after a rebuild.

```bash
# from engine/
../.venv/bin/python -c "import json, time; from pathlib import Path; from graphy import smash; nm = Path('../staging/quickstart/express/node_modules').resolve(); schemes = list(json.load(open('../staging/quickstart/express/.graphy/substrate/ring.json'))['minted']); t0 = time.perf_counter(); found = [smash.locate_node(s, nm) for s in schemes]; print(f'locate_node × {len(schemes)}: {(time.perf_counter()-t0)*1000:.0f} ms, {sum(f is not None for f in found)} located')"
(cd ../staging/quickstart/express && sha256sum .graphy/substrate/*_graph/nodes.json .graphy/substrate/*_graph/edges.json | awk '{print $1}' > /tmp/before.sha && rm -rf .graphy && ../../../.venv/bin/graphy eat . | tail -1 && sha256sum .graphy/substrate/*_graph/nodes.json .graphy/substrate/*_graph/edges.json | awk '{print $1}' > /tmp/after.sha && diff /tmp/before.sha /tmp/after.sha && echo identical)
(cd ../staging/quickstart/express && for i in 1 2 3; do /usr/bin/time -f "eat %e s" ../../../.venv/bin/graphy eat . 2>&1 | grep '^eat '; done)
python3 -m pytest -q tests/test_typescript.py -k slug_map     # six asks, one scan (glob called with "*" and "@*/*" once), a scoped package keyed by its specifier, the dotfile and the stray file not entries
git show HEAD~1:engine/graphy/smash.py > graphy/smash.py && python3 -m pytest -q tests/test_typescript.py -k slug_map    # RED: no attribute '_NODE_DIRS' (reverted after)
cd .. && python3 measure.py run && python3 measure.py diff recon.before29.json recon.json
```

| measure | before | after |
|---|---|---|
| `locate_node` over express's 86 schemes, in-process | 432 ms, 85 located | 10 ms, 85 located |
| `graphy eat .` on the express clone, three runs | 2.21 · 2.26 · 2.24 s (§61) | 1.20 · 1.22 · 1.19 s |
| the cold re-mint of express (581 files parsed) | — | 1.59 s |
| `walk_files` over the 85 package roots | 22 ms | 10 ms, the same 483 files |
| `hono` rebuild | 2.3 s (§64's receipt) | 2.30 s, four shards byte-identical |

| check | result |
|---|---|
| the floor | 489 passed · 3 skipped (488 + 1); the RED proof against the parent's code |
| the same answer | express: 172 `nodes.json` · `edges.json` the same sha256 after a cold re-mint; hono: 4 the same after a rebuild |
| the gate | `GRAPHY_STANDALONE_OK`; the graphy tenant's arms re-rendered (`node_dirs_of` moved the walk) |
| the receipt | `measure.py run` then `diff recon.before29.json recon.json`: **`quickstart.express.eat_again_seconds` 2.2 → 1.2 (−45 %)** — the eat over the eaten clone, the engine's own number in this lane — `tenants.express.seconds` 1.7 → 1.5, hono's doors and RSS down; three numbers the wrong way and none the locator's: `quickstart.express.eat_seconds` 4.4 → 6.1 and `.seconds` 5.0 → 6.6 (the cold eat's `npm install` over the network — the same lane read 7.7 · 8.4 · 8.1 · 5.0 · 6.6 across the last receipts), `tenants.fastapi.seconds` 2.7 → 3.3 (by hand under §61: 2.85 · 3.32 · 6.89, the box's noise). `MEASURE DIFF` exits 1 on those; closed on the engine lines by the standing ruling (§59) |

## 66 · THE ATLAS LAYS EACH PICTURE OUT ONCE — and places it once per orientation, sqlalchemy's atlas 1.86 → 1.50 s, the same files (2026-09-07 · graphyos issue 30)

**What it was.** `draw.render` called `S.layout(...)` on every call and `atlas` called it twice per
picture — ascii, then html — so every picture was laid out twice (263 ms of layout paid twice over
sqlalchemy's six pictures); and each emitter began with `_placed(lo, orient)`, the coordinate pass
(`_assign_cross`, 145 ms on ORM alone), again for the same orientation. `graphy draw --atlas` on
sqlalchemy: 1.86 s wall; in-process, building the six pictures from the store 328 ms, the ascii
emits 897 ms, the html emits 466 ms.

**What it is.** `draw.render` takes a `layout=` it is handed; `atlas` lays each picture out once and
hands it to both emits. `Layout.placed` memoizes the coordinate pass per orientation, so the second
emit reuses it (`_placed` looks the orientation up, `_place` is the pass). Old code and new over the
same store draw byte-identical atlases: sqlalchemy's 12 files and fastapi's 13. What remains is
the ascii canvas — ORM's is 625 rows × 3,477 columns: `Canvas.render` 0.49 s, `hseg` · `vseg`
0.47 s over the six pictures, and the crossing sweeps 0.52 s inside `layout` — a different issue.

**The token missed by a tenth.** The issue's done block said under 1.4 s; the atlas reads 1.51 ·
1.49 · 1.50. The layout-once and place-once cuts were the change; the tenth that remains is the
canvas, named above and filed. Closed with the miss named.

```bash
# from engine/
for i in 1 2 3; do /usr/bin/time -f "atlas %e s" ../.venv/bin/graphy draw --tenant tenants/sqlalchemy/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --atlas /tmp/atlas --partition tenants/sqlalchemy/partition.json 2>&1 | grep '^atlas'; done
git stash push graphy/sugiyama.py graphy/draw.py && ../.venv/bin/graphy draw … --atlas /tmp/atlas_old … && git stash pop && ../.venv/bin/graphy draw … --atlas /tmp/atlas_new … && diff -rq /tmp/atlas_old /tmp/atlas_new    # empty, sqlalchemy and fastapi
python3 -m pytest -q tests/test_draw.py -k lays_each_picture      # layout and _place each called once per picture over the fixture's atlas; the same files as before; render(pic, layout=lo) the same text
git show HEAD~1:engine/graphy/draw.py > graphy/draw.py && git show HEAD~1:engine/graphy/sugiyama.py > graphy/sugiyama.py && python3 -m pytest -q tests/test_draw.py -k lays_each_picture   # RED: no attribute '_place' (reverted after)
cd .. && python3 measure.py run && python3 measure.py diff recon.before30.json recon.json
```

| measure | before | after |
|---|---|---|
| `graphy draw --atlas` on sqlalchemy (6 pictures), three runs | 1.86 s | 1.51 · 1.49 · 1.50 s |
| `S.layout` calls · `_place` calls per atlas | 2 · 2 per picture | 1 · 1 per picture |
| fastapi's atlas (8 pictures, small) | 0.19 s | 0.18 s |

| check | result |
|---|---|
| the floor | 490 passed · 3 skipped (489 + 1); the RED proof against the parent's code |
| the same answer | old code vs new on the same store: sqlalchemy's 12 atlas files and fastapi's 13 byte-identical (`diff -rq` empty) |
| the gate | `GRAPHY_STANDALONE_OK`; the graphy tenant's arms re-rendered (`_place` moved the walk) |
| the receipt | `measure.py run` then `diff recon.before30.json recon.json`: **`MEASURE DIFF OK: 45 number(s) moved, none the wrong way past tolerance`** — the first clean receipt since §57; `tenants.fastapi.seconds` 3.3 → 2.8, `tenants.sqlalchemy.seconds` 5.5 → 5.6 (the atlas's 0.36 s inside a rebuild the box times to ±0.3), `pass.engine_hot_lanes` 1 (the floor) |

## 67 · THE CANVAS RENDERS THE DRAWING, NOT THE RECTANGLE — ORM's ascii 515 → 216 ms, the atlas 1.50 → 1.27 s, the same bytes (2026-09-07 · graphyos issue 31)

**What it was.** `Canvas.render` walked every cell of the rectangle: ORM's canvas is 625 rows ×
3,477 columns, 2.2 M cells, 678,327 `list.append`s and 215,583 `dict.get`s for a drawing that
touches a few percent of it — 0.217 s of the picture's 0.515 s ascii render. The road drawers
(`hseg` 11,460 calls · 0.148 s, `vseg` 3,501 · 0.079 s) wrote one dict entry per cell of every
road under a `(row, column)` tuple built per cell, for the crossing check.

**What it is.** The canvas records, per row, the last column any writer touched (`tile` · `hroad`
· `vroad` · `cross`), and `render` stops there: the blank tail is one run of spaces, preceded by
the colour reset the first blank cell would have emitted when the row's colour was still on, so
the text is the same bytes — the full-width rows included (a row ends in the reset, which `rstrip`
never strips, so every row was and is `w` wide). The road cells are keyed by row for the
horizontal roads and by column for the vertical ones: one lookup per cell, no tuple per cell, the
same crossing set. Old code and new over the same store: sqlalchemy's 12 atlas files and fastapi's
13 byte-identical. The test renders a canvas with a wide glyph, a coloured road that ends before
the edge, a heavy crossing road, a bridge and a road to the last column against the cell-by-cell
render copied verbatim into the test.

```bash
# from engine/
../.venv/bin/python - <<'P'
import time; from graphy import draw, federated_store as fs, fanout, sugiyama as S; from graphy.cli import _load_tenant
ten = _load_tenant("tenants/sqlalchemy/tenant.json"); subs = sorted(k[:-6] for k in ten.build_lanes)
store = fs.open_for(subs, tenant=ten, tenant_id="sqlalchemy", db_path=fs.store_path_for(subs, tenant=ten)); cut = fanout.load_partition("tenants/sqlalchemy/partition.json")
pic = draw.arm(store, "sqlalchemy", cut, "ORM"); lo = S.layout(pic.nodes, pic.edges, pic.labels); S._placed(lo, "LR")
t0 = time.perf_counter(); S.render(lo, title="ORM", orient="LR"); print(f"ORM ascii render {(time.perf_counter()-t0)*1000:.0f} ms")
P
for i in 1 2 3; do /usr/bin/time -f "atlas %e s" ../.venv/bin/graphy draw --tenant tenants/sqlalchemy/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --atlas /tmp/atlas --partition tenants/sqlalchemy/partition.json 2>&1 | grep '^atlas'; done
git stash push graphy/sugiyama.py && ../.venv/bin/graphy draw … --atlas /tmp/atlas_old … && git stash pop && ../.venv/bin/graphy draw … --atlas /tmp/atlas_new … && diff -rq /tmp/atlas_old /tmp/atlas_new    # empty, sqlalchemy and fastapi
python3 -m pytest -q tests/test_sugiyama.py -k not_the_rectangle
git show HEAD~1:engine/graphy/sugiyama.py > graphy/sugiyama.py && python3 -m pytest -q tests/test_sugiyama.py -k not_the_rectangle    # RED: 'Canvas' object has no attribute 'last' (reverted after)
cd .. && python3 measure.py run && python3 measure.py diff recon.before31.json recon.json
```

| measure | before | after |
|---|---|---|
| ORM's ascii render, layout and placement done | 515 ms | 267 ms with the row bound; 216 ms with the road cells keyed by row and column |
| `graphy draw --atlas` on sqlalchemy, three runs | 1.51 · 1.49 · 1.50 s (§66) | 1.29 · 1.27 · 1.27 s |
| the atlas since §65 | 1.86 s | 1.27 s |

| check | result |
|---|---|
| the floor | 491 passed · 3 skipped (490 + 1); the RED proof against the parent's code |
| the same answer | old code vs new on the same store: sqlalchemy's 12 atlas files and fastapi's 13 byte-identical |
| the gate | `GRAPHY_STANDALONE_OK`; the graphy tenant's arms re-rendered (`_touch` moved the walk) |
| the receipt | `measure.py run` then `diff recon.before31.json recon.json`: `tenants.sqlalchemy.seconds` 5.6 → 5.4, `pass.engine_hot_lanes` 1; two numbers the wrong way and neither the canvas's — `tenants.graphy.seconds` 2.1 → 2.8 (the same rebuild timed by hand right after: 1.98 · 1.98 · 2.07 s) and `index.verify_seconds` 0.5 → 0.6 (by hand: 0.54 · 0.56 · 0.54), the box's noise on a loaded afternoon. `MEASURE DIFF` exits 1 on those; closed on the engine lines by the standing ruling (§59) |

## 68 · THE CROSSING SWEEPS STOP WHEN THE ORDER STOPS MOVING — 4 to 12 sweeps instead of 24, the same best order, sqlalchemy's atlas 1.27 → 1.10 s (2026-09-07 · graphyos issue 32)

**What it was.** `_minimize_crossings` ran 24 sweeps on every picture — down, up, down, … — and
recounted every layer pair's crossings after each, stopping early only at zero. A median-order
sweep is a pure function of the order before it, so once an order repeats (a fixed point) every
further sweep returns it, and once it equals the order two sweeps back (a two-cycle) the sweeps
alternate the same two orders forever: `best` cannot improve after either. On sqlalchemy's six
atlas pictures the order stopped moving after 4 · 7 · 7 · 9 · 7 · 12 sweeps; the remaining 12–20
per picture recomputed the same orders and the same counts — `_minimize_crossings` 0.516 s of the
atlas's profile, `_total_crossings` 150 calls · 0.28 s.

**What it is.** The loop keeps the last two orders and stops when the new order equals either.
`best` is the same order kept at the same iteration. Old code and new over the same store:
sqlalchemy's 12 atlas files and fastapi's 13 byte-identical. The test runs `layout` over a
14-node tangle that never reaches zero crossings (14 remain) with the 24-sweep loop copied
verbatim beside it: the same layers, the crossing count called fewer than 25 times — 25 on the
parent's code.

```bash
# from engine/
for i in 1 2 3; do /usr/bin/time -f "atlas %e s" ../.venv/bin/graphy draw --tenant tenants/sqlalchemy/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --atlas /tmp/atlas --partition tenants/sqlalchemy/partition.json 2>&1 | grep '^atlas'; done
git stash push graphy/sugiyama.py && ../.venv/bin/graphy draw … --atlas /tmp/atlas_old … && git stash pop && ../.venv/bin/graphy draw … --atlas /tmp/atlas_new … && diff -rq /tmp/atlas_old /tmp/atlas_new    # empty, sqlalchemy and fastapi
python3 -m pytest -q tests/test_sugiyama.py -k sweeps_stop
git show HEAD~1:engine/graphy/sugiyama.py > graphy/sugiyama.py && python3 -m pytest -q tests/test_sugiyama.py -k sweeps_stop    # RED: assert 25 < 25 (reverted after)
cd .. && python3 measure.py run && python3 measure.py diff recon.before32.json recon.json
```

| measure | before | after |
|---|---|---|
| sweeps per picture, sqlalchemy's six | 24 each | 4 · 7 · 7 · 9 · 7 · 12 |
| `graphy draw --atlas` on sqlalchemy, three runs | 1.29 · 1.27 · 1.27 s (§67) | 1.11 · 1.10 · 1.11 s |
| the atlas since §65 | 1.86 s | 1.10 s |

| check | result |
|---|---|
| the floor | 492 passed · 3 skipped (491 + 1); the RED proof against the parent's code |
| the same answer | old code vs new on the same store: sqlalchemy's 12 atlas files and fastapi's 13 byte-identical |
| the gate | `GRAPHY_STANDALONE_OK` |
| the receipt | `measure.py run` then `diff recon.before32.json recon.json`: `tenants.sqlalchemy.seconds` 5.4 → 5.3, `pass.engine_hot_lanes` 1; one number the wrong way, `quickstart.express.eat_again_seconds` 1.2 → 1.6 — the eat, which no line of this change touches, timed by hand right after: 1.22 · 1.20 · 1.23 s (load 1.7). `MEASURE DIFF` exits 1 on it; closed on the engine lines by the standing ruling (§59) |

## 69 · A STORE READS ITS WHOLE-CORPUS SCANS ONCE — the atlas's six pictures share two scans instead of twelve, 1.10 → 0.95 s, the same files (2026-09-07 · graphyos issue 33)

**What it was.** `draw.units` · `pillars` · `arm` each iterated `store.owned(corpus)` and
`store.edges()` — a `SELECT … ORDER BY` per call over sqlite, the rows re-materialized per
picture. On sqlalchemy the two scans cost 17 + 26 ms and the atlas's six pictures paid them six
times: 258 ms of a 332 ms picture build, for 74 ms of picture logic; the atlas's profile read
`federated_store.edges` 149,694 rows and `owned` 83,755.

**What it is.** `SQLiteStore` keeps the rows of `owned(owner)` per owner and of `edges()` the first
time each is asked for, and answers from them after: the store is opened read-only (`mode=ro`) at
one generation, so the rows cannot move under a caller. `owned` hands each caller its own copy of
a columns dict, so a caller that mutates one does not reach the next. Every reader (`arms`,
`pillars`, `draw`) sees the same rows in the same order; old code and new draw byte-identical
atlases on sqlalchemy (12 files) and fastapi (13). The cost is the rows kept: the atlas's peak RSS
100.6 → 118.5 MB on sqlalchemy (25k edge tuples and 12k node rows), under the rebuild's own peak
(the build, 244 MB), so the lane's number does not move. The test traces sqlite: `edges()` twice
and `owned()` twice per owner run three `SELECT`s, five on the parent's code.

```bash
# from engine/
for i in 1 2 3; do /usr/bin/time -f "atlas %e s · %M kB peak" ../.venv/bin/graphy draw --tenant tenants/sqlalchemy/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --atlas /tmp/atlas --partition tenants/sqlalchemy/partition.json 2>&1 | grep '^atlas'; done
git stash push graphy/federated_store.py && ../.venv/bin/graphy draw … --atlas /tmp/atlas_old … && git stash pop && ../.venv/bin/graphy draw … --atlas /tmp/atlas_new … && diff -rq /tmp/atlas_old /tmp/atlas_new    # empty, sqlalchemy and fastapi
python3 -m pytest -q tests/test_federated_store.py -k scans_once
git show HEAD~1:engine/graphy/federated_store.py > graphy/federated_store.py && python3 -m pytest -q tests/test_federated_store.py -k scans_once    # RED: assert 5 == 3 (reverted after)
cd .. && python3 measure.py run && python3 measure.py diff recon.before33.json recon.json
```

| measure | before | after |
|---|---|---|
| building sqlalchemy's six pictures, in-process | 332 ms (258 of it the twelve scans) | the two scans once |
| `graphy draw --atlas` on sqlalchemy, three runs | 1.11 · 1.10 · 1.11 s (§68) | 0.95 · 0.96 · 0.96 s |
| the atlas's peak RSS | 100.6 MB | 118.5 MB (the rows kept) |
| the atlas since §65 | 1.86 s | 0.95 s |

| check | result |
|---|---|
| the floor | 493 passed · 3 skipped (492 + 1); the RED proof against the parent's code |
| the same answer | old code vs new on the same store: sqlalchemy's 12 atlas files and fastapi's 13 byte-identical; every tenant's `arms --verify` green in the receipt |
| the gate | `GRAPHY_STANDALONE_OK` |
| the receipt | `measure.py run` then `diff recon.before33.json recon.json`: **`MEASURE DIFF OK: 41 number(s) moved, none the wrong way past tolerance`** — the receipt 58.4 → 55.9 s, `tenants.sqlalchemy.rss_kb` 255,176 → 263,756 (+3 %, within tolerance: the rows kept), every other lane's RSS flat or down, `pass.engine_hot_lanes` 1 |

## 70 · 0.2.0 — THE STRANGER'S PATH, RUN AS A STRANGER — a fresh venv, the wheel, a repo graphy never saw, and a company repo with ten packages; eat settles the package before it installs anything (2026-09-07)

**Why a release.** 0.1.0 went to PyPI on the morning of the 7th; twenty-seven commits followed —
§48–§69, the whole optimization pass — and `pip install graphyos` handed none of it out. The README's
CI badge pointed at the private repo (`omnislash157/graphyos`), a broken image on the public page.
Both fixed here; the version is 0.2.0 in `pyproject.toml` and `graphy.__version__`, the changelog
derives it, and the `v0.2.0` tag on the public repo publishes by trusted publishing.

**The stranger's path, run as written.** A fresh venv, `pip install` of the 0.2.0 wheel with both
extras, `git clone pallets/click` — a repo no tenant or quickstart had touched — then the README's
two commands and nothing else:

```text
graphy eat .          PROVISION OK (a venv beside the repo, pip install click) · MINT OK: click 608 nodes / 3174 edges · RESOLVE OK 2136 labels → 536 edges · BUILD OK · CHECK OK · EAT OK  — 3.0 s
                      then the MCP block to paste, SEE IT (pillars · draw), ASK IT (blast · descend · walk), every line an absolute path
graphy showcase .     SHOWCASE OK: click · 3 arm(s) (CORE, TERMUI, COMPAT) · CHECK GREEN — 0.06 s; the page: .graphy/showcase/index.html (32 KB, self-contained: no script or stylesheet fetched)
git status --short    empty — .graphy/ carries a .gitignore of `*` and ignores itself
```

**A company repo.** A local clone of the operator's private application (never a tenant, nothing
of it travels): a pyproject, a requirements file, a package.json, ten importable top-level
packages. The first `graphy eat .` provisioned for 66 s (a venv and `pip install` of the whole
application; the box's disk, at 93 %, ran out under it) and then refused: `10 importable package(s)
under <repo> — auth, core, …; name one with --package`. The refusal is right; its place was wrong.
`_cmd_eat` now settles the package — the named one, the only one, or the refusal by name — before
`provision` runs: a test with two packages and no `--package` proves the provisioner is never
called and no `.graphy/` is made; on the parent's code the spy is reached first. Then, as the
refusal says, from the application's existing venv: `graphy eat . --package <its sdk package>
--site-packages <venv>/site-packages` → `MINT OK: <the package> 5349 nodes / 59966 edges`, a
165-shard ring (numpy 11,959 nodes, networkx 7,921, livekit 3,979 …), 15,456 files parsed, `EAT OK`
in 97.9 s; `graphy showcase .` in 1.26 s, `CHECK GREEN`, the page where it says; `git status`
clean; `.graphy/` 1.1 GB. The README's two-line block now carries the `--package` form and the
page's path, and the paragraph under it says what a big application's ring weighs.

```bash
# the stranger, from an empty directory
python3 -m venv venv && ./venv/bin/pip install 'graphyos[estate,typescript]==0.2.0' && git clone https://github.com/pallets/click.git && cd click
../venv/bin/graphy eat . && ../venv/bin/graphy showcase . && git status --short && ls .graphy/showcase
# the refusal before the install (from engine/)
python3 -m pytest -q tests/test_cli.py -k settles_the_package
git show HEAD~1:engine/graphy/cli.py > graphy/cli.py && python3 -m pytest -q tests/test_cli.py -k settles_the_package    # RED: the provisioner reached first (reverted after)
```

| check | result |
|---|---|
| the floor | 494 passed · 3 skipped (493 + 1); the RED proof against the parent's code |
| the gate | `GRAPHY_STANDALONE_OK` — `graphy resolves OK (0.2.0)` |
| the release | `bash release.sh` → `graphyos-0.2.0-py3-none-any.whl` · `.tar.gz`, twine check green, the changelog under `## 0.2.0`; the `v0.2.0` tag's run 34158170572: build success · publish success; PyPI answers 0.2.0; a fresh venv's `pip install graphyos==0.2.0` imports 0.2.0 and `graphy --help` runs; CI on the public commit (bcd9a98): gate success · floor (3.12) success · floor (3.10) success; the badge renders `passing` |

## 71 · THE RED TEAM — ten findings from a fresh agent told to hurt the product, ranked; the first fixed here: the showcase job holds no token and no checkout (2026-09-07 · graphyos issues 34–44)

**How it was run.** One agent with no knowledge of how the product was built, the map and the
README as its only brief, told to think as a security researcher, a skeptical senior engineer and
a hostile user: read the engine, run the floor, feed it garbage in a scratch directory, run the
first five minutes as a stranger, touch nothing in either repo. It ran 32 tools over eight minutes
and deleted what it made. Every finding below is on the board with its reproduction, one issue
each, in this order.

| # | severity | the finding | issue |
|---|---|---|---|
| 1 | high | `showcase-on-issue.yml` ran a stranger's repo in the job that held the workflow token (`actions/checkout` persists it in `.git/config`) and posted a page path grepped from a log that code could write — code execution on the runner with `issues: write`, for any GitHub account, twenty minutes a run | #34, this section |
| 2 | high | `eat` and `showcase <url>` run the repo's build (`pip install <repo>`); the README says "provisions its dependencies" | #35 |
| 3 | medium / high | the re-mint splice trusts a shard on disk: a planted edge survived `MINT OK · BUILD OK · CHECK OK` (reproduced) | #36 |
| 4 | medium | `.private_markers.sha256` is unsalted sha256 and public: two of seven markers recovered from a 21-word guess list | #44 |
| 5 | medium | a syntax error, a latin-1 file, 300 nested parentheses: no nodes, still "parsed 7 of 7" (reproduced) | #38 |
| 6 | medium | `check` fresh and `showcase` 0.0 s against uncommitted edits: the cursor is the HEAD alone (reproduced) | #39 |
| 7 | medium | a file named with backticks breaks out of the comment's fence (not reproduced) | #40 |
| 8 | low | `cartograph._build` runs a descriptor string with `shell=True`, dead code | #41 |
| 9 | low | Windows claimed by shims, `eat` cannot provision there | #42 |
| 10 | nit | the walk example seeds and targets one node; the MCP server says 0.1.0; `EAT REFUSED` after the banner; showcase clones into the cwd; "never a load" overreaches | #43 |

**What held.** Zero runtime dependencies; no model call anywhere in the engine; no hardcoded path
or username in any tracked file; the index refuses tampered bytes and never creates symlinks; the
MCP server survived every malformed request and stayed up; a shard edited without a re-eat reads
`STALE`; no `eval` · `exec` · `pickle`; every subprocess is argv but finding 8; the PR workflows use
`pull_request`, never `pull_request_target`; the release job holds `id-token: write` alone.

**The first fix: #34.** Two jobs. The showcase job carries `permissions: {}`, never checks this
repo out, installs `graphyos` from PyPI into a runner with nothing to steal, runs the stranger's
url into `$RUNNER_TEMP`, and reads the page from where the showcase writes it
(`<work>/<name>/.graphy/showcase/showcase.txt`, the name from the url) — never from a grepped log
line — then hands `comment.md` up as an artifact. The post job, `needs: showcase`, holds
`issues: write` and nothing else, downloads the artifact and posts it; a showcase that produced no
artifact posts nothing. The comment's fence is four backticks. `workflows.py` parses it; a floor
test pins the shape — no token and no checkout in the showcase job, the post job separate with the
one permission, no grep of the log — and reads RED against the old file on `GH_TOKEN`. What the
stranger's build can still do on the runner: burn its twenty minutes and read a runner that holds
nothing; #35's `--no-provision` takes even that away.

```bash
python3 workflows.py                                            # WORKFLOWS OK: 5 file(s)
cd engine && python3 -m pytest -q tests/test_workflows.py -k holds_no_token
git stash push ../.github/workflows/showcase-on-issue.yml && python3 -m pytest -q tests/test_workflows.py -k holds_no_token; git stash pop    # RED on the old file: 'GH_TOKEN' in the showcase job
# the live proof: an issue on the public repo naming a small public repo — the showcase job green with no token, the post job's comment on the issue
gh run list --repo omnislash157/graphyos --workflow showcase-on-issue.yml --limit 1
```

| check | result |
|---|---|
| the floor | 495 passed · 3 skipped (494 + 1); the RED proof against the old workflow |
| the gate | `GRAPHY_STANDALONE_OK` |
| the live run | issue #45 named `pallets/click`: run 34168519445 — `showcase` success (no token, no checkout, `permissions: {}`), `post` success; the comment on #45 carries click's page (the pillars, the units, the ring, the MCP block); CI green on the public commit 1447015 |

## 72 · EATING A STRANGER'S REPO RUNS ITS BUILD — the README says so, and `--no-provision` runs nothing of theirs (2026-09-07 · graphyos issue 35)

**The finding.** Red-team finding 2 (§71). `graphy eat <repo>` and `graphy showcase <url>` provision
by `pip install <repo>`, which runs the repo's build backend and every sdist dependency's; a
`package.json` repo gets `npm install --ignore-scripts`. The README said "provisions the repo's own
dependencies beside it" and showed `graphy showcase https://github.com/encode/httpx.git` — a newcomer
did not learn they had just executed that repo's build hooks on their machine.

**The change.** The README's install section says it in one bold sentence: eating a repo you do
not trust runs its build. `graphy eat . --no-provision` (and `showcase <url> --no-provision`, which
hands the flag to its eat) runs nothing of the repo's: no venv, no pip, no npm. The ring is read
from an empty directory (`<home>/no-ring/`), so the package is minted from its source alone and
every import it makes is left unresolved by name — the same path `--site-packages <empty>` always
took, now spelled as the intent. The line: `PROVISION SKIPPED: --no-provision; the ring is empty,
every import is unresolved`. `--no-provision` with `--site-packages` is a refusal (they contradict)
before anything lands. `graphy eat .` without the flag behaves exactly as before. The
showcase-on-issue workflow runs `--no-provision`: after §71 the stranger's build could still burn
twenty minutes on a runner that held nothing; now nothing of the stranger's runs at all.

**The floor.** `test_cli`: a repo with one package eaten under `--no-provision` — the provisioner is
a spy that throws and is never called, the line prints, `EAT OK` with the import named unresolved,
no `venv`, the `no-ring` directory empty, `ring.json` minting the root alone; the contradiction
refused with exit 2 and no `.graphy/` made. `test_showcase`: the argv the eat receives is pinned,
`--no-provision` present when asked and absent otherwise. `test_workflows`: the showcase job's run
line carries `--no-provision` — RED against the old workflow file.

```bash
cd engine && ../.venv/bin/python -m pytest -q tests/test_cli.py tests/test_showcase.py tests/test_workflows.py -k "no_provision or holds_no_token"
grep -n 'runs its build\|--no-provision' README.md | head -3
cd /tmp && rm -rf np && git clone -q https://github.com/pallets/click.git np && cd np && ~/graphy/.venv/bin/graphy eat . --no-provision | grep -E 'PROVISION SKIPPED|EAT OK' && ! [ -d .graphy/venv ]
git stash push .github/workflows/showcase-on-issue.yml && (cd engine && ../.venv/bin/python -m pytest -q tests/test_workflows.py -k holds_no_token); git stash pop    # RED on the old file: no --no-provision
python3 burden.py && bash standalone_check.sh | tail -1
python3 measure.py run && python3 measure.py diff recon.before35.json recon.json
```

| check | result |
|---|---|
| the live run | `pallets/click`, a fresh clone: `PROVISION SKIPPED` · `RING: 1 shard(s) · stdlib skipped 45 · unresolved _typeshed, typing_extensions` · `EAT OK: click + 0 ring shard(s) (17 of 17 files parsed, 0.2s)`; no `.graphy/venv` — against §70's 3.0 s with the venv and pip install |
| the floor | 497 passed · 3 skipped (495 + 2); the RED proof against the old workflow file |
| the gate | `GRAPHY_STANDALONE_OK`; `BURDEN OK` unchanged: runtime deps 0 · extras 3 · wheel 276,205 B (cap 400,000) |
| the receipt | two runs. Every engine line flat or better: `tenants.sqlalchemy.seconds` 5.3 → 5.0, its RSS 263,756 → 251,368 kB, every tenant rebuild OK, `pass.engine_hot_lanes` 1. The wrong way, both runs, only the lanes this change never touches: the quickstarts' clone + pip/npm install over the network (`quickstart.httpx.seconds` 4.6 → 5.6 then 5.4; express 7.0 → 8.8 then clean) and `floor.seconds` 7.5 → 8.9 on the second run under the operator's browser at 21 % CPU (7.6 s by hand, `-o addopts=""`). Closed on the engine lines by the standing ruling (§59) |

## 73 · THE SPLICE TRUSTED A SHARD ON DISK BYTE-FOR-BYTE — the payload must hash to its PROVENANCE before a splice (2026-09-07 · graphyos issue 36)

**The finding.** Red-team finding 3 (§71). The re-mint splice (`smash._reuse_from`) reused a shard's
records whenever the PROVENANCE's per-source-file sha256 and producer block matched — but that receipt
hashes the *sources*, never the records. One `imports` edge in `click_graph/edges.json` re-pointed to
`click://module/click.PLANTED`, then `graphy eat .` → `MINT OK … (parsed 0 of 17 files)` · `BUILD OK` ·
`CHECK OK`, the planted row in the store. A hostile repo commits `.graphy/substrate/<pkg>_graph/` with
matching source hashes (the workflow pins Python 3.12 and one graphy release, so the producer block is
predictable) and "no model decides an edge, never hand-edited" is false for anything eaten from it.

**The change.** Before a splice reuses a single record, the shard's `nodes.json` and `edges.json`
bytes must hash to `PROVENANCE.files` — the digests the mint wrote, the same check `index.verify_shard`
runs on a push. A mismatch is named on stderr and nothing of the shard is reused; the full mint runs
and overwrites it: `SPLICE REFUSED: <slug>_graph edges.json does not match its PROVENANCE (sha256 …
vs declared …) — the shard was edited after the mint; nothing of it is reused, minted fresh`. The
refusal is also carried in the new PROVENANCE under `sources.splice_refused`. The bytes are read once
for the hash and the JSON is decoded from them on the first file that matches, so an untouched shard
costs one sha256 per payload file more than before and parses nothing, as before.

**The floor.** `test_smash`: a shard with one planted `imports` edge, source hashes untouched — the
re-mint refuses by name, reuses 0 and parses 2, the shard carries no `PLANTED` byte and equals a full
mint byte-for-byte; a planted node, the same law; then the untouched shard splices as before — nothing
parsed, nothing on stderr, no `splice_refused`, the bytes the same. RED against the old `smash.py`
(the refusal line never printed). §53's splice tests unchanged and green.

```bash
cd engine && ../.venv/bin/python -m pytest -q tests/test_smash.py -k "planted or splice"
git stash push engine/graphy/smash.py && (cd engine && ../.venv/bin/python -m pytest -q tests/test_smash.py -k planted); git stash pop    # RED on the old splice
cd /tmp && rm -rf pl && git clone -q --depth 1 https://github.com/pallets/click.git pl && cd pl && ~/graphy/.venv/bin/graphy eat . --no-provision >/dev/null \
  && python3 -c "import json;p='.graphy/substrate/click_graph/edges.json';e=json.load(open(p));next(x for x in e if x['edge_type']=='imports')['dst']='click://module/click.PLANTED';json.dump(e,open(p,'w'))" \
  && ~/graphy/.venv/bin/graphy eat . --no-provision 2>&1 | grep -E 'SPLICE REFUSED|MINT OK|EAT OK' && ! grep -q PLANTED .graphy/substrate/click_graph/edges.json \
  && python3 -c "import sqlite3,glob;c=sqlite3.connect(glob.glob('.graphy/substrate/.mesh_store_*.sqlite')[0]);print('planted rows:',sum('PLANTED' in str(r) for t in ('nodes','edges') for r in c.execute(f'select * from {t}')))"
python3 burden.py && bash standalone_check.sh | tail -1
python3 measure.py run && python3 measure.py diff recon.before36.json recon.json
```

| check | result |
|---|---|
| the live run | `pallets/click`, a fresh clone eaten, one `imports` edge planted in `click_graph/edges.json`, eaten again: `SPLICE REFUSED: click_graph edges.json does not match its PROVENANCE (sha256 fdbb1043fce1… vs declared 89b7ddf70c29…) — … minted fresh` · `MINT OK: click 608 nodes / 3174 edges (parsed 17 of 17 files)` · `BUILD OK` · `CHECK OK` · `EAT OK … (17 of 17 files parsed, 1.0s)`; `PLANTED` in the shard 0, in the store's `nodes` and `edges` tables 0. Eaten a third time, untouched: `0 of 17 files parsed, 0.6s` — the splice as before |
| the floor | 498 passed · 3 skipped (497 + 1); the RED proof against the old `smash.py` |
| the gate | `GRAPHY_STANDALONE_OK`; `BURDEN OK` unchanged: runtime deps 0 · extras 3 · wheel 276,205 B (cap 400,000) |
| the receipt | two runs. The lines the change lives on are flat: `quickstart.httpx.eat_again_seconds` 0.4 → 0.4, `quickstart.express.eat_again_seconds` 1.2 → 1.2 (the splice over the previous shards, now with one sha256 per payload file), `eat_again_parsed` 0 on both; every tenant rebuild OK, `pass.engine_hot_lanes` 1 → 0; `tenants.hono.rss_kb` 119,744 → 115,320, `tenants.sqlalchemy.rss_kb` 259,120 → 253,392. The wrong way, only lanes the splice never runs in: `quickstart.express.eat_seconds` 3.8 → 5.9 (the first eat — no shard on disk, `npm install` over the network), `tenants.sqlalchemy.seconds` 5.0 → 6.0 on the second run (a wipe-and-mint, no splice; 4.7 s by hand right after), `floor.seconds` 8.9 → 10.7 (9.4 s by hand, `-o addopts=""`; one new test that mints six times). Closed on the engine lines by the standing ruling (§59) |

## 74 · A SYNTAX ERROR, A LATIN-1 FILE OR DEEP NESTING MINTED NOTHING AND COUNTED AS PARSED — the unreadable files are named in the mint line and the receipt (2026-09-07 · graphyos issue 38)

**The finding.** Red-team finding 5 (§71). `python_ast._emit_raw_records_for_file` returned no record on
`UnicodeDecodeError` or `SyntaxError`, and the mint counted the file as parsed: a package with `broken.py`
(a syntax error), `latin.py` (`# coding: latin-1`, one real `def`) and `deep.py` (300 nested parentheses)
read `MINT OK: badpkg 4 nodes / 2 edges (parsed 7 of 7 files)`, the three in PROVENANCE with `nodes: 0`.
A codebase with one latin-1 module lost it, and the walk said "names no node" with no hint. A file symlink
to `/etc/passwd` was read and parsed as a module of the corpus.

**The change.** The producer reads a file by its own encoding — the PEP 263 cookie or the BOM,
`tokenize.detect_encoding`, stdlib — so `latin.py` mints and a BOM-led file mints; what it still cannot
read is named with its reason: `syntax error line N` · `not utf-8` · `unknown encoding: X` · `too deeply
nested` · `null bytes` · `unreadable: <strerror>` · `symlink outside the corpus -> <target>`. The mint line
reads `MINT OK: badpkg 7 nodes / 3 edges (parsed 4 of 7 files; 3 unreadable: passwd.py symlink outside the
corpus -> /etc/passwd, broken.py syntax error line 1, deep.py too deeply nested)`; PROVENANCE carries
`unreadable: {file: reason}` beside `sources` (an unreadable file holds no span in the receipt and is asked
again on every mint, so the reason is always the mint's own — an older shard's empty span for it is not
trusted); `ring.json` carries it per shard; `EAT OK … (4 of 7 files parsed; 3 unreadable: …)`. A file
symlink whose target lies outside the corpus root is skipped by the walk and named, never read; a link
that stays inside is a module of the corpus, as before; a directory link is never descended, as before.
The bytes the mint hashes are the bytes the producer decodes — one read per file where there were two.
The TypeScript producer names a file it cannot read the same way (an `OSError`; tree-sitter never refuses).

**The floor.** `test_adapters`: nine files under one package — the walk names the escaped link and
lists the rest in order; the mint names five unreadable files with their reasons, parses five, and the
functions of `good.py` · `latin.py` · `bom.py` · `inside.py` are the nodes; `read_source` on its own;
a handed parse emits the same records as a read. `test_smash`: the mint line, PROVENANCE, `ring.json`,
the re-mint (`parsed 0 of 6 files; 3 unreadable: …`), an older shard's empty span not trusted, the
`EAT OK` line, the phrase past its cap. Both RED against the old engine.

```bash
cd engine && ../.venv/bin/python -m pytest -q tests/test_adapters.py -k unreadable tests/test_smash.py
git stash push -- engine/graphy && (cd engine && ../.venv/bin/python -m pytest -q tests/test_adapters.py -k unreadable tests/test_smash.py -k unreadable); git stash pop    # RED on the old producer
# the same answer: the three Python tenants minted by the old engine (a worktree at HEAD~) and the new, nodes.json · edges.json sha256 equal
cd engine && for pkg in "fastapi ../staging/corpora/fastapi" "sqlalchemy ../staging/corpora/sqlalchemy/venv/lib/python3.12/site-packages" "graphy ."; do set -- $pkg; ../.venv/bin/python -m graphy smash --package $1 --site-packages $2 --out /tmp/same/new/$1 --no-ring; done; sha256sum /tmp/same/*/*/*_graph/{nodes,edges}.json
# the live run: pylint's own test tree — files with deliberate syntax errors and bad coding cookies
cd /tmp && rm -rf pl && git clone -q --depth 1 https://github.com/pylint-dev/pylint.git pl && cd ~/graphy/engine \
  && ../.venv/bin/python -m graphy smash --package tests --site-packages /tmp/pl --corpus /tmp/pl/tests --out /tmp/plt --no-ring | grep MINT \
  && python3 -c "import json;d=json.load(open('/tmp/plt/tests_graph/PROVENANCE.json'));print(len(d['unreadable']),'unreadable;',d['sources']['parsed'],'parsed')"
cd .. && python3 burden.py && bash standalone_check.sh | tail -1
python3 measure.py run && python3 measure.py diff recon.before38.json recon.json
```

| check | result |
|---|---|
| the reproduction | the issue's package, plus a BOM-led file, a file symlink to `/etc/passwd` and a directory symlink to `/etc`: before, `parsed 7 of 7 files`; now `MINT OK: badpkg 7 nodes / 3 edges (parsed 4 of 7 files; 3 unreadable: passwd.py symlink outside the corpus -> /etc/passwd, broken.py syntax error line 1, deep.py too deeply nested)` — `latin.py` and `bom.py` mint, `passwd.py` is never read; the re-mint `parsed 0 of 7 files; 3 unreadable: …` |
| the live run | `pylint-dev/pylint` at `af3930e`, a fresh clone, its `tests/` tree minted as one corpus in 0.8 s: `MINT OK: tests 7762 nodes / 19273 edges (parsed 1276 of 1316 files; 40 unreadable: functional/c/consider/consider_using_dict_comprehension_py315.py syntax error line 7, … and 32 more)` — 37 syntax errors (the `_py315` cases this interpreter cannot parse, `syntax_error.py`, `tokenize_error.py`), `unknown encoding: IBO-8859-1` · `utf-9` · `lala` (the repo's own bad-cookie fixtures); `regrtest_data/no_stdout_encoding.py` (`coding:iso-8859-1`) mints its class and method. Minted again: `parsed 0 of 1316 files; 40 unreadable: …` — the same 40, named again |
| the same answer | fastapi 507 nodes / 3715 edges, sqlalchemy 11959 / 56604, graphy 965 / 10566 — `nodes.json` and `edges.json` sha256 equal between the old engine and the new on all three |
| the floor | 500 passed · 3 skipped (498 + 2); both RED against the old engine; the graphy tenant's `PRODUCE` arm re-rendered (`read_source` · `walk_files_naming_skips` · `_escapes` · `unreadable_phrase` · `Receipt.unreadable` in the walk), `ARMS OK` |
| the gate | `GRAPHY_STANDALONE_OK`; `BURDEN OK`: runtime deps 0 · extras 3 · wheel 278,572 B (cap 400,000) |
| the receipt | `measure.py run` then `diff recon.before38.json recon.json`: every tenant OK, `quickstart.httpx.eat_again_seconds` 0.4 → 0.4 and `quickstart.express.eat_again_seconds` 1.2 → 1.2 with `eat_again_parsed` 0 on both — the splice unchanged; `quickstart.httpx.eat_seconds` 4.3 → 4.0, `tenants.sqlalchemy.seconds` 6.0 → 5.6, `floor.seconds` 10.7 → 7.5, the receipt 58.4 → 55.6 s. The wrong way: `index.verify_seconds` 0.5 → 0.6 (a lane no line of this change runs in), `pass.engine_hot_lanes` 0 → 1 — the floor's hottest function is `container._write_parquet` where it was `posix.fsync`, the same three functions in a different order. Closed on the engine lines by the standing ruling (§59) |

## 75 · CHECK SAID FRESH AND SHOWCASE SAID 0.0 s AGAINST UNCOMMITTED EDITS — the working tree's dirt joins the cursor (2026-09-08 · graphyos issue 39)

**The finding.** Red-team finding 6 (§71). `_eat_run` set the tenant cursor to `git:<HEAD>` and the
showcase skipped the eat whenever `.graphy/tenant.json` stood; `check` never compared the cursor to
anything. Reproduced on a fresh `pallets/click` clone: a function appended to `src/click/core.py`
(uncommitted), then `graphy check` → `CHECK OK … store fresh`, `graphy showcase .` → `SHOWCASE OK … 0.0s`,
`graphy blast planted_fn` → "names no node". A newcomer iterating on the working tree saw a stale page over
a green audit; the `0.0s` was the only tell.

**The change.** `cartograph.repo_cursor` is the one writer of a git cursor: `git:<head>` when the tree is
clean — exactly yesterday's cursor — and `git:<head>+<16 hex>` when it is dirty, the digest over
`git status --porcelain -uall -z` (every untracked file spelled out) and the bytes of every file it names,
so a second edit to an already-modified file moves it; the tenant's own products (the data home, journal,
join keys, descriptor, the eat's `.graphy/`) are never dirt. `cartograph.cursor_drift` reads it back: a short
HEAD and a long one are the same HEAD; `sha256:` cursors never drift. `graphy eat` writes it and says
`EAT: the working tree is dirty (N file(s) past HEAD) — the cursor carries it` when it is; `graphy check`
grows a cursor lane — `CHECK RED: cursor lane: STALE — the working tree moved past the store: N file(s)
modified or untracked since the build — re-eat the repo (`graphy eat .`) …`, or `STALE — HEAD moved past
the store: built at <a>, HEAD is <b>`, COULD-NOT-TELL when git cannot read the HEAD; `showcase .` re-eats
when the descriptor's cursor drifted (`SHOWCASE: … — eating again`; the splice parses only what moved, §53).
The graphy tenant's `rebuild.sh` computes its cursor through the same function, so a store built from a
dirty engine tree carries the dirt and its `check` holds until the tree moves. A git cursor is read against
the tenant's declared root, so hono and express — whose corpora are pinned checkouts under `staging/corpora`,
not the root — now write `sha256:` content cursors as fastapi and sqlalchemy always did (the first receipt
read both RED: their cursor was the checkout's HEAD, the root's HEAD is this repo's). `ensure_fresh`
(stats.json against HEAD) is untouched.

**The floor.** `test_cartograph_freshness`: a clean tree's cursor byte-equal to `git:<head>`; one edit
grows 17 characters and counts 1; the same file edited again moves the digest with the status unchanged; an
untracked file counts, the excluded home does not; a subdirectory reads the same tree; short and long HEAD
agree; the revert restores the clean cursor; a commit names the HEAD; no repo → `(None, 0)`.
`test_showcase`: a current `.graphy` is reused, a dirty tree is eaten again and the log says why.
`test_cli`: eat · edit · `check` exit 1 with the line · eat again over the dirty tree · `CHECK OK` · commit ·
`STALE — HEAD moved`. All three RED against the old engine.

```bash
cd engine && ../.venv/bin/python -m pytest -q tests/test_cartograph_freshness.py tests/test_showcase.py tests/test_cli.py -k "dirty or working_tree"
git stash push -- engine/graphy && (cd engine && ../.venv/bin/python -m pytest -q tests/test_cartograph_freshness.py tests/test_showcase.py tests/test_cli.py -k "dirty or working_tree"); git stash pop    # RED on the old engine
# the live run: the issue's reproduction on a fresh clone
cd /tmp && rm -rf click && git clone -q --depth 1 https://github.com/pallets/click && cd click && G=~/graphy/.venv/bin/graphy \
  && $G eat . --no-provision | grep "EAT OK" && $G check --tenant .graphy/tenant.json --tenant-id click | tail -1 \
  && printf '\n\ndef planted_fn():\n    return 1\n' >> src/click/core.py \
  && $G check --tenant .graphy/tenant.json --tenant-id click; $G showcase . | grep -E "SHOWCASE|EAT OK" \
  && $G blast planted_fn --tenant .graphy/tenant.json --tenant-id click | head -1 && grep -o '"cursor": "[^"]*"' .graphy/tenant.json
cd ~/graphy && python3 burden.py && bash standalone_check.sh | tail -1
python3 measure.py run && python3 measure.py diff recon.before39.json recon.json
```

| check | result |
|---|---|
| the reproduction | `pallets/click` at `6aabf09`, eaten clean in 0.2 s, cursor `git:6aabf09`, `CHECK OK`; the function appended: `CHECK RED: cursor lane: STALE — the working tree moved past the store: 1 file(s) modified or untracked since the build — re-eat the repo (`graphy eat .`) …`; `graphy showcase .` → `SHOWCASE: the working tree moved past the store: 1 file(s) … — eating again` · `EAT: the working tree is dirty (1 file(s) past HEAD) — the cursor carries it` · `EAT OK … (1 of 17 files parsed, 3.0s)` · `SHOWCASE OK: click · 3 arm(s) … 3.0s`; `graphy blast planted_fn` → `BLAST seed=click://func/click.core.planted_fn … dependents=0`; `CHECK OK`; the cursor `git:6aabf09+77708a42cc70450d` |
| the same answer | a clean tree's cursor is `git:<short head>`, the string the old eat wrote; the graphy tenant's cursor is `git:<full head>` on a clean tree, as `rebuild.sh` wrote before |
| the floor | 503 passed · 3 skipped (500 + 3); all three RED against the old engine; the graphy tenant's six arm regions re-rendered for the new symbols (`repo_cursor` · `working_tree_dirt` · `cursor_drift` · `tenant_exclude`), `ARMS OK` |
| the gate | `GRAPHY_STANDALONE_OK`; `BURDEN OK`: runtime deps 0 · extras 3 · wheel 280,503 B (cap 400,000) · subprocess sites 26 over 6 programs — git was on the list |
| the receipt | the first run read hono · express RED — their git cursor was the checkout's HEAD read against the root (fixed above, the content cursor) — and graphy RED on `ARMS DRIFT` for the new symbols (re-rendered); the second: `MEASURE OK: floor 503 passed · gate OK 16.4s · tenants fastapi=OK sqlalchemy=OK hono=OK express=OK graphy=OK · quickstart httpx=OK express=OK · engine-hot lanes 1 · 56.2s`; `diff recon.before39.json recon.json`: `quickstart.httpx.eat_again_seconds` 0.4 → 0.4 and `quickstart.express.eat_again_seconds` 1.2 → 1.2 — the one `git status` the eat adds costs nothing the receipt can see; `quickstart.express.eat_seconds` 6.3 → 3.3. The wrong way: `floor.seconds` 7.5 → 9.1 with the three new tests at 0.2 s together (0.15 + 0.05 + 0.01 under `--durations`), and `quickstart.httpx.eat_seconds` 4.0 → 5.0 (the clone-and-install lane) — the load noise §49 names, both; `pass.engine_hot_lanes` 1 → 1 as §74 left it |

## 76 · A FILE NAMED WITH BACKTICKS COULD CLOSE THE SHOWCASE COMMENT'S FENCE — the text page is escaped and the workflow's fence is computed (2026-09-08 · graphyos issue 40)

**The finding.** Red-team finding 7 (§71), not reproduced on the eat path. `showcase-on-issue.yml` wrapped
`showcase.txt` in a fixed four-backtick fence and `compose` printed arm and module names verbatim into the
text: a line of three or more backticks at most three spaces in closes a Markdown fence, and whatever follows
lands as Markdown or HTML in a bot-authored comment. Module names are not slug-checked, so nothing in the lane
refused one. The live run found why the finding never reproduced end to end, and it is a different bug: a
module named `` ```.ts `` eats green and then the showcase dies with a `FanoutError` stack at the partition
check (`non-dotted prefix 'hostile.```'`), before `compose` runs, and under `--no-provision` the ring's
unresolved list is empty, so no import name reaches the page either — graphyos #46. The comment step, in that
case, posts the stack's tail inside the fence.

**The change.** Two layers, so neither has to be the last one. `showcase.fence_safe` writes the text page for
the fence: every line that could close one — up to three spaces, then three or more backticks — has that run
backslash-escaped (`` \`\`\` ``), visible in the fence, never a zero-width character; four spaces in is code
and stays; every other line is untouched. `compose` returns the text through it. The workflow's comment step
no longer fences with a fixed four: the body it posts (the page's first 60,000 bytes, or the refusal lines) is
written first, the longest backtick run inside it is measured (`grep -oE '`+' | awk`), and the fence is one
longer, four at least — so whatever the text carries, the fence closes exactly where the step closes it. The
html page is unchanged; it escapes for html, as before.

**The floor.** `test_showcase`: `fence_safe` on the closing shapes (bare, indented, with a name, five
backticks with trailing space), the non-closing ones (four spaces in, `x```` `, two backticks, tildes, plain,
empty) and a multi-line text; `compose` over arms named `` ``` `` and `` ````.ts `` with the origin `` ```` ``:
no line of the text matches the closing shape, the names are escaped rather than dropped, the html carries the
raw names and no backslash, and the page passes the draw check. The workflow's comment step is run as bash —
the script sliced from the parsed workflow — over a body carrying a five-backtick line (rc 0) and a refusal log
carrying a seven-backtick line (rc 2): the comment ends with a fence exactly one longer than the longest run,
the body verbatim between, and the refusal phrase only on the refusal. Both RED against the old showcase.py
and the old workflow (`git stash push -- engine/graphy .github`).

```bash
cd engine && ../.venv/bin/python -m pytest -q tests/test_showcase.py -k fence
git stash push -- engine/graphy .github && (cd engine && ../.venv/bin/python -m pytest -q tests/test_showcase.py -k fence); git stash pop    # RED on the old engine
cd .. && python3 workflows.py && bash standalone_check.sh | tail -1
# the step, by hand, over a page built to close a four-backtick fence
S=/tmp/graphy-fence; rm -rf $S && mkdir -p $S/showcase/x/.graphy/showcase && printf 'line\n`````\n  ```\\`\\`\\`\nend' > $S/showcase/x/.graphy/showcase/showcase.txt \
  && RUNNER_TEMP=$S NAME=x URL=https://example.invalid/x rc=0 bash -c "$(sed -n '/page="\$RUNNER_TEMP/,/} > "\$RUNNER_TEMP\/comment.md"/p' .github/workflows/showcase-on-issue.yml)" && cat $S/comment.md
python3 measure.py run && python3 measure.py diff recon.before40.json recon.json
```

| check | result |
|---|---|
| the step, by hand | a page with a five-backtick line and an escaped `` ```\`\`\` `` line: the comment fences with six backticks, the body verbatim between; a refusal log with `SHOWCASE REFUSED: x`: four backticks, `It refused, and this is what it said:` above it — the old step's fixed four would have opened a new block at the five |
| the same answer | a page with no backtick run longer than three fences with four backticks, byte-for-byte the old step's comment; a TypeScript repo eaten with `--no-provision` (three files, `import { f } from "```"`) showcased in 0.1 s → `SHOWCASE OK`, its comment fenced with four |
| the live finding | the module named `` ```.ts `` → `EAT OK … (3 of 3 files parsed)` then the `FanoutError` stack, exit 1, no `SHOWCASE` line — graphyos #46 |
| the floor | 505 passed · 3 skipped (503 + 2); both RED against the old showcase.py and the old workflow; the graphy tenant's six arm regions re-rendered for `fence_safe` (the first receipt read graphy RED on `ARMS DRIFT`), `ARMS OK` |
| the gate | `GRAPHY_STANDALONE_OK`; `WORKFLOWS OK: 5 file(s)` — the comment step parses as before; `BURDEN OK`: runtime deps 0 · extras 3 · wheel 280,886 B (cap 400,000) · subprocess sites 26 over 6 programs |
| the receipt | `MEASURE OK: floor 505 passed · gate OK 14.9s · tenants fastapi=OK sqlalchemy=OK hono=OK express=OK graphy=OK · quickstart httpx=OK express=OK · engine-hot lanes 1 · 57.0s`; `diff recon.before40.json recon.json`: `quickstart.httpx.eat_seconds` 5.0 → 4.9, `quickstart.express.eat_seconds` 3.3 → 3.7, the eat-again numbers flat — the change touches no lane the receipt times. The wrong way: `floor.seconds` 9.1 → 10.8 with the two new tests at 0.04 s together (`--durations`), and `index.verify_seconds` 0.5 → 0.6 — the load noise §49 names, both; `pass.engine_hot_lanes` 1 → 1 as §75 left it |

## 77 · CARTOGRAPH RAN A DESCRIPTOR STRING THROUGH A SHELL — the dead lane is deleted and the burden refuses any shell by name (2026-09-08 · graphyos issue 41)

**The finding.** Red-team finding 8 (§71). `cartograph._build` ran a tenant descriptor's build-lane command
string with `shell=True` from the tenant's root, and `burden.json` named it a `subprocess_delegates` entry so
the scan trusted it by name. Its only callers, `ensure_fresh` (stats.json against HEAD, rebuild on drift) and
`code_graph_publish_inplace` (the atomic swap through a sibling temp dir), had no caller in the package — the
rebuild-tables era's walk-time auto-rebuild, dead since the store became the reader (§4) — but a committed
`.graphy/tenant.json` made it a second code-execution path waiting for one caller.

**The change.** The lane is gone: `_build` · `ensure_fresh` · `code_graph_publish_inplace` · `_shell_quote_out`
· `_behind_commits` and the `_NT_STALE_REFUSE_COMMITS` cap, with `shlex` and `shutil`. `cartograph` keeps
`resolve_graph` · `repo_cursor` · `cursor_drift` · `working_tree_dirt` · `tenant_exclude` · `write_graph` and the
JSONL CLI. The descriptor's `build_lanes` field stays — it is the roster (`<slug>_graph:<kind>`), read by
`build` · `check` · `bridge` — but no engine code reads its command half again. `burden.py` grows a rule with no
list to grow: `shell=True` on any `subprocess` call (or a `shell=` keyword that is not the literal `False`), and
`os.system`, is named with its file and line — `a shell over a string (shell=True) — the engine runs argv only,
never shell=True`; `subprocess_delegates` is deleted from `burden.json` and the scan no longer reads it. If a
build lane is ever run again it runs as argv.

**The floor.** `test_cartograph_freshness`: the fifteen tests of the dead lane are gone with it; the removal
audit asserts `shell=True` absent from the source and the five names absent from the module (RED against the
old cartograph.py). `test_burden`: a synthetic `cartograph.py` with `shell=True`, `shell=flag` and `os.system`
under a name an older burden.json called a delegate — all three named with their line, `shell=False` passes,
and `burden.json` carries no `subprocess_delegates` (RED against the old burden.py, which trusted the
delegate). The new burden.py over the old cartograph.py names `graphy/cartograph.py:170`.

```bash
! rg -n 'shell=True' engine/graphy
python3 burden.py | tail -1 && bash standalone_check.sh | tail -1
cd engine && ../.venv/bin/python -m pytest -q tests/test_cartograph_freshness.py tests/test_burden.py
# the old code under the new floor and the new scan
mkdir -p /tmp/old/graphy && git show HEAD~1:engine/graphy/cartograph.py > /tmp/old/graphy/cartograph.py \
  && python3 -c "import burden, json; from pathlib import Path; print(burden.scan_subprocess(Path('/tmp/old/graphy'), json.loads(Path('burden.json').read_text())))"
python3 measure.py run && python3 measure.py diff recon.before41.json recon.json
```

| check | result |
|---|---|
| the done check | `rg -n 'shell=True' engine/graphy` prints nothing, exit 1; `BURDEN OK: runtime deps 0 · extras 3 · wheel 280,886 B (cap 400,000) · hosts 7 on the list of 6 · subprocess sites 24 over 6 program(s)` — two sites fewer, the delegate's and the `_behind_commits` `git rev-list`; `GRAPHY_STANDALONE_OK` |
| the old code under the new scan | `graphy/cartograph.py:170: a shell over a string (shell=True) — the engine runs argv only, never shell=True` |
| the floor | 491 passed · 3 skipped (505 − 15 + 1); the removal audit and the shell test both RED against the old engine; the graphy tenant's six arm regions re-rendered — SEAM's cartograph line loses the five names — `ARMS OK` |
| the gate | `GRAPHY_STANDALONE_OK`; `WORKFLOWS OK`; `CHANGELOG OK` |
| the receipt | `MEASURE OK: floor 491 passed · gate OK 16.5s · wheel 278,954 B · tenants fastapi=OK sqlalchemy=OK hono=OK express=OK graphy=OK · quickstart httpx=OK express=OK · engine-hot lanes 1 · 56.6s`; `diff recon.before41.json recon.json`: `floor.passed` 505 → 491 and `tenants.graphy.nodes` 2674 → 2653 · `edges` 6700 → 6626 read as regressions — the deleted lane and its tests counted down, by design; `floor.seconds` 10.8 → 8.1, `wheel.wheel_bytes` 280,886 → 278,954, `tenants.fastapi.seconds` 3.1 → 2.7. The wrong way: `quickstart.express.eat_seconds` 3.7 → 6.0 (the clone-and-`npm install` lane, no line of this change runs in it) — the load noise §49 names; `pass.engine_hot_lanes` 1 → 1 as §74 left it |

## 78 · WINDOWS WAS CLAIMED BY SHIMS BUT EAT COULD NOT PROVISION THERE — the README says Linux and macOS, and the venv's layout is resolved by sysconfig (2026-09-08 · graphyos issue 42)

**The finding.** Red-team finding 9 (§71). `provision.py` looked for the venv's interpreter at `bin/python`
and its site-packages by a glob over `lib/python*/site-packages`; a Windows venv is `Scripts\python.exe` and
`Lib\site-packages`, so a native `eat` died with `RuntimeError: the venv … has no site-packages`. `farm.py`
and `refresh.py` carried the same guess. `_portable_flock.py` makes every lock a silent no-op where `fcntl`
is absent; `.mcp.json`, the hooks and `shell install` are bash. The README said "Python 3.10+" with no OS line.

**The change.** The README says what is true: Linux and macOS, Windows through WSL — the hooks, `shell install`
and the MCP pointer are bash, and the store lock is a named no-op without `fcntl` (the flock shim's docstring
says the same). The easy gap is closed: `provision.venv_layout` is the one reader of a venv's layout — the
interpreter, the scripts dir and the site-packages resolved by `sysconfig.get_paths` under the platform's
scheme (`posix_prefix` · `nt`) with the venv as the base, never a glob. The version in the path is the venv's
own, from the `pyvenv.cfg` its creation wrote; when it is the running interpreter's, the live `py_version_short`
is used so an ABI-suffixed layout (`python3.13t`) resolves too. `provision` · `farm.provision_alone` ·
`refresh.provision` all read it; a missing site-packages is named with the path looked for and the scheme.
A native Windows `eat` now provisions; the lock there is still the named no-op.

**The floor.** `test_provision`: both layouts resolved (`bin/python` · `lib/python3.11/site-packages` under
`posix`, `Scripts\python.exe` · `Lib\site-packages` under `nt`), a venv with no cfg resolved to the running
interpreter's version, the box's own venv resolved to exactly where the live interpreter reads from
(`sysconfig.get_paths()['purelib']`), an eat on an nt-shaped venv provisioned and pip run through
`Scripts\python.exe`, a venv missing its site-packages refused with the path and the scheme named — RED
against the old provision.py, which raised `has no site-packages` on the nt venv.

```bash
grep -n 'Linux and macOS' README.md
cd engine && ../.venv/bin/python -m pytest -q tests/test_provision.py && cd ..
bash standalone_check.sh | tail -1
# the old code against an nt-shaped venv
git show HEAD~1:engine/graphy/provision.py > /tmp/old_provision.py   # then provision() over a Scripts/ · Lib/ venv → RuntimeError
S=/tmp/click && git clone -q --depth 1 https://github.com/pallets/click $S && cd $S && graphy eat . | grep -n 'PROVISION\|EAT OK'
python3 measure.py run && python3 measure.py diff recon.before42.json recon.json
```

| check | result |
|---|---|
| the done check | `README.md:55: Linux and macOS; on Windows, through WSL — …`; `tests/test_provision.py` 4 passed; `GRAPHY_STANDALONE_OK` |
| the old code on an nt venv | `OLD: the venv at …/.graphy/venv has no site-packages` · `NEW: …/.graphy/venv/Lib/site-packages` — the same fake runner, the same venv |
| the live eat | pallets/click: `PROVISION: …/.venv/bin/python3 -m venv …/click/.graphy/venv` · `PROVISION: …/click/.graphy/venv/bin/python -m pip install …` · `PROVISION OK: pip install click into …/.graphy/venv` · `EAT OK: click + 0 ring shard(s) … (17 of 17 files parsed, 2.8s)` — the posix layout through `sysconfig`, byte-identical to the glob's answer |
| the floor | 492 passed · 3 skipped (491 + 1); the graphy tenant's six arm regions re-rendered (the store stamp moved), `ARMS OK` |
| the gate | `GRAPHY_STANDALONE_OK`; `WORKFLOWS OK`; `CHANGELOG OK` |
| the receipt | `MEASURE OK: floor 492 passed · gate OK 26.4s · wheel 279,913 B · tenants fastapi=OK sqlalchemy=OK hono=OK express=OK graphy=OK · quickstart httpx=OK express=OK · engine-hot lanes 1 · 68.2s`; `diff recon.before42.json recon.json`: `wheel.wheel_bytes` 278,954 → 279,913 (+959 B, `venv_layout` and its docstring), `tenants.sqlalchemy.seconds` 5.3 → 5.0. The wrong way: `floor.seconds` 8.1 → 10.6, `gate.seconds` 16.5 → 26.4, `quickstart.httpx.eat_again_seconds` 0.4 → 0.7, `seconds` 56.6 → 68.2 — the full floor was running beside this receipt on the same box, the load noise §49 names; no line of this change runs in the gate or the eat-again lane; `pass.engine_hot_lanes` 1 → 1 as §74 left it |

## 79 · THE FIRST FIVE MINUTES — the walk example never finds itself, the MCP server says its own version, a refusal prints alone, showcase says where it clones, and "never a load" names the walk (2026-09-08 · graphyos issue 43)

**The finding.** Red-team finding 10 (§71): what a newcomer misreads in the first five minutes. The `ASK IT`
block `eat` prints ended with `walk --seed <pkg>://module/<pkg> --target <pkg>://module/<pkg>` whenever the
ring was empty — seed equals target, zero hops, it finds itself. `graphy mcp --help` listed five tools and the
README six; `mcp.py` carried `version 0.1.0` as a literal against the package's `0.2.0`. `EAT: repo …` went to
stdout before the package was settled, so a directory with no package printed the banner and then `EAT REFUSED`
on stderr — in a terminal the two interleave, and in a pipe the refusal came first and the banner last.
`showcase <url>` with no `--work` cloned into `./showcase/<name>` in the current directory and said nothing
until the `git clone` line. The README's "every walk is a query, never a load" reads as a promise about the
build to a stranger, and the build reads the shard JSON once.

**The change.** Each line fixed where it is. `cli._walk_target` is the example's target: the first ring
shard's root module, else the package's first submodule read from the shard's `nodes.json`, and the seed
itself only for a one-module package with an empty ring. The `mcp` help says six tools and names `draw`.
`mcp.SERVER_INFO` reads `graphy.__version__` — one copy of the version, never a second literal. In `eat`
the banner moves after the package is settled, so a refusal is the whole output, and every `EAT REFUSED`
flushes stdout before it writes stderr, so the streams cannot cross in a terminal. `showcase` with no
`--work` logs where the clone lands and how to move it before it clones, and names the reuse when the
clone already stands; the `--work` help says the same. The README sentence names the build as the one
read and the walk as what never reads a file again; its eval line says `draw` came after the run it measures.

**The floor.** `test_cli`: `_walk_target` over a ring (the ring first), no ring (the first submodule by
sort, `pkg.alpha` before `pkg.zeta`), a one-module package and a missing shard (the seed stands); an eat of
an empty directory in a subprocess — stderr starts with `EAT REFUSED` and no `EAT: repo` is printed on either
stream. `test_mcp`: `serverInfo` equals `{"name": "graphy", "version": graphy.__version__}` and is not
`0.1.0`. `test_showcase`: a url with no `--work` under a chdir'd tmp — the `SHOWCASE: no --work` line names
the directory and `--work <dir>` before the clone runs, the clone lands at `./showcase/thing`, and the
second run says `reusing the clone at …thing` and clones nothing. All four RED against the old engine.

```bash
cd engine && ../.venv/bin/python -c "from graphy import mcp, __version__; import inspect; assert '__version__' in inspect.getsource(mcp)" && cd ..
cd engine && ../.venv/bin/python -m pytest -q tests/test_cli.py tests/test_mcp.py tests/test_showcase.py && cd ..
bash standalone_check.sh | tail -1
# RED against the old engine
git stash push -q -- engine/graphy README.md && (cd engine && ../.venv/bin/python -m pytest -q tests/test_cli.py tests/test_mcp.py tests/test_showcase.py -k 'RED_walk_example or RED_eat_refusal_prints or RED_the_server_reports or RED_showcase_without_work'); git stash pop -q
# the live run
S=/tmp/live && mkdir -p $S && cd $S && git clone -q --depth 1 https://github.com/pallets/click click && graphy eat click | grep 'walk '   # then run the line it prints
mkdir -p $S/empty && script -qc "graphy eat $S/empty" /dev/null | head -3
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}' | graphy mcp --tenant $S/click/.graphy/tenant.json --tenant-id click 2>/dev/null | head -1
cd $S && graphy showcase https://github.com/pallets/click | grep '^SHOWCASE'
python3 measure.py run && python3 measure.py diff recon.before43.json recon.json
```

| check | result |
|---|---|
| the done check | the `__version__` assertion holds; `tests/test_cli.py tests/test_mcp.py tests/test_showcase.py` 50 passed; `GRAPHY_STANDALONE_OK` |
| RED against the old engine | the four new tests fail on the stashed `engine/graphy`: the target equals the seed, `EAT: repo` is printed on the refusal, `serverInfo.version == '0.1.0'`, no `SHOWCASE: no --work` line |
| the walk example | pallets/click, empty ring: `EAT OK: click + 0 ring shard(s) … (17 of 17 files parsed, 8.5s)`, the line printed is `walk … --seed click://module/click --target click://module/click._compat`; run as printed: `WALK PATH: … hops=2 visited=16 steps=click://module/click -> __future__://module/__future__ -> click://module/click._compat` |
| the refusal in a terminal | `graphy eat <empty dir>` under `script`: the first and only line is `EAT REFUSED: no importable package(s) under …; name one with --package` — no banner |
| the MCP server | `initialize` over the click tenant: `serverInfo {'name': 'graphy', 'version': '0.2.0'}`; `graphy mcp --help`: `six tools — hunt · descend · blast · walk · draw · explain — over one tenant's store` |
| showcase without `--work` | `SHOWCASE: no --work — the clone lands under …/showcase (the current directory); --work <dir> puts it elsewhere` before `SHOWCASE: git clone --depth 1 …/showcase/click`; `SHOWCASE OK: click · 3 arm(s) (CORE, TERMUI, COMPAT) · 0 ring shard(s) · CHECK GREEN · 3.9s` |
| the floor | 496 passed · 3 skipped (492 + 4); the graphy tenant's six arm regions verified, `ARMS OK` |
| the gate | `GRAPHY_STANDALONE_OK`; `WORKFLOWS OK`; `CHANGELOG OK` |
| the receipt | `MEASURE OK: floor 496 passed · gate OK 15.9s · wheel 280,344 B · tenants fastapi=OK sqlalchemy=OK hono=OK express=OK graphy=OK · quickstart httpx=OK express=OK · engine-hot lanes 1 · 54.9s`; `diff recon.before43.json recon.json`: `wheel.wheel_bytes` 279,913 → 280,344 (+431 B, `_walk_target` and the log lines), `tenants.hono.rss_kb` −4%, `quickstart.express.seconds` 6.6 → 4.5, `quickstart.httpx.eat_again_seconds` 0.7 → 0.4. The one wrong way: `quickstart.httpx.seconds` 4.6 → 6.0 with `eat_seconds` 4.1 → 4.7 — the first eat is a network pip install of httpx, the load noise §49 names; the eat lane's only new work is one read of the package shard's `nodes.json` for the example's target, and the eat-again lane that reads nothing from the network got faster; `pass.engine_hot_lanes` 1 → 1 as §74 left it. The first receipt read the graphy tenant RED: `ARMS DRIFT` on CLI, `_walk_target` joining `graphy.cli` — the six regions re-rendered (store e94407b1ec1b63a2), `ARMS OK`, and the second receipt reads every tenant OK |

## 80 · THE MARKER DIGESTS ARE KEYED — a wordlist reversed 5 of 7 plain hashes in 0.01 ms, none of the keyed ones; the key never travels and a box without it says SKIPPED (2026-09-08 · graphyos issue 44)

**The finding.** Red-team finding 4 (§71). `.private_markers.sha256` is tracked in the public repo, and
`scrub.py` hashed each private word as an unsalted sha256 of its lowercase alphanumerics. A company name is
a public fact: a guess list of 24 words built from the login name, its parts and the product names — the
public facts the red team started from — recovered 5 of the 7 markers from the tracked list in 0.011 ms.
The words the scrub exists to hide were one `sha256` away from the file that hides them.

**The change.** The digests are keyed: HMAC-SHA256 under `.private_key`, a 32-byte hex key `scrub.py --keygen`
writes once beside the script, gitignored like `.private_modules`, never tracked (`--keygen` refuses to
overwrite one that stands — a new key makes every digest stale). The tracked list holds the keyed digests,
which no wordlist reverses without the key; the same 24 guesses recover 0 of 7. `--hash <word>…` writes the
list under the key and refuses without one. A box without the key cannot run the sweep and says so, never a
hollow OK: `scrub.py` prints `SCRUB SKIPPED: no key at … — the keyed sweep over N file(s) needs the
operator's key; it runs on the operator's box, never here` and exits 0; `standalone_check.sh` prints
`prose scrub        SKIPPED (no .private_key beside scrub.py …)` instead of the two sweeps; `census.sh` prints
`CENSUS SKIPPED` and exits 0; `burden.py`'s summary says `scrub SKIPPED (no .private_key)`. CI has no key and
never needed one — the words are absent from the tree, which the sweep proves on the operator's box before
every push and every cut. `--key <path>` reads another path's key first, for a checkout that has none:
`sync_public.sh` scrubs the public checkout under this box's key by path and refuses to sync without it.
The keyed state is primed once per key and copied per token, and a token's digest is remembered across the
sweep — the two gate sweeps cost 0.84 s where the plain hash cost 0.54 s and the naive HMAC 2.24 s. §32's
cut instructions name the keyed sweep and the key that stays behind; the folder list names `.private_key`.

**The floor.** `tests/test_scrub.py` (new): a planted marker caught by file and line under the key, and a
clean file clean; the tracked digests reverse by no wordlist — a plain sha256 of the fixture's words is in no
line, a second key gives a different list, and the real list beside the repo holds no plain hash of the login
name, its parts or the product name; a copy of the script beside a list and no key says `SCRUB SKIPPED`,
exits 0 and prints no token, `--hash` refuses naming `--keygen`, and the same file under the key is
`SCRUB RED: 1 hit(s)` at its line; `--keygen` writes 64 hex at mode 0600 once and refuses the second time;
`--key <path>` scrubs a keyless checkout and an absent path says SKIPPED with the path. Three of five RED
against the old scrub. The first gate run caught the test file itself spelling a marker as a guess — the
guesses now derive from the login name, as the done check's do.

```bash
python3 scrub.py --tracked | tail -1                                          # SCRUB OK
python3 -c "import hashlib; lines = open('.private_markers.sha256').read().split(); import sys; sys.exit(0 if all(len(l) == 64 for l in lines) else 1)"
bash standalone_check.sh | tail -1
cd engine && ../.venv/bin/python -m pytest -q tests/test_scrub.py && cd ..
# RED against the old scrub
git stash push -q -- scrub.py .private_markers.sha256 && (cd engine && ../.venv/bin/python -m pytest -q tests/test_scrub.py); git stash pop -q
# the wordlist attack, old list vs new: the login name and its parts, the product names, the module list normalized
python3 - <<'P'
import hashlib, subprocess
from pathlib import Path
old = set(subprocess.run(["git","show","HEAD~1:.private_markers.sha256"],capture_output=True,text=True).stdout.split()); new = set(open(".private_markers.sha256").read().split())
home = Path.home().name; mods = Path(".private_modules").read_text().split()
guesses = sorted(set(["graphy","graphyos","omnislash", home, *home.split("-"), home.replace("-","")] + mods + [m.replace("_","") for m in mods]))
for name, lst in (("old", old), ("new", new)): print(name, "recovered", sum(hashlib.sha256(g.lower().encode()).hexdigest() in lst for g in guesses), "of", len(lst))
P
# the box with no key
mv .private_key .private_key.aside; python3 scrub.py --tracked | tail -1; bash census.sh | tail -1; python3 burden.py | tail -1; mv .private_key.aside .private_key
time (python3 scrub.py --tree engine >/dev/null; python3 scrub.py --tracked >/dev/null)
python3 measure.py run && python3 measure.py diff recon.before44.json recon.json
```

| check | result |
|---|---|
| the done check | `SCRUB OK: 207 file(s), no private token`; every line of the list is 64 hex; `unkeyed guesses match nothing`; `GRAPHY_STANDALONE_OK` |
| the wordlist attack | 24 guesses: the old list `recovered 5 of 7 in 0.011 ms`; the new list `recovered 0 of 7` |
| the same answer | `census.sh`: `flagged lines: 1910 across the tracked tree`, `CENSUS OK` — the same 1910 lines inside `staging/` as §32, 0 outside; the seven words regenerated from the tracked staging docs on this box, `--hash` under the new key |
| the box with no key | `SCRUB SKIPPED: no key at …/.private_key — the keyed sweep over 207 file(s) needs the operator's key; it runs on the operator's box, never here` (exit 0) · `CENSUS SKIPPED: no .private_key beside census.sh …` (exit 0) · `BURDEN OK: … scrub SKIPPED (no .private_key)` · the gate `prose scrub        SKIPPED (…)` |
| RED against the old scrub | `test_scrub.py` on the stashed `scrub.py` + list: the wordlist test, the SKIPPED test and the keygen test fail (the old script has no key, no `--keygen`, and its list is plain sha256) |
| the cost | the two gate sweeps: plain sha256 0.54 s · naive HMAC 2.24 s · primed and memoized 0.84 s; the receipt's gate 15.9 → 15.0 s |
| the floor | 501 passed · 3 skipped (496 + 5); the graphy tenant `ARMS OK` (the tests shard grew: 2663 → 2671 nodes, 6658 → 6677 edges) |
| the gate | `GRAPHY_STANDALONE_OK`; `BURDEN OK: … scrub OK` — no new dependency, host or program (`hmac` and `secrets` are stdlib); `WORKFLOWS OK`; `CHANGELOG OK` |
| the receipt | `MEASURE OK: floor 501 passed · gate OK 15.0s · wheel 280,344 B · tenants fastapi=OK sqlalchemy=OK hono=OK express=OK graphy=OK · quickstart httpx=OK express=OK · engine-hot lanes 1 · 53.2s`; `diff recon.before44.json recon.json`: the wheel byte-identical (no engine line moved), `quickstart.express.seconds` 4.5 → 3.8, `quickstart.httpx.seconds` 6.0 → 5.3; the one wrong way `wheel.seconds` 2.8 → 3.4, the wheel build, which no line of this change runs in; the first receipt read four wrong ways — the gate 15.9 → 19.1 s under the naive HMAC and the express quickstart's npm install — and the second, after the priming, reads none of them |

## 81 · A MODULE NAMED OUTSIDE THE DOTTED IDENTIFIER — a unit the walk found is a unit the partition carries, and the showcase ends on one line (2026-09-08 · graphyos issue 46)

**The finding.** Found on §76's live run. A TypeScript repo with a module named ```` ```.ts ```` — any name
that is not a dotted identifier: a backtick, a space — eats green (`EAT OK: hostile + 0 ring shard(s)`) and
`graphy showcase . --no-provision` dies with a stack, exit 1, no `SHOWCASE REFUSED` line. `pillars.to_partition`
writes the walk's unit names as the partition's prefixes, `fanout.load_partition` refused a prefix outside
`[A-Za-z0-9_~-]` with `group 'HOSTILE' carries a non-dotted prefix 'hostile.```'`, and the showcase verb caught
`ShowcaseError · TenantError · StoreError · OSError` — `FanoutError` was none of them. On the showcase-on-issue
workflow the comment would post the stack's tail as "what it said".

**The change.** A unit the walk found is a unit the partition can carry: the loader admits what a producer
minted — dotted segments, each non-empty, none carrying a control character — and refuses only what is no
dotted path at all (an empty segment `a..b` · `.a` · `a.`, a newline), naming the rule in the refusal. The
cut matches by exact prefix at segment boundaries as before, so ```` hostile.``` ```` claims ```` hostile.```.f ````
and nothing else. An arm's name is a section file and an html id, so `pillars._arm_name` folds everything
outside `[A-Za-z0-9_]` in the crown's last segment to `_` — a crown named ```` pkg.``` ```` names its arm `ARM`,
`pkg.my file` names `MY_FILE`. The showcase verb catches `FanoutError` and `PillarsError` as `draw` does:
`SHOWCASE REFUSED: <reason>` on one line, exit 2, never a stack.

**The floor.** `test_fanout`: a partition carrying ```` pkg.``` ````, `pkg.my file` and `pkg.a-b` loads and cuts by
exact prefix; the refusals now name an empty segment, a leading dot and a newline (the old case `pkg/a` is a
name a producer could mint and is admitted). `test_pillars`: the arm name from a non-dotted crown is `ARM`,
`MY_FILE`, `A_B2` under a taken name, and always `[A-Za-z0-9_]+`. `test_showcase`: a `FanoutError` and a
`PillarsError` under the showcase verb are one `SHOWCASE REFUSED:` line at exit 2; a proposal whose units
carry ```` hostile.``` ```` round-trips through `write_partition` → `load_partition`. Three RED against the old
engine (the loader refused, the arm was named ```` ``` ````, no round trip).

```bash
cd engine && ../.venv/bin/python -m pytest -q tests/test_showcase.py tests/test_fanout.py -k "non_dotted or nondotted" && cd ..
# the specimen from the issue: a module named ```.ts, eaten and showcased
S=/tmp/graphy-nondotted; rm -rf $S && mkdir -p $S/src && cd $S && git init -q && printf '{"name":"hostile","version":"0.0.1","main":"src/index.ts"}\n' > package.json && printf 'export function f() { return 1; }\n' > 'src/```.ts' && printf 'import { f } from "./```";\nexport const b = f();\n' > src/index.ts && printf 'import { b } from "./index";\nexport const c = b + 1;\n' > src/other.ts && git add -A && git -c user.email=x@y -c user.name=x commit -qm init && ~/graphy/.venv/bin/graphy showcase . --no-provision 2>&1 | tail -3 | grep -E '^SHOWCASE (OK|REFUSED)'; cd ~/graphy   # the OK line is followed by the page and the text paths, the REFUSED line is last
# RED against the old engine
git stash push -q -- engine/graphy && (cd engine && ../.venv/bin/python -m pytest -q tests/test_showcase.py tests/test_fanout.py tests/test_pillars.py -k "non_dotted or nondotted"); git stash pop -q
bash standalone_check.sh | tail -1
python3 measure.py run && python3 measure.py diff recon.before46.json recon.json
```

| check | result |
|---|---|
| the done check | the four named tests pass; the specimen: `EAT OK: hostile + 0 ring shard(s)` then `SHOWCASE: one pillar — corpus 'hostile' has no orchestrator at depth 2 …` then `SHOWCASE OK: hostile · 1 arm(s) (HOSTILE) · 0 ring shard(s) · CHECK GREEN · 0.1s`, exit 0 — the old engine died at `fanout.py:188` with the stack, exit 1; `GRAPHY_STANDALONE_OK` |
| the partition it wrote | `"HOSTILE": ["hostile", "hostile.```", "hostile.other"]`, `"rest": "EDGE"` — the same file the old loader refused, loaded and cut |
| RED against the old engine | the loader test (`carries a non-dotted prefix 'pkg.```'`), the arm-name test (`'```' == 'ARM'`), the round-trip test — three of four fail on the stashed `engine/graphy` |
| the floor | 505 passed · 3 skipped (501 + 4); the graphy tenant `ARMS OK` — the six regions re-stamped to store `e672f53fce0cc6d3` (the tests shard grew: 2671 → 2675 nodes, 6677 → 6692 edges), the inventories unchanged |
| the gate | `GRAPHY_STANDALONE_OK`; `BURDEN OK` — no new dependency, host or program; `WORKFLOWS OK`; `CHANGELOG OK` |
| the receipt | `MEASURE OK: floor 505 passed · gate OK 16.1s · wheel 280,722 B · tenants fastapi=OK sqlalchemy=OK hono=OK express=OK graphy=OK · quickstart httpx=OK express=OK · engine-hot lanes 1 · 57.9s`; `diff recon.before46.json recon.json`: the wheel +378 B (the comments and the two catches); three wall-clock wrong ways — `quickstart.httpx.seconds` 5.3 → 6.8 (the pip install), `tenants.fastapi.seconds` 2.6 → 3.2, `wheel.seconds` 3.4 → 5.2 (the wheel build) — none of the three runs the changed lines more than once per partition; the first receipt read the graphy tenant RED, and its rebuild run alone is `GRAPHY_TENANT_OK`, the second receipt `graphy=OK` |

## 82 · 0.2.1 — THE TEN RED-TEAM FIXES SHIPPED — the tag's run built and published, PyPI answers 0.2.1, a fresh venv installs it from PyPI (2026-09-08)

**The cut.** The board drained at §81: every red-team finding from §71 closed (graphyos #39–#46), thirteen
public commits past the `v0.2.0` tag, all green. The version bumped to 0.2.1 in `engine/pyproject.toml`,
`graphy.__version__` and the README's install line; the changelog regenerated under `## 0.2.1`; `bash release.sh`
built the wheel and the sdist and `twine check` passed both; the gate read `graphy resolves OK (0.2.1)`; a fresh
venv installed the built wheel, imported 0.2.1 and showcased §81's specimen. The private commit 28f362a synced as
graphyos c8932fd, the `v0.2.1` tag pushed on it, and `release.yml` published by trusted publishing — no token.

```bash
bash release.sh | tail -3                                   # RELEASE OK: graphyos 0.2.1 built and checked
bash standalone_check.sh | grep -E "resolves|STANDALONE"    # graphy resolves OK (0.2.1) · GRAPHY_STANDALONE_OK
gh run list --repo omnislash157/graphyos -L 4 --json name,headSha,conclusion
curl -s https://pypi.org/pypi/graphyos/json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"
python3 -m venv /tmp/v && /tmp/v/bin/pip install -q 'graphyos==0.2.1' && /tmp/v/bin/python -c "import graphy; print(graphy.__version__)" && /tmp/v/bin/graphy --help | head -1
```

| check | result |
|---|---|
| the release | `graphyos-0.2.1-py3-none-any.whl` · `graphyos-0.2.1.tar.gz`, twine check PASSED both; `CHANGELOG OK: 71 entries`; the gate `graphy resolves OK (0.2.1)`, `GRAPHY_STANDALONE_OK` |
| the tag's run | `v0.2.1` on graphyos c8932fd: release run 34220726510 — build success · publish success; CI run 34220725636 on the same sha success |
| PyPI | answers `0.2.1` within a minute of the publish; a fresh venv's `pip install --no-cache-dir graphyos==0.2.1` imports `0.2.1` and `graphy --help` runs |
| what shipped | §72 eat runs no build without `--provision` · §73 the splice hashes its payload · §74 the unparsed counted and named · §75 the dirty-tree cursor · §76 the comment fence · §77 the shell-free cartograph · §78 the venv layout by sysconfig, Linux and macOS · §79 the first five minutes · §80 the keyed markers · §81 the partition carries any name the walk found |

## 83 · THE GALLERY — ten showcases of repos people know, one index, one receipt, built inside the image so every Railway deploy is a fresh gallery on the current engine (2026-09-08 · graphyos issue 47)

**The finding.** The showcase page (§66, §71) existed one run at a time under a repo's `.graphy/showcase/`
and nowhere anyone could link to. The public repo read 0 stars and 1 fork two days in. Railway's first
deploy of the connected repo failed before anything was done: no Dockerfile, no requirements.txt, no
Procfile at the root and the package under `engine/` — its detector found nothing to build. Railway pulls
the connected repo and builds on its own builder, never GitHub Actions.

**The change.** `gallery.py` (+ `gallery.sh`, the venv wrapper) at the repo root: for every url in
`gallery.txt`, `graphy showcase <url> --no-provision --work <out>/.work --out <out>/<slug>/` — the clone
shallow, nothing of the stranger's repo executes — then `<out>/index.html`, every green page linked with its
arms (name and crown) and its ring read from its `showcase.txt`, the uvx line and the MCP block on top, and
`<out>/gallery.json`, the receipt: every url, the clone's commit, the `SHOWCASE` line it ended on, the page's
`check_artifact` verdict run a second time here. A page RED or REFUSED is named in the receipt and in a
`GALLERY LEFT OUT:` line and never in the index; the exit is 1 while anything is left out. The `Dockerfile`
at the root builds the gallery inside the image — the engine installed from the checkout (`pip install
/src/engine[typescript]`, what main does, not what PyPI last published), `gallery.sh` over `gallery.txt` at
image build, the directory served by `python3 -m http.server $PORT` (stdlib; Railway sets `PORT`, the
service's public port is 8080). `gallery/` is gitignored — a build product. The tenth url was this repo
itself, refused (`no importable package(s) under …` — the package is under `engine/`, and the showcase eats
a clone's root); swapped for encode/starlette, the self-showcase a later issue if it is wanted.

**The floor.** `tests/test_gallery.py` (new): `slug_of` admits github and gitlab urls and refuses ssh,
other hosts, an owner alone; `read_text_page` names the arms in order with crown and floor and the ring;
`compose_index` links only green pages, never a RED or a REFUSED one, is static html with no script;
`build` over a fake showcase writes the index and the receipt, links the good page, leaves the refused one
out and says so; the CLI refuses without two arguments and refuses a bad url before the first clone.

```bash
bash gallery.sh /tmp/graphy-gallery $(cat gallery.txt) | tail -1                    # GALLERY OK: 10 page(s) of 10
python3 -c "import json; r=json.load(open('/tmp/graphy-gallery/gallery.json')); assert all(p['check']==[] for p in r['pages']); print(len(r['pages']), 'pages checked green')"
(cd /tmp/graphy-gallery && timeout 3 python3 -m http.server 8765 >/dev/null 2>&1 &); sleep 1; curl -s localhost:8765/ | grep -c 'href="'
sg docker -c "docker build -t graphy-gallery ." && sg docker -c "docker run -d --rm -e PORT=8767 -p 8767:8767 --name graphy-gallery graphy-gallery" && sleep 2 && curl -s localhost:8765/ | grep -c 'href="'; sg docker -c "docker rm -f graphy-gallery"
cd engine && ../.venv/bin/python -m pytest -q tests/test_gallery.py && cd ..
bash standalone_check.sh | tail -1
```

| check | result |
|---|---|
| the done check | `GALLERY OK: 10 page(s) of 10 checked green -> /tmp/graphy-gallery/index.html · 0 left out · receipt /tmp/graphy-gallery/gallery.json · 26.6s`; `10 pages checked green`; the stdlib server over the directory answers the index with 12 `href=` (ten pages, the issues link, the source) and a page at 200; `GRAPHY_STANDALONE_OK` |
| the ten | httpx 3 arms (MODELS, CLIENT, EXCEPTIONS) · click 3 · fastapi 5 (ROUTING, DEPENDENCIES, OPENAPI, APPLICATIONS, COMPAT) · typer 4 · rich 14 · requests 4 · hono 6 · express 1 · zod 1 · starlette 2 — every page `CHECK GREEN`, 0.6–2.7 s each, the ring 0 on every one (`--no-provision`: nothing of theirs installs); the directory 884 KB without the clones |
| the image | `docker build -t graphy-gallery .` on this box (docker.io 29.1.3, installed today): the ten showcases run inside the build, `GALLERY OK: 10 page(s) of 10 … 12.1s`, the image 536 MB (python:3.12-slim + git + the engine + the pages); `docker run -e PORT=8767 -p 8767:8767` answers the index with 12 `href=` and `rich/index.html` at 200 — the `PORT` variable honored, which is what Railway sets (the service's public port is 8080, the Dockerfile's default) |
| the first url that refused | `omnislash157/graphyos`: `EAT REFUSED: no importable package(s) under …/.work/graphyos; name one with --package` — the package is under `engine/`; named in the receipt's `left_out` and the `GALLERY LEFT OUT:` line, the index without it, exit 1; swapped for encode/starlette |
| the floor | 510 passed · 3 skipped (505 + 5, `tests/test_gallery.py`); the first build test passed for the wrong reason (the fake read the wrong argument and the assertion allowed an empty green list) — tightened to assert the good page green, linked, and the refused one out |
| the gate | `GRAPHY_STANDALONE_OK`; `BURDEN OK` — no new dependency, host or program in the engine (the gallery is a root script over the `graphy` CLI and `git`; docker is Railway's builder, proven here, never a burden of the wheel); `CHANGELOG OK: 72 entries` |
| what waits on the operator | the Railway service connected to omnislash157/graphyos on main with the root directory `/` — it picks up the Dockerfile on its own; the custom domain graphy-os.com is already set on the service and pointed through Cloudflare on public port 8080; `gh repo edit omnislash157/graphyos --homepage https://graphy-os.com` once the first deploy answers (graphyos #48) |
| adoption (graphyos #51) | `python3 measure.py adoption` — the one off-box verb, never in `run` or the gate; the first reading, 2026-09-08 16:40 UTC: `ADOPTION: stars 0 · forks 1 · pypi day 219 · week 219 · month 219 · stranger showcases 0 · plugin installs absent`; stars · forks · watchers from `api.github.com/repos/omnislash157/graphyos`, the downloads from `pypistats.org/api/packages/graphyos/recent` (every download counted, mirrors and CI included — the first days are the mirror baseline, 0.2.1 published the same day), the showcases the issues naming one repo url opened by anyone but the owner (#45 is the operator's own, so 0), the plugin installs named absent because no source exists — neither the marketplace nor the MCP registry publishes a count; each reading in `adoption.json` (gitignored) with its source url and `fetched_at`; a source that does not answer is value null with the error named and exit 1, proven with a repo and a dist that do not exist (`stars absent · … · pypi absent`); `run --quick` re-run after — `recon.json` carries no `adoption` key, so `diff` over two runs never sees one; the floor +2 (`tests/test_measure.py`: the stranger filter — the owner in any case, a PR, two urls, all out; the CLI over a faked fetch — the line, the receipt's sources, the absent path's exit 1); 0.8 s |

## 84 · THE TOPICS — ten set by name, so the repo is found by anyone searching GitHub for mcp, code-graph, tree-sitter or claude-code; the homepage waits on the first Railway deploy (2026-09-08 · graphyos issue 48)

**The finding.** `gh repo view omnislash157/graphyos --json repositoryTopics,homepageUrl` read
`"repositoryTopics": null`, `"homepageUrl": ""` two days after the cut. A repo with no topics is in no
GitHub topic page and no topic search. Operator, 2026-09-08: "agreed on all of it".

**The change.** Metadata only, no file in the tree: `gh repo edit --add-topic` for what the code is —
`mcp` · `mcp-server` · `code-graph` · `static-analysis` · `tree-sitter` · `claude-code` · `python` ·
`typescript` · `dependency-graph` · `codebase-analysis`. The description kept. The homepage is
`https://graphy-os.com` once the gallery answers there (§83): at this writing the domain answers Railway's
`{"status":"error","code":404,"message":"Application not found"}` — the custom domain and the Cloudflare
proxy stand on the service, but no deployment is live behind it until the service is connected to the
repo and deploys the root `Dockerfile`. The homepage is set by hand after that, never guessed.

```bash
gh repo view omnislash157/graphyos --json repositoryTopics -q '[.repositoryTopics[].name] | sort | join(" ")'   # the ten, sorted
gh repo view omnislash157/graphyos --json homepageUrl,description -q '.homepageUrl, .description'
curl -s -o /dev/null -w '%{http_code}\n' https://graphy-os.com/                    # 200 once the deploy is live; 404 until then
curl -s https://graphy-os.com/ | grep -c 'href="'                                  # 12 when the gallery answers
```

| check | result |
|---|---|
| the done check | `claude-code code-graph codebase-analysis dependency-graph mcp mcp-server python static-analysis tree-sitter typescript` — the ten, sorted, exact |
| the description | unchanged: "Compile any codebase into a walkable substrate: …" |
| the homepage | `""` — held: graphy-os.com answers 404 `Application not found` (0 `href=`); the hold is `gh repo edit omnislash157/graphyos --homepage https://graphy-os.com` once the curl reads 200 and 12 |
| the gate | `GRAPHY_STANDALONE_OK`; `CHANGELOG OK: 73 entries` |

## 85 · THE PLUGIN — a Claude Code plugin manifest and an MCP registry server.json at the root, both running `graphy mcp --repo`; the repo door reads the tenant eat left and refuses an uneaten repo by name (2026-09-08 · graphyos issue 49)

**The finding.** `claude plugin --help` lists init · validate · install; graphy's server was reached by hand —
`.mcp.json` in this repo points at one tenant's `mcp.sh`, and a stranger writes their own pointer after
`graphy eat`. `ls engine/graphy/shell/claude-plugin` → nothing; no `server.json` anywhere. A static manifest
cannot know the eaten package's name, and `graphy mcp` refused without `--tenant-id`. Operator, 2026-09-08:
"get listed where MCP users look … agreed on all of it".

**The change.** `graphy mcp --repo <abs>` (`cli.repo_tenant`): the descriptor at `<repo>/.graphy/tenant.json`
and the root package from the ring receipt eat wrote beside it (`ring.json` `root`) — both declared by eat,
neither guessed; an uneaten repo, a descriptor without its ring, a ring without a root, and `--repo` mixed with
`--tenant` each refuse with the line that names it, exit 2. `cli.mcp_args` picks the form: `mcp --repo <repo>`
when the descriptor is eat's, the explicit pair otherwise — the block `eat` and `showcase` print now uses it.
`.claude-plugin/plugin.json` at the root (the checkout is the plugin) runs `graphy mcp --repo "${CLAUDE_PROJECT_DIR}"`;
`server.json` (schema 2025-12-11, `io.github.omnislash157/graphyos`, registryType pypi, runtimeHint uvx) names
the same argv; `graphyos = "graphy.cli:main"` joins `[project.scripts]` so `uvx graphyos` resolves. The version
is pyproject's: `release.sh --check` reads both manifests and refuses `VERSION DRIFT`. The README carries the
plugin paragraph and the registry's ownership proof (`<!-- mcp-name: … -->`). PyPI's 0.2.1 has neither the flag
nor the script — the release is graphyos #53; the marketplace listing and the registry submission are outside
accounts (the hold below).

```bash
claude plugin validate . 2>&1 | tail -1                                                          # the plugin root is the repo root
cd engine && ../.venv/bin/python -m graphy mcp --repo /tmp/np </dev/null 2>&1 | head -1           # an eaten repo: served, no id typed
cd engine && ../.venv/bin/python -m graphy mcp --repo /tmp; echo rc=$?                            # uneaten: refused by name, 2
cd /tmp/np && PATH="$HOME/graphy/.venv/bin:$PATH" claude -p --plugin-dir ~/graphy --allowedTools 'mcp__plugin_graphy_graphy__*' --model haiku 'Using only the graphy MCP tools, run blast on the symbol "Command" and reply with one line: the tool name you called and how many symbols it reported.'
bash release.sh --check | tail -1                                                                  # versions OK (…)
python3 burden.py | tail -1; bash standalone_check.sh | tail -1
```

| check | result |
|---|---|
| `claude plugin validate .` | `✔ Validation passed with warnings` — the one warning: `CLAUDE.md at the plugin root is not loaded as project context` (the router is the repo's, not the plugin's; `--strict` would refuse it) |
| the repo door, live | `graphy mcp: serving tenant 'click' generation 3fc4694d09fa052f on stdio (hunt, descend, blast, walk, draw, explain)` over `/tmp/np`; `--repo /tmp` → `MCP REFUSED: no tenant at /tmp/.graphy/tenant.json — run \`graphy eat /tmp\` first`, rc 2 |
| the plugin in Claude Code | `claude -p --plugin-dir ~/graphy` over `/tmp/np` answered `mcp__plugin_graphy_graphy__blast reported 3 symbols` in 7.7 s — the server's honest answer: `Command` names three nodes (`click.core.Command` · `click.decorators.command` · `click.core.Group.command`), a door never guesses |
| the versions | `versions OK (0.2.1 in pyproject.toml, .claude-plugin/plugin.json, server.json)` |
| the floor | 518 passed, 3 skipped in 8.3 s (+8: `repo_tenant` reads eat's layout, five refusals by name, the CLI's three refusals, the two manifests run the repo door at the package version) |
| the gate | `BURDEN OK … docs 34 tracked · scrub OK`; `GRAPHY_STANDALONE_OK` in 15.9 s |
| the hold | the marketplace listing and the registry submission are outside accounts; the registry entry resolves only after graphyos #53 ships 0.2.2 to PyPI |

## 86 · THE FIRST STEP — `uvx --from 'graphyos[typescript]' graphy showcase .` opens the README, proven from a scratch venv holding only uv; under it the picture: the graphy tenant's pillars as one standalone svg the rebuild draws and the gate re-renders byte for byte (2026-09-08 · graphyos issue 50)

**The finding.** The README's first step was a venv and a pip install; `uvx` runs a PyPI console script with
no venv the reader makes, and it was proven nowhere — `which uvx` → nothing on this box. The README carried
no picture: the showcase page was described in prose and never shown. Operator, 2026-09-08: "lower the first
step … agreed on all of it".

**The change.** The quickstart opens with the one line, run from a scratch venv that holds nothing but `uv`
(never the project's `.venv`), over the hostile TypeScript repo of §80 (`/tmp/graphy-nondotted`), against
PyPI's 0.2.1: `SHOWCASE OK`. Under it, the drawing: `graphy draw --emit svg` (`sugiyama.emit_svg_file`) — the
same `<svg>` the html page carries, with the namespace a file needs and the palette, both themes and the class
rules inlined in a `<style>`, no script, no external resource, so a README or an `<img>` shows the walk's own
drawing; `check_artifact` runs over it on the way out as it does over html. `docs/pillars.svg` is tracked:
`engine/tenants/graphy/rebuild.sh` writes it after the atlas, and `standalone_check.sh` re-renders it from the
graphy tenant's store in the gate's fresh venv and refuses a byte of drift — `pillars svg DRIFT` — the way
`graphy arms --verify` names a moved region; a box without the tenant (CI) says `pillars svg SKIPPED` by
name. `burden.json` names `www.w3.org`: the xmlns literal the scanner finds, a namespace the engine never
reaches — named rather than hidden from the regex. No GIF: a recorder is a new program; the svg is the
drawing the walk made. The rebuild's `arms --verify` also named six regions moved — `mcp_args` and
`repo_tenant` from §85 had never been re-rendered, and `emit_svg_file` joined — so the six were re-rendered
first (the router's law: drift named, never absorbed), and the svg moved with the store the same way
(`CLI (113→ ·→8)` became `CLI (114→ ·→9)`): the gate would have refused the stale picture.

```bash
U=/tmp/graphy-uv; rm -rf $U && python3 -m venv $U && $U/bin/pip install -q uv && cd /tmp/graphy-nondotted && time $U/bin/uvx --from 'graphyos[typescript]' graphy showcase . --no-provision 2>&1 | grep -E '^SHOWCASE OK'   # the repo: §80's done block builds it
cd /tmp/graphy-nondotted && rm -rf .graphy && time UV_CACHE_DIR=/tmp/graphy-uv-cache /tmp/graphy-uv/bin/uvx --from 'graphyos[typescript]' graphy showcase . --no-provision 2>&1 | grep -E '^SHOWCASE OK'   # cold uv cache
cd ~/graphy && bash engine/tenants/graphy/rebuild.sh | grep -E 'ARMS|DRAW OK|GRAPHY_TENANT_OK'; wc -c docs/pillars.svg; python3 -c "import xml.dom.minidom; xml.dom.minidom.parse('docs/pillars.svg'); print('XML OK')"
cd ~/graphy && bash standalone_check.sh | grep -E 'pillars svg|BURDEN|GRAPHY_STANDALONE_OK'
cd ~/graphy && sed -i 's/CLI (/CLX (/' docs/pillars.svg && bash standalone_check.sh | grep 'pillars svg'; git checkout docs/pillars.svg            # a hand inside the picture: DRIFT
cd engine && ../.venv/bin/python -m pytest -q -o addopts="" | tail -1
```

| check | result |
|---|---|
| the first step, from PyPI | `SHOWCASE OK: hostile · 1 arm(s) (HOSTILE) · 0 ring shard(s) · CHECK GREEN · 0.2s`, the page under `.graphy/showcase/`; 0.8 s wall with uv's cache warm, 0.5 s with `UV_CACHE_DIR` fresh — graphyos 0.2.1 and its `[typescript]` extra resolved and installed by uv inside that |
| the picture | `DRAW OK: 7 node(s) · 20 edge(s) · 3 under the weight floor -> …/docs/pillars.svg · CHECK GREEN` from the rebuild; 9,789 bytes, one `<svg xmlns=…>`, well-formed XML, no `<script`, both themes in its `<style>` |
| the rebuild | `ARMS OK: 6 arm(s) match the walk (store 8be38afd040c52bd)` after the six were re-rendered; `GRAPHY_TENANT_OK` in 2.3 s |
| the gate | `pillars svg OK`; a hand-edited svg → `pillars svg DRIFT — docs/pillars.svg is not what the store draws; run engine/tenants/graphy/rebuild.sh`, exit 3; `BURDEN OK … hosts 8 on the list of 7 · docs 34 tracked · scrub OK`; `GRAPHY_STANDALONE_OK` in 18.1 s |
| the floor | 519 passed, 3 skipped in 9.1 s (+1: the svg emit is one well-formed standalone document, no script, both themes, the CLI writes the same bytes twice) |
| the done block | all four lines green: `SHOWCASE OK`, `README.md:61` the uvx line, `docs/pillars.svg` one `<svg` and linked at `README.md:68`, `GRAPHY_STANDALONE_OK` |

## 87 · THE MEMORY LANE SHIPS WITH ITS TAPS — the installed router names lightning, bloodhound and reseed_graph with the installing interpreter's path; and Railway's builder pinned in the repo (2026-09-08 · graphyos issue 52)

**The finding.** The memory lane was in the wheel — `graphy/reseed.py`, `graphy/session_tail.py`,
`graphy/lightning/` with `bloodhound.py` and `reseed_graph.py`, 28 files in `graphyos-0.2.1` — and
`graphy shell install` wired PreCompact · SessionEnd · SessionStart to `graphy.reseed capture|inject`. But the
router the installed repo's cold agent reads first never said so: `grep -n "lightning\|bloodhound\|reseed"
engine/graphy/shell/claude/GRAPHY.md` → nothing. A dev who installed the hooks got the recovery files and no tap
to read them. Operator, 2026-09-08: "is our memory system and reseed compact and hooks a part of graphy — can we
say here's graphy and here is our house scaffold, devs can have complete recall of every session dead cold, and
lightning and bloodhound". Separately: graphy-os.com was bound to the Railway service and answered Railway's
404 `Application not found` — the deploy had failed with nothing in the dashboard's build settings, and the
repo carried nothing that named the builder.

**The change.** The shipped `GRAPHY.md` gains a MEMORY section: one paragraph saying what the two session
hooks do and where the files land (`.claude/recovery/reseed_tail.md`, `sessions/`), and the seven-tap table
this repo's CLAUDE.md carries, every tap rendered with `{{python}}` and a new `{{sessions}}`
(`<repo>/.claude/recovery/sessions`) so each door is declared to its archive, never guessed from the cwd.
`install.memory_taps` counts the rows from the rendered text (a row that runs `-m graphy.lightning` or
`-m graphy.reseed`), and `SHELL OK` prints the count. `shell/README.md` says the same; the README's shell row
names the lane. The march loop (`march.py`, `self-clear`, `rung-discipline`) stays this repo's house scaffold —
it needs a board. For Railway: `railway.json` at the root pins `builder: DOCKERFILE` and the start command, so
the dashboard's settings never decide the build; `.dockerignore` admits only what the Dockerfile copies (the
first local build sent `staging/` — 3.2 G — into the context and died on the tar); the router names both and
the Dockerfile and the gallery files it never listed.

```bash
cd ~/graphy/engine && ../.venv/bin/python -m pytest -q tests/test_shell.py -k memory
R=/tmp/graphy-nondotted && ~/graphy/.venv/bin/graphy shell install --repo $R | tail -1 && grep -c "lightning" $R/GRAPHY.md && grep -n "bloodhound" $R/GRAPHY.md | head -1
cd ~/graphy && bash standalone_check.sh | tail -1
cd ~/graphy && sg docker -c "docker build -t graphy-gallery ." 2>&1 | grep -E 'GALLERY OK|Successfully built'
cd engine && ../.venv/bin/python -m pytest -q -o addopts="" | tail -1
```

| check | result |
|---|---|
| the floor, `-k memory` | 2 passed: the rendered router names the four doors with the installing interpreter and `--path <repo>/.claude/recovery/sessions` on every lightning row, no `{{` survives, 7 taps counted; `graphy.lightning.bloodhound gate --with walk` taken verbatim from the installed router's own row answers over a `sessions/001.md` the test wrote, exit 0 |
| the done block's second line | `SHELL OK: hooks for tenant hostile under /tmp/graphy-nondotted run on …/.venv/bin/python3 · 7 memory tap(s) in GRAPHY.md`; `grep -c lightning` → 6; the bloodhound row at `GRAPHY.md:38` with the interpreter and the archive path filled |
| the gate | `GRAPHY_STANDALONE_OK` in 16.5 s; `WORKFLOWS OK`, `BURDEN OK`, `CHANGELOG OK` |
| the floor | 523 passed, 3 skipped in 8.4 s (+2) |
| the image | with `.dockerignore`: context 36.5 MB (was the whole tree, `staging/` included, and the tar died); `GALLERY OK: 10 page(s) of 10 checked green … 12.3s` inside the build, `Successfully built`, 401 MB, 26.3 s wall; `docker run -e PORT=8769` answers the index 200 with httpx and click linked. The Railway deploy itself is the operator’s dashboard to read: the repo now names the builder, and graphy-os.com answers Railway’s 404 until a deploy on this commit succeeds |
| the site, 2026-09-08 17:43 UTC | Railway's service had been connected to `omnislash157/graphyos-os`, a July repo whose root is five docs and `tenants/fastapi/descend.py` — exactly the "no deployable application" its log named; switched to `omnislash157/graphyos`, the custom domain freed from the deleted project and re-bound through Cloudflare, no build settings typed: `railway.json` chose the Dockerfile. `curl https://graphy-os.com/` → 200, `<title>graphy — the gallery`, `graphyos 0.2.2`, ten pages linked; `fastapi/index.html` 200 in 0.16 s, `zod/index.html` 200 in 0.05 s; headers `server: cloudflare`, `x-railway-edge: atl1`. The GitHub homepage set to https://graphy-os.com (§84's hold released). Re-derive: `curl -s https://graphy-os.com/ | grep -o "<title>[^<]*"` |

## 88 · 0.2.2 — THE PLUGIN'S ARGV RESOLVES FROM PYPI — `graphy mcp --repo` and the `graphyos` script ship, so the two manifests from §85 install against the index (2026-09-08 · graphyos issue 53)

**The finding.** §85 landed `graphy mcp --repo <eaten repo>` and the `graphyos` console script in the tree, and
the two static manifests at the root run that argv — `.claude-plugin/plugin.json` (`graphy mcp --repo
"${CLAUDE_PROJECT_DIR}"`) and `server.json` (`uvx graphyos mcp --repo <repo>`). PyPI answered 0.2.1, which has
neither: a stranger who installed the plugin against the index got `graphy mcp: error: unrecognized arguments:
--repo`, and `uvx graphyos` found no such executable. The registry submission held on #49 had an argv that
could not resolve.

**The change.** The release, nothing else: 0.2.2 in `engine/pyproject.toml`, `graphy.__version__`, the README's
install line, `.claude-plugin/plugin.json` and `server.json` (both checked against pyproject by `bash release.sh
--check` — VERSION DRIFT refuses); the changelog regenerated under `## 0.2.2`; `bash release.sh` built the wheel
and the sdist and `twine check` passed both; a fresh venv installed the built wheel, imported 0.2.2 and
`graphyos mcp --repo /tmp` refused by name (`MCP REFUSED: no tenant at /tmp/.graphy/tenant.json`) — the flag and
the script both there. The private commit synced to the public repo, the `v0.2.2` tag pushed on it, and
`release.yml` published by trusted publishing — no token. What ships past 0.2.1: §83 the gallery · §84 the topics ·
§85 the plugin and the registry entry · §86 the first step and the svg · §87 the memory lane's taps.

```bash
bash release.sh | tail -3                                   # RELEASE OK: graphyos 0.2.2 built and checked
bash standalone_check.sh | grep -E "resolves|versions|STANDALONE"   # graphy resolves OK (0.2.2) · versions OK · GRAPHY_STANDALONE_OK
gh run list --repo omnislash157/graphyos -L 4 --json name,headSha,conclusion
python3 -c "import urllib.request, json; print(json.load(urllib.request.urlopen('https://pypi.org/pypi/graphyos/json'))['info']['version'])"
rm -rf /tmp/graphyos-0.2.2 && python3 -m venv /tmp/graphyos-0.2.2 && /tmp/graphyos-0.2.2/bin/pip install -q graphyos==0.2.2 && /tmp/graphyos-0.2.2/bin/graphyos mcp --repo /tmp 2>&1 | tail -1
```

| check | result |
|---|---|
| the release | `graphyos-0.2.2-py3-none-any.whl` · `graphyos-0.2.2.tar.gz`, twine check PASSED both; `CHANGELOG OK: 77 entries`; the gate `graphy resolves OK (0.2.2)`, `versions OK (0.2.2 in pyproject.toml, .claude-plugin/plugin.json, server.json)`, `GRAPHY_STANDALONE_OK` in 17.7 s |
| the built wheel, a fresh venv | imports `0.2.2`; `graphyos mcp --repo /tmp` → `MCP REFUSED: no tenant at /tmp/.graphy/tenant.json — run \`graphy eat /tmp\` first` |
| the tag's run | `v0.2.2` on graphyos 2e64299 (private 7a6c8fa): release run 34255072298 — build success · publish success (trusted publishing, digital attestations); CI run 34255070530 on the same sha |
| PyPI | answers `0.2.2` within a minute of the publish (17:07 UTC); the done block: `release.sh --check` versions OK · PyPI 0.2.2 · a fresh venv's `pip install --no-cache-dir graphyos==0.2.2` then `graphyos mcp --repo /tmp` → `MCP REFUSED: no tenant at /tmp/.graphy/tenant.json` (grep -c → 1) — the script and the flag both resolve from the index |
| the hold | the registry submission (`mcp-publisher publish`) and the marketplace listing stay outside accounts — the argv now resolves; the operator's step |

## 89 · 0.2.3 — THE REGISTRY'S TWO REFUSALS — the mcp-name proof into the README the wheel ships, the description under the 100-character cap, both rules in `release.sh --check` (2026-09-08 · graphyos issue 54)

**The finding.** With 0.2.2 on PyPI (§88) the registry submission was walked to its door and refused twice.
The registry proves a PyPI package's ownership by finding `mcp-name: <server name>` in the package's README —
the one PyPI shows as the description. `engine/pyproject.toml` says `readme = "README.md"`, which is
`engine/README.md`; §85's marker sat only in the repo's root `README.md`, which no wheel carries:
`curl -s https://pypi.org/pypi/graphyos/0.2.2/json | python3 -c "import json,sys; print('mcp-name' in
json.load(sys.stdin)['info']['description'])"` → `False`. The floor's `test_cli.py` asserted the marker
against the root README — the file the registry never reads — so it passed while the wheel shipped without it.
And `mcp-publisher validate` in the public checkout answered `422 … expected length <= 100, location
body.description`: `server.json`'s description was 184 characters, a cap enforced server-side only. Railway's
piece of §87 closed the same hour: the service had been reading `omnislash157/graphyos-os`, a July repo.

**The change.** `engine/README.md` carries `<!-- mcp-name: io.github.omnislash157/graphyos -->` on its own
line; `server.json`'s description is 91 characters; the test reads the README pyproject names (a regex over
`readme = "…"`, never a guessed path) and asserts the marker with the boundary the registry requires, and the
cap. The door: `release.sh --check` gains two rules beside VERSION DRIFT — `MCP-NAME MISSING` when the README
pyproject names lacks the marker, `DESCRIPTION OVER CAP` when the description exceeds 100 — printed as
`registry OK (mcp-name in engine/README.md, description 91 chars)` and refused in the gate. The release: 0.2.3
(a PyPI description is immutable per version), the same mechanics as §88.

```bash
bash release.sh --check | tail -3                           # changelog OK · versions OK (0.2.3 …) · registry OK
sed -i '/mcp-name/d' engine/README.md && bash release.sh --check | tail -1; git checkout engine/README.md   # MCP-NAME MISSING
unzip -p dist/graphyos-0.2.3-py3-none-any.whl 'graphyos-0.2.3.dist-info/METADATA' | grep -n mcp-name
~/.local/bin/mcp-publisher validate                          # ✅ server.json is valid (v1.8.1, the registry's own schema and cap)
python3 -c "import urllib.request, json; d=json.load(urllib.request.urlopen('https://pypi.org/pypi/graphyos/json'))['info']; print(d['version'], 'mcp-name: io.github.omnislash157/graphyos' in d['description'])"
```

| check | result |
|---|---|
| the two rules, red | marker deleted from `engine/README.md` → `MCP-NAME MISSING: engine/README.md (the README the wheel ships) lacks …`, and the test fails `AssertionError: README.md`; description set to 101 chars → `DESCRIPTION OVER CAP: server.json description is 101 characters` |
| the two rules, green | `registry OK (mcp-name in engine/README.md, description 91 chars)`; the gate `graphy resolves OK (0.2.3)`, `BURDEN OK` (wheel 283,572 B), `GRAPHY_STANDALONE_OK` in 16.7 s |
| the wheel | `graphyos-0.2.3-py3-none-any.whl` METADATA line 291 is the marker; twine check PASSED both |
| the registry's validator | `mcp-publisher validate` (v1.8.1, installed at `~/.local/bin` from the release tarball, linux amd64) → `✅ server.json is valid`; before the cut, 422 on the description |
| the floor | 523 passed, 3 skipped in 9.2 s under `.venv` (unchanged: the manifest test gained two assertions, no new test); the system `python3` without the extras reads 508 passed, 14 skipped — every skip names duckdb, tree-sitter or the corpus venv by name |
| the tag's run | `v0.2.3` on graphyos abf4aaa (private 8df3b09): release run 34259552202 — build success · publish success by trusted publishing |
| PyPI | answers `0.2.3` within a minute of the publish (17:52 UTC) and its description carries `mcp-name: io.github.omnislash157/graphyos` → `0.2.3 True`; 0.2.2 read `False` fifteen seconds earlier |
| the registry | the operator ran `mcp-publisher login github` (the GitHub device flow) and `mcp-publisher publish` from `~/graphyos`, 2026-09-08 18:07 UTC: `io.github.omnislash157/graphyos` 0.2.3 listed, status active, isLatest true, one package — pypi `graphyos` 0.2.3, runtimeHint uvx. Re-derive: `curl -s 'https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.omnislash157/graphyos' \| python3 -c "import json,sys; s=json.load(sys.stdin)['servers'][0]; print(s['server']['version'], s['_meta']['io.modelcontextprotocol.registry/official']['status'])"` → `0.2.3 active`. §85's registry hold is released; the marketplace listing stays the operator's |

## 90 · THE GALLERY BUILDS ITS TEN PAGES SIDE BY SIDE — 11.3 s → 2.9 s on this box, 12.3 s → 2.6 s inside the image; the first issue of the optimization pass (2026-09-08 · graphyos issue 55)

**The number.** The gallery — the Railway image's one slow step and the site's whole rebuild on every push —
ran its ten showcases one after another. Two instruments on this box (8 cores): `/usr/bin/time` over
`gallery.sh` read `wall 11.29 s · rss 53284 kB · cpu user 5.12 sys 0.88`, and the receipt's `seconds` 11.3, the
sum of its ten pages, the slowest 2.3 (fastapi). The merged profile of the ten showcase processes
(`GRAPHY_PROFILE_DIR`, `pstats` over `showcase-*.prof`): of 14.8 s, **8.0 s in `select.poll`** — the parent
waiting on `git clone --depth 1`; the engine's hottest frame `tree_sitter.Parser.parse` at 0.6 s; one clone
alone 1.86 s. Ten network waits laid end to end on eight idle cores.

**The cause.** `gallery.build` was `[_run_showcase(…) for u in urls]`. Each showcase is its own subprocess with
its own clone under `.work/<name>` and its own `--out`; nothing is shared; the index is composed after the list.

**The change.** `build` runs the showcases through a `ThreadPoolExecutor` (stdlib) with `map` over the urls, so
the pages come back in url order and the index, the receipt's `pages` and `green` are the sequential build's byte
for byte; only the log lines interleave. `jobs_for(n)`: every core, never more than the urls, `GALLERY_JOBS`
overrides and a value that is not a positive integer is refused by name. Nothing in the engine moves; the
Dockerfile keeps its one line. The floor: the pool proven in-process (the runner replaced by a sleep per slug —
the slowest url first, three starts within 50 ms, the order kept, 0.12 s of floor), and `GALLERY_JOBS=1` makes
the same test fail on the wall — the red proof.

```bash
rm -rf /tmp/graphy-gallery-55 && /usr/bin/time -f 'wall %e s' bash gallery.sh /tmp/graphy-gallery-55 $(cat gallery.txt) 2>&1 | grep -E '^GALLERY OK|^wall'
python3 burden.py | tail -1
python3 measure.py diff recon.before55.json recon.json | tail -1
bash standalone_check.sh | tail -1
docker build -t graphy-gallery:55 . && docker run --rm graphy-gallery:55 python3 -c "import json; print(json.load(open('/site/gallery.json'))['seconds'])"
```

| check | result |
|---|---|
| before → after, this box | `wall 11.29 s` → `wall 2.92 s` (the receipt 11.3 → 2.9; the slowest page 2.5 s is the floor of the lane); rss 53 MB unchanged; cpu user 5.1 → 5.9 s |
| the same answer | the ten pages' `index.html` and `showcase.txt` against the sequential build: 0 of 20 differ once the out-directory path (the MCP block names it) and the per-page seconds are normalized; the receipt's pages identical but `seconds`; `green` identical and in url order |
| inside the image | `docker build` 17.3 s on this box (cached layers); `/site/gallery.json` says 2.6 s for 10 green pages (§87: 12.3 s); the container serves the index 200 |
| on Railway | the push of graphyos 825885e redeployed: `https://graphy-os.com/gallery.json` says built 18:27 UTC, 4.1 s for 10 green pages on 0.2.3 — the deploy before it (17:51 UTC, sequential) read 16.8 s on Railway's builder. Re-derive: `curl -s https://graphy-os.com/gallery.json \| python3 -c "import json,sys; r=json.load(sys.stdin); print(r['built_at'], r['seconds'])"` |
| the constraints | `BURDEN OK` with `burden.json` unchanged (`concurrent.futures` is stdlib); the same ten clones and nothing else fetched; `MEASURE DIFF OK: 7 number(s) moved, none the wrong way past tolerance` — the before re-pinned on the pre-change tree in the same hour (`git stash` · `measure.py run --quick --out recon.before55.json` · pop), since the first pin was a stale 16:41 receipt and the box reads 20% slower this hour on every hot frame |
| the review, `/code-review medium` | seven findings, every one fixed or refused by name. **Confirmed, the cause of a red CI run (34263086102):** the pool test asserted three starts within 50 ms, which holds only with three cores and no `GALLERY_JOBS` in the inherited environment — the runner has two; now the width is handed in (`build(…, jobs=3)`, `--jobs N` at the CLI, `GALLERY_JOBS` the other door, an explicit argument wins), the overlap is proven by a `threading.Barrier(3)` every fake waits at — a sequential build would break it — and the test passes under `GALLERY_JOBS=1 taskset -c 0,1`. The 40 ms stopwatch bound: gone with it. `os.cpu_count()` as the width inside a builder with a quota: the Dockerfile pins `--jobs 4` (the lane waits on clones, not cores) — 4.4 s on this box, 4.3 s inside the image. The receipt carries `jobs`, and `jobs == 1` runs the old list comprehension, no pool. `str.isdigit` admitting `'²'` (a traceback, not a refusal): `re.fullmatch('[0-9]+')`, proven at the CLI. The re-derive fence joined by ` · `: three lines. **Refused by name, filed:** the clone keyed on the bare repo name and reused without an origin check is `showcase._clone`, an engine change outside this issue's blast radius — graphyos #58 |
| the pre-review finding | two urls of one repo name (a/click and b/click) shared `.work/click` and the page directory — a silent overwrite in sequence, a race side by side; `build` now refuses the pair by name before any clone (`GALLERY REFUSED: two urls share the slug 'click': a/click and b/click`, exit 2), with a test that proves the runner never starts |
| the floor | 525 passed, 3 skipped (+2); the barrier test green on two cores under `GALLERY_JOBS=1` |
| the gate | `GRAPHY_STANDALONE_OK`, `BURDEN OK`, `WORKFLOWS OK` |

## 91 · THE MARKETPLACE — the repo is its own Claude Code marketplace; `claude plugin marketplace add omnislash157/graphyos` · `claude plugin install graphy@graphyos`, proven end to end from this box (2026-09-08 · graphyos issue 56)

**The finding.** The checkout was the plugin (§85) but no marketplace listed it: a stranger's only door was
`--plugin-dir` over a clone. Claude Code installs from a repo carrying `.claude-plugin/marketplace.json`.
Anthropic's own directory (`anthropics/claude-plugins-official`) takes third-party plugins only through its
submission form — the operator's step, not this issue.

**The change.** `.claude-plugin/marketplace.json` beside `plugin.json`: marketplace `graphyos`, one plugin
`graphy` whose source is `{"source": "github", "repo": "omnislash157/graphyos"}` — the checkout itself — with the
description, version, author, homepage, license and keywords the plugin manifest carries. `release.sh --check`'s
VERSION DRIFT now reads the marketplace entry and its metadata too (proven red at 0.0.0); the manifest test asserts
the entry; `claude plugin validate .` validates both manifests and passes clean. The README's plugin block is the
two lines a stranger types, and the checkout line for a box with no marketplace.

```bash
claude plugin validate . | tail -1                          # ✔ Validation passed
bash release.sh --check | tail -2                           # versions OK (… marketplace.json …) · registry OK
claude plugin marketplace add omnislash157/graphyos && claude plugin install graphy@graphyos && claude plugin list | grep -A3 graphy
cd /tmp/np && claude -p "Using the graphy plugin's MCP tools only, call blast on 'Context' …"   # the installed plugin's tool answers
```

| check | result |
|---|---|
| the manifests | `claude plugin validate .` → `✔ Validation passed` (the CLAUDE.md warning of §85 is gone: the root validates as a marketplace); `versions OK (0.2.3 in pyproject.toml, .claude-plugin/plugin.json, marketplace.json, server.json)`; red at 0.0.0: `VERSION DRIFT: … marketplace.json plugins[0] says 0.0.0; … metadata says 0.0.0` |
| the install, this box | `claude plugin marketplace add ~/graphy` (the path form, before the push) → `Successfully added marketplace: graphyos`; `claude plugin install graphy@graphyos` → `Successfully installed plugin: graphy@graphyos (scope: user)`, version 0.2.3, the source cloned from GitHub at graphyos 825885e into `~/.claude/plugins/cache/graphyos/graphy/0.2.3` |
| the command the plugin runs | `graphy` must be on PATH outside any venv: `pip install --user` is refused by PEP 668 on this box, so a dedicated venv (`~/.local/share/graphy-venv`, `graphyos[typescript]==0.2.3` from PyPI) with `~/.local/bin/graphy` linked — what pipx or `uv tool install graphyos` does; `graphy mcp --repo /tmp/np` serves tenant click |
| end to end | `cd /tmp/np && claude -p …` with no `--plugin-dir`: `Called mcp__plugin_graphy_graphy__blast on Context (resolved to click.core.Context)`, 3 turns, 14.8 s wall |
| the gate | `GRAPHY_STANDALONE_OK`, `BURDEN OK` (json, not a tracked doc) |
| the hold | the official directory: the submission form at clau.de/plugin-directory-submission on the operator's account |

## 92 · THE RESOLVER BINDS AN ANNOTATED PARAMETER — `ctx: Context` makes `ctx.invoke` an edge to `Context.invoke`; blast on click 1 → 6, 36 edges bound on click, 113 on SQLAlchemy, 42 on graphy itself; a parameter never falls through to module scope; the splice keys on the producer's code (2026-09-08 · graphyos issue 57)

**The number.** Over the eaten click checkout at `/tmp/np` (the repo §85 and §91 answered through the
plugin): `graphy blast click.core.Context.invoke --depth 3` → `dependents=1` — `Context.forward`'s
`self.invoke`. The source: five `ctx.invoke(` call sites. The issue's own count was wrong about their form —
one is `def invoke(self, ctx: Context)` (core.py:1406); two bind `ctx = get_current_context()` as a local; one is
an unannotated `new_func(ctx, …)`; one is a closure over an outer `ctx`. Only the first is a parameter the
function annotates, and only that form is a scope. The wider number, `rg -c 'ctx: Context\b|: Context[,)]'
src/click` → core.py 62 · types.py 29 · decorators.py 4: a class the whole package is written against, with every
`ctx.<method>(` on those parameters left as text.

**The law.** A text label becomes an edge only through the scope that binds it. A parameter's annotation is
that kind of binding: `def f(ctx: Context)` names `Context`, which resolves through the module's own definition
or its `imports` edge — the same two doors a call label walks — to exactly one class node; `ctx.invoke` inside
`f` is then `Context.invoke` by scope, the way `self.go` is the container's `go`. And a parameter is the
innermost scope: it never falls through to the module's definitions or imports it shadows — `def bare(json):
json.dumps()` is not the stdlib's `json`, whatever the module imported. `Optional[Context]`, `Context | None`,
a string, a `TypeVar`, a name that reaches no class node, a parameter the function does not annotate, or one the
body rebinds anywhere (an assignment, a loop or comprehension target, a nested def's own parameter, an
except/with alias): text, never a guess. The law in `CLAUDE.md` names the door.

**The change.** The producer says the annotation: `python_ast` emits `annotations: {param: text}` on every func
and method record — only a bare or dotted name (`_name_chain`), only for a parameter the body never rebinds
(`_rebound_names` walks the whole subtree) — and `args` is now every named parameter in signature order
(positional-only, positional, `*args`, keyword-only, `**kwargs`; it was positional only, and `graphy explain`
printed a truncated signature for every keyword-only function). The IR carries it: `Node.annotations`, a mapping
of strings whose keys must be in `args`. The resolver binds it: `_class_in_scope` walks the module's own
definition then `_qualify` (imports, re-exports) and answers only a node whose type is `class`; `_resolve_one`
takes a parameter head before the local rule — the annotation binds it or nothing does, `via: "annotation"` in
the sidecar, `unbound-attribute` when the class has no such member; a `decorates` label (the `src` side) never
enters the branch, since a decorator is evaluated in the enclosing scope where no parameter exists. The golden
`tests/fixtures/fastapi_graph` re-minted by its own PROVENANCE command; the fastapi, sqlalchemy and graphy
tenants rebuilt, the graphy tenant's arm regions re-rendered. TypeScript is untouched: its producer records
parameter patterns, not types; the seam is python's alone until a typed parameter is an edge there.

**The splice, found on the way.** The second mint refused its own output: `annotations name parameters that
args does not` — the IR's new check caught records the splice had reused from the *earlier* producer of the
same day, because `_reuse_from` keyed reuse on `adapter · graphy version · python version` and the tree's
version had not moved while the producer's code moved twice. A version string is not a producer's identity;
its source bytes are. The producer block now carries `source`, sha256 of the adapter module's own file (16 hex),
and a shard minted by other code never splices — proven in `test_smash`: the digest overwritten in PROVENANCE,
every file parses again and the shard's bytes equal a fresh mint.

```bash
cd /tmp/np && ~/graphy/.venv/bin/graphy eat . && ~/graphy/.venv/bin/graphy blast click.core.Context.invoke --tenant /tmp/np/.graphy/tenant.json --tenant-id click --depth 3 | head -1
python3 -c "import json; s=json.load(open('/tmp/np/.graphy/substrate/click_graph/wormhole_edges.json'))['summary']; print(s['via'])"
cd engine && GRAPHY_CORPUS_SITE_PACKAGES=$PWD/../staging/corpora/venv/lib/python3.12/site-packages ../.venv/bin/python -m pytest -q tests/test_smash.py -k parity
cd engine && bash tenants/sqlalchemy/rebuild.sh | grep -E 'RESOLVE OK: sqlalchemy|ARMS'
python3 measure.py diff recon.before57.json recon.json | tail -1
```

| check | result |
|---|---|
| click, before → after | `blast Context.invoke --depth 3`: `dependents=1` → `dependents=6 own=6` — hop1 `Command.invoke` (the annotated site), `Context.forward`, `Group.invoke`; hop2 `Command.main`; hop3 `Command.__call__`, `CliRunner.invoke`. `Context.fail` 4, `lookup_default` 5, `get_help` 1 where the door had nothing to say. The shard's RESOLVE: `annotation 36` beside import 159 · local 187 · self 160 · super 30 (37 before the rebinding rule; the one it dropped was a parameter the body reassigned) |
| the same answer | every one of the 36: a `calls` edge on the `dst` side whose source annotates the label's head with the target's class, checked over the sidecar against the node records — 0 exceptions; no edge exists that a scope did not bind |
| the class itself | `blast click.core.Context --depth 2` stays `dependents=0`: a binding is not an edge onto the class, and `annotates` is not one of the nine words — the issue's second done line asked for what the law does not give, refused by name |
| the seam test | `w: Widget` and keyword-only `k: Widget` bind through gamma's re-export (`resolver:annotation`); `u` (bare), `o: t.Optional[Widget]`, `s: 'Widget'` stay `unresolved`; `w.nothing` is `unbound-attribute` on the class; `@router.ping` on `def deco(router: Widget)` leaves no `decorates` edge while the call inside binds; `shadow` (a nested def's `w`), `loop` (`for w in xs`) and `bare(js)` over an imported `json` all stay text |
| the other tenants | sqlalchemy `annotation 113` of 11,222 resolved, `ARMS OK: 5 arm(s) match`; graphy `annotation 42` of 1,715, six regions re-rendered then `ARMS OK: 6 arm(s) match`; fastapi, the fixture placed alone: no annotation binds — every annotated class is starlette's or pydantic's and the fixture carries no ring |
| the golden | re-minted, `MINT OK: fastapi 507 nodes / 3715 edges`, PROVENANCE producer graphy 0.2.3 · source 4b10ecce7c83db60; 179 records carry 342 bindable annotations, 1,851 characters (the first cut stored every annotation's text: 1,611 keys, 101,053 characters, `nodes.json` 349 KB — now 245 KB against 213 KB before, the widened `args` the rest); the parity test against the corpus venv: 2 passed |
| the constraints | `BURDEN OK` (wheel 283,572 → 285,468 B, under the cap); `MEASURE DIFF OK: 6 number(s) moved, none the wrong way past tolerance` (the before pinned on the pre-change tree in the same hour; a first diff read the floor +18 % while a parity test and a second floor ran beside it — alone, 10.1 s against 9.0, inside tolerance); the floor 525 passed, 3 skipped; the gate `GRAPHY_STANDALONE_OK`, `pillars svg OK` |
| the review, `/code-review medium` | eight findings, every one fixed: a `decorates` label resolved in the parameter scope (confirmed on a synthetic ring — fixed by side); a nested def's parameter shadowing the annotated name (fixed by the rebinding rule); a loop, comprehension or assignment rebinding it (the same rule); an unannotated parameter still falling through to module scope — a name match the law forbids (fixed: a parameter never falls through); `args` and `annotations` disagreeing on the parameter list (`args` widened, the IR asserts the subset); 98 % of the stored annotation text unbindable (`_name_chain` keeps only a name); an unfilled template token committed to main in this table (this row fills it); the law and converge's docstring naming four doors while the engine emitted five (both name the annotation). Found on the way: the splice reusing another producer's records (above) |

## 93 · THE CLONE IS KEYED ON OWNER AND NAME AND CHECKED AGAINST ITS ORIGIN — `<work>/<owner>/<name>`, one parse the gallery's slug shares; a standing directory is reused only when its `remote.origin.url` is the url asked for; the ten gallery pages the same byte for byte (2026-09-08 · graphyos issue 58)

**The number.** The review of §90 named the cause behind the gallery's duplicate-slug refusal: `showcase._clone`
keyed the clone directory by the repo's bare name and reused any directory with a `.git` in it. On this box,
with `pallets/click` cloned at `<work>/click`, `graphy showcase https://github.com/some-fork/click.git --work
<work>` said `reusing the clone` and drew the fork's page from pallets' tree, the receipt attesting pallets' commit
under the fork's name. The gallery's pre-check (§90) covered one list; `graphy showcase <url> --work` by hand and
the showcase-on-issue workflow had nothing.

**The change.** `showcase.repo_of(url)` is the one parse — `(owner, name)` from an https, ssh or absolute-path
url: the name is the last segment, the owner every segment before it under the host (a GitLab group path stays
whole), `.git`, a trailing slash and userinfo folded, no owner/name tail refused by name, and a segment of `.`, `..`
or `.git` refused before it can walk out of `--work` — and `showcase.clone_dir(work, url)` is
`<work>/<owner>/<name>`. The owner is the parent directory, not a prefix on
the name: the eat's fallback for a `package.json` with no name is the directory's name, and `owner__name` renamed
zod's whole page (`COLINHACKS__ZOD` as the arm) before the key moved one level up. `gallery.slug_of` keeps its
github/gitlab gate and derives owner and name through `repo_of`; the receipt's `commit` reads the head at
`clone_dir`, the second copy of the key logic gone. On reuse `_clone` reads `git -C <dir> config --get
remote.origin.url` from the clone itself and compares it to the url asked for through the same parse (host,
owner, name: https and ssh, `.git` or not, a token in the url are one repo); a mismatch is `SHOWCASE REFUSED:
<dir> is a clone of <other>, not <url>` with userinfo stripped from both, never a page; a git that cannot open the
standing clone (dubious ownership) refuses with git's own reason. The showcase-on-issue workflow passes `--out`
and reads the page there — it no longer knows the clone's key at all, so the PyPI engine it installs and this
one both post the page (the review's first finding: the key had moved under a workflow that still installs the
release before it); the
gallery's duplicate-slug refusal stays, now guarding only the page directory — the clone race is impossible by
construction. `gallery.py` imports the key from `graphy.showcase`, falling back to this checkout's `engine/` when
no venv is on the path (the floor runs it under the bare interpreter).

**The issue's done line, refused by name.** It asked for the refusal with pallets' clone standing at
`<work>/pallets__click` and the fork asked — under the owner key that is two directories, so the fork simply
clones (and a fork that does not exist is `clone failed`). The origin check fires when a directory stands at the
*fork's* key holding another repo's clone: `git clone pallets/click <work>/some-fork/click` then the fork's url →
the refusal, which is the done proof below. The same url spelled `https://github.com/pallets/click` against a
clone made from `…/click.git` reuses.

```bash
cd engine && W=/tmp/graphy-58 && rm -rf $W && mkdir -p $W && git clone -q --depth 1 https://github.com/pallets/click.git $W/some-fork/click && ../.venv/bin/python -m graphy showcase https://github.com/some-fork/click.git --no-provision --work $W --out $W/page 2>&1 | tail -1
cd engine && python3 -m pytest -q -k "showcase or gallery" | tail -1
git stash && bash gallery.sh --jobs 4 /tmp/graphy-gallery-58-before $(cat gallery.txt) | tail -1 && git stash pop && bash gallery.sh --jobs 4 /tmp/graphy-gallery-58-after $(cat gallery.txt) | tail -1
cd engine && ../.venv/bin/python -m graphy blast showcase._clone --tenant tenants/graphy/tenant.json --tenant-id graphy --depth 2 | head -1
python3 measure.py diff recon.before58.json recon.json | tail -1
```

| check | result |
|---|---|
| the done proof | `SHOWCASE REFUSED: /tmp/graphy-58/some-fork/click is a clone of https://github.com/pallets/click.git, not https://github.com/some-fork/click.git`, exit 2; the same url reuses: `SHOWCASE: reusing the clone at /tmp/graphy-58/pallets/click` → `SHOWCASE OK: click · 1 arm(s) (CORE) · 0 ring shard(s) · CHECK GREEN · 0.6s` |
| blast radius, before the edit | `BLAST seed=graphy://func/graphy.showcase._clone … dependents=5 own=2 ring=3`: `showcase.showcase`, `cli._cmd_showcase`, three showcase tests; `gallery.slug_of` names no node — `gallery.py` is a root file outside the tenant, read by hand |
| the same answer | the ten pages built on the pre-change tree and on this one: 22 files, 0 differ once the clone path, the build time and the seconds are normalized; `gallery.json`'s ten `commit`s equal; the clone dirs `.work/click …` → `.work/pallets/click …` the one visible change |
| the floor | 528 passed, 3 skipped (+3: `repo_of`/`clone_dir` on urls, ssh, paths, sr.ht's `~owner`, a GitLab group path, a token url, and every `.`/`..`/`.git` shape refused; the origin refusal proven on a real `git init` + `git clone`, the spelling fold reusing; git refusing to read a standing clone named by its reason); the workflow's comment step re-run as bash against the `--out` page; `WORKFLOWS OK` |
| the tenant | graphy rebuilt, six arm regions re-rendered (the walk gained `repo_of` · `clone_dir` · `_parse` · `_same_repo` · `_shown`), `ARMS OK: 6 arm(s) match the walk` |
| the constraints | `BURDEN OK` (wheel 285,468 → 286,542 B); `CENSUS OK`; `MEASURE DIFF OK: 41 number(s) moved, none the wrong way past tolerance` (a first diff read quickstart httpx +21 % while the gallery built beside it — alone, inside tolerance; the clone is the network's); the gate `GRAPHY_STANDALONE_OK` |
| the review, `/code-review medium` | eight findings, every one fixed: the workflow's page path moved under the key while the job installs the PyPI release whose clone still lands at `<work>/<name>` — every issue showcase would have posted an empty refusal until a release shipped (fixed by `--out`: the workflow reads the page where it asked for it and carries no copy of the key); `.`, `..` and `.git` admitted as a segment, so `https://github.com/pallets/..` cloned into `--work` itself (refused by name); the origin fold narrower than the key, so a clone made over ssh was refused against its https spelling and a token url was echoed verbatim (one parse decides both, userinfo never shown); sr.ht's `~owner` refused (admitted); GitLab nested groups colliding on the last two segments (the owner is the whole group path); gallery's fallback catching only `ModuleNotFoundError`, so an installed engine older than the key died on a traceback (an `ImportError` with `graphy` already imported is `GALLERY REFUSED` naming the stale engine, proven by a stub module); the `--work` help text still saying `<name>`; git's exit on the origin read ignored, dubious ownership reported as `<no origin>` (git's reason, when its exit is neither 0 nor 1). A single-segment self-hosted remote (`https://git.example.com/click.git`) now refuses where it once cloned — accepted: a key needs an owner, and the refusal names the shape |

## 94 · THE HISTORY SHARD — the repo's own record minted as a substrate: 115 commits · 40 sessions · 95 sections · 54 issues · 37 receipts, 339 `touches` onto the code's module ids; a walk from a session lands in `graphy.showcase` in three hops (2026-09-08 · graphyos issue 59)

**The number.** The operator, verbatim: *"load these 2 words as bloodhound, co occurrence and follow the fan
out to tell me how the product changed over time … here's the exact sessions where it happens with the
timestamps, and the commits that ball smash into it. It's all part of the substrate graph … We need to turn
every single receipt file into a substrate that's walkable."* What the record held before this section, as
text in five places and as edges nowhere: 115 commits, 106 carrying a `Claude-Session` trailer, 130 naming a
RECON section or an issue; 40 captured sessions with a `captured_at`; 94 `## N ·` sections; 37 receipts named
for the issue they pin. The memory doors (`bloodhound`, `reseed_graph chain`) answered in 90 ms and stopped at
the session.

**The law, pointed at the repo itself.** A corpus with rules becomes AST. `adapters/history.py` is a producer
with its own vocabulary — node types `commit · session · section · issue · receipt`, edge types `authored ·
records · names · pins · touches · follows`, ids `history://<node_type>/<name>` — and `graphy history --repo
--out [--sessions] [--code <shard>]…` mints one shard in the smash shape (nodes.json · edges.json ·
PROVENANCE.json, the producer's source digest, every path portable). The graphy tenant's rebuild mints it as
`history_graph` beside `graphy_graph` and `tests_graph`; `init` declares the lane, the scheme index gets
`history`, and `converge · build · check · container · walk · explain · estate` read it with no new code and no
knowledge of the word. Nothing private travels: a session node is an id, a capture time, an exchange count and
a file name — never a body; the shard is a build product under `substrate/`; the receipt names no box.

**The join that is real and the one that is not.** The `Claude-Session` trailer on 106 commits names a claude.ai
session, and the whole record carries two distinct ones — it spans many local sessions and no session file
names it, so it is an attribute on the commit, never the join. The join is the window: a commit is authored by
the session whose capture window — after the previous capture, up to its own — holds the author time (one box,
one pane, captures in sequence). 109 of 115 commits land in a window; 6 land in none and get no edge: the five
made before the first capture (17:04 to 18:39 on 09-05, the archive begins 19:12) and the one made after the
last. The first cut had let the first window reach back to the beginning of time and authored those five onto
the first session — the review's first finding; a window has two ends. A session captured twice (a compact,
then the end) is one node with two windows. A `RECON §N` naming a section the file no longer carries is
dropped, not invented.

**The wormhole, from the shards' own files.** A commit's changed files become the code shards' own module ids
by the map the shards carry — every module node's `file`, matched on a `/` boundary — so `engine/graphy/cli.py`
is `graphy://module/graphy.cli` because `graphy_graph` says `graphy/cli.py` is; the rebuild hands the two code
shards in with `--code`, and a repo with none gets no touches and a receipt that says so (the first cut had
this repo's layout hardcoded into a pip-installed producer: click minted 0 touches under `HISTORY OK`). 339
`touches` edges; `converge` counts the seam: `history → graphy 212 edge(s) over 72 node(s)`, `history → tests
127 over 44`. Prose touches nothing; a path git would quote (`café.py`) still maps (`core.quotePath=false`).

**The door for inputs git never tracks.** The sessions archive and the receipts are gitignored, so the tenant's
cursor cannot see them move and `check` stays green over a stale history shard. `graphy history --out <shard>
--verify` recomputes the inputs digest (commit shas · session id@capture · section titles · receipts · the code
map) against the receipt's and exits 1 as `HISTORY STALE … re-mint` — proven on a fresh capture in the floor.

**Two doors read differently than the issue assumed, by design.** `blast` follows `calls · inherits · imports ·
decorates`, so a commit that touched a module is not its dependent — the estate answers `touches` directly, and
the issue's fourth done line was corrected mid-march to say so. The store resolves a bare symbol by its id's
tail, so `explain section/93` answers; `explain 59` refuses and lists `issue/59` and `section/59`, as two
matches must; a commit is named by its full sha until the timeline door (graphyos #60) prints the short form.

```bash
cd engine && ../.venv/bin/python -m graphy history --repo ~/graphy --sessions ~/graphy/.claude/recovery/sessions --code tenants/graphy/substrate/graphy_graph --code tenants/graphy/substrate/tests_graph --out /tmp/graphy-history/history_graph | tail -2
cd engine && bash tenants/graphy/rebuild.sh | grep -E '^HISTORY|^CHECK OK|^ARMS OK'
cd engine && ../.venv/bin/python -m graphy history --repo ~/graphy --out tenants/graphy/substrate/history_graph --verify
cd engine && ../.venv/bin/python -m graphy walk --tenant tenants/graphy/tenant.json --tenant-id graphy --seed history://session/f5f3ae96-cf01-42a9-a27f-4f021de79c96 --target graphy://module/graphy.showcase | head -1
cd engine && ../.venv/bin/python -m graphy estate --tenant tenants/graphy/tenant.json --tenant-id graphy --sql "select edge_type, count(*) from adj where src like 'history://%' group by 1 order by 1"
cd engine && ../.venv/bin/python -m graphy converge --tenant tenants/graphy/tenant.json --tenant-id graphy | grep -E 'history ->'
python3 measure.py diff recon.before59.json recon.json | tail -1
```

| check | result |
|---|---|
| the mint | `HISTORY OK: 115 commit(s) · 40 session(s) · 95 section(s) · 54 issue(s) · 37 receipt(s)`; `HISTORY: 109 commit(s) authored by a session's window, 6 in no window · 339 touches onto code module ids`; 0.09 s; the shard 339 nodes / 910 edges |
| the tenant | `BUILD OK: compiled 3065 nodes / 7778 edges` (2713 / 6818 before), `CONTAINER OK: 7 shard(s)`, `CHECK OK … container fresh for 7/7 shard(s)`, `ARMS OK: 6 arm(s) match the walk` after the regions that gained the adapter and the verb were re-rendered; `GRAPHY_TENANT_OK`; `--verify` → `HISTORY OK: … fresh` |
| the walk | `WALK PATH: seed=history://session/f5f3ae96-… target=graphy://module/graphy.showcase hops=3` — session → commit 7a6c8fa → `graphy://module/graphy` → `graphy.showcase`; `explain section/93` answers `section history.section.93 at RECON.md:4607` |
| the estate | `select count(*) from adj where edge_type='touches' and dst='graphy://module/graphy.showcase'` → 7, the seven commits that changed showcase.py, each a `history.commit.<sha7>` |
| blast radius, before the edit | `blast smash.mint --depth 2`: dependents 5 own (smash · cli · farm · refresh ×2), 20 tests; none touched — the producer is a sibling, the mint reuses smash's writers and `producer_source` learned one more name; `cli._cmd_smash`: 0 dependents |
| the floor | 535 passed, 3 skipped (+7: the joins on a synthetic three-commit repo with two sessions, one captured twice — one commit in a window, two in none; the receipt without sessions or code says so; the refusals; `module_id_of` on the shards' own files at a `/` boundary; `verify` fresh, stale on a new capture, fresh again; two shards naming one file refuse; the verb over this repo onto the tenant's two code shards, every `touches` dst owned) |
| the constraints | `BURDEN OK` (subprocess sites 25 → 26, git already on the program list; wheel 286,542 → 294,097 B); `CENSUS OK`; `MEASURE DIFF OK: 47 number(s) moved, none the wrong way past tolerance` (a first diff read the two quickstart clones +35 %/+100 % while the tenant rebuilt beside it — alone, inside tolerance); the gate `GRAPHY_STANDALONE_OK` |
| the review, `/code-review medium` | eight findings, every one fixed, and the two it dropped at its cap: the first window unbounded below, five pre-archive commits authored by guess (a window has two ends; the test that codified the guess fixed); this repo's layout hardcoded into the producer (the map is the code shards' own `file` attrs, handed in by `--code`); `check` blind to gitignored inputs (`--verify`, the digest door); `history://recon/<n>` under `node_type: section` breaking the id law (`history://section/<n>`); git quoting non-ASCII paths so a touch was dropped (`core.quotePath=false`, proven on `café.py`); an unquoted expansion in `rebuild.sh` (a bash array); absolute box paths in the receipt (`portable()` for every path, the mint command rebuilt from them, the floor asserts the receipt names no box); a mid-work finding recorded as RECON prose and not on the board (posted as a comment on graphyos #61); `producer_source` reused for `history`; dangling `touches` onto a deleted module — impossible by construction now that the map is the live shard's |

## 95 · THE TIMELINE DOOR — `graphy history <A> --with <B>`: two words as bloodhound co-occurrence, the fan-out walked into the story — sessions oldest first with timestamps, their commits, the RECON sections and issues, the receipt numbers that moved; `gallery` × `showcase` → 3 sessions · 45 commits · 13 sections · 17 issues · 4 receipts in 0.12 s cold (2026-09-08 · graphyos issue 60)

**The number.** The operator, verbatim: *"I say hey Claude, load these 2 words as bloodhound, co occurrence
and follow the fan out to tell me how the product changed over time. and then cold dead and like less than a
second, you spit out. The project started like this. We hit a setback and regress, and then blah blah blah,
here's the exact sessions where it happens with the timestamps, and the commits that ball smash into it."*
Before: `bloodhound "<A>" --with "<B>"` named the sessions in 90 ms and stopped there — no commit, no section,
no number.

**The door.** `timeline.py`: `hunt` is bloodhound's own trail, imported (`_matcher` · `trail_file`, the CLI
untouched) — the session files where the two terms sit within one window, each with its hottest cluster's
exchange and snippet; `story` is the walk over the compiled store's history shard (§94): the session node by
its file name or the id prefix the archive stamps on every capture, `authored` to its commits, each commit's
`records` to a RECON section and `names` to an issue, each issue's `pins` back to the receipt, and the
receipt's numbers against the receipt before it in measured time — the kept keys first (floor seconds ·
passed · wheel bytes · gate seconds · floor RSS), at most four, never a number that did not move; `render` is
the story, oldest first. Every line is a node's attrs; no model wrote one. The verb is the mint's (`history`
with a term is the timeline, without one the shard), the MCP server's seventh tool is `history` (term ·
partner · window · sessions), and the store is opened once — a query, never a load.

**What the record says, and the done block corrected by name.** The block at birth asked the operator's pair,
`bloodhound` × `fan out`, for three sessions and three RECON sections; the record holds two sessions that said
both words within ten tokens, on 09-05, whose four commits predate any `RECON §` in a message. The door says
so and the block was corrected mid-march: the pair that carries the product's arc is `gallery` × `showcase`
(three sessions, 09-07 and 09-08: the first twenty repos proposed, the gallery hosted, the site answering,
0.2.2 → 0.2.3 shipped, the pool, the marketplace, the resolver), the operator's pair asserted as answering
with what it has, under a second. A session bloodhound hits that the shard does not carry is named — `not in
the shard … re-mint` — never invented.

**The door built on the way — the receipt's noise.** Four receipts on one tree read red three times on
numbers no engine change moved: a quickstart's clone-and-install +89 % (the network), an eat-again 0.5 → 1.0 s
(+100 % of a coin), `pass.engine_hot_lanes` 0 → 1 (the threshold flip already on #61). Rolling the receipt
until green is not a gate, so the diff learned two rules (`measure.py`, proven in the floor): a time is a
regression only past the tolerance *and* past a floor in seconds (`--time-floor 0.5`: 0.5 → 1.0 is nothing,
9 → 11 is not), and a quickstart's `seconds` and `eat_seconds` — a clone, a pip or npm install — are tagged
`network`, shown and never judged — and because the eat's clock spans the mint too (the review's point),
`eat` now prints the provision's own seconds and the receipt carries `mint_seconds`, the eat less the
provision, which the diff judges (`BETTER`). The eat-again with no network is still judged. The receipt after
the review read `MEASURE DIFF OK` on its second run (the first: the threshold flip and fastapi 3.1 → 3.8 s
once); the flip stays #61's.

```bash
cd engine && /usr/bin/time -f 'wall %e s' ../.venv/bin/python -m graphy history gallery --with showcase --tenant tenants/graphy/tenant.json --tenant-id graphy --sessions ~/graphy/.claude/recovery/sessions
cd engine && ../.venv/bin/python -m graphy history bloodhound --with "fan out" --tenant tenants/graphy/tenant.json --tenant-id graphy --sessions ~/graphy/.claude/recovery/sessions | tail -1
cd engine && python3 -m pytest -q tests/test_timeline.py tests/test_mcp.py tests/test_measure.py | tail -1
python3 measure.py diff recon.before60.json recon.json | grep -E 'network|MEASURE'
```

| check | result |
|---|---|
| the story | `gallery` × `showcase`: `TIMELINE: 3 session(s) · 45 commit(s) · 13 section(s) · 17 issue(s) · 4 receipt(s) · 0.04 s`, `wall 0.12 s` cold; the first session (09-07 00:17) carries the thirty commits of the archive's first gap, the second (09-08 16:09) the gallery's birth (§81–§83, #46 · #47), the third (09-08 20:53) 0.2.2 → 0.2.3, the pool, the marketplace, the resolver (§87–§92); `recon.before55: floor.seconds 8.5 → 11.4 · gate.seconds 15.0 → 16.1 · floor.passed 501 → 523` and `recon.before57: floor.seconds 11.4 → 9.0` — the setback and the recovery, from the receipts |
| the operator's pair | `bloodhound` × `fan out`: `TIMELINE: 2 session(s) · 4 commit(s) · 0 section(s) · 0 issue(s) · 0 receipt(s)`, `wall 0.11 s` — the memory lane's birth on 09-05 (94b5095, 2be8f2e), before any commit named a section |
| blast radius, before the edit | `blast lightning.bloodhound.main --depth 1`: 1 test; `blast federated_store.open_for --depth 1`: 13 own · 27 tests — neither touched: the door imports bloodhound's trail and opens the store the way every door does |
| the floor | 544 passed, 3 skipped (+8: the hunt's window and exchange over a synthetic archive with a header-less note and a nested file that are never sessions; the story over a fake store — time order, the hottest of two captures speaking for one session, the numbers against the receipt before it, an unmatched session named; a store with no history shard refused by name; commits ordered by the instant, not the string; an undated receipt nobody's before; the refusals, one mode per call; cold under a second over this tenant; the MCP table; +1 on `measure.diff`: the floor, the network tag and `mint_seconds` judged) |
| the constraints | `BURDEN OK` (wheel 294,097 → 299,820 B); `CENSUS OK`; `MEASURE DIFF OK: 42 number(s) moved, none the wrong way past tolerance` (the sixth run on this tree; the four before the review above, one after it red on the flip); the gate `GRAPHY_STANDALONE_OK`; bloodhound's own output unchanged — its module untouched |
| the review, `/code-review medium` | eight findings, every one fixed: a session captured twice rendered twice with its fan-out doubled (one node, the hottest capture speaks — `bloodhound` alone: 5 files, 4 sessions); a store with no history shard answered `0 hold both` and a remedy that cannot mint, and the MCP tool over the fastapi tenant hunted this box's archive (refused by name: `this store carries no history shard — mint it …`; the header counts the hit files and the sessions in the shard apart); the hunt enumerated `rglob('*.md')` where the producer mints the top level behind a header gate (the door searches the producer's own files — `read_sessions` — so a hit is always a session the shard can carry); the verb switched modes on the bare term alone, so timeline flags without a term were refused in the mint's words and a stray term beside `--verify` never verified (one mode per call, refused by name when mixed); `eat_seconds` tagged network though the eat's clock spans the mint (`PROVISION OK … (N.Ns)` printed by eat, `mint_seconds` in the receipt, judged; the dead clause gone); commits ordered by the raw `%aI` string, wrong across offsets (the instant); an undated receipt sorting first as everyone's before (excluded); "six tools" in `graphy mcp --help`, the showcase page's MCP block and DOORS.md's prose (the count dropped — a number in an arm's prose) |

## 96 · THE OPTIMIZATION PASS READS 0 — the floor's "hottest engine frame" was the profiler's clock charging `_write_parquet` for duckdb's own threads (self 3.01 s over cumulative 1.76 s: impossible for a real frame); the wall clock says 94 parquet writes cost 182 ms of a 10 s floor; the floor 10.9 → 9.7 s by minting the engine once in the adapter tests (2026-09-08 · graphyos issue 61)

**The number.** The receipt after #58: `pass.engine_hot_lanes` 1, the floor, hottest frame
`container._write_parquet 3.75 s ENGINE`. Two receipts in one hour then read 1 and 0 on one tree (the
comment on #61): the number the pass ends on was a coin at its threshold — the before pinned for this issue
(`recon.before61.json`, the last receipt of #60) itself read 0, with `_write_parquet 3.04 s ENGINE` second
behind `select.poll` by 0.15 s.

**Two sources.** The receipt's frame, and a wall-clock log of every `_write_parquet` call in the floor (a
pytest plugin wrapping the function, each call's rows and milliseconds by test): **94 writes, 182 ms** in a
10.4 s floor — 47 `nodes` and 47 `adj`, none over 5 ms, the container tests 12–15 ms apiece. A single write
on a fresh connection: connect 7 ms, `read_json` 2–4 ms, `COPY … PARQUET` 1 ms. The two instruments disagreed
by 16×, and the profile itself said why: `_write_parquet` self time 3.01 s against cumulative time 1.76 s —
a frame's own time cannot exceed the time of everything under it. DuckDB runs `con.execute` on its own
thread pool and releases the GIL; cProfile's clock charges the calling frame for the wall time of work it
never saw. §57 had named the mechanism ("the profiler cannot see pybind11 — its time lands in the caller's
self time; a lane hot on such a frame is judged by the wall clock, never by the frame"); the receipt had
not learned it.

**The door.** The fact is narrower than "self over cumulative": a pybind11 call is invisible to cProfile,
so its wall time lands in the self time of the innermost *engine* frame that made it. Those frames are
enumerable: `measure.native_boundary()` walks the engine's own source and names every function that calls
`duckdb.connect`, a connection's `execute`/`sql` in a module that names duckdb (sqlite's `execute` is a
builtin the profiler sees), or a tree-sitter parser's `parse` (never `ast.parse`) — thirteen frames today,
`container._write_parquet · emit · emit_all · estate`, `traversal.store_walk · load_walk`,
`index_estate._load · emit_index · estate_index`, `cli._cmd_estate · _cmd_estate_index`, `gate._cited`,
`typescript_ast.mint_records`; the floor asserts the set and its refusals (`Spec.parse`, `compile_store`).
`summarize_profiles` shows such a frame as `NATIVE`, a frame whose self time exceeds its cumulative past
rounding as `ARTIFACT` (threads under the clock), and judges the lane — `stdlib_hot`, and `judged_on`
names the frame — on its hottest frame over the whole profile that is neither; a lane with no such frame
is `null` and `pass.unjudged`, never a verdict that ends the pass. The review's first cut of this rule
(self over cumulative alone, judged inside the top three) is what the review found: an all-artifact lane
judged on nothing, honest thread-pool frames hidden, `emit`'s inflated self time passing as honest. The
floor's judged frame is `posix.fsync` / `select.poll` — the stdlib's, the stores' durability and the
subprocess waits — so `engine_hot_lanes` reads **0** and stays there across runs.

**The floor, made cheaper on the way.** The three python_ast tests in `test_adapters.py` each minted the
whole engine package (72 files): 0.35 · 0.34 · 0.33 s apiece by `--durations` unprofiled, ~1 s apiece under
the profiler, which triples Python-heavy work. One module-scoped mint serves all three (0.34 s of setup
once, then 0.03 s a test): A/B on the wall clock, `pytest -q` three times each on one box in one
sitting — HEAD 12.15 · 12.20 · 12.57 s, this tree 9.76 · 11.31 · 9.90 s; the receipt's own floor read 9.7,
12.2 and 11.6 s on three runs of this tree against a before of 10.9 — the receipt's floor is a noisy
instrument at ±15 %, the A/B by hand is the one that resolves a two-second move. The floor's answer is
the same: 546 passed, 3 skipped.

**Found on the way, on the board.** In the profiled run `posix.fsync` reads 7.3 s of self time across
the floor — 99 `compile_store`s and their `_sync_then_replace`, each paying durability for a store a test
throws away: graphyos #62, with the re-derive and a done block.

```bash
cd engine && ../.venv/bin/python -m cProfile -o /tmp/tc.prof -m pytest -q -p no:cacheprovider tests/test_container.py && ../.venv/bin/python -c "import pstats; st=pstats.Stats('/tmp/tc.prof'); [print(k[2], 'self', round(v[2],2), 'cum', round(v[3],2)) for k,v in st.stats.items() if k[2]=='_write_parquet']"
cd engine && for i in 1 2; do /usr/bin/time -f 'floor wall %e s' ../.venv/bin/python -m pytest -q -p no:cacheprovider 2>&1 | grep wall; done
python3 measure.py run --out recon.json | tail -1 && python3 -c "import json; r=json.load(open('recon.json')); print(r['pass']['engine_hot_lanes'], r['floor']['seconds'], r['floor']['hot'])"
python3 measure.py diff recon.before61.json recon.json | tail -1
```

| check | result |
|---|---|
| the artifact, two sources | the profile: `_write_parquet ncalls 11 self 1.613 cum 0.541` over `test_container.py` alone, `62 self 3.01 cum 1.76` over the floor; the wall log: 94 writes, 182 ms, the largest 4.9 ms (12 rows) |
| the pass | `engine_hot_lanes` 1 → **0**, `unjudged` empty; the floor's `hot`: `posix.fsync`, `select.poll`, `container._write_parquet … ENGINE NATIVE` — the native frame shown, `judged_on` the stdlib frame |
| the floor | A/B by hand, three each: HEAD 12.15 · 12.20 · 12.57 s → 9.76 · 11.31 · 9.90 s; the receipt's floor 9.7 · 12.2 · 11.6 against 10.9 before (inside tolerance each way — noise, named); 546 passed, 3 skipped (+2: the boundary derived from the source, and a lane judged past it — null when nothing is left) |
| blast radius, before the edit | `blast container._write_parquet --depth 2`: `emit` · `emit_all` · `traversal.store_walk` and their tests — none touched: the engine's bytes are unchanged; the edit is the instrument and one test module |
| the constraints | `BURDEN OK` (`burden.json` unchanged; the wheel 299,820 → 299,851 B is #60's last commit, `cli.py`'s import move, landing in this issue's before/after — neither the test module nor `measure.py` ships in the wheel); `CENSUS OK`; `MEASURE DIFF OK`; the gate `GRAPHY_STANDALONE_OK`; `container.py`'s bytes unchanged |
| the review, `/code-review medium` | eight findings, every one fixed: the artifact rule judged inside the top three and fell through to a verdict on an all-artifact lane (the boundary is now named from the source, the judgement runs over the whole profile, nothing left is `null` and `unjudged`); self-over-cumulative is true of any thread-pool lane, hiding honest frames (the rule is the native boundary; the clock artifact is a label only); a boundary frame's caller inflated the same way (`emit` calls `duckdb.connect` itself and is in the set); the fsync finding kept as prose (graphyos #62); the wheel's 31 bytes attributed to a docstring not in the wheel (cli.py, #60's last commit); "~0.95 s apiece, the three slowest" was the profiler's number (0.35 s unprofiled, third to fifth); `measure.py`'s docstring still defining the old rule (rewritten); dead imports and a hand-copied threshold in the test (gone) |

## 97 · THE FLOOR STOPS PAYING DURABILITY FOR STORES IT THROWS AWAY — 107 fsyncs, 390 ms of a 10 s floor by the wall clock (the 7.3 s was one busy disk under the profiler); a no-op in the floor's conftest, the engine untouched, the durability test marked `durable` and proving the real call (2026-09-08 · graphyos issue 62)

**The number, two sources.** The receipt's profiled floor after #61 read `posix.fsync 7.34 s` of self time.
A wall-clock log of every `os.fsync` in the floor (`engine/tests/fsync_log.py`, a pytest plugin wrapping it,
by caller and test): **107 calls, 390 ms**, the largest 13 ms — 96 from `federated_store._sync_then_replace` (346 ms: `compile_store`'s
one sync of the finished store before the rename, RECON §59), 10 from `reseed._atomic_write` (41 ms), 1
from the durability test's own spy. The same log under the receipt's profiler on the next run: 834 ms,
one call of 406 ms — the disk's answer, different every run, 7.3 s once. The issue's own third candidate
set a refusal at 200 ms; the wall clock says 390, so the cheapest form landed: no engine door, no default
moved.

**The change.** `engine/tests/conftest.py`, the floor's one convention: an autouse fixture makes `os.fsync`
a counted no-op for every test — a store built under `tmp_path` is thrown away — except a test marked
`durable`, which gets the real call. `test_GREEN_the_tmp_store_syncs_once_before_the_rename` carries the
mark, asserts it got the real function (the review's point: the ordering spy alone passed under the
no-op — the mark was not load-bearing until the test checked `os.fsync is not conftest.NO_FSYNC`, red
without the mark, green with it), and proves the sync lands before the rename. A future engine fsync
written without the mark is a no-op in the floor; the convention says so in conftest's docstring and the
log plugin shows what reached the kernel. The engine's bytes are unchanged; `graphy build` on a tenant
syncs as it did. The wall log after: 1 real fsync left (the durable test's), 4 ms.

```bash
cd engine && rm -f /tmp/fs.log && FS_LOG=/tmp/fs.log ../.venv/bin/python -m pytest -q -p tests.fsync_log -p no:cacheprovider | tail -1 && python3 -c "import json; rows=[json.loads(l) for l in open('/tmp/fs.log')]; print(len(rows), 'fsync', round(sum(r['ms'] for r in rows)), 'ms')"
cd engine && git stash -q && rm -f /tmp/fs0.log && FS_LOG=/tmp/fs0.log ../.venv/bin/python -m pytest -q -p tests.fsync_log -p no:cacheprovider | tail -1; git stash pop -q      # the before: the plugin is untracked there — copy it beside first
cd engine && for i in 1 2 3; do /usr/bin/time -f 'floor %e s' ../.venv/bin/python -m pytest -q -p no:cacheprovider 2>&1 | grep floor; done
python3 measure.py diff recon.before62.json recon.json | tail -1
```

| check | result |
|---|---|
| the wall clock | before: 107 `os.fsync` · 390 ms (96 `_sync_then_replace` 346 ms · 10 `reseed._atomic_write` 41 ms · 1 spy); after: 1 · 4 ms |
| the floor | three runs each: before 9.76 · 11.31 · 9.90 s (§96's tree), after 9.52 · 10.16 · 10.52 s — a third of a second inside a ±1 s instrument; the receipt's floor 10.3 → 9.4 s; 546 passed, 3 skipped, the durable test green with the real fsync and red without its mark |
| blast radius, before the edit | `blast federated_store._sync_then_replace --depth 2`: `compile_store` · `cli._cmd_build` · `federated_store.main`, 9 tests — none touched: the edit is one conftest and one marker |
| the constraints | `BURDEN OK` (`burden.json` unchanged, the wheel 299,851 B unchanged); `CENSUS OK`; `MEASURE DIFF OK: 38 number(s) moved, none the wrong way past tolerance` (`floor.seconds 10.3 → 9.4 better`; a first run read the express tenant +0.9 s once — alone, `better`); the gate `GRAPHY_STANDALONE_OK`; `federated_store.py`'s bytes unchanged |
| the review, `/code-review medium` | four findings, every one fixed: the re-derive command named a plugin that lived in a scratch directory (`engine/tests/fsync_log.py` is tracked, the command runs from the checkout); the `durable` mark was not load-bearing — the ordering spy passed under the no-op (the test asserts the real function; red without the mark); an unfilled template token in this table (this row); the process-wide no-op makes a future unmarked fsync test vacuous (accepted by name: the convention is in conftest's docstring, the no-op counts its calls, and the log plugin shows what reached the kernel — a per-module patch needs an alias the engine does not carry) |

## 98 · THE REVIEW APPARATUS, PORTED — the adversarial-reviewer card (the done block is what is reviewed; callers and reverse callers from the walk; every blocker routed to one door), `review.py` the CLI battery in the gate (eight checks, each a set difference over a parse of the live tree, each proven red on its own fixture in the same run), and the visual battery over every page this engine emits; the battery's first live run found one class the floor, the gate and the receipt had passed five times (2026-09-09 · graphyos issue 63)

**The number, from the board.** Five issues (#58–#62) drew 33 review findings after the floor, the gate
and the receipt were green — a done line the record contradicted (#59, #60), a join by guess (#59), a
rule that judged on nothing (#61), an unfilled template token on main twice (§92, caught at §97), a
layout hardcoded into a producer, a test whose mark was not load-bearing. Each was fixed by hand after
a cold reviewer named it; none had a door. The review skill ran after the fact with no battery in front
of it and no walk behind it: the callers of a changed symbol were never put in front of the reviewer,
and the reviewer never ran the done block.

**The source.** The Enterprise deck's review apparatus on this box, read in full, nothing copied by
path: the adversarial-reviewer card (REFUTE never confirm; STEP ZERO the done token is the thing
reviewed; the mechanical and the judgment classes; the DISPOSITION — every blocker routed to exactly
one door or eliminated), the frontend-review battery (CLI first, a screenshot never certifies a done
token, every interaction driven), the build_checklist battery (set differences over a parse of the
live tree, fails loud when it cannot run), the visual lint lenses. What travelled is the doctrine and
the mechanical shape; what stayed is theirs by name — `CENSUS OK` after the port, the keyed scrub over
every new file (`SCRUB OK: 4 file(s)`).

**The change, three pieces.**

1. `.claude/skills/adversarial-reviewer/SKILL.md` — the card in graphy's terms. STEP ZERO runs the
   issue's done block line by line before a diff is read; the verdict opens `DONE BLOCK: GREEN|RED|JUDGED`
   then `VERDICT: SHIP|REVISE`. Twelve mechanical classes re-cut on this board's own specimens, each
   naming its door; seven judgment classes; the callers-and-reverse-callers class made concrete —
   `blast` · `descend` · `explain` of every changed symbol pasted into the review, a caller outside the
   diff a finding by name. The DISPOSITION has graphy's five homes: `burden.py`/`workflows.py` for a
   property of the tree · a `measure.py` direction for a number · `arms --verify`/`release.sh --check`
   for a build product · a `review.py` check for a set difference · the card for judgment; none of the
   five eliminates. `/code-review` stays the seat; the card is what it is told. The rung-discipline
   skill's step 6 and its door table carry it now; CLAUDE.md THE MARCH points at it.
2. `review.py` at the root — the battery, stdlib, in the gate. Every check a set difference, every
   check RAISES on a zero denominator and prints its denominator on the clean line, every check with a
   seeded fixture that trips it and a fixed one that does not (`--selftest`), and the flat run re-proves
   that as its own check (`gate-selftest`): `advertised-argv-parses` (every `graphy <verb> …` a document
   advertises — shell fences less comments, a text fence's opening command, every inline span — names a
   verb `cli._build_parser()` has and only flags that verb accepts; a placeholder is the reader's value);
   `cites-nonexistent` (every backticked dotted symbol whose head is a module of this tree is defined in
   the live tree by AST — the store's own input, so the check runs where the store is not);
   `argparse-dest-never-read`; `path-literal-names-nothing` (CLAUDE.md THE FOLDER and THE ENGINE MAP,
   burden.json's doc globs, the hook commands — on disk or gitignored by name); `template-token`;
   `sha-liveness` (RECON's newest section; git says which hex is a commit); `severance` under
   `--diff <ref>` (a function, class or method deleted since the ref that a Python file outside the diff
   imports and uses, by AST, plus every caller the graphy tenant's store holds an edge from, confirmed
   against the live file — the reverse-callers class, mechanical); `visual`. RECON is the record and its
   history advertises flags that have honestly died, so only its newest section is a surface. The gate
   runs the flat battery; the PR gate runs `--diff <base sha>` and posts it beside the burden and the
   receipt's diff.
3. `.claude/skills/frontend-review/SKILL.md` and the `visual` leg: every page this engine emitted on the
   box (the atlases, a showcase's index) holds `sugiyama.check_artifact`'s contract, keeps every colour
   literal inside a `--token:` declaration (a literal in a rule paints one theme and lies in the other),
   and binds every element its script hooks singly — a parse of the HTML, no browser, no new dependency.
   The card keeps the doctrine for the human pass: driven, not looked at.

**The battery's first live run.** `argparse-dest-never-read` found five module mains
(`augment_registry` · `cartograph` · `inventory` · `journal` · `mesh_federation_gate`) that declared
`--tenant-id` as required "for a complete declaration" and never read it — `--tenant-id " "` passed
argparse and was dropped on the floor. Each `_cli_tenant` now takes the declared receipt name and
refuses a blank one with the refusal `open_for` makes; `test_journal.py` carries the RED proof. The
other seven checks were clean on the tree at HEAD. Before the head rule was tightened the battery also
named four prose lines as commands ("graphy tenant's", "graphy onto", "graphy alone," inside text
fences — a code span is a command surface, which is why this sentence quotes them plainly; a `--replay` inside a comment) — a text fence's line is a command only when the command opens
it, and a comment is not a command; the fixture carries both.

```bash
python3 review.py --selftest | tail -1                       # REVIEW SELFTEST OK: 8 check(s), each red on its fixture
python3 review.py | tail -1                                  # REVIEW OK: 8 check(s) · 0 finding(s)
python3 review.py --diff HEAD~1 | tail -1                    # REVIEW OK: 9 check(s) · 0 finding(s)
python3 review.py | grep -E '^ ok ' | sed 's/^ ok  //'        # every denominator
for i in 1 2 3; do /usr/bin/time -f 'review %e s' python3 review.py 2>&1 >/dev/null | tail -1; done
git stash -q && python3 review.py | grep -c 'argparse-dest-never-read engine'; git stash pop -q     # the five, on the tree before this commit
cd engine && ../.venv/bin/python -m pytest -q tests/test_review.py tests/test_journal.py -p no:cacheprovider | tail -1
bash census.sh | tail -1 && python3 scrub.py review.py .claude/skills/adversarial-reviewer/SKILL.md .claude/skills/frontend-review/SKILL.md engine/tests/test_review.py
python3 measure.py diff recon.before63.json recon.json | tail -1
```

| check | result |
|---|---|
| the battery, live | 8 check(s) · 0 finding(s) in 0.80 · 0.80 · 0.80 s — 277 command(s) against 27 verb(s) · 79 symbol(s) against 2336 defined · 16 module(s) declaring arguments · 73 path(s) the router names · 38 tracked document(s) · 0 hex token(s) in §97 · 33 page(s) · 8 check(s) seeded red and green; `--diff HEAD~1` 9 checks in 0.91 s; `--diff HEAD~40` (5 deleted symbols) 1.92 s |
| the selftest | 8 checks, red 1 · 3 · 1 · 1 · 1 · 2 · 2 · 3 and green 0 on every fixed fixture, 0.18 s |
| the tree before this commit | `argparse-dest-never-read` 5 (the five mains); the other checks 0 |
| the battery on this commit's own diff | `severance` named `federated_store.py` and `query.py` still calling `cross_substrate._cli_tenant` with two arguments after the six copies became one — the two red floor tests, found by the check before the floor was run; the reverse-callers class caught its first specimen in the commit that built it |
| the floor | 553 passed, 3 skipped (546 before: `test_review.py`'s six, the journal's RED proof); 9.9 s in the receipt (10.1 before) |
| blast radius, before the edit | `blast cli._build_parser --depth 1`: `cli._main`; `blast sugiyama.check_artifact --depth 1`: `cli._cmd_draw` · `showcase.showcase` + 3 tests — both read-only from the battery; the five `_cli_tenant` edits' callers are the mains in the same files |
| the constraints | `BURDEN OK` (`burden.json` unchanged; the wheel 299,851 B unchanged); `CENSUS OK`; `SCRUB OK: 4 file(s)`; `claude plugin validate .` passed; `WORKFLOWS OK: 5 file(s)`; `MEASURE DIFF OK: 46 number(s) moved, none the wrong way past tolerance` (`gate.seconds 17.0 → 18.7`: the battery's second inside the gate; `wheel_bytes 299,851 → 299,965`: `tenant.cli_tenant`); the gate `GRAPHY_STANDALONE_OK`; the graphy tenant `GRAPHY_TENANT_OK` — the six arm regions re-rendered (six `_cli_tenant` functions left six module inventories), `docs/pillars.svg` re-drawn |
| the review, `/code-review medium` under the card | eight findings, every one folded in, each with its DISPOSITION: severance blind to a rename (`R100 old new` read as an addition) → `--no-renames`, a move is a delete and an add, the floor moves a module · NEW · review.py; a bare attribute match flagged `con.close()` as `K.close` → a reader names a symbol only through its own import binding (`a.K().m`, `K.m` after `from graphy.a import K`), the fixture's sqlite3 control · NEW · review.py; the five `_cli_tenant` copies validated the id and dropped it → one `tenant.cli_tenant` for the six mains (cross_substrate's copy too), the declared name stamped as the cursor `cli:<name>` · NOT NEW · argparse-dest-never-read was satisfied by a read that landed nowhere, accepted by name: an attribute read is a read, the door does not judge what a value reaches; `cites-nonexistent` misjudging `tenant.data_home` as a citation → a bare stem is judged when called, when its first tail segment is a module-level name, else not at all · NEW · review.py; the sha fixture's git under this box's HOME → `_fixture_env`, a failing fixture git is `REVIEW REFUSED` never a traceback · NEW · review.py; a blank `--tenant-id` died with a traceback and exit 1 → one line and exit 2 in every main, the floor asserts it · NEW · this card BLOCK TWO ②; severance parsed 647 files per deleted symbol (1.15 s each) → the bare name as a floor, one parse per reader across symbols, `--diff HEAD~40` 1.92 s for five · NEW · review.py; the severance green fixture never exercised an importer that does not use the name → the fixture's third reader · NOT NEW · gate-selftest was blind to it. Three dropped by the reviewer and taken anyway: the store's `contains` edge counted as a caller (`rel != 'contains'`), the router's "every path this file names" overclaim (the two fences named), the argparse proxy (above) |

## 99 · THE RESEED GRAPH AS SUBSTRATE — every exchange of the archive a node under its session, bound to the code on the literals it names: 392 exchanges · 304 `mentions` onto 127 code nodes through the shards' own dotted names and files (256, the resolver's rule minted as an edge) and a five-line alias registry (the hand weld, 48); `blast`, `explain` and `graphy history --symbol` answer "what did we say about this symbol" from the store in 0.09 s cold; the review's eleven findings folded in (2026-09-09 · graphyos issue 64)

**The number, from the board.** The operator, verbatim: *"having a walkable substrate joined to the literals
is nasty enough in itself, and we can even use an alias override registry if we have to manually weld this
on."* §94 put the sessions on the graph and §95 walked them; neither carried the exchanges or the literals
they name. `reseed_graph` indexed 234 exchange containers and 5,068 terms as a text index, not a shard: a
session that discussed `showcase._clone` was no edge onto `graphy://func/graphy.showcase._clone`, so
`explain` of that symbol showed `DOCS: none` and the estate held 0 exchange nodes (the issue's two
re-derive lines, both 0 on the tree before this commit).

**The change.** The history producer (§94) grows one node type and two edge types. `history://exchange/<session id>/<n>/<speaker>` is one `--- [n] USER|ASSISTANT` marker of the
archive — reseed_graph's own `_EX_RE`, imported, never a second regex — carrying session · n · speaker ·
captured_at · the count of literals in its span and no body (`role` stays the vocabulary's word: the node
type). `session -contains-> exchange`. `exchange -mentions-> <code node id>`: a literal the span carries — a
dotted identifier or a slashed path, never a bare word — that names exactly one node of the code shards
handed in, bound through the shards' own names (`adapters.history.symbol_index`: every node's `dotted` and
each of its two-or-more-segment tails, every module's `file` and each of its slash-suffixes) — the rule
`doors.resolve` applies to a query, minted as an edge that says how it bound (`via` · `literal`), which the
review named precisely: this is the resolver's binding, not the wormhole (a wormhole is a literal that IS a
node id, as `touches` is), and the section, the router and the docstring say so now. `via: dotted`
(`showcase._clone`) · `via: file` (`showcase.py`, `graphy/adapters/__init__.py`) · a literal naming two
nodes binds nothing and is counted (`__init__.py` alone names four). `--aliases <json>` is the hand weld: an
exact literal → one node id, hand-written (`tenants/graphy/aliases.json`: `bloodhound` → the module, `the
timeline door`, `the reseed graph`, `sugiyama`, `the showcase`), matched on token boundaries (`sugiyama`
inside `graphy.sugiyama` is the name the roster binds, never a second hit), tagged `via: alias` so a weld is
never mistaken for a binding; a target that is not a node refuses at mint, a literal the names already bind
refuses as redundant, and when both land on one node the name outranks the weld; `_meta` is the one key that
is not a literal, so `_clone` — exactly the bare word only the registry can bind — is one. The registry, the
code shards' node ids and every session file's sha256 join the inputs digest, so `--verify` names a moved
registry or an edited body as stale. A session captured twice is one node per exchange, the later
capture speaking. Nothing private travels: an exchange node is a session, a number, a speaker and a count;
the shard stays a build product under `substrate/`; `CENSUS OK`.

**The readers.** `doors.SEED_RELATIONS` admits `mentions` out of the seed only: an exchange that named a
symbol is a reader of it, a `BY OWNER: history=N` row under RING, and never a reader of its callers (the
review's specimen: `blast open_for` read `history=32` when two exchanges named it — thirty had named its
callers; it reads `history=2` now, and `blast_pr.py` prints them as `N conversation(s) named it`, apart from
the ring). `cross_substrate.DOC_EXPLAINS` admits `mentions` and `DOC_SCHEMES` admits `history`, with
`DOC_EXPLAINS_SEED_ONLY` holding it to the seed, so `explain` lists the exchanges that named the symbol
itself (`explain compile_store` had listed 25 that named its neighbours; it lists 0 now, and
`showcase._clone` its 3). `timeline.hunt_symbol`
is the new hunt: `graphy history --symbol <id or tail>` resolves through the doors' own `resolve` (two
matches refuse), walks the `mentions` edges against the node to their exchanges and sessions, and hands
`story` the same hits shape — no archive read; `--sessions` in this mode names the archive's captures the
shard does not carry (they cannot answer), `--window` and a term refuse by name; the MCP tool `history`
takes `symbol` instead of `term`, the same rules. reseed_graph's marker is imported inside the read, never
at the top of the producer — a `graphy.lightning` import runs the ripgrep probe, which speaks on stderr
ahead of every refusal on a box without rg (§95's own regression, re-introduced by the first cut and caught
by the review; the RED test runs the refusal with no PATH). Either mode's session block now carries `discussed:` — the code nodes its
exchanges bound, most mentioned first, from the store. The graphy tenant's rebuild passes the registry;
the six arm regions re-rendered (`PRODUCE` and `DOORS` moved: the producer's new functions, the
timeline's).

```bash
cd engine && bash tenants/graphy/rebuild.sh | grep -E '^HISTORY OK'                        # … 392 exchange(s) · 304 mention(s)
cd engine && ../.venv/bin/python -m graphy estate --tenant tenants/graphy/tenant.json --tenant-id graphy --sql "select json_extract_string(attrs,'\$.via') as via, count(*) from adj where edge_type='mentions' group by via order by via"
cd engine && ../.venv/bin/python -m graphy estate --tenant tenants/graphy/tenant.json --tenant-id graphy --sql "select count(distinct dst) from adj where edge_type='mentions'"
cd engine && ../.venv/bin/python -m graphy explain graphy.showcase._clone --tenant tenants/graphy/tenant.json --tenant-id graphy | grep -E 'DOCS|hop1 mentions'
cd engine && ../.venv/bin/python -m graphy blast graphy.showcase._clone --tenant tenants/graphy/tenant.json --tenant-id graphy --depth 1 | grep 'BY OWNER'
cd engine && ../.venv/bin/python -m graphy blast open_for --tenant tenants/graphy/tenant.json --tenant-id graphy | grep 'BY OWNER'      # history=2, the two that named it
cd engine && ../.venv/bin/python -m graphy explain compile_store --tenant tenants/graphy/tenant.json --tenant-id graphy | grep DOCS       # none: no exchange named it
cd engine && /usr/bin/time -f 'wall %e s' ../.venv/bin/python -m graphy history --symbol graphy://func/graphy.showcase._clone --tenant tenants/graphy/tenant.json --tenant-id graphy | tail -1
cd engine && for i in 1 2 3; do /usr/bin/time -f 'mint %e s' ../.venv/bin/python -m graphy history --repo .. --out /tmp/h$i --sessions ../.claude/recovery/sessions --code tenants/graphy/substrate/graphy_graph --code tenants/graphy/substrate/tests_graph --aliases tenants/graphy/aliases.json 2>&1 >/dev/null | tail -1; done
cd engine && ../.venv/bin/python -m graphy history gallery --with showcase --tenant tenants/graphy/tenant.json --tenant-id graphy --sessions ../.claude/recovery/sessions | tail -1
cd engine && ../.venv/bin/python -m pytest -q tests/test_history.py tests/test_timeline.py tests/test_doors.py -p no:cacheprovider | tail -1
python3 review.py --diff HEAD~1 | tail -1 && python3 measure.py diff recon.before64.json recon.json | tail -1
```

| check | result |
|---|---|
| the shard | `HISTORY OK: 121 commit(s) · 42 session(s) · 100 section(s) · 59 issue(s) · 42 receipt(s) · 392 exchange(s) · 304 mention(s)`; 209 of 1,110 distinct literals bind through the roster's names, 0 name two or more; `via`: dotted 103 · file 153 · alias 48, onto 127 distinct code nodes; the mint 0.25 · 0.25 · 0.25 s wall (§94's five counts are the record's own — this section and #63's close are the movement since the tree before this commit, and a mint without exchanges gives the same five) |
| the doors | `explain graphy.showcase._clone`: `DOCS (DOC_EXPLAINS endpoints, 3)`, all at hop 1 — the two sessions that shaped #58's clone (`f5f3ae96` ex 11–12, `db497e24` ex 10); `blast … --depth 1`: `BY OWNER: history=3  tests=2  graphy=1`; `blast open_for`: `history=2`; `explain compile_store`: `DOCS: none` |
| the symbol timeline | `TIMELINE: 2 session(s) · 17 commit(s) · 12 section(s) · 11 issue(s) · 7 receipt(s) · 0.01 s`, `wall 0.09 s` cold — the first session's block reads `discussed: graphy.showcase.showcase ×5 · graphy.converge ×3 · …` |
| the same answer | `gallery` × `showcase`: `5 session(s) · 52 commit(s) · 20 section(s) · 22 issue(s) · 9 receipt(s)` — §95's line read 3 · 45 · 13 · 17 · 4 over a 40-session archive; HEAD's own `timeline.py` loaded beside this tree's over today's store and archive gives the identical five, so the move is the archive's two new sessions, not the code |
| blast radius, before the edit | `blast adapters.history.build_ir --depth 1`: `mint`; `blast doors.explain`: `cli._cmd_door` · `mcp.Doors._door` + 2 tests; `blast doors.blast`: the same two + 1 test; `blast timeline.story`: `timeline.timeline`; `blast cross_substrate.explanations_from_store`: `doors.explain` · `query.main` — every caller inside the diff or reading the same shape; `query.main`'s `--explains` now lists exchanges too, by the same family |
| the floor | 560 passed, 3 skipped (553 before: the producer's six — the weld, the registry's refusals, the literal rule, the token-boundary alias, the edited body as drift, the refusal before the lightning import; the timeline's symbol mode; the doors' fixture grew a history shard with a neighbour-naming exchange inside its two tests); 10.1 · 10.8 across two receipts s in the receipt (9.9 before) |
| the constraints | `BURDEN OK` (`burden.json` unchanged, the wheel 299,965 → 306,126 B); `CENSUS OK`; `REVIEW OK: 9 check(s) · 0 finding(s)` under `--diff`; `MEASURE DIFF OK: 43 number(s) moved, none the wrong way past tolerance` (`floor.seconds 9.9 → 10.8`, `gate.seconds` 19.7, `engine_hot_lanes` 0; one receipt in between read `wheel.seconds 2.8 → 3.5` — pip's own build clock, 3.0 on the rerun, the number the row carries); the gate `GRAPHY_STANDALONE_OK` in 19.3 s |
| the review, `/code-review medium` under the adversarial-reviewer card | eleven findings, every one fixed or dispositioned: the top-level `_EX_RE` import re-introduced §95's stderr-before-refusal regression (fixed, RED test with no PATH — NOT NEW, the class §95 named; the door is the test); the digest blind to an edited body (fixed, RED test); `mentions` transitive in blast (fixed: `SEED_RELATIONS`, the fixture's neighbour-naming exchange) and in explain (fixed: `DOC_EXPLAINS_SEED_ONLY`); `_DOTTED`'s trailing lookahead refusing a sentence's dot (fixed, the review's four specimens pinned); an alias counted inside a name the roster binds (fixed: token boundaries); `bound` tallied per node not per literal (fixed: `bind` returns every literal that bound — 162 → 209 on the live archive, the number this row carries); the binding called a wormhole (the wording fixed everywhere; the mechanism is the issue's spec and `doors.resolve`'s rule — the law's question of whether `aliases.json` belongs under `join_keys` is put to the operator in the hold, not decided here); `--sessions`/`--window` unread beside `--symbol` (fixed: `--sessions` names the archive's captures the shard lacks, `--window` refuses); `_`-keys dropped from the registry (fixed: `_meta` alone); `aliases.json` untracked (added). Every disposition a test or a door; none eliminated |

## 100 · EAT MINTS THE HISTORY SHARD — a stranger's `blast` · `explain` · `history --symbol` reach the conversations the way the graphy tenant's do: `eat` lays `history_graph` beside the code shard of any git checkout (the graphy tenant's own mint: 125 commits · 45 sessions · 420 exchanges · 391 `mentions`), `shell install` re-mints it and recompiles the store, `check` grows a history lane that names the archive the cursor cannot see; the tenant root that is not the toplevel found and fixed on the way (2026-09-09 · graphyos issue 66)

**The number, from the board.** The operator: *"what about the reseed files as a graph that was an internal
thing that we built am i right in that? is that walkable to be searched on top of lightning ripping it via
bloodhound"* — and the answer was: walkable here, not there. §94 and §99 minted the history shard through one
script, `engine/tenants/graphy/rebuild.sh`, with its lane added by hand; `graphy eat` minted the package and its
ring and nothing of the repo's own record, so an eaten repo's store held zero `history://` nodes and the README's
fourth bullet was true of this repo and one command short of true for a stranger's (the softened bullet: `0be368d`).

**The change.** `cli.eat_history(repo, sub, home, package)` — the producer (`adapters.history.mint`) called in
process, never a subprocess: the checkout's commits, the sessions archive at `<repo>/.claude/recovery/sessions`
when it exists, the package's shard as the code the literals bind to, `<repo>/.graphy/aliases.json` the hand weld
when present. `_eat_run` calls it after the ring lands, adds `--lane history_graph:static-dep`, and
`_scheme_index_from_ring(…, extra=("history",))` reads the shard's own edges for its schemes (what the rebuild
did by hand). A directory that is not a git checkout: `HISTORY SKIPPED: … not a git checkout` and no lane; a mint
that refuses is named and the eat stands on the code alone. `shell/install.remint_history` re-mints the shard
`eat` laid (a tenant with none is named, never minted there) and runs `converge --resolve` and `build --container
none` behind it; the SHELL OK line carries the state. `_cmd_check` grows the history lane: `history.verify`
against the toplevel of the tenant's root — `cartograph.repo_toplevel`, because the graphy tenant's root is
`engine/tenants/graphy` and its RECON, receipts and archive sit two directories up: the first rebuild under the new
lane read `CHECK RED: history lane: STALE` with the shard fresh (0 sections and 0 receipts from the wrong
directory), which is the fix's own proof. `timeline.story` tells a shard with no session apart from no shard.
The installed `GRAPHY.md` drops its "needs the tenant's history shard" caveat and gains the `--symbol` row;
`shell/README.md`, `CLAUDE.md`'s eat row and the README's fourth bullet say what a stranger gets.

```bash
cd engine && python3 -m graphy eat <git checkout> --no-provision | grep -E '^HISTORY (OK|SKIPPED)'      # the shard, or the reason
cd engine && python3 -m graphy check --tenant <repo>/.graphy/tenant.json --tenant-id <pkg>                # after a session lands: history lane: STALE
cd engine && python3 -m graphy shell install --repo <repo> | grep -E '^HISTORY OK|history shard'         # re-minted, store recompiled
cd engine && python3 -m graphy check --tenant tenants/graphy/tenant.json --tenant-id graphy               # the graphy tenant: no history finding
cd engine && ../.venv/bin/python -m pytest -q tests/test_cli.py tests/test_shell.py tests/test_cartograph_freshness.py tests/test_timeline.py
```

| check | result |
|---|---|
| a scratch checkout with one session (`fix solo.b.f please`) | `HISTORY OK: 1 commit(s) · 1 session(s) · 0 section(s) · 0 issue(s) · 0 receipt(s) · 2 exchange(s) · 2 mention(s)`, `CHECK OK`, `EAT OK … 0.1s`; `explain solo.b.f` → `hop1 mentions history://exchange/…/1/user`; `history --symbol solo.b.f` → `TIMELINE: 1 session(s)` |
| a second session captured, nothing else moved | `graphy check` → `CHECK RED: history lane: STALE — the inputs digest … is not the shard's …` and no cursor finding (the archive ignores itself); `shell install` → `HISTORY OK: … 2 session(s) … 4 exchange(s) · 4 mention(s)` · `history shard re-minted, store recompiled`; `history --symbol` → `TIMELINE: 2 session(s)` |
| a directory that is not a checkout | `HISTORY SKIPPED: … is not a git checkout — no commits to mint; the sessions archive is still read by the memory doors`, `EAT OK`, `build_lanes == ["solo_graph"]`, no `history_graph/` |
| the production proof | `bash quickstart.sh https://github.com/honojs/hono.git` → `HISTORY OK: 1 commit(s) · 0 session(s) … 310 touches onto code module ids` (a shallow clone: one commit, no archive) · `GRAPHY_QUICKSTART_OK: hono eaten in 19.6s`; `estate --sql "select count(*) from nodes where id like 'history://commit/%'"` → 1; `shell install --repo …/hono` → `HISTORY OK` |
| the graphy tenant, `rebuild.sh` | `HISTORY OK: 125 commit(s) · 45 session(s) · 100 section(s) · 61 issue(s) · 42 receipt(s) · 420 exchange(s) · 391 mention(s)` (§99 read 392 · 304 over 43 sessions); the first rebuild under the new lane `CHECK RED: history lane: STALE` — the tenant root, not the toplevel — then green with `repo_toplevel`; `ARMS OK: 6 arm(s) match the walk (store 21db0d05845b1e38)`; `DRAW OK … -> docs/pillars.svg` |
| blast radius, before the edit | `blast cli._eat_run` 2 · `blast cli._scheme_index_from_ring` 3 · `blast cli._cmd_check` 0 · `blast cli.eat_history` 9 (graphy 6 · tests 3) · `blast shell.install.install` 4 (tests 3) · `blast timeline.story` 11 (graphy 5 · tests 5 · history 1) |
| the floor | 564 passed, 3 skipped in 10.9–11.6 s (560 before: the eat mint and the walk into the exchange, the grown archive as STALE and the re-mint, the bare directory skipped, `repo_toplevel`; the timeline's refusal test re-worded) |
| the constraints | `BURDEN OK` (the wheel 306,126 → 308,310 B); `CENSUS OK`; `SCRUB OK`; `REVIEW OK` under `--diff`; `MEASURE DIFF OK: 9 number(s) moved, none the wrong way past tolerance` (floor 11.6 s · gate 20.8 s · engine-hot lanes 0); the gate `GRAPHY_STANDALONE_OK` |
| the hold | none: the README's fourth bullet is now true of a stranger's repo; the arm regions re-rendered (`remint_history`, `eat_history`, `repo_toplevel` in their inventories) |

## 101 · THREE HARNESSES BEHIND THE MEMORY — the shape decides, never a name: `session_tail.harness_of` reads Claude Code's jsonl, a Codex rollout and a role/content jsonl by their fields; `shell install --harness codex|cursor` writes `.codex/hooks.json` and `.cursor/hooks.json` behind the same three scripts; a real Codex rollout on this box renders 16 exchanges with zero harness rows leaking (2026-09-09 · graphyos issue 67)

**The number, from the board.** The operator: *"its sort of is a model harness … the hooks are sort of agnostic
anyway."* They were agnostic in contract only: the shell README promised any harness the same entry points, but
`install` wrote one wiring and `extract_turns` read one shape — a Codex rollout (`~/.codex/sessions/…/rollout-*.jsonl`)
yielded zero exchanges and was refused as "essentially empty"; a Cursor `transcript_path` was never read.

**The change.** `session_tail.harness_of(row)` names the shape from the row's fields (`payload` under a `type` →
Codex; `type: user|assistant` or `message` → Claude Code; `role` + `content` at the top → the role/content jsonl);
`turn_of(row)` → `(role, text, real)` per shape, and `extract_turns` · `scan_stats` read through it, so
`assert_plausible` counts the same way for every harness. Codex: `response_item`/`message` rows by `payload.role`,
`input_text`/`output_text` blocks; the harness's own `# AGENTS.md instructions`, `<environment_context>` and
`<user_instructions>` user rows typed-not-real, every `developer` row noise; the session id read from the one
`session_meta` row (`reseed._assert_exact_session`). Cursor: `conversation_id` accepted as the session;
`reseed inject --json` prints `{"additional_context": …}` and `session_start.sh --json` calls it. `shell/install`
takes `harness=(…)`: `.claude/settings.json` as before; `.codex/hooks.json` from `shell/codex/hooks.json` (the same
event names and hook shape, `{{repo}}` filled — Codex has no `$CLAUDE_PROJECT_DIR`; the operator trusts it once with
`/hooks`); `.cursor/hooks.json` from `shell/cursor/hooks.json` (`version: 1`, `sessionStart` · `sessionEnd` ·
`preCompact`, merged by command); a harness with no wiring refuses by name. The gate rides only where the pre-edit
payload is documented (Claude Code) and the SHELL OK line says so per harness. `pyproject` ships the two new data
dirs. Fixtures are synthetic rows in the real shapes; no session body of this box reaches the tree.

```bash
cd engine && python3 -m graphy.reseed render --transcript "$(ls -t ~/.codex/sessions/2026/*/*/*.jsonl | head -1)" | grep -c '^--- \[[0-9]*\] USER$'   # 16 today
cd engine && python3 -m graphy.reseed render --transcript "$(ls -t ~/.codex/sessions/2026/*/*/*.jsonl | head -1)" | grep -c '<environment_context>'   # 0
cd engine && python3 -m graphy shell install --repo <eaten repo> --harness codex --harness cursor | grep harness
cd engine && echo '{"session_id":"x","source":"startup"}' | bash <repo>/.graphy/hooks/session_start.sh --json | python3 -c 'import json,sys; print(list(json.load(sys.stdin)))'   # ['additional_context']
cd engine && ../.venv/bin/python -m pytest -q tests/test_session_tail.py tests/test_reseed.py tests/test_shell.py
```

| check | result |
|---|---|
| a real Codex rollout on this box (3,851 rows: 17 user · 79 assistant · 19 developer message rows among 1,216 `item_completed`, 463 `reasoning`, 381 tool calls) | `render` → 16 `USER` markers, 16 `ASSISTANT`, `<environment_context>` 0, `<skills_instructions>` 0, `AGENTS.md instructions for` 0; before the change: refused as essentially empty |
| the synthetic rollout fixture | 4 user rows typed · 2 real, 3 assistant typed · 3 real; the developer rows, the AGENTS.md and environment rows absent from the render; the id from `session_meta` matches the hook's and a stranger's id is a mismatch |
| the role/content jsonl | two exchanges; the `tool_use` and `tool_result` rows skipped; a file in no known shape → `extract_turns == ([], 0)`, `render_full` refuses "essentially empty" |
| the wiring | `install --harness codex --harness cursor` → `.codex/hooks.json` with `SessionStart` · `SessionEnd` · `PreCompact` and the repo's absolute path in every command, `.cursor/hooks.json` `version: 1` with `sessionStart` · `sessionEnd` · `preCompact` and `session_start.sh --json`; a second install adds nothing; `--harness aider` → `SHELL REFUSED: no wiring for harness aider` |
| the hook, by hand | `echo '{…}' \| session_start.sh --json` → `{"additional_context": "# SESSION RE-SEED (startup) …"}`; the no-stdin form `session_start.sh --json now` the same |
| the graphy tenant | `HISTORY OK: 126 commit(s) · 45 session(s) · 101 section(s) … 420 exchange(s) · 391 mention(s)`; `ARMS OK: 6 arm(s) match the walk (store 7bed1ff3f501890e)` after the re-render (MEMORY and CLI moved); `DRAW OK … docs/pillars.svg`; `CHECK OK … container fresh for 7/7` |
| blast radius, before the edit | `extract_turns` 26 (tests 22) · `scan_stats` 25 · `turn_of` 29 · `harness_of` 17 · `reseed.do_capture` 12 · `do_inject` 9 · `shell.install.install` 5 · `_merge_cursor` 0 |
| the floor | 571 passed, 3 skipped in 10.9–11.3 s (564 before: the Codex fixture, the role/content jsonl, the unclaimed shape refused, the Codex capture with its own id, the Cursor conversation id, inject --json, the wiring per harness) |
| the constraints | `BURDEN OK` (the wheel 308,310 → 311,537 B; subprocess sites 26 → 27, `repo_toplevel`'s git); `CENSUS OK`; `SCRUB OK`; `REVIEW OK: 9 check(s)` under `--diff`; `MEASURE DIFF OK: 8 number(s) moved, none the wrong way`; the gate `GRAPHY_STANDALONE_OK` |
| the hold | Cursor is not on this box: its reader is proven on the shape documented outside Cursor, and the README says which harness is first |

## 102 · WINDOWS WRITES A STORE AGAIN — `_sync_then_replace` fsynced an `O_RDONLY` descriptor, which POSIX permits and Windows refuses, so `graphy build` raised `EBADF` and no store was ever written on the platform; one word fixes it, two tests go red on the old line on any host, and a `windows-latest` runner now guards the store lane on every push while the README stops claiming the rest (2026-09-13 · graphyos issue 77)

**The number, from the first client.** They ran graphyos 0.2.3 on a Windows production box
and every `build` failed there while the same tree succeeded on Linux. The visible symptom was
`BUILD REFUSED: [Errno 9] Bad file descriptor` — no path, no operation, no frame — so finding it took
a debugger around `compile_store`. The cause is four characters: `os.open(tmp, os.O_RDONLY)` before
`os.fsync(fd)`. On Windows `os.fsync` is `_commit`, which refuses a handle not open for writing.
POSIX permits the read-only fsync and says nothing, so this floor was green through the entire outage.

**The change.** `os.O_RDWR`, valid on both hosts, no platform branch. The work is the floor, because a
Linux runner cannot see this defect:
`test_GREEN_the_finished_store_is_fsynced_through_a_writable_descriptor` (durable) calls the lane
directly and asserts the access mode of the descriptor `fsync` is handed;
`test_GREEN_the_tmp_store_syncs_once_before_the_rename` resolved its fd through `/proc/self/fd/` —
itself Linux-only, so the single test covering this lane could never have run on the platform that was
broken — and now resolves it through a spy on the module's own `os.open`, which is portable and carries
the open flags, proving the order and the access mode with one spy. `ci.yml` grows `store-windows`.

**What the runner then said.** The first job ran the whole floor on `windows-latest` and came back 33
red of 583. Both durability tests passed, so the store IS written there now — but the platform is not
supported, and a permanently red job teaches a reader to ignore CI. The job narrows to `pytest -m
durable`, exactly the lane #77 broke; the other 33 are graphyos #88 with the runner's own output, six
of them the product rather than the floor (the producer writes the OS separator into node `file`
fields, so a shard minted on Windows is not the shard minted on Linux; `shell install` writes a
`settings.json` that will not parse; `bloodhound` cannot print its heat bars to a cp1252 console;
`showcase` reads a drive-lettered path as a malformed git url; `--profile` imports `resource`; the
journal mints a duplicate seq under a no-op lock). The README's platform paragraph states it with the
number and the issue — #77's second done-bullet, taken because the first is not honestly available.

```bash
cd engine && ../.venv/bin/python -m pytest -m durable -q                      # 2 passed — the mark store-windows runs
sed -n '/^def _sync_then_replace/,/os.replace/p' engine/graphy/federated_store.py | grep 'os.open'
sed -i 's/os.O_RDWR/os.O_RDONLY/' engine/graphy/federated_store.py && (cd engine && ../.venv/bin/python -m pytest -m durable -q); sed -i 's/os.O_RDONLY/os.O_RDWR/' engine/graphy/federated_store.py
python3 workflows.py | grep ci.yml                                            # ci.yml: 3 job(s) · 16 step(s)
gh run view --log-failed -R omnislash157/graphyos --job 103780129817 | grep -c '^FAILED'
```

| check | result |
|---|---|
| the defect, on the client's own box | `BUILD REFUSED: [Errno 9] Bad file descriptor` on every store; after the one word, `BUILD OK` and `CONTAINER OK: 9 shard(s) · 17,903 node row(s) · 114,921 edge row(s) · 5.36 MB parquet · 1.88 s` |
| both tests against the old line | red on Linux: `assert (0 & 2) == 2` — the access mode is the only thing that names this defect off-platform |
| the whole floor on `windows-latest`, 3.12 | 33 failed of 583; **the two durability tests passed** — the store lane is fixed on the platform, measured, not argued |
| the job that ships | `store-windows` runs `pytest -m durable` — 2 tests, green, and the one thing claimed is the one thing proven |
| the symlink-escape test | skips by name where symlinks are not grantable (Windows gives them to a privileged or developer-mode seat only) rather than erroring |
| the floor | 580 passed, 3 skipped (579 before: the new durability regression) |
| the constraints | `WORKFLOWS OK` 5 files, `ci.yml` 3 jobs · 16 steps; `REVIEW OK: 8 check(s)`; the gate `GRAPHY_STANDALONE_OK` |
| the hold | the release bullet of #77 is graphyos #79: the client stays on a hand-patched `site-packages` until 0.2.4 carries this |

## 103 · THE PUBLISHED WHEEL IS THE PRODUCT — graphyos 0.2.3 went to PyPI on 09-08 and the engine changed on 09-09 without the version moving, so `pip install graphyos` handed a stranger an engine with no `adapters/history.py` and no `eat_history` while the README led with the lane that work implements; 0.2.4 is the cut that carries it, and `release.sh --published` compares the published wheel's RECORD against the built one so no future cut can publish a changed engine under a published version (2026-09-13 · graphyos issue 79)

**The number, from the first client.** They found it and then found the worse half of it. Their install
came from a file URL — `direct_url.json` reading `file:///…/dist/graphyos-0.2.3-py3-none-any.whl` — so
**this tenant had never run the published wheel**, and every green they had reported was against
`dist/`, never PyPI. Meanwhile their own `pyproject.toml` pins `graphyos[typescript]==0.2.3` with no
local path: the next clean venv resolves that from the index, gets the historyless wheel, and their
rebuild dies on a verb that is not there. A 10,197-commit history lane was one `pip install -r` from
unbuildable. That moves #79 from a stranger's first impression to *the first tenant cannot rebuild
from a clean checkout*.

**Why nothing on this box could say so.** The gate is offline by law, `measure.py adoption` is the one
off-box verb and is never part of `run`, and neither reads the artifact. `twine check` validates
metadata, not identity. So the one fact that matters — *is what PyPI serves the engine in this tree* —
was checked by nobody.

**The change.** `release.sh --published`: read PyPI's index for the version in `pyproject.toml`; if the
version is absent, say so and pass (a fresh cut contradicts nothing); if present, download the wheel,
verify it against the digest PyPI published, and compare RECORD sets against the built wheel. RECORD
because it hashes **content** — a wheel is a zip and its bytes carry timestamps, so two honest builds
of one tree differ by sha256 and agree on RECORD; comparing symbols instead would find `eat_history`
in `cli.py` in a wheel whose adapter is missing. It runs in the default release lane, never in the
gate, and a PyPI that does not answer REFUSES rather than passing. The host is `pypi.org`, already on
the burden list, and the check lives at the root: `burden.scan_hosts` reads `engine/graphy` only, so
the engine's zero host reach is untouched.

```bash
bash release.sh --published                       # against 0.2.3 before the bump: REFUSED, 27 of 88 rows
bash release.sh                                   # versions · build · twine · published · changelog
python3 -c "import zipfile;print(len(zipfile.ZipFile('dist/graphyos-0.2.4-py3-none-any.whl').namelist()))"
python3 -m venv /tmp/v && /tmp/v/bin/pip install -q dist/graphyos-0.2.4-py3-none-any.whl && /tmp/v/bin/graphy eat <a git checkout> --package <pkg> --site-packages <its site-packages>
```

| check | result |
|---|---|
| the defect, named by the check that did not exist | `PUBLISHED REFUSED: PyPI already carries graphyos 0.2.3, and it is NOT this engine — 27 of 88 RECORD rows differ (graphy/adapters/history.py, graphy/shell/codex/hooks.json, graphy/shell/cursor/hooks.json, graphy/timeline.py, …)` |
| the two artifacts | PyPI's 0.2.3 wheel 283,572 B, uploaded 09-08 17:51; `dist/`'s 0.2.3 wheel 311,537 B, built 09-09 16:49 — one version string, two engines |
| the cut | graphyos 0.2.4: wheel 318,554 B · 90 files · sdist 422,510 B; `twine check` PASSED on both; `published OK (0.2.4 is not on PyPI — a fresh cut, nothing to contradict)` |
| what 0.2.3 lacked, present now | `graphy/adapters/history.py` · `graphy/timeline.py` · `graphy/harness.py` · `graphy/shell/codex/hooks.json` · `graphy/shell/cursor/hooks.json`; `def eat_history` in `cli.py`; the `harness` verb |
| a clean venv, the wheel, a scratch git checkout | `HISTORY OK: 1 commit(s) …` · `BUILD OK: compiled 4 nodes / 4 edges` · `CHECK OK` · `EAT OK`; `graphy history --repo . --out …` runs standalone; `graphy --help` lists `history` (graphyos #89) |
| the version, in five places — the fifth was unguarded | the cut found `graphy/__init__.py` still reading `0.2.3` because `release.sh --check` looked at four literals and not the package's own. Now checked: `versions OK (0.2.4 in pyproject.toml, graphy/__init__.py, .claude-plugin/plugin.json, marketplace.json, server.json)`; `registry OK`. Same class as #79 one level down — a version is a promise, and five literals cannot all be trusted |
| the floor | 581 passed, 3 skipped |
| the constraints | `BURDEN OK` (the wheel 318,554 B, cap 400,000); `CENSUS OK`; `SCRUB OK`; `REVIEW OK: 8 check(s)`; the gate `GRAPHY_STANDALONE_OK` |
| the hold | #79's first two bullets close when the first tenant installs `graphyos[typescript]==0.2.4` from the INDEX in a clean venv and rebuilds their 10,197-commit lane. Publishing is the operator's command; this box builds and refuses, it does not upload |

## 104 · A RELATION'S MEANING IS DECLARED, NOT HARDCODED — a tenant could always say what its edge types ARE and never what they MEAN, so every door walked `python_ast`'s four and went blind to the other 35 a real roster mints; the producer now declares `DEPENDS` · `REACHES` · `STRUCTURAL` · `LEXICAL` per edge type, the shard carries it in its own `PROVENANCE.json` beside the census, the build folds it into one store table and refuses two lanes that disagree, and an undeclared type is `LEXICAL` so an old shard answers exactly as it did (2026-09-13 · graphyos issue 68)

**The number, from the first client.** 547,767 edges, 67 distinct types, 32 lanes, 18 of them from
producers this engine never wrote. `BLAST_RELATIONS` saw 16.5% of it and `DESCEND_RELATIONS` 14.5%.
`blast` on a table with 22 inbound edges answered a confident **zero** while `estate --sql` listed
its readers — the door was not wrong about the graph, it was reading a vocabulary that was not the
graph's.

**Why the obvious fix is the wrong one.** Classified by meaning, that roster is 18.1% depends, 30.6%
containment and **51.3% lexical co-occurrence** — `touched` (commit → file) alone is 129,044 edges.
Walking every relation a tenant mints would make `blast` on a document node return a five-figure set
that means nothing, which is a worse door than one answering zero. The frozenset is wrong in one
direction and follow-all in the other, and one roster proves both. **The dense half of a real store
IS the lexical class, so classifying it is not a nicety on top of the traversal — it is what keeps
the traversal sparse.**

**Where it is declared, and why not the descriptor.** The shard's own `PROVENANCE.json`, because the
edge-type census is already in that file: declared-against-minted is a local check needing nothing
else open, and a vocabulary declared elsewhere can drift from what the lane contains with nothing
noticing. A tenant descriptor holds no producer knowledge to transcribe from, and a roster of 18
foreign producers cannot hold a registration ceremony in one shared file without a merge conflict
per emitter. The comparison is against the **mint** census and never the compiled store: resolution
happens at converge, not at mint, so 81,441 of those 547,767 edges sit in `edges.json` with a
`dst_repr` and no `dst` — 100% of `calls` and `inherits` — and a store-based check would report every
healthy code lane as declaring types it does not mint.

**The change.** `ir` gains the four classes and `Vocabulary.relations`, validated against the
producer's own edge types. `PYTHON_AST_VOCABULARY` and the TypeScript vocabulary declare
`calls → (depends, reaches)`, `inherits · imports · decorates → depends`, `contains → structural`,
which is exactly what `doors.py` hardcoded. `smash` writes a `vocabulary` block into every
`PROVENANCE.json`, naming the types it took the default for rather than leaving a silence.
`federated_store.fold_relations` reads every lane at compile into one `meta` row and raises on a
conflict naming both lanes; `relations_in` answers a class, or the default when a store declares
nothing. `doors.descend_relations` / `blast_relations` replace the constants at every use site, and
the constants become the fallback.

```bash
cd engine && ../.venv/bin/python -m pytest -q tests/test_doors.py
python3 -c "from graphy.ir import PYTHON_AST_VOCABULARY as V, DEPENDS, REACHES; print(sorted(V.types_in(DEPENDS)), sorted(V.types_in(REACHES)))"
python3 -c "import json,graphy.cli as c,graphy.federated_store as f; t=c._load_tenant('engine/tenants/graphy/tenant.json'); r=[s[:-6] for s in t.build_lanes]; print(json.dumps(f.open_for(r,tenant=t,tenant_id='graphy').relations))"
```

| check | result |
|---|---|
| the equivalence that makes it landable | what the two shipped producers DECLARE is what `doors.py` hardcoded: `depends` = `{calls, decorates, imports, inherits}`, `reaches` = `{calls}`, asserted against `doors.BLAST_RELATIONS` and `doors.DESCEND_RELATIONS` in the floor |
| a foreign relation, same shard twice | a `sql_census`-shaped lane whose `reads_table` binds code to a table: **PROVENANCE silent → `blast` returns 0 dependents** (today's answer, the constants untouched); **PROVENANCE declaring `reads_table: [depends]` → `blast` returns the reader**, tagged `reads_table`. The only difference between the two runs is the PROVENANCE |
| `DEPENDS` and `REACHES` are separate | declaring `[depends, reaches]` opens `descend` onto the table; declaring `[depends]` alone leaves `descend_relations` at the default and the table unreached — `imports` is exactly that case today |
| two lanes disagreeing | `StoreError: relation vocabulary conflict on 'reads_table': lane 'core' declares it ['depends'] and lane 'other' declares it ['lexical']` — the build refuses and names both |
| the old store | the graphy tenant's store compiled before this change carries no relations row: `store.relations == {}`, `blast walks ['calls','decorates','imports','inherits']`, `descend walks ['calls']` — the fallback, proven on a real store rather than argued |
| the re-minted store | `{"calls": ["depends","reaches"], "contains": ["structural"], "decorates": ["depends"], "imports": ["depends"], "inherits": ["depends"]}`, and the doors walk the same sets they walked before |
| before and after, on a live symbol | `descend` and `blast` on `graphy.doors.resolve` are **byte-identical** across the re-mint once the store generation is normalised (`dependents=17 own=11 ring=6`, `reached=1`); `explain` differs in one field, `reads=245 → 251`, because the source itself grew by two functions |
| the tests, against the old line | both declaration tests fail with the constants restored — the fix is what they measure |
| the floor | 585 passed, 3 skipped (581 before: the four door tests) |
| the constraints | `REVIEW OK: 8 check(s)`; `SCRUB OK`; the gate `GRAPHY_STANDALONE_OK`; the six arm regions and `docs/pillars.svg` re-rendered against store `b31998a02b935873` |
| the bound, stated so it is not relitigated | a declaration makes reachable what is already minted; it does not invent an edge an emitter never wrote. One measured table stays `0/0/0` even declared, because its reads go through DuckDB over Parquet and no SQL census sees them. This is not a substitute for an emitter gap |

## 105 · A DOOR SAYS WHAT IT DECLINED TO WALK — a zero from `blast` was two different statements, "nothing depends on this" and "I did not read the edges that do", printed identically; the doors now census the unwalked edges on the seed, tell a deliberate classification apart from an undeclared one, and the first run of that line found the declared vocabulary was being dropped on the only code path a user takes (2026-09-13 · graphyos issue 69)

**The number, from the first client.** `blast` on a table answered `dependents=0 own=0 ring=0` while
`estate --sql` listed 22 inbound edges across five relation types. For a tool whose contract is that
no model decided an edge, a silent zero is the worst available answer: it is indistinguishable from
an honest one, and the store knew the difference one query away.

**The change.** `doors.declined(store, seed, admitted, direction)` counts the edges on the seed that
point the way the door walks and were not admitted, by relation. `render_declined` prints
`NOT WALKED: reads_table 9 · indexes_on 8 — …` and — the judgement that keeps it from becoming
noise — **tells a declared skip from an undeclared one**. `contains` sits on nearly every node a code
producer mints and is `STRUCTURAL` on purpose; nagging about it on every healthy blast would train a
reader to scroll past the line that matters. So a DECLARED skip is silent while the answer is
non-zero and reads *"Every one is declared and deliberate: follows=lexical"* when it is zero; an
UNDECLARED one speaks at any size and says what to declare. The notice always appears on a zero,
because that is exactly where the door's silence and the graph's content disagree.

**What the first run of the line found, which is the real value of this rung.** On a healthy blast of
a live symbol it printed *"No producer declared what contains mean"* — and `contains` had been
declared `STRUCTURAL` an hour earlier in §104. Two defects behind one symptom:

- `traversal.Counting`, the proxy the CLI wraps every door's store in, forwarded four methods **by
  hand**. It did not forward `relations`, so every door run through the CLI fell back to the
  hardcoded defaults while the floor — which holds the store directly — stayed green. **§104's
  declared vocabulary worked everywhere except the one path a user takes.** It now forwards by
  default, so the next field added to a store cannot repeat it.
- `history.mint` writes its own PROVENANCE and never got §104's vocabulary block, so the history
  producer declared `follows` and `touches` in code and its shard carried nothing. The lane now
  carries its declaration like any other shard.

```bash
cd engine && ../.venv/bin/python -m pytest -q tests/test_doors.py
python3 -m graphy blast <a symbol with only structural edges> --tenant … --tenant-id …
python3 -c "import json,graphy.cli as c,graphy.federated_store as f; t=c._load_tenant('engine/tenants/graphy/tenant.json'); r=[s[:-6] for s in t.build_lanes]; print(json.dumps(f.open_for(r,tenant=t,tenant_id='graphy').relations))"
```

| check | result |
|---|---|
| the confident zero, explained | a lane whose `reads_table` nobody declared: `dependents=0` **and** `NOT WALKED: reads_table 1 — 1 edge(s) … No producer declared what reads_table mean, so the default was taken. Declare them … and re-mint that lane.` |
| a deliberate classification is not nagged about | `reads_table` declared `structural`, answer zero → `Every one is declared and deliberate: reads_table=structural`, and never a request for what was already given; the same skip with a non-zero answer renders empty |
| an honest zero stays clean | a node with no inbound edges at all: `declined == {}`, no line |
| the census is ordered | three relations on one seed → `reads_table 3 · indexes_on 2 · protects 1`, biggest first, `6 edge(s) on this seed` |
| `descend` too | `reads_table` leaving the reader, undeclared → the notice on the forward door; declared `[depends, reaches]` → walked, notice gone |
| the proxy defect the line found | `traversal.Counting(store).relations` was `AttributeError`-shaped silence; now equal to the store's, and `blast_relations(counted) == blast_relations(store)` is a floor test |
| the history lane | the tenant's store now folds 12 relation types across two producers: `authored·contains → structural`, `calls → depends,reaches`, `decorates·imports·inherits → depends`, `follows·mentions·names·pins·records·touches → lexical` |
| the tests, against the old line | all three declined tests fail with `render_declined` stubbed to empty — the notice is what they measure |
| the floor | 590 passed, 3 skipped (585 before: five door tests) |
| the constraints | `REVIEW OK: 8 check(s)`; the gate `GRAPHY_STANDALONE_OK`; arm regions and `docs/pillars.svg` re-rendered against store `20cc3c8f6472c3fa` |

## 106 · EAT NO LONGER DELETES A LANE IT DID NOT MINT — the prune could not tell "a dependency was dropped" from "something else minted this" and removed both at rc 0 with no count and no name; the previous ring, read before the substrate is cleared and trusted only for its own root package, tells them apart, so a dropped dependency is still pruned and a foreign lane refuses (2026-09-13 · graphyos issue 70)

**The number, from the first client's Windows box.** They ran `graphy eat . --package core
--site-packages .` from the install steps they were handed. It pruned the roster from **32 lanes to
10** — the live Postgres schema, the customer book, the item lexicon, the session memory, the wire,
identity, spec, egress and fourteen more — printed `EAT OK`, exited 0, and said nothing. They did not
notice until a house skill card told them the verb was forbidden. The `/tmp` repro in the issue is
110 bytes of Python; this is the same defect eating 22 lanes of a live tenant. And `check`'s
stale-history remediation led with `graphy eat .`, so **the audit recommended the command that
caused the loss**, with the safe verb in a parenthetical behind it.

**The distinction the issue said could not be made.** The body reads *"The engine cannot distinguish
'a shard the ring no longer names because a dependency was dropped' — correct to prune — from 'a
shard this ring never named because something else minted it' — data loss."* It can. The previous
`ring.json` names exactly what this lane minted last time, and `ring["root"]` names the package it
minted for. A lane in the previous ring **of the same root** and not in the new one is a dependency
this eat dropped — its own to prune, which is what the pruning was for. A lane in neither, or in a
ring minted for a different package, was put there by something else and is not this ring's to
remove at all. Two subtleties decided it: the read happens **before `_clear_substrate`**, which wipes
`ring.json`; and the root check is what makes the monorepo case work, because `eat --package A` then
`eat --package B` finds A's lanes in the previous ring and they are still not B's to delete.

**What refuses, and when.** Only a foreign lane, and only at the deletion — the shards are minted and
standing when it fires, so a refusal costs nothing but the build. `--force` prunes and names each
one. A dropped dependency prints `EAT DROPPED (n): …` rather than vanishing silently.

```bash
cd engine && ../.venv/bin/python -m pytest -q tests/test_cli.py -k "did_not_mint or re_eat or lane_safe"
graphy eat . --package pkg_a --site-packages . && graphy eat . --package pkg_b --site-packages .
graphy eat . --package pkg_b --site-packages . --force
```

| check | result |
|---|---|
| the monorepo case, live | `eat --package pkg_a` → 2 lanes; `eat --package pkg_b` → `EAT REFUSED: 1 lane(s) here were not minted by pkg_b's import ring, now or last time … NOTHING WAS DELETED`, exit 2, and **all three lanes stand** |
| `--force` | `EAT PRUNED (1, --force): pkg_a_graph`, then `EAT OK` — the deliberate path, naming what it removed |
| a dropped dependency still prunes | the existing floor test (`alpha` stops importing `gamma`) passes unchanged: same root, so `gamma_graph` is this lane's own and is removed without a refusal |
| the ordinary re-eat | same package twice: no refusal, no prune line, the lanes unchanged |
| `check`'s remediation | now leads with `graphy shell install --repo <abs>`, "touches no other lane", and names `graphy eat .` behind an explicit caveat — "only equivalent for a tenant whose lanes ARE its ring" |
| the floor | 593 passed, 3 skipped (590 before: the refusal, the ordinary re-eat, the remediation order) |
| the constraints | `REVIEW OK: 8 check(s)`; the gate `GRAPHY_STANDALONE_OK` |
| the bound | a monorepo still cannot get two packages into one built store by eating twice — the second eat refuses rather than deleting, which is this rung's whole job. The multi-lane rebuild is graphyos #71 and this does not pretend to be it |

## 107 · A PATH FIELD IS POSIX ON EVERY HOST — a shard minted on Windows carried `idna\cli.py` where a Linux mint of the same bytes at the same commit carried `idna/cli.py`, so byte-identity, the golden fixtures and the generation digest disagreed across hosts while every node id stayed clean and no walk was ever wrong; one normalisation at the typed record, where 85.7% of a real tenant's file fields pass through (2026-09-13 · graphyos issue 88)

**The measurement, from a Windows production box and two Linux boxes.** The first client built a
matched control — `pip install --target <scratch> idna==3.19`, the engine pointed at that directory,
the production venv untouched — and minted the same corpus this box minted:

```text
                    Linux            Windows
nodes / edges       58 / 395         58 / 395        identical, to the unit
files parsed        10 of 10         10 of 10        identical
node ids            58, 0 with `\`   58, 0 with `\`   identical
file-field digest   47e8d1eeb130931a 6b6d404c1ea8318c   the ONLY difference
  the same fields, separators normalised to `/`  →  47e8d1eeb130931a
```

Replacing `\` with `/` reproduces the Linux digest **character for character**. Nothing structural
diverges; it is the same graph with one field spelled in the local dialect. At production scale the
same box read **0 backslashes in 177,281 node ids** across 32 lanes, and 14,675 of 113,799 file
fields. So this is parity and reproducibility — genuinely broken — and never graph correctness.

**Where the fix goes, settled by a number rather than by taste.** The client attributed every
file-bearing node on their roster to the producer that minted it:

```text
file-bearing nodes            121,799   across 24 lanes
  adapters graphyos ships      17,365     14.3%   (python_ast 8,510 · history 8,855)
  emitters the house owns     104,434     85.7%   (session_memory 53,423 · item_lexicon 36,380 ·
                                                   pg_schema 13,513 · seven more)
```

Fixing `python_ast` alone closes **7%** of that surface. Fixing every adapter this engine ships closes
14.3%. The remaining 85.7% is minted by producers it does not own, in repos it will never see — and
any tenant with its own emitters has that shape, because that is what a tenant is. So the
normalisation goes at `ir.Node.from_mapping`, the last place a shard passes through before anything
reads it, which catches all 24 lanes for one line and every emitter nobody has written yet. The two
shipped producers normalise at their own walk as well, because a shard's `nodes.json` is compared
byte-for-byte by the golden fixtures and those bytes are written by the producer, not by the IR.

**A control that did not control, and the correction.** This box proposed `idna` as the cross-host
corpus without pinning it. Two Linux boxes already disagreed at 58/395 against 55/351 (3.19 against
3.18), and the Windows box shipped **3.11 — eight files, not ten**. Between 3.18 and 3.19 the digest
is blind to the skew because both ship the same ten module files; at 3.11 the file SET moves and the
digest moves with it for a reason that has nothing to do with separators. A bare "different digest"
from that run would have been a true verdict reached through a broken control. The count rule this
box wrote — *"if the counts also differ it is bigger than #88 says"* — was withdrawn before it fired.

```bash
cd engine && ../.venv/bin/python -m pytest -q tests/test_adapters.py -k posix
python3 -c "from graphy.adapters import python_ast as p; n,_,_ = p.mint_records(<a package>); print({r['file'] for r in n.values() if r.get('file')})"
```

| check | result |
|---|---|
| the typed record | `Node.from_mapping` with `file: "x\\sub\\mod.py"` → `x/sub/mod.py`; an already-posix path untouched; a record with no file stays `None` |
| the producer | `mint_records` over a nested package emits `deep/sub/mod.py` and no field carries a backslash |
| against the old line | both tests fail with the normalisation removed |
| the floor | 595 passed, 3 skipped (593 before) |
| the constraints | `REVIEW OK: 8 check(s)`; the gate `GRAPHY_STANDALONE_OK` |
| **CORRECTED by the adversarial review, §114** | the `ir.Node.from_mapping` half of this fix DID NOT RUN on the load path — `from_mapping` is called only from `validate_graph`, which discards the Node it builds, so a foreign shard's backslashes reached the compiled store untouched and this rung covered 14.3% of a real roster, not the 85.7% it claimed. The choke point is `native_json_graph_ir._resolve_shard`, where every shard is admitted as a raw dict |

## 108 · THE MULTI-LANE REBUILD IS PUBLIC — `eat` was first-class for one repo and one import ring and there was nothing for many lanes and mixed producers, so a tenant with its own emitters assembled the sequence out of `cli._clear_substrate`, `cartograph.repo_cursor` and `graphy._portable_flock`; `graphy.rebuild` runs clear → smash → history → init → converge → build → check with placed lanes kept across the clear, and a placed lane's schemes finally come from the ids it carries (2026-09-13 · graphyos issue 71)

**The number, from the first client.** Their rebuild was ~210 lines, of which the engine-orchestration
half was a reimplementation of `eat` minus the prune, resting on three names the engine never
exported — two of them underscore-private and all three free to move under them at any release. And
because the only thing that *looked* like a rebuild was `eat`, `eat` kept being reached for by
tenants it was never written for. That is the root graphyos #70 grew from: `eat` prunes.

**The shape, and the one line that decides it.** A MINTED lane names a package this engine's own
producer walks. A PLACED lane is a shard the tenant wrote itself — and the engine does not run it.
`cartograph` carries no build-lane runner and the engine never runs a shell, so a foreign emitter
stays the tenant's to invoke; what the engine owns is the orchestration around it, which is exactly
the half that was being copied. `clear_substrate(sub, keep=…)` holds a placed lane's whole directory
aside rather than stripping it to the three files a splice reads, so an emitter's own sidecar
survives a rebuild.

**A defect the rung surfaced.** `smash._schemes` derives a lane's `own` from its edge SOURCES, which
is right for a lane this engine minted — every edge leaves a node the lane owns. It is wrong for a
placed lane: a SQL census binds `code → table`, so every src is the code lane's scheme, and the
census claimed to own `core` while disowning the tables in its own `nodes.json`. `shard_schemes`
reads the node ids, because **a lane owns the ids it carries**; `out` is everything else its edges
touch, src or dst. An edges-only lane, which carries no id, keeps today's behaviour rather than
becoming a lane that owns nothing.

**A regression the floor caught the same minute.** Exporting the lane from `graphy/__init__.py`
pulled `cartograph` into every `import graphy`, and the cost of importing this package is a measured
invariant — `graphy.cli` loads five modules and no verb lane, so `--help` never pays for a door it
will not open. The exports are lazy (PEP 562 `__getattr__`) and the invariant holds. The function
`rebuild` is deliberately **not** exported at the package top level: a function of that name would
shadow the module of that name, and `graphy.rebuild.rebuild` would stop resolving.

```bash
cd engine && ../.venv/bin/python -m pytest -q tests/test_rebuild.py
python3 -c "import graphy; print(graphy.Lane, graphy.repo_cursor)"          # lazy, and resolving
python3 -c "import graphy, sys; import graphy.cli; print(len([m for m in sys.modules if m.startswith('graphy')]))"
```

| check | result |
|---|---|
| the done check | one minted lane and one lane a foreign producer wrote, through the public API with no underscore import: `REBUILD OK: 2 lane(s) — 1 minted · 1 placed`, a descriptor declaring both, `CONVERGE` finding the seam unprompted (`pg_schema -> core 1 edge(s) … reads_table=1`), `BUILD OK`, `CHECK OK` |
| the placed lane survives the clear | its `nodes.json` **and** the `emitter_receipt.json` the clear would otherwise have stripped |
| the placed lane is not second-class | its declared `reads_table: [depends]` folds into the store and `blast` on the table returns the code node — graphyos #68 and #71 meeting |
| the scheme index | `pg_schema` owns `pg_schema` and points out to `core`; before, it owned `core` and disowned its own tables |
| the refusals | a placed lane with no shard on disk, an empty roster, a roster that is all placed (no ring to derive the index from), a minted lane with no corpus, an unnamed lane — each by name |
| the three private names | `repo_cursor` and `clear_substrate` are public; `_portable_flock` is deliberately not exported — it is the call's business, not the caller's |
| the import cost | unchanged: `import graphy.cli` still loads `graphy · graphy.cli · graphy.ir · graphy.parity · graphy.tenant` and nothing else |
| the floor | 600 passed, 3 skipped (595 before: five rebuild tests) |
| the constraints | `REVIEW OK: 8 check(s)`; the gate `GRAPHY_STANDALONE_OK` |
| the hold | the first tenant's rebuild dropping all three private imports is theirs to run; this box proved the entry point, not their 32-lane roster through it. No CLI verb was added — the caller is a Python script, which is what a tenant with foreign producers has |

## 109 · A DOOR DOES NOT GUESS A CAUSE — `explain` printed one hardcoded sentence for every seed no test reached, telling a stranger their own untested function came from a wheel and a Postgres table the same; the line now states the mechanism it walked, and the wheel clause survives only where two receipts already on disk prove it (2026-09-13 · graphyos issue 72)

**The number, from the first client.** `doors.py:291` had no condition on it:

```python
lines.append("  TESTS: none reach it within the depth — the ring is minted from wheels, which carry no test suite")
```

It fired on a `pg_schema` table in a foreign lane, where there is no wheel and no ring anywhere near
the seed, and it fires on a stranger's own code the moment they eat their repo and ask about a
function they have not tested. A door whose whole contract is that no model decided an edge was
inventing a reason. The `DOCS:` line one row above is the model — it names the mechanism that found
nothing rather than supplying a cause.

**The change.** The line reads
`none reach it within depth N against the calls · decorates · imports · inherits family`, and the
family is the store's own declared one (§104), so a tenant that declared `reads_table` sees it in the
reason no test was found. `minted_from_distribution` decides the wheel clause from two receipts that
already exist: the shard's `PROVENANCE.corpus.path` and `ring.json`'s `site_packages`. A corpus
resolving under that directory came from an installed distribution and the clause names it with its
version; a corpus anywhere else does not claim it. A repo eaten in place does not qualify even when
its package happens to be installed, which is exactly the case that was being told it came from a
wheel.

```bash
python3 -m graphy explain typing_extensions --tenant tenants/graphy/tenant.json --tenant-id graphy | grep TESTS
cd engine && ../.venv/bin/python -m pytest -q tests/test_doors.py -k tests_line
```

| check | result |
|---|---|
| a ring lane, on the live tenant | `TESTS: none reach it within depth 3 against the calls · decorates · imports · inherits family — typing_extensions is minted from the installed typing_extensions 4.16.0, and a wheel carries no test suite` |
| a stranger's own untested function | the mechanism sentence, and **no wheel claim** |
| a foreign producer's node | the same, with no tenant and therefore no receipt to read |
| the claim dies when the receipt does | the same lane with its corpus path moved outside the recorded site-packages stops claiming a distribution — asserted, not assumed |
| the family is the declared one | a store declaring `reads_table` names it in the sentence |
| the floor | 602 passed, 3 skipped (600 before) |
| the constraints | `REVIEW OK: 8 check(s)`; the gate `GRAPHY_STANDALONE_OK` |

## 110 · AN EDGES-ONLY LANE IS A DECLARED SHAPE, AND A DANGLING ENDPOINT IS ONLY AN ERROR WHERE A LANE SAID IT WOULD BE — `check` was green on a shard holding zero nodes and 259 edges, and on 6,673 edges across a roster pointing at no node anywhere; the count is now reported and the red belongs to a lane that declared `endpoints: resolved` (2026-09-13 · graphyos issue 73)

**The number, from the first client.** `CHECK OK: … container fresh for 32/32 shard(s)` on a tenant
whose `sql_census` lane carried `"node_count": 0, "edge_count": 259` and whose store held 6,673 edges
resolving to nothing. A pure bridge lane is a real and useful shape — and it was entirely unguarded,
so the day a sibling stopped minting an id the bridge would drop that edge in silence.

**Why the count is not the finding.** For a code lane most dangling endpoints are third-party and
stdlib call targets the tenant deliberately does not mint: this repo's own roster reports 1,087
across six lanes, every one of them an `imports` into `__future__`, `abc`, `typing` and their
kind. A red on the number would be red for every healthy roster ever built, which is the fastest way
to make an audit worthless. **The silence was the defect, not the number.** So the number is a NOTE,
and a lane that means its edges must land says `"endpoints": "resolved"` in its PROVENANCE — the same
place §104 put the relation vocabulary, for the same reason: the receipt is already there.

**One line, not one per lane.** Every undeclared lane says the same thing for the same reason, and
six paragraphs of it on every check is exactly how a true notice trains a reader to scroll past the
line that matters — the judgement the doors' `NOT WALKED` line needed one rung earlier (§105). The
loose endpoints collapse into a single sorted line; an edges-only lane keeps its own, because that
one is rare and means something.

```bash
python3 -m graphy check --tenant tenants/graphy/tenant.json --tenant-id graphy | grep "CHECK NOTE"
cd engine && ../.venv/bin/python -m pytest -q tests/test_cli.py -k "edges_only or endpoints_resolve"
```

| check | result |
|---|---|
| this repo's own roster | `CHECK NOTE: 1087 edge endpoint(s) across 6 lane(s) resolve to no node in this roster — graphy 451 · duckdb 297 · tests 288 · typing_extensions 32 · tree_sitter 16 · tree_sitter_typescript 3 (first: imports dst=__future__://module/__future__). Not an error: no lane here declares …` |
| an edges-only lane | named as a shape with its edge types, and told how to make its endpoints binding |
| declared `endpoints: resolved`, endpoints land | no finding, no note |
| declared, one endpoint removed | `CHECK RED: lane bridge_graph declares \`endpoints: resolved\` and 1 endpoint(s) resolve to no node in this roster, first reads_table dst=code://func/code.mod.g`, exit 1 |
| undeclared, the same break | a NOTE on stdout, exit 0 — the shape reported, the roster not condemned |
| a text label is not a dangling endpoint | an edge carrying `dst_repr` and no `dst` is unbound, which is converge's business and a different state; only a resolved endpoint is checked |
| the cost | 34 ms over this repo's 7 lanes and 25,509 edges, read from the shards because the store's edge table carries no owner column to attribute a dangling edge to a lane |
| the floor | 604 passed, 3 skipped (602 before) |
| the constraints | `REVIEW OK: 8 check(s)`; the gate `GRAPHY_STANDALONE_OK` |

## 111 · `graphy recon` — THE COUNTERPART TO `eat` — the engine answered questions and shipped none, so a store sat compiled while its orientation was re-derived by reading source; one verb now walks every corpus, runs `pillars` with the depth escalated 2→3→4, falls back to the lane's own census where there is no pillar shape, and writes the briefing you hand an agent (2026-09-13 · graphyos issue 74)

**The number, from the first client.** Their MCP server was up in every session for months and
`pillars` had never been run once. The orientation it produces in one command was being re-derived
by reading source — at far greater cost and worse accuracy. `eat` got them a store and the product
then stopped and waited for them to already know that `pillars` is the orientation verb, that its
depth needs escalating when it refuses, that `blast` is the pre-edit check. None of that is
discoverable from having installed it, so an engine that works perfectly sat idle.

```text
graphy eat .        # I have a graph
graphy recon        # I have a briefing
```

**It invents nothing.** Every number is a count off compiled edges, it orchestrates verbs that
already exist, and it reuses `pillars.render` rather than re-implementing the crowns and the
cross-arm matrix. Where there is no pillar shape it says so in **`pillars`' own words** at the
deepest cut tried, because "no orchestrator at depth 4 — every unit is consumed more than it
consumes" tells a reader something and "no pillar shape" tells them nothing.

**Two bugs this lane had on its first run against this repo, both found by running it here.**
It required two arms to call something a shape, which rejected `duckdb`'s honest answer of *one*
pillar — a real and common answer for a small package. And it reported its own generic sentence
instead of the reason `pillars` had already produced. Neither would have shown up in a fixture;
both showed up in the first ten seconds of pointing it at the engine's own tenant.

**What it does NOT carry, and that is the point.** The first client's hand-built stand-in ends its
reading key with *"`blast` and `descend` walk the engine's four dependency relations only. A
house-minted relation answers zero — reach those with `walk` or `estate --sql`."* That paragraph was
documentation routing agents AROUND the hardcoded frozenset, and §104 deleted the need for it. This
header says the opposite and it is now true: every relation a producer declared is walked, and a
door names the relations it declined.

```bash
python3 -m graphy recon --tenant tenants/graphy/tenant.json --tenant-id graphy
cd engine && ../.venv/bin/python -m pytest -q tests/test_cli.py -k recon
```

| check | result |
|---|---|
| this repo, all seven lanes, no `--corpus` | `RECON OK: 7 corpus/corpora — 2 with a pillar shape, 5 by census · store 36174aa7e47c6276 -> …/RECON.md (13,695 B)` |
| the shapes | `graphy` 3 arms over 439 cross-unit edges at depth 2; `duckdb` 1 arm over 21 at depth 2 |
| the reasons, where there is none | `tests`: *the store owns no module-bearing node for corpus 'tests'*; `typing_extensions`: *no cross-unit edge at depth 4 — the corpus is one unit* — verified against the module graph, which is 1 unit and 0 cross-unit edges at every depth |
| the escalation is real | `typing_extensions` is tried at 2, 3 and 4 before the census answers |
| the artifact | a how-to-read header with the five roles and the cross-arm line, the store generation, per-corpus sections, a per-lane node and edge type census carrying **what each relation was declared as** (§104), and a staleness footer that says `graphy check` is what tells you and this file will not |
| where it lands | `<data_home>/RECON.md` by default — inside the `.graphy` an eaten repo already gitignores; `--out` overrides |
| the bytes | written `newline="\n"`, asserted on the bytes, so the briefing is LF on every host (the defect graphyos #93 carries for the hooks) |
| `eat` now says so | `recon` is the first line of its ASK IT block: `← START HERE: the whole codebase's shape, one file` |
| the floor | 607 passed, 3 skipped (604 before) |
| the constraints | `REVIEW OK: 8 check(s)`; the gate `GRAPHY_STANDALONE_OK` |

## 112 · THE CUT ESCALATES — `pillars` refused at a fixed depth, named the remedy ("cut deeper") and then made the caller do it by hand; it now deepens to a bound, says which depth answered, and a corpus with no shape at any depth refuses with advice it has not already spent (2026-09-13 · graphyos issue 75)

**The number, from the first client.** 13 code corpora. At the default depth **4 answered**; allowing
the cut to deepen 2→3→4, **9 answered**. Every one of the five that changed is an ordinary nested
Python package — `pkg.tools.thing` rather than `pkg.thing` — so any repo that nests one level deeper
than the default assumes was being told it has no architecture. The remaining four have no
orchestrator at any depth and still refuse; the escalation papers over nothing.

**Whose knowledge it is.** How deeply a repo nests its packages is a property of the repo, visible
to the engine and invisible to a caller who has not read it yet. A refusal that names the fix and
then demands the caller apply it is asking them to know the thing they came to ask about.

**Where it lives.** `pillars.shape(store, corpus, depth=None, max_depth=4)`. An explicit `--depth`
pins the cut and disables the escalation, so today's behaviour stays reachable and the pinned
refusal is unchanged. `recon` (§111) had grown its own copy of this loop one rung earlier and now
calls this one — two implementations of "how deep should the cut be" is one too many, and the door
is where a caller of `pillars` expects to find it.

**The refusal stops giving spent advice.** The pinned message ends "cut deeper (--depth) or it is one
pillar". After an escalation has tried four depths, that sentence tells the caller to do the thing
the door just did — which is how a refusal stops being read. The escalated form replaces it:

```text
PILLARS UNANSWERABLE: corpus 'typing_extensions' has no orchestrator at any depth from 2 to 4 —
every unit is consumed more than it consumes. Either it is one pillar, or raise the bound with
--max-depth
```

```bash
python3 -m graphy pillars --tenant tenants/graphy/tenant.json --tenant-id graphy --corpus duckdb
python3 -m graphy pillars --tenant … --corpus typing_extensions --depth 2     # pinned, refuses as before
cd engine && ../.venv/bin/python -m pytest -q tests/test_pillars.py
```

| check | result |
|---|---|
| a package nesting one level deeper | pinned at 2: `no orchestrator at depth 2`; unpinned: answers **at depth 3**, and the CLI prints `PILLARS: cut escalated to depth 3 — the default 2 yielded no orchestrator for this corpus` |
| a flat package | still answers at the default, and the escalated result is **identical** to the pinned one — arms, totals and graph depth asserted equal, so nothing moved for a corpus the default already fits |
| no shape at any depth | refuses naming the range tried, offers `--max-depth`, and does **not** repeat "cut deeper (--depth)" |
| the bound is honoured | `--max-depth 3` says "from 2 to 3"; a bound shallower than the default refuses by name |
| this repo, live | `typing_extensions` escalates 2→3→4 and then refuses honestly — its module graph is 1 unit and 0 cross-unit edges at every depth |
| `recon` agrees | the same 7 lanes, 2 shaped, 5 by census, through the shared implementation |
| the floor | 610 passed, 3 skipped (607 before) |
| the constraints | `REVIEW OK: 8 check(s)`; the gate `GRAPHY_STANDALONE_OK` |

## 113 · A LANE THAT IS NOT A CALL GRAPH GETS AN ANSWER — every orientation door was a code door, so `pillars` refused on all 18 of a tenant's producer-minted lanes; the refusal was correct and useless, because the engine had already written what each lane holds, and it now falls back to that census rather than answering empty-handed (2026-09-13 · graphyos issue 76)

**The number, from the first client.** `pillars` on `pg_schema` refused — *a table does not call
another table* — while the shard's own receipt held `column 12,469 · index 504 · table 311 · view
173`, joined by `contains 25,440 · indexes_on 504 · references 42 · protects 39`. Read out of the
provenance by hand, that one line is a better briefing for an agent than anything `pillars` could
produce for the lane. The same held for every one of their 18 producer lanes.

**No new computation.** `pillars.census(data_home, corpus)` reads the receipt minted beside every
shard; `render_census` orders by count and names the producer, so a reader knows **whose vocabulary
they are looking at** when the type names are not this engine's. The declared relation class rides
along (§104), so the line says which edges a door will actually walk:

```text
CENSUS: history — 874 node(s) · 1,993 edge(s), minted by history
  node types: exchange 460 · commit 143 · section 111 · issue 73 · session 45 · receipt 42
  edge types: contains 460 [structural] · touches 430 [lexical] · mentions 397 [lexical] · …
```

**The distinction the floor forced, which is the real content of this rung.** The first fallback
caught every `PillarsError`, and the existing floor went red on `--arms 1`: a caller asking for one
arm is a **typo**, not a lane without a shape, and answering it with a census silently rewards the
mistake with a different door's output. `PillarsArgumentError` now separates the two — the CLI
refuses on it, and `shape` re-raises it instead of retrying at a deeper cut, because an impossible
argument is impossible at every depth. Without that second change the subclass was swallowed by the
escalation loop and a typo still produced a census three lines later.

```bash
python3 -m graphy pillars --tenant tenants/graphy/tenant.json --tenant-id graphy --corpus history
python3 -m graphy pillars --tenant … --arms 1          # still a refusal, exit 1
cd engine && ../.venv/bin/python -m pytest -q tests/test_pillars.py
```

| check | result |
|---|---|
| a non-code lane, live | `PILLARS: no pillar shape for 'history' — …` then `PILLARS GAVE THE CENSUS INSTEAD: this lane has structure, it is not a call graph`, the census, exit **0** — the door answered |
| whose vocabulary | `minted by sql_census` in the head line; a lane this engine never produced says so |
| the declared class | `indexes_on 504 [depends] · contains 25,440 [structural]` — the census tells a reader which edges the doors walk |
| a corpus with no shard | refuses by name: *no readable shard receipt at …* — "this lane does not exist" never becomes "this lane is empty" |
| a receipt with no type census | says so rather than rendering an empty block |
| a caller error | `--arms 1` refuses, exit 1, and is **not** retried at a deeper cut |
| `recon` | drops its own census reader and calls this one — the third duplicate consolidated into a door in three rungs (§111 took the loop, §112 took the escalation, this takes the census) |
| the floor | 613 passed, 3 skipped (610 before) |
| the constraints | `REVIEW OK: 8 check(s)`; the gate `GRAPHY_STANDALONE_OK` |

## 114 · THE ADVERSARIAL REVIEW OF THE DAY'S TWELVE RUNGS — one confirmed blocker, and it is a claim in §107 that was true of the code and false of the code path (2026-09-13 · the review of 40154ff..HEAD)

**The pass.** Nineteen commits, 37 files, 2,807 insertions across `engine/`, twelve rungs and the
0.2.4 cut. The battery re-run by the reviewer rather than read from the builder's report:
`REVIEW OK: 9 check(s) · 0 finding(s)` with `severance 0` over 27 changed files; the gate
`GRAPHY_STANDALONE_OK`; the floor 613 passed; the `durable` mark green; 148 `test_RED_` controls.
Every new public symbol blasted against a store rebuilt for the review — `pillars.shape` 6
dependents, `doors.blast_relations` 17, `federated_store.fold_relations` 19, `smash.shard_schemes`
3 — no caller outside its diff.

**THE BLOCKER, class ① (THE PROXY IS NOT THE THING) and SCOPE.** §107 claimed the separator fix was
placed "at the typed record, where 85.7% of a real tenant's file fields pass through". The
normalisation was real and the reasoning about where it belonged was right. **The code path was
wrong.** `ir.Node.from_mapping` is called from exactly one place — `validate_graph`, which builds a
Node to validate it and **throws it away**. The store's load path runs through
`native_json_graph_ir._resolve_shard` on raw dicts and never constructs one.

Proven rather than argued, with a shard written by hand carrying `foreign\sub\mod.py`:

```text
before:  file field IN THE COMPILED STORE: 'foreign\sub\mod.py'   normalised? False
after:   file field IN THE COMPILED STORE: 'foreign/sub/mod.py'    normalised? True
```

So the rung covered the two producers that normalise at their own walk — **14.3%** of the first
client's file-bearing nodes — and not the 85.7% minted by emitters this engine does not own, which
was the entire argument for putting it where it went. The fix moves to `_resolve_shard`, the one
place every shard is admitted, whoever wrote it. §107's bound row is corrected in place rather than
left to read as it did.

**Why no door caught it, and where it is routed.** No check in the battery asks *is the code path
this claim names the code path that runs*, and no regex can. It is BLOCK TWO ① with a new specimen,
and the concrete guard is a floor test asserting the fact **at the surface that matters** — what
`store.record()` returns — rather than at the layer the fix happened to touch. That test is red
against the old line and is the test the first fix needed and did not have.

| check | result |
|---|---|
| the battery, re-run | `REVIEW OK: 9 check(s) · 0 finding(s)`, `severance 0` across 27 changed files |
| the gate and the floor, re-run | `GRAPHY_STANDALONE_OK`; 614 passed, 3 skipped after the fix |
| every new public symbol's callers | walked and pasted; none outside its own diff |
| a door on a stale store | refuses by name — `BLAST UNANSWERABLE: … names no node in this store`, exit 1. Class ② holds: not a silent zero |
| the blocker | CONFIRMED with a repro, fixed at `_resolve_shard`, regression test red on the old line |
| disposition | `NEW · this card · BLOCK TWO ①, specimen added` + a floor test at the store surface |
| the artifacts | arm regions and `docs/pillars.svg` re-rendered against store `a5d3511dca363bb5` |
| **verdict** | **DONE BLOCK: GREEN · VERDICT: SHIP**, after the blocker was fixed in the same session |

## 115 · A FAILURE IS NOT A REFUSAL — `build` printed a platform `OSError` in a refusal's shape, so `BUILD REFUSED: [Errno 9] Bad file descriptor` was the whole symptom of a Windows store bug; the tool's own judgement now refuses by name and everything else prints as a failure with its frame (2026-09-13 · graphyos issue 78)

**The defect.** `_cmd_build` caught `(StoreError, OSError, ValueError)` and printed each as
`BUILD REFUSED: {exc}`. A refusal is the engine's judgement. An `EBADF` from the platform is not one,
and giving it the refusal's shape threw away the path, the operation and the frame. The first
client had to put a debugger around `compile_store` to find the cause.

**What the walk found before the edit.** Removing `OSError` from the refusal set would have been
the one-line fix, and it would have been wrong. With a one-lane tenant and no shard on disk, today's
tree answered:

```text
BUILD REFUSED: [Errno 2] No such file or directory: '…/data/x_graph/nodes.json'
```

The most common user mistake reached the CLI as a raw `FileNotFoundError` too. It carried a filename
only because of where the loader happened to open the file. Every other expected read failure in
`federated_store` was already wrapped in a `StoreError` with its path; this one was not. So the fix
has two halves:

- `compile_store` checks every declared lane's `<data_home>/<slug>_graph/{nodes,edges}.json` before
  any open, and refuses by name: `lane 'x' is declared but has no shard (nodes.json + edges.json) at
  … — missing edges.json; mint or place the shard, then build`.
- `_cmd_build` keeps `StoreError` and `ValueError` as refusals. Any other `OSError` prints
  `BUILD FAILED: unexpected <Type> (errno=…, filename=…) while compiling <store path> — this is not a
  refusal; the traceback follows`, then the traceback, exit 2.

| check | result |
|---|---|
| the surface, a missing shard | `python3 -m graphy build …` → `BUILD REFUSED: lane 'x' is declared but has no shard …`, no traceback |
| the surface, an unexpected OSError | `test_RED_build_prints_an_unexpected_OSError_as_a_failure_with_its_frame_never_a_refusal` drives `cli.main(["build", …])`: no `BUILD REFUSED`, `errno=9`, the raising frame in the traceback |
| both tests against the unfixed tree | red (source stashed, both FAILED) |
| the graphy tenant | `build --container none` → `BUILD OK: compiled 3903 nodes / 9712 edges` |
| the floor | 616 passed, 3 skipped (`cd engine && ../.venv/bin/python -m pytest`), up from 614 |
| the gate and the battery | `GRAPHY_STANDALONE_OK`; `python3 review.py --diff HEAD` → `REVIEW OK: 9 check(s) · 0 finding(s)` |
| found on the way | the arm regions' `dependents=` counts `history` owners, so a session that discusses a crown turns `arms --verify` red. The same surface as graphyos issue 90, commented there rather than filed twice |
| the adversarial review | a cold subagent told the card re-ran the floor, the gate and the battery, and blasted `compile_store` (two engine callers plus 67 tests; the argv callers in `rebuild` · `refresh` · `eat` · `shell install` read only the exit code, which is still 2). It checked the new pre-check against `raw_shard`'s requirements and got a real `PermissionError` to print with its frame. **DONE BLOCK: JUDGED (each "Done when" bullet repro'd) · VERDICT: SHIP**, no blockers |
| disposition | the required file list was written in two places, so the check now derives it from `native_json_graph_ir.SHARD_INPUTS`: ELIMINATED, fixed in this commit · the same defect in the other verbs' catches: a new rung, graphyos issue 95, not a widening · the history lane went stale on this section's own edit: re-minted before commit |

## 116 · A ZERO SAYS WHY — `eat` printed `HISTORY OK: … 0 session(s)` over a 400-file archive and nothing else, because two header regexes missed on every file and a miss was a silent `continue`; the scan now counts what it saw, the receipt carries it, and a skipped file is named in the line CI and a human read (2026-09-13 · graphyos issue 80)

**The defect.** `read_sessions` read a file only when its head matched both `^session: <id>$` and
`^captured_at: <iso>$`. The first client's writer put pane attribution after the id
(`session: <id> · pane %99 (ledger-attributed)`) and wrote `captured_by` with no `captured_at`.
Both regexes missed on all 400 files, each was skipped with a bare `continue`, and the only signal
anywhere was the count of zero.

**The change.**

- `_SESSION_HEADER` accepts an optional ` · …` after the id. The id capture is still the hex-and-dash
  run only, so the attribution never becomes part of the id.
- `read_sessions(sessions, census=None)` fills `files · header · captured · read` as it scans. Its
  timeline callers pass nothing and are unchanged.
- `mint` stores the census in `PROVENANCE.history` as `session_files · session_headers ·
  session_captured`. `_history_report`, the one report both `graphy history` and `eat` print,
  leads with a scan line whenever the archive held more files than it read:
  `HISTORY: 40 file(s) · 40 with a session header · 0 with captured_at — 40 skipped: a session is read
  only when its header carries both session: <id> and captured_at: <iso>`. An archive that is fully
  read prints no extra line. A receipt from before this section has no `session_files` and prints
  none.
- The verify digest is built from what was read, so an existing archive's shard stays fresh.

| check | result |
|---|---|
| the client's shape | 40 of this repo's own sessions rewritten with the attribution suffix and `captured_by` → `python3 -m graphy history --repo … --sessions <that>` prints the scan line above, 0.10 s |
| the real archive | `python3 -m graphy history --repo <abs> --out <scratch> --sessions <abs>/.claude/recovery/sessions` → 51 files, `51 session(s)`, no scan line, 0.22 s |
| the floor test against the unfixed tree | `test_RED_an_archive_whose_headers_all_miss_names_what_it_skipped` red with the source stashed |
| the floor | `cd engine && python3 -m pytest -q` green |
| the gate and the battery | `GRAPHY_STANDALONE_OK`; `python3 review.py --diff HEAD` → `REVIEW OK: 9 check(s) · 0 finding(s)` |
| the adversarial review | a cold subagent told the card probed the regex (the attribution never enters the id; malformed separators still miss), ran old and new regex over the real archive (identical ids, all 51 read, the verify digest unmoved), checked an old receipt with no `session_files` (no line, no KeyError), and put the old regex back by monkeypatch to turn the floor test red. **VERDICT: REVISE**, and the code was not what it blocked: this section's first draft quoted the box's absolute checkout path (`SCRUB RED: RECON.md: private token`) while its gate row claimed green |
| disposition | the private path → NOT NEW · `scrub.py` fired as designed; the row now cites `<abs>` and the gate re-ran → `GRAPHY_STANDALONE_OK` · the gate row written before the gate ran → corrected by re-running first · the timeline doors (`hunt` · `history --symbol`) still pass no census and stay silent on a miss archive → ELIMINATED · outside the done block, which names the mint path · the tenant's history lane stale → ELIMINATED · stale before the diff; re-minted by the rebuild before close |

## 117 · THE ARCHIVE BINDS TO THE WHOLE RING — `eat_history` handed the history lane the root package's shard alone, so in a monorepo every session that named a sibling package bound nothing: the first client measured 548 mentions against the root and 2,667 against the ring, four in five of the weld lost; a literal now binds onto every shard the ring minted, while a commit still touches only the repo's own (2026-09-13 · graphyos issue 81)

**The defect.** `cli.eat_history` called `history.mint(…, code=[sub / f"{package}_graph"])`. The
ring had already minted every sibling and dependency beside it, and `ring.json` names each one,
but the literals bound only to the root package's names.

**The change.**

- `history.mint` (and `graphy history`) takes `names`/`--names`: shards whose names a literal binds
  onto beside `--code`, which never enter the file→module map a commit's `touches` read.
  The receipt carries them as `corpus.names` and `verify` reads them back.
- `cli._ring_code(sub, package)` returns the package's shard plus every on-disk shard `ring.json`'s
  `minted` names. `eat_history` passes the package's shard as `code` and that list as `names`.
- Why the split: the first draft passed the whole ring as `code`. The review ran it on hono, whose
  shard and zod's both record `src/index.ts`, and `code_index` refused (`--code shards disagree on
  'src/index.ts'`). The history lane was skipped under a green `EAT OK`. A dependency's file is
  never the repo's, so a touch onto it would be a join by guess anyway.
- The cost, which is lawful: a root literal that a ring shard also names now names two nodes and binds
  nothing. The review counted 79 of 1,511 root literals on the fastapi ring (`cli.main` is also
  idna's), 2 of 193 on express, and 0 on sqlalchemy and graphy.
- Latent, and outside the done block: `rebuild.rebuild` with several minted lanes reads the last
  smash's `ring.json`. No caller in this repo passes it `history=True`.

| check | result |
|---|---|
| hono, a real eat | a scratch git copy of the hono checkout with a one-exchange archive naming `v3.ZodError.ZodInvalidTypeIssue` and `aws_lambda.handler.sanitizeHeaderValue`, `graphy eat --package hono --producer typescript_ast --site-packages <hono_ring/node_modules>`. The fix gives `HISTORY OK … 2 mention(s)` (onto zod and hono), 310 touches, `CHECK OK`, 1.6 s. HEAD gives 1 mention (hono only) and the same 310 touches. The first draft gave `HISTORY SKIPPED` |
| graphy, a real eat | this repo's engine as a scratch checkout with the real archive, `--package graphy --site-packages <.venv site-packages>`, `RING: 5 shard(s)`. HEAD gives 357 mentions onto 1 shard; the fix gives 358 (one onto `typing_extensions`), 1.3 s. A clean A/B/A repeats both numbers. This archive talks about graphy itself, so the gain is small; the client's monorepo delta is the issue's evidence |
| the floor tests | `test_GREEN_eat_binds_the_archive_to_every_ring_shard_not_the_root_alone` (a git repo where `solo` imports a sibling `sib`: an exchange naming `sib.c.g` becomes a mention onto `sib://func/sib.c.g`, and `corpus.code` is `solo_graph` alone; red with the source stashed) · `test_GREEN_a_names_shard_binds_a_mention_and_never_a_touch_even_where_its_files_collide` (a names shard recording the root's own file: as `code` it refuses, as `names` it binds its mention, every touch stays on the root, `verify` is fresh) |
| the floor | `cd engine && python3 -m pytest -q` green |
| the gate | `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` |
| the adversarial review | a cold subagent told the card. **VERDICT: REVISE** on the first draft: the hono refusal above, found by a real eat, and the touch-by-guess of a dependency's file. Disposition: NEW → fixed here by the names/code split, with its floor test. The ambiguity cost → ELIMINATED, named above. `rebuild.rebuild`'s last-ring read → ELIMINATED, latent, named above |

## 118 · THE PRINTED MCP BLOCK RUNS THE GRAPHY THAT ATE — `eat` told a stranger to paste a config naming `shutil.which("graphy")`, which on the first client's box was another venv's engine, and an absolute `--repo` a tracked `.mcp.json` cannot carry; the command is now the console script beside the eating interpreter, spelled relative when it lives in the repo, with `--repo .` (2026-09-13 · graphyos issue 82)

**The defect.** `cli._graphy_command` read PATH first. `_next_steps` and `showcase.compose` pasted
`cmd[0]` and `mcp_args`' absolute repo into the block. The client's `~/.local/bin/graphy` was not
the install that ate the repo.

**The change.**

- `cli._graphy_command` never reads PATH: graphy (or graphy.exe) beside `sys.executable`, else
  `sys.executable -m graphy`.
- `cli.mcp_config(cmd, desc, package)` is the one block both printers use. For eat's layout the
  `--repo` is `.` and a command inside the repo is relative to it. A command outside the repo stays
  the absolute path of the eating install. A descriptor elsewhere keeps `--tenant`/`--tenant-id`.
- The printed line says the paths are relative, so the client starts in the repo root.

| check | result |
|---|---|
| a real eat | `pallets/itsdangerous` cloned into the scratchpad with an in-repo `.venv` holding this engine, `.venv/bin/graphy eat --repo <abs> --site-packages <.venv site-packages> --package itsdangerous` → `EAT OK` 0.1 s, printed `"command": ".venv/bin/graphy"`, `"args": ["mcp", "--repo", "."]`, no `CLAUDE_PROJECT_DIR` |
| the client, the surface | that block pasted into `.mcp.json`, `enableAllProjectMcpServers`, `claude -p "reply ok" --output-format stream-json --verbose` from the repo root → `graphy` `connected`, 7 `mcp__graphy__*` tools |
| the limit, measured | the same launch from `src/` → `failed`; an absolute config launched from `src/` → `connected`. A project config's relative command and argv resolve against the launch directory, not the project root. The plugin (`${CLAUDE_PROJECT_DIR}`) failed from `src/` too. Filed as graphyos #99 |
| the floor test | `test_next_steps_prints_a_project_mcp_json_that_runs_the_graphy_that_ate` (a decoy `graphy` on PATH, the venv inside and outside the repo, with and without the console script) — red with the source stashed |
| the floor · the gate | `cd engine && ../.venv/bin/python -m pytest -q` green · `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` |
| the adversarial review | a cold subagent told the card. **VERDICT: REVISE**, one blocker: a backticked graphy.exe in this section, which `review.py` reads as a dotted symbol, turned the gate red after it had passed. Disposition: fixed in the prose, gate re-run green. The code: all three done lines GREEN, and it confirmed the test goes red on the old code. Showcase text and page lacked the start-in-the-root line → fixed here. A script beside the interpreter without the executable bit → ELIMINATED, unlikely |

## 119 · A SHADOWING GRAPHY IS REFUSED BY NAME — a client repo's empty `graphy/__init__.py` ahead on `PYTHONPATH` killed the console script with `No module named 'graphy.cli'`, and a directory left holding only `__pycache__` loads as an empty namespace package in silence; the console scripts now enter through `_graphy_launch`, beside the package, which reads the spec of the name `graphy` before importing it and refuses naming the directory that won and the engine it hid (2026-09-13 · graphyos issue 83)

**The defect.** `[project.scripts]` named `graphy.cli:main`. The shim's import runs before a line of
the package can check anything, so no check inside `graphy/` can see a shadow.

**The change.**

- `_graphy_launch.py` is a top-level module (`[tool.setuptools] py-modules`) beside `graphy/`.
  `shadowing(spec)` reads `importlib.util.find_spec("graphy")`: no spec, a namespace spec, or an
  origin that is not its own sibling `graphy/__init__.py` is a refusal naming both paths. `main()`
  prints it on stderr and exits 2, else runs `graphy.cli.main`.
- `graphy` and `graphyos` both enter through it. `python -m graphy` does not: the name it runs is
  the one that shadows.

| check | result |
|---|---|
| the defect, reproduced | a scratch venv with this engine as a wheel, `PYTHONPATH=<dir holding an empty graphy/__init__.py>` → `ModuleNotFoundError: No module named 'graphy.cli'`. The editable `.venv` with a `__pycache__`-only `graphy/` on `PYTHONPATH` → `--help` ran with the package's `__file__` None |
| the real run | the same three shapes after the change: wheel + empty package → `graphy: REFUSED — the import name 'graphy' resolves to <dir>/graphy, which shadows the engine installed at <venv>/site-packages/graphy`, exit 2; editable + `__pycache__`-only → the namespace refusal, exit 2; editable + empty package → refused, exit 2. Clean `graphy --help` and `graphyos --help` from both installs run |
| the floor test | `tests/test_launch.py`: an empty `graphy/` first on `PYTHONPATH` → exit 2, both paths named, no `No module named`; the engine alone launches; a namespace spec and the intended spec; both `[project.scripts]` entries name `_graphy_launch:main` — red with the entries reverted |
| the floor · the gate | `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` |
| the adversarial review | a cold subagent told the card. **VERDICT: REVISE**, one blocker: the floor called the launcher directly, so reverting `[project.scripts]` to the old entry stayed green. Disposition: the wiring test above, shown red on the reverted entries. The reviewer's own run: a wheel and strict · compat · lenient editable installs, an empty shadow refused in all four, clean launches in all four, no false refusal; a namespace directory shadows only the lenient editable finder, where the refusal fires, and loses to a regular package everywhere else. `out of the working directory` in the refusal → dropped, a console script's path starts at its own `bin/`. A `.pyc`-only distribution → ELIMINATED, unlikely |

## 120 · A MONOREPO IS ITS OWN RING — `eat` over a repo with several importable packages refused with "name one with `--package`" and nothing more, so the first client named one and the default provision pip-installed the whole repo into a second venv; the move that works, `--site-packages` naming the directory the packages sit in, was found by reading source. The refusal now names that directory as the ring, and the README says it with the example (2026-09-13 · graphyos issue 84)

**The change.**

- The several-packages refusal in `_cmd_eat` appends: the package that imports the others, with
  `--site-packages <dir>` as the ring, where the directory is the parent of the candidates (the repo
  root, `src/`, or both).
- README: "A monorepo is its own ring", the one-command example, and the line that a second
  `eat --package` refuses and names the first ring's shards instead of deleting them (the #70 guard).
- Packages under both the root and `src/`: the refusal groups them by directory and says one
  `--site-packages` is one directory, a sibling in the other named unresolved.
- The #70 guard's advice is this eat again (`_eat_again`): the repo, `--package`, the resolved
  `--site-packages` or `--no-provision`, then `--force`, where it used to print `graphy eat . --force`,
  which a monorepo refuses.
- No `--ring repo` flag: the refusal prints the exact argument, so a flag would be a second
  spelling of it.

| check | result |
|---|---|
| the real run | a scratch git repo, `alpha` importing `beta.core` and `requests`, `beta` beside it: `graphy eat .` → `EAT REFUSED: 2 importable package(s) … alpha, beta; name one with --package — the package that imports the others, with --site-packages <repo> as the ring …`; `graphy eat . --package alpha --site-packages .` → `RING: 2 shard(s) · stdlib skipped 0 · unresolved requests`, `EAT OK … 0.1s`, no venv made; `eat --package beta` after it → exit 2, `NOTHING WAS DELETED`, naming `alpha_graph` |
| the review's repros, after | `r84/root`: `eat --package core --site-packages .` after `app` → the advice `graphy eat <repo> --package core --site-packages <repo> --force`, which ran → `EAT PRUNED (1, --force): app_graph`, `EAT OK`; `r84/mixed` (`app/` at the root, `src/core/`) → `they sit in 2 directories (<repo>: app; <repo>/src: core) …` |
| the floor tests | the root layout added to `test_RED_eat_settles_the_package_before_it_provisions_anything`; `test_the_several_packages_refusal_names_the_src_directory_as_the_ring`; `test_a_mixed_root_and_src_layout_is_told_one_directory_cannot_hold_both`; the advised argv asserted in `test_RED_eat_refuses_to_delete_a_lane_it_did_not_mint_and_force_is_the_deliberate_path` — all four red with `cli.py` stashed |
| the floor · the gate | `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` |
| the adversarial review | a cold subagent told the card. **VERDICT: REVISE**, two blockers. The README's `--force` sentence led to the guard's `graphy eat . --force`, which a monorepo refuses → the advice is the full argv, above. A mixed root and `src/` layout was promised siblings one directory cannot hold → grouped by directory, above. The dropped flag: acceptable, an alias. `showcase` over a monorepo passes on a refusal naming flags it does not take, and a repo package with a stdlib name is skipped silently: both predate this diff, filed as graphyos #100 and #101. The CLI arm region re-rendered for `_eat_again`; SEAM's 86→87 stays on #90 |

## 121 · A COMPONENT IS A MODULE — `typescript_ast` read `.ts` and `.js` and never opened a `.svelte` file, so 73.6% of the first client's SvelteKit frontend was invisible and `blast` on a store function its components call read 0; a `.svelte` or `.vue` file is now a module whose script blocks the same tree-sitter pass walks at the file's own lines, and a component's top-level calls are its own (2026-09-13 · graphyos issue 85)

**The defect.** `walk_files` filtered on `.ts .tsx .mts .cts .js .jsx .mjs .cjs`. A component was never
read, so it was never a candidate for any edge, right or wrong.

**The change** (`graphy/adapters/typescript_ast.py`).

- `.svelte` and `.vue` are read. `component_script` turns every byte outside a `<script>` body into
  a space and keeps the newlines, so one parse sees every script block at its own line and offset. A
  `<script>` inside an HTML comment is markup. `lang="ts"` picks the TypeScript grammar, anything
  else TSX. The template is markup and is not read.
- A component is a module named by its file (`components/Carousel.svelte` → `….components.Carousel`,
  never folded as `index`). When a source file already holds that name (`+page.svelte` beside
  `+page.ts`), the component takes `_svelte` / `_vue`.
- A component's top-level statements run per instance, so their calls are `calls` edges from the
  component module, including the calls inside an anonymous arrow (`onMount(() => load())`).
- No new vocabulary. A rune declaration (`let x = $state(0)`) is the call `$state(...)` at its line.
  An assignment to it is not an edge in the nine words.
- Names are counted across every file read: a component whose name another file also claims takes
  its suffix, so `Foo.svelte` beside `Foo.vue` are `Foo_svelte` and `Foo_vue`. A component's id
  moves when such a sibling appears, and the journal shows it born and died.
- Only a `<script>` that opens its line is a block: `{@html '<script>…</script>'}` in a template is markup.

| check | result |
|---|---|
| the fixture, the surface | a SvelteKit-shaped `svapp` (a store, `Carousel.svelte` with a module script, a commented script and a generics attribute, `+page.svelte` beside `+page.ts`, `Widget.vue`), `graphy eat . --no-provision` then `graphy blast loadItems` → `dependents=3`: `svapp.lib.Widget.go` and `svapp.lib.components.Carousel` at hop 1 by `calls`, `svapp.routes.+page_svelte` at hop 2 by `imports`. The old adapter never opened either component |
| a real SvelteKit app | `sveltejs/realworld`, shallow clone, `graphy eat . --no-provision`: before, `parsed 16 of 16 files`, 35 nodes / 89 edges; after, `parsed 40 of 40 files`, 59 nodes / 137 edges, 0.16 s. Its imports go through `$lib` (`$lib/api.js` 9 times): `RESOLVE … 83 label(s) -> 6 edge(s) … unresolved 67`. Aliased imports are filed as graphyos #102 |
| no change where there are no components | `PYTHON=../.venv/bin/python bash tenants/hono/rebuild.sh` → `hono 1174 nodes / 4596 edges` and `tenants/express/rebuild.sh` → `express 69 nodes / 398 edges`, the same with the adapter stashed. Both tenants' arm drift is the same before and after |
| the floor tests | `test_GREEN_single_file_components_are_read_at_their_own_lines` · `test_GREEN_blast_on_a_store_function_returns_the_components_that_call_it` (red on the old adapter) · `test_GREEN_component_names_never_merge_and_markup_scripts_and_plain_top_levels_mint_nothing` |
| the floor · the gate | `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` |
| the adversarial review | a cold subagent told the card. **VERDICT: REVISE.** Done lines 1, 3 and 4 GREEN, re-run: CRLF and multibyte markup keep lines; hono hashes identical; the receipt pin moves with the file listing. Line 2 RED and **the hold is correct**: `activeIndex` has no node type and an assignment has no edge type, so the ruling is two words (a state node, a write edge; the specimen's `mutates_state` is itself outside the nine), and the issue's "no new vocabulary" contradicts its own specimen. Blockers: CHANGELOG drift → regenerated; `Foo.svelte` beside `Foo.vue` merged into one module → names counted across every file, floor test. `{@html '<script>'}` read as code → a block must open its line, floor test. Vue's Options API (`export default { methods: {…} }`) mints no calls, because the pass never descends into object-literal methods → named here, not new. A mixed `const a = () => x(), b = y()` at a component's top level drops `y()` → ELIMINATED, minor |
| the arm region | PRODUCE re-rendered for `component_script`; SEAM's 86→87 stays on #90 |
| done line 2 | **MARCH HOLD** — the operator's ruling on the nine words: a state node type and a write edge type for a rune's declaration and its assignments, or the rune stays the tenant's emitter's |

## 122 · A RUNE IS STATE AND A WRITE IS AN EDGE — §121 held line 2 of issue 85 because the nine words had no place for a reactive binding or an assignment to one. The operator ruled for two words declared on `typescript_ast`'s own vocabulary, recognised through an exact table the producer owns: `let x = $state(…)` is a `state` node, and every assignment to it is `writes`, bound through scope, so `blast` on a rune names every writer (2026-09-14 · graphyos issue 85)

**The ruling.** The operator's words: "yeah 2 feels roght lets rearm amd test. if it doesnt work back to drawing board."
Option 2 was an exact rune table plus a `state` node and a `writes` edge (DEPENDS and REACHES),
declared by the producer and never by a door.

**The change** (`graphy/adapters/typescript_ast.py`).

- `SVELTE_RUNES`: `$state` · `$state.raw` · `$derived` · `$derived.by` are state; `$props` · `$bindable` ·
  `$effect*` · `$inspect` · `$host` are named and stay calls. `onMount` and `onDestroy` are imports
  from `svelte`, so they are not runes. Runes are read in components and in `*.svelte.ts` / `*.svelte.js`.
- `TYPESCRIPT_AST_VOCABULARY` adds `state` to the node types and `writes` to the edge types, as
  `writes: (DEPENDS, REACHES)`. A shard minted before this carries no `writes` and answers as it did.
- A top-level declarator or a class field whose value calls a state rune is a `state` node,
  contained by its module or class.
- Every assignment, compound assignment and `++`/`--` in a rune file is a `writes` label from the
  function, method or component-or-module top level doing it. `x.a.b` and `x[0]` write `x`, and
  `this.count.n` writes `this.count`. A name the enclosing function rebinds (a parameter or a local)
  is skipped. The resolver binds the label as it binds a call: local, `this.` or import.
- The shadow is lexical (`_writes_in`). A function adds its parameters and hoisted `var`s, a block
  its own `let`/`const`/class/function declarations, a `for` its loop variables and a `catch` its
  parameter, each for its own subtree only. A destructuring assignment (`[a, b] = [b, a]`,
  `({ count } = …)`) writes each element, and a bare `for (x of …)` writes `x`.
- A `function` or an object method rebinds `this` and a named function expression binds its own
  name, so `this.count = 1` inside `forEach(function () {…})` or `{ m() {…} }`, and `count = 8` inside
  `function count() {…}`, write nothing. An arrow keeps the enclosing `this`.

| check | result |
|---|---|
| the ruled fixture | `scratchpad/rune`: `graphy blast Carousel.activeIndex` → `dependents=2`, `Carousel.select` (line 11) and the component through `$effect` (line 7). The function whose parameter shadows the name is absent. `blast Counter.count` → `Counter.inc` by `this.count++`; `descend select` reaches `settings_svelte.settings` across the import. `draw --symbol`, `explain` and `check` answer over a state node |
| a real Svelte 5 codebase | `sveltejs/svelte.dev`, shallow clone, `graphy eat . --no-provision`. `packages/repl`: 46 files, 0.23 s, 51 state nodes, 75 write labels, 38 bound (37 onto state, 1 onto a setter method, a true write). `apps/svelte.dev`: 141 files, 0.29 s, 65 state nodes, 95 write labels, 58 bound, all onto state. 12 bound edges sampled at random against their source lines: all true writes (`this.#files = …`, `inited = true`, `modal_text = …`). The unbound labels sampled are plain `let`/`const`, `$props` destructures and plain class fields |
| no change where there are no runes | hono `1174 nodes / 4596 edges`, express `69 nodes / 398 edges`, the same as before: the write path runs only in rune files |
| the floor tests | `test_GREEN_a_rune_is_state_and_every_write_to_it_is_an_edge_bound_through_scope` (state nodes and lines, `writes` by local · `this.` · import, a shadowing parameter excluded, blast and descend at the surface); `test_GREEN_a_write_is_bound_through_lexical_scope_and_destructuring_is_a_write` (the review's specimens, exact set). Both are red on the #85 component commit's adapter (dbb92e0 here, 7acac09 on the public repo), which mints no writes; the second was written after the lexical rewrite, so its red against the first rune version is the review's repro, not a stash. `test_doors`' equivalence test names the one declared addition, `writes` |
| the floor · the gate | `cd engine && ../.venv/bin/python -m pytest -q` green · `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` |
| the adversarial review, round 1 | a cold subagent told the card. **VERDICT: REVISE**, two blockers. B1: writes bound by name through scope holes (a block `let`, a `for` variable, a `catch` parameter shadowing a rune, at a component's top level and inside a function) → the lexical shadow above, floor test. B2: destructuring and a bare `for … of` target missed, so blast undercounted → pattern leaves and `for` targets above, floor test. CHANGELOG drift → regenerated. Also re-run: `draw --check`, `pillars`, `recon`, `showcase` and the MCP `blast` tool answer over state nodes; `fold_relations` folds a TypeScript lane with `writes` beside a Python lane and beside an old TypeScript shard |
| named, not read | a write label binds to whatever node the resolver finds, state or not: `helper.cache = 1` writes the func `helper`, `api.x = 3` the module. 95 of 96 bound writes across the two real packages land on state, and the one that does not is a true write to a setter. Filtering by node type in the resolver would be a door reading the vocabulary. **Ruled by the operator (2026-09-14): accepted** — "accept writes onto non-state". Also not read: state local to a factory function (`function createX() { let c = $state(0) … }`), a destructured `let { a } = $state(…)`, arrow-function class fields, `$props`/`$bindable` as state, `bind:value` in the template, `delete obj.n`, Svelte 4's `$:`, a class `static {}` block, a default-parameter expression (`(x = count++) => x`), a second declarator after a function one (`const a = () => 1, b = count++`), and template event handlers (`onclick={() => count++}`). One wrong edge is named rather than fixed: a `static` method's `this.count = …` binds to the instance rune (0 `static` in svelte.dev's rune files) |
| the adversarial review, round 2 | a cold subagent told the card. **VERDICT: REVISE**, one blocker. B1 and B2 re-checked fixed on round 1's own specimens; done lines 1–4 GREEN; performance fine (a 3,000-function, 368 KB component 0.34 s; a function nested 1,500 deep 0.41 s). B3: the lexical walk descends into function expressions, which the calls path never did, so `this` inside a `function` or object method and a named function expression's own name bound to state → rebound above, three lines added to the scope floor test. The svelte.dev write sets are identical before and after. The sha citation named only the public repo's sha → both named. The missed writes above → named, rare |
| the adversarial review, round 3 | a cold subagent told the card. **VERDICT: SHIP**, DONE BLOCK GREEN. Line 3 was re-checked on a fresh eat of `apps/svelte.dev`: `blast …app_context.get_app_context` → `dependents=3`, the three `.svelte` callers a grep finds. B3 was confirmed fixed on round 2's specimens, round 1's reproduced unchanged, the class-body exception judged right, the six svelte.dev numbers re-derived. F1, a static method's `this` → named above, non-blocking |

## 123 · A DOC LANE DECLARES ITSELF — `explain … DOCS` pinned two schemes (`scrape` · `history`) and three relations in `cross_substrate.py`, so a client's placed skills shard, 67 `governs` edges admitted by converge and answerable through `walk` and `estate`, appeared under DOCS zero times. The doc lane now declares its relation in its own PROVENANCE, the rebuild carries it into the scheme index's `_meta`, the build folds it into the store, and `explain` admits the declared schemes and relations beside the defaults (2026-09-14 · graphyos issue 86)

**The change.**

- `cross_substrate.load_doc_declaration(index)` reads `_meta.doc_schemes` · `_meta.doc_relations` (the
  declared half, sorted; `{}` when absent). `doc_vocabulary(declared)` unions it with `DOC_SCHEMES` ·
  `DOC_EXPLAINS`: a tenant that declares a skills shard keeps its history exchanges, and one that
  declares nothing answers exactly as it did. `DOC_EXPLAINS_SEED_ONLY` (`mentions`) is unchanged.
- `federated_store`: `compile_store` stamps the declaration into the store's meta (`doc_vocabulary`),
  `SQLiteStore` and `ShardStore` expose it as `doc_declaration`, and `explanations_from_store` reads it
  — a door reads the store, never the index. The declaration is hashed into the input digest and the
  store's generation only when one is present, so a declaration added or withdrawn after a build reads
  STALE through `open_for` and `check`, and an undeclared roster keeps every digest and generation it had.
- `cli._scheme_index_from_ring` (the index `eat` and `rebuild` write): a lane whose PROVENANCE says
  `vocabulary.doc_relations: [edge types]` adds those relations and the schemes it owns to `_meta`
  (`cross_substrate.derive_doc_declaration`), each lane's schemes read from its shard
  (`smash.shard_schemes`), never from an index row; the lanes compared, at index write and at build,
  are every `<slug>_graph` shard in the data home (`federated_store._shard_lanes`) — never the index's
  row keys, the descriptor's spelling of its lanes or the roster a door loaded. A lane is hidden from
  the proof only by deleting its shard, and then no store loads it. Lanes that all declare may share a
  scheme (a manuals lane and its restricted twin); a co-owner that declares nothing refuses. The store
  answers with what its LOADED lanes declare (`_doc_declaration(tenant, substrates)`): `_meta` must
  carry at least that (else the index is stale) and nothing no shard on disk declares (else it was
  written by hand), and a declaring shard the store never loads changes nothing. The index carries the declaration and the build
  proves it: `compile_store` re-derives it from the lanes' PROVENANCE and shards and refuses
  (`StoreError`) when `_meta` disagrees, so a doc scheme written into `_meta` by hand, or a declaring lane under an index
  that never carried it, refuses by name.
- `mesh_federation_gate`: a heal and an observe rewrote `_meta` to the registry digest alone, dropping
  `standard` and now the doc keys; both merge into the existing `_meta` instead.
- `refresh.py` writes its own index from a package ring and carries no doc lane: untouched.
- A doc scheme is one the declaring lane owns alone: a lane that declares `doc_relations` and also
  carries another lane's ids refuses (`DocDeclarationError` → `RebuildError` · `EAT REFUSED`, exit 2)
  naming both lanes and the shared scheme. A declaration is a list of non-empty strings or one string;
  anything else refuses by name at index write, and a malformed hand-written `_meta` refuses the build
  (`StoreError`) and reads COULD-NOT-TELL in `check`. A seed is never its own DOCS endpoint.

| check | result |
|---|---|
| a real repo, a real doc lane | a clone of this repo; `rebuild.rebuild` with `Lane.mint("graphy", …)` over `engine/graphy` and `Lane.placed("skills")`, a shard emitted from the 21 real `SKILL.md` files (`.claude/skills` · `staging/skills`), each skill `governs` the `graphy://module/graphy.<stem>` whose exact `` `<stem>.py` `` it names and which exists on disk: 21 nodes, 8 edges. Undeclared: `explain graphy.sugiyama` → `DOCS: none`, `_meta` carries no doc keys. Declared (`doc_relations: ["governs"]`): `_meta.doc_schemes ["skills"]` · `doc_relations ["governs"]`, `explain graphy.sugiyama` → `DOCS (DOC_EXPLAINS endpoints, 4)`, `hop1 governs skills://skill/skills.claude.frontend_review` and three at hop 3. Rebuild 1.1 s, explain 0.02 s through the CLI. The script: `scratchpad/p86/run.py <clone> silent\|declare` |
| the floor tests | `test_rebuild::test_GREEN_a_doc_lane_that_declares_its_relation_is_listed_under_explain_docs[False,True]` (PROVENANCE → index → store → the CLI door through the counting proxy); `test_doors::test_GREEN_a_declared_doc_scheme_reaches_explain_and_the_defaults_still_stand` (both stores; the history exchange stays); `…_the_doc_declaration_moves_the_input_digest_only_when_declared`; `…_a_healed_scheme_index_keeps_what_its_writer_declared`. All four declared cases are red on a266ff3's engine |
| the floor · the gate | `cd engine && python3 -m pytest -q` green · `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` |
| the adversarial review, round 1 | a cold subagent told the card. DONE BLOCK GREEN, **VERDICT: REVISE**, two blockers. B1: `"doc_relations": "governs"` and `["governs", 3]` dropped silently (`CHECK OK`, `DOCS: none`), and a hand `_meta.doc_schemes: 5` crashed `build` → a bare string is one relation, anything else refuses by name, floor tests `test_RED_a_malformed_doc_declaration_refuses_by_name_and_a_bare_string_is_one_relation` · `test_RED_a_malformed_hand_declaration_refuses_the_build_and_a_seed_never_explains_itself`. B2: a skills lane carrying a stub `graphy://module/graphy.sugiyama` owned `graphy`, so `doc_schemes` became `["graphy","skills"]` and `explain graphy.sugiyama` listed itself, `graphy.draw` and `graphy.showcase` as DOCS → the sole-owner refusal and the seed guard above, `test_RED_a_doc_lane_carrying_another_lanes_scheme_refuses_naming_both`; the reviewer's `probe.py` on a fresh clone: the string case lists the 4 skills, the stub case refuses naming `skills` and `graphy`. The guard's test is red with the guard removed. Named, not fixed here → graphyos #106: the history producer still declares nothing, so the constants are narrowed rather than gone; `--build-index` writes no declaration; PROVENANCE is not a store input digest. Also named: declared relations are not seed-only, so a skill reaches a module at hop 3 through its neighbours, as `governed_by` always has |
| the adversarial review, round 2 | a fresh subagent handed the ledger. DONE BLOCK GREEN; line 3 byte-identical (explain · blast on three symbols, generation `89aaceb6ed9033df`) between a266ff3's engine and this one, and `check` on the real graphy and fastapi tenants still fresh. B1 and B2 confirmed fixed on round 1's specimens; a malformed hand `_meta` refuses in explain · blast · build, exit 2, and check exits 1. **VERDICT: REVISE**, one blocker. B3: `_meta.doc_schemes ["graphy"]` · `doc_relations ["imports"]` written by hand → BUILD OK, CHECK OK, `explain graphy.sugiyama` DOCS 75, the code lane's own modules. B2's class through the other door: the sole-owner rule lived only in the writer → the build re-derives and refuses a disagreement (above); the reviewer's `hand.py` on a fresh clone: `BUILD REFUSED` and `EXPLAIN REFUSED` naming the carried and the declared vocabulary, `check` exit 1; floor test `test_RED_a_hand_written_doc_declaration_no_lane_declares_refuses_the_build` (a hand code scheme, a widened scheme list, a declaring lane under an unstamped index). The seed guard's test now walks skill → skill → back, red with the guard removed. The refusal's advice now reads "the doc lane carries no other lane's ids". Named onto #106: one lane's declared relation applies to every doc scheme, `history` included |
| the adversarial review, round 3 | a fresh subagent handed the ledger. DONE BLOCK GREEN; line 3 on every real tenant: fastapi (10 lanes) · sqlalchemy (3) · hono (2) · express (63) · graphy (7) compiled with this engine to the live generations, `doc_vocabulary {}`, the proof 0.4–1.8 ms; a fresh `eat` of pallets/itsdangerous with its history shard → `DOCS: none`, no doc keys. B3 confirmed fixed. **VERDICT: REVISE**, two blockers. B4: a declaration added or withdrawn after a build → `CHECK OK … store fresh` and the old DOCS, because `open_for` falls back to the generation, which did not carry the declaration; this record's "a changed declaration reads STALE" was false → hashed into the generation (above); the reviewer's `probe.py declare_after` · `unstamp_after`: `CHECK RED … STALE`, `EXPLAIN REFUSED`, then `BUILD OK`, `CHECK OK`, DOCS 4; floor test `test_RED_a_declaration_changed_after_the_build_reads_stale_through_open_for`, red with the generation term removed. B5: B3's class through the index rows: `graphy.own = []`, `skills.own = [graphy, skills]` → BUILD OK, code under DOCS → ownership read from the shards (above); `probe.py rows_show`: `BUILD REFUSED`, `EXPLAIN REFUSED`; floor test `test_RED_index_rows_edited_to_hand_a_code_scheme_to_the_doc_lane_refuse_the_build`. Rounds 2 and 3 blocked on one class, a proof that read a hand-editable input; B5 closes the last such input the derivation reads. Named onto #106: a PROVENANCE edited after a build without an index rewrite is not seen until the next build |
| the adversarial review, round 4 | a fresh subagent handed the ledger and asked whether any hand-editable input still feeds the proof. DONE BLOCK GREEN; line 3 on the five real tenants: every live-shard generation equals the served one, `doc_declaration {}`; `derive_doc_declaration` 0.3–1.9 ms undeclared, `shard_schemes` 0.01–0.10 s over a declaring roster. **VERDICT: REVISE**, one blocker. B6: the lanes compared were the index's row KEYS — the `graphy` row deleted by hand and a skills shard carrying stub `graphy://` ids → BUILD OK, CHECK OK, `explain graphy.sugiyama` DOCS 6 with code modules → the descriptor's `build_lanes` (above); `probe.py droprow`: `BUILD REFUSED` · `EXPLAIN REFUSED` naming `skills` and `graphy`, `check` exit 1; `ghostlane` (a declaring row outside the roster): BUILD OK, DOCS 4; b3 · rows_show · declare_after unchanged. Floor test `test_RED_an_index_row_removed_for_the_code_lane_does_not_hide_its_ownership_from_the_doc_proof`, red with the row keys restored. The reviewer's answer: with B6 closed, the lanes come from the descriptor, ownership from the shards and the declaration from PROVENANCE, and what remains is #106's set. Judged lawful: a code lane's own PROVENANCE declaring `imports` a doc relation lists its modules under DOCS — a producer declaring its meaning |
| the adversarial review, round 5 | a fresh subagent handed the ledger. DONE BLOCK GREEN; B1–B6 still fixed on their specimens. **VERDICT: REVISE**, two blockers, both from round 4's `build_lanes` choice. B7: a tenant built from flags (`cli_tenant`, no lanes) — `graphy.query --mesh-set … --materialize` and `python -m graphy.federated_store --mesh-set` — crashed with an uncaught `StoreError` on a legitimate declared tenant, the proof finding no lane. B8: the store cleans a descriptor key (`journal._names`), the proof only stripped `_graph`, so `"graphy_graph/"` or `" graphy_graph"` loaded the lane and hid it from the proof → BUILD OK, CHECK OK, code under DOCS 6. Rounds 4 and 5 are one class, the proof's lanes not the store's lanes, and the round closes it rather than the spelling: the proof reads every shard on disk (above); `federated_store.main` refuses a `StoreError` by name, exit 2, and `query --materialize` returns usage. Re-run: `keyprobe.py` with `graphy_graph/` · ` graphy_graph` · `graphy_graph`: BUILD REFUSED, EXPLAIN REFUSED; the query repro lists `--governs--> [skills] hops=1 skills.claude.frontend_review`; droprow · b3 · rows_show · declare_after unchanged; `ghostlane` (a copy of the skills shard as `ghost_graph`) now refuses naming `ghost` and `skills`. Floor test `test_RED_the_doc_proof_reads_every_shard_on_disk_not_a_door_or_a_descriptor_spelling`, red on round 4's proof |
| the adversarial review, round 6 | a fresh subagent handed the ledger. Line 3 GREEN: the undeclared proof 9.8 ms on express (63 lanes), 1.9 ms on a 30-lane client repo, `check` fresh on fastapi · sqlalchemy · hono · express; every real data home's `*_graph` dirs equal its roster. **VERDICT: REVISE**, two blockers, both from round 5's shards-on-disk choice. B9: the client repo rosters `manuals_ast` and `manuals_ast_restricted`, both owning scheme `manuals_ast` — the issue's own manuals case — and two declaring lanes refused against each other (`twin.py twin_rostered`) → lanes that all declare may share a scheme (above); floor test `test_GREEN_two_doc_lanes_that_both_declare_may_share_their_scheme`, red with the declaring-twin exemption removed. B10: an unrostered `other_graph` declaring `cites` put a rostered lane's `cites` edge under DOCS, BUILD OK, CHECK OK (`twin.py stray_decides_with`) → ownership reads every shard, the answer counts only the loaded lanes (above); floor test `test_RED_a_declaring_shard_the_store_never_loads_changes_nothing`, red with the vocabulary read over the disk. `compile_store` stamps `shard.doc_declaration` rather than proving twice. Re-run on a fresh clone: `p86/run.py silent` → DOCS none, `declare` → DOCS 4, rebuild 0.7 s. Named, loud: an empty `*_graph` dir in the data home of a declaring tenant refuses its build (eat and rebuild remove such dirs) |
| the adversarial review, round 7 | a fresh subagent handed the ledger. **VERDICT: SHIP**, DONE BLOCK GREEN, zero blockers. Line 3: the silent roster compiles to `89aaceb6ed9033df` under a266ff3's engine and this one; a store over the code lane alone of a declared tenant is `e65ef66fa5c20a63`, as undeclared; fastapi and hono `check` fresh. B9 and B10 hold and their tests are red without their fixes; B3–B8 re-checked under the loaded-lane rule (hand `_meta`, edited rows, a declaration added after the build, a deleted row with stub ids, descriptor spellings). New hunts held: a `--mesh-set` subset without the doc lane answers 0 explanations with no refusal and the undeclared generation; one twin loaded lists only its own skill; a hand `_meta` borrowing an unloaded stray's declaration passes the gate and changes nothing, because the answer is what the loaded lanes declare. Named, loud: a stray `*_graph` with a malformed declaration, or a declaring stray sharing a code lane's scheme, refuses a tenant's build; a `_meta` change reads STALE on a store that never loads the doc lane |

## 124 · CLEAR THE SLOP — `/` stood at 95% (1.5G free) and review round 6 of #86 had died once on a full disk: session scratchpads holding dead review clones, five hand-built galleries, pytest trees, three August id maps in `/tmp`, the apt cache and a 76M journal. The box is evacuated by a census that names every candidate before it goes, and `sweep.py` keeps the repeat offenders gone: SessionEnd runs it, the gate proves its rules (2026-09-14 · graphyos issue 107)

- `sweep.py` (repo root, stdlib): every root and candidate must be a real directory this user owns
  (`lstat`: no symlink, `st_uid`), or it is never looked at. The census names every session scratchpad (`/tmp/claude-<uid>/<project>/<uuid>/`),
  pytest run tree and `/tmp/graphy-gallery*` with size, age and why; `--apply` removes the DEAD rows. KEEP when
  a process holds a file open under it or runs there (read from `/proc`, no lsof), when its session's Claude Code
  process is registered and alive (`<home>/sessions/<pid>.json`) or a live command line names its id (the
  homes are `~/.claude*`, `$CLAUDE_CONFIG_DIR` and every live process's own), when `pytest-current` points at it, or when
  its newest file or its transcript moved inside `--min-age` (24 h). A directory no rule names is never a
  candidate. A held path matches the candidate's own spelling and its realpath. `--selftest` proves each rule on
  a fixture and runs in `standalone_check.sh`; each of 20 guards removed in turn turns it red (owned_dir · the
  uid · the claude root · a project dir · the pytest root · realpath · the separator · holders · the registry ·
  the pid alive · the command line · `$CLAUDE_CONFIG_DIR` · a process's environ · pytest-current · newest file ·
  directory mtimes · transcript · the session-id and pytest-run names · the gallery glob) — each guard replaced
  by its unguarded spelling and `--selftest` re-run, twenty times. A candidate another sweep removed mid-census is skipped, never a traceback. The roots swept are the
  realpaths of `/tmp` and `tempfile.gettempdir()`, named on the closing line. A session idle past the age with no
  process and resumed later has lost its scratchpad: a scratchpad is temporary, and the docstring says so.
- Where it runs: `.claude/settings.json` SessionEnd → `sweep.py --apply --quiet`.
- Processes: zero zombies (`ps -eo stat | grep -c '^Z'` → 0). Every `claude` has a tty; the two without one
  (a 25-day `vite dev` whose parent `sh` is alive; a `uvicorn` holding its watchdog lock) are not orphaned
  by the rule, so nothing was killed.

| check | result |
|---|---|
| before | `df -B1M /` 2026-09-14T02:49Z → 27212M used · 1464M free · 95% |
| the census, then the sweep | `python3 sweep.py --min-age 6` → `python3 sweep.py --min-age 6 --apply --quiet` → `SWEEP OK: 67 removed · 1.8G freed · 25 kept` |
| one-shot, listed and unheld first | `/tmp/{node_meta,idmap,cand_map}.json` (590M, 2026-08-18) · `/tmp/discover_shared*.json` · `/tmp/{b842_11,graphyos-0.2.2,graphyos-0.2.2-local,graphy-uv,np}` removed; `sudo apt-get clean` (184M); `sudo journalctl --vacuum-size=16M` (76.2M → 16.0M, `journalctl --disk-usage`); `pip cache purge` (66 files) |
| after | `df -B1M /` → 24076M used · 4601M free · 84% (after the line-2 rows below) |
| the rest of line 2, item by item | old claude versions: `ls ~/.local/share/claude/versions` → one on disk (`2.1.270`); four deleted ones (2.1.251 · 2.1.263 · 2.1.267 · 2.1.269) still pin 827M because five live `claude` panes run from them (`for p in $(pgrep -x claude); do readlink /proc/$p/exe; done \| sort \| uniq -c`) — freed only by restarting those panes, the operator's (gated) · snap: `snap list --all` → no snaps installed · docker: `sudo du -xsh /var/lib/docker` → 208K · pip: `pip cache purge` then `rm -rf ~/.cache/pip/http-v2` → `du -sh ~/.cache/pip` 464K · uv: `rm -rf ~/.cache/uv` (7.5M) · npm: `npm cache clean --force`, then `~/.npm/_npx` (92M) kept — six live `chrome-devtools-mcp` run from it (`ps -eo args \| grep -c '[_]npx/.*chrome-devtools-mcp'`) |
| kept by rule | a scratchpad whose transcript moved an hour earlier (2.5G) — the SessionEnd sweep takes it once it is quiet |
| gated for the operator | `MARCH GATE: IRREVERSIBLE` posted on #107 and labeled `operator`: the home-directory tarballs, archives and non-git checkouts (`du -xsh ~/*.tar.gz ~/*archive* ~/*_runs ~/*_codex`), `~/.cache/ms-playwright` (700M, a download to come back), a `claude` stopped for 15 days on a live pane, and the five panes pinning 827M of deleted claude binaries — none deleted, none killed |
| the gate | `python3 sweep.py --selftest` → `SWEEP SELFTEST OK: 13 rule fixture(s) · 8 strays held (unnamed dirs · links to a session, a project, a claude root, a pytest root) · a foreign uid refused · a linked /tmp`, also under `TMPDIR=<a link>` · `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` |
| the adversarial review, round 1 | a cold subagent told the card. **VERDICT: REVISE**, three blockers. B1: §124 cited a gate comment #107 did not carry → posted and labeled `operator` (above). B2: line 2's claude versions, snap and regenerating caches unaccounted → the item-by-item row. B3: `candidates()` checked only children for symlinks and never the owner, so `/tmp/pytest-of-<user>` or `/tmp/claude-<uid>` planted as a link to a home directory had `pytest-N` and uuid dirs removed inside it, and a held file under the link's real path never matched (the reviewer's `sym/` fixture: 2 removed) → `owned_dir` on every root and candidate, the user from `pwd`, holders matched by realpath; fixtures for a linked session, a linked root, a foreign uid and a linked `/tmp`. N1: four guards whose removal left the selftest green (`PYTEST_RUN`, the child symlink, directory mtimes, the separator) → fixtures added, 13 of 13 red. N2: config homes read by a glob → `$CLAUDE_CONFIG_DIR`, every live process's own, and an id on a live command line keeps its scratchpad |
| the adversarial review, round 2 | a fresh subagent handed the ledger. B1 and B3 held on their repros (`r2/b3.py`); census 0.51 s under the 30 s hook. **VERDICT: REVISE**, three blockers. 1: five of its 20 mutants left the selftest green — the `/tmp/claude-<uid>` and project-dir owner checks (B3's own root: `r2/b3m.py` listed a linked victim with `--selftest` OK), the separator, and both N2 reads, so round 1's "13 of 13" overstated → fixtures for a linked claude root, a linked project, a prefix-sharing held path, a home named only by a process environ and one only by `$CLAUDE_CONFIG_DIR`; 20 of 20 red. 2: the claude-versions row was false — five panes run deleted binaries pinning 827M → the row names them, the gate comment carries them. 3: the census row's command omitted `--min-age 6` → written as run. Nit fixed: a candidate removed between listing and look is skipped |
| the adversarial review, round 3 | a fresh subagent handed the ledger. Round 2's three held (20/20 mutants red, the versions row true, the `--min-age 6` command); the selftest green as root, under `env -i`, with `CLAUDE_CONFIG_DIR` preset and restored. **VERDICT: REVISE**, two blockers. 1: `TMPDIR=<a link> python3 sweep.py --selftest` exited 1 — `pytest-current` (a real path) compared to the candidate spelled through the link, so the live pytest tree lost its protection (`r3run/pc.py`) → matched against both spellings, the fixture's scratch resolved, a pytest-current fixture through a linked /tmp, red with the old comparison. 2: the gate row's selftest line was stale → written as it prints. Notes taken: the hook sweeps `/tmp` and the temp dir both and names them; this record no longer cites a session scratchpad script |
| the adversarial review, round 4 | a fresh subagent handed the ledger. **VERDICT: SHIP**. Round 3's two held: the selftest OK under `/tmp`, `TMPDIR=<a link>` and `TMPDIR=<a scratchpad>`; `pc.py` keeps `pytest-2` ("pytest-current points here"); the old comparison restored is red; 20 of 20 mutants red; `review.py` OK, `release.sh --check` OK. Named, not blocking → graphyos #109: one root nested in the other double-counts the printed totals; the two-roots derivation has no fixture; an unreadable project dir aborts the sweep with a traceback. The sweep's gate lines now sit above review.py's comment block |

## 125 · THE LOOP DOES NOT LIMIT ITSELF — the march held #83, #84, #85 (twice), #86 and #107 on its block cap within seconds, each while a background reviewer was running, and #107 closed inside that hold and armed nothing: the hold branch looked only for a gate line. The cap now counts stalls alone, a rung closed during a hold marches the next, the hook's floor runs in the gate, and the sweep runs from the user crontab rather than a session (2026-09-14 · the operator's ruling)

- The diagnosis, from `.claude/recovery/march.log`: `02:52:30 blocked stop on issue 107 (1/4)` … `02:52:49 (4/4)`, `02:52:51 hold on issue 107: block cap` — 19 s, review round 1 in flight; the same four-in-seconds shape at 23:45:49–53 (#85) and 01:55:59–01:56:12 (#86). `march.py status` after the close: `phase: hold`, `issue_live_state: CLOSED`, `watcher_alive: false`.
- `march.py` `transcript_facts`: a Stop while the session's own background work is pending — launched per the harness's structured `toolUseResult` (`status: async_launched` → `agentId`, or `backgroundTaskId`), not yet named by a `<task-id>` notification — is allowed and counts nothing; a turn that called a tool since the last block resets the count; a text id in a tool's output or a reseed tail launches nothing. `cmd_stop_hook`'s hold branch: a stall hold whose issue is now closed runs `unblock` and `advance`. A disarm still holds.
- `CLAUDE.md` opens with the operator's law: a truth-seeking agent, prose not trusted, code king; graphyos a singular-context recursive self-improving mechanism, and a limit on the loop a defect to fix in code.
- The operator's gated march change (MARCH GATE for real gates, the four questions, the review rounds in rung-discipline §2.6, `test_march.py`) lands in this commit by the operator's ruling.
- The sweep leaves the session: `17 * * * * /usr/bin/python3 ~/graphy/sweep.py --apply --quiet >> .claude/recovery/sweep.log` in the user crontab (`crontab -l | grep graphy/sweep.py`), the SessionEnd hook kept as a second trigger.

| check | result |
|---|---|
| the hook's floor | `python3 -m pytest -q .claude/hooks/test_march.py` → 19 passed; new: `test_a_wait_on_a_live_background_review_never_counts_toward_the_cap` (ten stops, blocks 0, still working) · `test_a_notified_task_is_no_longer_pending_and_a_quoted_id_launches_nothing` · `test_a_turn_that_called_a_tool_resets_the_cap` (a true stall still holds) · `test_an_issue_closed_during_a_cap_hold_marches_the_next_rung` · `test_a_closed_issue_after_a_disarm_arms_nothing` · `test_a_background_shell_is_pending_until_notified` |
| each fix removed | pending → `if False` : 2 failed · the progress reset → `pass` : 1 failed · closed-during-hold → `if False` : 1 failed |
| this session's transcript | `transcript_facts` → pending `set()`, 66 tool calls (the text-scan draft read two ids out of a grep's output as pending; the structured read does not) |
| the gate | `standalone_check.sh` runs the hook's floor → `march OK` · `GRAPHY_STANDALONE_OK` |
| the review | none: committed by the operator's ruling ("build on it … commit and push") |

## 126 · THE HOUSE VOCABULARY IS FOLLOWED BY CLASS — a production tenant measured on graphyos 0.2.4: `blast <a schema table>` answered dependents=0 and `descend <its reader>` reached no schema node, although `adj` held the `reads_table` edge; `contains` 18,094 · `reads_table` 24 · `sourced_from` 9 · `indexes_on` 2 on the schema side, the doors following none of the last three. The fold that answers it (#68, bb5e256) landed after the 0.2.4 release commit (92bc100) and is in no published wheel; on main a placed lane's declared relations drive both doors through the supported rebuild, and an undeclared type is named, never followed. Also: the march has no cap (2026-09-14 · graphyos issue 110)

- The version fact: `git log --oneline | grep -n "#68\|0.2.4: the published"` → bb5e256 at 27, 92bc100 at 28 (newest first); `pip download graphyos==0.2.4 --no-deps` and `grep -c "fold_relations\|def relations_in" graphy/federated_store.py` → 0. The tenant's measurement is 0.2.4's hardcoded `BLAST_RELATIONS`, not a gap on main.
- The engine is unchanged by this rung. What the acceptance case needs on the house side: the placed lane's own `PROVENANCE.json` declares `vocabulary.relations` for its types (`reads_table`, `sourced_from`, `defines_table`, `defines_column`, `resolves_to`, `derived_from`, `joins_on` → `depends`, plus `reaches` where a descent should follow), and the engine it runs is past bb5e256.
- The pin: `tests/test_rebuild.py::test_GREEN_placed_lane_declared_relations_drive_blast_and_descend` — a minted `core` lane and a placed schema lane declaring `reads_table` and `sourced_from` as `depends`+`reaches` with `indexes_on` undeclared, through `rebuild.rebuild` and `cli.main`: `blast <table>` names the reader and the view, `NOT WALKED: indexes_on 1`, the index not among the dependents; `descend core.mod.run` reaches the table.
- The loop (5bf3c4b, the operator's ruling "remove both limits"): §125's stall cap and the watcher's kick cap are gone from `march.py` — an open issue with no background work pending is blocked on every stop, and the watcher kicks until the fresh context acks; `MARCH_MAX_BLOCKS` and `MARCH_MAX_KICKS` no longer exist. `test_a_malformed_gate_never_holds_the_loop` and `test_a_turn_that_called_a_tool_resets_the_stall_count` (twelve stalls, twelve blocks, still working) replace the two cap tests.

| check | result |
|---|---|
| the done test | `cd engine && ../.venv/bin/python -m pytest -q -k placed_lane_declared_relations_drive_blast_and_descend` → 1 passed |
| the fold removed | the compile's `RELATIONS_META` stamp → `"{}"` : 1 failed, printing `dependents=0` — the tenant's 0.2.4 answer, byte for byte in shape |
| the hook's floor | `python3 -m pytest -q .claude/hooks/test_march.py` → 19 passed |
| review round 1 | SHIP (cold): 0.2.4 wheel confirmed without the fold; six monkeypatched mutations each fail on an assertion (follow-all, fold removed, descend default, blast default, `sourced_from` dropped, notice suppressed); the five omitted house types pass both doors; a placed declaration conflicting with a minted lane refuses by name. Folded in: the test pins `hop1=2`; `march.py`'s stale "cap" comment. Filed: #112 (the changelog lists post-release sections under 0.2.4) · #113 (a declared relation the census never mints is silent). Observed, not filed: declaring any relation replaces the door defaults for the whole store, named by NOT WALKED on a pre-#68 shard |

## 127 · A DOOR REMEMBERS — only `walk` recorded: `blast` and `descend` printed `DOOR: reads=` and stored nothing, so every repeat paid the store again, and `graphy traversals` listed walks but could query none. Both doors now land generation-keyed parquet under `traversals/<gen>/doors/`, a repeat of the same (seed, depth) answers from the rows with zero reads and renders byte-identically, and `traversals --seed | --target` recalls every stored row, walks and doors alike, in one scan (2026-09-14 · graphyos issue 111)

- `doors.descent_of` · `doors.blast_of`: the answer built from what the walk found (reached in BFS order, the primitive set, the declined counts and classes), shared by the live door and the recalled one, so the two cannot drift.
- `traversal.door` · `store_door` · `load_door` · `stored_doors` · `recall`: one parquet per (door, seed, depth) with columns door · seed · depth · ord · hop · node · via_src · relation · owner · primitive · generation, the declined counts in the receipt; a receipt that does not describe its (door, seed, depth, generation), or a row count that disagrees with it, refuses. The key carries `traversal.vocabulary(store)` — a digest of the folded relation vocabulary, the families each door admits, `DOOR_FORMAT` and `traversal.rules_digest()` (the source digests of every module in `traversal.RULE_MODULES` — the import closure of `RULE_ROOTS`, verified by `review.py` `cache-key-closure` — each pinned by `_shared.source_sha` when the module is imported, so an upgraded engine never serves the old engine's answers and a long-lived process keys by the code it runs; an unreadable source runs the door live, stores nothing and refuses a recall by name) — because the generation hashes nodes and edges only: a lane that re-declares a relation over the same shards keeps its generation and must never keep its stored answers; `recall` admits only door rows stored under the live vocabulary. Door files sit in `doors/`, outside the walk glob, so `stored` and `replay` read walks exactly as before. No duckdb: the door runs live and says `TRAVERSAL SKIPPED`.
- The CLI: `descend` · `blast` print `TRAVERSAL: source=live|store reads=N stored=…` under the unchanged `DOOR:` line, `--no-store` lands nothing; `traversals --seed <symbol> | --target <symbol>` resolves through `doors.resolve` and prints each stored traversal's hops, `reads=0`. The MCP `descend` · `blast` tools land and recall the same rows.

| check | result |
|---|---|
| the done test | `cd engine && ../.venv/bin/python -m pytest -q -k blast_and_descend_record_and_recall` → 1 passed: the repeat reads `source=store reads=0` with the body byte-identical, the recalled Blast renders equal to a fresh live one, the primitives equal, recall by target and seed across walks and doors, a torn receipt refuses |
| the production run (FastAPI tenant, generation 5ddda285194b8126) | `graphy descend fastapi.routing.get_request_handler` → reached=77, `reads=131` source=live 0.12s; again → `reads=0 source=store` 0.11s. `graphy blast fastapi.routing.APIRouter --depth 3` → reads=3 live, then `reads=0` store. `graphy traversals --target starlette.concurrency.run_in_threadpool` → 1 traversal (the descent) `reads=0`; `--seed fastapi.routing.get_request_handler` → 78 rows `reads=0`, 0.11s |
| the floor · the gate | `python3 -m pytest -q` green · `standalone_check.sh` → `GRAPHY_STANDALONE_OK` |
| review round 1 (cold) | REVISE — a stored door answer ignored the declared relation vocabulary: `_census_store` blasted undeclared, `reads_table` declared over the same shards, the generation unchanged (`ecfe8b0a6dada9c7`), the live blast answered dependents=1 and the door replayed 0 from the store. Walked: `blast federated_store._generation_digest` → `ShardStore.__init__` · `from_mesh`; hashing relations into the generation would move every tenant's generation and every arm stamp, so the door key carries the vocabulary instead. `test_RED_a_redeclared_relation_is_never_recalled_stale` fails `store == live` with the key reverted. Observations folded: `load_door` escapes its path and names an unreadable parquet as a refusal; a `'` in a data home's path through `_write_parquet`/`load_walk`, and recall printing a descend's edge backwards, carried in the commit message |
| review round 2 (the ledger) | REVISE — the round-1 fix held on its specimen through the CLI and MCP (a new `-v` stem, dependents=1, recall by target the new blast only) and the §127 FastAPI numbers reproduce; the blocker was the same class through the engine hole: a door rule changed by an upgrade (`_bfs` patched) left the store answering the old dependents=1 against a live 0, keyed by nothing but a comment on `DOOR_FORMAT`. Fixed: `rules_digest` folds into `vocabulary`; the RED test's patched rules answer `source=live`, and fail `store == live` with the digest held constant. The listing tags a door answer under an older vocabulary `stale-vocab`. Eliminated: a relations-only change is invisible to `open_for` until `build` (#68's staleness check, live and stored agree — a board issue), the MCP `stored` wording |
| review round 3 (the ledger) | REVISE — both prior blockers held on their specimens (each RED assertion fails with its fix mutated away); the blocker was the same class through a third hole: `rules_digest` read the files from disk at the first door call, so a process that imported the engine (the MCP server `.mcp.json` starts) and saw `doors.py` rewritten before its first blast ran the old `_bfs` under the new key, and a fresh process then read that answer `source=store`. Fixed: `SOURCE_SHA` pinned at import in the four modules; the RED test rewrites every read_bytes after import and requires the same digest (a lazy disk read fails `'410e…' == 'f164…'`). `cross_substrate.py` joins the hashed set (orientation, `WIRE_BUCKET`). Eliminated: a zipimport reads no source (named: live, nothing stored), `sys.modules[__name__]` for the self-import |
| review round 4 (the ledger) | REVISE — all three prior blockers held on their specimens (each fix mutated away turns its RED assertion red; the fifo-driven upgrade keyed the old process by the old bytes). The blocker: the cache cost the answer — a read-only home (0555) made `traversal.door` raise PermissionError after the blast was computed, `BLAST REFUSED` exit 2, and a duckdb IOException (disk full) is no OSError. Fixed: a failed `store_door` (OSError · duckdb.Error) returns the live answer with `TRAVERSAL SKIPPED: the traversal store could not be written`; `test_RED_a_door_answers_when_its_store_cannot_be_written` fails with the guard removed. `rules_digest` combines the pins on every call (a reload moves it). Eliminated: `walk` on a read-only home crashes (pre-existing), the pin's import window, recall over-refusing on zipimport |
| the class, dogfooded | three rounds, one class — a stored answer keyed on less than its inputs — now a door: `traversal.RULE_ROOTS` · `RULE_MODULES` (the 11-module import closure of doors and traversal, each pinning `SOURCE_SHA = source_sha(__file__)`), and `review.py` `cache-key-closure` refuses a module the roots import that the key omits, a stale declaration, and an unpinned member. `python3 review.py --selftest` → `cache-key-closure red=3 green=0`; with `graphy.cross_substrate` dropped from `RULE_MODULES` on the live tree it names round 3's hole by file and line. The card gains class 12 and a ⑤ specimen |
| review round 5 (the ledger) | REVISE — R1–R4 held (the read-only home answers through `mcp.Doors` too; a runtime `sys.modules` diff after a real blast and descend loads nothing outside the key). The blocker was the new door itself: `cache-key-closure` read top-level imports only, so a rule behind a lazy import in `doors.blast` (a scratch depthrule module, edited) served `source=store` 4 dependents against a live 2 with the check reading `[]`. Fixed: `_imports` walks every Import and ImportFrom (function bodies, `if`, handlers), resolves relative imports and adds parent `__init__`s; `RULE_EXEMPT` declares what the roots reach that bears no rule (`graphy` · `graphy.journal` · `graphy.smash`, each with its reason, verified as a set difference); selftest `red=5 green=0`; on a tree copy with round 5's lazy depthrule import the check names it by file and line. Round 4's blocker dogfooded too: `traversal.CACHE_WRITERS` and `review.py` `cache-write-guarded` (selftest `red=2 green=0`) — on a tree copy with `walk`'s guard stripped it names `traversal.py:304`; `walk` now answers on a read-only home (it crashed before this rung), and a damaged stored parquet is a cache miss answered live and rewritten. The routing law: rung-discipline §2.6 item 3 and the card's DISPOSITION make the battery the default home and refuse a card route that names no attempted check |
| review round 6 (the ledger) | REVISE — R4 and R5 held (the read-only home answers through `mcp.Doors`; the tree copy names depthrule and walk's stripped guard); the exemptions hold (smash reaches the door only through the doc declaration hashed into the generation). The blocker was the new check: `cache-write-guarded` credited `except (OSError, json.JSONDecodeError)` (duckdb's IOException on a full disk is no OSError), a handler that re-raises, a writer called from a def or lambda written inside the try, an `as` alias and a `partial` — each read `[]`. Widened into the same check: only non-re-raising handlers count, OSError needs a base `.Error` exactly (or Exception), a def · lambda · class resets the guard, every use counts (a call, an alias, a rebinding, a value passed on, `getattr(module, "name")`); selftest `red=7 green=0`; the reviewer's own probe of nine variants names all eight unguarded ones. `cache-key-closure` follows `importlib.import_module("graphy.x")` · `__import__` literals (`red=6`). Folded: a damaged stored walk is re-walked (it was a traceback, exit 1), a leftover `.json` feed from an interrupted write no longer breaks `stored` · `stored_doors`, the §127 prose names `RULE_MODULES` not four files |
| review round 7 (the ledger) | SHIP — R4 · R5 · R6 re-verified on their own probes (nine guard variants flagged, the read-only home answers through `mcp.Doors`, the lazy import named); no false positive over the live engine's two writer uses; `_cached_walk` swallows only `StoredUnreadable`, a receipt that misdescribes its key still refuses and `--replay` refuses a damaged past walk by name (exit 2); the re-walk and both leftover-feed guards each go red when mutated away. Eliminated, carried in the commit message: a receipt overwritten from outside with non-dict JSON raises in `load_door` · `load_walk`, and a duckdb read failing on permissions re-walks live |

## 128 · A REBUILD NO LONGER TAKES THE DOOR DOWN — the clear removed the served store, the descriptor and the ring, so `graphy mcp` refused `no compiled store` from the clear until build landed. The next generation is now built in a sibling `<substrate>.gen-<token>/` seeded from the served one and lands in one descriptor rename after build; the served data home is never written, so the door the plugin ships opens the last good store FRESH at every step, and a rebuild that fails or is interrupted discards its stage (2026-09-14 · graphyos issue 98)

- `cli.stage_generation` · `cli.land_generation` · `cli.discard_generations` · `cli.served_data_home`: `eat` and `rebuild.rebuild` copy every served `<slug>_graph/` as the three splice files (a placed lane whole, taken from `substrate/` when its producer placed it there), run smash · history · init · scheme index · converge · build against `.tenant.json.next` pointing at the stage, move the stored traversals across, rename the descriptor, then remove every generation older than the one just replaced and clear `substrate/` down to the placed lanes — best effort, so a store a live door holds on Windows stays as garbage no descriptor names until a later landing. The replaced generation is kept whole until the next landing: a door that read the descriptor a moment before the rename finishes opening what it read (round 2). `check` runs on the landed descriptor.
- An eat that refuses (a lane it did not mint, #70) now leaves the served generation exactly as it was: `pkg_b` is staged and discarded, never minted beside `pkg_a` under a deleted descriptor.
- `traversal._make_under`: a door still holding a discarded generation never recreates it to cache an answer — the write raises into the cache guard, which answers live and names `TRAVERSAL SKIPPED`. Found by the production probe below: the held server's blast had resurrected the old generation's directory.
- The placement directory `substrate/` is an input only for the placed lanes a rebuild names; everything else is seeded from the served generation. A pre-generation `substrate/` kept for a reader had been overlaid whole into the next stage and brought back a lane the landing pruned, so every later eat refused (round 3). A substrate or generation is spelled one way (`cli._spelled`: parent resolved, leaf as named), so under a symlinked `substrate` the generations are still its own and one generation back is all that is kept (round 3: it had been one full store copy per rebuild).
- Generation identity has one spelling: `_shared.generation_name` builds `<substrate>.gen-<token>` and `_shared.generation_of` reads it (a token of `[0-9A-Za-z-]`, never a dotted release). `cli._of_family`, `cartograph._excluded`, `cartograph.generation_base` and `refresh.plan_for` all ask it; `refresh` names its sibling by the base, `substrate.<release>/`, so the name holds across landings (round 4: it had been `substrate.gen-<token>.<release>/`, a new orphaned sibling and venv per forced refresh, hidden from the cursor and never discarded). `review.py generation-identity` refuses `GENERATION_INFIX` or a `.gen-` literal outside `_shared.py` (red=3 green=0; against round 3's `_excluded` it names `cartograph.py:16` and `:129`).
- A served home is followed only inside its own family (`<substrate>` or `<substrate>.gen-<token>`, never a refresh sibling's dotted release): a descriptor copied with a checkout names the original's data home, which a re-eat of the copy never reads or moves (round 2).
- `cartograph.cursor_exclude` is the one exclusion `eat`, `rebuild`, `check` (through `tenant_exclude`) and `showcase` ask, and excluding a substrate excludes every generation of it: rebuild had excluded the descriptor's directory while check excluded the data home, so a `substrate.gen-*` beside a gitignored `data/substrate/` read CHECK RED on every rebuild (round 2). `review.py cursor-exclude-by-tenant` refuses a cursor call whose `exclude=` is not a declared `CURSOR_EXCLUDERS` call (red=5 green=0, an `as` alias and a `getattr` included since round 3; against HEAD's `rebuild.py` it names `rebuild.py:201`).
- The readers that spelled the path — `showcase`, `shell install` (and its history re-mint) and the gate — read `ring.json` from the data home the descriptor names; `review.py data-home-by-descriptor` refuses a path built on the literal `substrate` outside `cli.DATA_HOME_DECLARERS` (red=4 green=0, an f-string join included since round 2; against HEAD's `gate.py` it names `gate.py:56`).
- The marker design of 72ad4d7 (`.rebuild_in_flight`, `land_descriptor`, the STALE-served branch in `open_for`) is removed whole; `open_for` is as it was before #98.
- API note for a tenant calling `rebuild.rebuild`: the receipt's `substrate` is now the landed generation, and `substrate=` is the placement directory a producer writes placed lanes into — it is no longer the data home.
- Not in this rung: the five in-repo tenants' `rebuild.sh` still `rm -rf "$SUB" "$DESC"` (the FastAPI `.mcp.json` door goes down across its own rebuild), and `shell install`'s history re-mint still rebuilds the served generation in place.

| check | result |
|---|---|
| the done test | `cd engine && ../.venv/bin/python -m pytest -q -k store_stays_servable_through_a_rebuild` → 2 passed (`rebuild` · `eat`): the plugin's own argv, read from `.claude-plugin/plugin.json`, opens the last good generation with rc 0 before smash · init · converge · build, the new one after; a descriptor read before the rename still opens under refuse after it; a `SQLiteStore` held across the rebuild still answers; the replaced generation stands until the next landing removes it, and the held door's blast is then not cached into it; no staged descriptor. Against e3e3709's engine (only `served_data_home` added) it fails `('before smash', 2, None) … ('before build', 2, None)` |
| round 4's blocker as a test | `test_RED_a_refresh_sibling_keeps_its_name_across_landings_and_is_never_a_generation` (with `plan_for` over the served home: `{'substrate.gen-…-f5594a.2.0'} != {'substrate.2.0'}`) |
| round 3's blockers as tests | `test_RED_a_substrate_from_before_generations_never_brings_back_a_pruned_lane` (with the whole-substrate overlay: `EAT REFUSED … dep_graph`) · `test_RED_a_symlinked_substrate_keeps_one_generation_back_and_no_more` (with fully resolved family comparison: 4 generations after 4 rebuilds) |
| round 2's blockers as tests | `test_RED_rebuild_and_check_agree_on_dirt_when_the_substrate_sits_apart_from_the_descriptor` (with rebuild's old `(desc.parent,)` exclusion: `RebuildError: check failed`) · `test_RED_a_copied_checkout_never_follows_its_descriptor_into_the_original` (without the family guard the original's `traversals` leave its data home) · the done test's before-the-rename open (with the replaced generation discarded at landing: `no compiled store`) |
| round 1's blockers as tests | `test_RED_an_interrupted_rebuild_never_touches_the_served_store[smash · build]` (a ^C leaves the descriptor byte-identical and the store FRESH under refuse; against e3e3709 the descriptor is gone or torn) · `test_DURABLE_a_generation_lands_while_a_door_holds_the_served_store` (a read-only SQLite handle held across the landing; in the `store-windows` job's durable mark) |
| production | `graphy eat` of FastAPI 0.139.2 (a local clone, 5,129 nodes / 11,865 edges, 9 ring shards), a file added, re-eaten while the plugin's `graphy mcp --repo` was started in a loop and one server held open on stdio: re-eat 1.1 s wall · a door started at every step of it (14 in this sample, 13 in round 5's) · 0 refused · generations served `6da564ad44654076` then `c874b9020ec5af28` · the held server answered a JSON-RPC `blast fastapi.routing.APIRouter` after the landing (from the generation it opened, dependents=1) · two generations on disk after, the served and the one it replaced (before `_make_under`, a held blast after a discard had resurrected a third) |
| the floor · the gate | `python3 -m pytest -q` green (rc 0) · `standalone_check.sh` → `GRAPHY_STANDALONE_OK` · `review.py --diff HEAD` 14 checks · 0 findings |
| review | round 1 (on 72ad4d7's marker design): REVISE — B1 the shipped door (`--on-stale refuse`) still refused for the whole window and the done test asserted the gap · B2 the marker outlived an interrupted rebuild, serving a torn substrate under warn · B3 the design tore the inputs it served and moved the Windows `os.replace` failure to the end. All three answered by the generation design and pinned by the tests above. Round 2 (the generation design): REVISE — B1 the landing discarded the generation a door was still opening (`cannot measure shard input … FileNotFoundError`) · B2 rebuild's and check's cursor exclusions disagreed, CHECK RED on every rebuild with the substrate apart from the descriptor · B3 a copied checkout's descriptor was followed into the original. Fixed and pinned above; B2 is a `review.py` check, B1 and B3 specimens on the card's ⑥ with their red tests; folded: a failed stage copy removes its partial stage, a discard failure after the rename is named and never reported as the served store standing, the f-string join. Round 3: REVISE — B1 a pre-generation substrate kept for a reader was overlaid into the next stage, resurrecting a pruned lane and refusing every later eat · B2 a symlinked substrate was never its own family, one store copy per rebuild. Fixed and pinned above, specimens on the card's ⑥ (a lint over one function was tried and is a test in lint clothing); folded: `cursor-exclude-by-tenant` sees aliases and `getattr`. Two rounds found ⑥, so round 4 reviews the design. Round 4 (the design round): the generation design is sound — clearing shards under a kept store refuses (#97 hashes the inputs), a store replaced in place fails on Windows, and only a pointer untouched mid-build meets both; migrating the legacy substrate out at the first landing is not smaller and re-opens round 2's B1. REVISE — B1 three predicates spelled generation identity three ways and `refresh` named its sibling after the token. Fixed and pinned above, the door a `review.py` check. Round 5: **SHIP** — no blockers; re-measured on the final code (re-eat 1.1 s, 13 door starts, 0 refused, the held server answering after the landing, the refresh sibling `substrate.2.0` after landings 1 and 3). Observations carried in the commit: a substrate itself named `<x>.gen-<y>` reads as a generation of `<x>` (nothing deleted, dirt never under-counted); a landing whose rename fails loses the moved traversal rows (a cache, a re-walk); `_excluded` costs ~3.4× on 100k untracked paths; an explicit journal or join keys inside `substrate/` would be cleared |

## 129 · A FAILURE IS THE LAST LINE, AND AN INSTALLED TREE IS NOT REINSTALLED — piped, stdout is block-buffered and stderr is not, so a first client's Windows `EAT FAILED at build` printed in the middle of the edge summary before it; and `eat` ran `npm install` into a `node_modules` the user had already installed, a write into a directory nobody nominated (2026-09-14 · graphyos issue 87)

- `cli._StderrAfterStdout`: `cli.main` installs a stderr that flushes stdout before every write, once per process (a nested `main` sees it installed and leaves it), restored on the way out. Every verb's failure line goes through it, so the ten hand-placed `sys.stdout.flush()` calls on eat's refusal lines are gone.
- `provision.provision` under `typescript_ast`: a `node_modules` that is present is read as it stands — `npm install skipped — … already installed, not by graphy` — unless graphy's own receipt (written pending before its install, so a failed install is retried) (`.graphy/npm_provision.json`, the sha256 of `package.json` · `package-lock.json` · `npm-shrinkwrap.json` · `yarn.lock` · `pnpm-lock.yaml`) shows the lockfiles moved since its own install. An install is announced first: `PROVISION: about to write <node_modules> — npm install … ; --no-provision reads the tree as it stands`.

| check | result |
|---|---|
| the done tests | `test_RED_a_failure_line_is_the_last_line_when_both_streams_share_a_pipe` (a real `python -m graphy eat` refused after its mint, stdout and stderr into one pipe: the last line is `EAT REFUSED`; with the wrapper not installed the refusal lands before `MINT OK`) · `test_RED_an_installed_node_modules_is_never_reinstalled_unasked` (a user's tree untouched; absent → installed, announced with `--no-provision`, receipted; same lockfile → skipped; a moved lockfile under eat's own install → installed; with the skip removed the user's tree gets `npm install`) |
| production | `graphy eat` of the Express checkout (`staging/corpora/ts/express`, a copy, installed `node_modules`): rc 0 in 0.8 s, 62 ring shards, `npm install skipped — … already installed, not by graphy`, `node_modules` byte-identical (the depth-2 listing digest and its mtime unchanged). A planted lane then refused the re-eat with both streams piped through `cat`: 69 lines, the last `EAT REFUSED: 1 lane(s) here were not minted by express's import ring …` |
| the floor · the gate | `python3 -m pytest -q` green · `standalone_check.sh` → `GRAPHY_STANDALONE_OK` · `review.py --diff HEAD` 14 checks · 0 findings |
| review | round 1: REVISE — B1 the ownership receipt was written only after a successful install while the skip trusted its absence, so graphy's own failed `npm install` (a directory made, then a network error) read as `already installed, not by graphy` and was never retried. The claim is now written pending before the act; the red case in `test_RED_an_installed_node_modules_is_never_reinstalled_unasked` (a failing install, then a retry that runs npm) fails with the pending write removed (`3 == 4`). Specimen on the card's ⑥; the check tried (a receipt before the subprocess it attests) fires on `provision.json` and `PROVENANCE.json`, where writing on success is right. Observations: the skip is broader than "lockfile unchanged" (a user's stale tree stays theirs; `--site-packages` or deleting it); yarn/pnpm lockfiles are hashed but the install is still npm; `writelines`/`.buffer` on stderr would bypass the flush (no caller). Round 2: **SHIP** — the done lines re-run on the Express copy (69 lines, the last `EAT REFUSED`; npm skipped, `node_modules` unchanged), both tests fail with their fix removed, round 1's repro retries and installs; the pip receipt is not the same defect (its skip never trusts absence, and it writes only into graphy's own venv). Observations: a hand-written non-dict claim reads as a claim; the claim can appear in `git status` before `.graphy/.gitignore` is written; `graphy.query` · `shell.gate` · `lightning` do not pass through `cli.main` |
| review | round 2: **SHIP** — the ledger re-verified on its specimens (round 1's repro `0 of 1` at both holes; the new case red on the round-1 engine, green now; `-k` 16 · file 17 · step argv 20 · red-first 17 of 17); the fix refuted (a `KeyboardInterrupt` inside the guard closes the handle and a store `open_for` returns is never closed by it; `close()` three times is a no-op; every `return` before a `with store:` sits in the open's own `except`; no module-level cache holds a store; every duckdb connection closes in a `finally`); the walk at depth 1 names no caller outside the diff; the gate, the battery, `ARMS OK` on store 5577b094d4cc145b and run 34882890712 re-run by the seat. Non-blocking, folded: the platform row named two commits by one phrase — reworded |

## 130 · MAIN WAS RED FOR THIRTY-TWO RUNS AND THE LOOP NEVER READ IT — the last green `ci` on main is `4578d73` (0.2.4); every run since was red, for three causes, each hidden behind the one before: the receipt's wheel lane ran `release.sh` whole, whose PyPI check refuses every commit after a release; from §124 the gate ran the march's floor as `python3 -m pytest`, green here where pytest is installed system-wide and `No module named pytest` on every runner; from #98 a floor test planted its traversals through a `blast` that needs duckdb, which CI's floor does not install. Rungs closed on a red main because the close never looked (2026-09-14 · found marching graphyos issue 88)

- `release.sh --build`: the offline half — versions, the wheel and sdist, `twine check` — which `measure.py measure_wheel` runs; the bare `release.sh` (the operator's cut) still refuses a second, different version on PyPI (#79).
- `standalone_check.sh` runs the march floor with the gate's own fresh venv (`"$PY" -m pytest`). `test_RED_a_copied_checkout_never_follows_its_descriptor_into_the_original` plants the traversals by hand.
- `workflows.py --run <workflow> <job>`: a job run here the way a runner runs it — a copy of the tracked tree with no `.private_key`, `setup-python` a bare venv first on PATH, EVERY step run and reported, so a red never hides behind the first. Against HEAD it names all three at once (`ci.yml:gate` — the departure gate · the receipt; `ci.yml:floor` — the floor).
- `review.py host-interpreter`: a tracked shell script outside `staging/` runs `python -m`/`python3[.x] -m` on the host only for a standard-library module, in command position however led (indented, `if`/`exec`/`env`/an assignment, an absolute path, a flag before `-m`); a workflow `run:` may also use `pip` and what its own file pip-installs before the line (red=11 green=0; a venv's interpreter and a job's editable install are its own; against HEAD's `standalone_check.sh` it names `:71`).
- `.claude/hooks/march.py ci_red`: when the armed rung is closed, the Stop hook reads main's newest `ci` run and blocks on `failure` · `timed_out` · `startup_failure`, naming the sha, on every stop until it is green — except a stop waiting on the session's own background work (§125). Pending, green or unreadable marches.

| check | result |
|---|---|
| CI, run here | `python3 workflows.py --run .github/workflows/ci.yml gate` → `CI LOCAL OK: 5 step(s)` (gate 25.5 s · census · receipt 78.3 s); the same against a HEAD worktree → `CI LOCAL RED: 2 of 5 step(s) — the departure gate · the receipt`, and `floor` → `RED … the floor` |
| the doors' tests | `test_a_rung_closed_on_a_red_main_blocks_until_main_is_green` (with the read removed it fails) · `test_a_red_main_never_holds_a_session_waiting_on_its_own_background_work` (with the pending allowance removed it fails) |
| the floor · the gate | `python3 -m pytest -q` green · `standalone_check.sh` → `GRAPHY_STANDALONE_OK` · `review.py --diff HEAD` 15 checks · 0 findings · `test_march.py` 21 passed |
| review | round 1: REVISE — B1 a third red (the receipt's wheel lane, red since 0.2.4) masked behind the gate, so the done block reproduced only the first failing step (door: `workflows.py --run`, every step) · B2 `host-interpreter` blind to indented, keyword-led, versioned and absolute calls and to workflow `run:` bodies (widened, red 3 → 10) · B3 the red-main hold ran before §125's pending check (a red test). Round 2: REVISE — B4 the widening flagged a venv's own interpreter (`v/bin/python -m pytest`, the fix its message recommends) and read `pip install -e "engine[dev]"` as owning `engine`: only a bare or system-path interpreter is the host, and a local-path, editable, extras or requirements install owns every module (green fixture widened; red 10 → 11 with a `timeout`-led `-W` form). Folded: `workflows.py --run` puts only the venv and the system directories on PATH, so a host `~/.local/bin/pytest` cannot stand in for a missing extra. Round 3: **SHIP** — every round-1 specimen still matched over 40 probe lines, no new false positive on the tree, the restricted PATH changes no test's skip status. Bounds named: a workflow's editable install excuses every later job in its file; quoted `"python3"`, `sh -c` bodies, `xargs`, `$(which python3)` and a non-system absolute interpreter are not seen (none in the tree); `--run` does not emulate `env`/`if`/matrix/`${{ }}` or the runner's toolset |

## 131 · AN ARM'S LAST WALK COUNTS WHAT THE COMMIT OWNS — `graphy arms` stamped `dependents=N` from a blast over the whole store, and the store holds the ring the rendering interpreter installed and the history lane the sessions archive fed: one commit read `open_for` 73 here and 71 on the CI runner, then 86 and 87 after a session named the crown, so `arms --verify` read ARMS DRIFT with no code moved and the `blast radius` job was untrustworthy on any PR rendered elsewhere (2026-09-14 · graphyos issue 90)

- `arms._stamp_last_walks` counts only the reached dependents the corpus owns, and the line says so: `Last walk: crown=… dependents in graphy=N`. A dependent the corpus owns cannot be reached through another lane (a ring package never imports the corpus; a mention points into it), so the count is the commit's alone. The six tracked graphy arm regions are re-rendered in the new form (the CLI and DOORS crowns also moved, to `cli.served_data_home` and `traversal.home_for` — this session's code).
- `workflows.py --run` names a step that reads a `${{ }}` context SKIPPED with the reason, and counts skipped steps in its verdict.

| check | result |
|---|---|
| the red test | `test_RED_the_last_walk_counts_what_the_commit_owns_never_the_box_or_the_archive` (three blasts differing only in ring and history lanes stamp one line; with the old `len(reached) - 1` it fails) |
| the same regions from different rosters | over the graphy tenant's store (`duckdb · graphy · history · tests · tree_sitter · tree_sitter_typescript · typing_extensions`, 4,205 nodes), `arms.render_all` is byte-identical to stores compiled for `graphy · tests`, `graphy · tests · history` and `graphy · tests · duckdb · typing_extensions`; under the old count the first differs |
| rendered anywhere | `python3 workflows.py --run .github/workflows/blast-on-pr.yml blast` — a clean copy, no sessions archive, its own venv's ring: `HISTORY OK … 0 session(s)`, `BUILD OK: 3035 nodes / 7962 edges`, `ARMS OK: 6 arm(s) match the walk` against the regions rendered on this box from 4,205 nodes |
| production | `bash engine/tenants/graphy/rebuild.sh` → `ARMS OK: 6 arm(s) match the walk (store 70d2d3ba66002f87)`, 4 s |
| the floor · the gate | `python3 -m pytest -q` green · `standalone_check.sh` → `GRAPHY_STANDALONE_OK` · `review.py --diff HEAD` 15 checks · 0 findings · `workflows.py --run ci.yml gate` and `floor` → `CI LOCAL OK` |
| found on the way | the rebuild's `graphy harness` step appended draw bands and scaffolds carrying host-absolute paths to the six tracked arm files and wrote `GRAPH.md` · `*.walk.txt` · `drawings/` · a root `AGENTS.md`; the gate's scrub refused it. Reverted to the regions alone; filed as #128 |
| review | round 1: **SHIP** — two real rebuilds in clones with the diff applied, one with no ring at all (`graphy + 0 ring shard(s)`, 2,414 nodes) and one with the full extras and no sessions (3,453 nodes), each `ARMS OK: 6 arm(s)` against the tracked regions and `docs/pillars.svg` byte-identical; crowns, the corpus-owned reached sets with hops, and every region identical between the full store and `[graphy]` alone, `[graphy, history]`, `[duckdb, graphy, tree_sitter]` (fan-in counts only corpus-owned edges; `mentions` is admitted at hop 1 only). Observations: the other four tenants' regions never carried a last walk, so their `arms --verify` drifts before and after this diff (filed); `workflows.py --run` skips `blast_pr.py`'s `${{ }}` step, so done line 2 is proven for the verify, not the comment script |

## 132 · THE TRACKER IS SCRUBBED, AND A POST CARRYING A MARKER NEVER POSTS — `scrub.py` walked files only, and the public tracker, where a project's evidence gets written, carried keyed-marker hits the gate had never looked at (2026-09-14 · graphyos issue 91)

- `scrub.py --issues <owner>/<repo>`: every issue and pull request, open or closed — title, body, each comment — through the same keyed digests, each hit named `#N body:<line>` or `#N comment K:<line>`, never the word; a `gh` fetch that fails or does not answer a JSON list is `SCRUB REFUSED` (exit 2), never a clean zero. Off-box, like `release.sh --published`: not in the gate, which is offline.
- `scrub.py --text <file|->`: one draft, before it is posted.
- `scrub.py --gh-hook`, wired as a PreToolUse `Bash` hook in `.claude/settings.json`, decides from the command's own shell words (`_words`, quote-aware: single quotes literal, and each word marked when a `$(…)`, a backtick or a `$name` sits outside them), never from a regex over raw text. A post is any word named `gh` — a path, quotes, a line continuation — whose group and verb, after `-R`/`--repo` wherever they sit, is an issue, pr or release post; `sh -c` and `eval` bodies are parsed the same way. It scrubs only what travels: each `--title` · `--body` · `--comment` · `--notes` · `--subject` value (the `=` and attached `-bVALUE` forms), every body file (against the payload's `cwd` and any `cd`), a heredoc feeding the post's `-`, and a `$(cat <<EOF … EOF)` body. A word the shell builds is read when that is static — `$NAME` for a name the command assigns (or `HOME`/`PWD`), `$(cat F)` · `$(<F)` · a backticked `cat` as F's bytes — and otherwise refused: another command's output, an unset name, a piped `-`, a post run by `xargs`, an unreadable file, an unparseable command or any crash is `SCRUB REFUSED`, exit 2, never exit 1 (which a PreToolUse hook reads as allow). A path, a `cd`, a `--repo` or a script beside the post is never scrubbed. No key: allowed. rung-discipline's fork carries the law.
- Not covered, by name — the static limit: the hook reads the command the Bash tool was handed, not what runs, so a post from a script file, a sourced file, a function defined in an earlier call, `$cmd` as the command word, `env -S`, a subprocess, `gh api`, `gh alias`, `gh gist create`, release asset uploads, `--recover`, `--template`, `--fill`, or a commit message through `sync_public.sh` is not seen (#131 is the argv-level shim); `--issues` does not fetch PR reviews, releases or discussions (0 · 0 · off today), and GitHub keeps a redacted body's edit history. The issue body's count (22 hits over 14 issues, 2026-09-13) was taken before later edits to the board; the sweep on 2026-09-14 read 14 hits over 6 surfaces, all redacted (#130).

| check | result |
|---|---|
| the board, today | `python3 scrub.py --issues omnislash157/graphyos` → `SCRUB RED: 14 hit(s) in 391 surface(s)` in 4 s; redacted on the operator's ruling (edit history accepted) through the REST API, fully paginated — 129 issues and PRs, 135 comments, 0 PR review comments — every flagged word replaced by `[redacted]`: 14 replacements over 6 surfaces (#63 · #64 · #75 · #81 · #107 bodies, one #83 comment), then `SCRUB OK: 393 surface(s)`, which is 2 × 129 + 135, the same count the REST read gives, so `gh --json comments` truncated nothing (#130); a repo that does not resolve → `SCRUB REFUSED … never a clean zero`, exit 2 |
| the hook, live under the key | a post quoting one line of a board surface the sweep names → exit 2 `SCRUB REFUSED: this post to GitHub carries 1 private token(s)`; a clean `gh issue comment` and a plain `ls` → exit 0 |
| the red tests | `test_RED_the_tracker_is_scrubbed_by_issue_and_line_and_a_failed_fetch_refuses` (with the refusal replaced by an empty surface it fails) · `test_RED_a_post_to_github_carrying_a_marker_is_blocked_before_it_posts` (with the post match removed it fails) |
| the floor · the gate | `python3 -m pytest -q` green · `standalone_check.sh` → `GRAPHY_STANDALONE_OK` · `review.py --diff HEAD` 15 checks · 0 findings |
| review | round 1: REVISE — B1 the hook scrubbed the whole command, so a clean post whose body-file path or `cd` carried the home path's marker segment was refused and no rewording could clear it · B2 the body-file leg failed open (`--body-file=`, a piped `-`, a relative path against the hook's own cwd, an unreadable file raising to exit 1). Fixed by `posted_texts`; red cases in `test_RED_a_post_to_github_carrying_a_marker_is_blocked_before_it_posts` (with the whole command scrubbed again, or an unreadable file skipped, it fails); specimens on the card's ① and ②; the `review.py` check tried guards one parser. Found while fixing: scrubbing every heredoc refused a python script beside a post — a heredoc counts only when it feeds the post. Live under the key: a clean post from the scratchpad → exit 0, a body carrying the marker → exit 2. Round 2: REVISE — B3 a post named with a global flag (`gh -R o/r issue create`, `gh issue --repo o/r comment`), a line continuation, `/usr/bin/gh` or `"gh"` returned 0 unscrubbed · B4 a body built by `"$(cat f)"`, a backtick or `"$B"` posted unread. Same class in two rounds of one parser, so the parser was redesigned: shell words, not a regex; red cases shown failing first; mutation-checked (a `gh`-adjacent recognition, or treating a built word as literal, fails the test). Found on the way: the expansion check first read shlex's output, which drops quote kind, so a single-quoted markdown body with backticks was refused — a quote-aware tokenizer now; and a title with parentheses made a `$(cat <<EOF)` body look bare. Replayed over every `gh` post command in this project's transcripts (281): 169 scrubbed clean, 58 no post, 2 marker hits, 52 refused — 29 a body file deleted since, 13 a variable set in an earlier call, 7 another command's output, 3 before the heredoc-aware paren fix. Folded: `--issues` refuses a list answering its whole 5000 limit. Round 3 (the design round): keep "read only what travels" — no historical post used one narrow form, so an allowlist refuses nearly every post — and flip the flag grammar to fail closed. REVISE — B5 `pr review --comment` takes no value, so a fixed flag arity skipped the body · B6 an unquoted heredoc into `-`, `/dev/stdin`, `$1`/`$@` and the hook's own `$PWD` read as literal text · B7 `issue|pr reopen --comment` and `bash -ec` unrecognised · B8 RECON and the docstring overclaimed. Fixed: every word after the head is scrubbed except its envelope (a `--repo` value, a body-file path, a redirection and its target); any `$` not before whitespace expands; only names the command assigns, `HOME` and `PWD` resolve; `--…-file` reads its file. Found on the replay: redirect targets and an unlisted `--…-file` path were being scrubbed as posted words. Final replay over 285 unique historical commands: 131 scrubbed clean, 58 no post, 2 marker hits (both bodies since redacted), 94 refused — each a word bash itself would expand from something unreadable (41 another command's output, 29 a body file deleted since, 15 a name set in an earlier call, 6 a parameter) — 0 hits on a bare path, slowest 1.7 ms. **Compounding:** every specimen of rounds 1–3 is a line in `review_specimens/gh_hook.tsv`, replayed by `review.py specimen-corpus` (56 lines, selftest red=2 green=0; the round-1 hook fails 25 of them). Filed: #131 the argv-level `gh` shim, the complete form. Round 4: REVISE — B9 the heredoc pre-pass ran over raw text, so a quoted body quoting a heredoc repro lost those lines unscrubbed, and a heredoc fed to `bash` was not read as its script · B10 a quoted value starting `>` or `<` was skipped as a redirection · B11 a built group or verb (`gh issue $V`) was never recognised. Door: seven lines appended to `review_specimens/gh_hook.tsv`, red first (`specimen-corpus` 7 findings), then the fix — the tokenizer owns heredocs (only an unquoted `<<`, each body tied to the segment it feeds) and records whether a word's first character was bare (only a bare `>`/`<` redirects), and a built head word expands or refuses. 63 specimens green; replay over 292 unique commands: 136 clean, 60 no post, 2 marker hits, 94 refused (41 another command's output · 32 a file gone since · 12 a name set elsewhere · 6 a parameter · 2 a heredoc with no body · 1 an unclosed backtick), 0 bare-path hits, slowest 1.9 ms. Round 5: REVISE — eleven commands posted a marker while the hook exited 0, each confirmed against real bash with a logging `gh` stub: B12 a shell's script missed (options before `-c` such as `-euo pipefail`, a prefix assignment before `bash <<EOF`, a built `-c`/`eval` script) · B13 the heredoc end line was not bash's (a quoted delimiter kept its quotes, ` EOF`/`EOF ` ended the body, a backslash-newline was joined inside a quoted body) · B14 a greedy `$(cat <<EOF)` fast path swallowed a second substitution. Four rounds of the parser disagreeing with bash are one class, so the door is bash itself: `specimen-corpus` now runs every line under `bash` with a stub `gh` that logs what would travel, and a marker reaching the stub with the hook not refusing is a finding whatever the line expects (selftest red case added). Lines appended red first (11, the oracle agreeing line for line); then one heredoc reader by bash's rules shared by the tokenizer, `$(…)` and `$(cat <<EOF)`, every shell option scanned for `-c`, built scripts expanded. 75 specimens green by expectation and by bash. Round 6 (hunting with the bash oracle): REVISE — B15 an assignment bash keeps or drops was read otherwise (inside `if`/`for`/`{…}`, after `export` or `!`, and a prefix `B=a true` stored as if it persisted) · B16 a body file written earlier in the same command was read as it stood before bash ran (`cat > F <<EOF`, `echo >`, `tee`, `cp`). Ten lines appended red first (each line now restores the fixtures, since a line may rewrite them; the stub reads `-F<path>`). Fixed: a pre-scan by nesting depth — a name resolves only through a plain top-level assignment in an assignment-only segment, and is tainted if assigned any other way; writes are tracked in order — `cat > F <<EOF` is that body, any other write to a path, or an interpreter run before the post, makes a later read refuse. Mutation-checked (the persistence guards off: 12 findings; the writes off: 8). Folded: `gh label create|edit` are posts. 87 specimens green by expectation and by bash; replay over 297 unique commands: 136 clean, 63 no post, 2 marker hits, 96 refused (41 another command's output · 28 a body written earlier by a writer the hook cannot read · 14 a name not set · 6 a parameter · 4 a file gone since · 3 malformed), 0 bare-path hits, slowest 2.2 ms. Named limit widened: `gh alias`, `gh gist`, release assets, `--recover`, `--template`. Round 7 (the oracle hunt, told to weigh proportion): REVISE — B17 `gh issue|pr|release new`, gh's own alias of `create`, was no post (the plain filing verb under its other spelling) · B18 an assignment bash may skip (`true || B=clean`, `false && B=clean`) or run in a subshell (`B=clean | cat`, `B=clean &`) read as the value bash keeps, the default-fallback idiom `BODY="$(cat f)"; … || BODY="…"` among them · B19 `then`/`do` counted as openers with no closer, so the depth never returned to 0 and every clean filing after a loop or a branch refused (fail-closed, and no rewording cleared it). Sixteen lines appended red first (25 findings, the oracle agreeing on every fail-open). Fixed: `new` in the post table beside `repo create|edit` (a description travels); the blocks are a stack, so `)` closes only a subshell and `fi` only an `if`, which also catches the `case` arm round 7 called contrived; an assignment reached through `&&`·`||` or standing in a pipeline or backgrounded is conditional, and with any other assignment to the name it is tainted — one conditional assignment alone (`cd X && B="…" && gh …`) still resolves. Mutation-checked: B18 off → 10 findings, B19 off → 3, B17 off → 8. 102 specimens green by expectation and by bash; replay over 306 unique commands: 139 clean, 69 no post, 2 marker hits, 96 refused (unchanged from round 6), slowest 1.9 ms. Round 8: **SHIP** — 68 candidate lines under the oracle (case arms with `;&`/`;;&`, nested blocks, `else`/`elif` assignments, function bodies in every spelling, `until`/`while read`/`for ((…))`, three assignments across `||`, `cd` in a pipeline, `new` under every flag placement, `repo edit -d`, the write inside `( )`/`{ }`/`if`) all agree with bash; six prior specimens re-run by hand agree; mutations in scratch (`new` off → 4, `fi` closing nothing → 1, the conditional rule off → 10). Folded at commit, their lines red first on the hook as reviewed: `issue develop --name`, `project item-create --title`, `workflow run -f` are posts (a branch name, an item, a run's inputs travel — the prefilter matches `workflow run`, not the bare word, which put 130 `gh run list` commands in front of the parser and refused six), and `gh … > F` marks F written like any other redirect (a global unknown-writer flag was tried and refused 23 historical `gh issue view > F; cat > G <<EOF; … -F G` sequences). A second round-8 reviewer, forked from the session that landed §133, read REVISE on one more oracle-confirmed hole, B20: a `cd` inside `( … )` outlived the subshell in the hook's cwd, so this repo's own `( cd engine && … ) && gh … --body-file notes.md` refused, and `cd -` was followed as a directory named `-`. Six lines appended, three red first; fixed: the subshell restores its directory at `)`, and `cd -` · `pushd` · `popd` walk a directory stack. Round 9: REVISE — B21 the tokenizer split `2>&1`, `>& F` and `&> F` at the `&`, so `git status > log.txt 2>&1; gh … -F clean.md` refused with a false reason (the cwd itself read as written) and `echo … &> clean.md; gh … -F clean.md` posted the marker · B22 the round-8 `workflow run` verb was recognised by a two-word regex over raw text (`gh workflow --repo o/r run`, a line continuation: exit 0, the B3 forms again) and its `--json` inputs, read from stdin, were never read (the B2 class). Eleven lines appended, nine red first; fixed: `&` after a bare `>`/`<` or before `>` stays in its word, `>&`/`<&` lead the redirect alternations, a `>&` onto a descriptor writes no file; the prefilter matches `workflow` and the head parser does the rest; `--json` on `workflow run` reads the segment's heredoc or refuses, and the oracle's stub reads it too. Found on the replay: `workflow` in the prefilter put `gh api …/$jid/…` in front of the head parser, whose built-word rule (round 4) refused a command that posts nothing — a built head word now refuses only where the literal words before it could still start a post (line pinned, expect 0). 124 specimens green by expectation and by bash; replay over 347 unique commands: 140 clean, 109 no post, 2 marker hits, 96 refused (the same 96), slowest 1.9 ms. Round 10: REVISE — B23 a post standing inside `$(…)` or a backtick was never walked as a command: the tokenizer folds the substitution into one built word, and the word is only ever expanded, so `URL=$(gh issue create -t t -b …); echo "$URL"` — this box's own idiom, 23 times in its transcripts as `=$(gh issue create`, the capture-the-url form — posted the marker with exit 0, and the replays had filed such commands under "no post". Eleven lines appended, nine red first with the oracle agreeing; fixed: every built word, in any position and before `_expand` can swallow a refusal, has each `$(…)`/backtick body walked by `posted_texts` as a script (the `sh -c` · `eval` · heredoc-to-shell class of rounds 2, 4 and 5). Found on the replay: the inner walk began with a fresh environment, so `S=/x; URL=$(gh issue create -F $S/ask.md)` refused `$S` — a substitution runs in this shell, so the inner walk inherits the outer's names, directory and recorded writes (two lines pinned). 137 specimens green by expectation and by bash; replay over 351 unique commands: 146 clean, 108 no post, 2 marker hits, 97 refused (the 96, plus one substituted post whose title a `for` loop set — round 6's ruling), slowest 1.9 ms. Round 11: REVISE — B24 the `--flag=value` branch re-expanded the text after the first `=` of EVERY posted word as live shell, so a `$(cat <<'EOF' … EOF)` body carrying `URL=$(…)`, `PATH=$PATH`, `cost=$5` or `foo=$1` — the repo's dominant filing idiom with a shell line in it — refused on a garbage fragment, and the ledger's "41 another command's output" was mostly this false reason (class ④: the record's count re-derived below) · B25 a writer inside a walked `$(…)` never marked the outer command (the unknown-writer was a string copied into the inner environment) and `eval` was no writer, so `OUT=$(python3 gen.py 2>&1); gh … -F report.md` posted what the script wrote · the depth cap skipped a fourth nested shell instead of refusing it. Eleven lines appended, all red first (five over-refusals, six fail-opens the oracle confirmed); fixed: the whole word is scrubbed once and its `=` tail never re-expanded; the writer mark is a holder shared by every walk of one shell and `eval` is a writer; past the cap a script that could post refuses. 148 specimens green by expectation and by bash; replay over 352 unique commands: 183 clean, 109 no post, 3 marker hits (the third a 02:37 filing whose body the tracker no longer carries — `--issues` reads 400 surfaces clean), 57 refused, slowest 3.1 ms. Round 12: REVISE — B26 `writes_of` took a segment's first word as its command, so a writer after `do` · `then` · `time` · `env X=1` · `!` · `{` or inside `f() { … }` was invisible — B16's tracking never got the keyword list B15 carries (twenty oracle-confirmed fail-opens, `for … do python3 gen.py; done; gh … -F report.md` among them) · B27 the `bash -c` and heredoc-to-shell walks started with no record of the outer's writes, so `echo … > clean.md; bash -c 'gh … -F clean.md'` posted what was just written (B25's class through the one walk it did not touch). Fourteen lines appended, eleven red first; fixed: the command word follows its keywords and prefix words; a child shell inherits the directory and the writes so far (`child_env`), never an unexported name. Folded: the oracle leg that could not run a line (no bash, a timeout) is a finding, never a silent skip; the stub reads `-F=path` as pflag does. The round-11 breakdown was mislabeled (class ④) and is re-derived from the hook's own reasons: of 57 refused, 27 a file read after an interpreter that may write it (B16 by design), 19 a name or parameter not set, 4 a body file gone since, 4 another command's output, 2 a heredoc with no body, 1 a file written earlier by a writer the hook cannot read. 162 specimens green by expectation and by bash; replay over 353 unique commands: 183 clean, 110 no post, 3 marker hits, 57 refused, slowest 3.5 ms. Round 13 (refuting round 12's fix through its neighbours): REVISE — B28 a redirect heading a segment was taken as its command word, so `( … ) > clean.md; gh … -F clean.md` (this repo's subshell idiom one redirect away) and `> F cmd` were no write · B29 the round-12 prefix list carried a block's inner words (`then`, `do`) and not its openers, so `if python3 gen.py; then gh … -F report.md; fi` — the post-on-success idiom — and `while`/`until`/`function` bodies were no writers; and a prefix word's separated flag value (`nice -n 5`, `env -u X`) was the command. Twenty lines appended, seventeen red first; fixed: `writes_of` chooses the command word past the openers, the prefix words, their flags and values, `function`'s name and any redirect before it, and its write scan covers the whole segment. History: none of these shapes precedes a post in 4,197 of this box's commands — taken because they are round 12's own class through the adjacent hole, oracle-confirmed. 182 specimens green by expectation and by bash; replay over 355 unique commands: 183 clean, 112 no post, 3 marker hits, 57 refused, slowest 3.1 ms. Round 14: REVISE — B30 round 13's value-flag set served five programs at once, so `time -p cp …` and `command -p cp …` swallowed the command word, and the leading-redirect pattern lacked `<`, so `< body.md tee clean.md` was no writer; six lines appended, five red first; fixed: each prefix word carries its own value flags (`nice -n` · `sudo -u -g -C -p …` · `env -u -C -S` · `command -v -V`, which names a program and never runs it — the `command -v python3 && gh …` guard round 13 saw refuse now passes · `exec -a`), and `<` heads a segment like `>` and writes nothing. **The design ruling the round was asked for:** the writer-tracking class (B16 · B25–B30) is read from hand tables — prefix words, their value flags, a writer allowlist by program — and six rounds each found one entry short; the residual the oracle still shows (`sed --in-place`, `sort -o`, `find -exec cp`, `git mv`, `tar --transform`, `cat > F file <<EOF`) occurs 0 times before a post in 4,197 of this box's commands, and the smaller design (a global unknown-writer) was measured and rejected in round 8 (23 historical sequences refused). That residual is #131's, the argv-level shim that reads the body after every write has happened — named here so no later round re-hunts it. 188 specimens green by expectation and by bash; replay over 356 unique commands: 183 clean, 113 no post, 3 marker hits, 57 refused, slowest 3.0 ms. Eliminated: `$((1+2))` in a body refuses (a rewording clears it); `sudo` forms are outside proportion. Round 15 (the classes other than writer tracking): **SHIP** — 105 specimen lines re-driven through the real hook CLI with 0 mismatches; 99 cold candidates over the posted-word grammar (`--base`, `--milestone`, `--assignee`, `--web`, `-R` after the body, every redirect spelling, `<<-` with tabs), the post table (every `_POSTS` verb in the prefilter), the expansions and the hook's failure modes (no `command`, a bad cwd, a latin-1 byte, a lone surrogate, a 1 MB body in under 0.2 s, 200-deep `$(` in 37 ms) all agree with bash; the `--issues` sweep's unread surfaces measured (the board's two PR reviews have empty bodies, 0 inline review comments, 0 commit comments, 0 releases, discussions off; 13 label descriptions, the repo description and the milestones scrubbed by hand through `--text`). Folded from its non-blocking list: a bare `~` in a posted word or an assignment value is the home bash posts (a floor test, red with the fold removed). Carried: `gh project create|edit`, `issue transfer`, `repo rename` are not posts (0 uses here; #131's form); `-F - < F`, `-F=path`, `cd -- X`, `cd "$(git rev-parse --show-toplevel)"` refuse with a one-word rewording; an absolute asset path carrying the home segment refuses; a checkout with no marker list exits 1 before the hook (unreachable with the tracked list). Eliminated, carried here: `$'…'` bodies and `workflow run -F` refuse with a one-word rewording; a bare `cd` is not followed; a literal `$(…)` inside single quotes is walked as if it ran (a refusal at worst, never a post unread); `eval 'B=…'` and `printf -v` set a name the pre-scan never sees (obfuscation, #131); a `for` variable's refusal says "not set by this command", which is untrue of `for` — the refusal is right, the sentence is loose; a keyword-looking argument in a non-command position (`rg -c if …`) pushes the stack and refuses a later filing until reworded |

## 133 · THE BOARD HAS A DECLARED ORDER, AND THE MARCH READS IT — `arm --next` and the stop hook's advance picked the lowest open issue number, so a tenant's priority meant a hand re-arm per rung, which is a limit on the loop (2026-09-14)

The operator's words: "line up the rungs, march autonomously"; the order is the first production tenant's, sent on the fleet wire as its message #3320.

- `python3 .claude/hooks/march.py order 122 124 …` writes `.claude/recovery/march_order.json` (tempfile + `os.replace`, gitignored); `next_issue` — the one chooser, behind `cmd_arm`, `cmd_next` and the stop hook's `advance` — walks the order first over the open candidates without `blocked` or `operator`, so a closed or gated rung falls through, then the number sequence for a rung the order never named. Bare `order` prints it; `--clear` returns to the sequence; numbers with `--clear` is an argparse error. A file that is there and does not read as a list of ints is named — `order ignored — <why>` in `march.log`, bare `order` prints `IGNORED` and exits 1 — never a silent fall-back to the sequence.

| check | result |
|---|---|
| the order, live | `python3 .claude/hooks/march.py order` → the first production tenant's seventeen, `#122` first · `python3 .claude/hooks/march.py next` → `122` |
| the red test | `test_a_declared_order_is_marched_first_and_a_closed_or_gated_rung_falls_through` — 1 failed on the tree before the change, 22 passed after; a torn `[122,` file → the sequence and the log line; `[true, 122]` → exit 1 |
| the gate | `standalone_check.sh` → `GRAPHY_STANDALONE_OK` (`test_march.py` runs inside it) |
| review | round 1: REVISE — B1 `--help` still said "the lowest open issue" beside the new rule (card ④; the docstring rewritten) · B2 a corrupt order file read as no order, silently (card ②; named in the log and on `order`, red cases added). Round 2: SHIP — the double read folded into one (`read_order`); not taken: `status` does not print the order (`order` does) |

## 134 · THE LOCK IS REAL ON WINDOWS — `_portable_flock` was a named no-op wherever `fcntl` is absent, so two concurrent journal appends minted one seq there and the index and fan-out locks never blocked; it is `msvcrt.locking` now, one copy behind `fcntl.flock`'s own signature (2026-09-14 · graphyos issue 122)

The first production tenant's platform (§133's order puts this rung first). A no-op lock is data loss, not a degradation: `test_concurrent_appends_never_mint_duplicate_seq` read `assert 2 == 3` on windows-latest ([run 34855052453](https://github.com/omnislash157/graphyos/actions/runs/34855052453)), the index observer never blocked, and `fanout.py` carried its own second `msvcrt` branch that the floor's shim proved through `fcntl` — a shim that could not even import on the platform it stood in for.

- `graphy/_portable_flock.py`: POSIX re-exports `fcntl` whole; native Windows gets `MsvcrtFlock(msvcrt)` — `flock(fd, LOCK_EX | LOCK_UN [| LOCK_NB])` over one byte at `LOCK_OFFSET` (`2**31 - 2`, past any content a journal will hold, so a reader on another handle is never refused a byte the writer holds — a Windows lock is mandatory, the callers were written for advisory), the descriptor's position put back after each call, `LOCK_EX` polling `LK_NBLCK` every 5 ms (`LK_LOCK` sleeps a second per retry and gives up after ten), `LOCK_NB` raising `BlockingIOError` like `fcntl`. `LOCKING` says `fcntl` or `msvcrt`; there is no third value. `fanout.py`'s own branch is gone; every lock site (journal · index · fan-out · inventory · registry) reads the one helper, and a test refuses a second copy.
- The floor drives the class on Linux through a shim whose `locking` is a real `fcntl.flock` (the class's contract: it blocks, it polls, `LOCK_NB` raises, the byte is `LOCK_OFFSET`, the position is restored, the file is not extended); `msvcrt.locking` itself is proven by CI's `store-windows` job, which now runs the three tests #122 measured red as its second mark.

| check | result |
|---|---|
| red first | `S=$(mktemp -d) && git archive 3b8f644 engine \| tar -x -C $S && cp engine/tests/test_portable_flock.py $S/engine/tests/ && (cd $S/engine && "$OLDPWD/.venv/bin/python" -m pytest -q tests/test_portable_flock.py)` → 6 failed of 6 on the engine before the change (no `MsvcrtFlock`, no `LOCKING`, the old `import fcntl` shim, `fanout.py` its own copy; round 2 re-derived it — the first draft of the row said 4, the file's count at its first draft) · the three named tests on windows-latest: run 34855052453, `assert 2 == 3` |
| the three, here | `cd engine && ../.venv/bin/python -m pytest -q tests/test_journal.py tests/test_mesh_federation.py -k "concurrent or lock"` → 4 passed · with `tests/test_fanout.py -k "concurrent or lock"` → 5 passed |
| the three, on the platform | `gh workflow run ci.yml --repo omnislash157/graphyos --ref scratch/122-lock` → run 34877343982: `store-windows` green — the durable mark 3 passed, the lock mark `.sss........` 9 passed · 3 skipped (the shim tests need `fcntl`; the host and one-copy tests and the three measured tests ran on `msvcrt`); the floor jobs green |
| the floor · the CI floor job here | `cd engine && ../.venv/bin/python -m pytest -q` → all passed, 2 skipped · `python3 workflows.py --run .github/workflows/ci.yml floor` → `CI LOCAL OK` |
| production | `bash engine/tenants/graphy/rebuild.sh` → `GRAPHY_TENANT_OK` in 4.0 s (`ARMS OK: 6 arm(s) match the walk (store 26fdbfdb82a020f7)` after the six regions were re-rendered; the harness's own hub files — `AGENTS.md`, `GRAPH.md`, `*.walk.txt`, `drawings/` — are §132's known output, dropped, never committed) |
| the gate | `bash standalone_check.sh` → `arm regions OK` · `GRAPHY_STANDALONE_OK` — the arm regions verified inside it now; exit 1 from the verify is DRIFT with the diff's tail, any other exit is REFUSED with its line, never a clean zero |
| review | round 1: REVISE — B1 the walk moved (`_NoFcntl` → `MsvcrtFlock` in the seam) and the arm region did not, and the gate read green because it byte-checked the svg and never ran `arms --verify` (card 1 · the record the build product contradicts). Doored: the gate's tenant block runs `graphy arms … --verify` beside the svg and refuses drift by name; the regions re-rendered from the rebuilt store. Adjacent, doored: severance's def scan read only `tree.body`, so the deleted `_NoFcntl` under `except ImportError:` counted as no deletion — `_defs` now walks module-level `try`/`if`/`with`/`for`/`while`, the selftest fixture's deleted def sits under a `try`. Eliminated: the CI `-k` expression is a proxy for a `lock` marker (one unrelated `host` test rides along, green). Round 2: REVISE — B2 the red-first row said 4 failed and the re-derive says 6 (card 1 · the record contradicts the run; the row now carries its command). Folded from its non-blocking list: the gate's verify line swallowed stderr, so a REFUSED verify read as DRIFT — exit 1 is DRIFT with the tail, any other exit REFUSED with its line; README names every lock site. Found folding it: the first cut assigned the verify's output in a plain `X="$(…)"`, which under the gate's `set -e` killed the script on any non-zero exit with no line at all — the round-1 door had been proven red by hand, never through the gate; `|| ARMS_RC=$?` keeps the exit, and both branches are now proven through the gate itself (HEAD's stale SEAM.md → `arm regions DRIFT` + the two moved lines, exit 3; a bad partition → `arm regions REFUSED — the verify never ran (exit 2)`). Carried: `_defs` does not walk a module-level `match` or `except*` body (none in the engine today); the ci.yml comment says three tests where the step collects twelve. Round 3: **SHIP** — the ledger re-verified on its specimens (HEAD's arms → DRIFT exit 1 through the gate; `_defs` collects a class and its method under `if` under `except` under `with`, `finally`, `for`/`else`, `while`; the red-first command run verbatim → 6); every §134 number re-derived against its command; no `LOCK_SH`/`LOCK_NB` caller, every lock file opened writable, no stale reader of the deleted names; `review.py --diff 3b8f644` 16 checks, 0 findings. Folded: the DRIFT branch printed `tail -3` of the verify, which dropped the header and the arm's name when two arms drifted — it prints the whole output now. Carried: rounds 1 and 2 were both card 1 (a record the run contradicts); a row's re-derive command run by `review.py` is the design that makes the class mechanical |

## 135 · A VERB CLOSES THE STORE IT OPENED — every door left its sqlite handle open until the process died, and on Windows a file a process holds cannot be renamed or replaced, so the rename after an eat, the recompile a stale refusal advertises and a rebuild's landing all read `WinError 5`; every verb closes on every path now, and a tracker over `sqlite3.connect` proves it on any host (2026-09-14 · graphyos issue 124)

Split from #88 and measured on the first production tenant's platform ([run 34855052453](https://github.com/omnislash157/graphyos/actions/runs/34855052453)): `eat` then `.graphy.rename(…)` → `PermissionError: [WinError 5]`; `compile_store` over a store a reader still held → the same at `_sync_then_replace`; a rebuild's generation rename the same. POSIX never said a word — a held file renames fine there, and CPython's refcount closed most handles at the handler's return, which is exactly why no floor test had ever asked.

- `SQLiteStore` is a context manager (`__enter__` · `__exit__` → `close`, idempotent); `open_for` closes the store it opened before it refuses stale or unmeasurable, so a refusal never carries the handle out in its traceback. Every CLI verb that opens a store (`walk` · `arms` · `draw` · `descend|blast|explain` · `recon` · `pillars` · `traversals` · `history`) runs its body under `with store:`; `check` closes the store it opened only to ask whether it opens; `bridge` closes both sides in a `finally`, and `open_sides` closes the sides already open when a later one refuses; `mcp.serve` closes the server's one store when its input ends (`Doors.close`, and the verb holds it under `with`); `harness.run`, `showcase`, `cross_substrate.main`, `query.main` and `shell.gate.main` the same. The mechanics: a re-indent of each handler's remainder under `with store:` — no line of any body changed.
- The door is `tests/test_store_lifecycle.py`: `sqlite3.connect` is wrapped for the test's life and every connection it handed out is asked `SELECT 1` after the verb returns — a closed one raises `ProgrammingError`, an open one is the finding, by verb. Twelve verbs, `eat` followed by the rename the issue measured, the MCP server, the stale refusal, and the context manager. The tracker holds a reference to every connection, so refcount cannot close one behind the test's back: the test measures the explicit close, which is the only close Windows honours in a long-lived process.
- Found building it: the two tests that first borrowed helpers from `tests/test_federated_store.py` (`from tests.…`) passed under `python -m pytest` (the cwd is on `sys.path`) and under `workflows.py --run … floor` (`CI LOCAL OK`), and failed on every CI runner under the bare `pytest` binary (`ModuleNotFoundError: No module named 'tests'`, run 34881411756) — class ⑤, the local runner is not the runner. Rewritten over their own eaten repo; the red-first row below runs `python -m pytest` for the opposite reason: the `pytest` binary resolves `graphy` through the venv's editable install to the LIVE tree, so an archived engine under it reads 16 passed on the unfixed world.
- Round 1 found the same class through the refusals BEFORE the stale check: the digest raising on a shard file the store was compiled from that is gone, and `SQLiteStore.__init__`'s own four refusals after its `sqlite3.connect` (no generation row, a foreign format, no digest — each advertising the very recompile a held handle refuses on Windows). Everything after the connect in the constructor, and everything after the construct in `open_for`, now runs under one guard that closes on any exception; the case `…_when_open_for_refuses_before_the_stale_check` is red on the round-1 engine (`1 of 1 … still open`) and green now. `tenants/graphy/blast_pr.py`, the one `open_for` caller outside the graphy corpus the walk cannot name, holds its store under `with` too.
- The CI `store-windows` job runs the file and three of the four tests the issue measured red as its third mark (`the handle mark`), beside the durable and lock marks; the fourth, `test_rebuild`'s pruned-lane test, gets past its rename there and fails downstream on #88's separator class, so it is not claimed.

| check | result |
|---|---|
| red first | `S=$(mktemp -d) && git archive 8b80572 engine \| tar -x -C $S && cp engine/tests/test_store_lifecycle.py $S/engine/tests/ && (cd $S/engine && "$OLDPWD/.venv/bin/python" -m pytest -q tests/test_store_lifecycle.py)` → 17 failed of 17 on the engine before the change (every verb `1 of 1 sqlite connection(s) still open`, `eat` 2 of 3, the refusals 1 of 1 and 1 of 2, no context manager) |
| the door, here | `cd engine && ../.venv/bin/python -m pytest -q -k "a_verb_leaves_no_store_open"` → 16 passed · the whole file 17 passed · the handle-mark step's argv (the file + the three named tests) → 20 passed |
| the platform | `gh workflow run ci.yml --repo omnislash157/graphyos --ref scratch/124-handles` → run 34882890712 (the fourth dispatch; its head is the tree after round 1's fix — this tree — `git diff <head> --stat -- engine .github` empty): every job green — `floor (3.10)` · `floor (3.12)` · `gate` · `store-windows`, the handle mark `..........s.........` 19 passed · 1 skipped. Run 34881899843 (the third dispatch, the tree round 1 reviewed): `floor (3.10)` · `floor (3.12)` · `store-windows` green — the durable mark 3 passed, the lock mark `.sss........` 9 passed · 3 skipped, the handle mark `..........s........` 18 passed · 1 skipped (`traversals` refuses before it opens a store where duckdb is absent, and the dev extra carries none — the skip is named, never a silent green; here the estate venv has it and the case runs). The gate job on that run read red on exactly the two unfilled `_ROW` tokens of this section while it was being written — the template-token door doing its job, no engine finding. The two dispatches before it are the record's: 34881411756 — the two tests importing `tests.…` red on every runner, the platform's other reds the same two plus `traversals` measuring nothing; 34881645621 — `traversals` measuring nothing where duckdb is absent, and `test_rebuild`'s pruned-lane test past its rename and red seven lines later on an `EAT DROPPED` line Windows does not print, which is #88's separator class and is commented there, not claimed here |
| the floor · the CI floor job here | `cd engine && ../.venv/bin/python -m pytest -q` → all passed, 2 skipped · `cd engine && ../.venv/bin/pytest -q` (the binary, as CI) → exit 0 · `python3 workflows.py --run .github/workflows/ci.yml floor` → `CI LOCAL OK: 5 step(s)` |
| production | `bash engine/tenants/graphy/rebuild.sh` → `GRAPHY_TENANT_OK` in 4.01 s wall (`/usr/bin/time -f '%e'`, the round-1 tree), `ARMS OK: 6 arm(s) match the walk (store 5577b094d4cc145b)`, `docs/pillars.svg` redrawn (`CLI 148→149`, `DOORS 40→41` edges — the walk moved: `bridge` +`close_sides`, `mcp.Doors` 11 → 14, `SQLiteStore` 10 → 12) and the six regions re-rendered by `graphy arms`; the harness's hub files dropped as §132 names. The record's own class ④, caught by the gate before any review: the second rebuild of the session was run through a grep that kept `ARMS DRIFT` and dropped the exit — it had stopped at the drift (the regions were still HEAD's) and never redrew the svg, and this row's first draft said `GRAPHY_TENANT_OK` off the first rebuild of the session; `standalone_check.sh` read `pillars svg DRIFT` and the row was re-derived from a full run |
| the gate · the battery | `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` · `python3 review.py --diff 8b80572` → `REVIEW OK: 16 check(s) · 0 finding(s)` · `bash release.sh --check` → OK |
| review | round 1: REVISE — B1 `open_for`'s refusal path was not complete: the fix closed the two stale refusals and left the two before them open — the digest raising on a shard file gone, and `SQLiteStore.__init__`'s four refusals after its `sqlite3.connect` (class ⑥, the diff's own class through a different hole; repro: the tracker over a deleted `nodes.json` and over a store with its `input_digest` row deleted, `1 of 1 still open` each). Doored: `…_when_open_for_refuses_before_the_stale_check` in the same file, red on the round-1 engine; the constructor and `open_for` each guard everything after the open under one `except BaseException: close; raise`. B2 the record said four measured tests and 20 passed where the step runs three and its argv read 19, and one platform row joined two run ids (card 1 · ④); the three lines re-derived from the step's argv. Eliminated: `blast_pr.py` held its store (outside the graphy corpus, so the walk could not name it — a grep finding; closed under `with` anyway); the `pytest`-binary trap on the red-first row (a property of this box's editable install, named in the row); `mcp.open_tools` leaking if `Doors.__init__` raised (nothing in it raises on an accepted store) |

## 136 · THE MCP FACE RUNS THE CLI'S FRESHNESS CHECK PER CALL — the server pinned the store it booted on and answered confidently from a generation the CLI refused as STALE, or one the descriptor no longer named; every tool call now opens what a fresh `graphy <verb> --tenant` would open, and refuses in the one line the CLI prints (2026-09-14 · graphyos issue 97)

Measured on the first tenant's Linux seat, 2026-09-13: `graphy history … --tenant …` → `HISTORY REFUSED: compiled store … is STALE`, and the MCP `hunt` over the same tenant thirty seconds later answered 40 nodes, many of them paths deleted months earlier, with a third generation in the server's own instructions — three server processes with different boot times alive on one box. The CLI opened its store per invocation and ran `open_for`'s comparison each time; the server opened once at boot and never asked again.

- The comparison is one function on every face: `federated_store.check_fresh(store, roster, tenant=…, tenant_id=…, on_stale=…)` — the live inputs digested against the store's row, and when they moved, the live generation against the served one; returns fresh, refuses `StoreError` with the words every verb prints, or under `warn` says so on stderr and returns. `open_for` runs it on the store it just opened and closes on its refusal exactly as §135 left it. The server never runs it on a held store: before every tool call `mcp.Doors._assert_fresh` takes `input_signature` — the stat (size · mtime_ns · inode) of every file the digest reads, the store file and the descriptor — and while it equals the signature the served store was opened under, the call is served as is; when any moved, the server does what `graphy <verb> --tenant` does and nothing less: the descriptor re-read (`_load_tenant`), the roster derived (`_roster`), `open_for` on a fresh connection (which refuses STALE in the CLI's words, or warns), the old store closed once the new one is open. An unmoved store costs a handful of stats per call; a moved one the hash and a `sqlite3.connect` (the hash is 7.6 ms over the graphy tenant's seven shards: `../.venv/bin/python -c "import time; from graphy import cli, federated_store as fs; t=cli._load_tenant('tenants/graphy/tenant.json'); r=cli._roster(t); t0=time.perf_counter(); fs._compute_input_digest(r, tenant=t); print(round((time.perf_counter()-t0)*1000,1))"`). The signature is taken over the new roster's paths before the open and recorded only after it succeeds, so a write between the two moves the next call, never absorbed; a refusal leaves the server on the store it had and the next call tries again.
- Found by the production proof, not the fixture: on the plugin's own shape (`graphy mcp --repo`) a re-eat lands the next generation in a sibling `substrate.gen-…/` and renames the descriptor onto it (§128), so the served shards never move, the digest still matches, and the first cut kept answering from the generation the descriptor no longer named while the CLI served the new one — the issue's second paragraph through a different hole (class ⑥). The descriptor the server was booted from (`Doors.descriptor`, passed by the verb as `--tenant` or the one `--repo` resolves) is in the signature, so a landing is followed on the next call and stderr names the reopen once.
- Review round 1 found the same class through the swap at the SAME path: the first fix re-checked the store it held, and `graphy build` — the refusal's own advice, and what `shell install`'s re-mint runs — lands by `os.replace` at the store's own path, so the server kept its handle on the unlinked file, compared live shards against that file's row, and refused every call until restart while the CLI answered (the reviewer's real-process repro: shard moved → `HUNT REFUSED … STALE` · `graphy build` rc 0 · `graphy explain` rc 0 · the server `REFUSED` on every call). Its sibling by the walk of the reopen's early return: the reopen was keyed on the descriptor's data home alone, so a roster narrowed in the descriptor in place (a lane dropped, the store rebuilt) was never followed — the server answered a node the CLI said did not exist. Both fall to one design: a long-lived reader never checks a held handle; it opens what a fresh invocation opens, keyed by everything the invocation reads. The card's ⑥ carries the specimen.
- One copy of the refusal line: `federated_store.refused(verb, exc)` — flattened, with the rebuild hint — replaces the nine `_flatten(f"… REFUSED: {exc} — rebuild the store with \`graphy build\`")` sites in `cli.py` (`walk` ×2 · `bridge` · `arms` · `draw` · the doors · `pillars` · `mcp` · `history`), and the MCP tool's error text is the same call. The floor's stale case runs `graphy explain` on the same tenant the same minute and asserts the tool's text equals the CLI's last stderr line.
- The doors: `tests/test_mcp.py` — `…_refuses_a_store_that_went_stale_after_boot` (the done line: boot fresh, append a node to a served shard, `hunt` · `blast` · `explain` each refuse with `refused(VERB, <the StoreError open_for raises>)`, `explain`'s text byte-equal to the CLI's line), `…_re_checks_freshness_only_when_an_input_moved` (two calls over an unmoved store hash once; a same-byte rewrite moves the stat and re-hashes without a warning; `warn` says `is STALE` once and answers), `…_follows_the_descriptor_a_landing_renamed_onto_a_new_generation` (a git repo eaten, a source file added, re-eaten: the next `hunt` names the new symbol from the landed generation, the old home still on disk for a reader that began on it, stderr `reopened on generation <new> (was <boot>)` once), and round 1's two red cases `…_answers_again_after_the_build_its_own_refusal_prescribes` (stale → `graphy build` → the CLI answers → the next call answers and names the node the build added) and `…_follows_a_roster_narrowed_in_the_descriptor_in_place` (a lane dropped from the descriptor, the store rebuilt: the CLI has no such node and neither does the server, whose roster is the descriptor's); `tests/test_store_lifecycle.py` `test_the_mcp_server_closes_the_store_it_reopened_from` (the tracker: the store served before the reopen is closed, one connection held after it, none after `close`).
- The record's own class ④, again: the first rebuild of the session stopped at `ARMS DRIFT` (2 of 6 — the walk moved: `federated_store` +`check_fresh` · `input_signature` · `refused`, `mcp.Doors` 14 → 17, `open_for`'s dependents 21 → 25) and exited 1; read this time, the regions re-rendered, and the production row below is the full run that followed. The round-1 fix moved it again (`mcp.Doors` 17 → 16: the descriptor follow folded into `_assert_fresh`), the same stop, the same re-render.

| check | result |
|---|---|
| red first | `S=$(mktemp -d) && git archive 396bd0d engine \| tar -x -C $S && cp engine/tests/test_mcp.py $S/engine/tests/ && (cd $S/engine && "$OLDPWD/.venv/bin/python" -m pytest -q tests/test_mcp.py)` → the three new cases FAILED, the three that stood before pass (the stale one on the old engine: `isError` False — the server answered). Round 1's two cases were red on the round-1 tree by the reviewer's own probes (`r97r1/test_r97_probe.py`: `…build_in_place…recovers` and `…roster_narrowed…` FAILED, 2 of 4) and are green now |
| the door, here | `cd engine && ../.venv/bin/python -m pytest -q -k "mcp_refuses_a_store_that_went_stale_after_boot"` → 1 passed · `tests/test_mcp.py` 8 passed · `tests/test_store_lifecycle.py` 18 passed |
| production | `cd engine && ../.venv/bin/python <scratch>/prod_proof.py <a fresh clone of pallets/click, eaten>` — `graphy mcp --repo` as a real process: boot 9c85e1076441af4a, `hunt Command` 1.4 ms then 0.3 ms; a source file added and the repo re-eaten (`EAT OK`, 0.3 s) → the next `hunt later` answers `click://func/click._late.later` from generation a5766390bef662e6 in 3.0 ms and `graphy explain click._late.later --tenant …` answers the same; a node appended to the served `click_graph/nodes.json` in place → the next `hunt` `HUNT REFUSED: compiled store for roster ['click', 'history'] at … is STALE …` in 16.3 ms, byte-equal (verb aside) to `graphy explain`'s stderr the same minute, exit 2; the bytes restored → answers again; the server exits 0 on end of input with one `reopened on generation` line on stderr. `PROD PROOF OK` in 0.93 s wall (0.54 s on the round-1 fix). The reviewer's real-process repro on a fresh clone, on the round-1 fix: shard moved → `HUNT REFUSED … STALE`, `graphy build` rc 0, `graphy explain` rc 0, the server's next two `hunt`s answer. And `bash engine/tenants/graphy/rebuild.sh` → `GRAPHY_TENANT_OK` in 4.09 s wall (`/usr/bin/time -f '%e'`, the round-1 fix), `ARMS OK: 6 arm(s) match the walk (store 6168578d3cf543b9)`, `docs/pillars.svg` redrawn; the harness's hub files and draw bands dropped as §132 names (#128) |
| the floor · the CI floor job here | `cd engine && ../.venv/bin/python -m pytest -q` → exit 0, 2 skipped · `cd engine && ../.venv/bin/pytest -q` (the binary, as CI) → exit 0 · `python3 workflows.py --run .github/workflows/ci.yml floor` → `CI LOCAL OK: 5 step(s)` |
| the gate · the battery | `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` · `python3 review.py --diff 396bd0d` → `REVIEW OK: 16 check(s) · 0 finding(s)` · `bash release.sh --check` → OK |
| review | round 1: REVISE — B1 the server never recovered on the path its own refusal prescribes: the first fix ran `check_fresh` on the store it held, and `graphy build` lands by `os.replace` at the store's own path, so the held handle on the unlinked file compared live shards against the old row and refused every call until restart while the CLI answered (class ⑥, the issue's own class through the swap at the same path; repro: a real `graphy mcp --repo` process over an eaten click — shard moved → REFUSED · `graphy build` rc 0 · `graphy explain` rc 0 · the server REFUSED on every call); the sibling by the walk of the reopen's early return: a roster narrowed in the descriptor in place was never followed (`tools.roster` the boot roster against the descriptor's). Fixed by the reviewer's smaller design: a moved signature means the descriptor re-read, the roster derived, `open_for` on a fresh connection, swap, close — never a check on a held store; doored as two red cases in `tests/test_mcp.py` and the tracker case in `tests/test_store_lifecycle.py`; the card's ⑥ carries the specimen. Non-blocking, taken: the module docstring's "pinned for the session" line beside the new rule (④), the catch set on the reopen (the CLI's five, so the faces print one line on every refusal class), the tracker assertion on the reopen's close. Eliminated: the stat proxy (0 of 200 same-size back-to-back rewrites shared an `mtime_ns`; every landing changes the inode), the lazy `graphy.cli` import (the established pattern; no cycle), `initialize`'s boot generation (every answer carries its own) |
| review (round 2) | round 2, fresh with the ledger: SHIP — B1 and its sibling re-verified on their own specimens (the round-1 probe file 4 of 4, the real-process repro on a fresh clone: refused · `graphy build` · the CLI answers · the server's next two calls answer, one `reopened` line). The fix refuted through eight probes, each read: inputs whose mtime keeps moving (`walk`'s traversal rows, `blast`, a journal append) hash once — neither traversals nor the journal is in the signature, and neither is a digest input; a descriptor unlinked mid-life refuses every call by name with the old store still held and open, restored → answers with the old handle closed and no `reopened` line; `warn` across a build in place says `is STALE` once and `reopened` once; one connection held through every refusal and swap; a roster narrowed moves the store file and the old handle is closed; a symlinked shard edited through the link refuses STALE; two landings with no call between → the next call answers from the newest generation; nothing caches on the old store object (`Counting` per call, `traversal.door` keyed by the swapped tenant's home, `nbr_cache` function-local, `history` live). Whole diff cold: the nine sites exact (the one other hint spelling, `_cmd_recon`'s `build the store with`, predates the diff), no test asserts the old literal, severance clean, every §136 number re-derived. Eliminated: the first call after boot reopens once because the boot signature is not taken in `open_tools` (an 8 ms `sqlite3.connect` once per server; carried in the commit message); a `TenantError` mid-life carries the rebuild hint on the MCP face where `_cmd_door` prints it bare (wording); `.gitignore`'s `.claude/worktrees/` line rides along. A question for the board, not this rung: a long-lived server holding a store between calls is what makes `graphy build`'s `os.replace` refuse on Windows (#124's class on the CLI side) — open-per-call would make it impossible at 8.1 ms per call against 0.19 ms for the signature; filed |

## 137 · A HOUSE REBUILD DRIVER STAGES AND LANDS A GENERATION WITH TWO VERBS — the first client's driver ran the CLI verbs itself and unlinked `tenant.json` up front, so for a 423.7 s rebuild every `blast` refused `tenant descriptor not found` and the MCP servers were stopped; `graphy generation stage` and `graphy generation land` are the #98 helpers as verbs, and the door answers the same at every step (2026-09-14 · graphyos issue 133)

Measured by the first client's Windows production tenant, 2026-09-14. #98 (§128) landed the staging and the landing inside `eat` and `rebuild.rebuild`; that tenant calls neither — its house script drives the verbs, which is exactly the shape `rebuild.py`'s docstring records as the reason the lane exists.

- `graphy generation stage --substrate <abs> --tenant <descriptor> [--placed <slug>]…` → `cli.stage_generation`: the next generation seeded beside the served one (every shard's splice, a placed lane whole), the staged descriptor's path printed for `init --tenant <staged> --data-home <stage>`; a substrate that is itself a generation refuses. `graphy generation land --stage <abs> --tenant <descriptor> --tenant-id <id> [--placed <slug>]…` → the stage must be a generation of a substrate (`generation_of`), the staged descriptor must exist and name the stage, and the stage's store is opened through `open_for` on the staged descriptor — FRESH — before the rename; `cli.land_generation` then renames and discards the generations older than the one replaced. A stage `build` never landed a store in refuses by name; so does landing the served generation again. The verb imports nothing a house cannot: the two helpers are the ones `eat` and `rebuild` run.
- `served_previous(sub, desc)` and `staged_descriptor(desc)` are the one spelling of what a landing replaces and where the next descriptor sits — `stage_generation` and the verb ask the same function, so `stage` and `land` cannot disagree on the family (review round 2 of #98's rule, one copy).
- The door: `tests/test_rebuild.py::test_GREEN_generation_verbs_keep_the_door_answering` — a repo eaten once, a symbol added and committed, then the verb sequence with `blast core.mod.run` polled through the served descriptor after every step (stage · smash · init · converge · build): every answer byte-equal to the first with the generation stamp aside; `land` before `init` and before `build` refused with the served generation untouched; after `land` + `check` the answer names the added symbol, the replaced generation is kept one back, the staged descriptor is gone; landing the served generation, landing a non-generation and staging a generation each refuse by name.
- Found building it: the battery's `generation-identity` check caught a `.gen-` literal in a refusal string — the second spelling it exists to refuse — before any reviewer; reworded. The docs name the sequence in CLAUDE.md's taps (a row) and the engine map's verb list, and in `rebuild.py`'s docstring.

| check | result |
|---|---|
| red first | `S=$(mktemp -d) && git archive 396bd0d engine \| tar -x -C $S && cp engine/tests/test_rebuild.py $S/engine/tests/ && (cd $S/engine && "$OLDPWD/.venv/bin/python" -m pytest -q tests/test_rebuild.py -k generation_verbs_keep_the_door_answering)` → FAILED: `argparse.ArgumentError: … invalid choice: 'generation'` — the verb did not exist |
| the door, here | `cd engine && ../.venv/bin/python -m pytest -q -k "generation_verbs_keep_the_door_answering"` → 1 passed |
| production | `bash <scratch>/wt133_house_rebuild.sh <engine> <a fresh clone of pallets/click, eaten> click <clone>/src click.core.Command <clone>/src/click` — a house driver of public verbs only (stage · smash · init · a scheme index from ring.json · converge · build · land · check) with `blast click.core.Command` polled every 0.2 s through the served descriptor: `HOUSE REBUILD: 0.7 s wall · 4 poll(s) of blast · 0 refusal(s) · 1 distinct answer(s)`, `GENERATION LANDED … replaced <the eaten generation>, kept for a door that began on it`, `CHECK OK`, `HOUSE PROOF OK`. The client's 5 s poll over 423.7 s is the same ratio |
| the floor | `cd engine && ../.venv/bin/python -m pytest -q` → exit 0, 3 skipped |
| the gate · the battery | `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` · `python3 review.py --diff 396bd0d` → `REVIEW OK: 16 check(s) · 0 finding(s)` (severance 0 over 3 changed files) |
| review | round 1: SHIP — cold, in the worktree the rung was built in (base 396bd0d, the worktree's one commit — rebased onto main at the landing, so its own sha is not on main; the interpreter check printed the worktree's own engine). The done block re-run; the walk re-taken on a store rebuilt there (`stage_generation` ← `_cmd_generation` · `_eat_run` · `rebuild.rebuild`; `land_generation` ← `_cmd_generation` · `_eat_stage`; `served_previous` · `staged_descriptor` ← `stage_generation` and the verb only; `served_data_home` → 13 callers, untouched); the argv door proven load-bearing by mutating the new taps row's flag (`advertised-argv-parses CLAUDE.md:180` fired, restored). Refuted and held: a `graphy mcp` process opened before a verb-driven stage → land answers the same `blast` after it, the replaced generation still on disk; an abandoned stage is discarded by the next landing and `land --stage <abandoned>` refuses by name; a stage superseded by a newer `stage` before it landed refuses `no staged descriptor` (fail-closed, the served generation untouched); `--placed` spells `f"{slug}_graph"` as `rebuild.Lane.dirname` does; no `.gen-` or generation spelling outside `_shared.GENERATION_IDENTITY`. Non-blocking: this section's title carried a clause after the date that `release.sh`'s changelog derive silently drops — retitled at the landing, and the drop-as-skip is filed as #135 (five older sections are dropped the same way); the scratch driver's "distinct answers" key does not strip a stored traversal's path, so a second run reads 2 distinct under a green verdict (a scratch tool, not a proof); a superseded stage stays on disk until the next landing; a long-lived `graphy mcp` not following a landing — answered by #97, which landed first (the server reopens on the descriptor's new data home on its next call) |
| the landing | built in a worktree beside #97 (the pipelined rung), one commit rebased onto #97's main (6a2f371) with the record's two appended sections kept in order, the title retitled to the derive's shape, CHANGELOG.md re-derived (123 entries — this section now carried); on main: `bash engine/tenants/graphy/rebuild.sh` → `GRAPHY_TENANT_OK` in 4.32 s wall (after the known `ARMS DRIFT` stop and re-render: `mcp.Doors` and `cli` moved under #97 and this rung), `ARMS OK: 6 arm(s) match the walk (store 87582c852ad66d66)`, `docs/pillars.svg` redrawn; the floor under `python -m pytest` and the `pytest` binary, `standalone_check.sh`, `review.py --diff 6a2f371`, `release.sh --check` and `workflows.py --run … floor` re-run on main before the push — nothing from the worktree ships without that run |

## 138 · A CP1252 CONSOLE OR PIPE NEVER CRASHES A VERB THAT DRAWS — on windows-latest a piped `graphy eat` printed `EAT OK` and exited 1 on the first glyph cp1252 cannot encode, and the first client's box needed `PYTHONUTF8=1`; every entry point reconfigures its own streams to utf-8 before the first line, so the workaround is the engine's (2026-09-14 · graphyos issue 123)

Split from #88; measured on windows-latest (`omnislash157/graphyos` run 34855052453 — the private repo's CI, not the board's: `test_provision.py::test_RED_a_failure_line_is_the_last_line_when_both_streams_share_a_pipe`, `assert 1 == 0` after `EAT OK`) and on the first client's Windows Server box on `graphy draw`, masked there by `PYTHONUTF8=1`. Reproduced here without Windows: `PYTHONIOENCODING=cp1252` gives a Linux process the same streams a Windows pipe gives, and `explain graphy.cli.main` died on `│`, `draw --symbol` on its canvas, `eat` on the `←` in `_eat_stage` — after `EAT OK`, exit 1, the issue's shape exactly.

- `_shared.utf8_streams(*streams)` (no streams: stdout and stderr): every stream whose encoding cannot encode `_shared.GLYPHS` — the drawings' box and arrows, the doors' hops, the receipts' separators — is reconfigured to utf-8 with its own error handler kept; one that refuses the encoding is reconfigured to `errors=replace`; utf-8 and a stream with no `reconfigure` (a capture) are left alone. `cli.main` calls it before it wraps stderr, so every verb and every in-process host of `cli.main` (`eat` → `check` → `harness`, `showcase`, `shell install`) is covered once, and the re-entrant path returns early as before; the entry points that do not pass through `cli.main` — `graphy.lightning`, `bloodhound`, `reseed_graph`, `graphy.query`, `graphy.shell.gate`, `graphy.reseed` — call it first. The walk: `blast graphy._shared.utf8_streams --depth 2` → own callers those seven `main`s, hop 2 `_eat_stage` · `remint_history` · `showcase.showcase`.
- Found building it, by the subprocess test: stderr's default handler is `backslashreplace`, so a probe that honoured the handler never crashed stderr but left it cp1252 beside a utf-8 stdout, and the one pipe the two streams share carried two encodings (`0x97`, a cp1252 em-dash, in `EAT: harness exited 2 —`). The rule judges the encoding only. And `TextIOWrapper.reconfigure(encoding=)` resets `errors` to strict unless it is passed back, which the unit test caught against the docstring's claim that the handler is kept.
- Found by review round 2: `lightning/ripgrep.py` warned `ripgrep not found … —` at module level whenever rg was absent — windows-latest's condition, and the new CI step's — so the em-dash reached a cp1252 stderr while `graphy.lightning` was still importing, before any `main` could run `utf8_streams`. The warning is `warn_no_rg()` now, once, from the first search that takes the Python fallback; the subprocess test's lightning leg sets `GRAPHY_RG` to a path that does not exist, so every box runs the runner's condition and asserts the warning still prints, once, in utf-8; and the battery gained `import-time-glyph` — every print, logger call and `sys.std*.write` that runs at a module's import (the module body and the if · try · with · for · while · match · class blocks under it, never a def or a lambda) whose string literals carry a non-ASCII character, proven red on five shapes and green on the same calls inside a def, and naming exactly `ripgrep.py:42` on 29cf376's engine.
- The README's Windows paragraph no longer names `PYTHONUTF8=1` as the workaround; the `store-windows` job gained a fourth mark — the subprocess test and the pipe test that was the red — so the claim is run on the platform the issue names, not only simulated here.

| check | result |
|---|---|
| red first | `S=$(mktemp -d) && git archive 29cf376 engine \| tar -x -C $S && cp engine/tests/test_cli.py $S/engine/tests/ && (cd $S/engine && "$OLDPWD/.venv/bin/python" -m pytest -q tests/test_cli.py -k cp1252_console_never_crashes)` → 2 failed: `AttributeError: module 'graphy.cli' has no attribute 'utf8_streams'`; `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb7` — the pipe's bytes were cp1252 |
| the done block | `cd engine && PYTHONIOENCODING=cp1252 ../.venv/bin/python -m graphy draw --help >/dev/null` → rc 0 · `cd engine && ../.venv/bin/python -m pytest -q -k "cp1252_console_never_crashes"` → 2 passed |
| the surface | `PYTHONIOENCODING=cp1252` with `PYTHONUTF8` unset, stdout and stderr in one pipe: `graphy eat` rc 0 (`file` on the bytes: UTF-8 text) · `draw --symbol` rc 0 with the box glyphs · `explain` rc 0 · `graphy.lightning` · `bloodhound` · `graphy.shell.gate` rc 0; the issue's own red, `test_provision.py -k share_a_pipe`, green here under cp1252 and red against 29cf376's engine |
| the floor | `cd engine && ../.venv/bin/python -m pytest -q` → exit 0, 2 skipped |
| the gate · the battery · the record | `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` (after the tenant's rebuild: `GRAPHY_TENANT_OK`, `ARMS OK: 6 arm(s) match the walk`, `docs/pillars.svg` redrawn — the memory doors' new call into `_shared` is one more pillar edge: `graphy draw --tenant tenants/graphy/tenant.json --tenant-id graphy --corpus graphy --pillars --partition tenants/graphy/partition.json --lr --min-weight 2` prints `29 edge(s)` on this store and `28` on 29cf376's) · `python3 review.py --diff 29cf376` → `REVIEW OK: 16 check(s) · 0 finding(s)` (severance 0 over 9 changed files) · `bash release.sh --check` OK · `python3 workflows.py` → `WORKFLOWS OK: 5 file(s)` |
| review (round 1) | round 1: SHIP — cold. The done block re-run; the surface re-proven by the reviewer on a scratch repo eaten, showcased, `shell install`ed, its MCP door driven with `initialize` + `tools/call explain` + `tools/call hunt` and the gate fed hook JSON, every one under cp1252 in one pipe, every one rc 0 and utf-8 (`mcp.serve` writes `ensure_ascii=False`, so that line was the crash before and is utf-8 after). Refuted and held: the probe is complete — over every codec Python ships, the ones that pass `GLYPHS.encode` encode every non-ASCII literal in `engine/graphy`, so none passes the probe and dies on `×` · `≥` · `█` · an emoji; both tests red against 29cf376; `cp1252:replace` → utf-8 with replace kept, a `backslashreplace` stderr keeps its handler, a closed or `None` stream → `[]`; text buffered before a reconfigure would flush in the old encoding, and no path prints non-ASCII before the call (`_graphy_launch` prints only a refusal that exits); no CLI entry point outside the seven. Non-blocking: the stdin side of the same seam is untouched — `mcp.serve` iterates `sys.stdin` as text and the gate and the hooks `sys.stdin.read()`, so under a cp1252 pipe a utf-8 client's non-ASCII symbol or path decodes as mojibake (reproduced here: `hunt` of `José` over a cp1252 stdin answers about `JosÃ©`; filed as #136, the class is its own); CI never ran the fix on the platform — landed in this commit as the fourth mark, reviewed in round 2; an explicit `PYTHONIOENCODING=cp1252` is now overridden where `PYTHONUTF8=1` would not have — judgment, the issue's own wording; `GLYPHS` re-exported through `cli` for the tests' spelling; the two-function scratch repo's `harness exited 2` is pillars finding no orchestrator, pre-existing |
| review (round 2) | round 2, fresh with the ledger: REVISE — one blocker. B1: `graphy.lightning` · `bloodhound` · `reseed_graph` printed a cp1252 byte BEFORE `utf8_streams` ran — `lightning/ripgrep.py:42`'s import-time `logger.warning("ripgrep not found … —")`, emitted whenever rg is absent, which windows-latest is (the runner image ships none and `ci.yml` installs none), so the new CI step would have been red on the platform it was added for. Repro: `cd engine && GRAPHY_RG=/nonexistent ../.venv/bin/python -m pytest -q "tests/test_cli.py::test_GREEN_a_cp1252_console_never_crashes_draw_and_eat_in_a_subprocess"` → `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x97 in position 41`; the door: `GRAPHY_RG=/nonexistent PYTHONIOENCODING=cp1252 python -m graphy.lightning g --path <dir>` → rc 0 with `0x97` in the bytes; `bloodhound --help` and `reseed_graph --help` the same byte. Class: the card's ⑤ environment — round 1 held "no path prints non-ASCII before the reconfigure" on a box that has `/usr/bin/rg`; the round-1 surface run was not load-bearing for the no-rg branch. Walk: `blast graphy.lightning.ripgrep` → `blitz_hunt` imports it, `lightning/__init__` imports `blitz_hunt`, so `python -m graphy.lightning|bloodhound|reseed_graph` all pay the import before `main`. Fix: the warning lazy (`warn_no_rg`, once, from `python_matching_files`); the test's lightning leg under `GRAPHY_RG=<nonexistent>` with the warning asserted once and in utf-8 (red on the repro first: `0x97`); the door: `review.py` `import-time-glyph`, red 5 · green 0 on its fixture, 0 findings on this tree, `ripgrep.py:42` on 29cf376's. Re-verified after: the three doors under cp1252 with no rg → rc 0, `file` says UTF-8, the warning printed once from the search and not from `--help`. Non-blocking, taken: §138 named the CI run without its repo (it is the private repo's run) — named; "28 → 29" pillar edges re-derive only with the rebuild's flags — the command is in the cell now. Named and left: `test_provision`'s pipe test opens its pipe `text=True` without an encoding, so on Windows it decodes utf-8 bytes as cp1252 and passes on ASCII prefixes — it is the issue's own red, not a proof of the bytes there (the subprocess test beside it is); `workflows.py --run ci store-windows` cannot run here (windows-latest) — the step parses, both node ids collect |
| review (round 3) | round 3, fresh with the ledger: SHIP — round 2's specimen re-verified dead under `GRAPHY_RG=/nonexistent PYTHONIOENCODING=cp1252` with both streams in one file: `graphy.lightning` bare · `--containers` · `--cooccur` rc 0, UTF-8, the warning once; `--help` rc 0, none; `bloodhound` and `reseed_graph` rc 0, UTF-8, none (neither takes the fallback); the gate fed hook JSON rc 0. Stronger than the AST door: every one of the 77 modules under `engine/graphy` imported in its own subprocess under cp1252 with no rg — none logs, prints, `warnings.warn`s or `basicConfig`s a non-ASCII byte at import through any path. `blast warn_no_rg` → `python_matching_files` → `Lightning.hunt`, the one caller, and all three fallback branches of `hunt` route through it; the once-flag breaks no test. The walker proven on scratch fixtures: walrus · ternary · comprehension · f-string · `try/finally` · `except` · `match case` · `for … else` · `if __name__` all caught, a class body inside a def and a lambda not. Docstrings match code. Non-blocking, filed: the walker sees a compound statement's blocks but not its header expressions or a def's decorators and defaults — seven shapes missed, zero on the live tree (#137); the parent's side of the seam — `refresh._prove` and `farm.farm_one` decode their `graphy` children with the locale, mojibake on Windows now that the child writes utf-8, 17 `text=True` sites without an encoding (#138); the advertised `rg … \| graphy.lightning --files-from -` pipe crashes on a file outside the cwd, pre-existing on 29cf376 (#139). Named and left: `test_provision`'s pipe test decodes `text=True` on Windows and passes on ASCII asserts — the issue's red, the subprocess test beside it the bytes proof |
| the landing | one commit on main: `bash engine/tenants/graphy/rebuild.sh` → `GRAPHY_TENANT_OK` in 4.12 s wall (after the known `ARMS DRIFT` stop and re-render: `_shared` gained `utf8_streams`, `lightning.ripgrep` gained `warn_no_rg`), `ARMS OK: 6 arm(s) match the walk (store bffeb29661bb2b38)`, `docs/pillars.svg` redrawn; the harness step's private-language draw region and its untracked products reverted before every gate run (#108 · #128); floor · gate · battery (17 checks) · `release.sh --check` · `workflows.py` · `burden.py` (wheel 363,395 B) · `census.sh` green on the final tree |

## 139 · A FUNCTION REFERENCED AS A VALUE MINTS AN EDGE — `blast` answered a confident zero for all 26 CLI verbs and every callback in every roster, because `python_ast` minted an edge only for a call; a name read as a value — a dispatch table, a callback argument, a decorator's argument, a default — is `references` now, bound through the scope that binds it, declared `DEPENDS`, in both shipped producers (2026-09-14 · graphyos issue 94)

Found by dogfooding this engine on itself (#73's post-commit blast): `graphy blast graphy.cli._cmd_check` → `dependents=0 own=0 ring=0` on 7de5037's store for every `_cmd_*` handler, because each is wired `p.set_defaults(handler=_cmd_check)` and called once, dynamically, at `return handler(args)`. Not #69's silence (an edge the door declined) — the edge was never minted, so nothing could name it. A framework-heavy repo routes most of its entry points this way; those are the symbols a stranger most wants to blast.

- `ir.EDGE_TYPES` gains `references`; `PYTHON_AST_RELATIONS["references"] = (DEPENDS,)` — blast walks it reversed, descend does not (a descent through every callback would say something vaguer than "what this arrives at"). The TypeScript vocabulary inherits both. The doors' fallback constants (`doors.BLAST_RELATIONS`, the #68 set) are untouched: a shard minted before this change carries no `references` and answers exactly as it did, and a shard nobody declared never walks a type its producer did not mean. The word already exists on one client's `pg_schema` lane (§113: `references 42`); `fold_relations` refuses two lanes declaring one type differently, so a roster holding that lane declared beside a Python lane refuses at `build` by name — the law working, named here because it is a change for that roster.
- `python_ast._scan`: the same level-order pass (every push unchanged, two flags added — the visit-count test still counts pops as nodes minus leaves) collects every name read as a value whose head the module's own scope binds (`_module_bindings`: a tracked def or class, a module-level import alias) and that no scope between the reader and the module rebinds — the module's own top level and the class body around a class-level read (`_shadow_in`: an assignment, a for/with/except target, a comprehension target, a walrus, a lambda's parameter, a global, a `match` capture, star or mapping rest), the owning function (`_rebound_names` | its parameters). Keyed by the def or class that holds it, `None` for the module's own top level. Excluded by rule: a call's callee (`calls` already), a bare or subscripted decorator or base (`decorates` · `inherits`), a name under `annotation`/`returns` (a type, not a value), the inner names of a dotted chain (the chain is one label). One edge per site, `dst_repr` text for the resolver — which binds it through the same doors a call label walks (`local` · `import` · `reexport`); a label no rule reaches stays text. `_rebound_names` is computed once per function in `_scan` and handed to `_bindable_annotations` (#57) — it was computed twice for a round. The mint pin is `python_ast:references:…`, so a re-mint over a pre-#94 shard never splices a span that holds no reference.
- `typescript_ast._refs_in` beside `_calls_in`: the same descent (never into a nested declaration, into a function expression or arrow only when the component's top level is scanned), a lexical shadow carried per stack item the way `_writes_in` keeps it (a block's `let`/`const`/declarations, a `for`'s variables, a `for…of`'s binder — never visited —, a `catch` parameter, a descended function's parameters and hoisted names) over `_module_bound` (top-level function · class · interface · `const x = () => …` · CommonJS-assigned names, import and require bindings). A member chain is one label only when `_pure_chain` holds — every link a member expression, the base a name; `f(1).prop` is an expression, descended, its call keeping the callee flag. A property name, a type (annotation · alias · interface), a declarator's name, a re-export clause, a shorthand pattern, `this` mint nothing. Functions scan parameters and body (never the function's own name); methods scan the decorators the grammar lays as siblings before the member plus the member's children; a class field's value is the class's own reference; the module's top level scans every non-function statement (a route table, `app.use(handler)`, `export default handler`). Pin bumped likewise.
- The count, this repo's own shard, `graphy build`: `compiled 4456 nodes / 11302 edges` on 7de5037 → `4466 / 11855` here (`grep "BUILD OK" <rebuild log>`); minted per shard (`python3 -c "import json,collections; print(collections.Counter(e['edge_type'] for e in json.load(open('engine/tenants/graphy/substrate/<slug>_graph/edges.json')))"`) and bound by the resolver (the same over `wormhole_edges.json`'s `edges`): `graphy_graph` 707 minted · 152 bound, `tests_graph` 460 · 239, Hono's `hono_graph` 265 · 146, `zod_graph` 592 · 322. The mint of `engine/graphy` (`build_ir`, best of five): 0.380 s on 7de5037 → 0.402 s. The arms' `Last walk` blast counts widened while the cut sha stayed byte-identical (`0f1d43aa1cb8…`): CLI 13→17 · CUT 9→13 · DOORS 10→14 · PRODUCE 17→21 · SEAM 26→30 · MEMORY 15→15 — `pillars.RELATIONS` and `arms.FANIN_RELATIONS` are hardcoded and do not count it, filed as #140.
- Named and left, each fail-closed: a Python comprehension target shadows the whole module (Python 3 scopes it to the comprehension); a module-level def's decorators and defaults are not descended by `_shadow_in`; a chain whose head is `self`/`cls` mints nothing (a method passed as `self.on_done` is a real reference the resolver could bind through the container — the noise of every `self.attr` read outweighed it); TS `const a = () => {}, b = helper;` drops `b`; the two hand-rolled binder lists are the class both REVISE rounds found, filed as #141 (one reader over `symtable`).

| check | result |
|---|---|
| red first | `S=$(mktemp -d) && git archive 7de5037 engine \| tar -x -C $S && cp engine/tests/test_adapters.py engine/tests/test_typescript.py engine/tests/test_cli.py engine/tests/test_doors.py $S/engine/tests/ && (cd $S/engine && "$OLDPWD/.venv/bin/python" -m pytest -q -k "referenced_as_a_value or names_the_binder or declare_exactly_the_families")` → 4 failed: the producers mint `Counter()`, `blast` prints `dependents=0 own=0`, the vocabulary lacks the word |
| the done block | `cd engine && ../.venv/bin/python -m graphy blast graphy.cli._cmd_check --tenant tenants/graphy/tenant.json --tenant-id graphy --depth 1` → `own=1`, `hop1 graphy://func/graphy.cli._build_parser ◀─references─ graphy://func/graphy.cli._cmd_check`; the same for `_cmd_eat` · `_cmd_build` · `_cmd_draw` · `_cmd_harness`; `descend graphy.cli._build_parser` names no `_cmd_*` · `cd engine && ../.venv/bin/python -m pytest -q -k "referenced_as_a_value or names_the_binder"` → 3 passed (a dispatch table, a callback argument, a decorator's argument, a default, a class field and the module's own table mint; a parameter, a local, a comprehension target, a lambda's parameter, a for target, a class-body assignment, a match capture, a callee, a bare decorator, a subscripted base and an annotation do not) |
| the surface | a scratch repo with `set_defaults(handler=_cmd_check)` eaten cold with `--no-provision`, `blast verbs.cli._cmd_check` → `_build_parser ◀─references─`, the sidecar's edge `via: resolver:local`, `descend _build_parser` silent on it (`test_cli.py::test_GREEN_blast_names_the_binder_of_a_handler_referenced_as_a_value`) |
| the floor | `cd engine && ../.venv/bin/python -m pytest -q` → exit 0, 2 skipped |
| the gate · the battery | `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` · `python3 review.py --diff 7de5037` → `REVIEW OK: 17 check(s) · 0 finding(s)` (severance 0) · `ARMS OK: 6 arm(s) match the walk (store 17340ab7f2dc9bda)` after the re-render · Hono rebuilt under the project interpreter: `CHECK OK` |
| review (round 1) | round 1: REVISE — cold. Done block green; one blocker. B1: a name match at module scope and in a class body — the shadow set was empty whenever the holder was not a tracked function, so a comprehension target (`M = {raw: email for email, raw in ()}` → module references the import `email`), a lambda's parameter, a `for` target and a class-body assignment (`build = 1; USES = build`) still minted; a real specimen, `packaging/metadata.py:308`, swept across 3,292 site-packages files — one confirmed false edge, and the law is not a rate. TypeScript twin: a module-level `for (const helper of [1, 2]) { sink(helper); }` minted two references to the import `helper`, the body's read and the loop's own binder. Class: the card's ② — a scope resolving to nothing failed open. Walk: `_scan`'s one caller `_emit_raw_records_for_file`; `_refs_in`'s three sites all one branch. Fix: `_shadow_in` per module and per class body, the module's shadow strict for the whole file; the TS shadow lexical per stack item and the for-of binder never visited; both floor tests widened with the shapes, red on the base. Non-blocking, taken: `_rebound_names` computed twice per function (memoized, handed to `_bindable_annotations`, mint +21 % → +6 %); TS `type H = typeof helper` minted a value (a type alias and an interface are skipped); `class K(Generic[T])` double-minted `inherits "Generic[T]"` and `references "Generic"` (a subscripted base is `inherits` only). Named: `references` is a word one client's lane already mints (above); `pillars`/`arms` hardcode their relations (#140); the counts belong in this section (they do) |
| review (round 2) | round 2, fresh with the ledger: REVISE — B1 verified fixed with CPython's own `symtable` as the oracle over 3,423 real files and 39,615 reference sites, zero false; the class shadow does not leak into a method (a method reading a module def the class body shadows mints — correct); the memo gives `_bindable_annotations` the identical answer for every function. One new blocker. B2: a TypeScript member chain over a call result minted a reference labelled by a flattened chain — `f(1)?.prop` → `references g -> f.prop` — because `_expr_repr` on a member node erases the call, so the guard `"(" not in r` could never fire; real specimens `hono/src/jsx/components.ts:66` (`useContext(StreamingContext)?.scriptNonce` → `useContext.scriptNonce`), `matchedRoutes.at.path`, zod's `core.config.customError` — 11 on hono + zod, none bound, none on the base. Class: the card's ① — the proxy is not the thing, and a label nothing spells. Fix: `_pure_chain` walks the object spine; a chain over a call, a subscript or a cast is an expression, descended, the call keeping its callee flag — hono now mints `StreamingContext` from that line and nothing for `useContext`; the TS test carries `helper(1)?.x` · `helper(2).x` · `ns.arrow[0].y`, red on the base. Non-blocking, taken: `ast.MatchStar` and `ast.MatchMapping.rest` missing from both binder lists (zero hits across 6,082 real files; added, a floor line). Named and left: the comprehension target and the def-header shapes above, `const a = () => {}, b = helper;`, the two hand lists (#141) |
| review (round 3) | round 3, fresh with the ledger: SHIP — B2 re-verified dead on its own specimen (`components.ts:66` now mints `StreamingContext`, nothing for `useContext`) and by an independent oracle — every `references` label must appear literally on its own source line: red on the unfixed world (`_pure_chain` forced true → 7 non-literal labels on hono), 0 on hono · zod · express after. The new descent refuted on every shape named and held: `this.x.y` · `super.x` nothing; `helper!.prop` · `(helper).prop` once each; `ns[key].fn` → `ns`; `ns?.arrow` a pure chain the resolver binds; `helper().g()` and `new ns.Klass()` calls only; JSX member tags; class fields and decorated methods; the module's table, `app.get`, `export default`. B1 re-verified with a second `symtable` oracle over graphy · fastapi · pip · pydantic · anyio · starlette · typing_inspection: 0 non-literal labels, 0 local/param heads; no label carries `self`/`cls`/`this`. Surface: `bash quickstart.sh https://github.com/psf/requests requests` → `GRAPHY_QUICKSTART_OK: requests eaten in 5.2s`. Non-blocking, named: `_scan`'s return annotation says three where it returns four (no checker in the gate); a callee wrapped in parens, `!` or `as` mints a `calls` and a `references` at one site (both DEPENDS, 0 real occurrences on hono · zod · graphy); a module-level decorated class's decorator arguments are not scanned (fail-closed, the `const a = () => {}, b = helper` family); `graphy check` read STALE mid-review because this record was written after the build — clears on the landing's re-eat |
| the landing | one commit on main: the graphy tenant rebuilt (after the known `ARMS DRIFT` stop and re-render — every arm's `Last walk` widened, PRODUCE's inventory gained `_module_bindings` · `_reference_edges` · `_shadow_in` · `_is_bound_shape` · `_module_bound` · `_refs_in` · `_pure_chain`), `ARMS OK: 6 arm(s) match the walk (store 17340ab7f2dc9bda)`; the harness step's draw region and untracked products reverted before every gate run (#108 · #128); Hono rebuilt under the project interpreter, `CHECK OK`, its pre-existing `ARMS DRIFT` (a `Last walk` line the committed regions predate) reproduced on the base and left; floor · gate · battery (17 checks) · `release.sh --check` (125 entries) · `burden.py` · `census.sh` green on the final tree; filed from the rounds: #140 (pillars and arms hardcode their relations), #141 (one scope reader over `symtable`) |

## 140 · A GATE LINE NAMING A DIFFERENT ISSUE GATES THE RUNG IT NAMES — #111 was armed with its code built and uncommitted; its closing line gated #114's release step and `march.py` labeled #111 `operator`, advanced to #87 and skipped the two rungs the operator had prioritised, with the step's code spans stripped to `run  , and push the   tag`; a gate names the rung it belongs to in its head, `MARCH GATE: <gate> #N — <step>`, that rung is labeled and the armed one stays the lane, a step that only mentions another `#N` is refused, and the step travels verbatim (2026-09-14 · graphyos issue 116)

The loop limited itself through a mislabel: `gate_of` parsed the closing message after `_prose` had replaced every code span with a space, and `gate()` labeled the armed issue whatever the step said. The specimen is in `.claude/recovery/march.log` (`gate PUBLIC on issue 111: … run  , and push the   tag … (tracked as #114)`, then `armed 87`).

- `_gate_lines`: the gate token is still an order only at the start of a line outside code — a line whose token vanishes when its spans are blanked is prose — but the line yielded is the one as written, so the step keeps `` `bash release.sh` `` and `` `v0.2.5` ``. `_prose` remains the deferral scan's input.
- The rung a gate belongs to is spelled in the head — `_GATE_RE` takes an optional `#N` between the gate and the dash — never guessed from the step (`march.gates_of` reads every gate line, `march.route_gates` lands them): round 1 showed that reading "names" as "contains `#N`" moves the mislabel from the armed rung to whatever rung the step mentions for context (`the rationale is in #104`) or a PR number, with no route back. `route_gates` judges every line of the message before landing any (a message is a set: a refused line applies none of it), then lands every foreign head, then the armed rung's own line last because that one marches on. No head rung and no other `#N` in the step's prose (`gate_names`, code spans blanked) → `gate()` as before, the armed rung labeled and the next armed; no head rung and a step naming another rung → refused as malformed with the head form to write. A head rung → GitHub's answer, three ways (`march.issue_takes_a_gate`): it takes the gate — then the rung is labeled and the step commented, the armed rung untouched and the stop blocked with the lane named and the form that gates the armed rung itself; it cannot — closed, a pull request (`/pull/` in its url), or no such number (GitHub's definite `Could not resolve to an issue or pull request`, a typo'd head) — refused by name; or `gh` could not answer (transport, a timeout), the hook's could-not-tell — the session may stop with the failure named, never a block until GitHub recovers and never a stop on a definite answer. The board is the receipt: a rung already carrying the operator label and the exact gate line in a comment is left alone, and one missing either lands — no list in the state file, so a landing that failed between the label and the comment, or a label the operator removed, is read from the rung on the next stop. The hold branch takes the same route with `allow` in place of `block`. The specimen line as written (`… (tracked as #114)`) is now the refusal, and `MARCH GATE: PUBLIC #114 — …` is what it should have said.
- `python3 .claude/hooks/test_march.py`, the done block's own command, ran zero tests and exited 0 on the base — a pytest file with no `__main__`; it now runs the floor.
- The mislabel the specimen left on closed #111 removed by hand (`gh issue edit 111 --remove-label operator`); #114 already carried the label it was owed.

| check | result |
|---|---|
| red first | `S=$(mktemp -d) && git show d18190a:.claude/hooks/march.py > $S/march.py && cp .claude/hooks/test_march.py $S/ && .venv/bin/python -m pytest -q -p no:cacheprovider $S/test_march.py` → 8 failed, 22 passed: the base labels #103 for a head naming #104 and for a step mentioning it, strips the step's spans, labels a closed rung and a PR, blocks on a `gh` error, reads one gate line of two, and lands a refused message's other lines |
| the done block | `python3 .claude/hooks/test_march.py` → 30 passed (host interpreter, pytest 9.1.1) · `.venv/bin/python -m pytest -q -p no:cacheprovider .claude/hooks/test_march.py` → 30 passed · `bash standalone_check.sh \| tail -1` → `GRAPHY_STANDALONE_OK` |
| the specimen | `cd .claude/hooks && python3 -c "import march; [g] = march.gates_of('**MARCH GATE: PUBLIC — after #111 closes, bump the version to 0.2.5, run \`bash release.sh\`, and push the \`v0.2.5\` tag to omnislash157/graphyos (tracked as #114).**'); print(g, march.gate_names(111, g[1]))"` → `('PUBLIC', '… run `bash release.sh`, and push the `v0.2.5` tag … (tracked as #114).', None)` and `{114}` — the refusal; the head form `MARCH GATE: PUBLIC #114 — …` → `(…, 114)` |
| the battery | `python3 review.py --diff d18190a` → `REVIEW OK: 17 check(s) · 0 finding(s)`; `cites-nonexistent` now indexes `.claude/hooks/*.py` — a span citing the deleted first reader (`march.` + `gate_of`) appended to this file reads `cites-nonexistent 1` (round 3, B7) |
| review (round 1) | round 1: REVISE — cold. Done block green (and it ran zero tests on the base). Three blockers. B1: a `gh` error on the named rung was caught with the "not open" refusal under one handler and read as a decision — a block on every stop until GitHub recovered, a wedge the base did not have; the two never share a handler now, a `gh` error is `allow` with the failure named (a floor line: gh raising on the head rung → allow, nothing labeled). B2: any `#N` in the step relocated the gate — a mention for context, a PR number (`gh issue view` answers for one) — and the success text told the session to keep marching a rung that genuinely needed the operator, with no route back; the design call taken: the rung is spelled in the head, a mention is refused, the PR refused by url, every verdict carries the form to write (three floor lines). B3: the card's ④ — `rung-discipline` §18 and the hook's own INTERROGATION text still described the old law; both lines rewritten. Non-blocking, taken: a floor line for the `last_gate` dedup; named and left: the `capped` hold branch (`held_because` ending "still open") is unreachable on this tree — `held_because` is only ever `disarm` or `board drained` — so the hold route and its tests guard a path no code reaches (an observation, carried in the commit message) |
| review (round 2) | round 2, fresh with the ledger: REVISE — B1 · B2 · B3 re-verified dead on their own specimens (the real #111 line → the refusal; the head form → 114; the PR url shape confirmed on the real repo; every surface carries the head form). Two new blockers, both through the fix. B4: a definite "no such issue" from GitHub (`Could not resolve to an issue or pull request`, a typo'd `#141` or `#0`) was folded into could-not-tell, so the session was let stop on an open rung — a self-limit; the floor had pinned the defect (`#999` → allow). The abstraction named: GitHub's answer is three-way, and only the transport failure is could-not-tell; the floor line is red for not-found → block and green for a 502 → allow. B5: a foreign-rung gate is no longer terminal, so one message can carry a foreign gate and the armed rung's own line, and the first cut read only the first line while its block text demanded the second; every gate line is routed now, the armed rung's own last (a floor line: two lines → #104 labeled, #103 labeled and the next armed). Non-blocking, taken: the foreign rung's comment no longer says "the march moved on" (it never armed that rung); `BAD_GATE` shows the head form. Named and left: a head addressing the armed rung with a mention in its step is refused while a foreign head with a mention is accepted (documented, a nit); a changed step under the same head posts a second comment (a changed step is a new instruction); a transient `gh` failure letting the session stop is the module's pre-existing fail-open law, out of this rung |
| review (round 3) | round 3, fresh with the ledger, the design round: SHIP on the abstraction, REVISE on two. B1–B5 re-verified dead on their own specimens. The three-way answer holds — `HTTP 404` · `403 rate limit` · `401` · a login prompt · `Resource not accessible` · a timeout · a missing `gh` binary · bad JSON every one could-not-tell, nothing labeled; closed · PR · `Could not resolve` refused. B6: `last_gate` held one line, so two foreign heads in one message re-stopped duplicated the first's label and comment on every continuation stop, and a refused line landed after an earlier line had — `route_gates` now judges every line before landing any (a message is a set), and `last_gates` is the list of landed keys (a floor line: two heads stopped three times → one comment each; a closed head beside a good one and the rung's own → nothing applied, named). B7: this section's specimen row ran the deleted `gate_of` and named `route_gate`, and the battery read clean because `cites-nonexistent` indexed the engine, the tests and the root scripts, never the hooks — the index widened, the row fixed. Non-blocking, named: `PUBLIC#114` and `PUBLIC (#114)` fall to the bad-gate refusal (asked to rewrite); the hold branch's foreign refusal is an `allow` carrying the text; `capped` still unreachable |
| review (round 4) | round 4, fresh with the ledger: REVISE — B1–B7 re-verified dead on their own specimens (the widened cite check read 3 on two deleted names appended to this file, the selftest 16 red). B8: the receipt was a list saved after every landing, so a `gh` failure between two foreign landings named nothing of what landed and duplicated the first on the next stop, and a label the operator removed was never re-applied because the stale key said it stood — the card's ⑥ (#87's shape) and ①. The smaller design taken: the board is the receipt — `issue_takes_a_gate` views the rung's labels and comments and a rung carrying the label and the line is left alone; the state list is gone (a floor line: a 502 on the second of two heads → the first landed once, the second on the next stop, and the operator's removed label lands again). B9: the section's own prose still described the round-2 list beside a round-3 row that said otherwise — the card's ④; rewritten to the final design. Named and left: two lines gating the armed rung keep the first's step (the base's behaviour); a good foreign head beside a `TASTE` line never names the bad one (gates win over the bad-gate scan, pre-existing); `inject` and the open-issue block text show only the armless form; `capped` unreachable |
| review (round 5) | round 5, fresh with the ledger: SHIP — B1–B9 re-verified dead on their own specimens; the board-as-receipt design refuted and held: `gh issue view --json comments` returns every comment (155 on a vscode issue, no cap), a label present with the comment absent re-lands once (the edit idempotent, one comment) and a second stop writes nothing, a line quoted inside a longer comment reads as carried (the board holds the instruction verbatim), one caller of `issue_takes_a_gate`, `issue_state` unchanged for the hold, the close and `unblock`, one `gh` view per foreign head per stop. Surface: the done block's two commands, run by the reviewer — 30 passed on the host interpreter and the venv, `GRAPHY_STANDALONE_OK`. Named and left: the trailing `(?:\*\*|__)?` in `_GATE_RE` strips a step ending in `__` (`see __init__` posts as `see __init`) — on the base, an observation. The reviewer's own probe (`git checkout -- RECON.md` after appending a dead name) dropped this uncommitted section and restored it from the session's diff, byte-identical — checked here by `git diff --stat d18190a -- RECON.md` before and after |
| the landing | one commit on main: no engine change, so no rebuild — the graphy tenant's store and arms stand; `python3 .claude/hooks/test_march.py` → 30 passed · `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` · `python3 review.py --diff d18190a` → `REVIEW OK: 17 check(s) · 0 finding(s)` · `python3 review.py --selftest` → 16 red on fixtures · `bash release.sh --check` · `bash census.sh` · `python3 scrub.py --tracked` green on the final tree; the public cut by `bash sync_public.sh`, the board cleanup on #111 done by hand above |

## 141 · A PATH THE ENGINE WRITES IS POSIX ON EVERY HOST — on windows-latest `shell install` wrote a `.codex/hooks.json` the harness could not parse (`Invalid \escape`), the history adapter read git's utf-8 under cp1252 and lost `RECON §1` and `café.py`, `showcase` refused `C:\…\src/` as an ssh host named `C` and wrote `C:\…\src` into its page, and the burden, the profile receipt and eat's re-run command spelled `graphy\cli.py`; the paths in `shell install`'s wiring, every `PROVENANCE.json`, the showcase page and the profile receipt, and the messages the issue names, are `as_posix()`, every template value filled into JSON is escaped by `json.dumps`, git is decoded as utf-8, and a drive-lettered path is a path whose drive is a segment; the engine's other receipts are one shared writer away, filed (2026-09-14 · graphyos issue 125)

Split from #88 on the measured run ([34855052453](https://github.com/omnislash157/graphyos/actions/runs/34855052453), windows-latest, the whole floor): the four bullets the issue names were the red tests the run lists over a handful of engine sites and one class of test fixture. The sites:

- `shell.install`: the JSON templates (`codex/hooks.json` · `cursor/hooks.json`) were filled by the same `str.replace` the shell templates use, so a Windows path's backslashes reached the JSON raw. `_fill_json` escapes each value with `json.dumps` inside the template's own quotes; `_spell` gives every `Path` value its POSIX form on every template (`C:/venv/Scripts/python.exe`, which every Windows shell and interpreter accepts), so the hooks, the router and the wiring agree on one spelling.
- `adapters.history._git`: `subprocess.run(text=True)` decoded git's utf-8 under the console's locale, so on a cp1252 host `RECON §1` in a commit body and `café.py` in its file list were mojibake — the section a commit records and the module it touches lost, silently. Decoded utf-8 now, `errors="replace"`.
- `showcase._parse`: `C:\work\src/` matched the ssh `host:` arm. A drive-lettered path is folded to its POSIX form before the url regex with the drive as its first segment (`/c/work/src`), so the path the user typed and the `C:/work/src` git records as a clone's origin are one repo, and `C:\a\src` and `D:\a\src` are two — the way `/x/a/src` and `/y/a/src` already were (round 1 named the first cut's dropped drive as the asymmetry). The local target's `origin`, which the page and `showcase.txt` carry, the `--tenant` in the page's commands, the verb's receipt and its refusals spell POSIX too (round 1, B1); so do the command builder every command on the page starts with (round 2) and the hub line every eaten repo's page carries (round 3). The page's done token is the door for the class on this surface: `sugiyama.check_artifact` refuses a path spelled the OS way — a drive-lettered `C:\…` or a backslash file path — anywhere in an emitted page, `showcase()` runs the same predicate over `showcase.txt`, and `review.py`'s visual leg runs it over every tracked page, so the next f-string over a `Path` is caught on the page it reaches, with no inference over the code that wrote it. The door bit on its first Windows run: run 34912391409's path mark refused the page's MCP block, whose `--tenant` came from `cli.mcp_args` as `str(desc)` — the site round 3 had left to #142 because it looked unreachable from the page; it was the page's — and `mcp_args` spells `--repo` and `--tenant` POSIX now.
- `smash.portable` (the path every receipt carries — `corpus.path`, `mint_command`, the history shard's `sessions` and `code`), `burden.py`'s four message sites, `measure._engine_owned` · `_fmt_frame` (a frame's file is read POSIX whatever cProfile spelled, so the engine's hottest frame is judged on Windows), and `cli._eat_again` (the re-run command a refusal prints was single-quoted whole on Windows, for its separators): each `as_posix()`.
- The test fixtures: `test_history.py` wrote `RECON.md` and the session archive with `write_text()` and no encoding, so on Windows the `·` in `## 1 · THE FIRST` and in `session: … · pane %99` was cp1252 and the utf-8 reader dropped it — 0 sections, 0 session headers. Every write and read in the file names utf-8 now (by an AST pass over the file). The assertions in `test_shell`, `test_showcase` and `test_cli` that spelled the OS path now spell `as_posix()`, and `test_cli`'s two newline pins spell `os.linesep`; the diff is their count.

The claim is exactly the proven set, not the tree: round 2 found `ring.json`, `tenant.json` and the refresh, rebuild, farm, index and estate receipts still written with `str(Path)` — the same class a second time, so the design that makes it impossible (every `json.dump` in the engine through one writer whose `default` spells a `PurePath` POSIX, guarded by a `review.py` set difference over every `json.dump(s)` call) is graphyos #142 rather than a patch here, and every surface (this title, the README, the changelog, `ci.yml`'s comment) names the sites that are proven and names the rest as #142's.

The new floor lines, each red on the base engine (the red-first row is the count and the command): a repo directory whose name carries a backslash (a character on POSIX, the separator on Windows — the same test reads each platform's own case) installs wiring that parses; a drive-lettered path parses as a path and never an ssh host; a frame spelled `graphy\cli.py` is the engine's and reads `graphy/cli.py`; git's output is decoded utf-8 in a subprocess whose locale is plain C with coercion and UTF-8 mode off; and, from round 3, a showcase with a hub spells it POSIX and the page checker refuses the OS spelling. The battery grows one check, `json-template-spliced`: a `json.loads` over text a value was just spliced into (an f-string, `%`, `.format`, `.replace`, or `_fill`) is a finding — the specimen is this rung's, proven red on four shapes and green on the `_fill_json` form. `ci.yml`'s `store-windows` job gains the fifth mark: the test files this rung touched run whole on windows-latest with a deny list — the step's own comment names each deselected test and the reason it is another rung's red there — under a short `--basetemp` because a local path's clone key is every one of its segments and pytest's default tmp doubled past MAX_PATH. The step is the count of files and deselects; this prose carries none (review rounds 2, 4, 5, 6 and 7 each found one stale copy of a count here beside a row that held it — a count written in a doc is a lie waiting to happen).

| check | result |
|---|---|
| red first | from the repo root: `PY=$PWD/.venv/bin/python && S=$(mktemp -d) && git archive 9e10a0d \| tar -x -C $S && cp engine/tests/test_{shell,showcase,measure,history}.py $S/engine/tests/ && (cd $S/engine && PYTHONPATH=$S/engine $PY -m pytest -o addopts="" -q -p no:cacheprovider -k "backslash or drive_lettered or decoded_utf8 or hub_line" tests/test_shell.py tests/test_showcase.py tests/test_measure.py tests/test_history.py)` → 5 failed, 40 deselected: `Invalid \escape`, `not an <owner>/<name> git url`, `graphy\cli.py` not owned, `decoding with 'ANSI_X3.4-1968' codec failed`, and the hub test on the missing page checker (on Linux `str(hub) == as_posix`, so the fold itself is proven where it bites — the Windows mark, run 34912391409) |
| the done block | `cd engine && ../.venv/bin/python -m pytest -q tests/test_shell.py tests/test_history.py tests/test_showcase.py tests/test_burden.py` → 38 passed (`-o addopts=""` for the count; 37 before round 3's hub test) · `python3 workflows.py --run .github/workflows/ci.yml floor` → `CI LOCAL OK: 5 step(s) in ci.yml:floor, every one run` |
| the windows run | the working tree pushed as branch `win-125` on the private repo and `ci.yml` dispatched: [run 34909359644](https://github.com/omnislash157/graphyos/actions/runs/34909359644) — the path mark red on three (the memory-taps test spelling the OS path, the new test's backslash directory splitting into two there, `Filename too long` on the local-path clone key under a 100-char tmp); [run 34909649372](https://github.com/omnislash157/graphyos/actions/runs/34909649372) — `store-windows` green, every mark including the path mark. After round 1's fixes: run 34910790359 red on the drive test's superseded expectations, run 34910839343 red on one assertion spelling the clone directory the OS way, [run 34911130622](https://github.com/omnislash157/graphyos/actions/runs/34911130622) — every job green, the path mark included. After round 2's fix to the command builder: [run 34911617565](https://github.com/omnislash157/graphyos/actions/runs/34911617565) — every job green. After round 3's door: run 34912391409 red in the path mark on the MCP block's `str(desc)` (the door's first catch, `mcp_args` folded), then [run 34912716637](https://github.com/omnislash157/graphyos/actions/runs/34912716637) green on every job. After round 4 (the `mcp_args` callers re-spelled and their test added to the mark): [run 34913213181](https://github.com/omnislash157/graphyos/actions/runs/34913213181) green on every job. After round 5 widened the mark to `test_cli.py` whole: run 34913855180 red on one test the allow-list had never run there — #123's stream test pinned `b"\n"` where the wrapper writes `os.linesep`, a POSIX-newline pin in the test, re-spelled; run 34914216344 red on that test's second `b"\n"` pin, fixed one site per run when the test should have been read whole the first time; run 34914509711 green on every job with both pins re-spelled — then, with `test_measure.py` whole in the mark too (round 6), [run 34914578700](https://github.com/omnislash157/graphyos/actions/runs/34914578700) on the tree that lands — every job green; `gh run view 34914578700 --repo omnislash157/graphyos --json jobs` re-derives the jobs, and the path-mark step's own log (`--log --job <store-windows job id>`) the tests it ran, equal to `pytest --co` here with the step's argv |
| review (round 6) | round 6, fresh with the ledger, the design round on the mark's selection: REVISE — R1–R5 dead on their specimens; the deny list's three `check` deselects true and complete for the whole-floor run they came from, whose failure list predates #123 — which is why #123's own stream test first ran on Windows here and pinned `b"\n"` twice (B1, runs 10 and 11, both pins `os.linesep` now). B2, ③/④: the design's own rule was broken on its own line — `test_measure.py` kept as two ids with a false reason ("its other two tests need `resource`"): one test does, via the profiled subprocess, and `test_GREEN_summarize_names_the_hot_frames…` pins `_engine_owned(str(…))` and `_fmt_frame(str(…))` outside the mark (green under both spellings, as run 34855052453 had shown — the mark, not a reading, is the proof); the file runs whole with one deselect, the comment and this section corrected. Other files swept for pins on re-spelled symbols: none — `test_smash.py`'s `corpus == str(checkout)` and `test_index.py`'s `out == str(out)` pin `ring.json` and pull's receipt, #142's sites, which #142's done block runs. Six files whole, six deselects, each with a reason from run 34855052453 |
| review (round 7) | round 7, fresh with the ledger: REVISE on the record alone — R1–R6 dead on their specimens; run 34914578700 read whole, its mark's count equal to `pytest --co` here, every job green; every deselect's reason re-read against the whole-floor run's own log and true (the two `chmod(0)` checks strip nothing on NTFS, the `[]`-registry check reads OK there — a question for #88, untouched by this diff); the whole diff cold, nothing further. B1, ④ a fifth time in this rung: this section's prose carried three counts (the files and deselects in the mark, the new floor lines, the re-spelled assertions) that the rows and the tree had outgrown, one stale copy per round. The design taken, the constitution's own law: the prose carries no count — the step is the count of the mark, the red-first row (now over all five new tests, `5 failed`) is the count of the floor lines, the diff is the count of re-spellings. Named and left: `_eat_again`'s single quotes on a path with a space are POSIX-shell advice, not cmd.exe's; the six arm regions ride the landing commit with the rebuilt store (`ARMS OK` at `2af2495ff7c265a1`), no engine change so no re-dispatch |
| review (round 8) | round 8, fresh with the ledger: REVISE on the record alone — R1–R7 dead; every remaining cardinal in this section checked against its source and agreeing; run 34914578700 read whole against the tree. B1, ⑦ and ④: round 7 re-spelled the red-first row's interpreter from a relative path that never resolved (`../../.venv/bin/python` from a mktemp tree) to this box's absolute path — a private marker — so `scrub.py --tracked`, `census.sh`, `burden.py` and the gate all read RED on the worktree while the gate row here still said OK; round 7's SHIP condition had listed only the battery and the release check, and the scrub was not re-run after a record edit. The row now captures the interpreter before the `cd` (`PY=$PWD/.venv/bin/python`) and carries no home; the four gates re-run green below. Disposition: the doors fired, no new check — a SHIP condition names the whole gate, never a subset. Named and left: `graphy check` reads the cursor lane STALE on an uncommitted tree, fresh after the landing commit |
| review (round 9) | round 9, fresh with the ledger: REVISE on the record alone — round 8's SHIP condition run line by line and green (no home path; gate, census, burden, scrub OK; the red-first row pasted verbatim → 5 failed); R1–R8 dead, each fix probed for the class through a new hole (`_fill_json`'s escaping of `\`, `"` and newlines; `_spell` on a POSIX name carrying `\`; `portable`'s `relpath` only after `relative_to`; `shlex.quote` on `C:/…`; the producers' `file` keys already POSIX so the PROVENANCE claim holds). B1, ④ once more: this section's walk row carried two blast counts read off the pre-rung store, this rung's own tests absent from them — re-derived against the rebuilt generation and the row rewritten to name callers and the command with no hand-typed total (the design of round 7 applied to the last row that had one). Named and left: `smash.corpus_digest` feeds `str(relative_to)` into the corpus digest and looks POSIX keys up with an OS-spelled key, so the digest is host-local and the shortcut misses on Windows (correct, slower) — a line on #142; `ci.yml`'s comment counts by hand beside the line that is the count |
| review (round 10) | round 10, fresh with the ledger: REVISE on one clause of the record — round 9's SHIP condition run line by line; five of the six blasts matched the walk row's transcription and the sixth did not (`showcase.showcase` has a second engine-owned dependent, `cli._build_parser`, through the `references` edge #94 minted, which the row had dropped). The design the round asked for, taken: the row names the command, the symbols and the generation and transcribes no hop — the store is the reader, the arm regions carry the walk in git under a stamped generation. R1–R9 dead on their specimens; every remaining cardinal in the rows re-derived; the gates green; the `PROVENANCE.json` claim checked at the writer (the producers' keys already POSIX). Named and left: `json-template-spliced` has one declarer of its sanctioned filler; the MCP server did not connect this session, so every walk ran through the CLI doors on the same store |
| review (round 11) | round 11, fresh with the ledger: SHIP — the done block's two lines run on this tree, the Windows run read whole against the tree it proves, the walk row's two claims checked against the store for all nine symbols, R1–R10 dead on their specimens with each fix probed through a new hole (`_fill_json` round-trips `"`, `\`, a newline and `é`; `_parse` on `c:/a/b`, a trailing `\`, `C:/` and a `..` segment; `os_spelled_paths` clean on a JS regex, a POSIX value, a UNC path, an extension-less directory; every `Path` argument arrives as a `Path`), every cardinal in the rows re-derived. Named and left as observations: the walk row's "inside the diff" read as "in a module the diff touches" (so worded now); `C:a/b` still takes the ssh arm; a lone `C:\` in page prose trips the door, which is right for an emitted page |
| the landing | one commit on main; the graphy tenant rebuilt (`bash engine/tenants/graphy/rebuild.sh`, store `2af2495ff7c265a1`, `CHECK OK`), its six arm regions re-rendered and verified (`ARMS OK`); `bash standalone_check.sh` → `GRAPHY_STANDALONE_OK` · `python3 review.py --diff 9e10a0d` → `REVIEW OK: 18 check(s)` · `bash release.sh --check` · `bash census.sh` · `python3 scrub.py --tracked` · `python3 burden.py` · `python3 workflows.py` green on the final tree; the public cut by `bash sync_public.sh`; the throwaway branch `win-125` on the private repo deleted after the landing; the close comment narrows the issue body's claim to the proven set and points at #142 |
| the floor | `cd engine && ../.venv/bin/python -m pytest -o addopts="" -q -p no:cacheprovider` → 708 passed, 3 skipped (707 before round 3's hub test) |
| the battery | `python3 review.py` → `REVIEW OK: 17 check(s) · 0 finding(s)` (`json-template-spliced 0 (77 module(s), 113 json.loads call(s))`) · `python3 review.py --selftest` → `json-template-spliced red=4 green=0`, 17 checks seeded · `python3 review.py --diff 9e10a0d` → `REVIEW OK: 18 check(s) · 0 finding(s)` (severance the 18th) · `bash release.sh --changelog` re-derived `CHANGELOG.md` from this section's title, `--check` green |
| the gate | `bash standalone_check.sh \| tail -1` → `GRAPHY_STANDALONE_OK` · `bash census.sh` → `CENSUS OK` · `python3 scrub.py --tracked` → `SCRUB OK: 245 file(s)` · `python3 burden.py` → `BURDEN OK` · `bash release.sh --check` green · `python3 workflows.py` → `WORKFLOWS OK: 5 file(s)` |
| the walk | `cd engine && python3 -m graphy blast <symbol> --tenant tenants/graphy/tenant.json --tenant-id graphy --depth 2` for each symbol the diff changes (`smash.portable` · `showcase._parse` · `shell.install._fill` · `adapters.history._git` · `cli._eat_again` · `cli._graphy_command` · `cli.mcp_args` · `showcase.showcase` · `sugiyama.check_artifact`), against the rebuilt store (generation `2af2495ff7c265a1`, the tenant's `rebuild.sh`): every engine-owned dependent is in a module the diff touches and consumes the return value unchanged, or is the argparse binder, `draw.emit_checked` or `harness.run` consuming `check_artifact`'s list unchanged; every caller of `portable` embeds the string it returns and none splits it. The store is the reader and the arm regions under `engine/tenants/graphy/arms/` carry the walk's inventory under that generation (`ARMS OK`); this row transcribes no hop and no count — rounds 9 and 10 each found one transcription drifted from the store |
| review (round 1) | round 1: REVISE — cold. Done block GREEN + JUDGED: 37 passed, `CI LOCAL OK`, and the Windows clause read off run 34909649372's store-windows log (head = `win-125` = this tree minus RECON/CHANGELOG; the path mark ran the exact argv and 38 dots = 37 + 1 skipped = the four files minus the two deselected plus the three selected). Re-run: floor 707/3, battery 17/0 and 18/0, selftest red=4 green=0, gate green, red-first re-derived on a `git archive` of the base with the four errors §141 names, the C-locale env proven (`ANSI_X3.4-1968`, utf8_mode 0, on the venv and the host interpreter). One blocker, B1 — class 1/④, the record's universal claim refuted by the verb the rung fixes: `showcase` on a local target set `origin = str(repo)` and wrote it into the page and `showcase.txt`, and four of its refusals plus `cli._cmd_shell`'s summary spelled the OS way while every hook it wrote spelled POSIX. Fixed at the sites (this section's showcase bullet) and the claim narrowed on every surface to what is proven — the engine's JSON and receipts, and the messages the issue names — since a `review.py` check for "every f-string over a Path calls as_posix" needs type inference and would fire on argv and on OS-quoted errors; disposition → this card ④. Named and taken: the drive fold dropped the drive so `C:/a/src` and `D:/a/src` keyed alike — the drive is a segment now. Named and left: `json-template-spliced` is blind to the one-hop variable form and matches `_fill` by name (widen when the form appears); the builder's walk row was read off a store `check` calls STALE at 7de5037 — the graphy tenant's `rebuild.sh` runs at the landing; `errors="replace"` makes a raw byte in a filename U+FFFD on every host, deterministic and never a `touches` |
| review (round 2) | round 2, fresh with the ledger: REVISE — B1 re-verified and still reproducing through a hole the fix never took: the page's every command and its MCP block come from `cli._graphy_command`, `str(here / "graphy.exe")` on Windows, so one line read `C:\venv\Scripts\graphy.exe … --tenant C:/repo/…` (two spellings); fixed — the builder spells `as_posix()`, and `eat`'s end-of-run summary (`_next_steps`) spells its `--tenant` and `--repo` the same way. B2, the same class a second time and so the design round: "every path the engine writes into its JSON and its receipts" was still refuted by `ring.json`, `tenant.json` and the refresh, rebuild, farm, index and estate receipts, each its own `str(Path)`; the reviewer's two exits taken as the card says — (a) the claim narrowed on every surface to the enumerated proven set, (b) the design that makes the class impossible (one JSON writer whose `default` spells a `PurePath`, guarded by a `review.py` set difference over every `json.dump(s)` — no type inference) filed as graphyos #142, never widened into this rung. B3, class 1: the windows row cited the pre-fix green run; it names run 34911130622 now — the run id is the anchor, never the throwaway branch's sha, which is no ancestor of main and which `sha-liveness` refused when this row first carried it — with runs 34910790359 and 34910839343 as the stale-test reds they were (the reviewer read run 3's job list whole and found the standing-clone red already beside the drive test — a run is read whole, never the job a dispatch was for). Class 6 re-derived on a `git archive` of the base: four failed for the right reasons. Named and left: the #123 step's own `subprocess.run(text=True)` reader decodes utf-8 under cp1252 and passes by warning — this rung's class inside #88's list; a one-letter scp host reads as a drive, git for Windows's own rule |
| review (round 3) | round 3, fresh with the ledger, the design round on ④: REVISE — R1 and R2 re-verified dead through the paths they opened (`mcp_config` takes the POSIX command; no `.mcp.json` is written by any verb; the windows row names the run on the landing tree; the round read "no test pins `sys.executable` verbatim" — round 5 found the two that pin its `str()` spelling through the printed block, `test_cli.py`'s next-steps test, green on Linux where the spellings agree). B1, the class a third time on the narrowed claim's own surface: `compose`'s hub line wrote `{hub}` and `str(hub)` into `showcase.txt` and the page — `C:\work\src\.graphy\GRAPH.md` on Windows — and every eaten repo has a `GRAPH.md` (eat runs the harness), so every real showcase took the branch while no test built a hub and the Windows path mark never entered it. The reviewer's ruling taken whole: not a third narrowing but the output property — `check_artifact` refuses an OS-spelled path in any emitted page, `showcase()` over `showcase.txt` too, the visual leg over the twelve tracked pages green, and a test that builds a hub, asserts the POSIX line, doctors the page to the Windows spelling and reads the refusal by name; `_next_steps`' `--write`, `--partition` and `-o` paths and one more refusal (`the descriptor at …`) spelled the same way. On #142 as filed: well-formed, its sites true, two corrections carried to it — `rebuild.py` returns its receipt and never dumps it, and a check over the call guards the call, not a caller's `str()`, so the door there is the same output property over every `*.json` the Windows job writes. Named and left: `mcp_args` returns `str(desc)` for a non-eat-home descriptor — left as a #142 site by this round, and overturned by the next Windows run, which is the door's point (the round-4 row); `measure._engine_owned` on a drive-case mismatch |
| review (round 4) | round 4, fresh with the ledger: REVISE — R1–R3 re-verified dead; the door refuted by script (drive-lettered with and without an extension, in an attribute, JSON-escaped, entity-escaped, lowercase drive, `graphy\cli.py` all caught; `\u` and CSS escapes, regexes, fences, urls, POSIX paths, a bare `C:` all clean; a UNC path and an extension-less relative directory not caught and not emitted on any claimed surface; the producers already write `file` POSIX, so the door is no regression on drawn pages). The Windows clause judged off runs 34912391409 and 34912716637 read whole: the first red on the door's catch of `mcp_args` — round 3's "a #142 site" was wrong on the page's own surface — the second green on the tree that lands. B1, class 4: `mcp_args` moved mid-round and its two callers in `test_cli` still pinned `str()`, green on Linux and red on Windows, hidden because that test was not in the path mark — both spell `as_posix()` now and the test rides the mark. B2, ④: the round-3 row's leftover corrected above. The hub test is red on the base only for the missing helper: on Linux `str(hub) == as_posix`, so the fold is proven where it bites, the Windows path mark, where `test_showcase.py` runs whole and run 7 is the proof it bites. Named and left: a JSON-escaped newline before a file name reads as a separator (`"a\nb.py"`) — a real `graphy\tests\x.py` shares the letter, so the door cannot decide by it, and no emitted page carries a multi-line JSON string; the close comment narrows the issue body's "every path" to the proven set and points at #142 |
| review (round 5) | round 5, fresh with the ledger: REVISE — R1–R4 re-verified dead; the ninth run read whole (40 tests in the mark, the `mcp_args` test among them by count). B1, class 4 a second time and so the design round on the mark's selection: `test_cli.py`'s next-steps test pinned `str(venv / "graphy")` and `str(venv / "python")` against the command builder round 2 re-spelled — green on Linux, red on Windows, and not in the mark, exactly round 4's shape, because the mark was an allow-list of node ids and an allow-list sees only what it is told. The design taken: the mark runs files with a deny list — `test_cli.py` whole, its three `check` reds on the platform (#88's) deselected by name — so the next pin falls inside the mark by default. The two pins spell `as_posix()`. (This round kept `test_measure.py` as two ids "because its other tests import `resource`" — round 6 counted: one test does, through the profiled subprocess, and one of the other eight pins `_engine_owned` and `_fmt_frame` with `str()`; the file runs whole now with that one test deselected, the reason spelled true on `ci.yml`.) B2, ④: this section's done-block row said 37 where the block yields 38 since round 3, and the round-3 row said no test pinned `sys.executable` — both corrected in place. Named and left: `harness.render_graph_md` writes `--tenant {str(desc)}` and `--repo {str(repo)}` into GRAPH.md — outside the proven set, carried to #142; `mcp_args`' `--repo` arm is never observable through `mcp_config` (overwritten with `.`); a url carrying a backslash would trip the door |


## 142 · A STALE HISTORY LANE IS RE-MINTED ALONE — on the first client's Windows tenant every session capture turned `graphy check` red on the history lane, and its remedy named `graphy eat .` and `graphy shell install`, the two commands a tenant with house lanes cannot run (the first prunes every lane the ring did not mint, the second rewrites the hook wiring the house owns); `graphy history --remint --tenant <descriptor> --tenant-id <id>` mints the history shard again from the inputs its own PROVENANCE names into a staged generation seeded from the served one, carries every other lane byte-for-byte, converges, builds and lands in one descriptor rename, `check` names that verb and neither of the other two on any tenant, and `shell install` runs it instead of writing the served generation in place, which closes issue 119 with it (2026-09-15 · graphyos issue 132)

Measured by the client's seat, 2026-09-14 (#132): after any session capture, `graphy check --tenant .graphy/tenant.json --tenant-id core` printed `re-mint it: graphy eat . (or graphy shell install --repo <abs>)` on a 32-lane tenant where both are forbidden — #70's class a second time, the safe verb having become the unsafe one when the house took the wiring. The same session found #119 open: `shell.install.remint_history` ran `eat_history` into the data home the descriptor serves and then `converge` · `build` against the live descriptor — the in-place rebuild #98 removed from `eat`.

- **The verb.** `_cmd_history` gains a third mode: `--remint` with `--tenant` and `--tenant-id` alone (a mint flag or a timeline term refuses — the shard's own receipt names its inputs). `_history_remint` loads the tenant, refuses a descriptor with no `history_graph` lane or no shard behind it, and stages the next generation with the same `stage_generation` `eat` and `rebuild` use. `_history_remint_stage` then carries every other `*_graph` from the served generation whole (`copytree`, minus the container trio `build` defers), carries the generation's other inputs (`ring.json`, the registry, the scheme index, the journal — never the store file or the traversals, which the landing moves), mints the history shard through `history.remint` — `inputs_of`, the resolution `verify` already did over the receipt's `sessions` · `code` · `names` · `aliases` · `recon`, now one function both read — re-reads the record's own row of the scheme index from the new shard (no other row moves), writes the staged descriptor as the served one with every path under the served generation moved one over (`_moved_into`, by either spelling), runs `converge --resolve` and `build --container none` against it, lands with `land_generation` keeping the carried lanes in a placement directory, and runs `check`. Exit 0 `HISTORY REMINT OK`; 1 `HISTORY REMINT LANDED` when the check that follows names another lane — the cursor's, when the tree moved past the store, which no history re-mint can answer for; 2 refused with nothing landed (the `finally` removes an unlanded stage and its staged descriptor, as `_eat_run` does).
- **The remedy.** `check`'s stale-history line names the verb with the real descriptor spelled POSIX and the tenant id, and the rebuild the descriptor declares for the lane when `build_lanes["history_graph"][0]` is set. It names `eat` and `shell install` on no tenant: the ring-only tenant the #70 caveat served is the one for which the verb is strictly cheaper, so the branch is gone rather than kept.
- **The install lane.** `shell.install.remint_history` calls `graphy history --remint` and maps its exit: 0 → `re-minted, store recompiled` (the receipt the #66 floor pins), 1 → the same with `graphy check reads red on a lane the re-mint does not own`, 2 → `re-mint refused` with the command to read why. #119's done test (`remint_history_lands_a_generation`) proves the served data home byte-identical through converge and build and that neither step runs against the served descriptor.
- **What "no other shard digest" means, measured.** The resolver's sidecar carries `resolved_over`, the digest of every shard's sources in the ring (`native_json_graph_ir.ring_source_digest`, §63), and the ring now holds the new history shard — so `shard_input_digest` of a carried lane moves by that stamp alone while its `nodes.json`, `edges.json`, `PROVENANCE.json`, a placed producer's own receipt and every resolved edge are byte-identical. The floor test measures exactly that set; the stamp naming the roster it resolved over is the design, not a touch.
- **Round 1's blocker: the receipt named the generation the landing keeps.** `history.inputs_of` placed the receipt's code shards at their absolute paths in the served generation — still on disk, because the landing keeps it one back — and `mint` recorded them again, so the next landing discarded the shards the new receipt named: `check` read COULD-NOT-TELL, its remedy said `re-eat`, and the third re-mint refused. `history.remint` takes a `relocate` and `_history_remint_stage` re-points every receipt input that sits in the served generation or the placement directory into the stage (`_moved_into`, the copy it just carried), so a receipt written into a generation names that generation's shards; the COULD-NOT-TELL remedy names `graphy history --repo … --out …` into a staged generation and never `eat`; the LANDED line no longer presumes the cursor lane (the check's own lines name it); `--sessions` joins the flags `--remint` refuses; the declared-rebuild slot is exercised by a hand-edited descriptor. The class is on the card (BLOCK TWO ⑥: run the verb three times and read the receipt's paths after each).
- **Found beside it, filed:** `shell install` writes `GRAPHY.md` and `.claude/settings.json` untracked, so the very next `check` reads the cursor lane STALE and names `eat .` as the remedy — #143, with the re-derive.

| check | result |
|---|---|
| the done block | `cd engine && ../.venv/bin/python -m pytest -q -o addopts="" -k "stale_history_remedy_names_no_eat and history_remint_changes_no_other_shard"` → 1 passed: a `rebuild.rebuild` tenant (a minted `core` lane, a placed `pg_schema` lane with its `emitter_receipt.json`, `history=True`) goes RED on a second session capture, the stderr holds no `eat` (`\beat\b`) and no `shell install` and names `graphy history --remint --tenant <desc> --tenant-id core`; the verb exits 0, `check` exits 0, both carried lanes' producer files and resolved edges hash the same, the placement's receipt stands, a descriptor hand-edited to declare `bash tools/remint_history.sh` for the lane is told it beside the verb, `history --symbol core.mod.run` reads `TIMELINE: 2 session(s)` · `bash standalone_check.sh \| tail -1` → `GRAPHY_STANDALONE_OK` |
| red first | from the repo root: `S=$(mktemp -d) && git archive 82de4d8 \| tar -x -C $S && cp engine/tests/test_cli.py engine/tests/test_rebuild.py $S/engine/tests/ && (cd $S/engine && $PWD/../.venv/bin/python -m pytest -q -o addopts="" -p no:cacheprovider -k "stale_history_remedy_names_no_eat and history_remint_changes_no_other_shard or remint_history_lands_a_generation or history_remint_refuses or never_eat_or_shell_install")` → `4 failed` of 4: the old remedy's `graphy eat .` matched `\beat\b` (twice), the old install wrote `history_graph/nodes.json` into the served home before `converge` (`the served generation moved before converge`), and `--remint` exited 2 as an unknown flag |
| the production run, round 0 | `cd engine && /usr/bin/time -f "WALL %es" ../.venv/bin/python -m graphy history --remint --tenant $PWD/tenants/graphy/tenant.json --tenant-id graphy` on the graphy tenant as it stood (history STALE, cursor STALE at 9e10a0d with HEAD 82de4d8): `6 other lane(s) carried byte-for-byte: duckdb_graph · graphy_graph · tests_graph · tree_sitter_graph · tree_sitter_typescript_graph · typing_extensions_graph`, `HISTORY OK: 179 commit(s) · 69 session(s) · 142 section(s) · 102 issue(s) · 42 receipt(s) · 950 exchange(s) · 1035 mention(s)`, `BUILD OK: compiled 4614 nodes / 12265 edges`, `CHECK RED: cursor lane` alone, `HISTORY REMINT LANDED` exit 1 — the pre-generation `substrate/` kept one back, `tenant.json` serving `substrate.gen-…`, 1.51 s wall — and its receipt named `tenants/graphy/substrate/graphy_graph`, the pre-generation placement: round 1's blocker, on the real tenant |
| the production run, after round 1 | the same command on the tenant it left (history STALE again: §142 and the archive moved): `HISTORY OK: 179 commit(s) · 69 session(s) · 143 section(s) · 103 issue(s) · 42 receipt(s) · 950 exchange(s) · 1035 mention(s)`, `BUILD OK: compiled 4616 nodes / 12267 edges`, `CHECK RED: cursor lane` alone, `HISTORY REMINT LANDED` exit 1, 1.52 s wall; the receipt's `code` reads `tenants/graphy/substrate.gen-…/graphy_graph` · `tests_graph` — the generation it landed — and three generations stand: the placement `substrate/`, the one kept back, the served |
| review round 1 | REVISE — B1 the receipt named the kept generation (class ⑥, the reviewer's three-re-mint script reproduced: OK · LANDED with COULD-NOT-TELL · refused; fixed above, the floor test `three_remints_in_a_row_each_name_the_served_generation_as_their_input` red on the round-1 tree by that script, exactly two generations after each, the receipt's `code` under the served home), B2 the COULD-NOT-TELL remedy said `re-eat` (fixed; the same test deletes the receipt's shard and reads no `\beat\b`). Non-blocking taken: "byte-for-byte" narrowed to what is measured, `--sessions` refused, the declared slot tested; left: `--recon` cannot be refused while its default is the string, the carry duplicates a rebuild driver's `fanout/` into every generation, the done block's third line is spelled for the repo root |
| the floor | `cd engine && ../.venv/bin/python -m pytest -q -o addopts=""` → 712 passed, 3 skipped (708 before: three new lines and round 1's lifecycle test, the #70 source-pin test replaced by the behavioural one) |
| the battery | `python3 review.py --diff 82de4d8` → `REVIEW OK: 18 check(s) · 0 finding(s)` (severance: 0 symbols deleted across 5 changed files) · `python3 review.py --selftest` → `REVIEW SELFTEST OK: 17 check(s)` |
| the walk | `graphy blast` at depth 2 on the graphy tenant (`--on-stale warn`, the store at 9e10a0d) of every changed or newly-called symbol: `history.verify` → `_cmd_check` · `_cmd_history` and four `test_history` tests, all reading `(fresh, reason)` unchanged; `install.remint_history` → `install` → `_cmd_shell` and five `test_shell`/`test_cli` tests that read the `history` receipt by prefix; `eat_history` → `_eat_stage` and `remint_history` (the second caller gone in this diff); `stage_generation` · `land_generation` → `_cmd_generation` · `_eat_run` · `rebuild.rebuild`, none changed |
| review round 2 | SHIP — B1 and B2 re-verified dead on the reviewer's own three-re-mint scripts: an eaten repo, a `rebuild.rebuild` house tenant with a real placement directory, a symlinked substrate — `check` 0 after each landing, the receipt's `code` under the served generation, exactly two generations, the placed lane's receipt surviving three landings; the real tenant re-minted a third time in 1.41 s with its receipt naming the landed generation; red-first re-derived as 5 of 5 (the lifecycle test is red on the base too); the scheme-index row the verb rewrites equals what `rebuild.sh` derives. Non-blocking, named and left: the cursor lane's own remedy still says `graphy eat .` on a house tenant when HEAD moves (adjacent, widened into #143); `relocate` is not applied to a sessions archive placed inside the data home, a layout nothing here produces; the graphy tenant's cwd-relative receipt (`../.claude/recovery/sessions`) lets `check` and `--remint` run only from `engine/` — pre-existing, `smash.portable`'s family; the whole-roster `converge --resolve` per re-mint on a wide roster is a board note |
| the gate | `bash standalone_check.sh \| tail -1` → `GRAPHY_STANDALONE_OK` |

## 143 · A CHECKOUT NEVER REWRITES A TRACKED BYTE — on windows-latest `core.autocrlf`, Git for Windows' default, checked the golden fixture shard out CRLF, so `nodes.json` no longer matched the sha256 its PROVENANCE declares and `test_index`'s push-and-pull read `18c13a…` against `59e173…`; the same checkout corrupts `docs/pillars.svg`, `CHANGELOG.md` and every arm region the gate compares byte for byte; `.gitattributes` says `* -text` so git checks out exactly the bytes it holds on every host, `review.py eol-rewritable` reads the attribute git will apply to every tracked file and refuses one it does not cover, and the Windows job reads the attribute and runs the test that measured the corruption (2026-09-15 · graphyos issue 126)

Measured on the runner, 2026-09-14 (#88's whole-floor run 34855052453, split into #126): `nodes.json does not match its PROVENANCE: sha256 18c13a… vs declared 59e173…`. Reproduced here without a Windows box: a clone of this repo under `git clone -c core.autocrlf=true` checks the fixture out `i/lf w/crlf` and `test_index.py::test_fixture_shard_names_itself_and_pulls_identical` reads the same `18c13a…` — the digest is of the CRLF bytes, so the corruption is the client's and identical on any host with that setting.

- **The rule.** `.gitattributes` at the root, `* -text`: no tracked file is subject to end-of-line conversion, in either direction, on any client. The index already holds LF for every non-empty file and no binary is tracked (`git ls-files --eol | awk '{print $1}' | sort | uniq -c`: `i/lf` and 9 `i/none`, the zero-byte `__init__.py`s), so the rule changes no byte on this box and a fresh clone anywhere reads `attr/-text` and `w/lf`. A checkout that already exists keeps the CRLF it has (git rewrites a working file only when it touches it): `git rm -r --cached . && git reset --hard` once, and it holds the bytes the index does. The issue asked for the shard JSON and every file a digest is taken over; the blanket rule is chosen over a list because the list goes stale the day a new golden or a new byte-compared product lands, and a rule that goes stale is the defect again.
- **The door.** `review.py eol-rewritable` asks git, never a hand-built list of git's sources — every round found the next one. Two reads over every tracked file (`git ls-files -z` into `GIT_ATTR_NOSYSTEM=1 git -c core.attributesFile=/dev/null check-attr text ident working-tree-encoding filter -z --stdin`, the user's and the system's own switched off in both): the index's rules (`--cached`, what a commit holds) and the worktree's (what `git add -A` will commit), over every attribute under which a checkout is not the blob — `text` (line endings), `ident` (`$Id$` expansion), `working-tree-encoding` (a transcode), `filter` (a clean/smudge program, git-lfs's for one). A file whose `text` is not `unset` in the index — `unspecified` (no rule), `set` or `auto` (a rule that turns conversion on) — or whose `ident` or `filter` is on or whose `working-tree-encoding` is set to anything but UTF-8 (`unset`, the attribute switched off by name, is git's no-op and reads as one), or that the two reads answer differently, is the finding by name. An untracked, unignored `.gitattributes` (`git ls-files -o --exclude-standard`) is named as the cause; one deleted from the worktree (`git ls-files -d`) is a finding, because both reads fall back to the index's copy while the next `add -A` ships the deletion; `<git-dir>/info/attributes`, located by `git rev-parse --git-path` so a linked worktree's common dir is read, applies to both reads and ships with neither, so a non-empty one is a finding; and no row of `git ls-files --eol` reads `i/crlf`, because `-text` also stops git normalising a CRLF a Windows editor commits and the svg's `cmp` would find it late. The denominator is printed, zero tracked files RAISES. The selftest's red fixture: a rule narrowed to `engine/tests/fixtures/**`, a svg, a CRLF file in the index, an untracked `docs/.gitattributes` covering the svg, a box-only `* -text` the repo's `core.attributesFile` points at, a linked worktree whose common dir holds `* -text`, a `-text` file with `ident` on, a second repo whose worktree rule is narrower than its index's, and a third whose rule file is deleted from the worktree — twelve findings; the green fixture carries a `* text=auto` under a gitignored `.venv/`, a file with every rewriting attribute switched off by name, and one with `working-tree-encoding=UTF-8` — all must name nothing.
- **The mark.** `ci.yml`'s `store-windows` job gains the sixth step: `git check-attr text` on the fixture's `nodes.json`, `git ls-files --eol` over the fixture, the svg and the changelog, and `pytest tests/test_index.py` — the test that was red on run 34855052453, on the platform whose default did it; the attribute line exits 1 itself when it does not read `unset`, so the mark stands without the test.

| check | result |
|---|---|
| the done block | `git check-attr text engine/tests/fixtures/fastapi_graph/nodes.json` → `text: unset` · `cd engine && ../.venv/bin/python -m pytest -q tests/test_index.py` → 10 passed |
| red first | `S=$(mktemp -d) && git clone -q -c core.autocrlf=true . $S && (cd $S && git ls-files --eol engine/tests/fixtures/fastapi_graph/nodes.json)` on the base `8d178c0` → `i/lf w/crlf attr/` and `test_index.py` → `1 failed, 9 passed` with the issue's digest `18c13a193f50…`; the same clone with this `.gitattributes` copied in and the files checked out again → `attr/-text w/lf`, `10 passed in 0.34s`, 0.53 s wall. `git check-attr text` on the base reads `text: unspecified` |
| the battery | `python3 review.py` → `REVIEW OK: 18 check(s) · 0 finding(s)` (`eol-rewritable` over 889 tracked files × 4 attributes, the index's and the worktree's rules, 0.08 s of the battery's 7.3) · `python3 review.py --selftest` → `REVIEW SELFTEST OK: 18 check(s)`, `eol-rewritable red=12 green=0` |
| the workflow | `python3 workflows.py` → `WORKFLOWS OK: 5 file(s)`; the Windows job's proof is the public repo's CI on this push |
| review round 1 | REVISE — B1: the door read `unset` off a rule file that was still untracked on this box (`git ls-files --error-unmatch .gitattributes` → not known to git), so `review.py` was green while a fresh clone under `core.autocrlf=true` was red with the issue's digest, and `sync_public.sh` copies by `git ls-files`, so the public cut would have shipped without the rule (class ②/⑤, ADJACENT: the door was blind to an untracked rule file). Fixed: every rule file git consults must be tracked, the red fixture drops an untracked one, and `python3 review.py` on the tree as round 1 read it now names `.gitattributes: … not tracked`. Non-blocking taken: the record misnamed the 9 empty files as binaries; an existing checkout keeps its CRLF until renormalised, said above; a CRLF committed under `-text` would have passed, so `i/crlf` in the index is a finding; the CI step's attribute line exits 1 on its own. The reviewer's stronger green: the rule file committed in a scratch repo and cloned fresh under `autocrlf=true` reads `59e173…`, 10 passed — `unset` is proven to mean no conversion, not assumed |
| review round 2 | REVISE — B1 dead on its specimen; the fix refuted twice in B1's own class (git's answer on this box is not a clone's), which makes it a design round: B2, a `.gitattributes` under a gitignored directory (`.venv/probe/`, a stranger's checkout under `staging/quickstart/`) was named `not tracked — git add it` and turned the gate red on an innocent (class ③); B3, a box-only `core.attributesFile` saying `* -text` read green with no tracked rule at all (class ②/⑤ through git's third rule source). The smaller design replaces the hand enumeration: `check-attr --cached` with `core.attributesFile=/dev/null` and `GIT_ATTR_NOSYSTEM=1` reads the index's rules and nothing else, so an untracked rule file is red by the attribute reading itself (`git ls-files -o --exclude-standard` names it as the cause and never enters an ignored directory) and a global one cannot mask it. Re-verified on the reviewer's specimens: a `* text=auto` under `.venv/probe/` → 0 findings; a clone with `core.attributesFile` pointing at `* -text` and no tracked rule → 888 findings; the rule file copied in untracked → named as the cause, added → 0. Non-blocking taken: the doc count `879` swapped for its command; the pwsh step read as correct (`$attr` a String, `-notmatch` boolean, `exit 1` fails the step) and left to the public CI to prove |
| review round 3 | REVISE — B1, B2, B3 dead on their specimens, and the XDG and `~/.config/git/attributes` sources beside them; the same class a fourth and fifth time, so the round refuted the abstraction: B4, a linked worktree (`.git` a file) whose common dir held a box-only `* -text` read green because the info file's path was hand-built and `is_file()` on `<file>/info/attributes` is a silent False; B5, `--cached` proves what a commit ships now and nothing about what the pre-commit gate stands in front of — the worktree's rule narrowed to `engine/**` with the index intact read 0, and `git add -A` then shipped 689 findings to every clone. The design that ends the class: two reads from git itself over every tracked file, the index's and the worktree's, the box's sources off in both, a file the two answer differently a finding; the info file located by `git rev-parse --git-path`; and, found while re-verifying B5, a rule file deleted from the worktree (both reads fall back to the index's copy) named from `git ls-files -d`. Re-verified: the worktree probe → the common dir's `info/attributes` named; the narrowed worktree rule → 689 `unset in the index's rules and unspecified in the worktree's`; the deleted rule → named; restored → 0. The check has no declarer in `engine/` — a set difference over all 889 tracked files — so `review.py` is its home, not `burden.py`'s list by name |
| review round 4 | REVISE — B1–B5 and the deleted rule dead on their specimens against a clone of the next commit; the design probes held (an intent-to-add rule reads red honestly, a symlinked rule file is ignored by git and reads red, a skip-worktree rule reads 0 and the commit ships the index's copy, `eol=crlf` beside `-text` is ignored by git, every flag older than CI's git, the check is 0.07 s of the battery). B6: the door proved the `text` attribute and the record claimed the byte — a tracked `.gitattributes` saying `probe_ident.txt ident` or `probe_u16.txt working-tree-encoding=UTF-16LE` beside `* -text` read 0, and a fresh clone held `$Id: e95cb4e0… $` and UTF-16 where the blob holds `$Id$` and ASCII (class ①, the ledger's shape one source further in: an attribute inside the source the door does see). Fixed: the two reads cover `text` · `ident` · `working-tree-encoding` · `filter` (`REWRITING_ATTRS`), `ident` or `filter` on and any `working-tree-encoding` a finding by name, and the red fixture carries a `-text` file with `ident` on; the reviewer's own specimen now reads three findings (`filter` lfs, `ident` set, `working-tree-encoding` UTF-16LE). Non-blocking named and left: a rule staged and then committed past by `git commit -- <path>` ships HEAD without it, which no pre-commit check can see and the public cut (by `git ls-files`) carries anyway; a gitignored `.gitattributes` over tracked files reads as a disagreement, which is right, and the message no longer says `add -A` ships it; 1,500 `review-fixture-*` directories under `/tmp` from `test_review.py`'s seeding without cleanup — pre-existing, a `sweep.py` rule or its own rung |
| review round 5 | REVISE — B1–B6 and the deleted rule dead on fresh clones of the next commit; `REWRITING_ATTRS` proven complete against `gitattributes(5)` on this box (`crlf` and `eol` alone read `text: unspecified` and so red; `binary` reads `unset`; `diff` · `merge` · `whitespace` · `export-*` · `delta` · `encoding` leave a clone's bytes identical and read 0). B7: `_rewrites` read `working-tree-encoding: unset` as a transcode, so a tracked `* -text -working-tree-encoding -ident -filter` — the defensive spelling — turned the gate red on 889 innocents, and a `sub/.gitattributes` switching a real transcode off for one file was named beside it (class ③, ADJACENT to B2). Fixed: `unset` and git's own no-op `UTF-8` read as off, the green fixture carries both spellings; the reviewer's repro now names `probe` alone. Non-blocking taken: an unmerged index now refuses by name instead of `the parse is broken`. Named and left: `* -crlf` alone (a deprecated negative) reads red on `text: unspecified`, and the spelling the door demands is the one this rung ships; `i/mixed` rows are not `i/crlf`; round 4's two carried |
| review round 6 | SHIP — B1–B7 and the deleted rule dead on fresh clones of the next commit, each with its count re-derived (889 · 0 · 888 · 1 · 689 · 1 · 3 · `probe` alone); the B7 fix refuted by clone bytes: every UTF-8 spelling git accepts reads 0 with the clone equal to the blob, `utf_8` and `UTF-16` on an ASCII blob are named and the clone is not the blob, `-ident` reads 0, an undefined `filter` driver is named; an unmerged index refuses by name; a foreign HOME with `~/.gitattributes`, `core.attributesFile` and an XDG attributes file all saying `* text=auto` changes no verdict in either direction. The record's numbers, the router's lines, the changelog and the public manifest re-derived. Named and left: `_fixture_env` inherits `XDG_CONFIG_HOME`, so on a box whose XDG attributes say `* text=auto` the red fixture's own `git add` normalises its CRLF file and the `i/crlf` leg reads unproven (`red=10`, still green) — one env entry and one assertion, carried in the commit message; `working-tree-encoding=` and `ident=foo` read red where git treats both as off, spellings nobody writes; rounds 4–5's carried items. The proof at the surface: `git clone -c core.autocrlf=true` of the next commit → `i/lf w/lf attr/-text`, 10 passed, the same flags that read `18c13a…` on the base |
| the gate | `bash standalone_check.sh \| tail -1` → `GRAPHY_STANDALONE_OK` · the floor `cd engine && ../.venv/bin/python -m pytest -q -o addopts=""` → 712 passed, 3 skipped (unchanged: no engine file moved) |

## 144 · THE FLOOR ASSERTS THE PLATFORM, NOT POSIX — on windows-latest the whole floor was red after the sibling rungs landed, and most of the red was the floor's own claims about POSIX: a mode bit, a fifo, `O_NOFOLLOW`, a case-sensitive seat, `chmod(0)` as unreadable, a file symlink to a directory, a held store's generation removed, the `bash` on PATH, a Windows path as a bash word, and the locale as the encoding of utf-8 the engine and git wrote; behind them stood the engine's own seams (`resolve_graph` read a `\\?\\`-prefixed link target as an escape, `discard_generations` removed a symlinked substrate) and a scheduling assertion in `test_index`; every test now asserts the platform's truth or skips by name with its reason, none is deleted, and the Windows job runs the whole floor but the tests an open issue owns, each deselected by name (2026-09-15 · graphyos issue 127)

Measured on the runner, 2026-09-15, without a Windows box: a branch of this repo (`win-floor-127`, pushed to the private remote, `gh workflow run ci.yml --ref win-floor-127`) with the whole floor appended to the `store-windows` job. Each run's red is the count of distinct failed node ids, re-derived by `gh run view <id> --repo omnislash157/graphyos --log-failed \| grep -oE 'FAILED tests[^ ]*' \| sort -u \| wc -l`; the counts live in this table and nowhere else in the section:

| run | red | what |
|---|---|---|
| 34924254896 | 23 | the baseline, `5a80057` + the step: the tests the issue's list names once the siblings' reds are gone, plus `test_review`'s `eol-rewritable` fixed fixture (`_seed` wrote it in text mode, so Windows committed CRLF), `test_scrub`'s `gh` hook reading a Windows path as a bash word and its tilde test (bash's `~` is `$HOME`, which Python's `expanduser` ignores on Windows), and the tests an open issue owns — the list, `gh run view 34924254896 --repo omnislash157/graphyos --log-failed \| grep -oE 'FAILED tests[^ ]*' \| sort -u` (its `wc -l` → `23`; the other runs' → `6`, `1`, `1`) |
| 34925004719 | 6 | the fixes: the unreadable helper's own restore in the `check` tests (`icacls /deny (R)` takes READ_CONTROL with it, so nothing can read the ACL back), a `/` in a regex over a path the OS spells `\`, a Windows path in the scrub test, and the symlinked substrate refused a third rebuild — the engine: `discard_generations` ran `sub.rmdir()` on the tenant's `substrate` link, which POSIX refuses with ENOTDIR and Windows performs |
| 34925382389 | 1 | `test_index`'s fan-out test: `len(seen) > 1` over the thread ids a spy saw — a pool hands the next entry to an idle thread, so the test's small shards can all hash on one; green on this box and on the earlier Windows runs, by timing |
| 34925662739 | 1 | the scrub test's remaining Windows paths in bash words (`D={home}`, a redirect target, a heredoc) |
| 34925964524 | 0 | green, every `store-windows` step. The floor step's passed and skipped, from its progress lines since `addopts = "-q"` suppresses the summary: `gh run view 34925964524 --repo omnislash157/graphyos --log \| grep "floor on this" \| sed 's/^[^Z]*Z //' \| grep -E '^[.sFE]+ *\[' \| tr -d ' \n' \| sed 's/\[[^]]*\]//g' \| awk '{print gsub(/\./,"") " " gsub(/s/,"")}'` → `678 23`. Deselected, from the step's own argv: `grep -o -- '--deselect [^ ]*' .github/workflows/ci.yml \| wc -l` → `3`. Its wall time: `gh api repos/omnislash157/graphyos/actions/runs/34925964524/jobs --jq '.jobs[]\|select(.name=="store-windows")\|.steps[]\|select(.name\|test("floor on this"))\|.started_at+" "+.completed_at'` → `2026-09-15T03:42:31Z 2026-09-15T03:43:33Z` |

- **The tests, each with its ruling.** `test_scrub` keygen: the `0o600` assertion holds where there are mode bits; on Windows the key's secrecy is the profile directory's ACL, and the rest of the test runs. `test_provision`: the fake runner lays out the venv the way this host's `python -m venv` does (`layout=os.name`) and the expected site-packages is named per host; the RED test that names the posix layout by name passes `os_name="posix"` explicitly, as its own title says, and matches either separator. `test_fanout`: a `_symlink` helper stages a redirect and skips by name on a seat that cannot create one; the case-alias probe skips when `toc.md` `samefile`s `TOC.md` (a case-folding seat cannot hold the alias); the post-open probe injects its EIO at `os.set_blocking` where a fifo could have been opened non-blocking and at `os.fdopen` on Windows, which has no fifo and never calls the former — the same flaw either way; the fifo leg runs where `os.mkfifo` exists; the forced-fallback probe sets `O_NOFOLLOW` to 0 with `raising=False`, since a host with none runs that branch every time. `test_cli`'s three `check` tests: `_unreadable`, mode 0 where there are mode bits and an explicit deny ACE for Everyone (`*S-1-1-0:(RD)`, which binds an administrator too) on Windows, lifted on exit — the door read `CHECK COULD-NOT-TELL` on both. `test_rebuild`: the symlinked substrate is a directory link (`target_is_directory=True`, which Windows distinguishes) and skips on a seat that cannot create one; the servable-through-a-rebuild test asserts that on Windows the generation the held store pins stays on disk until the handle closes, best-effort as #98 and #124 designed it, and elsewhere that it is gone. `test_shell`, `test_draw`, `test_showcase`: the child's utf-8 and the file's utf-8 are decoded as utf-8, never the locale — the bloodhound test was never ripgrep's, its reader thread had died in cp1252 and `stdout` was `None`. `test_showcase`'s fence test runs the workflow's step under Git's bash on Windows (the `bash` on PATH there is WSL's stub, which prints a UTF-16 install hint and exits 1), with `SYSTEMROOT` and a POSIX `RUNNER_TEMP`, and skips by name where no Git bash sits beside `git`. `test_index`'s fan-out test holds two workers at a `Barrier(2, timeout=10)` inside the spy, so the pool must start a second thread and a pool that never does breaks the barrier. `test_scrub`'s bash words are `as_posix()` on every host, since the command IS a bash command.
- **The engine.** `cartograph.resolve_graph` strips the `\\?\` (and `\\?\UNC\`) prefix `os.readlink` returns on Windows before judging whether a link escapes its parent, so a sibling link resolves to its target and the receipt and the content share one pin there too. `cli.discard_generations` never `rmdir`s a symlinked substrate: the link is the tenant's. `scrub.py` expands a bare `~` as bash does, from `$HOME`. `review.py`'s `_seed` writes its fixture with `newline="\n"`, the bytes as written.
- **The mark.** `ci.yml`'s `store-windows` job: the `path mark` step (a file allow-list with its own deselects) becomes `the floor on this platform`, the whole floor with a deselect for each test an open issue owns — `test_mcp`'s rebuild-after-refusal holds a store across calls (#134), `test_measure`'s profile-dir test imports `resource` (#88), `test_rebuild`'s pruned-lane test pins a separator #88 re-spells. The earlier marks stay as the named claims inside it, and the `path mark`'s comment now sits on the floor step as its history. The README's Windows paragraph says so.

| check | result |
|---|---|
| the done block | `cd engine && ../.venv/bin/python -m pytest -q` → green, no failure · `python3 workflows.py --run .github/workflows/ci.yml floor` → the floor job's steps here |
| red first | run 34924254896's whole-floor step, its count in the first table |
| green on the platform | run 34925964524, every `store-windows` step green; the floor step's counts in the first table |
| the battery | `python3 review.py \| tail -1` → `REVIEW OK` with 0 findings · `python3 review.py --selftest \| tail -1` → `REVIEW SELFTEST OK` |
| the workflow | `python3 workflows.py \| tail -1` → `WORKFLOWS OK` |
| the gate | `bash standalone_check.sh \| tail -1` → `GRAPHY_STANDALONE_OK` (review round 1 read `CHANGELOG DRIFT` here: the gate had run before this section existed; `release.sh --changelog` derived it and the gate was run again on the tree that ships) |
| review round 1 | REVISE — B1: the gate read `CHANGELOG DRIFT` on the tree with this section, while the row above claimed green from a run made before the section existed (class 1, the done line the record contradicts; the door is `release.sh --check` and it fired — NOT NEW); B2: this section's header and its first table row summed the twenty, the two engine reds, the scheduling red and the three owned to 26 against the run's 23 — the engine and scheduling reds surfaced in runs 2 and 3, behind the fixes, not in the baseline (BLOCK TWO ④, fixed in the prose). Non-blocking, named: the `\\?\` strip is not guarded on `os.name` (nothing writes such a link on POSIX); the pruned-lane deselect rests on #88's own claim; `chmod(0)` does not stop root. The Barrier proven load-bearing: a pool forced to one worker reads RED |
| review round 2 | REVISE — round 1's B1 dead (the gate green, `release.sh --check` OK); B2 not dead and a new one beside it: this section still counted the issue's list as seventeen tests and eighteen rows when run 34924254896 shows sixteen tests and seventeen rows (`gh run view 34924254896 --repo omnislash157/graphyos --log-failed \| grep -oE 'FAILED tests[^ ]*' \| sort -u`), and the Windows step's comment said twenty tests and one engine seam where there are nineteen tests (twenty rows) and two (BLOCK TWO ④, the same class twice — fixed in the prose and the comment). B2: round 1's fix was a text replace whose target, the short `the gate` row, also stood in section 142, so round 1's two rows were written into #132's shipped table under its round 2 SHIP as well as here; section 142 is restored byte-for-byte to its base and `review.py review-row-order` now names a review-round row that follows a round at or past its own in one section (red on its fixture and on the specimen, `RECON.md:6442`; green on this record, 17 review rows over 145 sections — NEW · review.py). Non-blocking, named: `_symlink` in test_fanout skips on any OSError; the `\\?\\` strip carried from round 1 |
| review round 3 | REVISE — the design round: round 2's two blockers dead on their specimens (the counts re-derived from run 34924254896, section 142 byte-identical to base, `review-row-order` red on the specimen and under a mutant, green on the record), and the record class a third time through four more copies of the same numbers: the red-first row still said the issue's list was twenty of the run's failures, the re-derive command this section gave matched no log line (`grep -E '^[^ ]*FAILED'` against a prefix that carries spaces), the battery row named a check count the tree had already passed, and the section and the workflow counted marks the job no longer had, with the path mark's comment left above no step. The ruling taken is the reviewer's smaller design, not a fifth patch: every count lives once, in the first table, beside a command that re-derives it (`grep -oE 'FAILED tests[^ ]*'`); the header, the check rows, the changelog line, the Windows step's name and comment and the README carry no count; the path mark's comment sits on the floor step as its history. B3's disposition ELIMINATED rather than a new check: a check-count check guards a count this design no longer writes (BLOCK TWO ④, carried as the specimen; the scope question it raises is graphyos #145) |
| review round 4 | REVISE — round 3's specimens dead but two carried through: the green row's command cut the joined progress line at its first percentage and printed `72 0` for a row claiming more, and gave the deselect count no source (④, round 3's specimen one row lower — the door is the reviewer running every command; no gate check can read an off-box log); counts survived outside the table in the header, the mark bullet and the scheduling row (④ again, a number-word check rejected as firing on innocents). Fixed as the reviewer's note says: every command in the table now sits beside the output it printed when the row was written, the deselect count reads the step's own argv, and the seams, the deselects and the shards are named, not counted; the path mark's comment on the floor step reads as that step's history |
| review round 5 | SHIP — every command in the first table run by the reviewer beside the output pasted there, each one matching; no count of tests, rows, marks, seams, deselects, checks or runs left outside the table; nothing since the green Windows run's head touches a `run:` line or the engine, and the new battery fixture that reaches the Windows floor through `test_review` reads the same under CRLF. Named and eliminated: the tests bullet's count of `test_cli`'s `check` tests describes the source, not a run; carried from earlier rounds, the `\\?\\` strip unguarded on `os.name`, the pruned-lane deselect resting on #88's own claim, `chmod(0)` under root, `_symlink` skipping on any OSError |

## 145 · 0.2.5 IS PUBLISHED — PyPI carried 0.2.4, cut before the relation fold (#68), the recorded doors (#111), the generation landing (#98), the Windows store, lock, handle, console, path, byte and floor rungs (#122 #124 #123 #125 #126 #127) and everything else since; the production Windows seat ran 0.2.4 and none of its asks were in a wheel; the operator ruled the release (2026-09-15 · graphyos issue 114)

- **The cut.** The version bumped in the six places `release.sh` reads it; `bash release.sh` built the wheel and sdist, passed `twine check`, found no 0.2.5 on PyPI to collide with, and derived the changelog. The `v0.2.5` tag on omnislash157/graphyos publishes by trusted publishing (`release.yml`).
- **What it carries.** Main at the tag: the rungs RECON §103 through §144 record. The shell hooks rung (#93) is not in it: its review round 2 read REVISE and the work stays off main.

| check | result |
|---|---|
| the done block | `pip index versions graphyos \| head -1` → the new version listed |
| the cut | `bash release.sh \| tail -1` |
| the gate | `bash standalone_check.sh \| tail -1` → `GRAPHY_STANDALONE_OK` |

## 146 · A HOOK RUNS ON THE HOST IT WAS WRITTEN FOR — `shell install` wrote every hook through text mode, so on Windows each `.sh` shebang read `bash\r` and failed even where bash exists, and it wired only bash hooks, so on a box with no bash the memory lane it reported installed never ran; every file the installer writes now carries the line ending it means (LF, and CRLF for a `.cmd`), each `.sh` hook has a `.cmd` twin, Codex and Cursor are wired to the twins on Windows, Claude Code keeps its bash hooks through Git Bash and its wiring refuses by name on a Windows box with none, and a floor test runs each harness's wiring through the shell that harness uses and reads the tail it captured back (2026-09-15 · graphyos issue 93)

Measured by the first client on a Windows Server box (the issue body), and its second cause read from the source in the issue's comment: `install.py`'s writes passed no `newline=`. How Claude Code runs a hook on Windows is documented (code.claude.com/docs/en/hooks-guide: Git Bash when installed, PowerShell otherwise); which shell Codex and Cursor use there is not, so their wiring is an unquoted `.cmd` path, the form cmd.exe and PowerShell both run.

- **The bytes.** One writer, `install._write`, for every file the installer writes: `newline="\n"`, and `"\r\n"` for the `.cmd` twins.
- **The interpreter.** `hooks/*.cmd` beside `hooks/*.sh`, the same work with no bash, written on Windows. `install.git_bash` finds the bash a harness would run: `bash` on PATH unless it is WSL's `System32` stub, else Git Bash beside `git`. On Windows, `--harness claude` with no Git Bash raises `ShellError` before a byte is written and names Git for Windows, WSL, and the Codex and Cursor wiring. `_host_command` rewrites a Codex or Cursor command to its `.cmd` twin there.
- **The floor.** `test_shell`: the bytes on disk (no CR in any LF file, the shebang `#!/usr/bin/env bash\n`, CRLF throughout a `.cmd`); the refusal and the `.cmd` wiring with Git Bash made absent; and each harness's wiring run as that harness runs it (`sh -c` off Windows; Git Bash for Claude Code and cmd.exe for the twins on Windows) with the harness payload on stdin — the end hook captures the fixture transcript into `reseed_tail.md`, and the start hook prints its session id back.

Runs on the private repo's branches (`gh run view <id> --repo omnislash157/graphyos --log-failed | grep -oE 'FAILED tests[^ ]*' | sort -u`):

| run | branch | result |
|---|---|---|
| 34975928381 | `win-93-red`: this diff with `_write` passing no `newline=`, the writer as it was | red on windows-latest: `test_RED_every_byte_the_install_writes_is_the_byte_it_means` → `before_edit.sh carries a CR` (the issue's own defect) and a `.cmd` not CRLF; red on both Linux floors on the `.cmd` bytes — the byte test is load-bearing on both hosts |
| 34975925412 | `win-93`, first cut | red on windows-latest in one test: the Claude wiring test handed its command to Git Bash as an argv, which Windows re-quotes (`unexpected EOF while looking for matching '"'`) — the test's harness, not the hook; the gate red on `BURDEN RED graphy/shell/install.py: host git-scm.com is not in burden.json` — the refusal named a download URL |
| 34976261092 | `win-93`, the command as a script file and no URL | green on every job, the round 1 cut; no `test_shell` skip in the Windows floor step (`gh run view 34976261092 --repo omnislash157/graphyos --log \| grep '^store-windows' \| grep 'SKIPPED \[' \| grep -c test_shell` → `0`) |
| 34977333501 | `win-93`, review round 1's fixes | green on every job; the wiring test runs each harness from a plain path and from `josh.shaw/First Last`, Claude Code's with the backslash `CLAUDE_PROJECT_DIR` it sets; no `test_shell` skip in the Windows floor step (the same `grep -c test_shell` → `0`) |

| check | result |
|---|---|
| the done lines | hooks the harness executes on a host with no bash, or a refusal by name: the `.cmd` wiring and the Claude refusal in `test_shell` · hook files LF regardless of host: the byte test, red under the mutant · the lifecycle events fire on Windows and the tail is captured and injected: the wiring test on windows-latest, run 34976261092 · a floor test on the bytes written: the same byte test |
| the floor | `cd engine && ../.venv/bin/python -m pytest -q` → no failure |
| the battery | `python3 review.py \| tail -1` → `REVIEW OK` with 0 findings |
| the gate | `bash standalone_check.sh \| tail -1` → `GRAPHY_STANDALONE_OK` |
| review round 1 | REVISE — three blockers, all reproduced: `_host_command` rewrote the first `.sh` anywhere in the command, so a Windows repo under a folder like `josh.shaw` got wiring to a file that does not exist; the `.cmd` commands were unquoted, so a repo under `C:/Users/First Last` split at the space in cmd.exe and PowerShell alike; and the Windows proof of Claude Code's capture set `CLAUDE_PROJECT_DIR` to the forward-slash spelling, where Claude Code sets the backslash one (BLOCK TWO ①). Fixed: the rewrite matches `"<path>/.graphy/hooks/<name>.sh"[ args]` whole and refuses a command it did not write; every Codex and Cursor command quotes its path on every host (the cursor template too); an earlier install's `.sh` command is retired from the wiring on Windows rather than left failing beside the twin (round 1's non-blocking, taken); the wiring test runs from both paths with the harness's own `CLAUDE_PROJECT_DIR`, and cmd.exe gets one command line, never an argv. Non-blocking, named: `%` in a path is expanded by cmd.exe; `session_start.cmd` waits on a console when run by hand with no argument; install callers in `test_cli` pass no `os_name` and would refuse on a Windows box with no Git Bash |
| production, linux | `specs/93.md`'s block: a clone of pallets/itsdangerous eaten and wired, two real `claude -p` sessions → `reseed_diag.log`: `inject ok source=startup … tail_session=<the first session>`; installing three times over 0.2.4's Cursor wiring → one entry per event; the Windows job on the landing tree, run 34984040468, `store-windows => success`; the production Windows seat's run is a fleet message |

## 147 · THE MCP SERVER HOLDS NO STORE BETWEEN CALLS — a live `graphy mcp` held one sqlite connection for its life, so on Windows `graphy build`'s `os.replace` at the store's own path was refused while any server was alive; every tool call now opens what `graphy <verb> --tenant` opens, answers and closes, on an answer, a refusal or a fault (2026-09-15 · graphyos issue 134)

- spec: `specs/134.md` · `python3 spec_lint.py specs/134.md` → `SPEC OK`

| check | result |
|---|---|
| production, linux | `.venv/bin/python engine/tests/mcp_drive.py --graphy .venv/bin/graphy /tmp/p134/repo itsdangerous` → `build under the live server: exit 0` · `MCP DRIVE OK` |
| production, windows | the Windows job on the landing tree runs the rebuild-under-a-live-server test the #134 deselect skipped: run 34984857074, `store-windows => success`; the production Windows seat's run is a fleet message |
| red first | the two new lifecycle tests against HEAD's `mcp.py` → `2 failed` |
| the battery | `python3 review.py \| tail -1` → `REVIEW OK` · `bash standalone_check.sh \| tail -1` → `GRAPHY_STANDALONE_OK` |

## 148 · A TYPESCRIPT ALIAS IMPORT BINDS TO THE MODULE IT NAMES — `$lib/api.js` bound nothing, so a SvelteKit app's routes imported nothing; the TypeScript producer reads `compilerOptions.paths` by TypeScript's rules through an `extends` chain, names a missing target in the mint receipt, applies Kit's documented `$lib` default in a Kit project with no `$lib` entry, stores every alias path relative to the project, and keys receipt reuse on the alias map (2026-09-15 · graphyos issue 102)

- spec: `specs/102.md` · `python3 spec_lint.py specs/102.md` → `SPEC OK`

| check | result |
|---|---|
| red first, production | a fresh clone of sveltejs/realworld eaten on HEAD: `graphy blast api.get` → `dependents=0` |
| production, linux | the same clone eaten on this tree: `graphy blast api.get --tenant /tmp/p102/rw/.graphy/tenant.json --tenant-id realworld_svelte_dev` → `dependents=7 own=7`, the route loaders by name |
| the receipt | `PROVENANCE.json` `sources.aliases` → `jsconfig.json`, `$lib` → `src/lib`, `missing: jsconfig.json extends ./.svelte-kit/tsconfig.json: .svelte-kit/tsconfig.json does not exist` |
| the battery | `python3 review.py \| tail -1` → `REVIEW OK` · `bash standalone_check.sh \| tail -1` → `GRAPHY_STANDALONE_OK` |

## 149 · 0.2.6 IS PUBLISHED — 0.2.5 was cut before the Windows hooks (#93), the MCP server that holds no store (#134) and the TypeScript alias imports (#102); this box's installs pinned 0.2.4 and 0.2.3 from PyPI and ran none of it (2026-09-15 · graphyos issue 93)

| check | result |
|---|---|
| the cut | `bash release.sh \| tail -1` → `RELEASE OK: graphyos 0.2.6 built and checked` |
| published | `pip index versions graphyos \| head -1` → `graphyos (0.2.6)` |

## 150 · A CP1252 STDIN READS THE UTF-8 A CLIENT WROTE — #123 reconfigured stdout and stderr and left stdin as the pipe gave it, so under a cp1252 stdin (what a Windows pipe gives Python) `graphy mcp` answered about `'JosÃ©'`, the gate resolved an edit under `…/José/…` outside the root and allowed it, and the capture hook named a transcript under that path missing; `_shared.utf8_streams` now judges stdin by the same rule, before any entry point's first read (2026-09-15 · graphyos issue 136)

- spec: `specs/136.md` · `python3 spec_lint.py specs/136.md` → `SPEC OK`

| check | result |
|---|---|
| red first, production | pallets/itsdangerous cloned under `/tmp/p136/José/repo` and eaten, on HEAD: the MCP `hunt` · the gate on an unwalked `class Signer:` edit · the capture each exit 1 in the spec's production block; P6 (the installed SessionEnd hook through `sh`) exit 1 |
| production, linux | the same block on this tree: `HUNT: 'José'` · the gate exit 2 `GATE BLOCKED` · `reseed_tail.md` written; P6 exit 0, the tail with no CR |
| the battery | `python3 review.py \| tail -1` → `REVIEW OK` · `bash standalone_check.sh \| tail -1` → `GRAPHY_STANDALONE_OK` |

## 151 · THE ENGINE'S OWN WIRING IS NOT DIRT — the cursor counted what the engine wrote into the checkout, so a fresh clone read CHECK RED straight after `graphy eat .` (the harness's CLAUDE.md and AGENTS.md pointers) and again after `graphy shell install` (GRAPHY.md and the harness files), each time naming `eat .` to absorb them; `cartograph.cursor_exclude` now takes the tenant's root and excludes `ENGINE_WIRING` and each pointer while it carries the harness's mark, every cursor caller passes the root, and `check` names `graphy eat .` only for a tenant eat owns — any other is told its own rebuild (2026-09-15 · graphyos issue 143)

- spec: `specs/143.md` · `python3 spec_lint.py specs/143.md` → `SPEC OK`

| check | result |
|---|---|
| red first, production | pallets/itsdangerous cloned fresh, on HEAD: `graphy eat .` → `CHECK RED: cursor lane: STALE — … 2 file(s)` (AGENTS.md · CLAUDE.md); after `shell install --harness claude --harness codex --harness cursor` → `6 file(s)` |
| production, linux | the same on this tree: `CHECK OK` after the install; one line planted in `src/itsdangerous/signer.py` → `CHECK RED: cursor lane: STALE — … 1 file(s) … re-eat the repo (graphy eat .)`; the graphy tenant, a house roster → `… run the tenant's own rebuild` |
| the upgrade | `graphyos==0.2.6` eats, installs and re-eats over the wiring's dirt; this tree's `check` → STALE naming `graphy eat .`; one eat → `CHECK OK` |
| three installs | a clone under `First Last`, `shell install` × 3 for every harness → `CHECK OK` |
| the battery | `python3 review.py \| tail -1` → `REVIEW OK` · `bash standalone_check.sh \| tail -1` → `GRAPHY_STANDALONE_OK` |

## 152 · WINDOWS RUNS THE WHOLE FLOOR — the last two tests the `store-windows` job deselected under #88 run there: a verb under `GRAPHY_PROFILE_DIR` imported `resource`, which Windows lacks, and now reads its peak working set through `ctypes`; the pruned-lane test re-pointed its descriptor with a string replace the JSON's escaped backslashes never matched, and now edits the parsed fields; the README says Windows is supported (2026-09-15 · graphyos issue 88)

- spec: `specs/88.md` · `python3 spec_lint.py specs/88.md` → `SPEC OK`

| check | result |
|---|---|
| red first, windows | branch `win-88-red`, HEAD's engine with both deselects removed, run 34993450573: `store-windows` failure — `test_GREEN_profile_dir_makes_every_verb_leave_its_stats_and_rss` (a traceback in the profiled child) · `test_RED_a_substrate_from_before_generations_never_brings_back_a_pruned_lane` (no `EAT DROPPED (1): dep_graph`) |
| production, linux | a fresh pallets/itsdangerous clone eaten under `GRAPHY_PROFILE_DIR` → `eat-<pid>.json` with `rss_kb` 32816 |
| the battery | `python3 review.py \| tail -1` → `REVIEW OK` · `bash standalone_check.sh \| tail -1` → `GRAPHY_STANDALONE_OK` |
