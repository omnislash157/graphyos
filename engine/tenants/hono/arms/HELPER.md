# HELPER — the response helpers, the client and JSX (`hono.helper` · `hono.client` · `hono.jsx`)

> Load before touching `html`/`css`/`streaming`/`ssg`/`cookie`/`factory` helpers, the typed RPC
> client `hc`, or the JSX runtime and its hooks. The walk crowns `helper` second by fan-out and
> orchestrates `client` from it; `jsx` rides here because the helpers render it. Hand-cut from the
> walk's evidence; the generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
`jsx.context.useContext` is the most consumed symbol in the arm (from the middleware's JSX
renderer); `jsx.base.JSXNode` / `renderChildren` / `isUntrustedObject` are the render core; the
helpers lean on UTILS `html.raw` / `escapeToBuffer` and `stream.StreamingApi`. The client is a
typed proxy over `fetch` and consumes CORE's types only.

## The load-bearing symbols (walk-derived)
`jsx.context.useContext` / `captureRenderContext` · `jsx.children.toArray` · `jsx.base.JSXNode` /
`renderChildren` / `isUntrustedObject` / `renderUntrustedObject` / `getNameSpaceContext` ·
`jsx.hooks.useState` / `useCallback` · `jsx.utils.styleObjectForEach` · `jsx.dom.jsx_dev_runtime.jsxDEV`
· `helper.*` (one directory per helper) · `client.hc`.

## Cross-pillar joins
- → **UTILS** (`html`, `stream`), → **CORE** (`Context`, `HTTPException`, `types`); ← **MIDDLEWARE** (`useContext`).

<!-- graphy:arm HELPER generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=2e520bd7738adf3d cut=sha256:aad24b7d6d30ad452e6d672f1c65479bba955ffa256137e2ad0ba1e436a2a3d8 content=sha256:6db408e5d4bccba6a12074617fc9ab642faceb43c31b04d95aa07fe620b969ea -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`hono.client.client`** — classes: `ClientRequestImpl` (1); functions: `appendQueryParams` · `createProxy` · `hc`
**`hono.client.client_test`** — classes: `SafeBigInt` (1); functions: `pathname`
**`hono.client.fetch_result_please`** — classes: `DetailedError` (1); functions: `detectResponseType` · `fetchRP`
**`hono.client.types`** — classes: `CallbackOptions` · `ClientResponse` (8) · `Response` · `TypedURL`
**`hono.client.utils`** — functions: `buildSearchParams` · `deepMerge` · `isObject` · `mergePath` · `parseResponse` · `removeIndexString` · `replaceUrlParam` · `replaceUrlProtocol`
**`hono.helper.accepts.accepts`** — classes: `Accept` · `acceptsConfig` · `acceptsOptions`; functions: `accepts` · `defaultMatch` · `getSpecificity` · `matchType`
**`hono.helper.adapter`** — functions: `checkUserAgentEquals` · `env` · `getRuntimeKey`
**`hono.helper.conninfo.types`** — classes: `ConnInfo`
**`hono.helper.cookie`** — classes: `GetCookie` · `GetSignedCookie`; functions: `deleteCookie` · `generateCookie` · `generateSignedCookie` · `getCookie` · `getSignedCookie` · `setCookie` · `setSignedCookie`
**`hono.helper.css`** — classes: `CssType` · `CxType` · `DefaultContextType` · `KeyframesType` · `StyleType` · `ViewTransitionType`; functions: `createCssContext`
**`hono.helper.css.common`** — classes: `CssClassName` · `CssEscapedString`; functions: `buildStyleString` · `cssCommon` · `cxCommon` · `defaultOnInvalidSlug` · `hasUnsafeSelectorChar` · `isValidClassName` · `isValidKeyframeName` · `keyframesCommon` · `minify` · `normalizeLabel` · `rawCssString` · `toHash` · `viewTransitionCommon`
**`hono.helper.css.common_case_test`** — classes: `Support`; functions: `renderTest`
**`hono.helper.css.index_test`** — functions: `toCSS` · `toString`
**`hono.helper.dev`** — classes: `RouteData` · `ShowRoutesOptions`; functions: `getRouterName` · `handlerName` · `inspectRoutes` · `showRoutes`
**`hono.helper.dev.index_test`** — functions: `namedHandler` · `namedMiddleware`
**`hono.helper.factory`** — classes: `CreateHandlersInterface`
**`hono.helper.html`** — functions: `html`
**`hono.helper.proxy`** — classes: `ProxyFetch` · `ProxyRequestInit`; functions: `buildRequestInitFromRequest` · `preprocessRequestInit` · `proxy`
**`hono.helper.route`** — functions: `basePath` · `baseRoutePath` · `matchedRoutes` · `routePath`
**`hono.helper.ssg.middleware`** — classes: `SSGParam` · `SSGParamsMiddleware`; functions: `disableSSG` · `isSSGContext` · `onlySSG` · `ssgParams`
**`hono.helper.ssg.plugins`** — functions: `defaultPlugin` · `generateRedirectHtml` · `redirectPlugin`
**`hono.helper.ssg.ssg`** — classes: `FileSystemModule` (2) · `SSGPlugin` · `ToSSGAdaptorInterface` · `ToSSGInterface` · `ToSSGOptions` · `ToSSGResult`; functions: `combineAfterGenerateHooks` · `combineAfterResponseHooks` · `combineBeforeRequestHooks` · `determineExtension` · `fetchRoutesContent` · `generateFilePath` · `parseResponseContent` · `saveContentToFile` · `toSSG`
**`hono.helper.ssg.ssg_test`** — functions: `resolveRoutesContent`
**`hono.helper.ssg.utils`** — classes: `FilterStaticGenerateRouteData`; functions: `dirname` · `ensureWithinOutDir` · `filterStaticGenerateRoutes` · `getPathRoot` · `getUncRoot` · `handleNonDot` · `handleParent` · `handleSegments` · `isDynamicRoute` · `joinPaths` · `normalizePath` · `toSegments`
**`hono.helper.streaming.sse`** — classes: `SSEMessage` · `SSEStreamingApi` (2); functions: `run` · `streamSSE`
**`hono.helper.streaming.stream`** — functions: `stream`
**`hono.helper.streaming.text`** — functions: `streamText`
**`hono.helper.streaming.utils`** — functions: `isOldBunVersion`
**`hono.helper.testing`** — functions: `testClient`
**`hono.helper.websocket`** — classes: `SendOptions` · `UpgradeWebSocket` · `WSContext` (4) · `WSContextInit` (2) · `WSEvents` · `WebSocketHelperDefineContext`; functions: `createWSMessageEvent` · `defineWebSocketHelper`
**`hono.jsx.base`** — classes: `JSXFragmentNode` (1) · `JSXFunctionNode` (1) · `JSXNode` (5); functions: `Fragment` · `childrenToStringToBuffer` · `cloneElement` · `getNameSpaceContext` · `isUntrustedObject` · `isValidElement` · `jsx` · `jsxFn` · `memo` · `renderChildren` · `renderUntrustedObject` · `resolveFunctionComponentResult` · `shallowEqual` · `toSVGAttributeName`
**`hono.jsx.children`** — functions: `toArray`
**`hono.jsx.components`** — functions: `ErrorBoundary` · `childrenToString` · `resolveChildEarly`
**`hono.jsx.components_test`** — functions: `Fallback` · `drainStream` · `replacementResult` · `resolveCallback` · `stringify`
**`hono.jsx.context`** — classes: `Context`; functions: `captureContextValues` · `captureRenderContext` · `createContext` · `getContextValuesIn` · `getCurrentStore` · `loadAsyncLocalStorage` · `readContextValueIn` · `resumeWithContextValues` · `runWithRenderContext` · `useContext` · `warnIfStorelessAccess`
**`hono.jsx.context_isolation_test`** — functions: `importAsyncHooks` · `importHooks` · `importIndex` · `importStreaming`
**`hono.jsx.dom`** — functions: `cloneElement` · `createElement` · `memo`
**`hono.jsx.dom.client`** — classes: `Root` (2); functions: `createRoot` · `hydrateRoot`
**`hono.jsx.dom.components`** — functions: `ErrorBoundary` · `Suspense`
**`hono.jsx.dom.components_test`** — functions: `runner`
**`hono.jsx.dom.context`** — functions: `createContext` · `createContextProviderFunction`
**`hono.jsx.dom.context_test`** — functions: `runner`
**`hono.jsx.dom.css`** — classes: `CreateCssJsxDomObjectsType` · `CssType` · `CxType` · `DefaultContextType` · `KeyframesType` · `ViewTransitionType`; functions: `createCssContext` · `createCssJsxDomObjects` · `splitRule`
**`hono.jsx.dom.hooks`** — functions: `registerAction` · `useActionState` · `useFormStatus` · `useOptimistic`
**`hono.jsx.dom.intrinsic_element.components`** — functions: `button` · `clearCache` · `composeRef` · `documentMetadataTag` · `form` · `formActionableElement` · `input` · `link` · `meta` · `script` · `style` · `title`
**`hono.jsx.dom.jsx_dev_runtime`** — functions: `Fragment` · `jsxDEV`
**`hono.jsx.dom.render`** — functions: `apply` · `applyNodeObject` · `applyProps` · `applySelectValue` · `build` · `buildNode` · `createPortal` · `findChildNodeIndex` · `findInsertBefore` · `flushSync` · `getEventSpec` · `getNameSpaceContext` · `getNextChildren` · `invokeTag` · `isIgnorableAttributeError` · `isNodeString` · `isSameContext` · `normalizeFormValue` · `removeNode` · `render` · `renderNode` · `replaceContainer` · `toAttributeName` · `update` · `updateSync`
**`hono.jsx.dom.server`** — classes: `RenderToReadableStreamOptions` · `RenderToStringOptions`; functions: `prepareRoot` · `renderToReadableStream` · `renderToString`
**`hono.jsx.dom.utils`** — functions: `setInternalTagFlag`
**`hono.jsx.hooks`** — functions: `createRef` · `documentStartViewTransition` · `forwardRef` · `isDepsChanged` · `runCallback` · `startTransition` · `startTransitionHook` · `startViewTransition` · `use` · `useCallback` · `useDebugValue` · `useDeferredValue` · `useEffect` · `useEffectCommon` · `useId` · `useImperativeHandle` · `useInsertionEffect` · `useLayoutEffect` · `useMemo` · `useReducer` · `useRef` · `useState` · `useTransition` · `useViewTransition` · `viewTransitionHook`
**`hono.jsx.index_test`** — classes: `SiteData`
**`hono.jsx.intrinsic_element.common`** — functions: `isStylesheetLinkWithPrecedence` · `shouldDeDupeByKey`
**`hono.jsx.intrinsic_element.components`** — functions: `button` · `documentMetadataTag` · `form` · `formActionableElement` · `input` · `insertIntoHead` · `link` · `meta` · `newJSXNode` · `returnWithoutSpecialBehavior` · `script` · `style` · `title`
**`hono.jsx.intrinsic_elements`** — classes: `IntrinsicElements`
**`hono.jsx.jsx_dev_runtime`** — functions: `jsxDEV`
**`hono.jsx.jsx_runtime`** — functions: `jsxAttr` · `jsxEscape`
**`hono.jsx.streaming`** — functions: `Suspense` · `renderToReadableStream` · `serializeBoundaryChild`
**`hono.jsx.streaming_test`** — functions: `drainStream` · `readInitialSuspenseChunk` · `replacementResult` · `stringify`
**`hono.jsx.utils`** — functions: `cacheValidName` · `hasUnsafeStyleValue` · `isValidAttributeName` · `isValidStylePropertyName` · `isValidTagName` · `normalizeIntrinsicElementKey` · `styleObjectForEach`

## The inherits joins out — generated

- `helper.streaming.sse.SSEStreamingApi` ──inherits──▶ `hono.utils.stream.StreamingApi` [UTILS]

## Re-walk — generated

```bash
T=tenants/hono
python3 -m graphy blast hono://func/hono.jsx.context.useContext --tenant $T/tenant.json --tenant-id hono
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id hono --corpus hono --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id hono --corpus hono --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm HELPER -->
