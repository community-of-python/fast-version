import contextlib
import copy
import re
import typing
from types import MethodType

import fastapi
from fastapi.openapi.utils import get_openapi
from starlette import types
from starlette.responses import JSONResponse

from fast_version import helpers
from fast_version.router import VersionedAPIRoute, VersionedAPIRouter


_VERSION_RE: typing.Final = re.compile(r"^\d\.\d$")


def _get_vendor_media_type() -> str:
    return VersionedAPIRouter.VENDOR_MEDIA_TYPE


def init_fastapi_versioning(*, app: fastapi.FastAPI, vendor_media_type: str) -> None:
    VersionedAPIRouter.VENDOR_MEDIA_TYPE = vendor_media_type
    app.add_middleware(FastAPIVersioningMiddleware)
    app.openapi = MethodType(_custom_openapi, app)  # type: ignore[method-assign]


class FastAPIVersioningMiddleware:
    def __init__(self, app: fastapi.FastAPI) -> None:
        self.app = app

    async def __call__(self, scope: types.Scope, receive: types.Receive, send: types.Send) -> None:
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
                error_response = JSONResponse({"detail": "Wrong media type"}, status_code=406)
                break

            version = ""
            version_key = ""
            with contextlib.suppress(ValueError):
                version_key, version = version_str.strip().split("=")

            if version_key.lower().strip() != "version":
                error_response = JSONResponse({"detail": "No version in Accept header"}, status_code=400)
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


def _custom_openapi(self: fastapi.FastAPI) -> dict[str, typing.Any]:
    if self.openapi_schema:
        return self.openapi_schema

    routes = []
    for route_item in self.routes:
        if not isinstance(route_item, VersionedAPIRoute):
            routes.append(route_item)
            continue

        # trick to avoid merging routes
        route_copy: VersionedAPIRoute = copy.copy(route_item)
        route_copy.path_format = f"{route_copy.path_format}:{route_copy.version_str}"
        routes.append(route_copy)

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
    paths_dict = {}
    raw_path: str
    methods: dict[str, typing.Any]
    for raw_path, methods in self.openapi_schema["paths"].items():
        if ":" not in raw_path:
            continue
        clean_path, version = raw_path.split(":")
        for payload in methods.values():
            if "requestBody" not in payload:
                continue
            payload["requestBody"]["content"] = {
                f"{_get_vendor_media_type()}; version={version}": v
                for k, v in payload["requestBody"]["content"].items()
            }

        if clean_path not in paths_dict:
            paths_dict[clean_path] = methods
            continue

        helpers.dict_merge(paths_dict[clean_path], methods)
    self.openapi_schema["paths"] = paths_dict
    return self.openapi_schema
