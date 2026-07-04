---
summary: Extract Accept-header version parsing out of the middleware into a deep fast_version/accept.py module with a sealed-result interface, testable at its own seam.
---

# Extract the Accept-header version parse into a deep module

## Summary

The logic that turns a request's `Accept` header into a version tuple lives
inline in `FastAPIVersioningMiddleware.__call__`, expressed as a
`while True: ... break` loop that mixes ASGI plumbing with string parsing.
Today the only way to exercise a parse edge case is a full `TestClient`
round-trip. This change lifts the parse into a new `fast_version/accept.py`
module — the sole owner of "what a version is and how the `Accept` header
selects one" — behind a small pure interface returning a sealed result
(`Ignore | ParsedVersion | ParseError`). The middleware keeps only the ASGI
scope-type check and header extraction, then maps the result onto
`scope["version"]` or a 400. Behavior is preserved exactly.

## Motivation

`fast_version/app.py` — `FastAPIVersioningMiddleware.__call__`:

- The parse is a shallow-interfaced, un-seamed body: media-type matching,
  `;`/`=` splitting, version-key validation, regex validation, and defaulting
  all sit inside one ASGI method. The interface (an ASGI `__call__`) is nearly
  as wide as the implementation.
- Every parse edge case is tested through the ASGI layer:
  `test_no_version`, the 8-case parametrized `test_invalid_version`,
  `test_bad_accept_header_default_response`,
  `test_auto_version_when_no_version_provided` all spin up a full app to
  exercise a string split.
- Version knowledge is smeared across files: `_VERSION_RE` in `app.py`,
  `get_accept_header_from_scope` in the generic `helpers.py`, `DEFAULT_VERSION`
  in `router.py`. No single module answers "what is a version, what's valid,
  what's the default."

Deletion test on the inlined parse: extracting it concentrates the parsing
complexity behind one interface rather than moving it — the signal to deepen.

## Non-goals

- No behavior change. Multi-semicolon → `Ignore` and the lowercased-header
  comparison are preserved as-is.
- No fix to the vendor case-sensitivity quirk (see Risk / `deferred.md`) — it
  gets its own TDD change once the seam exists.
- No change to `VersionedAPIRoute.matches`. Matching a request's version
  against a route's version is routing's job and stays in `router.py`.
- No change to the public API (`VersionedAPIRouter`, `init_fastapi_versioning`).
  `parse_accept_version` is internal.

## Design

### 1. New module `fast_version/accept.py`

Sole owner of Accept-header version negotiation. Absorbs `_VERSION_RE` (from
`app.py`), `get_accept_header_from_scope` (from `helpers.py`), and
`DEFAULT_VERSION` (from `router.py`).

```python
import dataclasses
import re
import typing

from starlette import datastructures, types


_VERSION_RE: typing.Final = re.compile(r"^\d\.\d$")
DEFAULT_VERSION: typing.Final = (1, 0)


@dataclasses.dataclass(frozen=True, slots=True)
class Ignore:
    """Passthrough: the request selects no version; the downstream default applies."""


@dataclasses.dataclass(frozen=True, slots=True)
class ParsedVersion:
    version: tuple[int, int]


@dataclasses.dataclass(frozen=True, slots=True)
class ParseError:
    detail: str


AcceptVersion: typing.TypeAlias = Ignore | ParsedVersion | ParseError


def get_accept_header_from_scope(scope: types.Scope) -> str:
    headers = datastructures.Headers(scope=scope)
    return headers.get("Accept", "").strip().lower()


def parse_accept_version(accept_header: str, vendor_media_type: str) -> AcceptVersion:
    ...
```

`parse_accept_version` owns steps 3-7 of today's middleware, in order,
preserving each outcome exactly:

1. Empty header or `*/*` → `Ignore`.
2. `accept_header.split(";")` does not yield exactly two parts (0 or 2+
   semicolons) → `Ignore`.
3. `media_type.strip() != vendor_media_type` → `Ignore`.
4. The value part does not split into exactly `key=value`, or
   `key.lower().strip() != "version"` → `ParseError("No version in Accept header")`.
5. `_VERSION_RE` does not match the value → `ParseError("Version should be in
   <major>.<minor> format")`.
6. Otherwise → `ParsedVersion((major, minor))`.

The function is pure: no `scope`, no Starlette response types, no class-level
global. `vendor_media_type` is a plain argument.

### 2. Middleware becomes thin ASGI glue

`FastAPIVersioningMiddleware.__call__` keeps only the ASGI scope-type check and
header extraction, then `match`es the parse result:

```python
async def __call__(self, scope, receive, send) -> None:
    if scope["type"] == "http":
        header = accept.get_accept_header_from_scope(scope)
        result = accept.parse_accept_version(header, VersionedAPIRouter.VENDOR_MEDIA_TYPE)
        match result:
            case accept.ParsedVersion(version):
                scope["version"] = version
            case accept.ParseError(detail):
                response = JSONResponse({"detail": detail}, status_code=400)
                return await response(scope, receive, send)
            case accept.Ignore():
                pass
    return await self.app(scope, receive, send)
```

The `while True: ... break` loop, `contextlib.suppress`, and `_get_vendor_media_type`
usage in the middleware are gone. (`_get_vendor_media_type` remains only if
still used by `_custom_openapi`; it is — leave it.)

### 3. Downstream owners updated

- `router.py`: delete the local `DEFAULT_VERSION` and import it from
  `fast_version.accept`. `VersionedAPIRoute.matches` keeps
  `scope.get("version", accept.DEFAULT_VERSION)`.
- `helpers.py`: delete `get_accept_header_from_scope` (moved to `accept.py`).
  `dict_merge` and `ClassProperty` stay.
- `app.py`: delete `_VERSION_RE`, import `accept`, drop the inlined parse.

No import cycle: `accept.py` depends only on `starlette`/stdlib; `app.py` and
`router.py` import `accept`.

## Testing

- **New `tests/test_accept.py`** — exhaustive, pure unit tests on
  `parse_accept_version`, no `TestClient`:
  - `Ignore`: `""`, `"*/*"`, no-semicolon (`vendor` alone),
    multi-semicolon (`vendor; version=1.0; charset=utf-8`), wrong vendor.
  - `ParsedVersion`: `1.0`, `2.0` → `(1, 0)`, `(2, 0)`.
  - `ParseError("No version in Accept header")`: `vendor; vers1.1`,
    `vendor; vers=1.1`.
  - `ParseError("Version should be in <major>.<minor> format")`: the 8-case
    parametrized list from today's `test_invalid_version`
    (`"", "test", "0,.1", "0,1", "0,1,1", "0-1", "0/1", "1-1"`).
  - Assertions compare whole result values (frozen dataclass `__eq__`), e.g.
    `assert parse_accept_version("*/*", VENDOR) == Ignore()`.
- **`tests/test_app.py`** — thinned to one round-trip per outcome, proving the
  middleware wires parse → `scope`/`JSONResponse`: keep a 200-with-version,
  a 400-no-version, a 400-bad-format, and a passthrough-default assertion.
  Remove the exhaustive enumeration now covered at the parse seam.
- `just test-ci` — coverage stays at `--cov-fail-under=100`. Parse branch
  lines are covered by `test_accept.py`; the four middleware-mapping branches
  by the retained round-trips.
- `just lint-ci` — ruff `select = ["ALL"]` and `ty` clean; `just check-planning`.

## Risk

- **Coverage regression (medium likelihood, low impact).** Thinning
  `test_app.py` while adding `test_accept.py` could drop a covered middleware
  branch. Mitigation: the four retained round-trips map 1:1 to the four
  `match` arms; run `just test-ci` before pushing.
- **Behavior drift in the split logic (low likelihood, high impact).** The
  multi-semicolon and lowercase-comparison quirks are easy to "tidy" away.
  Mitigation: `test_accept.py` pins them explicitly as `Ignore`/comparison
  cases; the change is behavior-preserving by contract.
- **Deferred: vendor case-sensitivity.** The comparison runs a lowercased
  header media-type against a non-lowercased `vendor_media_type`; a mixed-case
  vendor silently never matches. Recorded in `deferred.md` as a follow-up TDD
  fix, cheap to write once the seam exists.
