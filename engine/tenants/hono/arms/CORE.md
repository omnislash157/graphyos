# CORE — the app and the request lifecycle (`hono.hono` · `hono_base` · `context` · `request` · `router` · `compose` · `http_exception` · `types`)

> Load before touching the `Hono` class, the `Context` a handler receives, `HonoRequest`, the
> router interface and its implementations, the middleware composer, or `HTTPException`. Hand-cut
> from the walk's evidence: the walk rules these shared under the floor (no arm takes two thirds of
> their fan-in) and this arm gathers them because they are the one request path every other arm
> rides. The generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
`Hono` (a preset over `HonoBase`) owns the router and dispatches; `compose` folds the middleware
stack into one handler; `Context` is what a handler and every middleware receives; the `Router`
interface has five implementations (`TrieRouter`, `RegExpRouter`, `PatternRouter`, `LinearRouter`,
`SmartRouter`) and the presets choose among them. `HTTPException` is raised from the middleware
and the helpers and caught by the app.

## The load-bearing symbols (walk-derived)
`router.Router` · `router.UnsupportedPathError` · `router.utils.createNullObject` · the five
router classes · `request.HonoRequest` · `request.cloneRawRequest` · `compose.compose` ·
`http_exception.HTTPException` · `hono_base.HonoBase` · `hono.Hono` · `context.Context`.

## Cross-pillar joins
- ← **ADAPTER** and the presets pick a router class; ← **MIDDLEWARE** and **HELPER** raise
  `HTTPException` and read `Context`; → **UTILS** for URL merging and decoding.

<!-- graphy:arm CORE generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=2e520bd7738adf3d cut=sha256:aad24b7d6d30ad452e6d672f1c65479bba955ffa256137e2ad0ba1e436a2a3d8 content=sha256:b5a70f2138784dd3e5efe731c2a24b3a17b803d90042a41abdfe0137d622e313 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`hono.compose`** — functions: `compose`
**`hono.context`** — classes: `BodyRespond` · `Context` (7) · `ContextRenderer` · `ContextVariableMap` · `DefaultRenderer` · `ExecutionContext` (2) · `Get` · `HTMLRespond` · `JSONRespond` · `NewResponse` · `ResponseInit` · `Set` · `SetHeaders` · `SetHeadersOptions` · `TextRespond`; functions: `createResponseInstance` · `setDefaultContentType`
**`hono.hono`** — classes: `Hono` (1)
**`hono.hono_base`** — classes: `Hono` (8); functions: `errorHandler` · `notFoundHandler`
**`hono.http_exception`** — classes: `HTTPException` (2)
**`hono.request`** — classes: `HonoRequest` (22); functions: `cloneRawRequest`
**`hono.router`** — classes: `Router` (2) · `UnsupportedPathError`
**`hono.router.common_case_test`** — functions: `getSuiteHierarchy` · `runTest`
**`hono.router.linear_router.router`** — classes: `LinearRouter` (2)
**`hono.router.pattern_router.router`** — classes: `PatternRouter` (2)
**`hono.router.reg_exp_router.matcher`** — functions: `match`
**`hono.router.reg_exp_router.node`** — classes: `Context` · `Node` (2); functions: `compareKey`
**`hono.router.reg_exp_router.prepared_router`** — classes: `PreparedRegExpRouter` (5); functions: `buildInitParams` · `serializeInitParams`
**`hono.router.reg_exp_router.router`** — classes: `RegExpRouter` (5); functions: `buildWildcardRegExp` · `findMiddleware`
**`hono.router.reg_exp_router.trie`** — classes: `Trie` (2)
**`hono.router.smart_router.router`** — classes: `SmartRouter` (4)
**`hono.router.trie_router.node`** — classes: `Node` (3)
**`hono.router.trie_router.router`** — classes: `TrieRouter` (2)
**`hono.router.utils`** — functions: `createNullObject`
**`hono.types`** — classes: `HTTPResponseError` · `HandlerInterface` · `NotFoundResponse` · `RouterRoute`

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/hono
python3 -m graphy blast hono://class/hono.router.Router --tenant $T/tenant.json --tenant-id hono
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id hono --corpus hono --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id hono --corpus hono --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm CORE -->
