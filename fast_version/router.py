import typing

from fastapi.routing import APIRoute, APIRouter
from fastapi.types import DecoratedCallable
from starlette import types
from starlette.responses import JSONResponse
from starlette.routing import Match

from fast_version.helpers import ClassProperty


DEFAULT_VERSION: typing.Final = (1, 0)


# ruff: noqa: B009, B010
# allow getattr, setattr with const
class VersionedAPIRoute(APIRoute):
    @property
    def version(self) -> tuple[int, int]:
        return typing.cast(tuple[int, int], getattr(self.endpoint, "version"))

    @property
    def version_str(self) -> str:
        return ".".join(str(x) for x in self.version)

    def matches(self, scope: types.Scope) -> tuple[Match, types.Scope]:
        match, child_scope = super().matches(scope)
        if match != Match.FULL:
            return match, child_scope

        request_version: tuple[int, int] = scope.get("version", DEFAULT_VERSION)
        if request_version == self.version:
            return Match.FULL, child_scope
        return Match.NONE, {}


class VersionedAPIRouter(APIRouter):
    VENDOR_MEDIA_TYPE = ""

    def api_route(
        self,
        path: str,
        **kwargs: typing.Any,  # noqa: ANN401
    ) -> typing.Callable[[DecoratedCallable], DecoratedCallable]:
        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            if not hasattr(func, "version"):
                setattr(func, "version", DEFAULT_VERSION)
            version_str = ".".join([str(x) for x in getattr(func, "version")])

            class VersionedJSONResponse(JSONResponse):
                @ClassProperty
                def media_type(self) -> str:  # type: ignore[override]
                    """Media type for docs."""
                    return f"{VersionedAPIRouter.VENDOR_MEDIA_TYPE}; version={version_str}"

            kwargs["response_class"] = VersionedJSONResponse
            kwargs["route_class_override"] = VersionedAPIRoute
            self.add_api_route(path, func, **kwargs)
            return func

        return decorator

    @staticmethod
    def set_api_version(version: tuple[int, int]) -> typing.Callable[[DecoratedCallable], DecoratedCallable]:
        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            setattr(func, "version", version)
            return func

        return decorator
