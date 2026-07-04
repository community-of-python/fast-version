# collapse-versioned-paths-seam — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lift the OpenAPI path-collapse loop out of `_custom_openapi` into a
pure `_collapse_versioned_paths` function, unit-testable at its own seam,
preserving behavior.

**Spec:** [`design.md`](./design.md)

**Branch:** `refactor/collapse-versioned-paths-seam`

**Commit strategy:** Per-task commits.

## Global constraints

- Python 3.10-3.14. Ruff `select = ["ALL"]`, line length 120, and `ty` must
  pass (`just lint` to auto-fix, `just lint-ci` to check).
- `ty: ignore` not `type: ignore`. Imports at module level; annotate all args.
- Coverage gate: `just test-ci` runs `--cov-fail-under=100`. Every commit stays
  green at 100%.
- Behavior-preserving: the generated OpenAPI schema is byte-identical.

---

### Task 1: Extract `_collapse_versioned_paths` (TDD)

**Files:**
- Modify: `fast_version/app.py` (add function; slim `_custom_openapi`)
- Modify: `tests/test_app.py` (add import + 4 unit tests)

**Interfaces produced:**
- `fast_version.app._collapse_versioned_paths(raw_paths: dict[str, typing.Any], versioned_paths: set[str], vendor_media_type: str) -> dict[str, typing.Any]`

- [ ] **Step 1: Write the failing unit tests**

  In `tests/test_app.py`, add `_collapse_versioned_paths` to the existing
  `from fast_version.app import ...` line (currently imports `_iter_openapi_routes`),
  and append these four tests. `VERSION_HEADER` is already imported from
  `tests.conftest`.

  ```python
  def test_collapse_versioned_paths_passes_through_non_versioned() -> None:
      raw = {"/simple/": {"get": {"responses": {"200": {"description": "ok"}}}}}
      result = _collapse_versioned_paths(raw, set(), VERSION_HEADER)
      assert result == {"/simple/": {"get": {"responses": {"200": {"description": "ok"}}}}}


  def test_collapse_versioned_paths_rewrites_request_body_content_key() -> None:
      raw = {
          "/test/:1.0": {
              "post": {"requestBody": {"content": {"application/json": {"schema": {"x": 1}}}}},
          },
      }
      result = _collapse_versioned_paths(raw, {"/test/:1.0"}, VERSION_HEADER)
      assert set(result) == {"/test/"}
      content = result["/test/"]["post"]["requestBody"]["content"]
      assert set(content) == {f"{VERSION_HEADER}; version=1.0"}
      assert content[f"{VERSION_HEADER}; version=1.0"] == {"schema": {"x": 1}}


  def test_collapse_versioned_paths_merges_two_versions_of_same_path() -> None:
      raw = {
          "/test/:1.0": {"post": {"requestBody": {"content": {"application/json": {"schema": {"v": 1}}}}}},
          "/test/:2.0": {"post": {"requestBody": {"content": {"application/json": {"schema": {"v": 2}}}}}},
      }
      result = _collapse_versioned_paths(raw, {"/test/:1.0", "/test/:2.0"}, VERSION_HEADER)
      assert set(result) == {"/test/"}
      content = result["/test/"]["post"]["requestBody"]["content"]
      assert set(content) == {f"{VERSION_HEADER}; version=1.0", f"{VERSION_HEADER}; version=2.0"}


  def test_collapse_versioned_paths_versioned_without_request_body() -> None:
      raw = {"/test/:1.0": {"get": {"responses": {"200": {"description": "ok"}}}}}
      result = _collapse_versioned_paths(raw, {"/test/:1.0"}, VERSION_HEADER)
      assert set(result) == {"/test/"}
      assert result["/test/"] == {"get": {"responses": {"200": {"description": "ok"}}}}
  ```

- [ ] **Step 2: Run the tests to verify they fail**

  Run: `uv run --no-sync pytest tests/test_app.py -k collapse_versioned_paths -q`
  Expected: FAIL — `ImportError: cannot import name '_collapse_versioned_paths'`.

- [ ] **Step 3: Add the function to `app.py`**

  In `fast_version/app.py`, add this module-level function (place it directly
  above `_custom_openapi`):

  ```python
  def _collapse_versioned_paths(
      raw_paths: dict[str, typing.Any],
      versioned_paths: set[str],
      vendor_media_type: str,
  ) -> dict[str, typing.Any]:
      """Collapse the per-version ``:<version>`` suffixed paths back onto their real path.

      Only request bodies are versioned (keyed by media type); operation-level fields
      (parameters, summary, tags, ...) come from the first-merged version, so versions
      of the same path+method should differ only in body schema.
      """
      paths_dict: dict[str, typing.Any] = {}
      for raw_path, methods in raw_paths.items():
          if raw_path not in versioned_paths:
              paths_dict[raw_path] = methods
              continue
          clean_path, version_str = raw_path.rsplit(":", 1)
          for payload in methods.values():
              if "requestBody" not in payload:
                  continue
              payload["requestBody"]["content"] = {
                  f"{vendor_media_type}; version={version_str}": content
                  for content in payload["requestBody"]["content"].values()
              }
          if clean_path not in paths_dict:
              paths_dict[clean_path] = methods
              continue
          helpers.dict_merge(paths_dict[clean_path], methods)
      return paths_dict
  ```

- [ ] **Step 4: Slim `_custom_openapi` to call it**

  In `fast_version/app.py`, replace the tail of `_custom_openapi` — the block
  from the comment `# Collapse the per-version paths back onto their real path.`
  through `self.openapi_schema["paths"] = paths_dict` (currently lines 101-125)
  — with:

  ```python
      self.openapi_schema["paths"] = _collapse_versioned_paths(
          self.openapi_schema["paths"],
          versioned_paths,
          _get_vendor_media_type(),
      )
      return self.openapi_schema
  ```

  Remove the now-unused local declarations (`vendor_media_type = ...`,
  `paths_dict`, `raw_path: str`, `methods: dict[str, typing.Any]`). Keep the
  `if self.openapi_schema:` guard and the `get_openapi(...)` call above unchanged.

- [ ] **Step 5: Run the unit tests to verify they pass**

  Run: `uv run --no-sync pytest tests/test_app.py -k collapse_versioned_paths -q`
  Expected: PASS (4 passed).

- [ ] **Step 6: Full gate**

  Run: `just test-ci` — expected 100% coverage, all tests pass (existing OpenAPI
  integration tests still green).
  Run: `just lint` then `just lint-ci` — ruff + ty clean.

- [ ] **Step 7: Commit**

  ```bash
  git add fast_version/app.py tests/test_app.py
  git commit -m "refactor: extract _collapse_versioned_paths from _custom_openapi"
  ```

---

### Task 2: Finalize the planning bundle

**Files:**
- Modify: `planning/changes/2026-07-04.03-collapse-versioned-paths-seam/design.md`

Behavior-preserving, so no `architecture/<capability>.md` promotion is required.

- [ ] **Step 1: Finalize the design summary**

  In the bundle's `design.md`, update the `summary:` frontmatter to the realized
  result (add the PR number once known, e.g. `... (shipped in #NN)`):
  `Extracted the OpenAPI path-collapse loop into pure _collapse_versioned_paths, unit-tested at its own seam beside _iter_openapi_routes; behavior unchanged.`

- [ ] **Step 2: Validate + full gate**

  Run: `just check-planning` — expected `planning: OK`.
  Run: `just lint-ci` and `just test-ci` — clean, 100%.

- [ ] **Step 3: Commit**

  ```bash
  git add planning/changes/2026-07-04.03-collapse-versioned-paths-seam/design.md
  git commit -m "docs(planning): finalize collapse-versioned-paths-seam summary"
  ```

---

## Finish

Push the branch and open a PR (never local-merge). Watch PR CI across Python
3.10-3.14. After merge: `git pull --ff-only` on `main`, delete the local branch,
`git remote prune origin`.
