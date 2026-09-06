# ORM — the mapper and its extensions (`sqlalchemy.orm` · `ext`)

> Load before touching a mapped class, a session, a relationship, a loader strategy, or an
> extension (`asyncio`, `hybrid`, `automap`, `declarative`, `mypy`). Hand-cut from the walk's
> evidence; `ext` rides here because the walk shows nearly all of it consuming `orm`. The re-walk
> is at the bottom.

## ⚖ The law of this arm
The ORM is the largest orchestrator by fan-out in the package and it consumes SQL and ENGINE,
never the reverse. `orm.base.instance_state` / `instance_dict` / `class_mapper` are the doors from
an object to its mapping; `session.Session` is the unit of work; `util.AliasedClass` and `_ORMJoin`
are how a mapped class becomes an expression. `ext.asyncio` reaches ENGINE's `greenlet_spawn`.

## The load-bearing symbols (walk-derived)
**`orm`** — `base.instance_state` / `instance_dict` / `class_mapper` / `state_str` / `_assertions` ·
`session.Session` · `util.AliasedClass` / `_ORMJoin` · `exc.UnmappedInstanceError` /
`UnmappedClassError` · `interfaces._AttributeOptions` · `path_registry.PathRegistry.coerce` ·
`state_changes._StateChange.declare_states` · `evaluator.UnevaluatableError`.
**`ext`** — `asyncio` (the greenlet client) · `hybrid` · `automap` · `declarative` · `mypy.util.fail`.

## Cross-pillar joins
- → **SQL**: `select`, `inspect`, `expect`, `bindparam`. → **ENGINE**: `greenlet_spawn`, the errors.
- ← **TESTING**: `instance_state`, the fixtures' mapped entities.

## The join out
typing_extensions — `Protocol`, `TypedDict` under the interfaces, `deprecated` on the retired
verbs.

<!-- graphy:arm ORM generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=3a9f8a3a4b15a939 cut=sha256:5fe44b5a68b5270696a6d629a7b1948137de8baef8cc767efcf102b2fb376aa4 content=sha256:6cc0d44a8e720e5d61f309406999c076ea588ad3b44caab82ff286a39e9367f5 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`sqlalchemy.ext.associationproxy`** — classes: `AmbiguousAssociationProxyInstance` (9) · `AssociationProxy` (9) · `AssociationProxyExtensionType` · `AssociationProxyInstance` (27) · `ColumnAssociationProxyInstance` (2) · `ObjectAssociationProxyInstance` (3) · `_AssociationCollection` (6) · `_AssociationDict` (23) · `_AssociationList` (31) · `_AssociationProxyProtocol` (3) · `_AssociationSet` (38) · `_AssociationSingleItem` (3) · `_CreatorProtocol` · `_DictSetterProtocol` (1) · `_GetSetFactoryProtocol` (1) · `_GetterProtocol` (1) · `_KeyCreatorProtocol` (1) · `_LazyCollectionProtocol` (1) · `_PlainCreatorProtocol` (1) · `_PlainSetterProtocol` (1) · `_ProxyBulkSetProtocol` (1) · `_ProxyFactoryProtocol` (1) · `_SetterProtocol` · `_lazy_collection` (4); functions: `association_proxy`
**`sqlalchemy.ext.asyncio.base`** — classes: `GeneratorStartableContext` (3) · `ProxyComparable` (4) · `ReversibleProxy` (4) · `StartableContext` (5); functions: `asyncstartablecontext`
**`sqlalchemy.ext.asyncio.engine`** — classes: `AsyncConnectable` (1) · `AsyncConnection` (33) · `AsyncEngine` (18) · `AsyncTransaction` (10); functions: `_get_sync_engine_or_connection` · `_no_insp_for_async_conn_yet` · `_no_insp_for_async_engine_xyet` · `async_engine_from_config` · `create_async_engine` · `create_async_pool_from_url`
**`sqlalchemy.ext.asyncio.exc`** — classes: `AsyncContextAlreadyStarted` · `AsyncContextNotStarted` · `AsyncMethodRequired`
**`sqlalchemy.ext.asyncio.result`** — classes: `AsyncCommon` (2) · `AsyncMappingResult` (13) · `AsyncResult` (21) · `AsyncScalarResult` (11) · `AsyncTupleResult` (13); functions: `_ensure_sync_result`
**`sqlalchemy.ext.asyncio.scoping`** — classes: `async_scoped_session` (47)
**`sqlalchemy.ext.asyncio.session`** — classes: `AsyncAttrs` (1) · `_AsyncAttrGetitem` (2) · `AsyncSession` (51) · `AsyncSessionTransaction` (8) · `_AsyncSessionContextManager` (3) · `async_sessionmaker` (5); functions: `async_object_session` · `async_session` · `close_all_sessions`
**`sqlalchemy.ext.automap`** — classes: `AutomapBase` (2) · `GenerateRelationshipType` (1) · `NameForCollectionRelationshipType` (1) · `NameForScalarRelationshipType` (1) · `PythonNameForTableType` (1) · `_Bookkeeping`; functions: `_is_many_to_many` · `_m2m_relationship` · `_relationships_for_fks` · `automap_base` · `classname_for_table` · `generate_relationship` · `name_for_collection_relationship` · `name_for_scalar_relationship`
**`sqlalchemy.ext.baked`** — classes: `BakedQuery` (18) · `Bakery` (2) · `Result` (16)
**`sqlalchemy.ext.compiler`** — classes: `_dispatcher` (2); functions: `compiles` · `deregister`
**`sqlalchemy.ext.declarative`** — functions: `as_declarative` · `declarative_base` · `has_inherited_table` · `synonym_for`
**`sqlalchemy.ext.declarative.extensions`** — classes: `AbstractConcreteBase` (3) · `ConcreteBase` (2) · `DeferredReflection` (3)
**`sqlalchemy.ext.horizontal_shard`** — classes: `IdentityChooser` (1) · `ShardChooser` (1) · `ShardedQuery` (2) · `ShardedSession` (6) · `set_shard_id` (1); functions: `execute_and_instances`
**`sqlalchemy.ext.hybrid`** — classes: `Comparator` (4) · `ExprComparator` (7) · `HybridExtensionType` · `_HybridClassLevelAccessor` (5) · `_HybridComparatorCallableType` (1) · `_HybridDeleterType` (1) · `_HybridExprCallableType` (1) · `_HybridGetterType` (1) · `_HybridSetterType` (1) · `_HybridUpdaterType` (1) · `hybrid_method` (4) · `hybrid_property` (16) · `_InPlace` (8); functions: `_unwrap_classmethod`
**`sqlalchemy.ext.indexable`** — classes: `index_property` (6)
**`sqlalchemy.ext.instrumentation`** — classes: `ExtendedInstrumentationRegistry` (9) · `InstrumentationManager` (17) · `_ClassInstrumentationAdapter` (19); functions: `_install_instrumented_lookups` · `_install_lookups` · `_reinstall_default_lookups` · `find_native_user_instrumentation_hook`
**`sqlalchemy.ext.mutable`** — classes: `Mutable` (4) · `MutableBase` (4) · `MutableComposite` (2) · `MutableDict` (10) · `MutableList` (14) · `MutableSet` (17); functions: `_setup_composite_listener`
**`sqlalchemy.ext.mypy.apply`** — functions: `_apply_placeholder_attr_to_class` · `add_additional_orm_attributes` · `apply_mypy_mapped_attr` · `apply_type_to_mapped_statement` · `re_apply_declarative_assignments`
**`sqlalchemy.ext.mypy.decl_class`** — functions: `_scan_declarative_assignment_stmt` · `_scan_declarative_decorator_stmt` · `_scan_for_mapped_bases` · `_scan_symbol_table_entry` · `scan_declarative_assignments_and_apply_types`
**`sqlalchemy.ext.mypy.infer`** — functions: `_infer_collection_type_from_left_and_inferred_right` · `_infer_type_from_decl_column` · `_infer_type_from_decl_column_property` · `_infer_type_from_decl_composite_property` · `_infer_type_from_left_and_inferred_right` · `_infer_type_from_mapped` · `_infer_type_from_relationship` · `extract_python_type_from_typeengine` · `infer_type_from_left_hand_type_only` · `infer_type_from_right_hand_nameexpr`
**`sqlalchemy.ext.mypy.names`** — functions: `expr_to_mapped_constructor` · `has_base_type_id` · `mro_has_id` · `type_id_for_callee` · `type_id_for_fullname` · `type_id_for_named_node` · `type_id_for_unbound_type`
**`sqlalchemy.ext.mypy.plugin`** — classes: `SQLAlchemyPlugin` (7); functions: `_add_globals` · `_base_cls_decorator_hook` · `_base_cls_hook` · `_cls_decorator_hook` · `_declarative_mixin_hook` · `_dynamic_class_hook` · `_fill_in_decorators` · `_metaclass_cls_hook` · `_queryable_getattr_hook` · `_set_declarative_metaclass` · `plugin`
**`sqlalchemy.ext.mypy.util`** — classes: `SQLAlchemyAttribute` (4); functions: `_get_info_metadata` · `_get_info_mro_metadata` · `_set_info_metadata` · `add_global` · `establish_as_sqlalchemy` · `fail` · `flatten_typechecking` · `format_type` · `get_callexpr_kwarg` · `get_has_table` · `get_is_base` · `get_mapped_attributes` · `has_declarative_base` · `info_for_cls` · `name_is_dunder` · `serialize_type` · `set_has_table` · `set_is_base` · `set_mapped_attributes` · `type_for_callee` · `unbound_to_instance`
**`sqlalchemy.ext.orderinglist`** — classes: `OrderingList` (13); functions: `_reconstitute` · `_unsugar_count_from` · `count_from_0` · `count_from_1` · `count_from_n_factory` · `ordering_list`
**`sqlalchemy.ext.serializer`** — classes: `Deserializer` (3) · `Serializer` (1); functions: `dumps` · `loads`
**`sqlalchemy.orm`** — functions: `__go`
**`sqlalchemy.orm._orm_constructors`** — functions: `_mapper_fn` · `aliased` · `backref` · `clear_mappers` · `column_property` · `composite` · `contains_alias` · `create_session` · `deferred` · `dynamic_loader` · `join` · `mapped_column` · `orm_insert_sentinel` · `outerjoin` · `query_expression` · `relationship` · `synonym` · `with_loader_criteria` · `with_polymorphic`
**`sqlalchemy.orm._typing`** — classes: `_LoaderCallable` (1) · `_ORMAdapterProto` (1) · `_OrmKnownExecutionOptions`; functions: `attr_is_internal_proxy` · `insp_is_aliased_class` · `insp_is_attribute` · `insp_is_mapper` · `insp_is_mapper_property` · `is_collection_impl` · `is_composite_class` · `is_has_collection_adapter` · `is_orm_option` · `is_user_defined_option` · `prop_is_relationship`
**`sqlalchemy.orm.attributes`** — classes: `AdHocHasEntityNamespace` (1) · `AttributeEventToken` (4) · `AttributeImpl` (18) · `CollectionAttributeImpl` (19) · `HasCollectionAdapter` (3) · `History` (11) · `InstrumentedAttribute` (4) · `QueryableAttribute` (24) · `ScalarAttributeImpl` (6) · `ScalarObjectAttributeImpl` (6); functions: `_is_collection_attribute_impl` · `_queryable_attribute_unreduce` · `backref_listeners` · `create_proxied_attribute` · `del_attribute` · `flag_dirty` · `flag_modified` · `get_attribute` · `get_history` · `get_state_history` · `has_parent` · `init_collection` · `init_state_collection` · `register_attribute` · `register_attribute_impl` · `register_descriptor` · `set_attribute` · `set_committed_value` · `unregister_attribute`
**`sqlalchemy.orm.base`** — classes: `DynamicMapped` (2) · `EventConstants` · `InspectionAttr` · `InspectionAttrExtensionType` · `InspectionAttrInfo` (1) · `LoaderCallableStatus` · `Mapped` (4) · `NotExtension` · `ORMDescriptor` (1) · `PassiveFlag` · `RelationshipDirection` · `SQLORMExpression` · `SQLORMOperations` (4) · `WriteOnlyMapped` (2) · `_DeclarativeMapped` (2) · `_MappedAnnotationBase` · `_MappedAttribute`; functions: `_assertions` · `_class_to_mapper` · `_entity_descriptor` · `_inspect_mapped_class` · `_inspect_mapped_object` · `_is_aliased_class` · `_is_mapped_class` · `_mapper_or_none` · `_parse_mapper_argument` · `_state_mapper` · `attribute_str` · `class_mapper` · `instance_dict` · `instance_state` · `instance_str` · `manager_of_class` · `object_mapper` · `object_state` · `opt_manager_of_class` · `state_attribute_str` · `state_class_str` · `state_str`
**`sqlalchemy.orm.bulk_persistence`** — classes: `BulkORMDelete` (5) · `BulkORMInsert` (6) · `default_insert_options` · `BulkORMUpdate` (9) · `BulkUDCompileState` (12) · `default_update_options` · `ORMDMLState` (8); functions: `_bulk_insert` · `_bulk_update` · `_expand_composites`
**`sqlalchemy.orm.clsregistry`** — classes: `ClsRegistryToken` · `_GetColumns` (2) · `_GetTable` (2) · `_ModNS` (2) · `_ModuleMarker` (8) · `_MultipleClassMarker` (6) · `_class_resolver` (5); functions: `_determine_container` · `_key_is_empty` · `_resolver` · `add_class` · `remove_class`
**`sqlalchemy.orm.collections`** — classes: `CollectionAdapter` (27) · `InstrumentedDict` · `InstrumentedList` · `InstrumentedSet` · `_AdaptedCollectionProtocol` · `_CollectionConverterProtocol` (1) · `collection` (9); functions: `__before_pop` · `__del` · `__go` · `__set` · `__set_wo_mutation` · `_assert_required_roles` · `_dict_decorators` · `_instrument_class` · `_instrument_membership_mutator` · `_list_decorators` · `_locate_roles_and_methods` · `_set_binops_check_loose` · `_set_binops_check_strict` · `_set_collection_attributes` · `_set_decorators` · `_setup_canned_roles` · `bulk_replace` · `collection_adapter` · `prepare_instrumentation`
**`sqlalchemy.orm.context`** — classes: `AbstractORMCompileState` (5) · `AutoflushOnlyORMCompileState` (2) · `CompoundSelectCompileState` · `FromStatement` (9) · `ORMCompileState` (12) · `default_compile_options` · `ORMFromStatementCompileState` (4) · `ORMSelectCompileState` (30) · `QueryContext` (2) · `default_load_options` · `_BundleEntity` (8) · `_ColumnEntity` (5) · `_DMLBulkInsertReturningColFilter` (1) · `_DMLReturningColFilter` (3) · `_DMLUpdateDeleteReturningColFilter` (1) · `_IdentityTokenEntity` (2) · `_MapperEntity` (8) · `_ORMColumnEntity` (4) · `_QueryEntity` (4) · `_RawColumnEntity` (4); functions: `_column_descriptions` · `_determine_last_joined_entity` · `_entity_from_pre_ent_zero` · `_legacy_filter_by_entity_zero`
**`sqlalchemy.orm.decl_api`** — classes: `DCTransformDeclarative` · `DeclarativeAttributeIntercept` · `DeclarativeBase` (4) · `DeclarativeBaseNoMeta` (4) · `DeclarativeMeta` (1) · `MappedAsDataclass` (1) · `_DynamicAttributesType` (2) · `_declared_attr_common` (3) · `_declared_directive` (5) · `_stateful_declared_attr` (3) · `declared_attr` (7) · `registry` (21); functions: `_check_not_declarative` · `_inspect_decl_meta` · `_setup_declarative_base` · `add_mapped_attribute` · `as_declarative` · `declarative_base` · `declarative_mixin` · `has_inherited_table` · `mapped_as_dataclass` · `synonym_for`
**`sqlalchemy.orm.decl_base`** — classes: `MappedClassProtocol` (1) · `_ClassScanMapperConfig` (20) · `_CollectedAnnotation` · `_DataclassArguments` · `_DeclMappedClassProtocol` (2) · `_DeferredMapperConfig` (8) · `_ImperativeMapperConfig` (3) · `_MapperConfig` (5); functions: `_add_attribute` · `_as_dc_declaredattr` · `_as_declarative` · `_check_declared_props_nocascade` · `_declarative_constructor` · `_declared_mapping_info` · `_del_attribute` · `_dive_for_cls_manager` · `_get_immediate_cls_attr` · `_is_declarative_props` · `_is_supercls_for_inherits` · `_mapper` · `_resolve_for_abstract_or_classical` · `_undefer_column_name`
**`sqlalchemy.orm.dependency`** — classes: `DependencyProcessor` (17) · `DetectKeySwitch` (11) · `ManyToManyDP` (9) · `ManyToOneDP` (8) · `OneToManyDP` (8)
**`sqlalchemy.orm.descriptor_props`** — classes: `Composite` · `CompositeProperty` (21) · `Comparator` (12) · `CompositeBundle` (2) · `ConcreteInheritedProperty` (2) · `DescriptorProperty` (3) · `Synonym` · `SynonymProperty` (7)
**`sqlalchemy.orm.dynamic`** — classes: `AppenderMixin` (12) · `AppenderQuery` · `DynaLoader` · `DynamicAttributeImpl` (1) · `DynamicCollectionHistory` (1); functions: `mixin_user_query`
**`sqlalchemy.orm.evaluator`** — classes: `UnevaluatableError` · `_EvaluatorCompiler` (26) · `_ExpiredObject` (2) · `_NoObject` (2); functions: `__getattr__`
**`sqlalchemy.orm.events`** — classes: `AttributeEvents` (12) · `InstanceEvents` (14) · `InstrumentationEvents` (6) · `MapperEvents` (16) · `QueryEvents` (4) · `SessionEvents` (28) · `_EventsHold` (4) · `HoldEvents` (1) · `_InstanceEventsHold` (1) · `HoldInstanceEvents` · `_InstrumentationEventsHold` (1) · `_MapperEventsHold` (1) · `HoldMapperEvents`
**`sqlalchemy.orm.exc`** — classes: `DetachedInstanceError` · `FlushError` · `LoaderStrategyException` (1) · `MappedAnnotationError` · `ObjectDeletedError` (2) · `ObjectDereferencedError` · `StaleDataError` · `UnmappedClassError` (2) · `UnmappedColumnError` · `UnmappedError` · `UnmappedInstanceError` (2); functions: `_default_unmapped` · `_safe_cls_name`
**`sqlalchemy.orm.identity`** — classes: `IdentityMap` (21) · `WeakInstanceDict` (15); functions: `_killed`
**`sqlalchemy.orm.instrumentation`** — classes: `ClassManager` (45) · `InstrumentationFactory` (4) · `_ExpiredAttributeLoaderProto` (1) · `_ManagerFactory` (1) · `_SerializeManager` (2); functions: `_generate_init` · `is_instrumented` · `register_class` · `unregister_class`
**`sqlalchemy.orm.interfaces`** — classes: `CompileStateOption` (2) · `CriteriaOption` (1) · `LoaderOption` (1) · `LoaderStrategy` (5) · `MapperOption` (2) · `MapperProperty` (13) · `ORMColumnDescription` · `ORMColumnsClauseRole` · `ORMEntityColumnsClauseRole` · `ORMFromClauseRole` · `ORMOption` (1) · `ORMStatementRole` · `PropComparator` (18) · `StrategizedProperty` (10) · `UserDefinedOption` (1) · `_AttributeOptions` (2) · `_DCAttributeOptions` · `_IntrospectsAnnotations` (4) · `_MapsColumns` (2)
**`sqlalchemy.orm.loading`** — classes: `PostLoad` (6); functions: `_decorate_polymorphic_switch` · `_instance_processor` · `_load_subclass_via_in` · `_populate_full` · `_populate_partial` · `_set_get_options` · `_setup_entity_query` · `_validate_version_id` · `_warn_for_runid_changed` · `get_from_identity` · `instances` · `load_on_ident` · `load_on_pk_identity` · `load_scalar_attributes` · `merge_frozen_result` · `merge_result`
**`sqlalchemy.orm.mapped_collection`** — classes: `KeyFuncDict` (6) · `_AttrGetter` (3) · `_PlainColumnGetter` (4) · `_SerializableColumnGetterV2` (4); functions: `_mapped_collection_cls` · `attribute_keyed_dict` · `column_keyed_dict` · `keyfunc_mapping`
**`sqlalchemy.orm.mapper`** — classes: `Mapper` (121) · `_ColumnMapping` (2) · `_OptGetColumnsNotAvailable`; functions: `_all_registries` · `_configure_registries` · `_dispose_registries` · `_do_configure_registries` · `_event_on_init` · `_event_on_load` · `_unconfigured_mappers` · `configure_mappers` · `reconstructor` · `validates`
**`sqlalchemy.orm.path_registry`** — classes: `AbstractEntityRegistry` (7) · `CachingEntityRegistry` (3) · `CreatesToken` (1) · `PathRegistry` (24) · `PathToken` (2) · `PropRegistry` (4) · `RootRegistry` (2) · `SlotsEntityRegistry` · `TokenRegistry` (4) · `_ERDict` (2); functions: `_unreduce_path` · `is_entity` · `is_root` · `path_is_entity` · `path_is_property`
**`sqlalchemy.orm.persistence`** — functions: `_collect_delete_commands` · `_collect_insert_commands` · `_collect_post_update_commands` · `_collect_update_commands` · `_connections_for_states` · `_emit_delete_statements` · `_emit_insert_statements` · `_emit_post_update_statements` · `_emit_update_statements` · `_finalize_insert_update_commands` · `_organize_states_for_delete` · `_organize_states_for_post_update` · `_organize_states_for_save` · `_postfetch` · `_postfetch_bulk_save` · `_postfetch_post_update` · `_sort_states` · `delete_obj` · `post_update` · `save_obj`
**`sqlalchemy.orm.properties`** — classes: `ColumnProperty` (14) · `Comparator` (8) · `MappedColumn` (13) · `MappedSQLExpression`
**`sqlalchemy.orm.query`** — classes: `AliasOption` (2) · `BulkDelete` (1) · `BulkUD` (3) · `BulkUpdate` (1) · `Query` (110) · `RowReturningQuery` (1)
**`sqlalchemy.orm.relationships`** — classes: `JoinCondition` (38) · `Relationship` · `RelationshipProperty` (36) · `Comparator` (17) · `_ColInAnnotations` (2) · `_RelationshipArg` (2) · `_RelationshipArgs` · `_RelationshipDeclared` (1); functions: `_annotate_columns` · `foreign` · `remote`
**`sqlalchemy.orm.scoping`** — classes: `QueryPropertyDescriptor` (1) · `scoped_session` (48)
**`sqlalchemy.orm.session`** — classes: `ORMExecuteState` (23) · `Session` (78) · `SessionTransaction` (21) · `SessionTransactionOrigin` · `SessionTransactionState` · `_ConnectionCallableProto` (1) · `_SessionClassMethods` (3) · `_SessionCloseState` · `sessionmaker` (5); functions: `_state_session` · `close_all_sessions` · `make_transient` · `make_transient_to_detached` · `object_session`
**`sqlalchemy.orm.state`** — classes: `AttributeState` (5) · `InstanceState` (48) · `PendingCollection` (4) · `_InstallLoaderCallableProto` (1) · `_InstanceDictProto` (1)
**`sqlalchemy.orm.state_changes`** — classes: `_StateChange` (3) · `_StateChangeState` · `_StateChangeStates`
**`sqlalchemy.orm.strategies`** — classes: `AbstractRelationshipLoader` (2) · `ColumnLoader` (4) · `DeferredColumnLoader` (6) · `DoNothingLoader` · `ExpressionColumnLoader` (4) · `ImmediateLoader` (4) · `JoinedLoader` (12) · `LazyLoader` (9) · `LoadDeferredColumns` (2) · `LoadLazyAttribute` (3) · `NoLoader` (2) · `PostLoader` (1) · `SelectInLoader` (9) · `SubqueryLoader` (12) · `_SubqCollections` (4) · `UninstrumentedColumnLoader` (3); functions: `_register_attribute` · `single_parent_validator`
**`sqlalchemy.orm.strategy_options`** — classes: `Load` (13) · `_AbstractLoad` (27) · `_AttributeStrategyLoad` (7) · `_ClassStrategyLoad` (2) · `_LoadElement` (18) · `_TokenStrategyLoad` (2) · `_WildcardLoad` (8); functions: `_expand_column_strategy_attrs` · `_generate_from_keys` · `_parse_attr_argument` · `_raise_for_does_not_link` · `contains_eager` · `defaultload` · `defer` · `immediateload` · `joinedload` · `lazyload` · `load_only` · `loader_unbound_fn` · `noload` · `raiseload` · `selectin_polymorphic` · `selectinload` · `subqueryload` · `undefer` · `undefer_group` · `with_expression`
**`sqlalchemy.orm.sync`** — functions: `_raise_col_to_prop` · `bulk_populate_inherit_keys` · `clear` · `populate` · `populate_dict` · `source_modified` · `update`
**`sqlalchemy.orm.unitofwork`** — classes: `DeleteAll` (4) · `DeleteState` (3) · `IterateMappersMixin` (1) · `PostSortRec` (2) · `PostUpdateAll` (2) · `Preprocess` (2) · `ProcessAll` (5) · `ProcessState` (3) · `SaveUpdateAll` (4) · `SaveUpdateState` (3) · `UOWTransaction` (18); functions: `track_cascade_events`
**`sqlalchemy.orm.util`** — classes: `AliasedClass` (6) · `AliasedInsp` (21) · `Bundle` (10) · `CascadeOptions` (3) · `LoaderCriteriaOption` (9) · `ORMAdapter` (2) · `ORMStatementAdapter` (1) · `_CleanupError` · `_DeStringifyAnnotation` (1) · `_EvalNameOnly` (1) · `_ORMJoin` (4) · `_TraceAdaptRole` · `_WrapUserEntity` (2); functions: `_cleanup_mapped_str_annotation` · `_entity_corresponds_to` · `_entity_corresponds_to_use_path_impl` · `_entity_isa` · `_extract_mapped_subtype` · `_getitem` · `_inspect_generic_alias` · `_inspect_mc` · `_is_mapped_annotation` · `_mapper_property_as_plain_name` · `_orm_annotate` · `_orm_deannotate` · `_orm_full_deannotate` · `_validator_events` · `has_identity` · `identity_key` · `polymorphic_union` · `was_deleted` · `with_parent`
**`sqlalchemy.orm.writeonly`** — classes: `AbstractCollectionWriter` (3) · `DynamicCollectionAdapter` (5) · `WriteOnlyAttributeImpl` (17) · `WriteOnlyCollection` (8) · `WriteOnlyHistory` (7) · `WriteOnlyLoader` (1)

## The inherits joins out — generated

- `ext.associationproxy._CreatorProtocol` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `ext.associationproxy._GetSetFactoryProtocol` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `ext.associationproxy._ProxyBulkSetProtocol` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `ext.associationproxy._ProxyFactoryProtocol` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `ext.associationproxy._SetterProtocol` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `ext.asyncio.exc.AsyncContextAlreadyStarted` ──inherits──▶ `sqlalchemy.exc.InvalidRequestError` [ENGINE]
- `ext.asyncio.exc.AsyncContextNotStarted` ──inherits──▶ `sqlalchemy.exc.InvalidRequestError` [ENGINE]
- `ext.asyncio.exc.AsyncMethodRequired` ──inherits──▶ `sqlalchemy.exc.InvalidRequestError` [ENGINE]
- `ext.asyncio.result.AsyncMappingResult` ──inherits──▶ `sqlalchemy.engine.result._WithKeys` [ENGINE]
- `ext.asyncio.result.AsyncResult` ──inherits──▶ `sqlalchemy.engine.result._WithKeys` [ENGINE]
- `ext.automap.GenerateRelationshipType` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `ext.automap.NameForCollectionRelationshipType` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `ext.automap.NameForScalarRelationshipType` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `ext.automap.PythonNameForTableType` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `ext.horizontal_shard.IdentityChooser` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `ext.horizontal_shard.ShardChooser` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `orm._typing._LoaderCallable` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `orm._typing._ORMAdapterProto` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `orm._typing._OrmKnownExecutionOptions` ──inherits──▶ `sqlalchemy.engine.interfaces._CoreKnownExecutionOptions` [ENGINE]
- `orm.attributes.AdHocHasEntityNamespace` ──inherits──▶ `sqlalchemy.sql.cache_key.HasCacheKey` [SQL]
- `orm.attributes.QueryableAttribute` ──inherits──▶ `sqlalchemy.event.registry.EventTarget` [ENGINE]
- `orm.attributes.QueryableAttribute` ──inherits──▶ `sqlalchemy.sql.base.Immutable` [SQL]
- `orm.attributes.QueryableAttribute` ──inherits──▶ `sqlalchemy.sql.cache_key.SlotsMemoizedHasCacheKey` [SQL]
- `orm.attributes.QueryableAttribute` ──inherits──▶ `sqlalchemy.sql.roles.JoinTargetRole` [SQL]
- `orm.attributes.QueryableAttribute` ──inherits──▶ `sqlalchemy.sql.roles.OnClauseRole` [SQL]
- `orm.base.Mapped` ──inherits──▶ `sqlalchemy.sql.roles.DDLConstraintColumnRole` [SQL]
- `orm.base.ORMDescriptor` ──inherits──▶ `sqlalchemy.util.langhelpers.TypingOnly` [ENGINE]
- `orm.base.SQLORMExpression` ──inherits──▶ `sqlalchemy.util.langhelpers.TypingOnly` [ENGINE]
- `orm.base.SQLORMOperations` ──inherits──▶ `sqlalchemy.util.langhelpers.TypingOnly` [ENGINE]
- `orm.base._MappedAnnotationBase` ──inherits──▶ `sqlalchemy.util.langhelpers.TypingOnly` [ENGINE]
- `orm.base._MappedAttribute` ──inherits──▶ `sqlalchemy.util.langhelpers.TypingOnly` [ENGINE]
- `orm.bulk_persistence.BulkORMDelete` ──inherits──▶ `sqlalchemy.sql.dml.DeleteDMLState` [SQL]
- `orm.bulk_persistence.BulkORMInsert` ──inherits──▶ `sqlalchemy.sql.dml.InsertDMLState` [SQL]
- `orm.bulk_persistence.BulkORMInsert.default_insert_options` ──inherits──▶ `sqlalchemy.sql.base.Options` [SQL]
- `orm.bulk_persistence.BulkORMUpdate` ──inherits──▶ `sqlalchemy.sql.dml.UpdateDMLState` [SQL]
- `orm.bulk_persistence.BulkUDCompileState.default_update_options` ──inherits──▶ `sqlalchemy.sql.base.Options` [SQL]
- `orm.collections._AdaptedCollectionProtocol` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `orm.collections._CollectionConverterProtocol` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `orm.context.AbstractORMCompileState` ──inherits──▶ `sqlalchemy.sql.base.CompileState` [SQL]
- `orm.context.CompoundSelectCompileState` ──inherits──▶ `sqlalchemy.sql.selectable.CompoundSelectState` [SQL]
- `orm.context.FromStatement` ──inherits──▶ `sqlalchemy.sql.base.Generative` [SQL]
- `orm.context.FromStatement` ──inherits──▶ `sqlalchemy.sql.elements.GroupedElement` [SQL]
- `orm.context.ORMCompileState.default_compile_options` ──inherits──▶ `sqlalchemy.sql.base.CacheableOptions` [SQL]
- `orm.context.ORMSelectCompileState` ──inherits──▶ `sqlalchemy.sql.selectable.SelectState` [SQL]
- `orm.context.QueryContext.default_load_options` ──inherits──▶ `sqlalchemy.sql.base.Options` [SQL]
- `orm.decl_base._DataclassArguments` ──inherits──▶ `typing_extensions.TypedDict` typing_extensions
- `orm.decl_base._DeclMappedClassProtocol` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `orm.evaluator.UnevaluatableError` ──inherits──▶ `sqlalchemy.exc.InvalidRequestError` [ENGINE]
- `orm.evaluator._ExpiredObject` ──inherits──▶ `sqlalchemy.sql.operators.ColumnOperators` [SQL]
- `orm.evaluator._NoObject` ──inherits──▶ `sqlalchemy.sql.operators.ColumnOperators` [SQL]
- `orm.exc.DetachedInstanceError` ──inherits──▶ `sqlalchemy.exc.SQLAlchemyError` [ENGINE]
- `orm.exc.FlushError` ──inherits──▶ `sqlalchemy.exc.SQLAlchemyError` [ENGINE]
- `orm.exc.LoaderStrategyException` ──inherits──▶ `sqlalchemy.exc.InvalidRequestError` [ENGINE]
- `orm.exc.MappedAnnotationError` ──inherits──▶ `sqlalchemy.exc.ArgumentError` [ENGINE]
- `orm.exc.ObjectDeletedError` ──inherits──▶ `sqlalchemy.exc.InvalidRequestError` [ENGINE]
- `orm.exc.ObjectDereferencedError` ──inherits──▶ `sqlalchemy.exc.SQLAlchemyError` [ENGINE]
- `orm.exc.StaleDataError` ──inherits──▶ `sqlalchemy.exc.SQLAlchemyError` [ENGINE]
- `orm.exc.UnmappedColumnError` ──inherits──▶ `sqlalchemy.exc.InvalidRequestError` [ENGINE]
- `orm.exc.UnmappedError` ──inherits──▶ `sqlalchemy.exc.InvalidRequestError` [ENGINE]
- `orm.instrumentation.ClassManager` ──inherits──▶ `sqlalchemy.event.registry.EventTarget` [ENGINE]
- `orm.instrumentation.ClassManager` ──inherits──▶ `sqlalchemy.util.langhelpers.HasMemoized` [ENGINE]
- `orm.instrumentation.InstrumentationFactory` ──inherits──▶ `sqlalchemy.event.registry.EventTarget` [ENGINE]
- `orm.instrumentation._ExpiredAttributeLoaderProto` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `orm.instrumentation._ManagerFactory` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `orm.interfaces.CompileStateOption` ──inherits──▶ `sqlalchemy.sql.cache_key.HasCacheKey` [SQL]
- `orm.interfaces.MapperProperty` ──inherits──▶ `sqlalchemy.sql.cache_key.HasCacheKey` [SQL]
- `orm.interfaces.ORMColumnDescription` ──inherits──▶ `typing_extensions.TypedDict` typing_extensions
- `orm.interfaces.ORMColumnsClauseRole` ──inherits──▶ `sqlalchemy.sql.roles.ColumnsClauseRole` [SQL]
- `orm.interfaces.ORMFromClauseRole` ──inherits──▶ `sqlalchemy.sql.roles.StrictFromClauseRole` [SQL]
- `orm.interfaces.ORMOption` ──inherits──▶ `sqlalchemy.sql.base.ExecutableOption` [SQL]
- `orm.interfaces.ORMStatementRole` ──inherits──▶ `sqlalchemy.sql.roles.StatementRole` [SQL]
- `orm.interfaces.PropComparator` ──inherits──▶ `sqlalchemy.sql.operators.ColumnOperators` [SQL]
- `orm.mapper.Mapper` ──inherits──▶ `sqlalchemy.event.registry.EventTarget` [ENGINE]
- `orm.mapper.Mapper` ──inherits──▶ `sqlalchemy.log.Identified` [ENGINE]
- `orm.mapper.Mapper` ──inherits──▶ `sqlalchemy.sql.cache_key.MemoizedHasCacheKey` [SQL]
- `orm.path_registry.PathRegistry` ──inherits──▶ `sqlalchemy.sql.cache_key.HasCacheKey` [SQL]
- `orm.path_registry.PathToken` ──inherits──▶ `sqlalchemy.sql.cache_key.HasCacheKey` [SQL]
- `orm.properties.ColumnProperty` ──inherits──▶ `sqlalchemy.log.Identified` [ENGINE]
- `orm.query.Query` ──inherits──▶ `sqlalchemy.event.registry.EventTarget` [ENGINE]
- `orm.query.Query` ──inherits──▶ `sqlalchemy.log.Identified` [ENGINE]
- `orm.query.Query` ──inherits──▶ `sqlalchemy.sql.annotation.SupportsCloneAnnotations` [SQL]
- `orm.query.Query` ──inherits──▶ `sqlalchemy.sql.base.Executable` [SQL]
- `orm.query.Query` ──inherits──▶ `sqlalchemy.sql.base.Generative` [SQL]
- `orm.query.Query` ──inherits──▶ `sqlalchemy.sql.selectable.HasHints` [SQL]
- `orm.query.Query` ──inherits──▶ `sqlalchemy.sql.selectable.HasPrefixes` [SQL]
- `orm.query.Query` ──inherits──▶ `sqlalchemy.sql.selectable.HasSuffixes` [SQL]
- `orm.query.Query` ──inherits──▶ `sqlalchemy.sql.selectable._SelectFromElements` [SQL]
- `orm.relationships.RelationshipProperty` ──inherits──▶ `sqlalchemy.log.Identified` [ENGINE]
- `orm.scoping.QueryPropertyDescriptor` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `orm.session.Session` ──inherits──▶ `sqlalchemy.event.registry.EventTarget` [ENGINE]
- `orm.session.SessionTransaction` ──inherits──▶ `sqlalchemy.engine.util.TransactionalContext` [ENGINE]
- `orm.session._ConnectionCallableProto` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `orm.state._InstanceDictProto` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `orm.strategies.LazyLoader` ──inherits──▶ `sqlalchemy.log.Identified` [ENGINE]
- `orm.strategy_options._AbstractLoad` ──inherits──▶ `sqlalchemy.sql.traversals.GenerativeOnTraversal` [SQL]
- `orm.strategy_options._LoadElement` ──inherits──▶ `sqlalchemy.sql.cache_key.HasCacheKey` [SQL]
- `orm.strategy_options._LoadElement` ──inherits──▶ `sqlalchemy.sql.traversals.HasShallowCopy` [SQL]
- `orm.util.AliasedInsp` ──inherits──▶ `sqlalchemy.sql.cache_key.HasCacheKey` [SQL]
- `orm.util.AliasedInsp` ──inherits──▶ `sqlalchemy.util.langhelpers.MemoizedSlots` [ENGINE]
- `orm.util.Bundle` ──inherits──▶ `sqlalchemy.sql.annotation.SupportsCloneAnnotations` [SQL]
- `orm.util.Bundle` ──inherits──▶ `sqlalchemy.sql.cache_key.MemoizedHasCacheKey` [SQL]
- `orm.util.ORMAdapter` ──inherits──▶ `sqlalchemy.sql.util.ColumnAdapter` [SQL]
- `orm.util.ORMStatementAdapter` ──inherits──▶ `sqlalchemy.sql.util.ColumnAdapter` [SQL]
- `orm.util._DeStringifyAnnotation` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `orm.util._EvalNameOnly` ──inherits──▶ `typing_extensions.Protocol` typing_extensions
- `orm.writeonly.WriteOnlyLoader` ──inherits──▶ `sqlalchemy.log.Identified` [ENGINE]

## Re-walk — generated

```bash
T=tenants/sqlalchemy
python3 -m graphy blast sqlalchemy://func/sqlalchemy.orm.base.instance_state --tenant $T/tenant.json --tenant-id sqlalchemy
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm ORM -->
