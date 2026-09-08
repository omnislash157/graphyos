# SEAM — the store, the resolver, the tenant, the journal, the container

> Hand-cut from the engine map (CLAUDE.md); the walk crowns `cli` over everything and this cut names the lanes instead. The generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
`tenant` is the declared identity everything refuses without; `converge` resolves text labels through scope and counts the wormholes; `federated_store` compiles and reads the sqlite store; `cross_substrate` loads and walks a set of shards; `journal` records born and died; `container` and `index_estate` are the parquet; `cartograph` runs declared build lanes and measures freshness.

<!-- graphy:arm SEAM generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=65db816d15896941 cut=sha256:a6e7f6dc67aab9bb6fd7793a207caee4a59936ab2d05b2d99191628da7cda284 content=sha256:234a126d28157a981d2d1e5652a6d654bc30005f3838b4c62a07488ec3a19e72 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`graphy._portable_flock`** — classes: `_NoFcntl` (1)
**`graphy._shared`** — functions: `_ast_edge_salience` · `_shim_adj_for_activate` · `credibility` · `lift` · `nonneg_int` · `resolve_excludes` · `salience`
**`graphy.augment_registry`** — functions: `_cli_tenant` · `_entry_body` · `_entry_span` · `_load_descriptor` · `_load_predicate` · `_lock_path` · `_registry_path` · `collect_augment_stamps` · `declared_from_stamp` · `descriptor_digest` · `main` · `normalize_descriptor` · `observed_from_index` · `register` · `stamp_from_descriptor` · `verify_registration`
**`graphy.cartograph`** — functions: `_cli_tenant` · `cartograph` · `cursor_drift` · `main` · `repo_cursor` · `repo_head_sha` · `resolve_graph` · `tenant_exclude` · `working_tree_dirt` · `write_graph`
**`graphy.container`** — classes: `ContainerError`; functions: `_attrs` · `_duckdb` · `_edge_rows` · `_node_rows` · `_write_parquet` · `_write_receipt` · `defer` · `emit` · `emit_all` · `emit_missing` · `estate` · `have_duckdb` · `node_forms` · `shard_digest` · `summarize` · `verify`
**`graphy.converge`** — classes: `Ring` (8); functions: `_dotted_of_id` · `_label_edges` · `_qualify` · `_resolve_one` · `_standard_of` · `_through_package` · `converge` · `load_ring` · `resolve`
**`graphy.cross_substrate`** — classes: `Material` · `MeshSet` (1) · `MeshSetStats` · `PathResult` · `RosterError` · `Step`; functions: `_cli_tenant` · `_derive_source_root` · `_explanations_core` · `_hydrate` · `_index_rows` · `_load_literal_join_schemes` · `_load_scheme_owners` · `_print_buckets` · `_print_human` · `_print_material` · `_print_path` · `_scheme` · `derive_roster` · `explanations` · `explanations_from_store` · `hydrate` · `hydrate_from_store` · `load_set` · `load_standard` · `main` · `path_to` · `query_set`
**`graphy.federated_store`** — classes: `Neighbour` · `SQLiteStore` (10) · `ShardStore` (11) · `StaleCursorError` (1) · `StoreError` · `WalkCursor` (3) · `_StoreAdj` (4); functions: `_advance` · `_as_cursor` · `_columns` · `_compute_input_digest` · `_finish` · `_frames` · `_generation_digest` · `_registry_input_digest` · `_repair_hint` · `_require_same_generation` · `_scheme_index_input_digest` · `_sha16` · `_shard_input_digest` · `_sync_then_replace` · `compile_store` · `frames` · `main` · `open_for` · `path_to` · `resume` · `spread` · `store_path_for`
**`graphy.index_estate`** — functions: `_load` · `_shard_dirs` · `catalog_digest` · `emit_index` · `estate_index` · `verify_index_estate`
**`graphy.inventory`** — functions: `_cli_tenant` · `_fmt` · `_render_overlay_section` · `collect_substrates` · `head_commit_sha` · `head_commit_time` · `main` · `render_markdown`
**`graphy.journal`** — classes: `TornJournalError`; functions: `_bounded` · `_cli_tenant` · `_cmd_diff_append` · `_cmd_event` · `_cmd_log` · `_cmd_losses` · `_cmd_steward` · `_contained` · `_cursor_from` · `_edge_key` · `_journal_root` · `_location_ok` · `_lose` · `_loss_log` · `_manifest_path` · `_names` · `_norm_cursor` · `_now_iso` · `_page_matches` · `_read_ids` · `_require_tenant` · `_roster_slugs` · `_tail_state` · `append_page` · `eligible_dir` · `find_events` · `find_graph_deaths` · `inplace_observer` · `journal_path` · `load_manifest` · `main` · `observe_publish` · `read_journal` · `shelf_journals` · `snapshot_ids` · `steward`
**`graphy.mesh_federation_gate`** — functions: `_atomic_write_index` · `_baseline_path` · `_build_row` · `_canon` · `_cli_tenant` · `_edge_join` · `_heal_index` · `_index_drift` · `_index_drifted_rows` · `_index_lock` · `_index_lock_path` · `_index_path` · `_join_keys_path` · `_load_index` · `_node_schemes` · `_owners` · `_parked` · `_registry` · `_registry_digest` · `_resolve_member` · `_row_cursor` · `_scan_schemes` · `_stdlib` · `_validate_roster_membership` · `_write_baseline` · `_write_index` · `build_index` · `census` · `classify` · `cmd_all` · `cmd_census` · `cmd_emit_map` · `cmd_verify_map` · `emit_map` · `main` · `observe` · `roster` · `verify_card`
**`graphy.tenant`** — classes: `Tenant` (2) · `TenantError`

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/graphy
python3 -m graphy blast graphy://func/graphy.federated_store.open_for --tenant $T/tenant.json --tenant-id graphy
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id graphy --corpus graphy --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id graphy --corpus graphy --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm SEAM -->
