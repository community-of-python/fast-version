# OpenAPI Versioning Fix (FastAPI 0.139+) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore correct multi-version OpenAPI schema generation under FastAPI 0.139 / Starlette 1.3.1, where `app.include_router` hides routes inside an opaque `_IncludedRouter` and `get_openapi` no longer honors mutated `path_format`.

**Architecture (revised to Option A during execution):** Adapt the original single-call `_custom_openapi` to FastAPI 0.139. Enumerate routes via `fastapi.routing.iter_route_contexts` (finds routes nested in included routers, with effective prefixed paths), shallow-copy each versioned route with its `path_format` suffixed by `:<version>`, and pass them all through ONE `get_openapi` call. Post-process by splitting the `:<version>` suffix, rewriting request-body media types, and merging per-version paths with `helpers.dict_merge`. A single call is required so FastAPI disambiguates same-named-but-different models across versions — the per-version variant originally drafted here regressed that case (see the fix commit and updated spec).

**Tech Stack:** Python 3.10+, FastAPI 0.139, Starlette 1.3, pytest / pytest-asyncio, ruff (ALL), mypy strict, uv + just.

## Global Constraints

- Python floor: `requires-python = ">=3.10,<4"`; mypy `python_version = 3.10`, ruff `target-version = py310`. Code must run on 3.10.
- Lint must pass `just lint-ci`: `ruff format --check`, `ruff check --no-fix`, `mypy .` (strict).
- Type-checker is **mypy**: suppress with `# type: ignore[...]` (not `# ty: ignore`).
- All function arguments annotated; all imports at module level.
- Line length 120.
- `uv.lock` is git-ignored in this repo — never stage it.
- The `httpx` -> `httpx2` dev-dependency swap in `pyproject.toml` is intentional and kept.
- Do not change runtime request routing (`FastAPIVersioningMiddleware`, `VersionedAPIRoute.matches`) or widen the `\d\.\d` version format.

---

## Preliminary: branch

- [ ] **Step 0: Create a feature branch** (currently on `main`; never commit the fix to `main`).

```bash
git checkout -b fix/openapi-versioning-fastapi-0139
```

---

### Task 1: Per-version OpenAPI schema generation

Replace the broken `_custom_openapi` mechanism. Add a route-enumeration helper that
finds versioned routes even when nested inside an included router, and rebuild the
schema per version. This is the core fix.

**Files:**
- Modify: `fast_version/app.py` (imports; add `_collect_route_contexts`; rewrite `_custom_openapi`)
- Test: `tests/test_app.py` (add helper test + prefixed-router integration test; existing `test_openapi_schema` already covers the no-prefix case)

**Interfaces:**
- Produces: `_collect_route_contexts(app: fastapi.FastAPI) -> tuple[list[RouteContext], dict[tuple[int, int], list[RouteContext]]]` — returns `(non_versioned_contexts, versioned_contexts_by_version)`. `RouteContext` is `fastapi.routing.RouteContext`.
- Produces: `_custom_openapi(self: fastapi.FastAPI) -> dict[str, typing.Any]` — unchanged signature; still bound onto `app.openapi` by `init_fastapi_versioning`.
- Consumes: `helpers.dict_merge` (existing), `VersionedAPIRoute.version` (existing property returning `tuple[int, int]`).

- [ ] **Step 1: Add the failing tests**

Add these imports at the top of `tests/test_app.py` (below the existing imports):

```python
import fastapi

from fast_version import init_fastapi_versioning
from fast_version.app import _collect_route_contexts
from tests.conftest import VERSIONED_ROUTER_OBJ
```

Append these two tests to `tests/test_app.py`:

```python
async def test_collect_route_contexts_finds_versioned_routes_behind_prefix() -> None:
    app = fastapi.FastAPI()
    init_fastapi_versioning(app=app, vendor_media_type=VERSION_HEADER)
    app.include_router(VERSIONED_ROUTER_OBJ, prefix="/api")

    _, versioned = _collect_route_contexts(app)

    assert set(versioned.keys()) == {(1, 0), (2, 0), (1, 1)}


async def test_openapi_schema_with_prefix() -> None:
    amount_of_versions: typing.Final = 2

    app = fastapi.FastAPI()
    init_fastapi_versioning(app=app, vendor_media_type=VERSION_HEADER)
    app.include_router(VERSIONED_ROUTER_OBJ, prefix="/api")
    client = TestClient(app=app)

    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    paths: dict[str, typing.Any] = response.json()["paths"]
    assert "/api/test/" in paths
    assert len(paths["/api/test/"]["get"]["responses"]["200"]["content"]) == amount_of_versions
    assert len(paths["/api/test/"]["post"]["responses"]["200"]["content"]) == amount_of_versions
    assert len(paths["/api/test/"]["post"]["requestBody"]["content"]) == amount_of_versions
```

- [ ] **Step 2: Run the new + existing OpenAPI tests to confirm they fail**

Run: `uv run pytest tests/test_app.py -k "openapi or collect_route_contexts" -v`
Expected: `test_collect_route_contexts_finds_versioned_routes_behind_prefix` FAILS with `ImportError`/`AttributeError` (`_collect_route_contexts` does not exist yet); `test_openapi_schema` and `test_openapi_schema_with_prefix` FAIL on the content-length assertions (`assert 1 == 2`) because versions collapse under FastAPI 0.139.

- [ ] **Step 3: Update imports in `fast_version/app.py`**

Replace the current import block. Remove the now-unused `copy` import and the `starlette.responses.JSONResponse` import is still needed by the middleware — keep it. Add the `fastapi.routing` imports. The full import block becomes:

```python
import contextlib
import re
import typing
from types import MethodType

import fastapi
from fastapi.openapi.utils import get_openapi
from fastapi.routing import RouteContext, iter_route_contexts
from starlette import types
from starlette.responses import JSONResponse

from fast_version import helpers
from fast_version.router import VersionedAPIRoute, VersionedAPIRouter
```

(Versus the original imports, this drops `import copy` — the old hack used `copy.copy` — and adds the `fastapi.routing` line. After the rewrite, verify `copy` no longer appears anywhere in `app.py`.)

- [ ] **Step 4: Add the `_collect_route_contexts` helper**

Insert this function into `fast_version/app.py` immediately above `_custom_openapi`:

```python
def _collect_route_contexts(
    app: fastapi.FastAPI,
) -> tuple[list[RouteContext], dict[tuple[int, int], list[RouteContext]]]:
    """Split app routes into non-versioned contexts and versioned contexts grouped by version.

    Traverses nested routers (FastAPI wraps included routers in an opaque object), so
    routes added via ``app.include_router`` are found and keep their effective paths.
    """
    non_versioned: list[RouteContext] = []
    versioned: dict[tuple[int, int], list[RouteContext]] = {}
    for route_context in iter_route_contexts(app.routes):
        original_route = route_context.original_route
        if isinstance(original_route, VersionedAPIRoute):
            versioned.setdefault(original_route.version, []).append(route_context)
        else:
            non_versioned.append(route_context)
    return non_versioned, versioned
```

- [ ] **Step 5: Rewrite `_custom_openapi`**

Replace the entire existing `_custom_openapi` function body with:

```python
def _custom_openapi(self: fastapi.FastAPI) -> dict[str, typing.Any]:
    if self.openapi_schema:
        return self.openapi_schema

    non_versioned, versioned = _collect_route_contexts(self)

    def build(routes: list[RouteContext]) -> dict[str, typing.Any]:
        return get_openapi(
            title=self.title,
            version=self.version,
            openapi_version=self.openapi_version,
            summary=self.summary,
            description=self.description,
            terms_of_service=self.terms_of_service,
            contact=self.contact,
            license_info=self.license_info,
            routes=routes,
            webhooks=self.webhooks.routes,
            tags=self.openapi_tags,
            servers=self.servers,
        )

    schema = build(non_versioned)
    vendor_media_type = _get_vendor_media_type()
    for version, route_contexts in versioned.items():
        version_str = ".".join(str(part) for part in version)
        version_schema = build(route_contexts)
        for methods in version_schema["paths"].values():
            for payload in methods.values():
                if "requestBody" not in payload:
                    continue
                payload["requestBody"]["content"] = {
                    f"{vendor_media_type}; version={version_str}": content
                    for content in payload["requestBody"]["content"].values()
                }
        helpers.dict_merge(schema, version_schema)

    self.openapi_schema = schema
    return self.openapi_schema
```

Rationale for each piece:
- Response `content` keys are already correct per version because `VersionedJSONResponse.media_type` bakes in `; version=X.Y`; only `requestBody` content (default `application/json`) needs rewriting, and it is rewritten only inside per-version schemas (never on the non-versioned base), so non-versioned request bodies are untouched.
- `helpers.dict_merge` merges paths and components across versions; shared model schemas with identical content merge cleanly.
- Caching on `self.openapi_schema` preserves the second-call behavior asserted by `test_openapi_schema`.

- [ ] **Step 6: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS, `18 passed` (16 existing + 2 new). Coverage on `fast_version/app.py` should be 100%.

- [ ] **Step 7: Run linters**

Run: `uv run ruff format fast_version/app.py tests/test_app.py --check && uv run ruff check fast_version tests --no-fix && uv run mypy .`
Expected: all pass, `Success: no issues found`. If `ruff format --check` reports a diff, run `uv run ruff format .` and re-run.

- [ ] **Step 8: Commit**

```bash
git add fast_version/app.py tests/test_app.py
git commit -m "fix: rebuild OpenAPI schema per version for FastAPI 0.139+

include_router now hides routes in an opaque _IncludedRouter and get_openapi
ignores mutated path_format, collapsing same-path versioned routes. Enumerate
routes via iter_route_contexts and build one schema per version, then merge."
```

---

### Task 2: ~~Remove dead `version_str` property~~ — DROPPED

This task is no longer applicable. It assumed the per-version approach (Option 2),
which stopped using `VersionedAPIRoute.version_str`. The chosen Option A reuses
`version_str` to build the `:<version>` path suffix, so the property is live and must
stay. No action.

---

### Task 3: Keep the intended dependency swap

The staged `httpx` -> `httpx2` dev-dependency change is intentional (per user) and
unrelated to the bug. Commit it separately so history is clean.

**Files:**
- Modify: `pyproject.toml` (already staged as `M`, line 33: `"httpx"` -> `"httpx2"`)

- [ ] **Step 1: Confirm the diff is only the dev-dependency swap**

Run: `git diff pyproject.toml`
Expected: single line change under `[dependency-groups].dev`, `- "httpx"` / `+ "httpx2"`. Nothing else.

- [ ] **Step 2: Verify the full CI-equivalent locally**

Run: `uv run ruff format . --check && uv run ruff check . --no-fix && uv run mypy . && uv run pytest -q`
Expected: all green, `18 passed`. This mirrors `just lint-ci` + `just test`.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore(deps): switch dev dependency httpx -> httpx2"
```

---

### Task 4: Push and open PR

- [ ] **Step 1: Push the branch**

```bash
git push -u origin fix/openapi-versioning-fastapi-0139
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --fill --title "Fix OpenAPI versioning under FastAPI 0.139+"
```

Include in the body: the root cause (include_router now hides routes in `_IncludedRouter`; `get_openapi` ignores mutated `path_format`), the per-version-merge fix, added prefixed-router coverage, and that the `httpx2` dev-dep swap rides along.

- [ ] **Step 3: Watch CI**

Run: `gh pr checks --watch`
Expected: the reusable `community-of-python/community-workflow` matrix (Python 3.10-3.14) passes. If a specific Python version fails, reproduce locally with that interpreter before pushing a fix.

---

## Notes / follow-ups (not blocking)

- `CLAUDE.md` (untracked) currently states `uv.lock` is committed here; it is actually git-ignored. Correct that line when `CLAUDE.md` is next touched — out of scope for this branch.
- The route-enumeration in `_collect_route_contexts` depends on FastAPI internals (`iter_route_contexts` / `RouteContext`). `test_collect_route_contexts_finds_versioned_routes_behind_prefix` is the canary: if a future FastAPI bump breaks enumeration, that test fails loudly and locally.
