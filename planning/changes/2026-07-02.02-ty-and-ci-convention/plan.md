# ty and CI-convention Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mypy with ty and swap the community-workflow reusable CI for the modern-python self-hosted workflow set, adopting the convention's peripheral tooling (eof-fixer, ruff/coverage settings).

**Architecture:** Type-checking moves from mypy to Astral's ty (defaults, unpinned — `uv.lock` is git-ignored). CI moves from a single `workflow.yml` that delegates to `community-of-python/community-workflow` to a self-hosted four-workflow set ported from the canonical sibling `modern-di-fastapi`: `ci.yml` -> reusable `_checks.yml`, tag-driven `release.yml` on OIDC Trusted Publishing, and `scheduled.yml` weekly dep-check.

**Tech Stack:** uv, just, ruff, ty, eof-fixer, pytest + pytest-cov, GitHub Actions, uv_build.

**Spec:** [`design.md`](./design.md)

**Branch:** `chore/ty-and-ci-convention` (already created).

**Commit strategy:** Per-task commits. This is a tooling migration, not feature
work — there is no new runtime behavior to test-first, so each task's
"verification" is a lint/type-check/pytest gate rather than a TDD red-green
cycle. Keep the tree green at each commit where possible (the ty swap and the CI
swap are independently shippable).

## Global Constraints

- Python floor: `requires-python = ">=3.10,<4"`; CI matrix is exactly
  `3.10, 3.11, 3.12, 3.13, 3.14`.
- ty runs on **defaults** — no `[tool.ty]` table.
- ty is **unpinned** (`uv.lock` git-ignored; `just install` runs
  `uv lock --upgrade`). Do not add a lockfile or pin.
- Keep the existing `[tool.ruff.lint].ignore` list unchanged.
- Coverage must stay at **100%** (`--cov-fail-under=100`). Repo is currently at
  100%; do not lower the gate.
- Use `ty: ignore` (never `type: ignore`) for suppressions in this repo.
- Reuse the sibling `modern-di-fastapi` shapes verbatim except where this plan
  specifies a `fast-version` substitution.

---

### Task 1: Replace mypy with ty (deps, config, suppressions)

**Files:**
- Modify: `pyproject.toml`
- Modify: `fast_version/app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Produces: a repo whose type checker is `ty`; consumed by the justfile
  (`ty check`) and CI (`just install lint-ci`) in later tasks.

- [ ] **Step 1: Swap the lint dependency group**

  In `pyproject.toml`, replace the `lint` group:

  ```toml
  lint = [
      "ty",
      "ruff",
      "eof-fixer",
      "typing-extensions",
  ]
  ```

- [ ] **Step 2: Delete the mypy config**

  Remove this entire table from `pyproject.toml`:

  ```toml
  [tool.mypy]
  python_version = "3.10"
  strict = true
  ```

- [ ] **Step 3: Convert the two `fast_version/app.py` suppressions**

  Line 27:
  ```python
      app.add_middleware(FastAPIVersioningMiddleware)  # ty: ignore[invalid-argument-type]
  ```
  Line 28:
  ```python
      app.openapi = MethodType(_custom_openapi, app)  # ty: ignore[invalid-assignment]
  ```

- [ ] **Step 4: Convert the two `tests/test_app.py` suppressions**

  Line 188:
  ```python
      async def _create(_: item_v1) -> dict[str, typing.Any]:  # ty: ignore[invalid-type-form]
  ```
  Line 193:
  ```python
      async def _create_v2(_: item_v2) -> dict[str, typing.Any]:  # ty: ignore[invalid-type-form]
  ```

- [ ] **Step 5: Sync the new tooling and run ty**

  Run:
  ```bash
  uv lock --upgrade && uv sync --all-extras --frozen --group lint
  uv run ty check
  ```
  Expected: `All checks passed!` (0 diagnostics). If ty reports an
  **unused-ignore** or a different code at any of the four sites, correct that
  line's `ty: ignore[<code>]` to the code ty prints, then re-run until clean. Do
  not add blanket `# ty: ignore` without a code.

- [ ] **Step 6: Confirm tests still pass**

  Run:
  ```bash
  uv run --no-sync pytest
  ```
  Expected: `20 passed`.

- [ ] **Step 7: Commit**

  ```bash
  git add pyproject.toml fast_version/app.py tests/test_app.py
  git commit -m "chore: replace mypy with ty"
  ```

---

### Task 2: Adopt convention justfile + ruff/coverage settings

**Files:**
- Modify: `justfile`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: the `ty` tooling from Task 1.
- Produces: `just lint-ci`, `just test-ci`, `just test-branch`, and OIDC
  `just publish` recipes consumed by the CI workflows in Task 3.

- [ ] **Step 1: Rewrite the justfile**

  Replace the whole file with:

  ```just
  default: install lint test

  install:
      uv lock --upgrade
      uv sync --all-extras --frozen --group lint

  lint:
      uv run eof-fixer .
      uv run ruff format
      uv run ruff check --fix
      uv run ty check

  lint-ci:
      uv run eof-fixer . --check
      uv run ruff format --check
      uv run ruff check --no-fix
      uv run ty check
      uv run python planning/index.py --check

  index:
      uv run python planning/index.py

  check-planning:
      uv run python planning/index.py --check

  test *args:
      uv run --no-sync pytest {{ args }}

  test-ci:
      uv run --no-sync pytest --cov=. --cov-report term-missing --cov-report xml --cov-fail-under=100

  test-branch:
      uv run --no-sync pytest --cov=. --cov-branch --cov-fail-under=100

  # Auth via PyPI Trusted Publishing (OIDC); uv publish auto-detects the CI id-token.
  publish:
      rm -rf dist
      uv version $GITHUB_REF_NAME
      uv build
      uv publish
  ```

- [ ] **Step 2: Add ruff format/fix settings in pyproject.toml**

  Change `[tool.ruff]` from:
  ```toml
  [tool.ruff]
  line-length = 120
  target-version = "py310"
  ```
  to:
  ```toml
  [tool.ruff]
  fix = false
  unsafe-fixes = true
  line-length = 120
  target-version = "py310"

  [tool.ruff.format]
  docstring-code-format = true
  ```
  Leave `[tool.ruff.lint]` (the `select`/`ignore`/`isort` block) unchanged.

- [ ] **Step 3: Move coverage flags out of pytest addopts**

  In `[tool.pytest.ini_options]` change:
  ```toml
  addopts = "--cov=. --cov-report term-missing"
  ```
  to:
  ```toml
  addopts = ""
  ```

- [ ] **Step 4: Add the coverage report table**

  Append to `pyproject.toml`:
  ```toml
  [tool.coverage.report]
  exclude_also = [
      "if typing.TYPE_CHECKING:",
  ]
  ```

- [ ] **Step 5: Bump the build-backend floor**

  Change `[build-system]` `requires` from `["uv_build"]` to:
  ```toml
  requires = ["uv_build>=0.11,<1.0"]
  ```

- [ ] **Step 6: Run the full local gate**

  Run:
  ```bash
  just lint
  just test-ci
  ```
  Expected: `just lint` completes with no ruff/ty/eof-fixer errors (it may
  reformat/fix files — re-run until clean and stage any changes); `just test-ci`
  shows `20 passed` and `TOTAL ... 100%` with no `--cov-fail-under` failure.

- [ ] **Step 7: Commit**

  ```bash
  git add justfile pyproject.toml
  git commit -m "chore: adopt convention justfile, ruff and coverage settings"
  ```

---

### Task 3: Replace CI with the self-hosted workflow set

**Files:**
- Delete: `.github/workflows/workflow.yml`
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/_checks.yml`
- Create: `.github/workflows/release.yml`
- Create: `.github/workflows/scheduled.yml`
- Create: `.github/scripts/report-scheduled-failure.sh`

**Interfaces:**
- Consumes: `just install lint-ci`, `just test-ci`, `just publish` from Task 2.

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

  ```yaml
  name: main
  on:
    push:
      branches:
        - main
    pull_request: {}

  concurrency:
    group: ${{ github.head_ref || github.run_id }}
    cancel-in-progress: true

  jobs:
    checks:
      uses: ./.github/workflows/_checks.yml
  ```

- [ ] **Step 2: Create `.github/workflows/_checks.yml`**

  ```yaml
  name: checks
  on:
    workflow_call: {}

  jobs:
    lint:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v6
        - uses: extractions/setup-just@v4
        - uses: astral-sh/setup-uv@v8.2.0
          with:
            enable-cache: true
            cache-dependency-glob: "**/pyproject.toml"
        - run: uv python install 3.10
        - run: uv python pin 3.10
        - run: just install lint-ci

    pytest:
      runs-on: ubuntu-latest
      strategy:
        fail-fast: false
        matrix:
          python-version:
            - "3.10"
            - "3.11"
            - "3.12"
            - "3.13"
            - "3.14"
      steps:
        - uses: actions/checkout@v6
        - uses: extractions/setup-just@v4
        - uses: astral-sh/setup-uv@v8.2.0
          with:
            enable-cache: true
            cache-dependency-glob: "**/pyproject.toml"
        - run: uv python install ${{ matrix.python-version }}
        - run: uv python pin ${{ matrix.python-version }}
        - run: just install
        - run: just test-ci
  ```

- [ ] **Step 3: Create `.github/workflows/release.yml`**

  ```yaml
  name: Release

  # Tag-driven: pushing a semver tag publishes to PyPI and creates the matching
  # GitHub Release. The tag is the sole entry point; by convention a tag is only
  # cut off a green main, so there is no in-workflow CI gate.
  on:
    push:
      tags:
        - '[0-9]+.[0-9]+.[0-9]+'               # stable:      2.7.2
        - '[0-9]+.[0-9]+.[0-9]+[a-z]+[0-9]+'   # pre-release: 2.0.0rc1, 4.0.0a2

  # contents: write -> create the GitHub Release; id-token: write -> OIDC for PyPI Trusted Publishing.
  permissions:
    contents: write
    id-token: write

  jobs:
    release:
      runs-on: ubuntu-latest
      environment: pypi  # scopes the PyPI Trusted Publisher; hook for approval rules
      steps:
        - uses: actions/checkout@v6
        - uses: extractions/setup-just@v4
        - uses: astral-sh/setup-uv@v8.2.0

        # PyPI is irreversible, so it runs FIRST: if it fails the job stops and no
        # GitHub Release is created advertising a version that never reached PyPI.
        # `just publish` derives the version from $GITHUB_REF_NAME (the tag name).
        # Auth via PyPI Trusted Publishing (OIDC); no PYPI_TOKEN. Needs a Trusted
        # Publisher on the fast-version PyPI project (env: pypi, workflow: release.yml).
        - run: just publish

        # Description source: planning/releases/<tag>.md if present (verbatim, no
        # auto-changelog appended); otherwise GitHub's generated notes. A tag with
        # a letter (2.0.0rc1) is a pre-release -> flagged so GitHub won't mark it
        # "Latest".
        - name: Resolve release metadata
          id: meta
          run: |
            set -euo pipefail
            notes="planning/releases/${GITHUB_REF_NAME}.md"
            if [ -f "$notes" ]; then
              echo "body_path=$notes" >> "$GITHUB_OUTPUT"
              echo "generate_notes=false" >> "$GITHUB_OUTPUT"
            else
              echo "generate_notes=true" >> "$GITHUB_OUTPUT"
            fi
            if [[ "$GITHUB_REF_NAME" =~ [a-z] ]]; then
              echo "prerelease=true" >> "$GITHUB_OUTPUT"
            else
              echo "prerelease=false" >> "$GITHUB_OUTPUT"
            fi

        - name: Publish GitHub Release
          uses: softprops/action-gh-release@v3
          with:
            body_path: ${{ steps.meta.outputs.body_path }}
            generate_release_notes: ${{ steps.meta.outputs.generate_notes }}
            prerelease: ${{ steps.meta.outputs.prerelease }}
            draft: false
  ```

- [ ] **Step 4: Create `.github/workflows/scheduled.yml`**

  ```yaml
  name: scheduled-dep-check
  on:
    schedule:
      - cron: "0 6 * * 1"        # Mondays 06:00 UTC
    workflow_dispatch: {}

  concurrency:
    group: scheduled-dep-check
    cancel-in-progress: false

  jobs:
    checks:
      uses: ./.github/workflows/_checks.yml

    report-failure:
      needs: checks
      if: failure() && github.event_name == 'schedule'
      runs-on: ubuntu-latest
      permissions:
        contents: read
        issues: write
      steps:
        - uses: actions/checkout@v6
        - name: Open or update tracking issue
          env:
            GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
            RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
          run: bash .github/scripts/report-scheduled-failure.sh
  ```

- [ ] **Step 5: Create `.github/scripts/report-scheduled-failure.sh`**

  ```bash
  #!/usr/bin/env bash
  set -euo pipefail

  LABEL="scheduled-failure"
  TITLE="Scheduled dependency check failed"

  # Ensure the label exists. --force makes this idempotent: creates if absent,
  # updates color/description without error if present.
  gh label create "$LABEL" \
    --color "FBCA04" \
    --description "Weekly dependency check failures" \
    --force

  # Find an open issue with our label, if any. --jq '.[0].number // empty'
  # yields the first number or an empty string when there are no matches.
  existing=$(gh issue list --label "$LABEL" --state open --json number --jq '.[0].number // empty')

  if [ -z "$existing" ]; then
    body=$(printf '%s\n\n%s\n\n%s\n\n%s' \
      "The weekly scheduled dependency check failed." \
      "First failing run: ${RUN_URL}" \
      "Likely cause: a transitive dev or lint dependency (ruff, ty, eof-fixer, pytest, typing-extensions) released a breaking change. Reproduce locally with \`just install\` then \`just lint\` and \`just test\`." \
      "Close this issue once fixed. The next scheduled failure will open a fresh issue.")
    gh issue create --title "$TITLE" --label "$LABEL" --body "$body"
  else
    gh issue comment "$existing" --body "Failed again: ${RUN_URL}"
  fi
  ```

  Then make it executable:
  ```bash
  chmod +x .github/scripts/report-scheduled-failure.sh
  ```

- [ ] **Step 6: Delete the old workflow**

  ```bash
  git rm .github/workflows/workflow.yml
  ```

- [ ] **Step 7: Validate the YAML parses**

  Run:
  ```bash
  uv run python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('workflows OK')"
  ```
  Expected: `workflows OK` (no traceback). If `yaml` is unavailable, use
  `python -c` under a uv env that has it, or skip — CI will parse on push.

- [ ] **Step 8: Commit**

  ```bash
  git add .github/workflows .github/scripts
  git commit -m "ci: adopt modern-python self-hosted workflow set"
  ```

---

### Task 4: Update CLAUDE.md to match the new tooling

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: the realized tooling from Tasks 1-3.

No `architecture/` edit: that directory holds only `README.md` (capability pages
are authored lazily), and this change is dev tooling, not a library-capability
behavior change — so there is nothing to promote.

- [ ] **Step 1: Update the Commands block (lines ~19-22)**

  Change:
  ```
  just install    # uv lock --upgrade + uv sync --all-extras --all-groups --frozen
  just lint       # ruff format, ruff check --fix, mypy (mutates files)
  just lint-ci    # same checks, no mutation (--check / --no-fix)
  just test       # uv run pytest (coverage is on by default via addopts)
  ```
  to:
  ```
  just install    # uv lock --upgrade + uv sync --all-extras --frozen --group lint
  just lint       # eof-fixer, ruff format, ruff check --fix, ty check (mutates files)
  just lint-ci    # same checks, no mutation (--check / --no-fix) + planning index check
  just test       # uv run --no-sync pytest; just test-ci adds coverage (--cov-fail-under=100)
  ```

- [ ] **Step 2: Update the Conventions bullets (lines ~89-92)**

  Change:
  ```
  - Ruff with `select = ["ALL"]` (line length 120), mypy `strict`. Both must pass;
    CI runs `lint-ci` plus pytest across Python 3.10-3.14 via the shared
    `community-of-python/community-workflow` reusable workflow.
  - `type: ignore` (not `ty: ignore`) is used here since the type checker is mypy.
  ```
  to:
  ```
  - Ruff with `select = ["ALL"]` (line length 120) and `ty` (defaults). Both must
    pass; CI runs `lint-ci` plus pytest across Python 3.10-3.14 via the repo's
    self-hosted GitHub Actions workflows (`ci.yml` -> `_checks.yml`), with
    tag-driven OIDC publishing (`release.yml`) and a weekly dependency check
    (`scheduled.yml`).
  - `ty: ignore` (not `type: ignore`) is used here since the type checker is ty.
  ```

- [ ] **Step 3: Verify no stale mypy/community-workflow references remain**

  Run:
  ```bash
  grep -nE "mypy|community-workflow|all-groups|type: ignore" CLAUDE.md
  ```
  Expected: no output (all references updated).

- [ ] **Step 4: Commit**

  ```bash
  git add CLAUDE.md
  git commit -m "docs: describe ty and self-hosted CI in CLAUDE.md"
  ```

---

### Task 5: Finalize the bundle and open the PR

**Files:**
- Modify: `planning/` (index + bundle summary, if needed)

- [ ] **Step 1: Full local gate**

  Run:
  ```bash
  just lint-ci
  just test-ci
  ```
  Expected: both green — lint-ci passes (ruff/ty/eof-fixer clean + planning
  index check OK), test-ci shows `20 passed` at `100%`.

- [ ] **Step 2: Refresh the planning index**

  Run:
  ```bash
  just index
  just check-planning
  ```
  Expected: `planning: OK`. The `design.md` `summary:` frontmatter already states
  the realized result; adjust only if the implementation diverged.

  ```bash
  git add planning
  git commit -m "docs(planning): refresh index"
  ```
  (Skip this commit entirely if `git status` shows nothing changed under
  `planning/`.)

- [ ] **Step 3: Push and open the PR**

  ```bash
  git push -u origin chore/ty-and-ci-convention
  gh pr create --fill
  ```
  In the PR body, include an **Operations prerequisite** note:

  > Before the first tag after this merges, configure a PyPI **Trusted
  > Publisher** for the `fast-version` project: environment `pypi`, workflow
  > `release.yml`, repo `community-of-python/fast-version`. Without it, a tag
  > push fails at `just publish`. Publish runs before the GitHub Release step, so
  > a failed publish will not create a Release for an unpublished version.

- [ ] **Step 4: Watch CI**

  ```bash
  gh pr checks --watch
  ```
  Expected: the `main` workflow's `lint` and `pytest` (3.10-3.14) jobs pass.
  If a check shows a stale `refs/pull/<n>/merge` failure, re-run the local gate
  at HEAD and push a fresh commit to force GitHub to recompute the merge ref.
