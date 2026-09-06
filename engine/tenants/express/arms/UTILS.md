# UTILS — the helpers and the view (`express.utils` · `express.view`)

> Load before touching this module. Hand-cut by module because the walk rules express one pillar;
> the generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
`utils.compileETag` / `compileQueryParser` / `compileTrust` · `normalizeType` / `normalizeTypes` · `setCharset` · `etag` / `wetag`; `view.View` and its `lookup` / `render` / `resolve`. Consumed by APPLICATION and RESPONSE; reaches `etag`, `mime-types`, `content-type`, `qs`, `proxy-addr` in the ring.

<!-- graphy:arm UTILS generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=ecab7ec77bc6bdf7 cut=sha256:c839152b4faa5af6a6cfb0fe78d6fe50195eae3b0092a5e29778f9a673abf337 content=sha256:7d461428283fef311553d369dbbc019307dfb13344c85d211b9255e00a1bae42 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`express.utils`** — functions: `acceptParams` · `compileETag` · `compileQueryParser` · `compileTrust` · `createETagGenerator` · `normalizeType` · `normalizeTypes` · `parseExtendedQueryString` · `setCharset`
**`express.view`** — functions: `View` · `lookup` · `render` · `resolve` · `tryStat`

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/express
python3 -m graphy blast express://module/express.view --tenant $T/tenant.json --tenant-id express
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id express --corpus express --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id express --corpus express --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm UTILS -->
