import typing

import fastapi
import pydantic
import pytest
from starlette import status
from starlette.testclient import TestClient

from fast_version import init_fastapi_versioning
from fast_version.app import _iter_openapi_routes
from fast_version.router import VersionedAPIRoute, VersionedAPIRouter
from tests.conftest import DOCS_URL_PREFIX, VERSION_HEADER, VERSIONED_ROUTER_OBJ


pytestmark = [pytest.mark.asyncio]


async def test_get(test_client: TestClient) -> None:
    response = test_client.get(
        "/test/",
        headers={"Accept": f"{VERSION_HEADER}; version=1.0"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"version": [1, 0]}
    assert response.headers["content-type"] == f"{VERSION_HEADER}; version=1.0"

    response = test_client.get(
        "/test/",
        headers={"Accept": f"{VERSION_HEADER}; version=2.0"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"version": [2, 0]}
    assert response.headers["content-type"] == f"{VERSION_HEADER}; version=2.0"

    response = test_client.get(
        "/test/",
        headers={"Accept": f"{VERSION_HEADER}; version=3.1"},
    )
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response.json() == {"detail": "Method Not Allowed"}


async def test_post(test_client: TestClient) -> None:
    response = test_client.post(
        "/test/",
        json={},
        headers={"Accept": f"{VERSION_HEADER}; version=1.0"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"version": [1, 0]}
    assert response.headers["content-type"] == f"{VERSION_HEADER}; version=1.0"

    response = test_client.post(
        "/test/",
        json={},
        headers={"Accept": f"{VERSION_HEADER}; version=1.1"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"version": [1, 1]}
    assert response.headers["content-type"] == f"{VERSION_HEADER}; version=1.1"

    response = test_client.post(
        "/test/",
        json={},
        headers={"Accept": f"{VERSION_HEADER}; version=2.0"},
    )
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response.json() == {"detail": "Method Not Allowed"}


async def test_simple_router(test_client: TestClient) -> None:
    response = test_client.get("/simple/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {}

    with test_client.websocket_connect("/ws/") as session:
        text = session.receive_text()
        assert text == "Hello, world!"


async def test_bad_accept_header_default_response(test_client: TestClient) -> None:
    response = test_client.get(
        "/test/",
        headers={"Accept": "application/vnd.wrong+json; version=1.0"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == f"{VERSION_HEADER}; version=1.0"


async def test_no_version(test_client: TestClient) -> None:
    response = test_client.get(
        "/test/",
        headers={"Accept": f"{VERSION_HEADER}; vers1.1"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "No version in Accept header"}

    response = test_client.get(
        "/test/",
        headers={"Accept": f"{VERSION_HEADER}; vers=1.1"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "No version in Accept header"}


@pytest.mark.parametrize(
    "version",
    ["", "test", "0,.1", "0,1", "0,1,1", "0-1", "0/1", "1-1"],
)
async def test_invalid_version(test_client: TestClient, version: str) -> None:
    response = test_client.get(
        "/test/",
        headers={"Accept": f"{VERSION_HEADER}; version={version}"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "Version should be in <major>.<minor> format"}


async def test_auto_version_when_no_version_provided(test_client: TestClient) -> None:
    response = test_client.get("/test/", headers={"Accept": f"{VERSION_HEADER}"})
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == f"{VERSION_HEADER}; version=1.0"

    response = test_client.get("/test/", headers={"Accept": "application/json"})
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == f"{VERSION_HEADER}; version=1.0"


async def test_openapi_docs(test_client: TestClient) -> None:
    response = test_client.get(DOCS_URL_PREFIX)
    assert response.status_code == status.HTTP_200_OK


async def test_openapi_schema(test_client: TestClient) -> None:
    amount_of_versions: typing.Final = 2

    response = test_client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    paths: dict[str, typing.Any] = response.json()["paths"]
    assert len(paths) == amount_of_versions
    assert set(paths["/test/"].keys()) == {"get", "post"}
    assert len(paths["/test/"]["get"]["responses"]["200"]["content"]) == amount_of_versions
    assert len(paths["/test/"]["post"]["responses"]["200"]["content"]) == amount_of_versions
    assert len(paths["/test/"]["post"]["requestBody"]["content"]) == amount_of_versions

    response = test_client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK


async def test_iter_openapi_routes_finds_prefixed_versioned_paths() -> None:
    app = fastapi.FastAPI()
    init_fastapi_versioning(app=app, vendor_media_type=VERSION_HEADER)
    app.include_router(VERSIONED_ROUTER_OBJ, prefix="/api")

    routes = _iter_openapi_routes(app)

    versioned_paths = {route.path_format for route in routes if isinstance(route, VersionedAPIRoute)}
    assert versioned_paths == {"/api/test/:1.0", "/api/test/:2.0", "/api/test/:1.1"}


async def test_openapi_schema_with_prefix() -> None:
    amount_of_versions: typing.Final = 2

    app = fastapi.FastAPI()
    init_fastapi_versioning(app=app, vendor_media_type=VERSION_HEADER)
    app.include_router(VERSIONED_ROUTER_OBJ, prefix="/api")
    client = TestClient(app=app)

    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    paths: dict[str, typing.Any] = response.json()["paths"]
    assert "/api/test/" in paths
    assert len(paths["/api/test/"]["get"]["responses"]["200"]["content"]) == amount_of_versions
    assert len(paths["/api/test/"]["post"]["responses"]["200"]["content"]) == amount_of_versions
    assert len(paths["/api/test/"]["post"]["requestBody"]["content"]) == amount_of_versions


async def test_openapi_schema_distinct_models_with_shared_name_across_versions() -> None:
    # Two different models sharing a class name (as if defined in separate v1/v2 modules).
    # A single get_openapi call must disambiguate them; a per-version merge would collapse
    # both request bodies onto one component schema and silently corrupt v1.0.
    item_v1 = pydantic.create_model("Item", name=(str, ...))
    item_v2 = pydantic.create_model("Item", name=(str, ...), price=(float, ...))
    router = VersionedAPIRouter()

    @router.post("/thing/")
    async def _create(_: item_v1) -> dict[str, typing.Any]:  # type: ignore[valid-type]
        return {}

    @router.post("/thing/")
    @router.set_api_version((2, 0))
    async def _create_v2(_: item_v2) -> dict[str, typing.Any]:  # type: ignore[valid-type]
        return {}

    app = fastapi.FastAPI()
    init_fastapi_versioning(app=app, vendor_media_type=VERSION_HEADER)
    app.include_router(router)
    client = TestClient(app=app)

    schema = client.get("/openapi.json").json()
    content = schema["paths"]["/thing/"]["post"]["requestBody"]["content"]
    v1_ref = content[f"{VERSION_HEADER}; version=1.0"]["schema"]["$ref"]
    v2_ref = content[f"{VERSION_HEADER}; version=2.0"]["schema"]["$ref"]
    assert v1_ref != v2_ref

    schemas = schema["components"]["schemas"]
    assert set(schemas[v1_ref.rsplit("/", 1)[-1]]["properties"]) == {"name"}
    assert set(schemas[v2_ref.rsplit("/", 1)[-1]]["properties"]) == {"name", "price"}
