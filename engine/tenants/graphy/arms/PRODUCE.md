# PRODUCE — the producers, the mint, the ring, the farm

> Hand-cut from the engine map (CLAUDE.md); the walk crowns `cli` over everything and this cut names the lanes instead. The generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
A producer maps a parse tree onto the nine words (`adapters.python_ast`, `adapters.typescript_ast`); `ir` validates; `smash` mints a package into a shard and follows its imports into the ring; `index` pushes and pulls content-addressed shards; `refresh` follows upstream into a sibling; `farm` mints many; `provision` installs a repo's own dependencies for `eat`; `release` enforces one release per scheme.

<!-- graphy:arm PRODUCE generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=152515ef4edab57a cut=sha256:a6e7f6dc67aab9bb6fd7793a207caee4a59936ab2d05b2d99191628da7cda284 content=sha256:f46852076df6849943eb080cbb553b5251e18cd9369033dbd999ce874af67c75 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`graphy.adapters._receipt`** — classes: `Receipt` (3); functions: `splice`
**`graphy.adapters.outline`** — classes: `_NodeRecords` (1); functions: `_slugify` · `build_ir` · `parse_outline`
**`graphy.adapters.python_ast`** — classes: `_NodeRecords` (1); functions: `_class_info` · `_defs_in` · `_dotted_for` · `_emit_import_edges` · `_emit_raw_records_for_file` · `_emit_records_for_file` · `_expr_repr` · `_is_excluded` · `_local_package_names` · `_node_id` · `_resolve_module_dst` · `_scan` · `_scheme_of` · `_walk_stmt` · `build_ir` · `is_package_dir` · `mint_records` · `walk_files`
**`graphy.adapters.typescript_ast`** — classes: `ProducerUnavailable` · `_Wrap` (1); functions: `_assigned_functions` · `_calls_in` · `_decorators` · `_dotted_for` · `_expr_repr` · `_func_of_lexical` · `_heritage` · `_module_for_specifier` · `_node_id` · `_parsers` · `_require_spec` · `_requires_in` · `_text` · `_unwrap_export` · `_walk_class` · `_walk_module` · `build_ir` · `excludes_for` · `is_package_dir` · `mint_records` · `slug_of_specifier` · `walk_files`
**`graphy.farm`** — classes: `FarmError` · `Spec` (2) · `Verdict`; functions: `_fetch_text` · `_pip` · `farm` · `farm_one` · `import_names_for` · `normalize` · `provision_alone` · `provision_npm` · `select_npm_release` · `select_release` · `top_npm_packages` · `top_packages`
**`graphy.index`** — classes: `IndexError_` · `_Source` (2); functions: `_check_name` · `_fetch_entry` · `_notice` · `_read_shard` · `_receipts` · `_resolve` · `_rewrite_catalog` · `_sha` · `_verify_entry` · `_write_atomic` · `address_of` · `catalog` · `default_name` · `pull` · `push` · `verify_index` · `verify_shard`
**`graphy.ir`** — classes: `Edge` (1) · `Evidence` (1) · `IRError` · `Node` (1) · `Provenance` (1) · `Vocabulary` (1); functions: `_is_int` · `_parse_endpoint` · `_parse_optional` · `_type_name` · `validate_graph`
**`graphy.native_json_graph_ir`** — classes: `OverrideIR` · `OverrideRecord` (1) · `ResolvedShard`; functions: `_canonical_payload` · `_classify_path` · `_detect_alias_cycle` · `_detect_duplicate_json_keys` · `_escape_json_pointer_segment` · `_file_sha256` · `_fold` · `_json_pointer` · `_remember` · `_resolve_shard` · `_scalar_leaves` · `load_graph_ir` · `load_override_ir` · `raw_shard` · `shard_input_digest` · `validate_shard`
**`graphy.parity`** — classes: `Golden` (2) · `Harness` (5) · `ParityError` · `_NotJson` (1); functions: `_as_json` · `_eq` · `_witness` · `json_equal` · `load_golden`
**`graphy.provision`** — classes: `Provisioned`; functions: `_declaration` · `_run` · `provision`
**`graphy.refresh`** — classes: `CheckFailed` · `Plan` · `RefreshError`; functions: `_declare` · `_descriptor` · `_fetch_pypi` · `_ids` · `_prove` · `_remint_fixture` · `_run` · `_shards` · `_sibling_tenant` · `_version_in` · `current_provenance` · `diff_shards` · `is_final` · `is_newer` · `latest_release` · `parse_version` · `plan_for` · `provision` · `refresh` · `render_pages`
**`graphy.release`** — classes: `Release` (1) · `ReleaseError`; functions: `_owned_schemes` · `collisions` · `release_of` · `require_one_release` · `roster_releases`
**`graphy.smash`** — classes: `Producer` (1) · `SmashError`; functions: `_counts` · `_file_receipt` · `_graphy_version` · `_import_schemes` · `_license_of` · `_reuse_from` · `_schemes` · `_write_json` · `_write_records` · `corpus_digest` · `distributions` · `distributions_node` · `divergence` · `git_head` · `golden_from_shard` · `locate` · `locate_node` · `mint` · `mint_command_for` · `node_dir_for` · `parity` · `portable` · `shard_payload` · `slug_for` · `slug_for_specifier` · `smash` · `stdlib_names`

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/graphy
python3 -m graphy blast graphy://func/graphy.native_json_graph_ir.load_graph_ir --tenant $T/tenant.json --tenant-id graphy
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id graphy --corpus graphy --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id graphy --corpus graphy --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm PRODUCE -->
