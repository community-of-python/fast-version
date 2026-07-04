---
status: accepted
summary: VENDOR_MEDIA_TYPE stays a process-global class attribute on VersionedAPIRouter; instance-scoping it collides with the per-route response-class mechanism and one vendor per process is an accepted constraint.
supersedes: null
superseded_by: null
---

# Vendor media type stays process-global class state

**Decision:** Keep the vendor media type as a mutable class attribute
(`VersionedAPIRouter.VENDOR_MEDIA_TYPE`), set once by
`init_fastapi_versioning`. Do **not** rework it into per-app / per-router
instance state.

## Context

Architecture review #2 (candidate B) flagged the vendor as process-global class
state: `VENDOR_MEDIA_TYPE` is a mutable class attribute read by three call sites
(the middleware, `_get_vendor_media_type`, and the response `ClassProperty`).
The consequences are real but mild — two FastAPI apps in one process cannot hold
different vendors, and the test suite relies on serial execution not to bleed the
global between apps. The proposed deepening was to make the vendor instance state
owned by the app/router that configured it.

## Decision & rationale

Rejected; the class-global stays. Two reasons:

- **It collides with a mechanism already decided.** The per-route response class
  reaches the vendor precisely *because* it is a class-level global it can read
  lazily (see the ClassProperty decision,
  `decisions/2026-07-04-classproperty-stays-for-ordering-independence.md`). A
  per-route `VersionedJSONResponse` subclass has no handle on its app or router
  instance, so instance-scoping the vendor would require re-plumbing exactly the
  response-content-type path that decision deliberately left alone.
- **One vendor per process is an accepted, documented constraint.** It is called
  out in `CLAUDE.md` ("effectively one vendor media type per process"). The
  library's public surface (`init_fastapi_versioning(app=, vendor_media_type=)`)
  reads as app-scoped, but the single-process-single-vendor reality has not
  caused friction, and no user has needed multi-vendor-per-process.

The global's cost (test-ordering fragility, one vendor per process) does not
justify re-plumbing a mechanism that is working and separately decided.

## Revisit trigger

Reopen if either changes:

- A concrete need arises to run two versioned apps with **different** vendor
  media types in the **same process** (e.g. mounting two independently-versioned
  APIs), making per-app vendor ownership load-bearing.
- The per-route response-class mechanism is reworked for another reason (its own
  revisit triggers are in the ClassProperty decision), at which point threading
  the vendor as instance state may become cheap.
