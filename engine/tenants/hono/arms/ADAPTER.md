# ADAPTER — the runtimes and the presets (`hono.adapter` · `hono.preset`)

> Load before touching a runtime binding (Cloudflare Workers/Pages, Deno, Bun, Node's
> `serveStatic`, AWS Lambda, Netlify, Vercel, Service Worker, Fastly) or a preset (`quick`, `tiny`).
> The walk crowns `adapter` as a stand-alone orchestrator and `preset` likewise; hand-cut together
> because both are the outermost layer: they pick a router and bind the app to a runtime. The
> generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
Nothing in the package consumes an adapter. An adapter reaches CORE for a router class and
`HTTPException`, HELPER for `serveStatic`'s shared core, UTILS for base64 and mime types. The
AWS Lambda handler is the one class hierarchy here: `EventProcessor` with its V1, V2, ALB and
Lattice subclasses.

## The load-bearing symbols (walk-derived)
`adapter.aws_lambda.handler.EventProcessor` (→ `EventV1Processor` · `EventV2Processor` ·
`ALBProcessor` · `LatticeV2Processor`) · `adapter.cloudflare_workers.serve_static.serveStatic` ·
`adapter.bun.server.getBunServer` · `adapter.service_worker.handler.handle` · `preset.quick.Hono`
· `preset.tiny.Hono`.

## Cross-pillar joins (all outbound)
- → **CORE** (the router classes, `HTTPException`), → **HELPER**, → **UTILS** (`encode`).

<!-- graphy:arm ADAPTER generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=2e520bd7738adf3d cut=sha256:aad24b7d6d30ad452e6d672f1c65479bba955ffa256137e2ad0ba1e436a2a3d8 content=sha256:6501a9dfa1d98de42af36646b9a226ac01c17d87be79efd7f25e229c392eeef3 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`hono.adapter.aws_lambda.conninfo`** — functions: `getConnInfo`
**`hono.adapter.aws_lambda.handler`** — classes: `ALBProcessor` (6) · `ALBProxyEvent` · `APIGatewayProxyEvent` · `APIGatewayProxyEventV2` · `EventProcessor` (11) · `EventV1Processor` (6) · `EventV2Processor` (6) · `LatticeProxyEventV2` · `LatticeV2Processor` (6); functions: `defaultIsContentTypeBinary` · `getProcessor` · `getRequestContext` · `handle` · `isContentEncodingBinary` · `isLatticeEventV2` · `isProxyEventALB` · `isProxyEventV2` · `sanitizeHeaderValue` · `streamHandle` · `streamToNodeStream`
**`hono.adapter.aws_lambda.types`** — classes: `ALBRequestContext` · `ApiGatewayRequestContext` · `ApiGatewayRequestContextV2` · `Authorizer` · `ClientCert` · `ClientContext` · `ClientContextClient` · `ClientContextEnv` · `CognitoIdentity` · `Identity` · `LambdaContext` (1) · `LatticeRequestContextV2`
**`hono.adapter.bun.conninfo`** — functions: `getConnInfo`
**`hono.adapter.bun.conninfo_test`** — functions: `createRandomBunServer`
**`hono.adapter.bun.serve_static`** — functions: `serveStatic`
**`hono.adapter.bun.server`** — functions: `getBunServer`
**`hono.adapter.bun.ssg`** — functions: `toSSG`
**`hono.adapter.bun.websocket`** — classes: `BunServerWebSocket` (2) · `BunWebSocketData` · `BunWebSocketHandler` (3) · `CreateWebSocket`; functions: `createBunWebSocket` · `createWSContext`
**`hono.adapter.cloudflare_pages.conninfo`** — functions: `getConnInfo`
**`hono.adapter.cloudflare_pages.handler`** — functions: `handle` · `handleMiddleware` · `serveStatic`
**`hono.adapter.cloudflare_pages.handler_test`** — functions: `createEventContext`
**`hono.adapter.cloudflare_workers.conninfo`** — functions: `getConnInfo`
**`hono.adapter.cloudflare_workers.serve_static`** — functions: `serveStatic`
**`hono.adapter.cloudflare_workers.serve_static_module`** — functions: `module`
**`hono.adapter.cloudflare_workers.utils`** — functions: `getContentFromKVAsset`
**`hono.adapter.deno.conninfo`** — functions: `getConnInfo`
**`hono.adapter.deno.serve_static`** — functions: `serveStatic`
**`hono.adapter.deno.ssg`** — functions: `toSSG`
**`hono.adapter.lambda_edge.conninfo`** — functions: `getConnInfo`
**`hono.adapter.lambda_edge.handler`** — classes: `Callback` · `CloudFrontConfig` · `CloudFrontCustomOrigin` · `CloudFrontEdgeEvent` · `CloudFrontEvent` · `CloudFrontHeader` · `CloudFrontHeaders` · `CloudFrontRequest` · `CloudFrontResponse` · `CloudFrontResult` · `CloudFrontS3Origin`; functions: `convertHeaders` · `createBody` · `createRequest` · `createResult` · `handle` · `isContentTypeBinary`
**`hono.adapter.netlify.conninfo`** — functions: `getConnInfo`
**`hono.adapter.netlify.handler`** — functions: `handle`
**`hono.adapter.service_worker`** — functions: `fire`
**`hono.adapter.service_worker.handler`** — functions: `handle`
**`hono.adapter.service_worker.types`** — classes: `ExtendableEvent` (1) · `FetchEvent` (1)
**`hono.adapter.vercel.conninfo`** — functions: `getConnInfo`
**`hono.adapter.vercel.handler`** — functions: `handle`
**`hono.preset.quick`** — classes: `Hono` (1)
**`hono.preset.tiny`** — classes: `Hono` (1)

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/hono
python3 -m graphy blast hono://func/hono.adapter.bun.server.getBunServer --tenant $T/tenant.json --tenant-id hono
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id hono --corpus hono --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id hono --corpus hono --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm ADAPTER -->
