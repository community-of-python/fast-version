# Planning

fast-version's planning home. The two axes: [`../architecture/`](../architecture/)
holds the living truth about what the library does **now**; [`changes/`](changes/)
records how it got there. The Quick path and Conventions below are applied from
[`lesnik512/planning-convention`](https://github.com/lesnik512/planning-convention)
(applied version in [`.convention-version`](.convention-version)); update them by
running that repo's `APPLY.md` flow.

## Quick path (start here)

> The fast lane for making a change. The full reference is in
> [Conventions](#conventions) below — read it only when this isn't enough.

**1. Choose a lane — first matching rule wins:**

1. Any of: needs design judgment · new file/module · public-API change ·
   cross-cutting or multi-file · non-trivial test design → **Full**
   (`design.md` + `plan.md`)
2. Purely mechanical: typo · dep bump · linter/formatter/CI tweak ·
   mechanical rename · single-line config → **Tiny** (no bundle, conventional
   commit)
3. Small-but-real, none of the above: ≲30 LOC net · ≤2 files · no new file ·
   no public-API change · one straightforward test → **Lightweight**
   (`change.md`)

Ambiguous between two? Take the heavier. A `change.md` that outgrows its lane
splits into `design.md` + `plan.md`.

**2. Create the bundle** (Full / Lightweight only):
`planning/changes/YYYY-MM-DD.NN-<slug>/`, where `.NN` is a zero-padded
intra-day counter. Copy the matching template from
[`_templates/`](_templates/).

**3. Ship in the implementing PR:** hand-edit the affected
`architecture/<capability>.md`, finalize the bundle's `summary:` to the
realized result, and run `just check-planning` before pushing.

## Conventions

> This is the portable convention, sourced from the canonical repo
> [`lesnik512/planning-convention`](https://github.com/lesnik512/planning-convention)
> (applied version in [`.convention-version`](.convention-version)). To update
> it, run that repo's `APPLY.md` flow. The generated change index (`just index`)
> and the `## Other` pointers below are repo-local.

### Two axes, never mixed

- **`architecture/` (repo root) — the present.** One file per capability, plus
  a single `glossary.md` (the ubiquitous language); living prose, updated in the
  same PR that ships the change. The truth home.
- **`planning/changes/` — the past-and-pending.** One folder per change,
  kept in place after ship.

A change **promotes** its conclusions into the affected
`architecture/<capability>.md` by hand **in the implementing PR, alongside the
code** — the edit rides in the same diff and is reviewed with it, never applied
as a separate post-merge step. That hand-edit is what keeps `architecture/`
true; the bundle stays in `changes/` as the *why*.

### Glossary

`architecture/glossary.md` is the project's **ubiquitous language** — one page
defining the domain terms that code, specs, and capability pages all share. Like
the capability files beside it, it is living prose with **no frontmatter**, dated
by git, and authored lazily: it appears when the first term is worth pinning down.

Each entry is a term, a one-or-two-sentence definition of what it *is* (not what
it does), and an optional `_Avoid_:` line naming the synonyms to reject:

```md
**Timer**:
A scheduled future delivery, identified by a timer id.
_Avoid_: job, task, alarm
```

Keep it a glossary, not a spec — no implementation detail. A change that
introduces or sharpens a term updates `glossary.md` in the same PR, the same way
a behavior change promotes into a capability file.

### Change bundles

A change is a folder `changes/YYYY-MM-DD.NN-<slug>/`:

- `YYYY-MM-DD` — proposal date; `.NN` — zero-padded intra-day counter
  (`.01`, `.02`, …) that breaks same-date ties so the timeline sorts stably.
- `<slug>` — kebab-case description, not a story ID.

`summary` is written when the change is created (the intent one-liner) and
**finalized at ship** to state the realized result — set in the implementing
PR, alongside the code and the `architecture/` promotion. No post-merge
bookkeeping, no folder move. `date` and `slug` are never written — they are
read from the bundle's directory name.

### Three lanes

| Lane | Artifacts | Use when |
|------|-----------|----------|
| **Full** | `design.md` + `plan.md` | design judgment; new file/module; public-API change; cross-cutting/multi-file; non-trivial test design |
| **Lightweight** | `change.md` | small-but-real: ≲30 LOC net, ≤2 files, no new file, no public-API change, single straightforward test |
| **Tiny** | none — conventional commit | typo, dep bump, linter/formatter/CI tweak, mechanical rename, single-line config |

Heavier lane wins on ambiguity. A `change.md` that outgrows its lane splits
into `design.md` + `plan.md`.

### Artifacts at a glance

- **`design.md`** — the spec: the *thinking* (why, design, trade-offs, scope).
- **`plan.md`** — the plan: the *sequencing* (the executor's task checklist).
- **`change.md`** — both, condensed, for the lightweight lane.
- **`releases/<semver>.md`** — per-release user-facing notes.
- **`audits/<date>-<slug>.md`** — findings from a code/docs/bug-hunt sweep;
  spawns fix changes.
- **`retros/<date>-<slug>.md`** — what we learned after a body of work.
- **`deferred.md`** — real-but-unscheduled items, each with a revisit trigger.
- **`decisions/<YYYY-MM-DD>-<slug>.md`** — one file per design decision taken
  (especially options *rejected*), each with a revisit trigger; listed by
  `just index`.

Templates live in [`_templates/`](_templates/).

### Frontmatter

`date` and `slug` are **derived from the directory / file name** — never
repeated in frontmatter. So:

- `design.md` / `change.md`: `summary` (single line) only.
- `plan.md`: **no frontmatter** — its identity is the bundle directory.
- `decisions/*.md`: `status` (accepted|superseded), `summary`, and optional
  `supersedes` / `superseded_by`.
- Files in `architecture/` carry **no** frontmatter — living prose, dated by git.

**`summary`** is one line: written at creation as the intent, then **finalized
at ship** to state the realized result — what shipped and its effect. It is the
only field the index renders.

## Index

`just index` prints the change/decision listing (a query over the bundles,
newest-first — never committed). `just check-planning` validates the bundles.

## Other

- [`deferred.md`](deferred.md) — real-but-unscheduled items, each with a revisit trigger.
- [`../architecture/README.md`](../architecture/README.md) — the promotion rule for the truth home.
