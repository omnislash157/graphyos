# DIALECTS — the databases (`sqlalchemy.dialects`)

> Load before touching PostgreSQL, MySQL/MariaDB, SQLite, Oracle or MSSQL specifics: a type, a
> compiler, a reflection query, a driver binding. Hand-cut from the walk's evidence; the crown the
> walk ranks second by fan-out. The re-walk is at the bottom.

## ⚖ The law of this arm
A dialect consumes SQL (the type subclasses, `to_instance`, `quoted_name`) and ENGINE
(`interfaces.Dialect`, `make_url`, `await_only`) and is consumed by nobody inside the package
except the testing harness. Its real joins out are the DBAPI drivers it imports at runtime
(`psycopg2`, `psycopg`, `asyncpg`, `pymysql`, `oracledb`, `cx_Oracle`, `sqlcipher3`, …): the ring
did not carry them, so `ring.json` lists them as unresolved and the walk stops at the boundary —
reported, never guessed.

## The load-bearing symbols (walk-derived)
**`postgresql`** — `ranges.Range` / `AbstractSingleRangeImpl` · `array.ARRAY` / `array` ·
`json.JSON` / `JSONB` · `types.INTERVAL` · `base.PGIdentifierPreparer`.
**`mysql`** — `base.MySQLDialect` · `types._StringType` / `_IntegerType` / `_NumericType` ·
`reflection._pr_compile`.
**`mssql`** — `information_schema.CoerceUnicode`.

## Cross-pillar joins
- → **SQL**: `String`, `Numeric`, `to_instance`, `quoted_name`, `expect`, `select`.
- → **ENGINE**: `interfaces.Dialect`, `make_url`, `await_only`, `NoSuchTableError`.

<!-- graphy:arm DIALECTS generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=3a9f8a3a4b15a939 cut=sha256:5fe44b5a68b5270696a6d629a7b1948137de8baef8cc767efcf102b2fb376aa4 content=sha256:d085e56261d92629562467878a8d87d7448c8e88fc49d0ed423072c1764f3678 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`sqlalchemy.dialects`** — functions: `_auto_fn`
**`sqlalchemy.dialects.mssql.aioodbc`** — classes: `MSDialectAsync_aioodbc` · `MSExecutionContext_aioodbc` (1)
**`sqlalchemy.dialects.mssql.base`** — classes: `BIT` · `DATETIME2` (1) · `DATETIMEOFFSET` (1) · `DOUBLE_PRECISION` (1) · `IMAGE` · `MONEY` · `MSDDLCompiler` (12) · `MSDialect` (28) · `MSExecutionContext` (7) · `MSIdentifierPreparer` (4) · `MSSQLCompiler` (46) · `MSSQLStrictCompiler` (3) · `MSTypeCompiler` (35) · `MSUUid` (2) · `NTEXT` · `REAL` (1) · `ROWVERSION` · `SMALLDATETIME` · `SMALLMONEY` · `SQL_VARIANT` · `TIME` (3) · `TIMESTAMP` (2) · `TINYINT` · `UNIQUEIDENTIFIER` (1) · `VARBINARY` (1) · `XML` · `_BASETIMEIMPL` · `_DateTimeBase` (1) · `_MSDate` (2) · `_MSDateTime` · `_MSUnicode` · `_MSUnicodeText` · `_UnicodeLiteral` (1); functions: `_db_plus_owner` · `_db_plus_owner_listing` · `_owner_plus_db` · `_schema_elements` · `_switch_db`
**`sqlalchemy.dialects.mssql.information_schema`** — classes: `CoerceUnicode` (1) · `NVarcharSqlVariant` (1) · `NumericSqlVariant` (1) · `_cast_on_2005` (1); functions: `_compile`
**`sqlalchemy.dialects.mssql.json`** — classes: `JSON` · `JSONIndexType` (1) · `JSONPathType` (1) · `_FormatTypeMixin` (3)
**`sqlalchemy.dialects.mssql.provision`** — functions: `_mssql_create_db` · `_mssql_drop_db` · `_mssql_drop_ignore` · `_mssql_get_temp_table_name` · `_mssql_temp_table_keyword_args` · `_reap_mssql_dbs` · `drop_all_schema_objects_pre_tables` · `generate_driver_url` · `normalize_sequence` · `post_configure_engine`
**`sqlalchemy.dialects.mssql.pymssql`** — classes: `MSDialect_pymssql` (6) · `MSIdentifierPreparer_pymssql` (1) · `_MSNumeric_pymssql` (1)
**`sqlalchemy.dialects.mssql.pyodbc`** — classes: `MSDialect_pyodbc` (6) · `MSExecutionContext_pyodbc` (2) · `_BINARY_pyodbc` · `_JSONIndexType_pyodbc` (1) · `_JSONPathType_pyodbc` (1) · `_JSON_pyodbc` (1) · `_MSFloat_pyodbc` · `_MSNumeric_pyodbc` · `_ODBCDATETIMEOFFSET` · `_ODBCDateTime` · `_ODBCDateTimeBindProcessor` (1) · `_String_pyodbc` (1) · `_UnicodeText_pyodbc` (1) · `_Unicode_pyodbc` (1) · `_VARBINARY_pyodbc` · `_ms_binary_pyodbc` (1) · `_ms_numeric_pyodbc` (3)
**`sqlalchemy.dialects.mysql.aiomysql`** — classes: `AsyncAdaptFallback_aiomysql_connection` · `AsyncAdapt_aiomysql_connection` (7) · `AsyncAdapt_aiomysql_cursor` (1) · `AsyncAdapt_aiomysql_dbapi` (5) · `AsyncAdapt_aiomysql_ss_cursor` (1) · `MySQLDialect_aiomysql` (7)
**`sqlalchemy.dialects.mysql.asyncmy`** — classes: `AsyncAdaptFallback_asyncmy_connection` · `AsyncAdapt_asyncmy_connection` (9) · `AsyncAdapt_asyncmy_cursor` · `AsyncAdapt_asyncmy_dbapi` (4) · `AsyncAdapt_asyncmy_ss_cursor` (1) · `MySQLDialect_asyncmy` (7)
**`sqlalchemy.dialects.mysql.base`** — classes: `MariaDBIdentifierPreparer` · `MySQLCompiler` (38) · `MySQLDDLCompiler` (11) · `MySQLDialect` (54) · `MySQLExecutionContext` (3) · `MySQLIdentifierPreparer` (2) · `MySQLTypeCompiler` (40) · `_DecodingRow` (3)
**`sqlalchemy.dialects.mysql.cymysql`** — classes: `MySQLDialect_cymysql` (4) · `_cymysqlBIT` (1)
**`sqlalchemy.dialects.mysql.dml`** — classes: `Insert` (3) · `OnDuplicateClause` (1); functions: `insert`
**`sqlalchemy.dialects.mysql.enumerated`** — classes: `ENUM` (4) · `SET` (6)
**`sqlalchemy.dialects.mysql.expression`** — classes: `match` (4)
**`sqlalchemy.dialects.mysql.json`** — classes: `JSON` · `JSONIndexType` (1) · `JSONPathType` (1) · `_FormatTypeMixin` (3)
**`sqlalchemy.dialects.mysql.mariadb`** — classes: `INET4` · `INET6` · `MariaDBDialect` · `MariaDBTypeCompiler` (2); functions: `loader`
**`sqlalchemy.dialects.mysql.mariadbconnector`** — classes: `MySQLCompiler_mariadbconnector` · `MySQLDialect_mariadbconnector` (14) · `MySQLExecutionContext_mariadbconnector` (4) · `_MariaDBUUID` (1)
**`sqlalchemy.dialects.mysql.mysqlconnector`** — classes: `IdentifierPreparerCommon_mysqlconnector` (2) · `MariaDBDialect_mysqlconnector` · `MariaDBIdentifierPreparer_mysqlconnector` · `MySQLCompiler_mysqlconnector` (1) · `MySQLDialect_mysqlconnector` (12) · `MySQLExecutionContext_mysqlconnector` (2) · `MySQLIdentifierPreparer_mysqlconnector` · `_myconnpyBIT` (1)
**`sqlalchemy.dialects.mysql.mysqldb`** — classes: `MySQLCompiler_mysqldb` · `MySQLDialect_mysqldb` (14) · `MySQLExecutionContext_mysqldb`
**`sqlalchemy.dialects.mysql.provision`** — functions: `_allow_stale_update_impl` · `_delete_from_all_tables` · `_mysql_configure_follower` · `_mysql_create_db` · `_mysql_drop_db` · `_mysql_temp_table_keyword_args` · `_upsert` · `generate_driver_url`
**`sqlalchemy.dialects.mysql.pymysql`** — classes: `MySQLDialect_pymysql` (7); functions: `_connection_ping_reconnects_true`
**`sqlalchemy.dialects.mysql.pyodbc`** — classes: `MySQLDialect_pyodbc` (4) · `MySQLExecutionContext_pyodbc` (1) · `_pyodbcTIME` (1)
**`sqlalchemy.dialects.mysql.reflection`** — classes: `MySQLTableDefinitionParser` (15) · `ReflectedState` (1); functions: `_pr_compile` · `_re_compile` · `_strip_values` · `cleanup_text`
**`sqlalchemy.dialects.mysql.types`** — classes: `BIGINT` (1) · `BIT` (2) · `CHAR` (2) · `DATETIME` (1) · `DECIMAL` (1) · `DOUBLE` (1) · `FLOAT` (2) · `INTEGER` (1) · `LONGBLOB` · `LONGTEXT` (1) · `MEDIUMBLOB` · `MEDIUMINT` (1) · `MEDIUMTEXT` (1) · `NCHAR` (1) · `NUMERIC` (1) · `NVARCHAR` (1) · `REAL` (1) · `SMALLINT` (1) · `TEXT` (1) · `TIME` (2) · `TIMESTAMP` (1) · `TINYBLOB` · `TINYINT` (2) · `TINYTEXT` (1) · `VARCHAR` (1) · `YEAR` (1) · `_FloatType` (2) · `_IntegerType` (2) · `_MatchType` (1) · `_NumericType` (2) · `_StringType` (2)
**`sqlalchemy.dialects.oracle.base`** — classes: `OracleCompiler` (39) · `OracleDDLCompiler` (8) · `OracleDialect` (59) · `OracleExecutionContext` (2) · `OracleIdentifierPreparer` (2) · `OracleTypeCompiler` (26) · `_OuterJoinColumn` (1)
**`sqlalchemy.dialects.oracle.cx_oracle`** — classes: `OracleCompiler_cx_oracle` (1) · `OracleDialect_cx_oracle` (23) · `OracleExecutionContext_cx_oracle` (8) · `_CXOracleDate` (2) · `_CXOracleTIMESTAMP` (1) · `_LOBDataType` · `_OracleBINARY_DOUBLE` · `_OracleBINARY_FLOAT` · `_OracleBinary` (3) · `_OracleBinaryFloat` (1) · `_OracleChar` (1) · `_OracleEnum` (1) · `_OracleInteger` (3) · `_OracleInterval` (1) · `_OracleLong` (1) · `_OracleNChar` (1) · `_OracleNUMBER` · `_OracleNumeric` (3) · `_OracleRaw` · `_OracleRowid` (1) · `_OracleString` · `_OracleText` (1) · `_OracleUUID` (1) · `_OracleUnicodeStringCHAR` (1) · `_OracleUnicodeStringNCHAR` (1) · `_OracleUnicodeTextCLOB` (1) · `_OracleUnicodeTextNCLOB` (1)
**`sqlalchemy.dialects.oracle.oracledb`** — classes: `AsyncAdaptFallback_oracledb_connection` · `AsyncAdapt_oracledb_connection` (13) · `AsyncAdapt_oracledb_cursor` (8) · `AsyncAdapt_oracledb_ss_cursor` (1) · `OracleDialectAsync_oracledb` (3) · `OracleDialect_oracledb` (11) · `OracleExecutionContextAsync_oracledb` (2) · `OracleExecutionContext_oracledb` · `OracledbAdaptDBAPI` (2)
**`sqlalchemy.dialects.oracle.provision`** — functions: `_connect_with_retry` · `_ora_drop_all_schema_objects_post_tables` · `_ora_drop_all_schema_objects_pre_tables` · `_ora_drop_ignore` · `_ora_stop_test_class_outside_fixtures` · `_oracle_configure_follower` · `_oracle_create_db` · `_oracle_drop_db` · `_oracle_follower_url_from_main` · `_oracle_generate_driver_url` · `_oracle_is_preferred_driver` · `_oracle_post_configure_engine` · `_oracle_post_configure_testing_engine` · `_oracle_set_default_schema_on_connection` · `_oracle_temp_table_keyword_args` · `_purge_recyclebin` · `_reap_oracle_dbs` · `_update_db_opts`
**`sqlalchemy.dialects.oracle.types`** — classes: `BFILE` · `BINARY_DOUBLE` · `BINARY_FLOAT` · `DATE` (2) · `FLOAT` (1) · `INTERVAL` (7) · `LONG` · `NCLOB` · `NUMBER` (3) · `RAW` · `ROWID` · `TIMESTAMP` (1) · `VARCHAR2` · `_OracleBoolean` (1) · `_OracleDate` (1) · `_OracleDateLiteralRender` (2)
**`sqlalchemy.dialects.oracle.vector`** — classes: `SparseVector` (2) · `VECTOR` (4) · `comparator_factory` (3) · `VectorDistanceType` · `VectorIndexConfig` (1) · `VectorIndexType` · `VectorStorageFormat` · `VectorStorageType`
**`sqlalchemy.dialects.postgresql._psycopg_common`** — classes: `_PGDialect_common_psycopg` (15) · `_PGExecutionContext_common_psycopg` (1) · `_PsycopgARRAY` · `_PsycopgFloat` · `_PsycopgHStore` (2) · `_PsycopgINT2VECTOR` · `_PsycopgNumeric` (2) · `_PsycopgOIDVECTOR`
**`sqlalchemy.dialects.postgresql.array`** — classes: `ARRAY` (5) · `Comparator` (3) · `array` (4); functions: `All` · `Any` · `_split_enum_values`
**`sqlalchemy.dialects.postgresql.asyncpg`** — classes: `AsyncAdaptFallback_asyncpg_connection` · `AsyncAdapt_asyncpg_connection` (19) · `AsyncAdapt_asyncpg_cursor` (13) · `AsyncAdapt_asyncpg_dbapi` (4) · `DataError` · `DatabaseError` · `Error` · `IntegrityError` · `InterfaceError` · `InternalClientError` · `InternalError` · `InternalServerError` · `InvalidCachedStatementError` (1) · `NotSupportedError` · `OperationalError` · `ProgrammingError` · `Warning` · `AsyncAdapt_asyncpg_ss_cursor` (10) · `AsyncPgEnum` · `AsyncPgInterval` (1) · `AsyncpgARRAY` · `AsyncpgBigInteger` · `AsyncpgBit` · `AsyncpgBoolean` · `AsyncpgByteA` · `AsyncpgCHAR` · `AsyncpgDate` · `AsyncpgDateTime` · `AsyncpgFloat` · `AsyncpgInteger` · `AsyncpgJSON` (1) · `AsyncpgJSONB` (1) · `AsyncpgJSONIndexType` · `AsyncpgJSONIntIndexType` · `AsyncpgJSONPathType` (1) · `AsyncpgJSONStrIndexType` · `AsyncpgNumeric` (2) · `AsyncpgOID` · `AsyncpgREGCLASS` · `AsyncpgREGCONFIG` · `AsyncpgSmallInteger` · `AsyncpgString` · `AsyncpgTime` · `PGCompiler_asyncpg` · `PGDialect_asyncpg` (21) · `PGExecutionContext_asyncpg` (3) · `PGIdentifierPreparer_asyncpg` · `_AsyncpgMultiRange` (2) · `_AsyncpgRange` (2)
**`sqlalchemy.dialects.postgresql.base`** — classes: `PGCompiler` (38) · `PGDDLCompiler` (23) · `PGDeferrableConnectionCharacteristic` (3) · `PGDialect` (71) · `PGExecutionContext` (2) · `PGIdentifierPreparer` (3) · `PGInspector` (5) · `PGReadOnlyConnectionCharacteristic` (3) · `PGTypeCompiler` (46) · `ReflectedDomain` · `ReflectedDomainConstraint` · `ReflectedEnum` · `ReflectedNamedType` · `_CompilerSequence` (1)
**`sqlalchemy.dialects.postgresql.dml`** — classes: `Insert` (3) · `OnConflictClause` (1) · `OnConflictDoNothing` · `OnConflictDoUpdate` (1); functions: `insert`
**`sqlalchemy.dialects.postgresql.ext`** — classes: `ExcludeConstraint` (3) · `_regconfig_fn` (1) · `aggregate_order_by` (5) · `phraseto_tsquery` · `plainto_tsquery` · `to_tsquery` · `to_tsvector` · `ts_headline` (1) · `websearch_to_tsquery`; functions: `array_agg`
**`sqlalchemy.dialects.postgresql.hstore`** — classes: `HSTORE` (3) · `Comparator` (13) · `_HStoreArrayFunction` · `_HStoreDefinedFunction` · `_HStoreDeleteFunction` · `_HStoreKeysFunction` · `_HStoreMatrixFunction` · `_HStoreSliceFunction` · `_HStoreValsFunction` · `hstore`; functions: `_parse_error` · `_parse_hstore` · `_serialize_hstore`
**`sqlalchemy.dialects.postgresql.json`** — classes: `JSON` (1) · `Comparator` (1) · `JSONB` (1) · `Comparator` (8) · `JSONPATH` · `JSONPathType` (3)
**`sqlalchemy.dialects.postgresql.named_types`** — classes: `CreateDomainType` · `CreateEnumType` · `DOMAIN` (2) · `DomainDropper` (1) · `DomainGenerator` (1) · `DropDomainType` · `DropEnumType` · `ENUM` (7) · `EnumDropper` (1) · `EnumGenerator` (1) · `NamedType` (7) · `NamedTypeDropper` (2) · `NamedTypeGenerator` (2)
**`sqlalchemy.dialects.postgresql.pg8000`** — classes: `PGCompiler_pg8000` (1) · `PGDialect_pg8000` (20) · `PGExecutionContext_pg8000` (2) · `PGIdentifierPreparer_pg8000` (1) · `ServerSideCursor` (12) · `_PGARRAY` · `_PGBigInteger` · `_PGBoolean` · `_PGDate` · `_PGEnum` (1) · `_PGFloat` · `_PGInteger` · `_PGInterval` (2) · `_PGJSON` (1) · `_PGJSONB` (1) · `_PGJSONIndexType` (1) · `_PGJSONIntIndexType` · `_PGJSONPathType` · `_PGJSONStrIndexType` · `_PGNullType` · `_PGNumeric` (1) · `_PGNumericNoBind` (1) · `_PGOIDVECTOR` · `_PGSmallInteger` · `_PGString` · `_PGTime` · `_PGTimeStamp` · `_Pg8000MultiRange` (2) · `_Pg8000Range` (2)
**`sqlalchemy.dialects.postgresql.pg_catalog`** — classes: `INT2VECTOR` · `NAME` · `OIDVECTOR` · `PG_NODE_TREE` · `_SpaceVector` (1)
**`sqlalchemy.dialects.postgresql.provision`** — functions: `_create_citext_extension` · `_pg_create_db` · `_pg_drop_db` · `_postgresql_set_default_schema_on_connection` · `_postgresql_temp_table_keyword_args` · `_upsert` · `drop_all_schema_objects_post_tables` · `drop_all_schema_objects_pre_tables` · `prepare_for_drop_tables`
**`sqlalchemy.dialects.postgresql.psycopg`** — classes: `AsyncAdaptFallback_psycopg_connection` · `AsyncAdapt_psycopg_connection` (17) · `AsyncAdapt_psycopg_cursor` (11) · `AsyncAdapt_psycopg_ss_cursor` (6) · `PGCompiler_psycopg` · `PGDialectAsync_psycopg` (8) · `PGDialect_psycopg` (21) · `PGExecutionContext_psycopg` · `PGIdentifierPreparer_psycopg` · `PsycopgAdaptDBAPI` (2) · `_PGBigInteger` · `_PGBoolean` · `_PGDate` · `_PGInteger` · `_PGInterval` · `_PGJSON` (2) · `_PGJSONB` (2) · `_PGJSONIntIndexType` · `_PGJSONPathType` · `_PGJSONStrIndexType` · `_PGNullType` · `_PGREGCONFIG` · `_PGSmallInteger` · `_PGString` · `_PGTime` · `_PGTimeStamp` · `_PsycopgMultiRange` (2) · `_PsycopgRange` (2); functions: `_log_notices`
**`sqlalchemy.dialects.postgresql.psycopg2`** — classes: `ExecutemanyMode` · `PGDialect_psycopg2` (17) · `PGExecutionContext_psycopg2` (2) · `PGIdentifierPreparer_psycopg2` · `_PGJSON` (1) · `_PGJSONB` (1) · `_Psycopg2DateRange` · `_Psycopg2DateTimeRange` · `_Psycopg2DateTimeTZRange` · `_Psycopg2NumericRange` · `_Psycopg2Range` (2)
**`sqlalchemy.dialects.postgresql.psycopg2cffi`** — classes: `PGDialect_psycopg2cffi` (3)
**`sqlalchemy.dialects.postgresql.ranges`** — classes: `AbstractMultiRange` (1) · `AbstractMultiRangeImpl` · `AbstractRange` (1) · `comparator_factory` (11) · `AbstractSingleRange` (1) · `AbstractSingleRangeImpl` · `DATEMULTIRANGE` · `DATERANGE` · `INT4MULTIRANGE` · `INT4RANGE` · `INT8MULTIRANGE` · `INT8RANGE` · `MultiRange` (1) · `NUMMULTIRANGE` · `NUMRANGE` · `Range` (30) · `TSMULTIRANGE` · `TSRANGE` · `TSTZMULTIRANGE` · `TSTZRANGE`; functions: `_is_int32`
**`sqlalchemy.dialects.postgresql.types`** — classes: `BIT` (1) · `BYTEA` · `CIDR` · `CITEXT` (1) · `INET` · `INTERVAL` (6) · `MACADDR` · `MACADDR8` · `MONEY` · `OID` · `PGUuid` (1) · `REGCLASS` · `REGCONFIG` · `TIME` (1) · `TIMESTAMP` (1) · `TSQUERY` · `TSVECTOR` · `_NetworkAddressTypeMixin` (1)
**`sqlalchemy.dialects.sqlite.aiosqlite`** — classes: `AsyncAdaptFallback_aiosqlite_connection` · `AsyncAdapt_aiosqlite_connection` (11) · `AsyncAdapt_aiosqlite_cursor` (10) · `AsyncAdapt_aiosqlite_dbapi` (3) · `AsyncAdapt_aiosqlite_ss_cursor` (5) · `SQLiteDialect_aiosqlite` (6) · `SQLiteExecutionContext_aiosqlite` (1)
**`sqlalchemy.dialects.sqlite.base`** — classes: `DATE` (2) · `DATETIME` (3) · `SQLiteCompiler` (25) · `SQLiteDDLCompiler` (9) · `SQLiteDialect` (26) · `SQLiteExecutionContext` (2) · `SQLiteIdentifierPreparer` · `SQLiteTypeCompiler` (5) · `TIME` (3) · `_DateTimeMixin` (4) · `_SQliteJson` (1)
**`sqlalchemy.dialects.sqlite.dml`** — classes: `Insert` (3) · `OnConflictClause` (1) · `OnConflictDoNothing` · `OnConflictDoUpdate` (1); functions: `insert`
**`sqlalchemy.dialects.sqlite.json`** — classes: `JSON` · `JSONIndexType` (1) · `JSONPathType` (1) · `_FormatTypeMixin` (3)
**`sqlalchemy.dialects.sqlite.provision`** — functions: `_drop_dbs_w_ident` · `_format_url` · `_reap_sqlite_dbs` · `_sqlite_create_db` · `_sqlite_drop_db` · `_sqlite_follower_url_from_main` · `_sqlite_post_configure_engine` · `_sqlite_post_configure_testing_engine` · `_sqlite_temp_table_keyword_args` · `_upsert` · `generate_driver_url` · `stop_test_class_outside_fixtures`
**`sqlalchemy.dialects.sqlite.pysqlcipher`** — classes: `SQLiteDialect_pysqlcipher` (4)
**`sqlalchemy.dialects.sqlite.pysqlite`** — classes: `SQLiteDialect_pysqlite` (9) · `_SQLiteDialect_pysqlite_dollar` (1) · `_SQLiteDialect_pysqlite_numeric` (3) · `_SQLite_pysqliteDate` (2) · `_SQLite_pysqliteTimeStamp` (2)

## The inherits joins out — generated

- `dialects.mssql.aioodbc.MSDialectAsync_aioodbc` ──inherits──▶ `sqlalchemy.connectors.aioodbc.aiodbcConnector` [ENGINE]
- `dialects.mssql.base.BIT` ──inherits──▶ `sqlalchemy.sql.sqltypes.Boolean` [SQL]
- `dialects.mssql.base.DATETIME2` ──inherits──▶ `sqlalchemy.sql.sqltypes.DateTime` [SQL]
- `dialects.mssql.base.DATETIMEOFFSET` ──inherits──▶ `sqlalchemy.sql.sqltypes.DateTime` [SQL]
- `dialects.mssql.base.DOUBLE_PRECISION` ──inherits──▶ `sqlalchemy.sql.sqltypes.DOUBLE_PRECISION` [SQL]
- `dialects.mssql.base.IMAGE` ──inherits──▶ `sqlalchemy.sql.sqltypes.LargeBinary` [SQL]
- `dialects.mssql.base.MSDDLCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.DDLCompiler` [SQL]
- `dialects.mssql.base.MSDialect` ──inherits──▶ `sqlalchemy.engine.default.DefaultDialect` [ENGINE]
- `dialects.mssql.base.MSExecutionContext` ──inherits──▶ `sqlalchemy.engine.default.DefaultExecutionContext` [ENGINE]
- `dialects.mssql.base.MSIdentifierPreparer` ──inherits──▶ `sqlalchemy.sql.compiler.IdentifierPreparer` [SQL]
- `dialects.mssql.base.MSSQLCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.SQLCompiler` [SQL]
- `dialects.mssql.base.MSTypeCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.GenericTypeCompiler` [SQL]
- `dialects.mssql.base.MSUUid` ──inherits──▶ `sqlalchemy.sql.sqltypes.Uuid` [SQL]
- `dialects.mssql.base.NTEXT` ──inherits──▶ `sqlalchemy.sql.sqltypes.UnicodeText` [SQL]
- `dialects.mssql.base.REAL` ──inherits──▶ `sqlalchemy.sql.sqltypes.REAL` [SQL]
- `dialects.mssql.base.SMALLDATETIME` ──inherits──▶ `sqlalchemy.sql.sqltypes.DateTime` [SQL]
- `dialects.mssql.base.TIME` ──inherits──▶ `sqlalchemy.sql.sqltypes.TIME` [SQL]
- `dialects.mssql.base.TIMESTAMP` ──inherits──▶ `sqlalchemy.sql.sqltypes._Binary` [SQL]
- `dialects.mssql.base.TINYINT` ──inherits──▶ `sqlalchemy.sql.sqltypes.Integer` [SQL]
- `dialects.mssql.base.VARBINARY` ──inherits──▶ `sqlalchemy.sql.sqltypes.LargeBinary` [SQL]
- `dialects.mssql.base.VARBINARY` ──inherits──▶ `sqlalchemy.sql.sqltypes.VARBINARY` [SQL]
- `dialects.mssql.base.XML` ──inherits──▶ `sqlalchemy.sql.sqltypes.Text` [SQL]
- `dialects.mssql.base._MSDate` ──inherits──▶ `sqlalchemy.sql.sqltypes.Date` [SQL]
- `dialects.mssql.base._MSDateTime` ──inherits──▶ `sqlalchemy.sql.sqltypes.DateTime` [SQL]
- `dialects.mssql.base._MSUnicode` ──inherits──▶ `sqlalchemy.sql.sqltypes.Unicode` [SQL]
- `dialects.mssql.base._MSUnicodeText` ──inherits──▶ `sqlalchemy.sql.sqltypes.UnicodeText` [SQL]
- `dialects.mssql.information_schema.CoerceUnicode` ──inherits──▶ `sqlalchemy.sql.type_api.TypeDecorator` [SQL]
- `dialects.mssql.information_schema.NVarcharSqlVariant` ──inherits──▶ `sqlalchemy.sql.type_api.TypeDecorator` [SQL]
- `dialects.mssql.information_schema.NumericSqlVariant` ──inherits──▶ `sqlalchemy.sql.type_api.TypeDecorator` [SQL]
- `dialects.mssql.pyodbc.MSDialect_pyodbc` ──inherits──▶ `sqlalchemy.connectors.pyodbc.PyODBCConnector` [ENGINE]
- `dialects.mssql.pyodbc._BINARY_pyodbc` ──inherits──▶ `sqlalchemy.sql.sqltypes.BINARY` [SQL]
- `dialects.mysql.aiomysql.AsyncAdapt_aiomysql_connection` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_dbapi_connection` [ENGINE]
- `dialects.mysql.aiomysql.AsyncAdapt_aiomysql_connection` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_terminate` [ENGINE]
- `dialects.mysql.aiomysql.AsyncAdapt_aiomysql_cursor` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_dbapi_cursor` [ENGINE]
- `dialects.mysql.aiomysql.AsyncAdapt_aiomysql_dbapi` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_dbapi_module` [ENGINE]
- `dialects.mysql.aiomysql.AsyncAdapt_aiomysql_ss_cursor` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_dbapi_ss_cursor` [ENGINE]
- `dialects.mysql.asyncmy.AsyncAdapt_asyncmy_connection` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_dbapi_connection` [ENGINE]
- `dialects.mysql.asyncmy.AsyncAdapt_asyncmy_connection` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_terminate` [ENGINE]
- `dialects.mysql.asyncmy.AsyncAdapt_asyncmy_cursor` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_dbapi_cursor` [ENGINE]
- `dialects.mysql.asyncmy.AsyncAdapt_asyncmy_dbapi` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_dbapi_module` [ENGINE]
- `dialects.mysql.asyncmy.AsyncAdapt_asyncmy_ss_cursor` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_dbapi_ss_cursor` [ENGINE]
- `dialects.mysql.base.MySQLCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.SQLCompiler` [SQL]
- `dialects.mysql.base.MySQLDDLCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.DDLCompiler` [SQL]
- `dialects.mysql.base.MySQLDialect` ──inherits──▶ `sqlalchemy.engine.default.DefaultDialect` [ENGINE]
- `dialects.mysql.base.MySQLExecutionContext` ──inherits──▶ `sqlalchemy.engine.default.DefaultExecutionContext` [ENGINE]
- `dialects.mysql.base.MySQLIdentifierPreparer` ──inherits──▶ `sqlalchemy.sql.compiler.IdentifierPreparer` [SQL]
- `dialects.mysql.base.MySQLTypeCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.GenericTypeCompiler` [SQL]
- `dialects.mysql.dml.Insert` ──inherits──▶ `sqlalchemy.sql.dml.Insert` [SQL]
- `dialects.mysql.dml.OnDuplicateClause` ──inherits──▶ `sqlalchemy.sql.elements.ClauseElement` [SQL]
- `dialects.mysql.enumerated.ENUM` ──inherits──▶ `sqlalchemy.sql.sqltypes.Enum` [SQL]
- `dialects.mysql.enumerated.ENUM` ──inherits──▶ `sqlalchemy.sql.type_api.NativeForEmulated` [SQL]
- `dialects.mysql.expression.match` ──inherits──▶ `sqlalchemy.sql.base.Generative` [SQL]
- `dialects.mysql.pyodbc.MySQLDialect_pyodbc` ──inherits──▶ `sqlalchemy.connectors.pyodbc.PyODBCConnector` [ENGINE]
- `dialects.mysql.types.BIGINT` ──inherits──▶ `sqlalchemy.sql.sqltypes.BIGINT` [SQL]
- `dialects.mysql.types.CHAR` ──inherits──▶ `sqlalchemy.sql.sqltypes.CHAR` [SQL]
- `dialects.mysql.types.DATETIME` ──inherits──▶ `sqlalchemy.sql.sqltypes.DATETIME` [SQL]
- `dialects.mysql.types.INTEGER` ──inherits──▶ `sqlalchemy.sql.sqltypes.INTEGER` [SQL]
- `dialects.mysql.types.LONGBLOB` ──inherits──▶ `sqlalchemy.sql.sqltypes._Binary` [SQL]
- `dialects.mysql.types.MEDIUMBLOB` ──inherits──▶ `sqlalchemy.sql.sqltypes._Binary` [SQL]
- `dialects.mysql.types.NCHAR` ──inherits──▶ `sqlalchemy.sql.sqltypes.NCHAR` [SQL]
- `dialects.mysql.types.NVARCHAR` ──inherits──▶ `sqlalchemy.sql.sqltypes.NVARCHAR` [SQL]
- `dialects.mysql.types.SMALLINT` ──inherits──▶ `sqlalchemy.sql.sqltypes.SMALLINT` [SQL]
- `dialects.mysql.types.TEXT` ──inherits──▶ `sqlalchemy.sql.sqltypes.TEXT` [SQL]
- `dialects.mysql.types.TIME` ──inherits──▶ `sqlalchemy.sql.sqltypes.TIME` [SQL]
- `dialects.mysql.types.TIMESTAMP` ──inherits──▶ `sqlalchemy.sql.sqltypes.TIMESTAMP` [SQL]
- `dialects.mysql.types.TINYBLOB` ──inherits──▶ `sqlalchemy.sql.sqltypes._Binary` [SQL]
- `dialects.mysql.types.VARCHAR` ──inherits──▶ `sqlalchemy.sql.sqltypes.VARCHAR` [SQL]
- `dialects.mysql.types._IntegerType` ──inherits──▶ `sqlalchemy.sql.sqltypes.Integer` [SQL]
- `dialects.mysql.types._MatchType` ──inherits──▶ `sqlalchemy.sql.sqltypes.MatchType` [SQL]
- `dialects.mysql.types._StringType` ──inherits──▶ `sqlalchemy.sql.sqltypes.String` [SQL]
- `dialects.oracle.base.OracleCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.SQLCompiler` [SQL]
- `dialects.oracle.base.OracleDDLCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.DDLCompiler` [SQL]
- `dialects.oracle.base.OracleDialect` ──inherits──▶ `sqlalchemy.engine.default.DefaultDialect` [ENGINE]
- `dialects.oracle.base.OracleExecutionContext` ──inherits──▶ `sqlalchemy.engine.default.DefaultExecutionContext` [ENGINE]
- `dialects.oracle.base.OracleIdentifierPreparer` ──inherits──▶ `sqlalchemy.sql.compiler.IdentifierPreparer` [SQL]
- `dialects.oracle.base.OracleTypeCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.GenericTypeCompiler` [SQL]
- `dialects.oracle.cx_oracle._CXOracleTIMESTAMP` ──inherits──▶ `sqlalchemy.sql.sqltypes.TIMESTAMP` [SQL]
- `dialects.oracle.cx_oracle._OracleBinary` ──inherits──▶ `sqlalchemy.sql.sqltypes.LargeBinary` [SQL]
- `dialects.oracle.cx_oracle._OracleChar` ──inherits──▶ `sqlalchemy.sql.sqltypes.CHAR` [SQL]
- `dialects.oracle.cx_oracle._OracleEnum` ──inherits──▶ `sqlalchemy.sql.sqltypes.Enum` [SQL]
- `dialects.oracle.cx_oracle._OracleInteger` ──inherits──▶ `sqlalchemy.sql.sqltypes.Integer` [SQL]
- `dialects.oracle.cx_oracle._OracleNChar` ──inherits──▶ `sqlalchemy.sql.sqltypes.NCHAR` [SQL]
- `dialects.oracle.cx_oracle._OracleNumeric` ──inherits──▶ `sqlalchemy.sql.sqltypes.Numeric` [SQL]
- `dialects.oracle.cx_oracle._OracleString` ──inherits──▶ `sqlalchemy.sql.sqltypes.String` [SQL]
- `dialects.oracle.cx_oracle._OracleText` ──inherits──▶ `sqlalchemy.sql.sqltypes.Text` [SQL]
- `dialects.oracle.cx_oracle._OracleUUID` ──inherits──▶ `sqlalchemy.sql.sqltypes.Uuid` [SQL]
- `dialects.oracle.cx_oracle._OracleUnicodeStringCHAR` ──inherits──▶ `sqlalchemy.sql.sqltypes.Unicode` [SQL]
- `dialects.oracle.cx_oracle._OracleUnicodeTextCLOB` ──inherits──▶ `sqlalchemy.sql.sqltypes.UnicodeText` [SQL]
- `dialects.oracle.oracledb.AsyncAdaptFallback_oracledb_connection` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdaptFallback_dbapi_connection` [ENGINE]
- `dialects.oracle.oracledb.AsyncAdapt_oracledb_connection` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_dbapi_connection` [ENGINE]
- `dialects.oracle.oracledb.AsyncAdapt_oracledb_cursor` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_dbapi_cursor` [ENGINE]
- `dialects.oracle.oracledb.AsyncAdapt_oracledb_ss_cursor` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_dbapi_ss_cursor` [ENGINE]
- `dialects.oracle.types.BFILE` ──inherits──▶ `sqlalchemy.sql.sqltypes.LargeBinary` [SQL]
- `dialects.oracle.types.BINARY_DOUBLE` ──inherits──▶ `sqlalchemy.sql.sqltypes.Double` [SQL]
- `dialects.oracle.types.BINARY_FLOAT` ──inherits──▶ `sqlalchemy.sql.sqltypes.Float` [SQL]
- `dialects.oracle.types.DATE` ──inherits──▶ `sqlalchemy.sql.sqltypes.DateTime` [SQL]
- `dialects.oracle.types.FLOAT` ──inherits──▶ `sqlalchemy.sql.sqltypes.FLOAT` [SQL]
- `dialects.oracle.types.INTERVAL` ──inherits──▶ `sqlalchemy.sql.sqltypes._AbstractInterval` [SQL]
- `dialects.oracle.types.LONG` ──inherits──▶ `sqlalchemy.sql.sqltypes.Text` [SQL]
- `dialects.oracle.types.NCLOB` ──inherits──▶ `sqlalchemy.sql.sqltypes.Text` [SQL]
- `dialects.oracle.types.NUMBER` ──inherits──▶ `sqlalchemy.sql.sqltypes.Integer` [SQL]
- `dialects.oracle.types.NUMBER` ──inherits──▶ `sqlalchemy.sql.sqltypes.Numeric` [SQL]
- `dialects.oracle.types.RAW` ──inherits──▶ `sqlalchemy.sql.sqltypes._Binary` [SQL]
- `dialects.oracle.types.TIMESTAMP` ──inherits──▶ `sqlalchemy.sql.sqltypes.TIMESTAMP` [SQL]
- `dialects.oracle.types.VARCHAR2` ──inherits──▶ `sqlalchemy.sql.sqltypes.VARCHAR` [SQL]
- `dialects.oracle.types._OracleBoolean` ──inherits──▶ `sqlalchemy.sql.sqltypes.Boolean` [SQL]
- `dialects.oracle.types._OracleDate` ──inherits──▶ `sqlalchemy.sql.sqltypes.Date` [SQL]
- `dialects.postgresql.asyncpg.AsyncAdapt_asyncpg_connection` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_terminate` [ENGINE]
- `dialects.postgresql.asyncpg.AsyncAdapt_asyncpg_connection` ──inherits──▶ `sqlalchemy.engine.interfaces.AdaptedConnection` [ENGINE]
- `dialects.postgresql.asyncpg.AsyncpgBigInteger` ──inherits──▶ `sqlalchemy.sql.sqltypes.BigInteger` [SQL]
- `dialects.postgresql.asyncpg.AsyncpgBoolean` ──inherits──▶ `sqlalchemy.sql.sqltypes.Boolean` [SQL]
- `dialects.postgresql.asyncpg.AsyncpgCHAR` ──inherits──▶ `sqlalchemy.sql.sqltypes.CHAR` [SQL]
- `dialects.postgresql.asyncpg.AsyncpgDate` ──inherits──▶ `sqlalchemy.sql.sqltypes.Date` [SQL]
- `dialects.postgresql.asyncpg.AsyncpgDateTime` ──inherits──▶ `sqlalchemy.sql.sqltypes.DateTime` [SQL]
- `dialects.postgresql.asyncpg.AsyncpgFloat` ──inherits──▶ `sqlalchemy.sql.sqltypes.Float` [SQL]
- `dialects.postgresql.asyncpg.AsyncpgInteger` ──inherits──▶ `sqlalchemy.sql.sqltypes.Integer` [SQL]
- `dialects.postgresql.asyncpg.AsyncpgJSONIndexType` ──inherits──▶ `sqlalchemy.sql.sqltypes.JSON.JSONIndexType` [SQL]
- `dialects.postgresql.asyncpg.AsyncpgJSONIntIndexType` ──inherits──▶ `sqlalchemy.sql.sqltypes.JSON.JSONIntIndexType` [SQL]
- `dialects.postgresql.asyncpg.AsyncpgJSONStrIndexType` ──inherits──▶ `sqlalchemy.sql.sqltypes.JSON.JSONStrIndexType` [SQL]
- `dialects.postgresql.asyncpg.AsyncpgNumeric` ──inherits──▶ `sqlalchemy.sql.sqltypes.Numeric` [SQL]
- `dialects.postgresql.asyncpg.AsyncpgSmallInteger` ──inherits──▶ `sqlalchemy.sql.sqltypes.SmallInteger` [SQL]
- `dialects.postgresql.asyncpg.AsyncpgString` ──inherits──▶ `sqlalchemy.sql.sqltypes.String` [SQL]
- `dialects.postgresql.asyncpg.AsyncpgTime` ──inherits──▶ `sqlalchemy.sql.sqltypes.Time` [SQL]
- `dialects.postgresql.base.PGCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.SQLCompiler` [SQL]
- `dialects.postgresql.base.PGDDLCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.DDLCompiler` [SQL]
- `dialects.postgresql.base.PGDeferrableConnectionCharacteristic` ──inherits──▶ `sqlalchemy.engine.characteristics.ConnectionCharacteristic` [ENGINE]
- `dialects.postgresql.base.PGDialect` ──inherits──▶ `sqlalchemy.engine.default.DefaultDialect` [ENGINE]
- `dialects.postgresql.base.PGExecutionContext` ──inherits──▶ `sqlalchemy.engine.default.DefaultExecutionContext` [ENGINE]
- `dialects.postgresql.base.PGIdentifierPreparer` ──inherits──▶ `sqlalchemy.sql.compiler.IdentifierPreparer` [SQL]
- `dialects.postgresql.base.PGInspector` ──inherits──▶ `sqlalchemy.engine.reflection.Inspector` [ENGINE]
- `dialects.postgresql.base.PGReadOnlyConnectionCharacteristic` ──inherits──▶ `sqlalchemy.engine.characteristics.ConnectionCharacteristic` [ENGINE]
- `dialects.postgresql.base.PGTypeCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.GenericTypeCompiler` [SQL]
- `dialects.postgresql.base.ReflectedDomainConstraint` ──inherits──▶ `typing_extensions.TypedDict` typing_extensions
- `dialects.postgresql.base.ReflectedNamedType` ──inherits──▶ `typing_extensions.TypedDict` typing_extensions
- `dialects.postgresql.dml.Insert` ──inherits──▶ `sqlalchemy.sql.dml.Insert` [SQL]
- `dialects.postgresql.dml.OnConflictClause` ──inherits──▶ `sqlalchemy.sql.elements.ClauseElement` [SQL]
- `dialects.postgresql.ext.ExcludeConstraint` ──inherits──▶ `sqlalchemy.sql.schema.ColumnCollectionConstraint` [SQL]
- `dialects.postgresql.hstore._HStoreArrayFunction` ──inherits──▶ `sqlalchemy.sql.functions.GenericFunction` [SQL]
- `dialects.postgresql.hstore._HStoreDefinedFunction` ──inherits──▶ `sqlalchemy.sql.functions.GenericFunction` [SQL]
- `dialects.postgresql.hstore._HStoreDeleteFunction` ──inherits──▶ `sqlalchemy.sql.functions.GenericFunction` [SQL]
- `dialects.postgresql.hstore._HStoreKeysFunction` ──inherits──▶ `sqlalchemy.sql.functions.GenericFunction` [SQL]
- `dialects.postgresql.hstore._HStoreMatrixFunction` ──inherits──▶ `sqlalchemy.sql.functions.GenericFunction` [SQL]
- `dialects.postgresql.hstore._HStoreSliceFunction` ──inherits──▶ `sqlalchemy.sql.functions.GenericFunction` [SQL]
- `dialects.postgresql.hstore._HStoreValsFunction` ──inherits──▶ `sqlalchemy.sql.functions.GenericFunction` [SQL]
- `dialects.postgresql.hstore.hstore` ──inherits──▶ `sqlalchemy.sql.functions.GenericFunction` [SQL]
- `dialects.postgresql.named_types.DOMAIN` ──inherits──▶ `sqlalchemy.sql.sqltypes.SchemaType` [SQL]
- `dialects.postgresql.named_types.ENUM` ──inherits──▶ `sqlalchemy.sql.sqltypes.Enum` [SQL]
- `dialects.postgresql.named_types.ENUM` ──inherits──▶ `sqlalchemy.sql.type_api.NativeForEmulated` [SQL]
- `dialects.postgresql.named_types.NamedTypeDropper` ──inherits──▶ `sqlalchemy.sql.ddl.InvokeDropDDLBase` [SQL]
- `dialects.postgresql.named_types.NamedTypeGenerator` ──inherits──▶ `sqlalchemy.sql.ddl.InvokeCreateDDLBase` [SQL]
- `dialects.postgresql.pg8000._PGBigInteger` ──inherits──▶ `sqlalchemy.sql.sqltypes.BigInteger` [SQL]
- `dialects.postgresql.pg8000._PGBoolean` ──inherits──▶ `sqlalchemy.sql.sqltypes.Boolean` [SQL]
- `dialects.postgresql.pg8000._PGDate` ──inherits──▶ `sqlalchemy.sql.sqltypes.Date` [SQL]
- `dialects.postgresql.pg8000._PGFloat` ──inherits──▶ `sqlalchemy.sql.sqltypes.Float` [SQL]
- `dialects.postgresql.pg8000._PGInteger` ──inherits──▶ `sqlalchemy.sql.sqltypes.Integer` [SQL]
- `dialects.postgresql.pg8000._PGJSONIndexType` ──inherits──▶ `sqlalchemy.sql.sqltypes.JSON.JSONIndexType` [SQL]
- `dialects.postgresql.pg8000._PGJSONIntIndexType` ──inherits──▶ `sqlalchemy.sql.sqltypes.JSON.JSONIntIndexType` [SQL]
- `dialects.postgresql.pg8000._PGJSONStrIndexType` ──inherits──▶ `sqlalchemy.sql.sqltypes.JSON.JSONStrIndexType` [SQL]
- `dialects.postgresql.pg8000._PGNullType` ──inherits──▶ `sqlalchemy.sql.sqltypes.NullType` [SQL]
- `dialects.postgresql.pg8000._PGNumeric` ──inherits──▶ `sqlalchemy.sql.sqltypes.Numeric` [SQL]
- `dialects.postgresql.pg8000._PGSmallInteger` ──inherits──▶ `sqlalchemy.sql.sqltypes.SmallInteger` [SQL]
- `dialects.postgresql.pg8000._PGString` ──inherits──▶ `sqlalchemy.sql.sqltypes.String` [SQL]
- `dialects.postgresql.pg8000._PGTime` ──inherits──▶ `sqlalchemy.sql.sqltypes.Time` [SQL]
- `dialects.postgresql.pg8000._PGTimeStamp` ──inherits──▶ `sqlalchemy.sql.sqltypes.DateTime` [SQL]
- `dialects.postgresql.psycopg.AsyncAdapt_psycopg_connection` ──inherits──▶ `sqlalchemy.engine.interfaces.AdaptedConnection` [ENGINE]
- `dialects.postgresql.psycopg._PGBigInteger` ──inherits──▶ `sqlalchemy.sql.sqltypes.BigInteger` [SQL]
- `dialects.postgresql.psycopg._PGBoolean` ──inherits──▶ `sqlalchemy.sql.sqltypes.Boolean` [SQL]
- `dialects.postgresql.psycopg._PGDate` ──inherits──▶ `sqlalchemy.sql.sqltypes.Date` [SQL]
- `dialects.postgresql.psycopg._PGInteger` ──inherits──▶ `sqlalchemy.sql.sqltypes.Integer` [SQL]
- `dialects.postgresql.psycopg._PGJSONIntIndexType` ──inherits──▶ `sqlalchemy.sql.sqltypes.JSON.JSONIntIndexType` [SQL]
- `dialects.postgresql.psycopg._PGJSONStrIndexType` ──inherits──▶ `sqlalchemy.sql.sqltypes.JSON.JSONStrIndexType` [SQL]
- `dialects.postgresql.psycopg._PGNullType` ──inherits──▶ `sqlalchemy.sql.sqltypes.NullType` [SQL]
- `dialects.postgresql.psycopg._PGSmallInteger` ──inherits──▶ `sqlalchemy.sql.sqltypes.SmallInteger` [SQL]
- `dialects.postgresql.psycopg._PGString` ──inherits──▶ `sqlalchemy.sql.sqltypes.String` [SQL]
- `dialects.postgresql.psycopg._PGTime` ──inherits──▶ `sqlalchemy.sql.sqltypes.Time` [SQL]
- `dialects.postgresql.psycopg._PGTimeStamp` ──inherits──▶ `sqlalchemy.sql.sqltypes.DateTime` [SQL]
- `dialects.postgresql.types.BYTEA` ──inherits──▶ `sqlalchemy.sql.sqltypes.LargeBinary` [SQL]
- `dialects.postgresql.types.CITEXT` ──inherits──▶ `sqlalchemy.sql.sqltypes.TEXT` [SQL]
- `dialects.postgresql.types.INTERVAL` ──inherits──▶ `sqlalchemy.sql.sqltypes._AbstractInterval` [SQL]
- `dialects.postgresql.types.INTERVAL` ──inherits──▶ `sqlalchemy.sql.type_api.NativeForEmulated` [SQL]
- `dialects.postgresql.types.TIME` ──inherits──▶ `sqlalchemy.sql.sqltypes.TIME` [SQL]
- `dialects.postgresql.types.TIMESTAMP` ──inherits──▶ `sqlalchemy.sql.sqltypes.TIMESTAMP` [SQL]
- `dialects.sqlite.aiosqlite.AsyncAdapt_aiosqlite_connection` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_terminate` [ENGINE]
- `dialects.sqlite.aiosqlite.AsyncAdapt_aiosqlite_connection` ──inherits──▶ `sqlalchemy.engine.interfaces.AdaptedConnection` [ENGINE]
- `dialects.sqlite.aiosqlite.AsyncAdapt_aiosqlite_dbapi` ──inherits──▶ `sqlalchemy.connectors.asyncio.AsyncAdapt_dbapi_module` [ENGINE]
- `dialects.sqlite.base.SQLiteCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.SQLCompiler` [SQL]
- `dialects.sqlite.base.SQLiteDDLCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.DDLCompiler` [SQL]
- `dialects.sqlite.base.SQLiteDialect` ──inherits──▶ `sqlalchemy.engine.default.DefaultDialect` [ENGINE]
- `dialects.sqlite.base.SQLiteExecutionContext` ──inherits──▶ `sqlalchemy.engine.default.DefaultExecutionContext` [ENGINE]
- `dialects.sqlite.base.SQLiteIdentifierPreparer` ──inherits──▶ `sqlalchemy.sql.compiler.IdentifierPreparer` [SQL]
- `dialects.sqlite.base.SQLiteTypeCompiler` ──inherits──▶ `sqlalchemy.sql.compiler.GenericTypeCompiler` [SQL]
- `dialects.sqlite.dml.Insert` ──inherits──▶ `sqlalchemy.sql.dml.Insert` [SQL]
- `dialects.sqlite.dml.OnConflictClause` ──inherits──▶ `sqlalchemy.sql.elements.ClauseElement` [SQL]

## Re-walk — generated

```bash
T=tenants/sqlalchemy
python3 -m graphy blast sqlalchemy://class/sqlalchemy.dialects.postgresql.ranges.Range --tenant $T/tenant.json --tenant-id sqlalchemy
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id sqlalchemy --corpus sqlalchemy --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm DIALECTS -->
