---
status: accepted
summary: The ClassProperty + per-route VersionedJSONResponse stay; the descriptor's lazy class-level read is what makes init_fastapi_versioning order-independent w.r.t. include_router, so collapsing it would impose an init-ordering contract or lifespan coupling.
supersedes: null
superseded_by: null
---

# ClassProperty stays: it decouples init timing from route registration

**Decision:** Keep `helpers.ClassProperty` and the per-route
`VersionedJSONResponse` subclass built in `VersionedAPIRouter.api_route`. Do
**not** collapse them by resolving the response `media_type` to a plain string.

## Context

An architecture review (candidate 3) flagged `ClassProperty` as the one
bespoke abstraction in the codebase — a hand-rolled `classproperty` living in
the otherwise-generic `helpers.py`, existing only so each versioned route's
response `media_type` can be `f"{vendor}; version=X.Y"`. The vendor is unknown
when the route is decorated (it is set later by `init_fastapi_versioning`), so
`media_type` is computed lazily at access time via the descriptor.

Verified mechanics (FastAPI 0.139.0 / Starlette 1.3.1):

- `get_openapi` reads `route.response_class.media_type` **live** at
  schema-generation time (`fastapi/openapi/utils.py:279`), which runs on the
  first `/openapi.json` request — after `init`.
- `APIRoute.__init__` eagerly builds the runtime handler and captures the
  `response_class` **object** in a closure; Starlette reads `media_type` off
  that class live per response.
- `_custom_openapi` rewrites only `requestBody` content keys, not response
  content — so response content-type versioning in the schema comes solely
  from `response_class.media_type`.

Proposed shapes: **A1** resolve `media_type` to a plain string in `init` by
iterating `app.routes`; **A2** resolve it in a startup/lifespan handler `init`
registers; **B** delete the per-route classes and version the response
content-type in the middleware + a symmetric `_custom_openapi` response
rewrite.

## Decision & rationale

Rejected all of them; `ClassProperty` stays. The deciding discovery is that
**the descriptor's laziness is load-bearing, not gratuitous** — it decouples
*when the vendor is configured* from *when routes are registered*. Concretely,
the two shipped usages call `init` in opposite orders and both work only
because of it:

- `README.md` calls `include_router(...)` then `init_fastapi_versioning(...)`
  (init **last**).
- `tests/conftest.py` calls `init_fastapi_versioning(...)` then
  `include_router(...)` (init **first**).

Given that, each alternative trades the descriptor for a worse cost:

- **A1** works only when routes are already mounted at `init` time, so it
  imposes a new contract — "call `init_fastapi_versioning` after every
  `include_router`" — and breaks the init-first order the tests (and likely
  users) rely on. A behavior change to buy the removal of a 6-line descriptor.
- **A2** keeps order-independence but reaches `init` into app lifespan
  (mutating route internals from a startup handler), risking interaction with
  user-defined lifespans and using the older event idiom — heavier coupling
  than what it replaces.
- **B** removes the most, but at ASGI send time the middleware cannot cleanly
  tell a `VersionedAPIRoute` response (wants `vendor; version=X.Y`) from a
  plain `APIRouter` response (must stay `application/json`) — `scope["version"]`
  is present for both via the default — so it would over-stamp the vendor
  content-type onto non-versioned responses without new route→scope plumbing
  and send-message interception.

`ClassProperty` is small, isolated, and its laziness is exactly the property
that makes the library forgiving about configuration order. That is worth its
six lines.

## Revisit trigger

Reopen if any of these change:

- The project decides to make init-ordering explicit anyway (e.g. requires
  `init_fastapi_versioning` last for another reason), which would make **A1**
  free.
- Python or the typing stack gains a clean, standard class-level lazy property,
  removing the "bespoke" objection to `ClassProperty` without changing timing.
- FastAPI adds a per-route response content-type hook that does not require a
  class-level `media_type`, or `_custom_openapi` starts rewriting response
  content for another reason (which would make **B**'s schema half free).
