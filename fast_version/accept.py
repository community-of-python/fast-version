import contextlib
import dataclasses
import re
import typing

from starlette import datastructures, types


_VERSION_RE: typing.Final = re.compile(r"^\d\.\d$")
DEFAULT_VERSION: typing.Final = (1, 0)


@dataclasses.dataclass(frozen=True, slots=True)
class Ignore:
    """Passthrough: the request selects no version; the downstream default applies."""


@dataclasses.dataclass(frozen=True, slots=True)
class ParsedVersion:
    version: tuple[int, int]


@dataclasses.dataclass(frozen=True, slots=True)
class ParseError:
    detail: str


AcceptVersion: typing.TypeAlias = Ignore | ParsedVersion | ParseError


def get_accept_header_from_scope(scope: types.Scope) -> str:
    headers = datastructures.Headers(scope=scope)
    return headers.get("Accept", "").strip().lower()


def parse_accept_version(accept_header: str, vendor_media_type: str) -> AcceptVersion:
    if not accept_header or accept_header == "*/*":
        return Ignore()

    try:
        media_type, version_str = accept_header.split(";")
    except ValueError:
        return Ignore()

    # Media types are case-insensitive (RFC 9110 8.3.1); the header side is already
    # lowercased by get_accept_header_from_scope, so lowercase the vendor to match.
    if media_type.strip() != vendor_media_type.lower():
        return Ignore()

    version_key = ""
    version = ""
    with contextlib.suppress(ValueError):
        version_key, version = version_str.strip().split("=")

    if version_key.lower().strip() != "version":
        return ParseError(detail="No version in Accept header")

    if not _VERSION_RE.match(version):
        return ParseError(detail="Version should be in <major>.<minor> format")

    major_str, minor_str = version.split(".")
    return ParsedVersion(version=(int(major_str), int(minor_str)))
