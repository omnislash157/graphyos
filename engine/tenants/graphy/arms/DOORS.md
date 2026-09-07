# DOORS — the questions: hunt, descend, blast, walk, explain, the bridge, the MCP server

> Hand-cut from the engine map (CLAUDE.md); the walk crowns `cli` over everything and this cut names the lanes instead. The generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
`doors` answers over one store; `traversal` keeps the walks; `query` spreads activation; `bridge` walks between two tenants on a declared literal; `mcp` serves the six tools on stdio.

<!-- graphy:arm DOORS generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=2a155c6926e2a9eb cut=sha256:a6e7f6dc67aab9bb6fd7793a207caee4a59936ab2d05b2d99191628da7cda284 content=sha256:2d0b295f1067392c54a0ad4e232d92d753cd8c624861de45806883cfb7a0cd23 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`graphy.bridge`** — classes: `BridgeError` · `BridgeResult` (1) · `Hop` (1) · `Side` (1); functions: `_roster` · `_scheme` · `cross` · `open_sides` · `render` · `verify_joins`
**`graphy.doors`** — classes: `Blast` · `Crossing` · `Descent` · `DoorError` · `Explanation` · `Reach`; functions: `_bfs` · `_fmt_chain` · `blast` · `chain` · `descend` · `explain` · `render_blast` · `render_descend` · `render_explain` · `resolve`
**`graphy.mcp`** — classes: `Doors` (10) · `ToolError`; functions: `_error` · `_result` · `handle` · `open_tools` · `serve`
**`graphy.query`** — classes: `LoadStats` · `Mesh` · `NodeState`; functions: `_build_parser` · `_coerce_salience` · `_coerce_witnesses` · `_format_human` · `_infer_edge_path` · `_nonneg_float` · `_pos_int_min1` · `_print_explanations` · `_print_mesh_set_human` · `_required_edge_fields` · `_strict_decay` · `activate` · `adjacency` · `classify` · `load` · `main` · `query` · `rank`
**`graphy.traversal`** — classes: `Counting` (5) · `StoredWalk` (1) · `TraversalError` · `WalkOutcome`; functions: `_chain` · `_key` · `_paths` · `_steps` · `home_for` · `load_walk` · `replay` · `store_walk` · `stored` · `walk`

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/graphy
python3 -m graphy blast graphy://func/graphy.traversal.home_for --tenant $T/tenant.json --tenant-id graphy
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id graphy --corpus graphy --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id graphy --corpus graphy --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm DOORS -->
