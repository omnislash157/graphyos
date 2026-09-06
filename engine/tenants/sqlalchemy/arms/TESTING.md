# TESTING — the harness the package ships (`sqlalchemy.testing`)

> Load before touching a fixture, an assertion helper, an exclusion rule, or the test engine. The
> walk crowns this unit first by fan-out because it consumes every other pillar; it is an arm of
> its own so that the shared floor is not ruled by what the harness happens to import. Hand-cut
> from the walk's evidence; the generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm
Nothing in the package consumes `testing`; it consumes everything. `assertions.eq_` is the most
called symbol here; `exclusions.closed` / `open` / `only_if` / `skip_if` rule which backends a test
runs on; `schema.Table` / `Column` wrap SQL's with test-only defaults; `config.fixture` and
`engines.testing_engine` hand a test its engine. Its join out is `pytest`, which the ring did
not carry.

## The load-bearing symbols (walk-derived)
`assertions.eq_` / `is_true` / `is_false` · `exclusions.closed` / `open` / `only_if` / `skip_if` /
`compound` · `schema.Table` / `Column` · `config.fixture` / `skip_test` · `engines.testing_engine`
· `entities.ComparableEntity`.

## Cross-pillar joins (all outbound)
- → **SQL** (the heaviest), **ORM** (`instance_state`, mapped entities), **ENGINE**
  (`await_only`, `make_url`), **DIALECTS**.

<!-- graphy:arm TESTING generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=3a9f8a3a4b15a939 cut=sha256:5fe44b5a68b5270696a6d629a7b1948137de8baef8cc767efcf102b2fb376aa4 content=sha256:c3d60e4fc13859d91c09e43beeef24a6e22cf2ddc43b879711f1ab9360b1c124 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`sqlalchemy.testing`** — functions: `against`
**`sqlalchemy.testing.assertions`** — classes: `AssertsCompiledSQL` (1) · `AssertsExecutionResults` (11) · `ComparesIndexes` (1) · `ComparesTables` (2) · `_ErrorContainer`; functions: `_assert_no_stray_pool_connections` · `_assert_proper_exception_context` · `_assert_raises` · `_expect_raises` · `_expect_warnings` · `_expect_warnings_sqla_only` · `assert_raises` · `assert_raises_context_ok` · `assert_raises_message` · `assert_raises_message_context_ok` · `assert_warns` · `assert_warns_message` · `emits_warning` · `emits_warning_on` · `eq_` · `eq_ignore_whitespace` · `eq_regex` · `expect_deprecated` · `expect_deprecated_20` · `expect_raises` · `expect_raises_message` · `expect_warnings` · `expect_warnings_on` · `global_cleanup_assertions` · `in_` · `int_within_variance` · `is_` · `is_false` · `is_instance_of` · `is_none` · `is_not` · `is_not_none` · `is_true` · `le_` · `ne_` · `not_in` · `startswith_` · `uses_deprecated`
**`sqlalchemy.testing.assertsql`** — classes: `AllOf` (2) · `AssertRule` (2) · `CompiledSQL` (7) · `Conditional` (1) · `CountStatements` (3) · `CursorSQL` (2) · `DialectSQL` (6) · `EachOf` (3) · `Or` (1) · `RegexSQL` (3) · `SQLAsserter` (3) · `SQLCursorExecuteObserved` · `SQLExecuteObserved` (2) · `SQLMatchRule`; functions: `assert_engine`
**`sqlalchemy.testing.asyncio`** — functions: `_assume_async` · `_maybe_async` · `_maybe_async_provisioning` · `_maybe_async_wrapper` · `_run_coroutine_function` · `_shutdown`
**`sqlalchemy.testing.config`** — classes: `Config` (12) · `Variation` (10) · `_AddToMarker` (1) · `_NullFixtureFunctions` (10); functions: `async_test` · `combinations` · `combinations_list` · `fixture` · `fixture_classmethod` · `get_current_test_name` · `mark_base_test_class` · `skip_test` · `variation` · `variation_fixture`
**`sqlalchemy.testing.engines`** — classes: `ConnectionKiller` (18) · `DBAPIProxyConnection` (4) · `DBAPIProxyCursor` (5) · `ReconnectFixture` (6); functions: `all_dialects` · `assert_conns_closed` · `close_first` · `close_open_connections` · `mock_engine` · `reconnecting_engine` · `rollback_open_connections` · `testing_engine`
**`sqlalchemy.testing.entities`** — classes: `BasicEntity` (2) · `ComparableEntity` (1) · `ComparableMixin` (2)
**`sqlalchemy.testing.exclusions`** — classes: `BooleanPredicate` (3) · `LambdaPredicate` (3) · `NotPredicate` (3) · `OrPredicate` (5) · `Predicate` (3) · `SpecPredicate` (3) · `compound` (15); functions: `_is_excluded` · `_server_version` · `against` · `closed` · `db_spec` · `exclude` · `fails` · `fails_if` · `fails_on` · `fails_on_everything_except` · `future` · `only_if` · `only_on` · `open` · `skip` · `skip_if` · `succeeds_if` · `warns_if`
**`sqlalchemy.testing.fixtures.base`** — classes: `FutureEngineMixin` · `TestBase` (16)
**`sqlalchemy.testing.fixtures.mypy`** — classes: `MypyTest` (8)
**`sqlalchemy.testing.fixtures.orm`** — classes: `DeclarativeMappedTest` (2) · `MappedTest` (13) · `ORMTest` (1) · `RemoveORMEventsGlobally` (1); functions: `after_test` · `close_all_sessions` · `fixture_session` · `stop_test_class_inside_fixtures`
**`sqlalchemy.testing.fixtures.sql`** — classes: `CacheKeyFixture` (3) · `ComputedReflectionFixtureTest` (2) · `NoCache` (1) · `RemovesEvents` (3) · `TablesTest` (18); functions: `insertmanyvalues_fixture`
**`sqlalchemy.testing.pickleable`** — classes: `Address` · `AddressWMixin` · `Bar` (3) · `BarWithoutCompare` (2) · `BrokenComparable` (4) · `Child1` · `Child2` · `Dingaling` · `EmailUser` · `Foo` (2) · `Mixin` · `NotComparable` (4) · `OldSchool` (2) · `OldSchoolWithoutCompare` (1) · `Order` · `Parent` · `Screen` (1) · `User`
**`sqlalchemy.testing.plugin.bootstrap`** — functions: `load_file_as_module`
**`sqlalchemy.testing.plugin.plugin_base`** — classes: `FixtureFunctions` (8); functions: `__ensure_cext` · `_do_skips` · `_engine_uri` · `_exclude_tag` · `_include_tag` · `_init_symbols` · `_list_dbs` · `_log` · `_possible_configs_for_cls` · `_post_setup_options` · `_prep_testing_database` · `_register_sqlite_numeric_dialect` · `_requirements` · `_requirements_opt` · `_restore_engine` · `_set_disable_asyncio` · `_set_tag_exclude` · `_set_tag_include` · `_setup_config` · `_setup_engine` · `_setup_options` · `_setup_profiling` · `_setup_requirements` · `after_test` · `after_test_fixtures` · `before_test` · `configure_follower` · `final_process_cleanup` · `generate_sub_tests` · `memoize_important_follower_config` · `post` · `post_begin` · `pre` · `pre_begin` · `read_config` · `restore_important_follower_config` · `set_coverage_flag` · `set_fixture_functions` · `setup_options` · `start_test_class_outside_fixtures` · `stop_test_class` · `stop_test_class_outside_fixtures` · `want_class` · `want_method`
**`sqlalchemy.testing.plugin.pytestplugin`** — classes: `PytestFixtureFunctions` (9) · `XDistHooks` (2); functions: `_apply_maybe_async` · `_is_wrapped_coroutine_function` · `_log_sqlalchemy_info` · `_parametrize_cls` · `_pytest_fn_decorator` · `collect_types_fixture` · `pytest_addoption` · `pytest_collection_finish` · `pytest_collection_modifyitems` · `pytest_configure` · `pytest_pycollect_makeitem` · `pytest_runtest_call` · `pytest_runtest_logreport` · `pytest_runtest_setup` · `pytest_runtest_teardown` · `pytest_sessionfinish` · `pytest_sessionstart` · `pytest_unconfigure` · `setup_class_methods` · `setup_test_methods`
**`sqlalchemy.testing.profiling`** — classes: `ProfileStatsFile` (9); functions: `_start_current_test` · `count_functions` · `function_call_count`
**`sqlalchemy.testing.provision`** — classes: `register` (6); functions: `_adapt_update_db_opts` · `_configs_for_db_operation` · `_generate_driver_urls` · `allow_stale_update_impl` · `allow_stale_updates` · `configure_follower` · `create_db` · `create_follower_db` · `delete_from_all_tables` · `drop_all_schema_objects` · `drop_all_schema_objects_post_tables` · `drop_all_schema_objects_pre_tables` · `drop_db` · `drop_follower_db` · `drop_materialized_views` · `drop_views` · `follower_url_from_main` · `generate_db_urls` · `generate_driver_url` · `get_temp_table_name` · `is_preferred_driver` · `normalize_sequence` · `post_configure_engine` · `post_configure_testing_engine` · `prepare_for_drop_tables` · `reap_dbs` · `run_reap_dbs` · `set_default_schema_on_connection` · `setup_config` · `stop_test_class_outside_fixtures` · `temp_table_keyword_args` · `update_db_opts` · `upsert`
**`sqlalchemy.testing.requirements`** — classes: `Requirements` · `SuiteRequirements` (251)
**`sqlalchemy.testing.schema`** — classes: `eq_clause_element` (3) · `eq_compile_type` (3) · `eq_type_affinity` (3); functions: `Column` · `Table` · `_schema_column` · `_truncate_name` · `mapped_column` · `pep435_enum`
**`sqlalchemy.testing.suite.test_cte`** — classes: `CTETest` (9)
**`sqlalchemy.testing.suite.test_ddl`** — classes: `FutureTableDDLTest` · `LongNameBlowoutTest` (6) · `TableDDLTest` (14)
**`sqlalchemy.testing.suite.test_deprecations`** — classes: `DeprecatedCompoundSelectTest` (9)
**`sqlalchemy.testing.suite.test_dialect`** — classes: `ArgSignatureTest` (3) · `AutocommitIsolationTest` (7) · `DifficultParametersTest` (4) · `EscapingTest` (1) · `ExceptionTest` (3) · `FutureWeCanSetDefaultSchemaWEventsTest` · `IsolationLevelTest` (7) · `PingTest` (1) · `ReturningGuardsTest` (8) · `WeCanSetDefaultSchemaWEventsTest` (4)
**`sqlalchemy.testing.suite.test_insert`** — classes: `InsertBehaviorTest` (10) · `LastrowidTest` (5) · `ReturningTest` (9)
**`sqlalchemy.testing.suite.test_reflection`** — classes: `BizarroCharacterTest` (5) · `ComponentReflectionTest` (76) · `ComponentReflectionTestExtra` (18) · `CompositeKeyReflectionTest` (3) · `ComputedReflectionTest` (5) · `HasIndexTest` (4) · `HasTableTest` (12) · `IdentityReflectionTest` (4) · `NormalizedNameTest` (3) · `OneConnectionTablesTest` (1) · `QuotedNameArgumentTest` (11) · `TableNoColumnsTest` (7) · `TempTableElementsTest` (3); functions: `_multi_combination`
**`sqlalchemy.testing.suite.test_results`** — classes: `PercentSchemaNamesTest` (5) · `RowFetchTest` (8) · `ServerSideCursorsTest` (9)
**`sqlalchemy.testing.suite.test_rowcount`** — classes: `RowCountTest` (12)
**`sqlalchemy.testing.suite.test_select`** — classes: `BitwiseTest` (3) · `CollateTest` (4) · `CompoundSelectTest` (10) · `ComputedColumnTest` (4) · `DistinctOnTest` (1) · `ExistsTest` (4) · `ExpandingBoundInTest` (32) · `FetchLimitOffsetTest` (31) · `IdentityAutoincrementTest` (2) · `IdentityColumnTest` (5) · `IsOrIsNotDistinctFromTest` (2) · `JoinTest` (8) · `LikeFunctionsTest` (20) · `OrderByLabelTest` (9) · `PostCompileParamsTest` (8) · `SameNamedSchemaTableTest` (5) · `ValuesExpressionTest` (1) · `WindowFunctionTest` (4)
**`sqlalchemy.testing.suite.test_sequence`** — classes: `HasSequenceTest` (12) · `HasSequenceTestEmpty` (1) · `SequenceCompilerTest` (1) · `SequenceTest` (9)
**`sqlalchemy.testing.suite.test_types`** — classes: `ArrayTest` (4) · `BinaryTest` (3) · `BooleanTest` (5) · `CastTypeDecoratorTest` (2) · `DateHistoricTest` (1) · `DateTest` (1) · `DateTimeCoercedToDateTimeTest` (1) · `DateTimeHistoricTest` (1) · `DateTimeMicrosecondsTest` · `DateTimeTZTest` (1) · `DateTimeTest` (1) · `EnumTest` (4) · `IntegerTest` (5) · `IntervalTest` (6) · `JSONLegacyStringCastIndexTest` (8) · `JSONTest` (16) · `NativeUUIDTest` · `NumericTest` (21) · `PrecisionIntervalTest` · `StringTest` (8) · `TextTest` (10) · `TimeMicrosecondsTest` (1) · `TimeTZTest` (1) · `TimeTest` (1) · `TimestampMicrosecondsTest` (1) · `TrueDivTest` (7) · `UnicodeTextTest` (2) · `UnicodeVarcharTest` (2) · `UuidTest` (8) · `_DateFixture` (6) · `_LiteralRoundTripFixture` (1) · `_UnicodeFixture` (8)
**`sqlalchemy.testing.suite.test_unicode_ddl`** — classes: `UnicodeSchemaTest` (5)
**`sqlalchemy.testing.suite.test_update_delete`** — classes: `SimpleUpdateDeleteTest` (6)
**`sqlalchemy.testing.util`** — classes: `RandomSet` (6) · `adict` (2); functions: `all_partial_orderings` · `conforms_partial_ordering` · `count_cache_key_tuples` · `drop_all_tables` · `drop_all_tables_from_metadata` · `fail` · `flag_combinations` · `force_drop_names` · `function_named` · `lambda_combinations` · `lazy_gc` · `metadata_fixture` · `non_refcount_gc_collect` · `picklers` · `provide_metadata` · `random_choices` · `resolve_lambda` · `round_decimal` · `rowset` · `run_as_contextmanager` · `skip_if_timeout` · `teardown_events` · `total_size` · `unpickle_in_subprocess`
**`sqlalchemy.testing.warnings`** — functions: `assert_warnings` · `setup_filters` · `warn_test_suite`

## The inherits joins out — generated

(no inherits edge leaves this arm)

## Re-walk — generated

```bash
T=tenants/sqlalchemy
python3 -m graphy blast sqlalchemy://func/sqlalchemy.testing.assertions.eq_ --tenant $T/tenant.json --tenant-id sqlalchemy
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm TESTING -->
