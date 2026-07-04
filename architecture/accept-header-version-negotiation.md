# Accept-header version negotiation

How a client selects a route version, and how the library resolves and serves
it. A client sends `Accept: <vendor-media-type>; version=<major>.<minor>` (e.g.
`application/vnd.some.name+json; version=2.0`); the library routes to the
matching versioned route and stamps the response `content-type` with the
resolved version.

Three layers cooperate through the ASGI `scope["version"]` key: **parse** (the
middleware), **match** (the route), **respond** (the response class).

## Parse — `fast_version/accept.py`

`FastAPIVersioningMiddleware` extracts the `Accept` header (lowercased, stripped
by `get_accept_header_from_scope`) and calls the pure
`parse_accept_version(accept_header, vendor_media_type)`, which returns a sealed
result:

- **`Ignore`** — the request selects no version, so the middleware leaves
  `scope["version"]` unset and the default applies downstream. Produced for an
  empty or `*/*` header, a header that does not split into exactly one `;`, or a
  media type that is not the vendor media type. Media-type comparison is
  case-insensitive (the vendor is lowercased to match the already-lowercased
  header — RFC 9110 §8.3.1, RFC 6838 §4.2).
- **`ParsedVersion((major, minor))`** — a valid `version=X.Y`. The middleware
  writes the tuple into `scope["version"]`.
- **`ParseError(detail)`** — the middleware returns a 400 with that detail. Two
  cases: a missing or misnamed version key → `"No version in Accept header"`; a
  value that fails `^\d\.\d$` → `"Version should be in <major>.<minor> format"`.

The parse is pure and holds all string-level rules; the middleware keeps only the
ASGI concerns (the `scope["type"] == "http"` guard, header extraction, and
mapping the result onto `scope`/a 400 response).

## Match — `fast_version/router.py`

Each versioned route is a `VersionedAPIRoute`. Starlette calls `matches` on every
route; the override returns `Match.FULL` only when the request's resolved version
(`scope.get("version", accept.DEFAULT_VERSION)`) equals the route's own version,
and `Match.NONE` otherwise. So several routes can share a path and method,
distinguished only by version; a request whose version matches none of them
yields 405.

A route's version lives as a `version` attribute on the endpoint function.
`VersionedAPIRouter.api_route` defaults it to `DEFAULT_VERSION` when absent, and
the `set_api_version((major, minor))` decorator overrides it. (Version is carried
on the function rather than passed as a route keyword — a deliberate choice
constrained by FastAPI's closed verb-method signatures; see
`planning/decisions/2026-07-04-version-stays-a-function-decorator.md`.)

## Respond — `fast_version/router.py`

Each versioned route gets a per-route `VersionedJSONResponse` whose `media_type`
resolves to `<vendor>; version=<major>.<minor>`, so the response `content-type`
carries the served version. The vendor part is read lazily at access time via the
`ClassProperty` descriptor, which decouples when the vendor is configured from
when routes are registered (see
`planning/decisions/2026-07-04-classproperty-stays-for-ordering-independence.md`).

## Configuration

`init_fastapi_versioning(app=, vendor_media_type=)` wires the three layers: it
sets the class-level `VENDOR_MEDIA_TYPE`, adds the middleware, and swaps in the
custom OpenAPI generator. The vendor media type is process-global class state —
one vendor per process (see
`planning/decisions/2026-07-04-vendor-media-type-stays-process-global.md`).
