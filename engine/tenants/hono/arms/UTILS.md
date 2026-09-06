# UTILS — the floor (`hono.utils`)

> Load before touching HTML escaping, base64, URL handling, JWT, streams, cookies, mime types, or
> any helper shared across the package. The walk names `utils` the floor: the greatest fan-in no
> arm owns. Hand-cut from the walk's evidence; the generated region at the bottom is the walk's own
> inventory and the re-walk.

## ⚖ The law of this arm
Nothing here knows about `Hono` or `Context`. `html.raw` and `html.escapeToBuffer` are the most
called symbols from the helpers; `encode.encodeBase64` / `decodeBase64` serve the adapters and
the middleware; `url.mergePath` · `checkOptionalParameter` · `tryDecodeURIComponent` serve the
router; `jwt.types` carries the token error classes; `stream.StreamingApi` is the streaming
helpers' base.

## The load-bearing symbols (walk-derived)
`html.raw` · `html.escapeToBuffer` · `encode.encodeBase64` / `decodeBase64` / `decodeBase64Url` ·
`url.mergePath` / `checkOptionalParameter` / `tryDecodeURIComponent` · `accept.parseAccept` ·
`jwt.types.JwtTokenInvalid` / `JwtHeaderInvalid` · `stream.StreamingApi`.

## Cross-pillar joins (all inbound)
- ← **HELPER** (html, streams), **MIDDLEWARE** (accept, encode, jwt), **ADAPTER** (encode), **CORE** (url).

<!-- graphy:arm UTILS generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=2e520bd7738adf3d cut=sha256:aad24b7d6d30ad452e6d672f1c65479bba955ffa256137e2ad0ba1e436a2a3d8 content=sha256:44bf6781a5da5e31db92f9c1c9249201f6bd038a884a12f38cfd7dc70483bedc -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`hono.utils.accept`** — classes: `Accept`; functions: `consumeWhitespace` · `getNextAcceptValue` · `getNextParam` · `ignoreTrailingWhitespace` · `isWhitespace` · `parseAccept` · `parseQuality` · `skipInvalidAcceptValue` · `skipInvalidParam`
**`hono.utils.basic_auth`** — functions: `auth`
**`hono.utils.body`** — classes: `ParseBody`; functions: `convertFormDataToBodyData` · `handleParsingAllValues` · `handleParsingNestedValues` · `isRawRequest` · `parseBody` · `parseFormData` · `throwNestingLimitExceeded`
**`hono.utils.buffer`** — functions: `bufferToFormData` · `bufferToString` · `constantTimeEqualString` · `equal` · `timingSafeEqual` · `timingSafeEqualString`
**`hono.utils.color`** — functions: `getColorEnabled` · `getColorEnabledAsync`
**`hono.utils.concurrent`** — classes: `Pool` (1); functions: `createPool`
**`hono.utils.cookie`** — functions: `_serialize` · `getCryptoKey` · `makeSignature` · `parse` · `parseSigned` · `serialize` · `serializeSigned` · `trimCookieWhitespace` · `verifySignature`
**`hono.utils.crypto`** — functions: `createHash` · `md5` · `sha1` · `sha256`
**`hono.utils.encode`** — functions: `decodeBase64` · `decodeBase64Url` · `encodeBase64` · `encodeBase64Url`
**`hono.utils.encode_test`** — functions: `str2UInt8Array` · `toURLBase64`
**`hono.utils.filepath`** — functions: `getFilePath` · `getFilePathWithoutDefaultDocument`
**`hono.utils.filepath_test`** — functions: `slashToBackslash`
**`hono.utils.handler`** — functions: `findTargetHandler` · `isMiddleware`
**`hono.utils.html`** — functions: `escapeToBuffer` · `raw` · `resolveCallback` · `resolveCallbackSync` · `stringBufferToString`
**`hono.utils.ipaddr`** — functions: `convertIPv4BinaryToString` · `convertIPv4MappedIPv6ToIPv4` · `convertIPv4ToBinary` · `convertIPv6BinaryToString` · `convertIPv6ToBinary` · `createInvalidIPAddressError` · `distinctRemoteAddr` · `expandIPv6` · `isIPv4MappedIPv6` · `isIPv6LinkLocal` · `parseIPv4ToBinary` · `parseIPv6HexCode` · `throwInvalidIPv4Address` · `throwInvalidIPv6Address`
**`hono.utils.ipaddr_test`** — functions: `expectInvalidIPAddressError`
**`hono.utils.jwt.jws`** — classes: `HonoJsonWebKey`; functions: `exportPublicJwkFrom` · `getKeyAlgorithm` · `importPrivateKey` · `importPublicKey` · `isCryptoKey` · `pemToBinary` · `signing` · `verifying`
**`hono.utils.jwt.jwt`** — classes: `TokenHeader`; functions: `decode` · `decodeHeader` · `decodeJwtPart` · `encodeJwtPart` · `encodeSignaturePart` · `isTokenHeader` · `sign` · `verify` · `verifyWithJwks`
**`hono.utils.jwt.jwt_test`** — functions: `exportJWK` · `exportPEMPrivateKey` · `exportPEMPublicKey` · `generateECDSAKey` · `generateEd25519Key` · `generateRSAKey` · `generateRSAPSSKey`
**`hono.utils.jwt.types`** — classes: `JwtAlgorithmMismatch` (1) · `JwtAlgorithmNotAllowed` (1) · `JwtAlgorithmNotImplemented` (1) · `JwtAlgorithmRequired` (1) · `JwtHeaderInvalid` (1) · `JwtHeaderRequiresKid` (1) · `JwtPayloadRequiresAud` (1) · `JwtSymmetricAlgorithmNotAllowed` (1) · `JwtTokenAudience` (1) · `JwtTokenExpired` (1) · `JwtTokenInvalid` (1) · `JwtTokenIssuedAt` (1) · `JwtTokenIssuer` (1) · `JwtTokenNotBefore` (1) · `JwtTokenSignatureMismatched` (1)
**`hono.utils.mime`** — functions: `getExtension` · `getMimeType`
**`hono.utils.stream`** — classes: `StreamingApi` (8)
**`hono.utils.url`** — functions: `_decodeURI` · `_getQueryParam` · `checkOptionalParameter` · `extractGroupsFromPath` · `getPath` · `getPathNoStrict` · `getPattern` · `getQueryParams` · `getQueryStrings` · `mergePath` · `replaceGroupMarks` · `splitPath` · `splitRoutingPath` · `tryDecode` · `tryDecodeURI` · `tryDecodeURIComponent`

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/hono
python3 -m graphy blast hono://func/hono.utils.html.raw --tenant $T/tenant.json --tenant-id hono
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id hono --corpus hono --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id hono --corpus hono --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm UTILS -->
