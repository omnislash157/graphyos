# OPENAPI — the mirror (`fastapi.openapi.utils` · `openapi.models` · `openapi.docs` · `openapi.constants`)

> Load before touching `/openapi.json`, the Swagger or ReDoc pages, or any schema output. This arm
> is a consumer: it reads the routes (ROUTING), their flattened dependants (DEPENDENCIES) and the
> pydantic schemas (COMPAT) and emits the document. Nothing calls into it except the app's
> `openapi()` and `setup()`. Walk-derived; the generated region at the bottom is the walk's own inventory and the re-walk.

## ⚖ The law of this arm

`get_openapi` is the top-level builder and `get_openapi_path` is the per-route builder; a schema
question walks them in that order. The document is assembled as pydantic models
(`openapi.models`, all rooted at `BaseModelWithConfig`) and then passed through `jsonable_encoder`.
The arm owns no behavior of the running app — change what it reflects, and it reflects the change.

## The join out — read first
- `openapi.models.BaseModelWithConfig` ──inherits──▶ pydantic `BaseModel`, and every spec model
  extends it: `Info` · `Server` · `Schema` · `Parameter` / `Header` (← `ParameterBase`) ·
  `RequestBody` · `Response` · `Operation` · `PathItem` · `Components` · `Tag` · `OpenAPI` · the
  security models `APIKey` / `HTTPBase` / `HTTPBearer` / `OAuth2` / `OpenIdConnect` (← `SecurityBase`)
  and the `OAuthFlow*` family. `Reference` and `Discriminator` extend `BaseModel` directly;
  `Example` is a `TypedDict`; `ParameterInType` / `SecuritySchemeType` / `APIKeyIn` are enums.
- The email type in the models joins `email_validator`. The docs pages return Starlette's
  `HTMLResponse`.

## The load-bearing symbols (walk-derived)
**`openapi.utils`**
- `get_openapi` — `routing.iter_route_contexts` → `_get_api_route_for_openapi` →
  `get_openapi_path` per route; `get_fields_from_routes` → `get_flat_models_from_fields` →
  `get_model_name_map` → `get_definitions` for the components; builds `OpenAPI` and encodes it with
  `jsonable_encoder`. Webhooks ride the same path.
- `get_openapi_path` — `get_openapi_operation_metadata`, `get_flat_dependant`,
  `get_openapi_security_definitions`, `_get_openapi_operation_parameters`, `get_flat_params`,
  `get_openapi_operation_request_body`, `get_schema_from_model_field`, `deep_dict_update`,
  `is_body_allowed_for_status_code`; the response section is built with nested `setdefault`.
- `generate_operation_id` · `generate_operation_summary` · `get_openapi_security_definitions` ·
  `get_openapi_operation_request_body` · `_get_openapi_operation_parameters` ·
  `get_fields_from_routes` · `_get_api_route_for_openapi`.

**`openapi.docs`** — `get_swagger_ui_html` · `get_redoc_html` ·
`get_swagger_ui_oauth2_redirect_html` · `_html_safe_json`; the app's `setup()` mounts them.

**`openapi.constants`** — the method and reference constants the builders share.

## The data flow
`FastAPI.openapi()` checks the router's routes version, then `get_openapi(routes=…)`. For each route,
`get_openapi_path` flattens the route's `Dependant` into parameters, request body and security
definitions, and pulls each field's schema through `_compat`. The per-model definitions are
collected once across all routes (`get_fields_from_routes` → `get_definitions`) and land in
`components.schemas`. The result is a pydantic `OpenAPI` model, encoded to a dict.

## Cross-pillar joins (all outbound)
- → **ROUTING**: `iter_route_contexts`; ← the app's `openapi()` and `setup()` are the only callers.
- → **DEPENDENCIES**: `get_flat_dependant`, `get_flat_params`, `get_validation_alias`,
  `_get_flat_fields_from_params`; the security models mirror the schemes in
  `fastapi.security`.
- → **COMPAT**: `get_schema_from_model_field`, `get_flat_models_from_fields`,
  `get_model_name_map`, `get_definitions`, `jsonable_encoder`, `deep_dict_update`,
  `is_body_allowed_for_status_code`, `lenient_issubclass`.

<!-- graphy:arm OPENAPI generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=98a23a7b377422b0 cut=sha256:1b374eca2713cf023978e1dc5ff0b4f0e0a6472095555c435a3933cd7180d8d2 content=sha256:d380c37c29803836be65614c16ea0fb9b68987572ebdce88b907951c223189b5 -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`fastapi.openapi.docs`** — functions: `_html_safe_json` · `get_redoc_html` · `get_swagger_ui_html` · `get_swagger_ui_oauth2_redirect_html`
**`fastapi.openapi.models`** — classes: `APIKey` · `APIKeyIn` · `BaseModelWithConfig` · `Components` · `Contact` · `Discriminator` · `EmailStr` (5) · `Encoding` · `Example` · `ExternalDocumentation` · `HTTPBase` · `HTTPBearer` · `Header` · `Info` · `License` · `Link` · `MediaType` · `OAuth2` · `OAuthFlow` · `OAuthFlowAuthorizationCode` · `OAuthFlowClientCredentials` · `OAuthFlowImplicit` · `OAuthFlowPassword` · `OAuthFlows` · `OpenAPI` · `OpenIdConnect` · `Operation` · `Parameter` · `ParameterBase` · `ParameterInType` · `PathItem` · `Reference` · `RequestBody` · `Response` · `Schema` · `SecurityBase` · `SecuritySchemeType` · `Server` · `ServerVariable` · `Tag` · `XML`
**`fastapi.openapi.utils`** — functions: `_get_api_route_for_openapi` · `_get_openapi_operation_parameters` · `generate_operation_id` · `generate_operation_summary` · `get_fields_from_routes` · `get_openapi` · `get_openapi_operation_metadata` · `get_openapi_operation_request_body` · `get_openapi_path` · `get_openapi_security_definitions`

## The inherits joins out — generated

- `openapi.models.Example` ──inherits──▶ `typing_extensions.TypedDict` typing_extensions

## Re-walk — generated

```bash
T=tenants/fastapi
python3 -m graphy blast fastapi://class/fastapi.openapi.models.HTTPBase --tenant $T/tenant.json --tenant-id fastapi
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id fastapi --corpus fastapi --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id fastapi --corpus fastapi --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm OPENAPI -->
