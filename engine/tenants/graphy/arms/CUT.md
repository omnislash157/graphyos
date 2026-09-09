# CUT — the fan-out, the pillars, the arms, the drawings, the showcase

> Hand-cut from the engine map (CLAUDE.md); the walk crowns `cli` over everything and this cut names the lanes instead. The generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
`fanout` cuts a shard by a partition with a receipt; `pillars` deduces the arms from the module graph; `arms` renders the generated region into each arm file and verifies it; `sugiyama` lays out and renders; `draw` draws from the store; `showcase` writes the page.

<!-- graphy:arm CUT generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=7bed1ff3f501890e cut=sha256:a6e7f6dc67aab9bb6fd7793a207caee4a59936ab2d05b2d99191628da7cda284 content=sha256:089e46e05e2f6ddf240ced0523609f61404db818f719e1011a426d4972c8b44e -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`graphy.arms`** — classes: `ArmsError` · `Region` (2) · `Verdict`; functions: `_inventory` · `_joins_and_crowns` · `_short` · `_stub` · `_tail` · `generate` · `read_region` · `render_all` · `render_region` · `render_verdicts` · `verify`
**`graphy.draw`** — classes: `DrawError` · `Picture` (1); functions: `_short` · `arm` · `atlas` · `neighbourhood` · `pillars` · `render` · `units`
**`graphy.fanout`** — classes: `Cut` (5) · `FanoutError`; functions: `_acquire_publish_lock` · `_cut_flaw` · `_edge_endpoint` · `_edge_flaw` · `_endpoint_flaw` · `_node_flaw` · `_node_group` · `_read_pinned_entry` · `_receipt_flaw` · `_release_publish_lock` · `_render_node_line` · `_render_section` · `_render_toc` · `_section_filename` · `_sha256` · `compile_fanout` · `load_partition` · `verify_fanout`
**`graphy.pillars`** — classes: `ModuleGraph` (5) · `PillarsError` · `Proposal` (1) · `Ruling`; functions: `_arm_name` · `_module_of` · `diff` · `module_graph` · `propose` · `render` · `render_diff` · `to_partition` · `write_partition`
**`graphy.showcase`** — classes: `ShowcaseError`; functions: `_clone` · `_esc` · `_parse` · `_same_repo` · `_shown` · `clone_dir` · `compose` · `fence_safe` · `repo_of` · `showcase`
**`graphy.sugiyama`** — classes: `Canvas` (8) · `Layout` (2); functions: `_adj_json` · `_all_nodes` · `_ansi` · `_apply_fas` · `_assign_cross` · `_beacon` · `_build_layers` · `_center` · `_count_crossings` · `_count_crossings_pairwise` · `_dedupe` · `_disp_w` · `_edge_from_to` · `_edge_path` · `_esc` · `_fas` · `_greedy_fas` · `_insert_dummies` · `_longest_path_layering` · `_median_order` · `_minimize_crossings` · `_place` · `_placed` · `_render_iso` · `_tarjan_sccs` · `_total_crossings` · `_wcswidth` · `check_artifact` · `draw` · `emit_html` · `emit_svg` · `emit_svg_file` · `from_dsl` · `from_graph` · `layout` · `layout_json` · `render` · `wcswidth`

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/graphy
python3 -m graphy blast graphy://func/graphy.fanout.load_partition --tenant $T/tenant.json --tenant-id graphy
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id graphy --corpus graphy --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id graphy --corpus graphy --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm CUT -->
