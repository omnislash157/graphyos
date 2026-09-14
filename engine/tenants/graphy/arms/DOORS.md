# DOORS — the questions: hunt, descend, blast, walk, explain, the bridge, the MCP server

> Hand-cut from the engine map (CLAUDE.md); the walk crowns `cli` over everything and this cut names the lanes instead. The generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
`doors` answers over one store; `traversal` keeps the walks; `query` spreads activation; `bridge` walks between two tenants on a declared literal; `mcp` serves the tools on stdio. A history shard in the roster makes the archive's exchanges readers of the code: `blast` lists the ones that mention a symbol under their own owner, `explain` lists them with the docs, and `timeline` walks from a symbol into the sessions that discussed it.

<!-- graphy:arm DOORS generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=6168578d3cf543b9 cut=sha256:0f1d43aa1cb87a767f760bdce58094258cb244f46054c04b6f20ee098f6e3cd8 content=sha256:bb2077a8934d33eab377c273fe268fdb0534b2e8a31e5a487c44754da03f233f -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`graphy.bridge`** — classes: `BridgeError` · `BridgeResult` (1) · `Hop` (1) · `Side` (1); functions: `_roster` · `_scheme` · `close_sides` · `cross` · `open_sides` · `render` · `verify_joins`
**`graphy.doors`** — classes: `Blast` · `Crossing` · `Descent` · `DoorError` · `Explanation` · `Reach`; functions: `_bfs` · `_fmt_chain` · `blast` · `blast_of` · `blast_relations` · `chain` · `declined` · `descend` · `descend_relations` · `descent_of` · `explain` · `minted_from_distribution` · `render_blast` · `render_declined` · `render_descend` · `render_explain` · `resolve`
**`graphy.mcp`** — classes: `Doors` (16) · `ToolError`; functions: `_error` · `_result` · `handle` · `open_tools` · `serve`
**`graphy.query`** — classes: `LoadStats` · `Mesh` · `NodeState`; functions: `_build_parser` · `_coerce_salience` · `_coerce_witnesses` · `_format_human` · `_infer_edge_path` · `_nonneg_float` · `_pos_int_min1` · `_print_explanations` · `_print_mesh_set_human` · `_required_edge_fields` · `_strict_decay` · `activate` · `adjacency` · `classify` · `load` · `main` · `query` · `rank`
**`graphy.traversal`** — classes: `Counting` (6) · `DoorOutcome` · `StoredUnreadable` · `StoredWalk` (1) · `TraversalError` · `WalkOutcome`; functions: `_cached_walk` · `_chain` · `_door_paths` · `_key` · `_make_under` · `_paths` · `_steps` · `door` · `home_for` · `load_door` · `load_walk` · `recall` · `replay` · `rules_digest` · `store_door` · `store_walk` · `stored` · `stored_doors` · `vocabulary` · `walk`

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/graphy
python3 -m graphy blast graphy://func/graphy.traversal.home_for --tenant $T/tenant.json --tenant-id graphy
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id graphy --corpus graphy --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id graphy --corpus graphy --partition $T/partition.json --dir $T/arms --verify
```

Last walk: crown=`graphy://func/graphy.traversal.home_for` dependents in graphy=10 → arms/DOORS.walk.txt

<!-- /graphy:arm DOORS -->
