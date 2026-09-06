# ROUTING — the spine (`fastapi.routing` · `fastapi.applications` · `fastapi.sse`)

> Load before touching the app object, a router, a route, the verb decorators, the request→response
> handler, or the SSE stream. Walk-derived; the generated region at the bottom is the walk's own inventory and the re-walk. **This arm inherits
> Starlette** — a routing question that dead-ends here continues in Starlette's `Router` / `Route` /
> `Starlette`, and the app never reimplements what the parent already does.

## ⚖ The law of this arm

`get_request_handler` is the choke point. It is the per-route ASGI handler: solve the dependency
tree → call the endpoint → validate and encode the response → or stream it. Every routing behavior
change walks it first. `FastAPI` is an `APIRouter` host: its verb decorators delegate to the one
router it builds in `__init__`, and the app's own doors are the docs, the exception handlers and
`openapi()`.

## The join out — read first
- `FastAPI` ──inherits──▶ Starlette's `Starlette` — lifespan, the middleware stack, mounting and
  exception-handler registration are the parent's.
- `APIRouter` ──inherits──▶ Starlette's `Router` · `APIRoute` ──inherits──▶ `Route` ·
  `APIWebSocketRoute` ──inherits──▶ `WebSocketRoute` · the include and frontend route families
  ──inherits──▶ `BaseRoute` · `_FrontendStaticFiles` ──inherits──▶ `StaticFiles`.
- `EventSourceResponse` ──inherits──▶ Starlette's `StreamingResponse`; `ServerSentEvent` is a pydantic
  `BaseModel`. The SSE lane rides `anyio` memory streams and `anyio.sleep` for keepalives.

## The load-bearing symbols (walk-derived)
**Classes**
- `applications.FastAPI` — builds `routing.APIRouter` and `State`, then `setup()` installs the docs
  routes and the default exception handlers. Its verbs and `include_router` delegate to the router;
  `openapi()` reads the router's routes version and calls `get_openapi`.
- `routing.APIRouter` — the verb decorators, `add_api_route` / `api_route`, `include_router`,
  `websocket` / `add_api_websocket_route`, the event handlers, and `app` (the ASGI entry, wrapped by
  `AsyncExitStackMiddleware`). `_mark_routes_changed` / `_get_routes_version` are how the app knows
  the OpenAPI document is stale.
- `routing.APIRoute` — one HTTP route; `__init__` runs `_populate_api_route_state`, wraps the handler
  with `request_response`, and exposes `get_route_handler` (the override seam for a custom route class).
- `routing.APIWebSocketRoute` — the WebSocket route; `get_websocket_app` / `websocket_session`.
- `RouteContext` · `_EffectiveRouteContext` · `_RouterIncludeContext` · `_IncludedRouter` — this
  HEAD's include model: a router included into another carries its context (prefix, tags,
  dependencies) and matches through `_IncludedRouter`, whose `effective_*` methods resolve it. This
  family exists in the shard and in no training-data summary of the framework — the reason to walk.
- `_FrontendRoute` · `_FrontendRouteGroup` · `_FrontendStaticFiles` — the frontend route family
  (`_normalize_frontend_path`, `_join_frontend_paths`, `_frontend_path_specificity`,
  `_is_frontend_navigation_request`).

**The request lifecycle (module functions)**
- `get_request_handler` — solve → `dependant.call` → serialize; raises `RequestValidationError` /
  `HTTPException`; for streams builds `StreamingResponse` and `format_sse_event`; runs sync endpoints
  through the threadpool (`run_endpoint_function`, `iterate_in_threadpool`).
- `serialize_response` — `field.validate` then `jsonable_encoder`; `ResponseValidationError` on failure.
- `_build_response_args` · `_extract_endpoint_context` (→ `EndpointContext`) · `request_response` ·
  `_build_dependant_with_parameterless_dependencies` · `_populate_api_route_state`.
- `iter_route_contexts` / `_iter_routes_with_context` — the route enumeration OPENAPI reads.
- the scope helpers `_get_fastapi_scope` · `_update_scope` · `_restore_fastapi_scope_key` ·
  `_get_scope_effective_route_context` — how per-request route state rides the ASGI scope.
- the lifespan helpers `_merge_lifespan_context` · `_wrap_gen_lifespan_context` · `_DefaultLifespan`.

## The data flow, one route end to end
`APIRouter.get("/x")` → `add_api_route` (`get_value_or_default` picks router-vs-route settings,
`route_class` builds the route) → `APIRoute.__init__` → `get_dependant` analyzes the endpoint
signature once (DEPENDENCIES) → per request `get_request_handler` → `solve_dependencies` → the
endpoint → `serialize_response` → `jsonable_encoder` (COMPAT).

## Cross-pillar joins
- → **DEPENDENCIES**: `get_dependant` at construction, `solve_dependencies` per request,
  `get_flat_dependant` for the route's fields.
- → **COMPAT**: `Default` / `DefaultPlaceholder` (the sentinel every signature carries),
  `jsonable_encoder`, `HTTPException`, `get_value_or_default`, `lenient_issubclass`,
  `create_model_field`, `EndpointContext`, `FastAPIError`.
- ← **OPENAPI** reads `iter_route_contexts`; the app's `openapi()` and `setup()` call into OPENAPI.

<!-- graphy:arm ROUTING generated — do not edit inside this region; `graphy arms` regenerates it, `graphy arms --verify` names drift
     store=98a23a7b377422b0 cut=sha256:1b374eca2713cf023978e1dc5ff0b4f0e0a6472095555c435a3933cd7180d8d2 content=sha256:05ea817147b6a1aeff530a0feb910a858dc489e041edcd632458b786df783e4a -->
## The walk's inventory — generated

Every symbol the partition places in this arm, by module; a class carries its method count. The prose above is judgment; this region is the walk, re-rendered from the store on every rebuild and refused when it drifts.

**`fastapi.applications`** — classes: `FastAPI` (23)
**`fastapi.routing`** — classes: `APIRoute` (4) · `APIRouter` (32) · `APIWebSocketRoute` (2) · `RouteContext` (8) · `_APIRouteLike` · `_AsyncLiftContextManager` (3) · `_DefaultLifespan` (4) · `_EffectiveRouteContext` (4) · `_FrontendRoute` (6) · `_FrontendRouteGroup` (8) · `_FrontendStaticFiles` (9) · `_IncludedRouter` (9) · `_RouteWithPath` · `_RouterIncludeContext` (3); functions: `_build_dependant_with_parameterless_dependencies` · `_build_response_args` · `_extract_endpoint_context` · `_frontend_dependency_endpoint` · `_frontend_path_specificity` · `_frontend_scope_specificity` · `_get_fastapi_scope` · `_get_resolved_absolute_path` · `_get_scope_effective_route_context` · `_get_scope_included_router` · `_is_frontend_navigation_request` · `_iter_accept_media_types` · `_iter_included_route_candidates` · `_iter_routes_with_context` · `_join_frontend_paths` · `_merge_lifespan_context` · `_normalize_frontend_path` · `_populate_api_route_state` · `_restore_fastapi_scope_key` · `_update_scope` · `_wrap_gen_lifespan_context` · `get_request_handler` · `get_websocket_app` · `iter_route_contexts` · `request_response` · `run_endpoint_function` · `serialize_response` · `websocket_session`
**`fastapi.sse`** — classes: `EventSourceResponse` · `ServerSentEvent` (1); functions: `_check_event_single_line` · `_check_id_valid` · `_check_single_line` · `format_sse_event`

## The inherits joins out — generated

- `applications.FastAPI` ──inherits──▶ `starlette.applications.Starlette` starlette
- `routing.APIRoute` ──inherits──▶ `starlette.routing.Route` starlette
- `routing.APIRouter` ──inherits──▶ `starlette.routing.Router` starlette
- `routing.APIWebSocketRoute` ──inherits──▶ `starlette.routing.WebSocketRoute` starlette
- `routing._FrontendRoute` ──inherits──▶ `starlette.routing.BaseRoute` starlette
- `routing._FrontendRouteGroup` ──inherits──▶ `starlette.routing.BaseRoute` starlette
- `routing._FrontendStaticFiles` ──inherits──▶ `starlette.staticfiles.StaticFiles` starlette
- `routing._IncludedRouter` ──inherits──▶ `starlette.routing.BaseRoute` starlette
- `sse.EventSourceResponse` ──inherits──▶ `starlette.responses.StreamingResponse` starlette

## Re-walk — generated

```bash
T=tenants/fastapi
python3 -m graphy blast fastapi://func/fastapi.routing.iter_route_contexts --tenant $T/tenant.json --tenant-id fastapi
python3 -m graphy pillars --tenant $T/tenant.json --tenant-id fastapi --corpus fastapi --against $T/partition.json
python3 -m graphy arms --tenant $T/tenant.json --tenant-id fastapi --corpus fastapi --partition $T/partition.json --dir $T/arms --verify
```

<!-- /graphy:arm ROUTING -->
