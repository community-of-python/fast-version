# Fix OpenAPI version schema generation for FastAPI 0.139+

Date: 2026-07-01

## Problem

`test_openapi_schema` fails after a dependency upgrade. `GET /test/` in the
generated OpenAPI schema contains only `version=2.0` in its `responses.200.content`
instead of both `1.0` and `2.0`. Runtime version routing is unaffected (all other
tests pass); only schema generation is broken.

### Root cause

The staged `httpx` -> `httpx2` change is unrelated (test-only dependency). The real
trigger is `uv lock --upgrade` (run by `just install`) bumping **FastAPI to 0.139.0 /
Starlette 1.3.1**, which shipped a routing/OpenAPI refactor.

`_custom_openapi` (`fast_version/app.py`) worked by:
1. Iterating `self.routes`, finding `VersionedAPIRoute` instances.
2. Shallow-copying each and suffixing `path_format` with `:<version>` so
   `get_openapi` would not merge same-path routes.
3. Splitting the `:<version>` suffix back off and merging per-version schemas with
   `helpers.dict_merge`, rewriting request-body `content` keys to include
   `; version=X.Y`.

FastAPI 0.139 breaks steps 1 and 2:
- `app.include_router(R)` no longer flattens routes into `app.routes`; it stores a
  single opaque `_IncludedRouter`. `self.routes` contains **zero** `VersionedAPIRoute`
  instances, so nothing gets suffixed.
- `get_openapi` now reads `path_format` off a `RouteContext` computed through an
  effective-route-context layer. Verified: mutating `original_route.path_format` does
  **not** propagate to what `get_openapi` reads. The copy-and-mutate mechanism is
  structurally dead, not one-line-fixable.

## Approach (chosen: per-version schema merge)

Stop tricking `get_openapi` into not merging. Instead, generate a clean schema per
version and merge the results:

1. **Enumerate versioned routes.** Collect all `VersionedAPIRoute` instances the app
   serves, including those nested inside `_IncludedRouter` (and any nested routers),
   with their effective paths. This route-enumeration is the one unavoidable
   FastAPI-internal dependency; both candidate approaches share it.
2. **Group routes by version** (the `route.version` tuple).
3. **Call `get_openapi` once per version group**, passing only that version's
   `VersionedAPIRoute`s plus all non-versioned routes, via the public `routes=`
   parameter. No two routes in a group share path+method, so nothing collides and no
   `path_format` mutation or `:`-suffix string surgery is needed.
4. **Merge the per-version schemas** into a single schema with `helpers.dict_merge`.
   Response `content` keys are already correct per version because
   `VersionedJSONResponse.media_type` bakes in `; version=X.Y`. Request-body `content`
   keys still need the existing rewrite to `<vendor>; version=X.Y`.
5. Cache the result on `self.openapi_schema` as before.

### Why this over "restore the mechanism"

The alternative (traverse `_IncludedRouter`, copy routes, re-suffix `path_format`,
pass a flat list) rebuilds on the exact internal path-computation layer that just
broke, plus fragile `:`-splitting. Option 2 depends only on `get_openapi`'s public
`routes=` param; the sole internal dependency (route enumeration) is shared by both.
Fewer fragile assumptions -> more durable across future FastAPI refactors.

## Testing (TDD)

Write the failing test first, then implement.

- Extend/confirm `test_openapi_schema`: `GET /test/` and `POST /test/` each expose
  both versions in `responses.200.content`; `POST /test/` request body exposes both
  versions in `requestBody.content`; total path count is correct; second call returns
  the cached schema.
- **New coverage:** a versioned router included with a `prefix=` must still produce a
  correctly versioned, merged schema at the prefixed path. Current tests do not cover
  prefixes, and route-enumeration through `_IncludedRouter` is the risky part.
- Non-versioned routes (`/simple/`, websocket) remain untouched in the schema.
- All existing tests continue to pass under FastAPI 0.139 / Starlette 1.3.1.

## Out of scope

- The `httpx` -> `httpx2` dev-dependency swap is intentional and kept as-is.
- No change to runtime request routing (middleware, `VersionedAPIRoute.matches`).
- No widening of the `\d\.\d` version format.

## Risks

- Route enumeration relies on FastAPI/Starlette internals (`_IncludedRouter` and its
  route-context accessors). Mitigation: isolate this traversal in one small helper
  with a focused test, so a future break is localized and obvious.
