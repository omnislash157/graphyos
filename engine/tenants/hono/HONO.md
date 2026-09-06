# Hono — the tenant router

> The arm-doc law: no numbers, no status, no history — only the tap. Every symbol named here came
> out of the walk; re-walk before you trust it. Counts, with the commands that re-derive them, live
> in `RECON.md` at the working-repo root, never here.

**What this tenant is.** The second language. Hono's TypeScript source at a pinned tag, minted by
the `typescript_ast` producer (tree-sitter parses, the producer maps onto the same nine words the
Python producer emits: module · func · class · method; imports · contains · calls · inherits ·
decorates), converged by the same resolver (a local definition, the module's own import bindings
through re-exports, `this` against the containing class, `super` against a resolved base), built,
audited, fanned out and armed by the same verbs. No consumer downstream knows the language: the
store, the walk, the doors, pillars, arms and the bridge read only the vocabulary. `rebuild.sh`
pins the checkout under `staging/corpora/ts/hono`, mints from `src/`, resolves the ring from the
checkout's `node_modules` — Hono declares no runtime dependency, so the ring is the root shard
alone and the receipt names every specifier the tests import that node_modules did not carry.

**What the producer says and does not say.** A file is a module (`index.ts` folds to its
directory); `class`, `abstract class` and `interface` are class; a `function` declaration or a
module-level `const x = () => …` is func; a method or accessor is method. Bare specifiers become
`pkg://module/pkg` literals — wormholes once that package is minted, Node's built-ins the
ecosystem's standard library. A package under node_modules that ships only `dist/` JavaScript is
not a corpus this producer reads: the ring reports it, never parses build output. Type aliases,
enums and namespaces are not in the vocabulary and are not nodes; a call on a parameter
(`c.json(…)`, `app.get(…)`) is a label no scope binds and stays text.

## ⚖ THE FIVE PILLARS — cut by hand from the walk's evidence, marked as such; each arm file ends in the walk's own generated region

| pillar | router | modules | the choke point | joins out |
|---|---|---|---|---|
| **CORE** — the app and the request path | [`arms/CORE.md`](arms/CORE.md) | `hono` · `hono_base` · `context` · `request` · `router` · `compose` · `http_exception` · `types` | `router.Router` and its five implementations · `compose` | none |
| **UTILS** — the floor | [`arms/UTILS.md`](arms/UTILS.md) | `utils` | `html.raw` · `encode` · `url.mergePath` | Node `crypto` · `fs` · `path` (the standard library) |
| **MIDDLEWARE** — the built-ins | [`arms/MIDDLEWARE.md`](arms/MIDDLEWARE.md) | `middleware` · `validator` | the factories | none |
| **HELPER** — helpers, the client, JSX | [`arms/HELPER.md`](arms/HELPER.md) | `helper` · `client` · `jsx` | `jsx.context.useContext` · `jsx.base.JSXNode` | none |
| **ADAPTER** — runtimes and presets | [`arms/ADAPTER.md`](arms/ADAPTER.md) | `adapter` · `preset` | `aws_lambda.handler.EventProcessor` | Node `async_hooks` |

**Where the hand and the walk disagree.** `graphy pillars` (which skips every node the producer
marks `role: test`) crowns `middleware`, `helper`, `adapter`, `preset` and `validator` by fan-out
and makes `utils` the floor with `types`, `context`, `router` and `hono` shared under it. The
curated file gathers the request path into CORE because a change to how a request is dispatched
lands in all of them; folds `preset` into ADAPTER and `validator` into MIDDLEWARE because each is
one file that stands alone only by the numbers; and moves `jsx` from MIDDLEWARE to HELPER because
the helpers render it. `graphy pillars --against partition.json` names every unit cut
differently, with the numbers.

## THE EDGE — routed here, no arm

The package `index.ts` (the facade), and every `*.test.ts` beside the sources: the producer marks
them `role: test`, the doors list them under "tests", and pillars ignore them.

## THE TAPS — run from `engine/`, the tenant dir is `T=tenants/hono`

| move | the tap |
|---|---|
| rebuild the tenant: pin the checkout, mint with tree-sitter, converge, build, check, fan out, verify the arms | `PYTHON=../.venv/bin/python bash $T/rebuild.sh` → `HONO_TENANT_OK` — the interpreter needs `graphyos[typescript]`; `HONO_RELEASE=<tag>` pins another tag; `HONO_NODE_MODULES=<abs>` resolves the ring from elsewhere |
| rebuild the tenant from a shard index instead of minting — every shard a `pulled` lane | `GRAPHY_SHARD_INDEX=<abs dir or https base> GRAPHY_PULL="hono==4.13.7 zod==4.5.4" PYTHON=../.venv/bin/python bash $T/rebuild.sh` → `PULL OK` ×2 · `HONO_TENANT_OK` |
| mint any TypeScript package | `python3 -m graphy smash --package <slug> --site-packages <node_modules> --corpus <src dir> --out <abs> --producer typescript_ast` |
| eat a TypeScript repo in one verb | `../.venv/bin/graphy eat --repo <abs> --site-packages <abs>/node_modules` — the producer is chosen from `package.json` when no Python package is found; `bash ../quickstart.sh <ts repo url>` does the clone, the install and the eat |
| what the ring holds, and what node_modules could not carry | `python3 -c 'import json;r=json.load(open("$T/substrate/ring.json"));print(r["producer"], sorted(r["minted"]));print(r["unresolved"])'` |
| draw it: the pillars, the unit map, one arm, a symbol's neighbourhood — the rebuild lands the atlas at `$T/substrate/atlas/` | `python3 -m graphy draw --tenant $T/tenant.json --tenant-id hono --corpus hono --pillars --partition $T/partition.json --lr` · `--symbol hono.compose.compose --radius 2 --emit html --interactive -o page.html` · `--check page.html` |
| the doors | `python3 -m graphy descend\|blast\|explain <symbol> --tenant $T/tenant.json --tenant-id hono` — e.g. `blast hono.router.Router`, `descend hono.compose.compose`, `explain hono.request.HonoRequest` |
| does A reach B | `python3 -m graphy walk --tenant $T/tenant.json --tenant-id hono --seed hono://class/hono.hono.Hono --target hono://class/hono.router.trie_router.router.TrieRouter` |
| the bridge into a Python tenant | `python3 -m graphy bridge --tenant $T/tenant.json --tenant-id hono --tenant tenants/fastapi/tenant.json --tenant-id fastapi --join <scheme> …` — no scheme is minted on both sides today, so every join refuses by name: the refusal is the evidence, never a guess |
| the arms the walk proposes; the units it cuts differently | `python3 -m graphy pillars --tenant $T/tenant.json --tenant-id hono --corpus hono` · `--against $T/partition.json` |
| the generated region in each arm file | `python3 -m graphy arms --tenant $T/tenant.json --tenant-id hono --corpus hono --partition $T/partition.json --dir $T/arms` · `--verify` |
| the MCP server over this tenant | `python3 -m graphy mcp --tenant $T/tenant.json --tenant-id hono` |

Node ids are `hono://<node_type>/<dotted>` — `hono://class/hono.hono.Hono`,
`hono://func/hono.compose.compose`, `hono://method/hono.request.HonoRequest.json`; a directory's
`index.ts` is the directory's module (`hono://module/hono.router.trie_router`).
