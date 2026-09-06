# COMPAT — the pydantic boundary (`fastapi._compat` · `encoders` · `utils` · `types` · `exceptions` · `exception_handlers` · `datastructures`)

> Load before touching validation, serialization, JSON-schema generation, an exception class, an
> exception handler, `UploadFile`, or any helper the other three pillars share. This is the most
> depended-on cluster in the package: by fan-in the `_compat` family, `exceptions` and `types` lead
> the walk, and every other pillar calls in. Walk-derived; the generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm

Pydantic is joined here and nowhere else. `_compat` is the switchboard: it re-exports `_compat.v2`
(the pydantic-v2 binding) and `_compat.shared` (the version-neutral annotation checks). Pydantic v1
is detected and **refused**, not bridged — `is_pydantic_v1_model_instance` / `annotation_is_pydantic_v1`
lead to `PydanticV1NotSupportedError`. `lenient_issubclass` is the single most-called helper across
the pillars; `jsonable_encoder` is the one exit from a Python object to JSON. A change to how a value
is validated or encoded lands here, and the three other pillars inherit it.

## The join out — read first
- `_compat.v2.ModelField` wraps a pydantic `FieldInfo`; `_compat.v2.GenerateJsonSchema`
  ──inherits──▶ pydantic's JSON-schema generator; `pydantic_core` supplies the validation errors.
- `exceptions.HTTPException` ──inherits──▶ Starlette's `HTTPException`; `WebSocketException`
  ──inherits──▶ Starlette's `WebSocketException`; `datastructures.UploadFile` ──inherits──▶
  Starlette's `UploadFile`.

## The load-bearing symbols (walk-derived)
**`_compat.shared`** — `lenient_issubclass` · `field_annotation_is_sequence` /
`_complex` / `_scalar` / `_scalar_sequence` · `value_is_sequence` ·
`is_bytes_or_nonable_bytes_annotation` · `is_uploadfile_or_nonable_uploadfile_annotation` ·
`is_bytes_sequence_annotation` · `is_uploadfile_sequence_annotation` · the pydantic-v1 detectors.

**`_compat.v2`** — `ModelField` · `GenerateJsonSchema` · `get_schema_from_model_field` ·
`get_definitions` · `get_model_fields` / `get_cached_model_fields` · `create_body_model` ·
`get_flat_models_from_model` / `_annotation` / `_field` / `_fields` · `get_model_name_map` ·
`is_scalar_field` · `copy_field_info` · `serialize_sequence_value` · `get_missing_field_error` ·
`evaluate_forwardref` · `normalize_name` · `_regenerate_error_with_loc` · `_has_computed_fields`.

**`encoders`** — `jsonable_encoder` (recursive; `model_dump` for models, `dataclasses.asdict`,
`ENCODERS_BY_TYPE`, a caller's `custom_encoder`) · `isoformat` · `decimal_encoder` ·
`generate_encoders_by_class_tuples`.

**`utils`** — `create_model_field` · `get_path_param_names` · `get_value_or_default` ·
`is_body_allowed_for_status_code` · `generate_unique_id` · `generate_operation_id_for_path` ·
`deep_dict_update`.

**`datastructures`** — `Default` / `DefaultPlaceholder` (the sentinel every ROUTING signature
carries, and the most-called symbol in the package) · `UploadFile` (`read` / `write` / `seek` /
`close` / `_validate`).

**`exceptions`** — `HTTPException` · `WebSocketException` · `FastAPIError` (→
`DependencyScopeError`, `PydanticV1NotSupportedError`) · `ValidationException` (→
`RequestValidationError`, `WebSocketRequestValidationError`, `ResponseValidationError`; `.errors()`)
· `EndpointContext` · `FastAPIDeprecationWarning`.

**`exception_handlers`** — `http_exception_handler` · `request_validation_exception_handler` ·
`websocket_request_validation_exception_handler`, installed by the app's `setup()`.

**`types`** — the shared type aliases; imported by more modules than any other file here.

## Cross-pillar joins (all inbound)
- ← **ROUTING**: `Default`, `jsonable_encoder`, `HTTPException`, `get_value_or_default`,
  `lenient_issubclass`, `create_model_field`, `EndpointContext`, `FastAPIError`,
  `is_body_allowed_for_status_code`.
- ← **DEPENDENCIES**: `lenient_issubclass`, `create_model_field`, `get_cached_model_fields`,
  `ModelField`, `is_scalar_field`, the annotation checks, `get_missing_field_error`,
  `UploadFile`, `HTTPException` (every security scheme's failure path).
- ← **OPENAPI**: `get_schema_from_model_field`, `get_flat_models_from_fields`,
  `get_model_name_map`, `get_definitions`, `jsonable_encoder`, `deep_dict_update`,
  `is_body_allowed_for_status_code`, `lenient_issubclass`.

<!-- graphy:arm COMPAT generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=98a23a7b377422b0 cut=sha256:1b374eca2713cf023978e1dc5ff0b4f0e0a6472095555c435a3933cd7180d8d2 content=sha256:a7f2be2f9aa537a07e383ddde5e301c9b08e58345a42716644b07468dd75b7ed -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`fastapi._compat.shared`** — functions: `_annotation_is_complex` · `_annotation_is_sequence` · `annotation_is_pydantic_v1` · `field_annotation_is_complex` · `field_annotation_is_scalar` · `field_annotation_is_scalar_sequence` · `field_annotation_is_sequence` · `is_bytes_or_nonable_bytes_annotation` · `is_bytes_sequence_annotation` · `is_pydantic_v1_model_class` · `is_pydantic_v1_model_instance` · `is_uploadfile_or_nonable_uploadfile_annotation` · `is_uploadfile_sequence_annotation` · `lenient_issubclass` · `value_is_sequence`
**`fastapi._compat.v2`** — classes: `GenerateJsonSchema` (1) · `ModelField` (10); functions: `_has_computed_fields` · `_regenerate_error_with_loc` · `asdict` · `copy_field_info` · `create_body_model` · `evaluate_forwardref` · `get_cached_model_fields` · `get_definitions` · `get_flat_models_from_annotation` · `get_flat_models_from_field` · `get_flat_models_from_fields` · `get_flat_models_from_model` · `get_missing_field_error` · `get_model_fields` · `get_model_name_map` · `get_schema_from_model_field` · `is_scalar_field` · `normalize_name` · `serialize_sequence_value`
**`fastapi.datastructures`** — classes: `DefaultPlaceholder` (3) · `UploadFile` (7); functions: `Default`
**`fastapi.encoders`** — classes: `Color` · `PyExtraColor`; functions: `decimal_encoder` · `generate_encoders_by_class_tuples` · `isoformat` · `jsonable_encoder`
**`fastapi.exception_handlers`** — functions: `http_exception_handler` · `request_validation_exception_handler` · `websocket_request_validation_exception_handler`
**`fastapi.exceptions`** — classes: `DependencyScopeError` · `EndpointContext` · `FastAPIDeprecationWarning` · `FastAPIError` · `HTTPException` (1) · `PydanticV1NotSupportedError` · `RequestValidationError` (1) · `ResponseValidationError` (1) · `ValidationException` (4) · `WebSocketException` (1) · `WebSocketRequestValidationError` (1)
**`fastapi.utils`** — functions: `create_model_field` · `deep_dict_update` · `generate_operation_id_for_path` · `generate_unique_id` · `get_path_param_names` · `get_value_or_default` · `is_body_allowed_for_status_code`

## The inherits joins out — generated

- `_compat.v2.GenerateJsonSchema` ──inherits──▶ `pydantic.json_schema.GenerateJsonSchema` pydantic
- `datastructures.UploadFile` ──inherits──▶ `starlette.datastructures.UploadFile` starlette
- `exceptions.HTTPException` ──inherits──▶ `starlette.exceptions.HTTPException` starlette
- `exceptions.WebSocketException` ──inherits──▶ `starlette.exceptions.WebSocketException` starlette

## Re-walk — generated

```bash
T=tenants/fastapi
python3 -m graphy blast fastapi://func/fastapi.datastructures.Default --tenant $T/tenant.json --tenant-id fastapi
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id fastapi --corpus fastapi --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id fastapi --corpus fastapi --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm COMPAT -->
