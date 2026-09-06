# DEPENDENCIES — the engine (`fastapi.dependencies` · `fastapi.params` · `fastapi.param_functions` · `fastapi.security`)

> Load before touching `Depends`, `Security`, any of `Query` / `Path` / `Body` / `Header` / `Cookie` /
> `Form` / `File`, any auth scheme, or anything that reads an endpoint signature. This is the
> framework's defining feature: the endpoint's parameters ARE a dependency tree, built once at route
> construction and solved per request. Walk-derived; the generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm

Two choke points, one per phase. **Build:** `get_dependant` turns a callable's signature into a
`Dependant`, one `analyze_param` per parameter. **Solve:** `solve_dependencies` walks that tree per
request, recursing into sub-dependencies, pulling values with `request_params_to_args` and
`request_body_to_args`, and validating them at the pydantic boundary (COMPAT). The params are
markers the build phase reads, and every security scheme is a dependency the solve phase calls —
neither is a parallel system.

## The join out — read first
- `params.Param` and `params.Body` ──inherits──▶ pydantic's `FieldInfo`. `Path` / `Query` / `Header`
  / `Cookie` extend `Param`; `Form` extends `Body`; `File` extends `Form`; `Security` extends
  `Depends`. `param_functions` carries the callables of the same names you actually write.
- Every scheme ──inherits──▶ `security.base.SecurityBase`: `APIKeyBase` → `APIKeyQuery` /
  `APIKeyHeader` / `APIKeyCookie`; `HTTPBase` → `HTTPBasic` / `HTTPBearer` / `HTTPDigest`; `OAuth2` →
  `OAuth2PasswordBearer` / `OAuth2AuthorizationCodeBearer`; `OpenIdConnect`. The credential carriers
  (`HTTPBasicCredentials`, `HTTPAuthorizationCredentials`) are pydantic `BaseModel`s.
- Values come off Starlette's `Request` / `WebSocket`; form bodies need `python-multipart`
  (`ensure_multipart_is_installed`).

## The load-bearing symbols (walk-derived)
**The tree** — `dependencies.models`
- `Dependant` — the resolved node: sub-dependencies, the path / query / header / cookie / body
  fields, the callable, the security requirements, the scope. `_unwrapped_call` and `_impartial`
  are its most-called helpers (unwrapping `functools.partial` and decorators to the real callable).
- `ParamDetails` · `SolvedDependency` — the per-parameter and per-solve carriers.

**Build** — `dependencies.utils`
- `get_dependant` → `Dependant`, `get_path_param_names` (COMPAT), `get_typed_signature`,
  `analyze_param`, `add_non_field_param_to_dependency`, `add_param_to_fields`; raises
  `DependencyScopeError`.
- `analyze_param` — classifies one parameter: `lenient_issubclass`, `is_scalar_field`,
  `create_model_field`, `copy_field_info`, the `field_annotation_is_*` and `is_uploadfile_*`
  checks (COMPAT), and the default markers `params.Path` / `Query` / `Body` / `File`.
- `get_typed_signature` · `get_typed_annotation` · `get_typed_return_annotation` ·
  `get_stream_item_type` — annotation resolution, `Annotated[]` included.
- `get_flat_dependant` · `get_flat_params` · `_get_flat_fields_from_params` ·
  `get_parameterless_sub_dependant` · `get_validation_alias` · `get_body_field` — the flattened
  views ROUTING and OPENAPI read.

**Solve** — `dependencies.utils`
- `solve_dependencies` — recursion, `request_params_to_args`, `request_body_to_args`,
  `_solve_generator` (the `yield` dependencies), `SecurityScopes`, `BackgroundTasks`, `Response`,
  `run_in_threadpool` for sync callables; returns `SolvedDependency`.
- `request_params_to_args` · `request_body_to_args` → `_validate_value_with_model_field`,
  `get_validation_alias`, `get_cached_model_fields`, `_extract_form_body`,
  `get_missing_field_error`; `_get_multidict_value`, `_should_embed_body_fields`,
  `is_union_of_base_models`, `_is_json_field`.

**Security** — every scheme's `__call__` reads the request through
`security.utils.get_authorization_scheme_param` and, on failure, `make_not_authenticated_error` →
`HTTPException` (COMPAT). `APIKeyBase.check_api_key` is the shared API-key check.
`OAuth2PasswordRequestForm` / `…Strict` are the form bodies of the password flow; `SecurityScopes`
is what a scoped dependency receives.

## The data flow
Construction: `get_dependant(endpoint)` → `Dependant`, stored on the `APIRoute`. Per request:
`solve_dependencies(request, dependant)` → depth-first sub-dependencies (cached by callable) →
`request_*_to_args` validate against pydantic fields → the endpoint is called with the solved
kwargs. A security scheme is one node in that tree.

## Cross-pillar joins
- ← **ROUTING** calls `get_dependant` at construction and `solve_dependencies` per request.
- → **COMPAT**: `lenient_issubclass`, `create_model_field`, `get_cached_model_fields`,
  `ModelField`, `is_scalar_field`, the annotation checks, `get_missing_field_error`,
  `HTTPException`, `UploadFile`.
- ← **OPENAPI** reads `get_flat_dependant`, `get_flat_params`, `get_validation_alias`,
  `_get_flat_fields_from_params`.

<!-- graphy:arm DEPENDENCIES generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=98a23a7b377422b0 cut=sha256:1b374eca2713cf023978e1dc5ff0b4f0e0a6472095555c435a3933cd7180d8d2 content=sha256:9ba45a3c692d0c4a70268603a598a2718fbc527fee765001af8fe012650d3d1e -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`fastapi.dependencies.models`** — classes: `Dependant` (10); functions: `_impartial` · `_unwrapped_call`
**`fastapi.dependencies.utils`** — classes: `ParamDetails` · `SolvedDependency`; functions: `_extract_form_body` · `_get_flat_fields_from_params` · `_get_multidict_value` · `_get_signature` · `_is_json_field` · `_should_embed_body_fields` · `_solve_generator` · `_validate_value_with_model_field` · `add_non_field_param_to_dependency` · `add_param_to_fields` · `analyze_param` · `ensure_multipart_is_installed` · `get_body_field` · `get_dependant` · `get_flat_dependant` · `get_flat_params` · `get_parameterless_sub_dependant` · `get_stream_item_type` · `get_typed_annotation` · `get_typed_return_annotation` · `get_typed_signature` · `get_validation_alias` · `is_union_of_base_models` · `request_body_to_args` · `request_params_to_args` · `solve_dependencies`
**`fastapi.param_functions`** — functions: `Body` · `Cookie` · `Depends` · `File` · `Form` · `Header` · `Path` · `Query` · `Security`
**`fastapi.params`** — classes: `Body` (2) · `Cookie` (1) · `Depends` · `File` (1) · `Form` (1) · `Header` (1) · `Param` (2) · `ParamTypes` · `Path` (1) · `Query` (1) · `Security`
**`fastapi.security.api_key`** — classes: `APIKeyBase` (3) · `APIKeyCookie` (2) · `APIKeyHeader` (2) · `APIKeyQuery` (2)
**`fastapi.security.base`** — classes: `SecurityBase`
**`fastapi.security.http`** — classes: `HTTPAuthorizationCredentials` · `HTTPBase` (4) · `HTTPBasic` (3) · `HTTPBasicCredentials` · `HTTPBearer` (2) · `HTTPDigest` (2)
**`fastapi.security.oauth2`** — classes: `OAuth2` (3) · `OAuth2AuthorizationCodeBearer` (2) · `OAuth2PasswordBearer` (2) · `OAuth2PasswordRequestForm` (1) · `OAuth2PasswordRequestFormStrict` (1) · `SecurityScopes` (1)
**`fastapi.security.open_id_connect_url`** — classes: `OpenIdConnect` (3)
**`fastapi.security.utils`** — functions: `get_authorization_scheme_param`

## The inherits joins out — generated

- `params.Body` ──inherits──▶ `pydantic.fields.FieldInfo` pydantic
- `params.Param` ──inherits──▶ `pydantic.fields.FieldInfo` pydantic

## Re-walk — generated

```bash
T=tenants/fastapi
python3 -m graphy blast fastapi://func/fastapi.security.utils.get_authorization_scheme_param --tenant $T/tenant.json --tenant-id fastapi
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id fastapi --corpus fastapi --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id fastapi --corpus fastapi --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm DEPENDENCIES -->
