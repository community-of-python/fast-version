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
