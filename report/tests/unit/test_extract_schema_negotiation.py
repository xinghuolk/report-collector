from src.api.routes.extract import _resolve_schema_version


def test_query_schema_has_highest_priority() -> None:
    assert _resolve_schema_version(
        "v1",
        "v2",
        "application/vnd.financial-reports.v1+json",
    ) == "v1"


def test_x_schema_version_fallback() -> None:
    assert _resolve_schema_version(None, "v1", None) == "v1"


def test_accept_header_fallback() -> None:
    assert _resolve_schema_version(
        None,
        None,
        "application/vnd.financial-reports.v2+json",
    ) == "v2"


def test_default_schema_is_v2() -> None:
    assert _resolve_schema_version(None, None, None) == "v2"
