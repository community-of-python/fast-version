import typing

import pytest
from starlette import status
from starlette.testclient import TestClient

from tests.conftest import DOCS_URL_PREFIX, VERSION_HEADER


pytestmark = [pytest.mark.asyncio]


async def test_get(test_client: TestClient) -> None:
    response = test_client.get("/test/", headers={"Accept": f"{VERSION_HEADER}; version=1.0"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"version": [1, 0]}
    assert response.headers["content-type"] == f"{VERSION_HEADER}; version=1.0"

    response = test_client.get("/test/", headers={"Accept": f"{VERSION_HEADER}; version=2.0"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"version": [2, 0]}
    assert response.headers["content-type"] == f"{VERSION_HEADER}; version=2.0"

    response = test_client.get("/test/", headers={"Accept": f"{VERSION_HEADER}; version=3.1"})
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response.json() == {"detail": "Method Not Allowed"}


async def test_post(test_client: TestClient) -> None:
    response = test_client.post("/test/", json={}, headers={"Accept": f"{VERSION_HEADER}; version=1.0"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"version": [1, 0]}
    assert response.headers["content-type"] == f"{VERSION_HEADER}; version=1.0"

    response = test_client.post("/test/", json={}, headers={"Accept": f"{VERSION_HEADER}; version=1.1"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"version": [1, 1]}
    assert response.headers["content-type"] == f"{VERSION_HEADER}; version=1.1"

    response = test_client.post("/test/", json={}, headers={"Accept": f"{VERSION_HEADER}; version=2.0"})
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response.json() == {"detail": "Method Not Allowed"}


async def test_simple_router(test_client: TestClient) -> None:
    response = test_client.get("/simple/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {}

    with test_client.websocket_connect("/ws/") as session:
        text = session.receive_text()
        assert text == "Hello, world!"


async def test_bad_accept_header(test_client: TestClient) -> None:
    response = test_client.get("/test/", headers={"Accept": "application/vnd.wrong+json; version=1.0"})
    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE
    assert response.json() == {"detail": "Wrong media type"}


async def test_no_version(test_client: TestClient) -> None:
    response = test_client.get("/test/", headers={"Accept": f"{VERSION_HEADER}; vers1.1"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "No version in Accept header"}

    response = test_client.get("/test/", headers={"Accept": f"{VERSION_HEADER}; vers=1.1"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": "No version in Accept header"}


@pytest.mark.parametrize("version", ["", "test", "0,.1", "0,1", "0,1,1", "0-1", "0/1", "1-1"])
async def test_invalid_version(test_client: TestClient, version: str) -> None:
    response = test_client.get("/test/", headers={"Accept": f"{VERSION_HEADER}; version={version}"})
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
