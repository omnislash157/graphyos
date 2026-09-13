# CLI — the verbs and the shell

> Hand-cut from the engine map (CLAUDE.md); the walk crowns `cli` over everything and this cut names the lanes instead. The generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
`cli` is every verb, one handler each, refusing by name before it reads anything; `shell` bolts the hooks and the gate onto an eaten repo. The walk crowns `cli` over the whole package — every other unit is its foundation — which is what a thin CLI over a library should look like.

<!-- graphy:arm CLI generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=a5d3511dca363bb5 cut=sha256:0f1d43aa1cb87a767f760bdce58094258cb244f46054c04b6f20ee098f6e3cd8 content=sha256:3547de734640df745d7383c63e9c5cf4afeb0cdbc1edf699d2438b6f80d08159 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`graphy.cli`** — functions: `_build_parser` · `_clear_substrate` · `_cmd_arms` · `_cmd_bridge` · `_cmd_build` · `_cmd_check` · `_cmd_container` · `_cmd_converge` · `_cmd_door` · `_cmd_draw` · `_cmd_eat` · `_cmd_estate` · `_cmd_estate_index` · `_cmd_fanout` · `_cmd_farm` · `_cmd_harness` · `_cmd_history` · `_cmd_index` · `_cmd_init` · `_cmd_mcp` · `_cmd_pillars` · `_cmd_pull` · `_cmd_push` · `_cmd_recon` · `_cmd_refresh` · `_cmd_shell` · `_cmd_showcase` · `_cmd_smash` · `_cmd_timeline` · `_cmd_traversals` · `_cmd_walk` · `_descriptor_dict` · `_eat_run` · `_eat_typescript` · `_endpoint_audit` · `_flatten` · `_graphy_command` · `_history_report` · `_load_tenant` · `_main` · `_next_steps` · `_package_candidates` · `_parse_lanes` · `_profiled` · `_render_walk` · `_roster` · `_scheme_index_from_ring` · `_tenant_dirs` · `_torn_line` · `_walk_target` · `eat_history` · `main` · `mcp_args` · `repo_tenant`
**`graphy.shell.gate`** — functions: `_cited` · `_module` · `_symbols` · `main`
**`graphy.shell.install`** — classes: `ShellError`; functions: `_fill` · `_merge_cursor` · `_merge_hooks` · `_write_wiring` · `install` · `memory_taps` · `remint_history`

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/graphy
python3 -m graphy blast graphy://func/graphy.cli._load_tenant --tenant $T/tenant.json --tenant-id graphy
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id graphy --corpus graphy --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id graphy --corpus graphy --partition $T/partition.json --dir $T/arms --verify
```

Last walk: crown=`graphy://func/graphy.cli._load_tenant` dependents=28 → arms/CLI.walk.txt

<!-- /graphy:arm CLI -->
