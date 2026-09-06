# ENGINE — the connection and the shared floor (`sqlalchemy.engine` · `pool` · `connectors` · `event` · `events` · `exc` · `util` · `log`)

> Load before touching a connection, a pool, an event hook, an exception class, or a helper the
> other pillars share. Hand-cut from the walk's evidence: the walk rules `exc`, `util` and `engine`
> shared (no arm takes two thirds of their fan-in) and this arm gathers them so a change to how the
> package connects, errors or logs lands in one place. The re-walk is at the bottom.

## ⚖ The law of this arm
`exc.InvalidRequestError` and `exc.ArgumentError` are the two most-raised classes in the package,
raised from SQL, the ORM and the dialects alike. `util.concurrency.greenlet_spawn` is the single
join to greenlet, and the ORM's async session is its client. `engine.url.make_url` is how a
string becomes a connection target; `pool` hands out and reclaims DBAPI connections.

## The load-bearing symbols (walk-derived)
**`exc`** — `InvalidRequestError` · `ArgumentError` · `CompileError` · `NoSuchTableError` ·
`UnsupportedCompilationError` · `ResourceClosedError`.
**`util`** — `concurrency.greenlet_spawn` / `await_only` · `compat.inspect_getfullargspec` ·
`langhelpers.TypingOnly` · `deprecations.warn_deprecated`.
**`engine`** — `url.make_url` · `base.Engine` / `Connection` · `interfaces.Dialect`.
**`event`** — `registry.EventTarget`. **`log`** — `Identified`.

## Cross-pillar joins (all inbound)
- ← **ORM**: `greenlet_spawn`, `Identified`, `EventTarget`, the error classes.
- ← **DIALECTS**: `make_url`, `await_only`, `NoSuchTableError`, `interfaces.Dialect`.
- ← **SQL**: `CompileError`, `ArgumentError`, `warn_deprecated`.

## The join out
greenlet — `util.concurrency` imports it and `greenlet_spawn` drives it. typing_extensions —
`Protocol`, `TypedDict` under the interfaces; `deprecated` under the deprecation helpers.

<!-- graphy:arm ENGINE generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=3a9f8a3a4b15a939 cut=sha256:5fe44b5a68b5270696a6d629a7b1948137de8baef8cc767efcf102b2fb376aa4 content=sha256:71bee53065f64a8024b522850a59b3e43586c941ed6afdf70e821eaa2cdbc8f4 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`sqlalchemy.connectors`** — classes: `Connector`
**`sqlalchemy.connectors.aioodbc`** — classes: `AsyncAdaptFallback_aioodbc_connection` · `AsyncAdapt_aioodbc_connection` (8) · `AsyncAdapt_aioodbc_cursor` (2) · `AsyncAdapt_aioodbc_dbapi` (3) · `AsyncAdapt_aioodbc_ss_cursor` · `aiodbcConnector` (4)
**`sqlalchemy.connectors.asyncio`** — classes: `AsyncAdaptFallback_dbapi_connection` · `AsyncAdapt_dbapi_connection` (7) · `AsyncAdapt_dbapi_cursor` (21) · `AsyncAdapt_dbapi_module` (1) · `AsyncAdapt_dbapi_ss_cursor` (5) · `AsyncAdapt_terminate` (4) · `AsyncIODBAPIConnection` (5) · `AsyncIODBAPICursor` (14)
**`sqlalchemy.connectors.pyodbc`** — classes: `PyODBCConnector` (11)
**`sqlalchemy.engine._py_processors`** — functions: `int_to_boolean` · `str_to_date` · `str_to_datetime` · `str_to_datetime_processor_factory` · `str_to_time` · `to_decimal_processor_factory` · `to_float` · `to_str`
**`sqlalchemy.engine._py_row`** — classes: `BaseRow` (12); functions: `rowproxy_reconstructor` · `tuplegetter`
**`sqlalchemy.engine._py_util`** — functions: `_distill_params_20` · `_distill_raw_params`
**`sqlalchemy.engine.base`** — classes: `Connection` (65) · `Engine` (16) · `ExceptionContextImpl` (1) · `NestedTransaction` (8) · `OptionEngine` (1) · `OptionEngineMixin` (4) · `RootTransaction` (10) · `Transaction` (13) · `TwoPhaseTransaction` (5)
**`sqlalchemy.engine.characteristics`** — classes: `ConnectionCharacteristic` (5) · `IsolationLevelCharacteristic` (3) · `LoggingTokenCharacteristic` (5)
**`sqlalchemy.engine.create`** — functions: `create_engine` · `create_pool_from_url` · `engine_from_config`
**`sqlalchemy.engine.cursor`** — classes: `BufferedRowCursorFetchStrategy` (9) · `CursorFetchStrategy` (7) · `CursorResult` (29) · `CursorResultMetaData` (21) · `FullyBufferedCursorFetchStrategy` (7) · `NoCursorDMLFetchStrategy` (1) · `NoCursorDQLFetchStrategy` (1) · `NoCursorFetchStrategy` (6) · `ResultFetchStrategy` (7) · `_NoResultMetaData` (8); functions: `null_dml_result`
**`sqlalchemy.engine.default`** — classes: `DefaultDialect` (62) · `DefaultExecutionContext` (43) · `StrCompileDialect`
**`sqlalchemy.engine.events`** — classes: `ConnectionEvents` (20) · `DialectEvents` (8)
**`sqlalchemy.engine.interfaces`** — classes: `AdaptedConnection` (3) · `BindTyping` · `CacheStats` · `ConnectionEventsTarget` · `CreateEnginePlugin` (5) · `DBAPIConnection` (6) · `DBAPICursor` (13) · `DBAPIModule` (1) · `Error` (1) · `IntegrityError` · `InterfaceError` · `OperationalError` · `DBAPIType` · `Dialect` (80) · `ExceptionContext` · `ExecuteStyle` · `ExecutionContext` (17) · `ReflectedCheckConstraint` · `ReflectedColumn` · `ReflectedComputed` · `ReflectedConstraint` · `ReflectedForeignKeyConstraint` · `ReflectedIdentity` · `ReflectedIndex` · `ReflectedPrimaryKeyConstraint` · `ReflectedTableComment` · `ReflectedUniqueConstraint` · `_CoreKnownExecutionOptions`
**`sqlalchemy.engine.mock`** — classes: `MockConnection` (6); functions: `create_mock_engine`
**`sqlalchemy.engine.processors`** — functions: `to_decimal_processor_factory`
**`sqlalchemy.engine.reflection`** — classes: `Inspector` (52) · `ObjectKind` · `ObjectScope` · `ReflectionDefaults` (8) · `_ReflectionInfo` (1); functions: `cache` · `flexi_cache`
**`sqlalchemy.engine.result`** — classes: `ChunkedIteratorResult` (4) · `FilterResult` (12) · `FrozenResult` (4) · `IteratorResult` (9) · `MappingResult` (13) · `MergedResult` (2) · `RMKeyView` (7) · `Result` (31) · `ResultInternal` (16) · `ResultMetaData` (14) · `ScalarResult` (11) · `SimpleResultMetaData` (10) · `TupleResult` (13) · `_NoRow` · `_WithKeys` (1); functions: `null_result` · `result_tuple`
**`sqlalchemy.engine.row`** — classes: `ROMappingItemsView` · `ROMappingKeysValuesView` · `ROMappingView` (7) · `Row` (21) · `RowMapping` (9)
**`sqlalchemy.engine.strategies`** — classes: `MockEngineStrategy`
**`sqlalchemy.engine.url`** — classes: `URL` (26); functions: `_parse_url` · `make_url`
**`sqlalchemy.engine.util`** — classes: `TransactionalContext` (10) · `_TConsSubject`; functions: `connection_memoize`
**`sqlalchemy.event.api`** — functions: `_event_key` · `contains` · `listen` · `listens_for` · `remove`
**`sqlalchemy.event.attr`** — classes: `RefCollection` (1) · `_ClsLevelDispatch` (10) · `_CompoundListener` (12) · `_EmptyListener` (14) · `_InstanceLevelDispatch` (13) · `_JoinedListener` (8) · `_ListenerCollection` (7) · `_MutexProtocol` (2) · `_empty_collection` (8)
**`sqlalchemy.event.base`** — classes: `Events` (4) · `_Dispatch` (10) · `_DispatchCommon` (3) · `_HasEventsDispatch` (6) · `_JoinedDispatcher` (5) · `_UnpickleDispatch` (1) · `dispatcher` (2) · `slots_dispatcher` (1); functions: `_is_event_name` · `_remove_dispatcher`
**`sqlalchemy.event.legacy`** — functions: `_augment_fn_docs` · `_indent` · `_legacy_listen_examples` · `_legacy_signature` · `_omit_standard_example` · `_standard_listen_example` · `_version_signature_changes` · `_wrap_fn_for_legacy`
**`sqlalchemy.event.registry`** — classes: `EventTarget` · `_EventKey` (12); functions: `_clear` · `_collection_gced` · `_removed_from_collection` · `_stored_in_collection` · `_stored_in_collection_multi`
**`sqlalchemy.exc`** — classes: `AmbiguousForeignKeysError` · `ArgumentError` · `AwaitRequired` · `Base20DeprecationWarning` (1) · `CircularDependencyError` (2) · `CompileError` · `ConstraintColumnNotFoundError` · `DBAPIError` (3) · `DataError` · `DatabaseError` · `DisconnectionError` · `DontWrapMixin` · `DuplicateColumnError` · `HasDescriptionCode` (3) · `IdentifierError` · `IllegalStateChangeError` · `IntegrityError` · `InterfaceError` · `InternalError` · `InvalidRequestError` · `InvalidatePoolError` · `LegacyAPIWarning` · `MissingGreenlet` · `MovedIn20Warning` · `MultipleResultsFound` · `NoForeignKeysError` · `NoInspectionAvailable` · `NoReferenceError` · `NoReferencedColumnError` (2) · `NoReferencedTableError` (2) · `NoResultFound` · `NoSuchColumnError` · `NoSuchModuleError` · `NoSuchTableError` · `NotSupportedError` · `ObjectNotExecutableError` (2) · `OperationalError` · `PendingRollbackError` · `ProgrammingError` · `ResourceClosedError` · `SADeprecationWarning` · `SAPendingDeprecationWarning` · `SATestSuiteWarning` · `SAWarning` · `SQLAlchemyError` (3) · `StatementError` (4) · `TimeoutError` · `UnboundExecutionError` · `UnreflectableTableError` · `UnsupportedCompilationError` (2)
**`sqlalchemy.log`** — classes: `Identified` (2) · `InstanceLogger` (10) · `echo_property` (2); functions: `_add_default_handler` · `_qual_logger_name_for_cls` · `class_logger` · `instance_logger`
**`sqlalchemy.pool.base`** — classes: `ConnectionPoolEntry` (2) · `ManagesConnection` (3) · `Pool` (14) · `PoolProxiedConnection` (10) · `PoolResetState` · `ResetStyle` · `_AdhocProxiedConnection` (8) · `_AsyncConnDialect` · `_ConnDialect` (6) · `_ConnectionFairy` (19) · `_ConnectionRecord` (16) · `_CreatorFnType` (1) · `_CreatorWRecFnType` (1); functions: `_finalize_fairy`
**`sqlalchemy.pool.events`** — classes: `PoolEvents` (12)
**`sqlalchemy.pool.impl`** — classes: `AssertionPool` (6) · `AsyncAdaptedQueuePool` · `FallbackAsyncAdaptedQueuePool` · `NullPool` (5) · `QueuePool` (13) · `SingletonThreadPool` (9) · `StaticPool` (8)
**`sqlalchemy.util._collections`** — classes: `FacadeDict` (5) · `LRUCache` (11) · `OrderedIdentitySet` (1) · `OrderedProperties` (1) · `PopulateDict` (2) · `Properties` (21) · `ReadOnlyProperties` · `ScopedRegistry` (5) · `ThreadLocalRegistry` (5) · `UniqueAppender` (3) · `WeakPopulateDict` (2) · `WeakSequence` (5) · `_CreateFuncType` (1) · `_ScopeFuncType` (1); functions: `_ordered_dictionary_sort` · `coerce_generator_arg` · `coerce_to_immutabledict` · `flatten_iterator` · `has_dupes` · `has_intersection` · `merge_lists_w_ordering` · `to_column_set` · `to_list` · `to_set` · `update_copy`
**`sqlalchemy.util._concurrency_py3k`** — classes: `AsyncAdaptedLock` (3) · `_AsyncIoGreenlet` (1) · `_Runner` (7) · `greenlet` (3); functions: `_safe_cancel_awaitable` · `await_fallback` · `await_only` · `get_event_loop` · `getcurrent` · `greenlet_spawn` · `in_greenlet` · `is_exit_exception` · `iscoroutine`
**`sqlalchemy.util._has_cy`** — functions: `_import_cy_extensions`
**`sqlalchemy.util._py_collections`** — classes: `IdentitySet` (36) · `ImmutableDictBase` (8) · `OrderedSet` (28) · `ReadOnlyContainer` (5) · `immutabledict` (10); functions: `unique_list`
**`sqlalchemy.util.compat`** — classes: `FullArgSpec`; functions: `_formatannotation` · `_get_and_call_annotate` · `_get_dunder_annotations` · `_vendored_get_annotations` · `anext_` · `b` · `b64decode` · `b64encode` · `cmp` · `dataclass_fields` · `decode_backslashreplace` · `dict_union` · `get_annotations` · `importlib_metadata_get` · `inspect_formatargspec` · `inspect_getfullargspec` · `local_dataclass_fields` · `md5_not_for_security`
**`sqlalchemy.util.concurrency`** — classes: `_AsyncUtil` (4); functions: `AsyncAdaptedLock` · `_not_implemented` · `_util_async_run` · `_util_async_run_coroutine_function` · `await_fallback` · `await_only` · `greenlet_spawn` · `in_greenlet` · `is_exit_exception`
**`sqlalchemy.util.deprecations`** — functions: `_decorate_cls_with_warning` · `_decorate_with_warning` · `_sanitize_restructured_text` · `_warn_with_version` · `became_legacy_20` · `deprecated` · `deprecated_cls` · `deprecated_params` · `moved_20` · `warn_deprecated` · `warn_deprecated_limited`
**`sqlalchemy.util.langhelpers`** — classes: `EnsureKWArg` (2) · `HasMemoized` (4) · `memoized_attribute` (2) · `MemoizedSlots` (2) · `PluginLoader` (5) · `TypingOnly` (1) · `_FastIntFlag` · `_IntFlagMeta` (2) · `_Missing` · `_hash_limit_string` (3) · `_memoized_property` (3) · `_non_memoized_property` (1) · `classproperty` (2) · `generic_fn_descriptor` (6) · `hybridmethod` (3) · `hybridproperty` (3) · `portable_instancemethod` (4) · `rw_hybridproperty` (5) · `safe_reraise` (2) · `symbol` (4); functions: `_dedent_docstring` · `_exec_code_in_env` · `_inspect_func_args` · `_unique_symbols` · `_warnings_warn` · `add_parameter_text` · `as_interface` · `asbool` · `asint` · `assert_arg_type` · `attrsetter` · `bool_or_str` · `chop_traceback` · `class_hierarchy` · `clsname_as_plain_name` · `coerce_kw_type` · `constructor_copy` · `constructor_key` · `counter` · `create_proxy_methods` · `decode_slice` · `decorator` · `dictlike_iteritems` · `duck_type_collection` · `ellipses_string` · `find_matching_paren` · `format_argspec_init` · `format_argspec_plus` · `generic_repr` · `get_callable_argspec` · `get_cls_kwargs` · `get_func_kwargs` · `getargspec_init` · `has_compiled_ext` · `inject_docstring_text` · `inject_param_text` · `iterate_attributes` · `map_bits` · `md5_hex` · `memoized_instancemethod` · `method_is_overridden` · `methods_equivalent` · `monkeypatch_proxied_specials` · `only_once` · `parse_user_argument_for_enum` · `quoted_token_parser` · `repr_tuple_names` · `set_creation_order` · `string_or_unprintable` · `strip_outer_parens` · `tag_method_for_warnings` · `unbound_method_to_callable` · `walk_subclasses` · `warn` · `warn_exception` · `warn_limited` · `wrap_callable`
**`sqlalchemy.util.preloaded`** — classes: `_ModuleRegistry` (3)
**`sqlalchemy.util.queue`** — classes: `AsyncAdaptedQueue` (10) · `Empty` · `FallbackAsyncAdaptedQueue` · `Full` · `Queue` (14) · `QueueCommon` (8)
**`sqlalchemy.util.tool_support`** — classes: `code_writer_cmd` (10)
**`sqlalchemy.util.topological`** — functions: `_gen_edges` · `find_cycles` · `sort` · `sort_as_subsets`
**`sqlalchemy.util.typing`** — classes: `ArgsTypeProtocol` · `CallableReference` (3) · `DescriptorProto` (3) · `DescriptorReference` (3) · `GenericProtocol` · `RODescriptorReference` (3) · `SupportsKeysAndGetItem` (2) · `_TypingInstances` (1); functions: `_copy_generic_annotation_with` · `_de_optionalize_fwd_ref_union_types` · `_get_type_name` · `de_optionalize_union_types` · `de_stringify_annotation` · `eval_expression` · `eval_name_only` · `fixup_container_fwd_refs` · `flatten_newtype` · `includes_none` · `is_a_type` · `is_fwd_none` · `is_fwd_ref` · `is_generic` · `is_literal` · `is_newtype` · `is_non_string_iterable` · `is_origin_of` · `is_origin_of_cls` · `is_pep593` · `is_pep695` · `is_union` · `make_union_type` · `pep695_values` · `resolve_name_to_real_class_name`

## The inherits joins out — generated

- `connectors.asyncio.AsyncIODBAPIConnection` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `connectors.asyncio.AsyncIODBAPICursor` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `engine.interfaces.DBAPIConnection` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `engine.interfaces.DBAPICursor` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `engine.interfaces.DBAPIModule` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `engine.interfaces.DBAPIType` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `engine.interfaces.ReflectedColumn` ──inherits──▶ `typing_extensions.TypedDict` typing_extensions
- `engine.interfaces.ReflectedComputed` ──inherits──▶ `typing_extensions.TypedDict` typing_extensions
- `engine.interfaces.ReflectedConstraint` ──inherits──▶ `typing_extensions.TypedDict` typing_extensions
- `engine.interfaces.ReflectedIdentity` ──inherits──▶ `typing_extensions.TypedDict` typing_extensions
- `engine.interfaces.ReflectedIndex` ──inherits──▶ `typing_extensions.TypedDict` typing_extensions
- `engine.interfaces.ReflectedTableComment` ──inherits──▶ `typing_extensions.TypedDict` typing_extensions
- `engine.interfaces._CoreKnownExecutionOptions` ──inherits──▶ `typing_extensions.TypedDict` typing_extensions
- `engine.result.ResultInternal` ──inherits──▶ `sqlalchemy.sql.base.InPlaceGenerative` [SQL]
- `engine.util._TConsSubject` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `event.attr._MutexProtocol` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `pool.base._CreatorFnType` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `pool.base._CreatorWRecFnType` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `util._collections._ScopeFuncType` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `util._concurrency_py3k.greenlet` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `util.typing.ArgsTypeProtocol` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `util.typing.DescriptorProto` ──inherits──▶ `typing_extensions.Protocol` typing_extensions

## Re-walk — generated

```bash
T=tenants/sqlalchemy
python3 -m graphy blast sqlalchemy://class/sqlalchemy.exc.InvalidRequestError --tenant $T/tenant.json --tenant-id sqlalchemy
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm ENGINE -->
