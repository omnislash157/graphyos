# MIDDLEWARE — the built-ins (`hono.middleware` · `hono.validator`)

> Load before touching a shipped middleware (cors, jwt, basic/bearer auth, logger, cache, compress,
> etag, secure-headers, csrf, body-limit, …) or the validator. The walk crowns `middleware` first
> by fan-out. Hand-cut from the walk's evidence; `validator` rides here because it is a middleware
> factory the walk cannot place (it stands alone). The generated region at the bottom is the walk's
> own inventory and the re-walk.

## ⚖ The law of this arm
Every middleware is a factory returning `(c, next) => …`; it reads `Context`, may raise
`HTTPException`, and reaches UTILS for encoding, JWT and accept parsing. Nothing in the package
consumes a middleware except the presets and the tests.

## The load-bearing symbols (walk-derived)
The factories under `middleware.*` (one directory per middleware, `index.ts` the door) ·
`validator.validator`.

## Cross-pillar joins (all outbound)
- → **CORE** (`Context`, `HTTPException`), → **UTILS** (`encode`, `jwt`, `accept`, `cookie`).

<!-- graphy:arm MIDDLEWARE generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=2e520bd7738adf3d cut=sha256:aad24b7d6d30ad452e6d672f1c65479bba955ffa256137e2ad0ba1e436a2a3d8 content=sha256:f1aa18d6226e8a089352fcbff6119b7ea4ea8fa7ef43e5e61864e236190921b0 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`hono.middleware.basic_auth`** — functions: `basicAuth`
**`hono.middleware.bearer_auth`** — functions: `bearerAuth`
**`hono.middleware.body_limit`** — functions: `bodyLimit`
**`hono.middleware.body_limit.index_test`** — functions: `buildRequestInit`
**`hono.middleware.cache`** — functions: `cache` · `createCacheKey` · `createQueryDigest` · `parseVaryDirectives` · `reportCacheNotAvailable` · `shouldSkipCache` · `shouldSkipCacheControl`
**`hono.middleware.cache.index_test`** — classes: `Context` (2) · `MockCache` (4)
**`hono.middleware.combine`** — functions: `every` · `except` · `some`
**`hono.middleware.combine.index_test`** — functions: `nextMiddleware`
**`hono.middleware.compress`** — classes: `CompressionOptions`; functions: `compress` · `selectEncoding` · `shouldTransform`
**`hono.middleware.compress.index_test`** — functions: `decompressResponse`
**`hono.middleware.context_storage`** — functions: `contextStorage` · `getContext` · `tryGetContext`
**`hono.middleware.cors`** — functions: `cors`
**`hono.middleware.csrf`** — classes: `CSRFOptions`; functions: `csrf` · `isSecFetchSite`
**`hono.middleware.csrf.index_test`** — functions: `buildSimplePostRequestData`
**`hono.middleware.etag`** — functions: `etag` · `etagMatches` · `initializeGenerator` · `stripWeak`
**`hono.middleware.etag.digest`** — functions: `generateDigest` · `mergeBuffers`
**`hono.middleware.etag.index_test`** — functions: `createPatternedBody`
**`hono.middleware.ip_restriction`** — classes: `IPRestrictionRules`; functions: `buildMatcher` · `ipRestriction` · `parseCidrPrefix`
**`hono.middleware.jsx_renderer`** — functions: `createRenderer` · `jsxRenderer` · `useRequestContext`
**`hono.middleware.jsx_renderer.index_test`** — functions: `RequestUrl`
**`hono.middleware.jwk.jwk`** — functions: `jwk` · `unauthorizedResponse`
**`hono.middleware.jwt.jwt`** — functions: `jwt` · `unauthorizedResponse`
**`hono.middleware.language.language`** — classes: `DetectorOptions` · `LanguageVariables`; functions: `cacheLanguage` · `detectFromCookie` · `detectFromHeader` · `detectFromPath` · `detectFromQuery` · `detectLanguage` · `languageDetector` · `normalizeLanguage` · `parseAcceptLanguage` · `validateOptions`
**`hono.middleware.logger`** — functions: `colorStatus` · `humanize` · `log` · `logger` · `time`
**`hono.middleware.method_not_allowed`** — functions: `methodNotAllowed`
**`hono.middleware.method_override`** — functions: `getExecutionCtx` · `methodOverride`
**`hono.middleware.powered_by`** — functions: `poweredBy`
**`hono.middleware.pretty_json`** — classes: `PrettyOptions`; functions: `prettyJSON`
**`hono.middleware.request_id.request_id`** — functions: `requestId`
**`hono.middleware.secure_headers.secure_headers`** — classes: `ContentSecurityPolicyOptions` · `ReportToEndpoint` · `ReportToOptions` · `ReportingEndpointOptions` · `SecureHeadersOptions`; functions: `NONCE` · `camelToKebab` · `generateNonce` · `getCSPDirectives` · `getFilteredHeaders` · `getPermissionsPolicyDirectives` · `getReportToOptions` · `getReportingEndpoints` · `secureHeaders` · `setHeaders`
**`hono.middleware.serve_static`** — functions: `serveStatic`
**`hono.middleware.serve_static.path`** — functions: `defaultJoin`
**`hono.middleware.timeout`** — functions: `timeout`
**`hono.middleware.timing.timing`** — classes: `SetMetric` · `Timer` · `TimingOptions`; functions: `endTime` · `getTime` · `setMetric` · `startTime` · `timing` · `wrapTime`
**`hono.middleware.trailing_slash`** — functions: `appendTrailingSlash` · `trimTrailingSlash`
**`hono.validator.validator`** — functions: `validator`
**`hono.validator.validator_test`** — functions: `onErrorHandler` · `zodValidator`

## The inherits joins out — generated

- `middleware.cache.index_test.Context` ──inherits──▶ `hono.context.ExecutionContext` [CORE]

## Re-walk — generated

```bash
T=tenants/hono
python3 -m graphy blast hono://func/hono.middleware.jsx_renderer.useRequestContext --tenant $T/tenant.json --tenant-id hono
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id hono --corpus hono --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id hono --corpus hono --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm MIDDLEWARE -->
