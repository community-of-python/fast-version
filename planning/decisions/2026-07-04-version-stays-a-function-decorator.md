---
status: accepted
summary: Per-route version stays on the endpoint function (set_api_version); it is not folded into a version= kwarg on the router verb methods, because FastAPI's closed verb signatures make every alternative worse.
supersedes: null
superseded_by: null
---

# Version stays a function decorator, not a route kwarg

**Decision:** Keep attaching the per-route version to the endpoint function
(the `version` attribute, set by `VersionedAPIRouter.set_api_version` or
defaulted in `api_route`). Do **not** rework it into a `version=` parameter on
the router's verb methods.

## Context

An architecture review (candidate 2, `planning/changes/` bundle
`2026-07-04.01-extract-accept-version-parse` was candidate 1) flagged
`set_api_version` as a shallow pass-through: its whole body is
`setattr(func, "version", version)`, the version is read back by name in three
places (`api_route`, `VersionedAPIRoute.version`, and the response media type),
it needs a `# ruff: noqa: B009, B010` for getattr/setattr-with-constant, and the
two decorators must be **stacked in the right order** — `@ROUTER.set_api_version`
has to sit *below* `@ROUTER.get`, or the route is registered before the version
attribute exists. The proposed deepening was to declare the version where the
route is declared: `@ROUTER.get("/test/", version=(2, 0))`.

Three mechanisms were on the table:

- **A — thin verb-method overrides.** Override `.get/.post/.put/.delete/.patch/
  .options/.head` to accept `version=` and forward the rest via `**kwargs` to
  `super().<verb>()`, setting `func.version` before the parent decorator
  registers the route.
- **B — one versioned method.** A single `@ROUTER.versioned("/test/",
  methods=["GET"], version=(2, 0))`, or reuse the already-`**kwargs`
  `api_route` override.
- **C — reject; keep `set_api_version`.**

## Decision & rationale

Chose **C**. The blocker is a verified FastAPI constraint (checked against
FastAPI 0.139.0 / Starlette 1.3.1 in `.venv`):

> FastAPI's verb methods (`APIRouter.get`, `.post`, …) forward a **closed,
> explicit list of named parameters** to `api_route` — there is no `**kwargs`
> passthrough — and `api_route`'s own signature is likewise closed. So a
> `version=` keyword on `.get()` raises `TypeError: got an unexpected keyword
> argument 'version'` unless the verb methods are overridden.

Given that, every alternative trades away more than it removes:

- **A** realizes the target ergonomics but forces the seven/eight forwarded
  verb signatures to collapse into `**kwargs`, so library users lose the
  explicit `response_model=`/`status_code=`/… parameters and their IDE
  autocomplete on the verb methods. Adding ~30 parameters' worth of lost
  signature surface (or ~240 lines re-declaring them) to delete a 3-line
  pass-through fails the deletion test — it moves and multiplies interface
  complexity rather than concentrating it.
- **B** invents a second routing idiom that sits awkwardly beside the familiar
  `.get`/`.post`, for a marginal gain.
- The friction **C** leaves in place is real but bounded: the stacking order is
  documented in `CLAUDE.md`, and the `set_api_version` mechanism is one small
  method. The eager-registration model (FastAPI adds the route the moment the
  verb decorator is applied) is what makes the order matter; nothing short of
  overriding the verb methods removes it.

So the function-attribute mechanism stays. It is the least-bad fit for
FastAPI's closed signatures, and the cost of "fixing" it exceeds the cost of
living with it.

## Revisit trigger

Reopen if any of these change:

- FastAPI gives `APIRouter` verb methods a `**kwargs` passthrough (or an
  official per-route metadata slot), so `version=` can ride along without
  re-declaring signatures.
- FastAPI stops registering routes eagerly at decoration time, removing the
  decorator-stacking order dependency by itself.
- The project decides the `.get`/`.post` explicit signatures are not worth
  preserving (e.g. it already wraps them for another reason), which would make
  **A** cheap.
