from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import Request
from sqlalchemy.engine import Engine

from financial_report_analysis.storage.database import (
    create_sqlite_engine,
    initialize_database,
)
from financial_report_analysis.storage.historical_ingestion import (
    HistoricalIngestionService,
)
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository

STORAGE_DB_PATH_ENV = "FRA_STORAGE_DB_PATH"


@dataclass(frozen=True, slots=True, init=False)
class ApiRuntime:
    storage_db_path: Path | None
    storage_engine: Engine | None
    storage_repository: SqlAlchemyP5ArtifactRepository | None
    historical_ingestion_service: HistoricalIngestionService | None

    def __init__(
        self,
        *,
        storage_db_path: Path | None,
        engine: Engine | None = None,
        storage_engine: Engine | None = None,
        storage_repository: SqlAlchemyP5ArtifactRepository | None,
        historical_ingestion_service: HistoricalIngestionService | None,
    ) -> None:
        resolved_engine = storage_engine if storage_engine is not None else engine
        object.__setattr__(self, "storage_db_path", storage_db_path)
        object.__setattr__(self, "storage_engine", resolved_engine)
        object.__setattr__(self, "storage_repository", storage_repository)
        object.__setattr__(
            self,
            "historical_ingestion_service",
            historical_ingestion_service,
        )

    @property
    def engine(self) -> Engine | None:
        return self.storage_engine


def build_api_runtime(
    storage_db_path: str | Path | None = None,
) -> ApiRuntime:
    resolved_path = _resolve_storage_db_path(storage_db_path)
    if resolved_path is None:
        return ApiRuntime(
            storage_db_path=None,
            storage_engine=None,
            storage_repository=None,
            historical_ingestion_service=None,
        )

    engine = create_sqlite_engine(resolved_path)
    initialize_database(engine)
    return ApiRuntime(
        storage_db_path=resolved_path,
        storage_engine=engine,
        storage_repository=SqlAlchemyP5ArtifactRepository(engine),
        historical_ingestion_service=HistoricalIngestionService(engine),
    )


def get_runtime(request: Request) -> ApiRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if not isinstance(runtime, ApiRuntime):
        raise RuntimeError("API runtime is not configured")
    return runtime


def _resolve_storage_db_path(storage_db_path: str | Path | None) -> Path | None:
    if storage_db_path is not None:
        return Path(storage_db_path)

    env_value = os.getenv(STORAGE_DB_PATH_ENV)
    if env_value:
        return Path(env_value)
    return None
