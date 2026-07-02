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

> **SUPERSEDED — implemented as Option A (single-call).** The step-by-step
> per-version implementation originally drafted here was rejected during review: one
> `get_openapi` call per version prevents FastAPI from disambiguating
> same-named-but-different Pydantic models across versions, silently corrupting such
> schemas. The shipped implementation (single `get_openapi` call over a flat route
> list with `:<version>`-suffixed paths) is described below and lives in commits
> `6d5f68e` (core fix) and `7c2598a` (exact-path-match robustness). See the updated
> spec for the full rationale.

**Files (as shipped):**
- Modify: `fast_version/app.py` (imports add `copy`, `fastapi.routing.{RouteContext, iter_route_contexts}`, `starlette.routing.BaseRoute`; add `_iter_openapi_routes`; rewrite `_custom_openapi`).
- Test: `tests/test_app.py` (four new tests, see below).

**Interfaces (as shipped):**
- `_iter_openapi_routes(app: fastapi.FastAPI) -> tuple[list[BaseRoute | RouteContext], set[str]]` — returns `(routes, versioned_suffixed_paths)`. Non-versioned routes pass through as `RouteContext`; each versioned route is a `copy.copy` with `path_format` set to `f"{route_context.path_format}:{original_route.version_str}"`. The returned set holds those suffixed paths for exact-match identification during post-processing.
- `_custom_openapi(self: fastapi.FastAPI) -> dict[str, typing.Any]` — unchanged signature; still bound onto `app.openapi` by `init_fastapi_versioning`. Makes ONE `get_openapi` call over `_iter_openapi_routes(self)[0]`, then for each generated path in the versioned-paths set: `rsplit(":", 1)` into `clean_path` + `version_str`, rewrite `requestBody.content` keys to `<vendor>; version=X.Y`, and merge onto `clean_path` (first occurrence direct, later via `helpers.dict_merge`). Non-versioned paths pass through untouched. Caches on `self.openapi_schema`.
- Consumes: `helpers.dict_merge`, `VersionedAPIRoute.version`/`version_str` (both stay).

**Tests (as shipped):**
- Existing `test_openapi_schema` (no-prefix, both versions in get/post response + post requestBody) — still passes.
- `test_iter_openapi_routes_finds_prefixed_versioned_paths` — with `prefix="/api"`, the returned set and the copies' `path_format`s are `{"/api/test/:1.0", "/api/test/:2.0", "/api/test/:1.1"}`.
- `test_openapi_schema_with_prefix` — prefixed router exposes both versions at `/api/test/`.
- `test_openapi_schema_distinct_models_with_shared_name_across_versions` — regression guard for the single-call requirement (distinct `$ref`s + correct per-version properties for two same-named models).
- `test_openapi_schema_preserves_non_versioned_path_with_colon` — a non-versioned `/resource:activate` keeps its `application/json` body (colon not mistaken for a version suffix).

**TDD note:** the existing `test_openapi_schema` was already RED under FastAPI 0.139; the model and colon regression tests were confirmed RED against the pre-fix code before implementing. Final state: 20 passed, ruff/mypy strict clean, 100% coverage on `app.py` and `router.py`.

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
