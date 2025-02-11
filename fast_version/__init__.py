from fast_version.app import init_fastapi_versioning
from fast_version.router import VersionedAPIRouter


__all__ = [
    "VersionedAPIRouter",
    "init_fastapi_versioning",
]
