FastAPI versioning library
==
[![Test Coverage](https://codecov.io/gh/community-of-python/fast-version/branch/main/graph/badge.svg)](https://codecov.io/gh/community-of-python/fast-version)
[![MyPy Strict](https://img.shields.io/badge/mypy-strict-blue)](https://mypy.readthedocs.io/en/stable/getting_started.html#strict-mode-and-configuration)
[![Supported versions](https://img.shields.io/pypi/pyversions/fast-version.svg)](https://pypi.python.org/pypi/fast-version)
[![downloads](https://img.shields.io/pypi/dm/fast-version.svg)](https://pypistats.org/packages/fast-version)
[![GitHub stars](https://img.shields.io/github/stars/modern-python/fast-version)](https://github.com/modern-python/fast-version/stargazers)

<img src="./logo.svg" width="250" />

This package adds versioning by Accept-header into FastAPI

## Quickstart:

### Installation

```shell
$ pip install fast-version
```

### Defining app and routes
```python
import fastapi

from fast_version import VersionedAPIRouter, init_fastapi_versioning


VERSION_HEADER: str = "application/vnd.some.name+json"
ROUTER_OBJ = VersionedAPIRouter()


@ROUTER_OBJ.get("/test/")
async def test_get() -> dict:
    return {"version": (1, 0)}


@ROUTER_OBJ.get("/test/")
@ROUTER_OBJ.set_api_version((2, 0))
async def test_get_v2() -> dict:
    return {"version": (2, 0)}


app = fastapi.FastAPI()
app.include_router(ROUTER_OBJ)
init_fastapi_versioning(app=app, vendor_media_type=VERSION_HEADER)
```

### Query Examples
```bash
# call 1.0 version
curl -X 'GET' 'https://test.ru/test/' -H 'accept: application/vnd.some.name+json; version=1.0'

curl -X 'GET' 'https://test.ru/test/' -H 'accept: application/vnd.some.name+json'

curl -X 'GET' 'https://test.ru/test/'

# call 2.0 version
curl -X 'GET' 'https://test.ru/test/' -H 'accept: application/vnd.some.name+json; version=2.0'
```
