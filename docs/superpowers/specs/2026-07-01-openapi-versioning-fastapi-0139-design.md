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

## Approach (chosen: single-call, flat route list with version-suffixed paths)

> **Decision history.** An earlier draft chose a per-version approach (one
> `get_openapi` call per version group, then merge). During implementation review it
> was found to regress a real case (see "Why single-call" below), and the design was
> changed to the single-call approach documented here.

Adapt the original `_custom_openapi` mechanism to FastAPI 0.139's route model:

1. **Enumerate routes with effective paths.** Iterate
   `fastapi.routing.iter_route_contexts(app.routes)`. This sees `VersionedAPIRoute`s
   nested inside included routers (`_IncludedRouter`) and exposes each route's
   effective `path_format` (prefix included). This route-enumeration is the one
   unavoidable FastAPI-internal dependency.
2. **Build a flat route list for a single call.** Non-versioned contexts pass through
   unchanged. Each versioned route is shallow-copied with
   `path_format = f"{context.path_format}:{route.version_str}"` so `get_openapi` keeps
   same-path versions distinct. Because the copies are passed directly (not through an
   included router), `get_openapi` reads `path_format` from the copy, so the suffix
   takes effect.
3. **One `get_openapi` call** over that list.
4. **Post-process paths.** For each generated path: no `:` -> keep as-is; otherwise
   `rsplit(":", 1)` into `clean_path` + `version_str`, rewrite each operation's
   `requestBody.content` keys to `<vendor>; version=X.Y`, and merge into `clean_path`
   (`helpers.dict_merge` for later occurrences). Response `content` keys are already
   correct because `VersionedJSONResponse.media_type` bakes in `; version=X.Y`.
5. Cache on `self.openapi_schema` as before.

### Why single-call (not per-version merge)

FastAPI disambiguates same-named-but-different Pydantic models **only within one
`get_openapi` call**. If two versions define different models sharing a class name
(e.g. an `Item` that gains a `price` field in v2, defined in separate `v1/`/`v2/`
modules — a normal versioning pattern), a single call emits two distinct component
schemas with correct per-version `$ref`s. Splitting into one call per version makes
each call see only its own models, so both versions `$ref` the same
`#/components/schemas/Item` and the merge silently corrupts the older version. The
single-call property of the original design was load-bearing for correctness; this
approach preserves it. Cost: it reuses the `path_format`-suffix + `:`-split mechanism,
which is FastAPI-internal but fails visibly (a stray `:` in a path) rather than
silently, and is guarded by a regression test.

## Testing (TDD)

Write the failing test first, then implement.

- Extend/confirm `test_openapi_schema`: `GET /test/` and `POST /test/` each expose
  both versions in `responses.200.content`; `POST /test/` request body exposes both
  versions in `requestBody.content`; total path count is correct; second call returns
  the cached schema.
- **New coverage:** a versioned router included with a `prefix=` must still produce a
  correctly versioned, merged schema at the prefixed path. Current tests do not cover
  prefixes, and route-enumeration through `_IncludedRouter` is the risky part.
- **New coverage (regression guard):** two versions of one POST route whose body
  models share a class name but differ in fields must produce distinct component
  schemas and distinct per-version `$ref`s. This test fails on the per-version
  approach and passes on the single-call approach.
- Non-versioned routes (`/simple/`, websocket) remain untouched in the schema.
- All existing tests continue to pass under FastAPI 0.139 / Starlette 1.3.1.

## Out of scope

- The `httpx` -> `httpx2` dev-dependency swap is intentional and kept as-is.
- No change to runtime request routing (middleware, `VersionedAPIRoute.matches`).
- No widening of the `\d\.\d` version format.

## Risks

- Route enumeration and the `path_format`-suffix trick rely on FastAPI/Starlette
  internals (`iter_route_contexts`, `RouteContext.path_format`, and `get_openapi`
  keying paths off `path_format`). Mitigation: isolate the traversal in one small
  helper (`_iter_openapi_routes`) with a focused test asserting the effective
  version-suffixed paths, so a future break is localized and fails loudly.
