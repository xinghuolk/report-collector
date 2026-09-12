from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from financial_report_analysis.api.routes import router
from financial_report_analysis.api.runtime import ApiRuntime, build_api_runtime

API_HOST_ENV = "FRA_API_HOST"
API_PORT_ENV = "FRA_API_PORT"
DEFAULT_API_HOST = "0.0.0.0"
DEFAULT_API_PORT = 8001


def create_app(
    storage_db_path: str | Path | None = None,
    *,
    runtime: ApiRuntime | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Financial Report Analysis API",
        version="0.1.0",
    )
    app.state.runtime = runtime or build_api_runtime(storage_db_path)
    app.include_router(router)
    return app


app = create_app()


def build_uvicorn_settings() -> dict[str, Any]:
    return {
        "host": os.getenv(API_HOST_ENV, DEFAULT_API_HOST),
        "port": int(os.getenv(API_PORT_ENV, str(DEFAULT_API_PORT))),
        "reload": False,
    }


def main() -> None:
    import uvicorn

    uvicorn.run(
        "financial_report_analysis.api.app:app",
        **build_uvicorn_settings(),
    )
