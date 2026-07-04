# Glossary

The project's ubiquitous language — the domain terms that code, specs, and
capability pages share. Living prose, no frontmatter, dated by git.

**Vendor media type**:
The base media type a deployment configures to signal versioned requests, e.g.
`application/vnd.some.name+json`. Passed once to `init_fastapi_versioning` and
matched case-insensitively against the request's `Accept` media type.
_Avoid_: content type (too generic), MIME type

**Version**:
A `(major, minor)` pair identifying one API version, each a single digit
(`0`-`9`). Written `major.minor` on the wire (`version=2.0`).
_Avoid_: revision, API level

**Default version**:
`(1, 0)` — the version a request resolves to when it selects none (no `Accept`
header, a non-vendor media type, or a vendor media type with no `version`
parameter). Owned by `accept.DEFAULT_VERSION`.

**Versioned route**:
A route registered through `VersionedAPIRouter`, carrying its own version.
Several versioned routes may share the same path and method, differing only by
version; the router selects among them by the request's resolved version.
_Avoid_: endpoint (reserve for the handler function)

**Accept-header negotiation**:
Resolving which versioned route serves a request from its `Accept` header. Spans
three cooperating layers — parse, match, respond — joined by the ASGI
`scope["version"]` key.
_Avoid_: content negotiation (broader HTTP concept)

**Resolved version**:
The `(major, minor)` written into `scope["version"]` by the middleware after a
successful parse, or the default when the middleware leaves it unset. What
route matching compares against.
