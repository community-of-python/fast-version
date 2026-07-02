# ty-and-ci-convention — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mypy with ty and adopt the modern-python self-hosted CI
workflow set (OIDC release, weekly dep-check) plus the convention's peripheral
tooling.

**Spec:** [`design.md`](./design.md)

**Branch:** `chore/ty-and-ci-convention`

**Commit strategy:** Per-task commits (each task leaves the tree lint+test green
where possible; the ty swap and CI swap are separable).

---

### Task 1: Swap mypy for ty in pyproject + source

**Files:**
- Modify: `pyproject.toml`
- Modify: `fast_version/app.py`
- Modify: `tests/test_app.py`

Replace the type checker and its inline suppressions so `ty check` is clean.

- [ ] **Step 1: pyproject type-checker deps + config**

  In `pyproject.toml`: delete the `[tool.mypy]` table. Change the `lint`
  dependency group to `ty, ruff, eof-fixer, typing-extensions` (remove `mypy`).
  Leave no `[tool.ty]` table.

- [ ] **Step 2: Convert the four suppressions**

  - `fast_version/app.py:27` -> `# ty: ignore[invalid-argument-type]`
  - `fast_version/app.py:28` -> `# ty: ignore[invalid-assignment]`
  - `tests/test_app.py:188` and `:193` -> `# ty: ignore[invalid-type-form]`

- [ ] **Step 3: Verify ty is clean**

  ```bash
  uv sync --all-extras --frozen --group lint || uv lock --upgrade && uv sync --all-extras --frozen --group lint
  uv run ty check
  ```

  Expected: `All checks passed` / 0 diagnostics. If new diagnostics appear,
  add the correct `# ty: ignore[<code>]` and note it.

- [ ] **Step 4: Commit**

  ```bash
  git add pyproject.toml fast_version/app.py tests/test_app.py
  git commit -m "chore: replace mypy with ty"
  ```

---

### Task 2: Adopt convention justfile + ruff/coverage settings

**Files:**
- Modify: `justfile`
- Modify: `pyproject.toml`

Bring recipes and tool settings to the `modern-di-fastapi` shape.

- [ ] **Step 1: justfile recipes**

  Update `install` (`--frozen --group lint`), `lint` (eof-fixer/ruff
  format/ruff check --fix/ty check), `lint-ci` (check-only + `python
  planning/index.py --check`), `test`/`test-ci`/`test-branch`, and `publish`
  (OIDC, drop `$PYPI_TOKEN`). Keep `index`/`check-planning`.

- [ ] **Step 2: ruff + coverage in pyproject**

  Add `fix = false` and `unsafe-fixes = true` under `[tool.ruff]`; add
  `[tool.ruff.format]` `docstring-code-format = true`; set `addopts = ""`; add
  `[tool.coverage.report]` `exclude_also = ["if typing.TYPE_CHECKING:"]`; bump
  `[build-system] requires` to `uv_build>=0.11,<1.0`. Keep the existing ruff
  `ignore` list.

- [ ] **Step 3: Verify lint + coverage**

  ```bash
  just lint
  just test-ci
  ```

  Expected: lint clean; 20 tests pass at 100% coverage (`--cov-fail-under=100`
  holds).

- [ ] **Step 4: Commit**

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

Port the four-workflow set from `modern-di-fastapi`, adapted to this repo.

- [ ] **Step 1: Add the four workflows + script**

  Copy `ci.yml`, `_checks.yml`, `release.yml`, `scheduled.yml` and
  `.github/scripts/report-scheduled-failure.sh` from
  `../../pypi/modern-di-fastapi`. In `release.yml`, replace `modern-di-fastapi`
  references with `fast-version` (Trusted Publisher note, project name).
  `chmod +x` the script.

- [ ] **Step 2: Remove the old workflow**

  ```bash
  git rm .github/workflows/workflow.yml
  ```

- [ ] **Step 3: Validate workflow YAML**

  Confirm each workflow parses (e.g. `python -c "import yaml,sys;
  [yaml.safe_load(open(f)) for f in sys.argv[1:]]" .github/workflows/*.yml`) and
  matrix versions are 3.10-3.14.

- [ ] **Step 4: Commit**

  ```bash
  git add .github/workflows .github/scripts
  git commit -m "ci: adopt modern-python self-hosted workflow set"
  ```

---

### Task 4: Update docs + promote to architecture

**Files:**
- Modify: `CLAUDE.md`
- Modify: `architecture/<capability>.md` (only if a tooling/CI page exists)

Keep the dev-facing docs true to the new tooling.

- [ ] **Step 1: CLAUDE.md**

  Conventions: type checker is ty; use `ty: ignore` not `type: ignore`. Update
  the CI description from the `community-of-python/community-workflow` reusable
  preset to the self-hosted workflow set.

- [ ] **Step 2: architecture check**

  Inspect `architecture/`. If a tooling/CI/build capability page exists, promote
  the change into it; otherwise no architecture edit is needed (versioning pages
  are unaffected). Note the outcome.

- [ ] **Step 3: Regenerate planning index + check**

  ```bash
  just index
  just check-planning
  ```

  Expected: index updated, check passes.

- [ ] **Step 4: Commit**

  ```bash
  git add CLAUDE.md architecture planning
  git commit -m "docs: describe ty and self-hosted CI"
  ```

---

### Task 5: Finalize + PR

- [ ] **Step 1: Full local gate**

  ```bash
  just lint-ci
  just test-ci
  ```

  Both green.

- [ ] **Step 2: Finalize the bundle summary**

  Confirm `design.md` frontmatter `summary:` states the realized result; run
  `just index && just check-planning`.

- [ ] **Step 3: Push + open PR**

  Push the branch and open a PR. In the PR body, call out the **Operations**
  prerequisite: a PyPI Trusted Publisher must be configured for `fast-version`
  (env `pypi`, workflow `release.yml`) before the first tag, or releases fail at
  publish. Watch CI.
