# Adopt planning-convention (v1.1.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fresh-adopt the `lesnik512/planning-convention` (v1.1.1) into fast-version and unify the superpowers spec/plan flow onto `planning/changes/`.

**Architecture:** Follow the canonical `APPLY.md` §§1-6 for a fresh adopt: copy the owned files (`index.py`, `_templates/*`) verbatim, scaffold `planning/` and `architecture/`, merge the convention prose into `planning/README.md`, and judgment-merge `Justfile` + `CLAUDE.md`. On top of that, migrate the two existing `docs/superpowers/` artifacts into a change bundle and delete that tree. The validator (`planning/index.py`) is stdlib-only and gets wired into `lint-ci`.

**Tech Stack:** Python 3.10+ (stdlib only for `index.py`), `uv` + `just`, ruff (select ALL), mypy strict. No new dependencies.

## Global Constraints

- Spec: [`design.md`](./design.md). This is a fresh adopt at convention version **1.1.1**.
- No changes to `fast_version/` source or `tests/`. No `pyproject.toml` change.
- `index.py` and `_templates/*` are **copied verbatim** from the canonical repo — never hand-edit them (edits are discarded on the next convention update).
- Lint must pass `just lint-ci`: `ruff format --check`, `ruff check --no-fix`, `mypy .` (strict), and the new `python planning/index.py --check` step.
- `planning/index.py` trips `INP001` (implicit namespace package) under `select=["ALL"]`. Per the modern-python convention repos (`../pypi/*`), the fix is a file-level `# ruff: noqa: INP001` header on `index.py` itself and **no `planning/__init__.py`** — NOT a ruff-config change. (An empty `__init__.py` was tried first but makes coverage's `--cov=.` count the vendored validator, dropping coverage to 71%; keeping `planning/` a non-package restores 100%.) Only `INP001` is suppressed; this v1.1.1 `index.py` has a D212-safe docstring, so adding `D212` would trip `RUF100`.
- Type-checker is **mypy**: suppress with `# type: ignore[...]` (never `# ty: ignore`). Verified: the verbatim `index.py` passes `mypy --strict` and `ruff format --check` as-is.
- `uv.lock` is git-ignored here — never stage it.
- Bundle/decision naming is enforced by the validator: bundles `changes/YYYY-MM-DD.NN-slug/`, decisions `decisions/YYYY-MM-DD-slug.md`. `date`/`slug` are derived from the name, never written in frontmatter.
- Canonical source for verbatim copies: clone `https://github.com/lesnik512/planning-convention` fresh in each task that needs it (do not rely on a pre-existing local clone).

---

## Preliminary: branch

Already on branch `chore/adopt-planning-convention` (created during brainstorming; `design.md` is committed on it). If starting fresh, `git checkout chore/adopt-planning-convention`. Never commit to `main`.

---

### Task 1: Install the owned canonical files + package marker

> **Superseded during execution:** Task 1 originally created an empty `planning/__init__.py` to silence `INP001`. That made coverage's `--cov=.` count the vendored validator (100%->71%). The shipped approach (commit after Task 6) instead adds a `# ruff: noqa: INP001` header to `index.py` and removes `planning/__init__.py`, matching the modern-python convention repos — ruff clean, coverage 100%, no pyproject change. Steps below are the original record.

Copy the verbatim-owned files and the version record. The empty `__init__.py` is what keeps the vendored `index.py` from failing `INP001` under fast-version's `select = ["ALL"]` ruff config.

**Files:**
- Create: `planning/index.py` (verbatim from canonical)
- Create: `planning/__init__.py` (empty — package marker for lint)
- Create: `planning/_templates/{change,design,plan,decision,release,glossary}.md` (verbatim)
- Create: `planning/.convention-version` (contents: `1.1.1`)

**Interfaces:**
- Produces: `planning/index.py` runnable as `uv run python planning/index.py [--check]`; resolves `changes/`, `decisions/` relative to its own parent (`planning/`) and tolerates their absence.

- [ ] **Step 1: Clone the canonical repo to a temp dir**

```bash
PC="$(mktemp -d)/pc"; git clone --depth 1 https://github.com/lesnik512/planning-convention.git "$PC"
```

- [ ] **Step 2: Copy the owned files verbatim**

```bash
mkdir -p planning/_templates
cp "$PC/index.py" planning/index.py
cp "$PC"/_templates/*.md planning/_templates/
: > planning/__init__.py
printf '1.1.1\n' > planning/.convention-version
```

- [ ] **Step 3: Verify the copies match canonical (no drift)**

Run: `diff "$PC/index.py" planning/index.py && for f in "$PC"/_templates/*.md; do diff "$f" "planning/_templates/$(basename "$f")"; done && echo VERBATIM_OK`
Expected: `VERBATIM_OK` (no diff output).

- [ ] **Step 4: Verify the validator runs**

Run: `uv run python planning/index.py --check`
Expected: `planning: OK` (the adopt bundle's `design.md` already has `summary`; no other bundles yet).

- [ ] **Step 5: Verify lint is clean on the new files**

Run: `uv run ruff check planning/ --no-fix && uv run ruff format planning/ --check && uv run mypy planning/index.py && echo LINT_OK`
Expected: `LINT_OK`. (If `INP001` appears, `planning/__init__.py` is missing or non-empty-path — recreate it.)

- [ ] **Step 6: Commit**

```bash
git add planning/index.py planning/__init__.py planning/_templates planning/.convention-version
git commit -m "chore(planning): install convention validator + templates (v1.1.1)"
```

---

### Task 2: Scaffold the planning prose and directories

Create the human-facing `planning/README.md` (repo-local title/intro + the canonical Quick-path/Conventions prose + repo-local Index/Other), `deferred.md`, and the empty `decisions/`/`releases/` dirs (git needs a tracked file to keep a dir).

**Files:**
- Create: `planning/README.md`
- Create: `planning/deferred.md`
- Create: `planning/decisions/.gitkeep`, `planning/releases/.gitkeep`

- [ ] **Step 1: Clone canonical (for the convention body)**

```bash
PC="$(mktemp -d)/pc"; git clone --depth 1 https://github.com/lesnik512/planning-convention.git "$PC"
```

- [ ] **Step 2: Assemble `planning/README.md`**

APPLY §2: keep our own title/intro, splice the canonical `convention.md` body **from its `## Quick path` heading to EOF**, then our repo-local sections.

```bash
{ cat <<'HEAD'
# Planning

fast-version's planning home. The two axes: [`../architecture/`](../architecture/)
holds the living truth about what the library does **now**; [`changes/`](changes/)
records how it got there. The Quick path and Conventions below are applied from
[`lesnik512/planning-convention`](https://github.com/lesnik512/planning-convention)
(applied version in [`.convention-version`](.convention-version)); update them by
running that repo's `APPLY.md` flow.

HEAD
sed -n '/^## Quick path/,$p' "$PC/convention.md"
cat <<'TAIL'

## Index

`just index` prints the change/decision listing (a query over the bundles,
newest-first — never committed). `just check-planning` validates the bundles.

## Other

- [`deferred.md`](deferred.md) — real-but-unscheduled items, each with a revisit trigger.
- [`../architecture/README.md`](../architecture/README.md) — the promotion rule for the truth home.
TAIL
} > planning/README.md
```

- [ ] **Step 3: Create `deferred.md` and the dir placeholders**

```bash
printf '# Deferred\n\nReal-but-unscheduled items, each with a revisit trigger. Empty for now.\n' > planning/deferred.md
mkdir -p planning/decisions planning/releases
: > planning/decisions/.gitkeep
: > planning/releases/.gitkeep
```

- [ ] **Step 4: Verify the README has all three parts and points at the version file**

Run: `grep -q '^## Quick path' planning/README.md && grep -q '^## Conventions' planning/README.md && grep -q '^## Index' planning/README.md && grep -q '.convention-version' planning/README.md && echo README_OK`
Expected: `README_OK`.

- [ ] **Step 5: Commit**

```bash
git add planning/README.md planning/deferred.md planning/decisions/.gitkeep planning/releases/.gitkeep
git commit -m "docs(planning): add convention README, deferred, and dir scaffolding"
```

---

### Task 3: Create the architecture truth home

Create `architecture/README.md` at the repo root stating the promotion rule. Do **not** author capability files or `glossary.md` (lazy, per the convention).

**Files:**
- Create: `architecture/README.md`

- [ ] **Step 1: Write `architecture/README.md`**

```bash
mkdir -p architecture
cat > architecture/README.md <<'EOF'
# Architecture

The living truth about what fast-version does **now** — one file per capability,
plus a single `glossary.md` (the ubiquitous language) when terms are worth
pinning down. Living prose, **no frontmatter**, dated by git.

**Promotion rule:** when a change alters a capability's behavior, hand-edit the
matching `architecture/<capability>.md` in the **same PR** as the code — the doc
edit rides in the same diff and is reviewed with it, never as a separate
post-merge step. Capability files and `glossary.md` are authored lazily: they
appear when the first capability or term is worth pinning down.

Change history and the convention itself live under [`../planning/`](../planning/).
EOF
```

- [ ] **Step 2: Verify**

Run: `test -f architecture/README.md && grep -q 'Promotion rule' architecture/README.md && echo ARCH_OK`
Expected: `ARCH_OK`.

- [ ] **Step 3: Commit**

```bash
git add architecture/README.md
git commit -m "docs(architecture): add truth-home README with promotion rule"
```

---

### Task 4: Migrate the existing docs/superpowers artifacts into a bundle

Move the shipped OpenAPI-0.139 spec+plan (currently in `docs/superpowers/`) into a change bundle, reframe the spec to lean frontmatter, and delete the now-empty tree. `git mv` preserves history.

**Files:**
- Move: `docs/superpowers/specs/2026-07-01-openapi-versioning-fastapi-0139-design.md` → `planning/changes/2026-07-01.01-openapi-versioning-fastapi-0139/design.md`
- Move: `docs/superpowers/plans/2026-07-02-openapi-versioning-fastapi-0139.md` → `planning/changes/2026-07-01.01-openapi-versioning-fastapi-0139/plan.md`
- Delete: the emptied `docs/superpowers/` tree

- [ ] **Step 1: Create the bundle dir and move both files**

```bash
mkdir -p planning/changes/2026-07-01.01-openapi-versioning-fastapi-0139
git mv docs/superpowers/specs/2026-07-01-openapi-versioning-fastapi-0139-design.md \
       planning/changes/2026-07-01.01-openapi-versioning-fastapi-0139/design.md
git mv docs/superpowers/plans/2026-07-02-openapi-versioning-fastapi-0139.md \
       planning/changes/2026-07-01.01-openapi-versioning-fastapi-0139/plan.md
```

- [ ] **Step 2: Add lean frontmatter to the migrated `design.md` and drop the redundant `Date:` line**

The convention requires `summary:` only on `design.md`; `date`/`slug` come from the dir name. Edit `planning/changes/2026-07-01.01-openapi-versioning-fastapi-0139/design.md`:

Prepend at the very top of the file:

```
---
summary: Restored multi-version OpenAPI schema generation under FastAPI 0.139+ via a single get_openapi call over version-suffixed route copies (shipped in #12).
---

```

Then delete the body line `Date: 2026-07-01` (and the blank line following it) — the date is derived from the bundle directory name. Leave everything else (from `## Problem` onward) unchanged. `plan.md` carries **no** frontmatter — leave it exactly as moved.

- [ ] **Step 3: Remove the now-empty docs/superpowers tree**

```bash
rm -rf docs/superpowers
rmdir docs 2>/dev/null || true
```

Run: `test ! -e docs/superpowers && echo DOCS_GONE`
Expected: `DOCS_GONE`.

- [ ] **Step 4: Validate the bundles**

Run: `uv run python planning/index.py --check`
Expected: `planning: OK` (both the adopt bundle and the migrated bundle pass name-format, allowed-files, and required-`summary` checks).

- [ ] **Step 5: Confirm the index renders both changes**

Run: `uv run python planning/index.py`
Expected: a `## Changes` list containing `adopt-planning-convention` (2026-07-02) and `openapi-versioning-fastapi-0139` (2026-07-01), newest-first.

- [ ] **Step 6: Commit**

```bash
git add planning/changes/2026-07-01.01-openapi-versioning-fastapi-0139 docs
git commit -m "docs(planning): migrate OpenAPI-0.139 spec+plan into a change bundle"
```

---

### Task 5: Wire the validator into the Justfile

Add the `index` / `check-planning` recipes and make `lint-ci` run the validator.

**Files:**
- Modify: `Justfile`

- [ ] **Step 1: Add the validator step to `lint-ci`**

In `Justfile`, change the `lint-ci` recipe from:

```
lint-ci:
    uv run ruff format . --check
    uv run ruff check . --no-fix
    uv run mypy .
```

to:

```
lint-ci:
    uv run ruff format . --check
    uv run ruff check . --no-fix
    uv run mypy .
    uv run python planning/index.py --check
```

- [ ] **Step 2: Add the `index` and `check-planning` recipes**

Insert after the `test` recipe (before `publish`):

```
index:
    uv run python planning/index.py

check-planning:
    uv run python planning/index.py --check
```

- [ ] **Step 3: Verify the recipes work**

Run: `just check-planning`
Expected: `planning: OK`.
Run: `just index | head -5`
Expected: starts with `# Planning index`.

- [ ] **Step 4: Commit**

```bash
git add Justfile
git commit -m "build: wire planning validator into lint-ci + add index recipes"
```

---

### Task 6: Merge the CLAUDE.md pointers

Add a `## Workflow` section (authoritative convention pointer + the unification override) and the promotion reminder in `## Architecture`. Preserve all other content.

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Insert the `## Workflow` section after the single-test line**

Find:

```
Run a single test: `just test tests/test_app.py::test_get` or
`uv run pytest -k test_openapi_schema`.
```

Insert immediately after it:

```

## Workflow

Planning follows the convention in [`planning/README.md`](planning/README.md) —
its **Quick path** is authoritative. Pick a lane (Full = `design.md` + `plan.md`,
Lightweight = `change.md`, Tiny = conventional commit) and create a bundle under
`planning/changes/YYYY-MM-DD.NN-<slug>/`. In this repo the superpowers
brainstorming/writing-plans flow writes specs and plans **into that bundle**, not
into `docs/superpowers/`. Run `just check-planning` before pushing.
```

- [ ] **Step 2: Add the promotion reminder under `## Architecture`**

Find:

```
## Architecture

Versioning is implemented across three layers that cooperate through the ASGI
```

Replace with:

```
## Architecture

> **Promotion rule:** when a change alters a capability's behavior, update the
> matching `architecture/<capability>.md` in the same PR (see
> `architecture/README.md`).

Versioning is implemented across three layers that cooperate through the ASGI
```

- [ ] **Step 3: Verify**

Run: `grep -q '^## Workflow' CLAUDE.md && grep -q 'Promotion rule' CLAUDE.md && echo CLAUDE_OK`
Expected: `CLAUDE_OK`.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: point CLAUDE.md at the planning convention + promotion rule"
```

---

### Task 7: Full verification (APPLY §6)

Confirm the whole repo is green before opening the PR.

- [ ] **Step 1: Planning check**

Run: `just check-planning`
Expected: `planning: OK`.

- [ ] **Step 2: Full lint-ci (now includes the planning step)**

Run: `just lint-ci`
Expected: ruff format clean, ruff check clean, mypy `Success`, `planning: OK`. Exit 0.

- [ ] **Step 3: Test suite unchanged and green**

Run: `just test`
Expected: same pass count as before adoption (source/tests untouched); no errors. Coverage report prints (no fail-under configured).

- [ ] **Step 4: Confirm no stray files / no uv.lock staged**

Run: `git status --porcelain && git diff --cached --name-only | grep -q uv.lock && echo "LOCK_STAGED_BUG" || echo "clean"`
Expected: working tree clean, `clean` (uv.lock not staged).

---

### Task 8: Push and open the PR

- [ ] **Step 1: Push the branch**

```bash
git push -u origin chore/adopt-planning-convention
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "Adopt planning-convention (fresh adopt v1.1.1)" --body "$(cat <<'EOF'
Fresh adopt of lesnik512/planning-convention at **v1.1.1** (APPLY.md §§1-6).

**What landed**
- `planning/`: verbatim `index.py` + `_templates/*`, `.convention-version` (1.1.1), convention `README.md`, `deferred.md`, `decisions/`, `releases/`.
- `architecture/README.md`: truth-home + promotion rule (capability files authored lazily).
- `Justfile`: `index` / `check-planning` recipes; `lint-ci` now runs `python planning/index.py --check`.
- `CLAUDE.md`: `## Workflow` pointer + `## Architecture` promotion reminder.

**Unification (repo-specific)**
- The superpowers spec/plan flow now writes into `planning/changes/<bundle>/`.
- Migrated the shipped OpenAPI-0.139 spec+plan from `docs/superpowers/` into `planning/changes/2026-07-01.01-openapi-versioning-fastapi-0139/` and removed `docs/superpowers/`.
- This adoption dogfoods the convention: it lives in `planning/changes/2026-07-02.01-adopt-planning-convention/`.

**Deviation from vanilla APPLY**
- `planning/index.py` carries a one-line `# ruff: noqa: INP001` header so it passes fast-version's stricter ruff (`select=["ALL"]`, no `INP` ignore) without a `planning/__init__.py` — matching the modern-python convention repos. Keeping `planning/` a non-package also keeps the vendored validator out of `--cov=.`, so coverage stays 100%. No pyproject changes. Note: canonical `main`'s v1.1.1 `index.py` does not yet ship this header, so a future APPLY re-copy must re-add it.

Verified locally: `just check-planning` → `planning: OK`; `just lint-ci` green; `just test` green.
EOF
)"
```

- [ ] **Step 3: Watch CI**

Run: `gh pr checks --watch`
Expected: the reusable `community-of-python/community-workflow` matrix (Python 3.10-3.14) passes. If a version fails, reproduce locally with that interpreter before pushing a fix.

---

## Notes

- Do not run `just install` as part of this work — it does `uv lock --upgrade` and could pull unrelated dependency bumps into the branch. This adoption adds no dependencies.
- If a future convention update lands, re-run the canonical `APPLY.md` UPDATE path (applies only CHANGELOG entries newer than the recorded `1.1.1`); it will overwrite `planning/index.py` and `planning/_templates/*` verbatim again — re-add the `# ruff: noqa: INP001` header to `index.py` afterward (canonical `main` does not yet carry it) and do not create a `planning/__init__.py`.
