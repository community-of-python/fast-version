import typing

import fastapi
import pydantic
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

from fast_version import VersionedAPIRouter, init_fastapi_versioning


DOCS_URL_PREFIX: typing.Final = "/api/doc/"
VERSION_HEADER: typing.Final = "application/vnd.some.name+json"
VERSIONED_ROUTER_OBJ: typing.Final = VersionedAPIRouter()
ROUTER_OBJ: typing.Final = fastapi.APIRouter()


class Body(pydantic.BaseModel):
    field1: str | None = None
    field2: int | None = None


class Body2(Body):
    field3: bool = True


@ROUTER_OBJ.websocket("/ws/")
async def websocket_endpoint(session: WebSocket) -> None:
    await session.accept()
    await session.send_text("Hello, world!")
    await session.close()


@ROUTER_OBJ.get("/simple/")
async def route_get_simple() -> dict[str, typing.Any]:
    return {}


@VERSIONED_ROUTER_OBJ.get("/test/")
async def route_get() -> dict[str, typing.Any]:
    return {"version": (1, 0)}


@VERSIONED_ROUTER_OBJ.get("/test/")
@VERSIONED_ROUTER_OBJ.set_api_version((2, 0))
async def route_get_v2() -> dict[str, typing.Any]:
    return {"version": (2, 0)}


@VERSIONED_ROUTER_OBJ.post("/test/")
async def route_post(_: Body) -> dict[str, typing.Any]:
    return {"version": (1, 0)}


@VERSIONED_ROUTER_OBJ.post("/test/")
@VERSIONED_ROUTER_OBJ.set_api_version((1, 1))
async def route_post_v1_1(_: Body2) -> dict[str, typing.Any]:
    return {"version": (1, 1)}


@pytest.fixture
def test_client() -> TestClient:
    app: typing.Final = fastapi.FastAPI(docs_url=DOCS_URL_PREFIX)
    init_fastapi_versioning(app=app, vendor_media_type=VERSION_HEADER)
    app.include_router(ROUTER_OBJ)
    app.include_router(VERSIONED_ROUTER_OBJ)

    return TestClient(app=app)
