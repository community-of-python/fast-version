import typing

import pytest

from fast_version.accept import (
    Ignore,
    ParsedVersion,
    ParseError,
    get_accept_header_from_scope,
    parse_accept_version,
)


VENDOR: typing.Final = "application/vnd.some.name+json"


@pytest.mark.parametrize(
    "header",
    [
        "",
        "*/*",
        VENDOR,  # no semicolon -> split yields one part
        f"{VENDOR}; version=1.0; charset=utf-8",  # two semicolons
        "application/vnd.wrong+json; version=1.0",  # wrong vendor
    ],
)
def test_parse_ignore(header: str) -> None:
    assert parse_accept_version(header, VENDOR) == Ignore()


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (f"{VENDOR}; version=1.0", (1, 0)),
        (f"{VENDOR}; version=2.0", (2, 0)),
    ],
)
def test_parse_version(header: str, expected: tuple[int, int]) -> None:
    assert parse_accept_version(header, VENDOR) == ParsedVersion(version=expected)


@pytest.mark.parametrize(
    "header",
    [f"{VENDOR}; vers1.1", f"{VENDOR}; vers=1.1"],
)
def test_parse_missing_version_key(header: str) -> None:
    assert parse_accept_version(header, VENDOR) == ParseError(detail="No version in Accept header")


@pytest.mark.parametrize(
    "version",
    ["", "test", "0,.1", "0,1", "0,1,1", "0-1", "0/1", "1-1"],
)
def test_parse_bad_version_format(version: str) -> None:
    result = parse_accept_version(f"{VENDOR}; version={version}", VENDOR)
    assert result == ParseError(detail="Version should be in <major>.<minor> format")


def test_get_accept_header_from_scope_normalizes() -> None:
    scope: typing.Final = {"type": "http", "headers": [(b"accept", b"  Foo/Bar  ")]}
    assert get_accept_header_from_scope(scope) == "foo/bar"


def test_get_accept_header_from_scope_missing() -> None:
    assert get_accept_header_from_scope({"type": "http", "headers": []}) == ""
