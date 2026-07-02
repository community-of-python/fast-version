---
summary: Fresh-adopt the lesnik512/planning-convention (v1.1.2) and unify the superpowers spec/plan flow onto planning/changes/.
---

# Design: Adopt the planning-convention (fresh adopt, v1.1.2)

## Summary

Apply the portable planning convention from
[`lesnik512/planning-convention`](https://github.com/lesnik512/planning-convention)
to fast-version as a **fresh adopt** at version **1.1.2**, following that repo's
`APPLY.md` §§1–6. The convention installs a two-axis model — `architecture/`
(repo root; the living truth of what the system does now) and
`planning/changes/` (dated change bundles: the history) — plus a stdlib
validator (`planning/index.py`) wired into `lint-ci`. On top of the standard
adopt, unify the existing superpowers flow so brainstorming/writing-plans write
into `planning/changes/<bundle>/` instead of `docs/superpowers/`. This is
additive planning infrastructure; no `fast_version/` source or test behavior
changes.

## Motivation

The repo already runs a superpowers flow that writes specs to
`docs/superpowers/specs/` and plans to `docs/superpowers/plans/` (two artifacts
from the OpenAPI-0.139 work, shipped in #12, live there now). That location is
ad hoc and splits a single change's spec and plan across two directories with no
validator, no index, and no link to a `architecture/` truth home. The
planning-convention gives a single dated bundle per change, lean machine-checked
frontmatter, and a promotion rule that keeps architecture docs true in the same
PR as the code. Adopting it replaces the ad hoc layout with a portable,
agent-friendly one that is updated by re-running its `APPLY.md`.

## Non-goals

- No changes to `fast_version/` source or to any test in `tests/`.
- Do **not** pre-author `architecture/` capability files or
  `architecture/glossary.md`; the convention authors those lazily, when the
  first capability or term is worth pinning down. Only `architecture/README.md`
  (the promotion rule) is created now.
- No change to the release/publish flow, CI reusable-workflow wiring, or
  `pyproject.toml` beyond what the adopt requires (it requires none).
- Not a general refactor of `CLAUDE.md` or `README.md` — only the targeted
  merges `APPLY.md` prescribes.

## Design

### 1. Verbatim-copied files (owned by the canonical repo)

Copied exactly from the canonical repo, local edits intentionally discarded:

- `planning/index.py` — the validator + index generator (Python stdlib only, no
  new dependency). Resolves `changes/` and `decisions/` relative to its own
  parent (`planning/`) and tolerates their absence.
- `planning/_templates/{change,design,plan,decision,release,glossary}.md`.

### 2. Fresh-adopt scaffolding (`APPLY.md` §5)

- Directories: `planning/changes/`, `planning/decisions/`, `planning/releases/`.
- `planning/deferred.md` — one-line header for real-but-unscheduled items.
- `planning/README.md` — a fast-version-specific page title/intro, then the body
  of the canonical `convention.md` **below its `# Planning convention` title**
  (the Quick path + Conventions prose), then repo-local `## Index` and
  `## Other` sections. It points at `planning/.convention-version` and the
  canonical repo.
- `architecture/README.md` (repo root) — states the promotion rule: one file per
  capability; shipping a change hand-edits the matching
  `architecture/<capability>.md` in the same PR.

### 3. Version record

- `planning/.convention-version` → `1.1.2` (the latest CHANGELOG version).

### 4. Judgment-merged files (edit in place, preserve existing content)

- `Justfile`: add the two recipes
  ```
  index:
      uv run python planning/index.py
  check-planning:
      uv run python planning/index.py --check
  ```
  and add `uv run python planning/index.py --check` as a step in the existing
  `lint-ci` recipe (which already runs ruff-check, ruff-no-fix, mypy).
- `CLAUDE.md`: add a `## Workflow` section naming `planning/README.md`'s Quick
  path as the authoritative planning convention and recording the unification
  override (the superpowers brainstorming/writing-plans flow writes specs+plans
  into `planning/changes/<bundle>/`, not `docs/superpowers/`). Add the promotion
  reminder to the existing `## Architecture` section: "When a change alters a
  capability's behavior, update the matching `architecture/<capability>.md` in
  the same PR." All other content preserved.

### 5. Unification specifics

- **This adoption dogfoods the convention.** Its own design doc is this file, at
  `planning/changes/2026-07-02.01-adopt-planning-convention/design.md`
  (`summary:` frontmatter only). The `writing-plans` step adds `plan.md` to the
  same bundle.
- **Migrate the existing artifacts.** The two `docs/superpowers/` files (the
  OpenAPI-0.139 change shipped in #12) move into
  `planning/changes/2026-07-01.01-openapi-versioning-fastapi-0139/` as
  `design.md` + `plan.md`, reframed to lean frontmatter — `design.md` keeps a
  one-line `summary:` finalized to the realized result, `plan.md` carries none
  (its identity is the bundle directory). `date`/`slug` are dropped from
  frontmatter since they are derived from the directory name. After migration,
  remove the now-empty `docs/superpowers/` tree.

## Operations

None. All changes are in-repo files; no DNS, infra, or external accounts.

## Out of scope

Covered under Non-goals: source/test changes, seeding capability/glossary files,
and non-adopt refactors.

## Testing

- `just check-planning` must print `planning: OK` (validates both migrated
  bundles and this one: name format `YYYY-MM-DD.NN-slug`, allowed bundle files,
  required `summary` frontmatter on specs).
- `just lint-ci` must pass end to end, including the new planning-check step.
- `just test` must stay green (the suite is untouched; this confirms no
  incidental breakage).

## Risk

- **Low: frontmatter drift.** `index.py`'s `parse_frontmatter` is a minimal
  single-line-scalar reader; the migrated `design.md` must keep `summary` on one
  line and `plan.md` must have no frontmatter. Mitigation: run
  `just check-planning` before pushing.
- **Low: `lint-ci` breakage from the new step.** Mitigation: verify the step
  runs and exits 0 locally before opening the PR.
- **Low: losing history when removing `docs/superpowers/`.** Mitigation: the
  content is migrated (via `git mv` where possible) into the bundle, so git
  history is preserved; nothing is deleted outright.
