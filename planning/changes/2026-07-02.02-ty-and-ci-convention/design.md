---
summary: Replace mypy with ty and swap the community-workflow reusable CI for the modern-python self-hosted workflow set (OIDC release, weekly dep-check).
---

# Design: Adopt ty and the modern-python CI convention

## Summary

Bring `fast-version`'s tooling in line with the `modern-python` convention as
realized in the canonical sibling `modern-di-fastapi`. Two coupled changes:
(1) replace **mypy** with Astral's **ty** as the type checker, and (2) replace
the single `workflow.yml` that delegates to the `community-of-python/community-workflow`
reusable preset with the self-hosted four-workflow set (`ci.yml` + `_checks.yml`,
tag-driven `release.yml` on OIDC Trusted Publishing, and `scheduled.yml` weekly
dep-check). Along the way adopt the convention's peripheral tooling: `eof-fixer`,
the ruff `fix`/`unsafe-fixes`/`docstring-code-format` settings, and the
`test-ci`/`test-branch` split with `--cov-fail-under=100`.

## Motivation

The `modern-python` org convention (documented in that org's `CLAUDE.md`)
standardizes on **ty** for type checking and a self-hosted CI workflow set with
OIDC publishing and a weekly dependency-drift check. `fast-version` still runs
mypy and rides the older `community-of-python/community-workflow` reusable preset
(token-based publishing on `release: published`, no dep-drift guard). The sibling
`modern-di-fastapi` already runs the target shape end to end, so this is an
alignment change against a proven reference, not a green-field design.

## Non-goals

- pyproject `[project.urls]` (PyPI well-known labels), `classifiers`, and
  `keywords` — the "Repository metadata" convention — are left unchanged; a
  separate follow-up.
- Removing the dead poetry-style `packages = [...]` key under `[project]` is out
  of scope.
- No change to the library's runtime behavior or public API
  (`VersionedAPIRouter`, `init_fastapi_versioning`).

## Design

### 1. Type checker: mypy -> ty

- `pyproject.toml`: delete the `[tool.mypy]` table; change the `lint`
  dependency group from `ruff, mypy` to `ty, ruff, eof-fixer, typing-extensions`.
  No `[tool.ty]` table — ty runs on defaults, matching the sibling.
- Convert the four existing `# type: ignore[...]` comments to ty diagnostic
  codes (confirmed by running `ty check`):
  - `fast_version/app.py:27` `add_middleware(...)` -> `# ty: ignore[invalid-argument-type]`
  - `fast_version/app.py:28` `app.openapi = MethodType(...)` -> `# ty: ignore[invalid-assignment]`
  - `tests/test_app.py:188` param annotation -> `# ty: ignore[invalid-type-form]`
  - `tests/test_app.py:193` param annotation -> `# ty: ignore[invalid-type-form]`
- ty stays **unpinned**: `uv.lock` is git-ignored and `just install` runs
  `uv lock --upgrade`, so the version floats. The weekly `scheduled.yml`
  dep-check is the guard against a breaking ty release, matching convention.

### 2. justfile -> convention recipes

Adopt the `modern-di-fastapi` recipe set:

- `install`: `uv lock --upgrade` then `uv sync --all-extras --frozen --group lint`.
- `lint`: `eof-fixer . && ruff format && ruff check --fix && ty check`.
- `lint-ci`: `eof-fixer . --check && ruff format --check && ruff check --no-fix
  && ty check && python planning/index.py --check`.
- `test *args`: `uv run --no-sync pytest {{ args }}`.
- `test-ci`: `uv run --no-sync pytest --cov=. --cov-report term-missing
  --cov-report xml --cov-fail-under=100`.
- `test-branch`: `uv run --no-sync pytest --cov=. --cov-branch --cov-fail-under=100`.
- `publish`: OIDC form (`rm -rf dist && uv version $GITHUB_REF_NAME && uv build
  && uv publish`) — drops `$PYPI_TOKEN`.
- Keep `index` and `check-planning` as-is.

### 3. ruff + coverage settings

- `[tool.ruff]`: add `fix = false` and `unsafe-fixes = true`.
- Add `[tool.ruff.format]` with `docstring-code-format = true`.
- Keep the existing `[tool.ruff.lint].ignore` list unchanged — it is tuned for
  this repo (includes `SIM118`/`PLC0206`/`TCH`) and differs intentionally from
  the sibling's.
- `[tool.pytest.ini_options]`: set `addopts = ""` (coverage flags move into the
  `test-ci`/`test-branch` recipes).
- Add `[tool.coverage.report]` with `exclude_also = ["if typing.TYPE_CHECKING:"]`.
- `[build-system]`: bump `requires` to `uv_build>=0.11,<1.0` for parity.

### 4. CI: self-hosted four-workflow set

Delete `.github/workflows/workflow.yml`. Add, ported from `modern-di-fastapi` and
adapted to this repo:

- `ci.yml`: `on: push (main) + pull_request`, concurrency group, calls
  `_checks.yml`.
- `_checks.yml`: `workflow_call`; `lint` job (checkout@v6, setup-just@v4,
  setup-uv@v8.2.0, `uv python install/pin 3.10`, `just install lint-ci`) and
  `pytest` job (matrix 3.10-3.14, `just install`, `just test-ci`).
- `release.yml`: tag-driven (`[0-9]+.[0-9]+.[0-9]+` and pre-release variant),
  `permissions: contents: write + id-token: write`, `environment: pypi`; runs
  `just publish` first (OIDC), then resolves release metadata (uses
  `planning/releases/<tag>.md` if present) and publishes a GitHub Release. Adapt
  the sibling's `modern-di-fastapi` references to `fast-version`.
- `scheduled.yml`: Mondays 06:00 UTC + `workflow_dispatch`; calls `_checks.yml`,
  and on scheduled failure runs `.github/scripts/report-scheduled-failure.sh` to
  open/update a `scheduled-failure` tracking issue (`issues: write`).
- Add `.github/scripts/report-scheduled-failure.sh` (from the sibling; its
  message body already names ty/ruff/eof-fixer, so no edit needed).

### 5. Docs

Update project `CLAUDE.md`:

- Conventions section: type checker is **ty**, and use `ty: ignore` (not
  `type: ignore`).
- Architecture/commands references to CI: describe the self-hosted workflow set
  rather than the `community-of-python/community-workflow` reusable preset.

Check `architecture/` for a tooling/CI capability page to promote into; the
versioning capability pages are unaffected by this change.

## Operations

Out-of-repo, required for release to work (publishing only, not CI checks):

- Configure a **PyPI Trusted Publisher** for the `fast-version` project:
  environment `pypi`, workflow `release.yml`, repository
  `community-of-python/fast-version`. Until this exists, a tag push fails at
  `just publish`. Because publish runs before the GitHub Release step, a failed
  publish does not create a Release advertising an unpublished version.
- Optional: create the GitHub `pypi` environment (approval rules / scoping).

## Testing

- `just lint` — ruff format/check clean, `ty check` reports **0 diagnostics**
  (the 4 mapped ignores silence cleanly), `eof-fixer` clean.
- `just test-ci` — 20 tests pass at **100%** coverage (already at 100%, so
  `--cov-fail-under=100` holds).
- CI workflows exercised by the PR's own `ci.yml` run. `release.yml` /
  `scheduled.yml` are validated by inspection + `workflow_dispatch` after merge.

## Risk

- **Floating ty** (unpinned) could break on a new release. Mitigation:
  `scheduled.yml` catches drift weekly; same posture as the sibling.
- **ty surfaces diagnostics beyond the mapped four.** Mitigation: run `just lint`
  during implementation before committing; adjust ignores if needed.
- **OIDC release requires external PyPI setup.** Mitigation: set up the Trusted
  Publisher before the first tag; the publish-before-Release ordering prevents a
  half-published release.
- **Divergence from the shared community-of-python reusable** is intentional and
  accepted.
