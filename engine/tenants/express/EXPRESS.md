# Express — the tenant router

> The arm-doc law: no numbers, no status, no history — only the tap. Every symbol named here came
> out of the walk; re-walk before you trust it. Counts, with the commands that re-derive them, live
> in `RECON.md` at the working-repo root, never here.

**What this tenant is.** JavaScript through the `typescript_ast` producer: Express 5 at a pinned
tag, its `lib/` minted from CommonJS — `require` bound as imports (a bare name to the module, a
destructured name to the symbol, `exports.x = require(…)` a re-export), a function assigned to a
member (`app.listen = function …`, `exports.query = function …`) read as a definition — and its
runtime ring followed into the checkout's own `node_modules`: every dependency ships JavaScript
and every one mints. The same resolver binds the labels (`require`'d names through the import
bindings, `this` against the containing class), the same verbs build, audit, fan out and arm.
Nothing downstream of the IR knows the language.

**What the producer says and does not say.** A checkout is read from its source and its build
output is skipped; a shipped package (no `src/`) is read from what it ships, `lib/` and `dist/`
included. `module.exports = function name …` is `name`; an anonymous function assigned to
`module.exports` has no name and is no node. A getter installed by a call (`defineGetter(req,
'protocol', …)`) is a call, not a definition, and stays text. `.min.js` is skipped.

## ⚖ THE FOUR PILLARS — cut by module, because the walk rules the package one pillar; each arm file ends in the walk's own generated region

| pillar | router | modules | the choke point | joins out |
|---|---|---|---|---|
| **APPLICATION** | [`arms/APPLICATION.md`](arms/APPLICATION.md) | `express` · `application` | `createApplication` · `app.handle` | `router` · `finalhandler` · `debug` · `depd` |
| **REQUEST** | [`arms/REQUEST.md`](arms/REQUEST.md) | `request` | `req.get` · `req.accepts` | `accepts` · `type-is` · `parseurl` · `proxy-addr` · `fresh` · `range-parser` |
| **RESPONSE** | [`arms/RESPONSE.md`](arms/RESPONSE.md) | `response` | `res.send` · `res.render` | `send` · `content-disposition` · `cookie` · `etag` · `mime-types` · `statuses` · `vary` |
| **UTILS** | [`arms/UTILS.md`](arms/UTILS.md) | `utils` · `view` | `compileETag` · `View.render` | `etag` · `mime-types` · `content-type` · `qs` |

**Where the hand and the walk disagree.** `graphy pillars` says: no orchestrator at depth 2 —
every module is consumed more than it consumes — cut deeper or it is one pillar. It is one
pillar; the curated file cuts it by module so an agent lands in the file it needs. The proposal
is recorded as that sentence in `substrate/pillars.txt` on every rebuild.

## THE TAPS — run from `engine/`, the tenant dir is `T=tenants/express`

| move | the tap |
|---|---|
| rebuild the tenant: pin the checkout, install the runtime ring, mint, converge, build, check, fan out, verify the arms | `PYTHON=../.venv/bin/python bash $T/rebuild.sh` → `EXPRESS_TENANT_OK` — `EXPRESS_RELEASE=<tag>` pins another tag; `EXPRESS_NODE_MODULES=<abs>` resolves the ring from elsewhere |
| what the ring holds, and what node_modules could not carry | `python3 -c 'import json;r=json.load(open("$T/substrate/ring.json"));print(len(r["minted"]), sorted(r["minted"])[:10]);print(r["unresolved"])'` |
| the doors | `python3 -m graphy descend\|blast\|explain <symbol> --tenant $T/tenant.json --tenant-id express` — e.g. `descend app.handle`, `blast res.send`, `explain createApplication` |
| does A reach B, across the ring | `python3 -m graphy walk --tenant $T/tenant.json --tenant-id express --seed express://func/express.application.app.handle --target router://module/router` |
| eat a JavaScript repo in one verb | `../.venv/bin/graphy eat --repo <abs> --site-packages <abs>/node_modules`; `bash ../quickstart.sh https://github.com/expressjs/express.git` |
| the generated region in each arm file | `python3 -m graphy arms --tenant $T/tenant.json --tenant-id express --corpus express --partition $T/partition.json --dir $T/arms` · `--verify` |

Node ids are `express://<node_type>/<dotted>` — `express://func/express.application.app.listen`,
`express://func/express.response.res.send`, `express://class/express.view.View`.
