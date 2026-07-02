# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`fast-version` adds Accept-header-based API versioning to FastAPI. Clients select a
route version via `Accept: <vendor-media-type>; version=<major>.<minor>` (e.g.
`application/vnd.some.name+json; version=2.0`). Multiple endpoints can share the same
path+method but differ by version. Public API is just two names exported from
`fast_version/__init__.py`: `VersionedAPIRouter` and `init_fastapi_versioning`.

## Commands

Uses `uv` and `just`. `uv.lock` is git-ignored here (see `.gitignore`), so it is not
committed; `just install` regenerates it via `uv lock --upgrade`.

```bash
just install    # uv lock --upgrade + uv sync --all-extras --all-groups --frozen
just lint       # ruff format, ruff check --fix, mypy (mutates files)
just lint-ci    # same checks, no mutation (--check / --no-fix)
just test       # uv run pytest (coverage is on by default via addopts)
just            # default recipe: install, lint, test
```

Run a single test: `just test tests/test_app.py::test_get` or
`uv run pytest -k test_openapi_schema`.

## Workflow

Planning follows the convention in [`planning/README.md`](planning/README.md) —
its **Quick path** is authoritative. Pick a lane (Full = `design.md` + `plan.md`,
Lightweight = `change.md`, Tiny = conventional commit) and create a bundle under
`planning/changes/YYYY-MM-DD.NN-<slug>/`. In this repo the superpowers
brainstorming/writing-plans flow writes specs and plans **into that bundle**, not
into `docs/superpowers/`. Run `just check-planning` before pushing.

## Architecture

> **Promotion rule:** when a change alters a capability's behavior, update the
> matching `architecture/<capability>.md` in the same PR (see
> `architecture/README.md`).

Versioning is implemented across three layers that cooperate through the ASGI
`scope["version"]` key:

1. **Middleware parses the Accept header** (`fast_version/app.py`,
   `FastAPIVersioningMiddleware`). It only acts when the media type before `;`
   matches the configured `VENDOR_MEDIA_TYPE`; otherwise it passes through
   untouched (so `*/*`, `application/json`, missing/other media types are ignored,
   defaulting to v1.0). When it matches, it parses `version=X.Y`, validates against
   `_VERSION_RE` (`^\d\.\d$`), and writes the parsed tuple into `scope["version"]`.
   Malformed version key -> 400 "No version in Accept header"; malformed version
   value -> 400 "Version should be in <major>.<minor> format".

2. **Route matching selects the endpoint by version** (`fast_version/router.py`,
   `VersionedAPIRoute.matches`). Starlette calls `matches` on each route; this
   override returns `Match.FULL` only when `scope["version"]` (default `(1, 0)`)
   equals the route's own version. A path+method with no matching version yields
   405. Version is stored as a `version` attribute on the endpoint function:
   `VersionedAPIRouter.api_route` sets `DEFAULT_VERSION` (1, 0) if absent, and the
   `set_api_version((maj, min))` decorator overrides it. The response's
   `content-type` is set to the vendor media type + resolved version via a
   dynamically-generated `VersionedJSONResponse` using the `ClassProperty` descriptor.

3. **OpenAPI schema is rebuilt to avoid version collisions** (`fast_version/app.py`,
   `_custom_openapi`, monkey-patched onto `app.openapi`). Because multiple routes
   share a path, it temporarily suffixes each versioned route's `path_format` with
   `:<version>` so `get_openapi` does not merge them, then splits the suffix back
   off and merges the per-version schemas under the clean path (via
   `helpers.dict_merge`), rewriting request/response `content` keys to include
   `; version=X.Y`.

`init_fastapi_versioning(app=, vendor_media_type=)` wires all three: it sets the
class-level `VENDOR_MEDIA_TYPE`, adds the middleware, and swaps in `_custom_openapi`.

### Key constraints

- `VENDOR_MEDIA_TYPE` is **class-level state** on `VersionedAPIRouter`, set globally
  by `init_fastapi_versioning`. There is effectively one vendor media type per process.
- Version format is strictly single-digit `major.minor` (the regex is `\d\.\d`, not
  `\d+`). Widening it means changing `_VERSION_RE`.
- Define versioned endpoints with `VersionedAPIRouter`; the highest/oldest default
  (no `set_api_version`) is v1.0. Order in tests: the plain route is v1.0, extra
  versions are stacked with `@ROUTER.set_api_version((maj, min))` above the endpoint.

## Conventions

- Ruff with `select = ["ALL"]` (line length 120), mypy `strict`. Both must pass;
  CI runs `lint-ci` plus pytest across Python 3.10-3.14 via the shared
  `community-of-python/community-workflow` reusable workflow.
- `type: ignore` (not `ty: ignore`) is used here since the type checker is mypy.
- Tests are ASGI integration tests using `starlette.testclient.TestClient`;
  `asyncio_mode = "auto"`. Fixtures/endpoints live in `tests/conftest.py`.