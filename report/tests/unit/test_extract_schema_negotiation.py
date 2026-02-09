from starlette.requests import Request

from src.api.routes.extract import _resolve_schema_version


def _build_request(headers: dict[str, str]) -> Request:
    raw_headers = [(k.lower().encode("utf-8"), v.encode("utf-8")) for k, v in headers.items()]
    scope = {"type": "http", "method": "POST", "path": "/api/v1/extract/content", "headers": raw_headers}
    return Request(scope)


def test_query_schema_has_highest_priority() -> None:
    request = _build_request(
        {
            "accept": "application/vnd.financial-reports.v1+json",
            "x-schema-version": "v2",
        }
    )
    assert _resolve_schema_version(request, "v1") == "v1"


def test_x_schema_version_fallback() -> None:
    request = _build_request({"x-schema-version": "v1"})
    assert _resolve_schema_version(request, None) == "v1"


def test_accept_header_fallback() -> None:
    request = _build_request({"accept": "application/vnd.financial-reports.v2+json"})
    assert _resolve_schema_version(request, None) == "v2"


def test_default_schema_is_v2() -> None:
    request = _build_request({})
    assert _resolve_schema_version(request, None) == "v2"
