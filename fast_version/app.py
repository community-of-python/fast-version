import contextlib
import copy
import re
import typing
from types import MethodType

import fastapi
from fastapi.openapi.utils import get_openapi
from fastapi.routing import RouteContext, iter_route_contexts
from starlette import types
from starlette.responses import JSONResponse
from starlette.routing import BaseRoute

from fast_version import helpers
from fast_version.router import VersionedAPIRoute, VersionedAPIRouter


_VERSION_RE: typing.Final = re.compile(r"^\d\.\d$")


def _get_vendor_media_type() -> str:
    return VersionedAPIRouter.VENDOR_MEDIA_TYPE


def init_fastapi_versioning(*, app: fastapi.FastAPI, vendor_media_type: str) -> None:
    VersionedAPIRouter.VENDOR_MEDIA_TYPE = vendor_media_type
    app.add_middleware(FastAPIVersioningMiddleware)  # type: ignore[arg-type]
    app.openapi = MethodType(_custom_openapi, app)  # type: ignore[method-assign]


class FastAPIVersioningMiddleware:
    def __init__(self, app: fastapi.FastAPI) -> None:
        self.app = app

    async def __call__(
        self,
        scope: types.Scope,
        receive: types.Receive,
        send: types.Send,
    ) -> None:
        error_response: JSONResponse | None = None
        while True:
            if scope["type"] != "http":
                break

            accept_header_from_request = helpers.get_accept_header_from_scope(scope)
            if not accept_header_from_request or accept_header_from_request == "*/*":
                break

            media_type: str
            version_str: str
            try:
                media_type, version_str = accept_header_from_request.split(";")
            except ValueError:
                break

            if media_type.strip() != _get_vendor_media_type():
                break

            version = ""
            version_key = ""
            with contextlib.suppress(ValueError):
                version_key, version = version_str.strip().split("=")

            if version_key.lower().strip() != "version":
                error_response = JSONResponse(
                    {"detail": "No version in Accept header"},
                    status_code=400,
                )
                break

            if not _VERSION_RE.match(version):
                error_response = JSONResponse(
                    {"detail": "Version should be in <major>.<minor> format"},
                    status_code=400,
                )
                break

            scope["version"] = tuple(int(version_part) for version_part in version.split("."))
            break
        if error_response:
            return await error_response(scope, receive, send)
        return await self.app(scope, receive, send)


def _iter_openapi_routes(app: fastapi.FastAPI) -> list[BaseRoute | RouteContext]:
    """Build the route list for a single ``get_openapi`` call.

    Traverses nested routers (FastAPI wraps included routers in an opaque object), so
    routes added via ``app.include_router`` are found and keep their effective paths.
    Non-versioned routes pass through unchanged; each versioned route is shallow-copied
    with its ``path_format`` suffixed by ``:<version>`` so ``get_openapi`` keeps
    same-path versions distinct within one call. A single call is required so FastAPI
    disambiguates same-named-but-different Pydantic models across versions.
    """
    routes: list[BaseRoute | RouteContext] = []
    for route_context in iter_route_contexts(app.routes):
        original_route = route_context.original_route
        if not isinstance(original_route, VersionedAPIRoute):
            routes.append(route_context)
            continue
        route_copy = copy.copy(original_route)
        route_copy.path_format = f"{route_context.path_format}:{original_route.version_str}"
        routes.append(route_copy)
    return routes


def _custom_openapi(self: fastapi.FastAPI) -> dict[str, typing.Any]:
    if self.openapi_schema:
        return self.openapi_schema

    self.openapi_schema = get_openapi(
        title=self.title,
        version=self.version,
        openapi_version=self.openapi_version,
        summary=self.summary,
        description=self.description,
        terms_of_service=self.terms_of_service,
        contact=self.contact,
        license_info=self.license_info,
        routes=_iter_openapi_routes(self),
        webhooks=self.webhooks.routes,
        tags=self.openapi_tags,
        servers=self.servers,
    )

    vendor_media_type = _get_vendor_media_type()
    paths_dict: dict[str, typing.Any] = {}
    raw_path: str
    methods: dict[str, typing.Any]
    for raw_path, methods in self.openapi_schema["paths"].items():
        if ":" not in raw_path:
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
    self.openapi_schema["paths"] = paths_dict
    return self.openapi_schema
