---
summary: Match the vendor media type case-insensitively per RFC 9110/6838, so a mixed-case configured vendor no longer silently falls through to Ignore.
---

# Change: Case-insensitive vendor media-type matching

**Lane:** lightweight — one-line behavior fix in `accept.py` plus one seam test;
no new file, no public-API change.

## Goal

`parse_accept_version` compared the request media type (already lowercased by
`get_accept_header_from_scope`) against `vendor_media_type` as configured. A
mixed-case vendor (e.g. `application/vnd.Some.Name+json`) never matched and the
request silently fell through to `Ignore`, defaulting to v1.0. Media types are
case-insensitive (RFC 9110 §8.3.1, RFC 6838 §4.2), so the match must be too.
Resolves the item recorded in [`../../deferred.md`](../../deferred.md).

## Approach

Lowercase the vendor in the comparison only:
`media_type.strip() != vendor_media_type.lower()`. This is the robustness
principle — liberal in what we accept (case-insensitive match), conservative in
what we send: the response `content-type` still echoes the exact casing the user
configured (that string is unchanged, so no emitted-header behavior changes).
Normalizing at `init` was rejected because it would also rewrite the emitted
content-type casing — a change beyond the bug, with no spec basis.

## Files

- `fast_version/accept.py` — `.lower()` on the vendor in the media-type check.
- `tests/test_accept.py` — `test_parse_matches_vendor_case_insensitively`: a
  mixed-case vendor matches a lowercased request media type → `ParsedVersion`.
- `planning/deferred.md` — remove the now-resolved entry.

## Verification

- [x] Failing test first — `pytest tests/test_accept.py::test_parse_matches_vendor_case_insensitively`
      → `AssertionError: Ignore() == ParsedVersion(version=(1, 0))`.
- [x] Apply the `.lower()` fix.
- [x] Test passes.
- [ ] `just test-ci` — full suite green, coverage 100%.
- [ ] `just lint-ci` — ruff + ty clean, `planning: OK`.
