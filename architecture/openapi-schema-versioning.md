# OpenAPI schema versioning

How the generated OpenAPI schema represents several versions that share one path.
Because multiple versioned routes have the same path and method, a naive
`get_openapi` call would merge them and lose the per-version request bodies. The
library replaces `app.openapi` with a custom generator that keeps the versions
distinct and then collapses them back under the clean path, keyed by media type.

Implemented in `fast_version/app.py`, installed by `init_fastapi_versioning`
(`app.openapi = MethodType(_custom_openapi, app)`).

## Build a disambiguated route list — `_iter_openapi_routes`

Traverses the app's routes (descending into included routers) and returns a route
list for a single `get_openapi` call, plus the set of paths it made distinct.
Non-versioned routes pass through unchanged. Each versioned route is
shallow-copied with its `path_format` suffixed by `:<version>`, so `get_openapi`
treats same-path versions as separate paths within one call — a single call is
required so FastAPI disambiguates same-named-but-different Pydantic models across
versions.

The function returns the exact set of suffixed paths, so downstream
post-processing matches versioned paths by identity rather than by sniffing for a
colon (a non-versioned path may legitimately contain one, e.g. `/x:action`).

## Collapse back onto the real path — `_collapse_versioned_paths`

A pure `(raw_paths, versioned_paths, vendor_media_type) -> paths` transform.
Non-versioned paths pass through. For each suffixed path it splits off the
`:<version>`, rewrites every operation's `requestBody` content key to
`<vendor>; version=<major>.<minor>`, and merges the per-version operations back
under the clean path via `helpers.dict_merge`. Operation-level fields
(parameters, summary, tags) come from the first-merged version, so versions of
one path+method should differ only in body schema.

Only **request** bodies are rewritten here. Response content-type versioning comes
from each route's `VersionedJSONResponse.media_type` (see
[accept-header-version-negotiation.md](accept-header-version-negotiation.md)),
which `get_openapi` reads directly — so the response side needs no rewrite.

## Caching

`_custom_openapi` caches its result in `app.openapi_schema` and returns the cached
value on later calls, matching FastAPI's own generate-once behavior.
