# MEMORY — the continuity lane

> Hand-cut from the engine map (CLAUDE.md); the walk crowns `cli` over everything and this cut names the lanes instead. The generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
`session_tail` turns a transcript into its semantic tail; `reseed` captures and injects it around a clear; `lightning` is the ripgrep-anchored search over the archive. The walk names this the floor no arm consumes — it runs beside the engine, not under the CLI.

<!-- graphy:arm MEMORY generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=372abbb186a597b9 cut=sha256:a6e7f6dc67aab9bb6fd7793a207caee4a59936ab2d05b2d99191628da7cda284 content=sha256:b8bdcaf859deb4131cd7409e03d869018e263d5cea08abad7673f86bb012daa1 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`graphy.lightning.archive`** — functions: `sessions_dir`
**`graphy.lightning.blitz_hunt`** — classes: `Lightning` (5)
**`graphy.lightning.block_blast`** — functions: `find_blocks` · `find_blocks_regex` · `find_containing_block` · `find_python_blocks`
**`graphy.lightning.bloodhound`** — classes: `Cluster` (3) · `FileTrail` (1); functions: `_bar` · `_exchange_marks` · `_matcher` · `main` · `run` · `trail_file`
**`graphy.lightning.bolt_cli`** — functions: `_looks_explicitly_pathlike` · `_looks_like_missing_corpus` · `_resolve_search_inputs` · `_validate_corpus` · `main`
**`graphy.lightning.code_hit`** — functions: `_code_hit_from_chunk`
**`graphy.lightning.context_strike`** — functions: `expand_and_merge` · `find_code_boundary` · `find_matches`
**`graphy.lightning.extras.stats`** — functions: `quick_stats`
**`graphy.lightning.extras.storm_cooccurrence`** — functions: `_bar` · `_footprint` · `_min_gap` · `container_cooccur` · `container_cooccur_markdown` · `container_neighbors` · `container_neighbors_markdown` · `containers_json` · `containers_markdown` · `containers_of` · `containers_test_mode` · `containers_test_mode_markdown` · `storm_markdown`
**`graphy.lightning.files_from_envelope`** — functions: `files_from_envelope` · `hunt_envelope_files`
**`graphy.lightning.formatters`** — functions: `to_json` · `to_markdown`
**`graphy.lightning.hit_kind`** — functions: `_prose_spans` · `classify_file_lines` · `is_prose_only`
**`graphy.lightning.log_blast`** — functions: `find_log_blocks` · `normalize_route` · `route_query_pattern`
**`graphy.lightning.models`** — classes: `CodeBlock` · `CodeChunk` · `CodeMatch` · `FileHit` · `LightningResult` (2) · `SessionHit` · `SessionSearchResult` (2) · `SessionSegment`
**`graphy.lightning.pattern_splinter`** — functions: `build_code_pattern` · `detokenize` · `get_identifier_variations` · `split_identifier` · `token_count` · `tokenize`
**`graphy.lightning.prose_blast`** — functions: `find_prose_blocks` · `has_exchanges`
**`graphy.lightning.pseudo_ast.blocks`** — functions: `_find_blocks_in_script` · `_find_blocks_rust_go` · `_find_blocks_svelte` · `_find_blocks_svelte_with_stem` · `_find_body_brace` · `_find_open_brace` · `_line_of` · `find_brace_blocks` · `find_brace_blocks_for_path`
**`graphy.lightning.pseudo_ast.brace`** — functions: `brace_block` · `neutralize`
**`graphy.lightning.pseudo_ast.svelte`** — functions: `role_from_path` · `split_svelte`
**`graphy.lightning.reseed_graph`** — classes: `Box` · `Corpus` (1) · `Forest`; functions: `_bar` · `_date_of` · `_norm` · `_resolve` · `_segments` · `_sessions_of` · `_snippet` · `_subseq` · `build` · `cmd_chain` · `cmd_heat` · `cmd_search` · `cmd_topics` · `header` · `main` · `topic_forest`
**`graphy.lightning.ripgrep`** — functions: `_bounded_filesystem_inventory` · `_git_searchable_files` · `_relative_is_ignored` · `python_matching_files` · `resolve_rg` · `rg_matching_files` · `searchable_files`
**`graphy.lightning.source_kind`** — functions: `_is_doc_file` · `_is_slop_dir` · `_is_test_file` · `classify_sources` · `gitignored_set` · `liveness_verdict`
**`graphy.reseed`** — functions: `_age` · `_archive` · `_assert_exact_session` · `_atomic_write` · `_diag` · `_disk_fallback` · `_exchange_count` · `_header` · `_newest_archive_sha` · `_project_dir` · `_read_hook_stdin` · `do_capture` · `do_inject` · `main` · `recovery_dir`
**`graphy.session_tail`** — classes: `TailError`; functions: `_blocks` · `_budget` · `_is_real_user` · `_text_of` · `assert_plausible` · `bounded_tail` · `extract_turns` · `pair_turns` · `project_slug` · `projects_root` · `projects_roots` · `render_full` · `render_json` · `render_markdown` · `render_recent_markdown` · `scan_stats` · `semantic_sha256`

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/graphy
python3 -m graphy blast graphy://class/graphy.lightning.models.CodeBlock --tenant $T/tenant.json --tenant-id graphy
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id graphy --corpus graphy --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id graphy --corpus graphy --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm MEMORY -->
