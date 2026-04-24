from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from financial_report_analysis.api.app import app as module_app
from financial_report_analysis.api.app import build_uvicorn_settings
from financial_report_analysis.api.app import create_app
from financial_report_analysis.api.runtime import ApiRuntime
from financial_report_analysis.api.runtime import STORAGE_DB_PATH_ENV, build_api_runtime


def test_create_app_keeps_global_app_pattern() -> None:
    assert isinstance(module_app, FastAPI)
    assert isinstance(module_app.state.runtime, ApiRuntime)


def test_create_app_allows_runtime_override() -> None:
    runtime = ApiRuntime(
        storage_db_path=None,
        storage_engine=None,
        storage_repository=None,
        historical_ingestion_service=None,
    )

    app = create_app(runtime=runtime)

    assert app.state.runtime is runtime


def test_create_app_attaches_runtime_bundle_with_storage_path(
    tmp_path: Path,
) -> None:
    storage_db_path = tmp_path / "runtime.db"

    app = create_app(storage_db_path=storage_db_path)

    runtime = app.state.runtime
    assert runtime.storage_db_path == storage_db_path
    assert runtime.storage_engine is not None
    assert runtime.historical_ingestion_service is not None
    assert runtime.historical_ingestion_service.engine is runtime.storage_engine
    assert storage_db_path.exists()


def test_create_app_runtime_override_wins_over_storage_path(tmp_path: Path) -> None:
    explicit_runtime = build_api_runtime(tmp_path / "explicit.db")

    app = create_app(
        storage_db_path=tmp_path / "ignored.db",
        runtime=explicit_runtime,
    )

    assert app.state.runtime is explicit_runtime
    assert explicit_runtime.storage_db_path == tmp_path / "explicit.db"
    assert not (tmp_path / "ignored.db").exists()


def test_build_api_runtime_uses_env_fallback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    storage_db_path = tmp_path / "env.db"
    monkeypatch.setenv(STORAGE_DB_PATH_ENV, str(storage_db_path))

    runtime = build_api_runtime()

    assert runtime.storage_db_path == storage_db_path
    assert runtime.storage_engine is not None


def test_build_uvicorn_settings_uses_analysis_api_env(monkeypatch) -> None:
    monkeypatch.setenv("FRA_API_HOST", "127.0.0.1")
    monkeypatch.setenv("FRA_API_PORT", "8123")

    settings = build_uvicorn_settings()

    assert settings == {
        "host": "127.0.0.1",
        "port": 8123,
        "reload": False,
    }


def test_build_uvicorn_settings_defaults_to_analysis_service_port(
    monkeypatch,
) -> None:
    monkeypatch.delenv("FRA_API_HOST", raising=False)
    monkeypatch.delenv("FRA_API_PORT", raising=False)

    settings = build_uvicorn_settings()

    assert settings["host"] == "0.0.0.0"
    assert settings["port"] == 8001
