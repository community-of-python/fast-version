import copy
import typing
from types import MethodType

import fastapi
from fastapi.openapi.utils import get_openapi
from fastapi.routing import RouteContext, iter_route_contexts
from starlette import types
from starlette.responses import JSONResponse
from starlette.routing import BaseRoute

from fast_version import accept, helpers
from fast_version.router import VersionedAPIRoute, VersionedAPIRouter


def _get_vendor_media_type() -> str:
    return VersionedAPIRouter.VENDOR_MEDIA_TYPE


def init_fastapi_versioning(*, app: fastapi.FastAPI, vendor_media_type: str) -> None:
    VersionedAPIRouter.VENDOR_MEDIA_TYPE = vendor_media_type
    app.add_middleware(FastAPIVersioningMiddleware)  # ty: ignore[invalid-argument-type]
    app.openapi = MethodType(_custom_openapi, app)  # ty: ignore[invalid-assignment]


class FastAPIVersioningMiddleware:
    def __init__(self, app: fastapi.FastAPI) -> None:
        self.app = app

    async def __call__(
        self,
        scope: types.Scope,
        receive: types.Receive,
        send: types.Send,
    ) -> None:
        if scope["type"] == "http":
            header = accept.get_accept_header_from_scope(scope)
            result = accept.parse_accept_version(header, VersionedAPIRouter.VENDOR_MEDIA_TYPE)
            match result:
                case accept.ParsedVersion(version):
                    scope["version"] = version
                case accept.ParseError(detail):
                    response = JSONResponse({"detail": detail}, status_code=400)
                    return await response(scope, receive, send)
                case accept.Ignore():
                    pass
        return await self.app(scope, receive, send)


def _iter_openapi_routes(
    app: fastapi.FastAPI,
) -> tuple[list[BaseRoute | RouteContext], set[str]]:
    """Build the route list for a single ``get_openapi`` call.

    Traverses nested routers (FastAPI wraps included routers in an opaque object), so
    routes added via ``app.include_router`` are found and keep their effective paths.
    Non-versioned routes pass through unchanged; each versioned route is shallow-copied
    with its ``path_format`` suffixed by ``:<version>`` so ``get_openapi`` keeps
    same-path versions distinct within one call. A single call is required so FastAPI
    disambiguates same-named-but-different Pydantic models across versions.

    Returns the route list plus the set of suffixed paths it produced, so schema
    post-processing can identify versioned paths by exact match rather than by sniffing
    for a colon (a non-versioned path may legitimately contain one, e.g. ``/x:action``).
    """
    routes: list[BaseRoute | RouteContext] = []
    versioned_paths: set[str] = set()
    for route_context in iter_route_contexts(app.routes):
        original_route = route_context.original_route
        if not isinstance(original_route, VersionedAPIRoute):
            routes.append(route_context)
            continue
        suffixed_path = f"{route_context.path_format}:{original_route.version_str}"
        route_copy = copy.copy(original_route)
        route_copy.path_format = suffixed_path
        routes.append(route_copy)
        versioned_paths.add(suffixed_path)
    return routes, versioned_paths


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


def _custom_openapi(self: fastapi.FastAPI) -> dict[str, typing.Any]:
    if self.openapi_schema:
        return self.openapi_schema

    routes, versioned_paths = _iter_openapi_routes(self)
    self.openapi_schema = get_openapi(
        title=self.title,
        version=self.version,
        openapi_version=self.openapi_version,
        summary=self.summary,
        description=self.description,
        terms_of_service=self.terms_of_service,
        contact=self.contact,
        license_info=self.license_info,
        routes=routes,
        webhooks=self.webhooks.routes,
        tags=self.openapi_tags,
        servers=self.servers,
    )

    self.openapi_schema["paths"] = _collapse_versioned_paths(
        self.openapi_schema["paths"],
        versioned_paths,
        _get_vendor_media_type(),
    )
    return self.openapi_schema
