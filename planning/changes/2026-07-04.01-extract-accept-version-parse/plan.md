# extract-accept-version-parse — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Accept-header version parsing into a pure `fast_version/accept.py`
module with a sealed-result interface, testable at its own seam, preserving
behavior.

**Spec:** [`design.md`](./design.md)

**Branch:** `refactor/extract-accept-version-parse`

**Commit strategy:** Per-task commits.

## Global constraints

- Python 3.10-3.14; `match`/`|` unions available.
- Ruff `select = ["ALL"]`, line length 120, and `ty` must pass (`just lint-ci`).
- Use `ty: ignore`, never `type: ignore`.
- All imports at module level; annotate all function arguments.
- Coverage gate: `just test-ci` runs `--cov-fail-under=100`. Every task's
  commit must leave the suite green at 100%.
- Behavior-preserving: no route, response, or error-message change.

---

### Task 1: Create the `accept.py` parse module (TDD)

**Files:**
- Create: `fast_version/accept.py`
- Create: `tests/test_accept.py`

**Interfaces produced (later tasks rely on these exact names/types):**
- `fast_version.accept.Ignore` — frozen dataclass, no fields.
- `fast_version.accept.ParsedVersion(version: tuple[int, int])` — frozen dataclass.
- `fast_version.accept.ParseError(detail: str)` — frozen dataclass.
- `fast_version.accept.AcceptVersion` — `Ignore | ParsedVersion | ParseError`.
- `fast_version.accept.DEFAULT_VERSION: tuple[int, int] = (1, 0)`.
- `fast_version.accept.get_accept_header_from_scope(scope) -> str`.
- `fast_version.accept.parse_accept_version(accept_header: str, vendor_media_type: str) -> AcceptVersion`.

This task adds the new module and its unit tests. Old copies of
`get_accept_header_from_scope` (helpers), `_VERSION_RE` (app), and
`DEFAULT_VERSION` (router) remain in place until later tasks — temporary
duplication, suite stays green.

- [ ] **Step 1: Write the failing tests**

  Create `tests/test_accept.py`:

  ```python
  import typing

  import pytest

  from fast_version.accept import (
      Ignore,
      ParsedVersion,
      ParseError,
      get_accept_header_from_scope,
      parse_accept_version,
  )


  VENDOR: typing.Final = "application/vnd.some.name+json"


  @pytest.mark.parametrize(
      "header",
      [
          "",
          "*/*",
          VENDOR,  # no semicolon -> split yields one part
          f"{VENDOR}; version=1.0; charset=utf-8",  # two semicolons
          "application/vnd.wrong+json; version=1.0",  # wrong vendor
      ],
  )
  def test_parse_ignore(header: str) -> None:
      assert parse_accept_version(header, VENDOR) == Ignore()


  @pytest.mark.parametrize(
      ("header", "expected"),
      [
          (f"{VENDOR}; version=1.0", (1, 0)),
          (f"{VENDOR}; version=2.0", (2, 0)),
      ],
  )
  def test_parse_version(header: str, expected: tuple[int, int]) -> None:
      assert parse_accept_version(header, VENDOR) == ParsedVersion(version=expected)


  @pytest.mark.parametrize(
      "header",
      [f"{VENDOR}; vers1.1", f"{VENDOR}; vers=1.1"],
  )
  def test_parse_missing_version_key(header: str) -> None:
      assert parse_accept_version(header, VENDOR) == ParseError(detail="No version in Accept header")


  @pytest.mark.parametrize(
      "version",
      ["", "test", "0,.1", "0,1", "0,1,1", "0-1", "0/1", "1-1"],
  )
  def test_parse_bad_version_format(version: str) -> None:
      result = parse_accept_version(f"{VENDOR}; version={version}", VENDOR)
      assert result == ParseError(detail="Version should be in <major>.<minor> format")


  def test_get_accept_header_from_scope_normalizes() -> None:
      scope: typing.Final = {"type": "http", "headers": [(b"accept", b"  Foo/Bar  ")]}
      assert get_accept_header_from_scope(scope) == "foo/bar"


  def test_get_accept_header_from_scope_missing() -> None:
      assert get_accept_header_from_scope({"type": "http", "headers": []}) == ""
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `uv run pytest tests/test_accept.py -q`
  Expected: FAIL — `ModuleNotFoundError: No module named 'fast_version.accept'`.

- [ ] **Step 3: Create the module**

  Create `fast_version/accept.py`:

  ```python
  import contextlib
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
      if not accept_header or accept_header == "*/*":
          return Ignore()

      try:
          media_type, version_str = accept_header.split(";")
      except ValueError:
          return Ignore()

      if media_type.strip() != vendor_media_type:
          return Ignore()

      version_key = ""
      version = ""
      with contextlib.suppress(ValueError):
          version_key, version = version_str.strip().split("=")

      if version_key.lower().strip() != "version":
          return ParseError(detail="No version in Accept header")

      if not _VERSION_RE.match(version):
          return ParseError(detail="Version should be in <major>.<minor> format")

      major_str, minor_str = version.split(".")
      return ParsedVersion(version=(int(major_str), int(minor_str)))
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `uv run pytest tests/test_accept.py -q`
  Expected: PASS (all cases).

- [ ] **Step 5: Lint**

  Run: `just lint` then `just lint-ci`
  Expected: clean (ruff + ty).

- [ ] **Step 6: Commit**

  ```bash
  git add fast_version/accept.py tests/test_accept.py
  git commit -m "refactor: add accept.py version-parse module with unit tests"
  ```

---

### Task 2: Rewire the middleware; drop the inline parse

**Files:**
- Modify: `fast_version/app.py` (imports; `FastAPIVersioningMiddleware.__call__`)
- Modify: `fast_version/helpers.py` (remove `get_accept_header_from_scope`)

**Interfaces consumed:** `accept.parse_accept_version`,
`accept.get_accept_header_from_scope`, `accept.Ignore/ParsedVersion/ParseError`.

Middleware now delegates to the parse module. `helpers.get_accept_header_from_scope`
is removed in the same task so it does not become uncovered dead code.

- [ ] **Step 1: Rewrite `FastAPIVersioningMiddleware.__call__`**

  In `fast_version/app.py`, replace the entire `while True: ... break` body of
  `__call__` (currently lines ~35-83) with:

  ```python
      async def __call__(
          self,
          scope: types.Scope,
          receive: types.Receive,
          send: types.Send,
      ) -> None:
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

- [ ] **Step 2: Fix `app.py` imports**

  In `fast_version/app.py`:
  - Delete `import contextlib` and `import re` (no longer used).
  - Delete the module-level `_VERSION_RE = re.compile(...)` line and the
    `_get_vendor_media_type` call inside the old middleware (removed with the body).
  - Add `from fast_version import accept` to the `fast_version` imports.
  - Keep `from fast_version import helpers` (still used by `_custom_openapi`)
    and `_get_vendor_media_type` (still used by `_custom_openapi`).

- [ ] **Step 3: Remove the moved helper**

  In `fast_version/helpers.py`, delete `get_accept_header_from_scope`. Then
  remove the now-unused import: change `from starlette import datastructures, types`
  to delete the line entirely (neither is used by `dict_merge`/`ClassProperty`).
  The file keeps only `import typing`, `dict_merge`, and `ClassProperty`.

- [ ] **Step 4: Run the full suite**

  Run: `just test`
  Expected: PASS — existing `test_app.py` round-trips (get/post/no-version/
  invalid/bad-vendor/auto) still pass unchanged.

- [ ] **Step 5: Coverage + lint**

  Run: `just test-ci` then `just lint-ci`
  Expected: coverage 100%, ruff + ty clean.

- [ ] **Step 6: Commit**

  ```bash
  git add fast_version/app.py fast_version/helpers.py
  git commit -m "refactor: delegate Accept-header parsing to accept.py"
  ```

---

### Task 3: Relocate `DEFAULT_VERSION` to `accept.py`

**Files:**
- Modify: `fast_version/router.py`

Completes the single-owner: the version default now lives beside the version
regex and result types. `VersionedAPIRoute.matches` keeps its behavior.

- [ ] **Step 1: Point router at `accept.DEFAULT_VERSION`**

  In `fast_version/router.py`:
  - Delete `DEFAULT_VERSION: typing.Final = (1, 0)`.
  - Add `from fast_version import accept` to the imports.
  - In `VersionedAPIRoute.matches`, change
    `scope.get("version", DEFAULT_VERSION)` to
    `scope.get("version", accept.DEFAULT_VERSION)`.
  - In `VersionedAPIRouter.api_route`'s decorator, the default assignment
    `setattr(func, "version", DEFAULT_VERSION)` becomes
    `setattr(func, "version", accept.DEFAULT_VERSION)`.

- [ ] **Step 2: Run the full suite**

  Run: `just test`
  Expected: PASS (matching + defaulting unchanged).

- [ ] **Step 3: Coverage + lint**

  Run: `just test-ci` then `just lint-ci`
  Expected: coverage 100%, ruff + ty clean. No import cycle
  (`accept` depends only on starlette/stdlib).

- [ ] **Step 4: Commit**

  ```bash
  git add fast_version/router.py
  git commit -m "refactor: move DEFAULT_VERSION into accept.py"
  ```

---

### Task 4: Thin `test_app.py` to one round-trip per outcome

**Files:**
- Modify: `tests/test_app.py`

Exhaustive parse enumeration now lives in `test_accept.py`. `test_app.py`
retains one round-trip per middleware `match` arm, proving the wiring. OpenAPI
tests (`test_openapi_*`, `test_iter_openapi_routes_*`) are unrelated — leave
them untouched.

- [ ] **Step 1: Reduce the parse round-trips**

  In `tests/test_app.py`:
  - Keep `test_get`, `test_post`, `test_simple_router` unchanged (they cover
    the `ParsedVersion` arm and non-versioned routing).
  - Keep `test_auto_version_when_no_version_provided` unchanged (the `Ignore`
    arm — passthrough default content-type).
  - Delete `test_bad_accept_header_default_response` (a second `Ignore` case,
    now covered exhaustively in `test_accept.py`).
  - Replace `test_no_version` (two requests) with a single-request version:

    ```python
    async def test_no_version(test_client: TestClient) -> None:
        response = test_client.get(
            "/test/",
            headers={"Accept": f"{VERSION_HEADER}; vers=1.1"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {"detail": "No version in Accept header"}
    ```

  - Replace the parametrized `test_invalid_version` (8 cases) with a single
    bad-format round-trip:

    ```python
    async def test_invalid_version_format(test_client: TestClient) -> None:
        response = test_client.get(
            "/test/",
            headers={"Accept": f"{VERSION_HEADER}; version=1-1"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {"detail": "Version should be in <major>.<minor> format"}
    ```

  - Remove the now-unused `@pytest.mark.parametrize` import usage if it leaves
    `pytest` unused (it does not — `pytestmark`/fixtures still use it).

- [ ] **Step 2: Run the full suite**

  Run: `just test`
  Expected: PASS.

- [ ] **Step 3: Coverage must stay at 100%**

  Run: `just test-ci`
  Expected: coverage 100% — the four retained round-trips map 1:1 to the
  `ParsedVersion` / `ParseError(no version)` / `ParseError(bad format)` /
  `Ignore` arms; parse branches are covered by `test_accept.py`.
  If any middleware line is uncovered, restore the matching round-trip.

- [ ] **Step 4: Lint**

  Run: `just lint-ci`
  Expected: ruff + ty clean.

- [ ] **Step 5: Commit**

  ```bash
  git add tests/test_app.py
  git commit -m "test: move exhaustive parse cases to the accept seam"
  ```

---

### Task 5: Record the deferred fix and finalize the bundle

**Files:**
- Modify: `planning/deferred.md`
- Modify: `planning/changes/2026-07-04.01-extract-accept-version-parse/design.md` (finalize `summary`)

Behavior is unchanged, so no `architecture/<capability>.md` promotion is
required by the rule. Record the case-sensitivity follow-up and finalize the
bundle summary.

- [ ] **Step 1: Append the deferred item**

  Add to `planning/deferred.md`:

  ```markdown
  - **Vendor media-type case-sensitivity** — `parse_accept_version` compares a
    lowercased header media-type against a non-lowercased `vendor_media_type`,
    so a mixed-case vendor never matches (silently falls through to `Ignore`).
    Revisit trigger: a user configures a vendor type with uppercase letters, or
    we decide to guarantee case-insensitive media-type matching. Fix is a
    failing `tests/test_accept.py` case plus a `.lower()` on the vendor.
  ```

- [ ] **Step 2: Finalize the design summary**

  In the bundle's `design.md`, update the `summary:` frontmatter to state the
  realized result once the PR number is known, e.g.:
  `Extracted Accept-header version parsing into fast_version/accept.py behind a
  sealed-result interface; exhaustive cases moved to the parse seam (shipped in #NN).`

- [ ] **Step 3: Validate planning + full CI checks**

  Run: `just check-planning` then `just lint-ci` then `just test-ci`
  Expected: all pass; coverage 100%.

- [ ] **Step 4: Commit**

  ```bash
  git add planning/deferred.md planning/changes/2026-07-04.01-extract-accept-version-parse/design.md
  git commit -m "docs(planning): record deferred vendor case-sensitivity fix"
  ```

---

## Finish

Push the branch and open a PR (never local-merge). Watch PR CI across Python
3.10-3.14. After merge: `git pull --ff-only` on `main`, delete the local
branch, `git remote prune origin`.
