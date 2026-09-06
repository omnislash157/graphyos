# APPLICATION — the app (`express.express` · `express.application`)

> Load before touching this module. Hand-cut by module because the walk rules express one pillar;
> the generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
`createApplication` builds the app object and mixes in `application`'s `app.*` methods — `app.use`, `app.listen`, `app.handle`, `app.set`/`get`, `app.engine`, `app.render`, `app.route`, `app.param`. Every method is a function assigned to a member, which the producer reads as a definition; the router the app delegates to is the `router` package in the ring, resolved through `require`.

<!-- graphy:arm APPLICATION generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=ecab7ec77bc6bdf7 cut=sha256:c839152b4faa5af6a6cfb0fe78d6fe50195eae3b0092a5e29778f9a673abf337 content=sha256:31eecb959c3794e33737f8f70a6f1e0150b4bfc50de288b38350af45190b914a -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`express.application`** — functions: `all` · `defaultConfiguration` · `disable` · `disabled` · `enable` · `enabled` · `engine` · `handle` · `init` · `listen` · `param` · `path` · `render` · `route` · `set` · `use` · `logerror` · `tryRender`
**`express.express`** — functions: `createApplication`

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/express
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id express --corpus express --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id express --corpus express --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm APPLICATION -->
