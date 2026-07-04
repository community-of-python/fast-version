---
summary: Extract the OpenAPI path-collapse/content-rewrite loop out of _custom_openapi into a pure _collapse_versioned_paths function, unit-testable at its own seam, mirroring the already-extracted _iter_openapi_routes.
---

# Give the OpenAPI path-collapse its own seam

## Summary

`_custom_openapi` (`fast_version/app.py`) ends with a ~25-line loop that collapses
the per-version `:<version>`-suffixed paths back onto their real path: it splits
the suffix, rewrites each `requestBody` content key to `{vendor}; version=X.Y`,
and merges same-path versions via `helpers.dict_merge`. That loop is a pure
`dict -> dict` transform, but it lives inside the monkey-patched `app.openapi`, so
the only way to exercise it is to build an app and fetch `/openapi.json`. This
change lifts it into `_collapse_versioned_paths(raw_paths, versioned_paths,
vendor_media_type) -> dict`, testable directly with fixture dicts. Behavior is
preserved exactly.

## Motivation

`_iter_openapi_routes` — the *first* half of the OpenAPI-versioning transform (build
the suffixed route list) — is already a module-level function with a direct unit
test (`test_iter_openapi_routes_finds_prefixed_versioned_paths`). Its second half,
the schema-collapse loop, was left inline. The asymmetry is the friction: one half
is testable at a seam, the other only through the full pipeline. Extracting the
loop completes the pattern and makes the collapse rules (colon split, content-key
rewrite, per-version merge) verifiable without an ASGI round-trip.

This is a modest tidy-up, not a hot spot — the integration tests already cover the
happy paths. The win is locality and a unit seam, not a bug surface.

## Non-goals

- No behavior change. The in-place `requestBody` content rewrite and the
  `dict_merge` semantics are preserved exactly.
- No new module. The function sits next to `_iter_openapi_routes` in `app.py`
  (see the rejected alternative below).
- No change to `_iter_openapi_routes`, the middleware, or the response-class
  mechanism.

## Design

### 1. New module-level function in `app.py`

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

Vendor is a plain argument (not read from the `VENDOR_MEDIA_TYPE` global inside),
so the function is pure with respect to global state and tests pass any vendor
string. The in-place payload mutation is kept — it is behavior-preserving and
invisible to callers that build a fresh schema each time.

### 2. `_custom_openapi` calls it

The tail of `_custom_openapi` collapses to:

```python
    self.openapi_schema["paths"] = _collapse_versioned_paths(
        self.openapi_schema["paths"],
        versioned_paths,
        _get_vendor_media_type(),
    )
    return self.openapi_schema
```

The local `vendor_media_type`, `paths_dict`, `raw_path`, `methods` variables and the
inline loop are removed; the explanatory comment moves into the function docstring.

### Rejected alternative

A dedicated `fast_version/openapi.py` owning both `_iter_openapi_routes` and
`_collapse_versioned_paths` was considered (symmetry with `accept.py`). Rejected as
YAGNI: `app.py` is ~127 lines with no size pressure, and relocating the working,
already-tested `_iter_openapi_routes` would churn its test import for a cohesion gain
that isn't paying rent. If `app.py` later grows, promoting both is a clean follow-up.

## Testing

Four unit tests in `tests/test_app.py` (beside the `_iter_openapi_routes` test),
calling `_collapse_versioned_paths` directly with fixture path-dicts — one per
branch:

1. Non-versioned path → passed through unchanged.
2. Versioned path with `requestBody` → content key rewritten to `{vendor};
   version=X.Y`, path un-suffixed.
3. Two versions of one path → merged onto the clean path (both media-type keys).
4. Versioned path without `requestBody` → collapsed, no content rewrite.

Pure addition — every existing OpenAPI integration test stays (they own
"the schema is correct through the real pipeline"; the unit tests own "the collapse
transform is correct at its seam"). `just test-ci` stays at 100% coverage;
`just lint-ci` clean.

## Risk

- **Coverage regression (low).** The four unit tests plus the retained integration
  tests cover every branch of the function. Mitigation: `just test-ci` before push.
- **Accidental behavior drift (low).** The loop moves verbatim; the only structural
  change is `return paths_dict` instead of assigning `self.openapi_schema["paths"]`
  inline. Mitigation: the existing integration tests (distinct-models, prefix,
  colon-preservation) exercise the real pipeline unchanged.
