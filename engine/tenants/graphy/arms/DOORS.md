# DOORS — the questions: hunt, descend, blast, walk, explain, the bridge, the MCP server

> Hand-cut from the engine map (CLAUDE.md); the walk crowns `cli` over everything and this cut names the lanes instead. The generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
`doors` answers over one store; `traversal` keeps the walks; `query` spreads activation; `bridge` walks between two tenants on a declared literal; `mcp` serves the tools on stdio. A history shard in the roster makes the archive's exchanges readers of the code: `blast` lists the ones that mention a symbol under their own owner, `explain` lists them with the docs, and `timeline` walks from a symbol into the sessions that discussed it.

<!-- graphy:arm DOORS generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=7bed1ff3f501890e cut=sha256:a6e7f6dc67aab9bb6fd7793a207caee4a59936ab2d05b2d99191628da7cda284 content=sha256:873552fe676bfdb8a037c996e57a942d10c495c20abd09097b8f165c6cbb58ef -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`graphy.bridge`** — classes: `BridgeError` · `BridgeResult` (1) · `Hop` (1) · `Side` (1); functions: `_roster` · `_scheme` · `cross` · `open_sides` · `render` · `verify_joins`
**`graphy.doors`** — classes: `Blast` · `Crossing` · `Descent` · `DoorError` · `Explanation` · `Reach`; functions: `_bfs` · `_fmt_chain` · `blast` · `chain` · `descend` · `explain` · `render_blast` · `render_descend` · `render_explain` · `resolve`
**`graphy.mcp`** — classes: `Doors` (11) · `ToolError`; functions: `_error` · `_result` · `handle` · `open_tools` · `serve`
**`graphy.query`** — classes: `LoadStats` · `Mesh` · `NodeState`; functions: `_build_parser` · `_coerce_salience` · `_coerce_witnesses` · `_format_human` · `_infer_edge_path` · `_nonneg_float` · `_pos_int_min1` · `_print_explanations` · `_print_mesh_set_human` · `_required_edge_fields` · `_strict_decay` · `activate` · `adjacency` · `classify` · `load` · `main` · `query` · `rank`
**`graphy.traversal`** — classes: `Counting` (5) · `StoredWalk` (1) · `TraversalError` · `WalkOutcome`; functions: `_chain` · `_key` · `_paths` · `_steps` · `home_for` · `load_walk` · `replay` · `store_walk` · `stored` · `walk`

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/graphy
python3 -m graphy blast graphy://func/graphy.doors.resolve --tenant $T/tenant.json --tenant-id graphy
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id graphy --corpus graphy --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id graphy --corpus graphy --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm DOORS -->
