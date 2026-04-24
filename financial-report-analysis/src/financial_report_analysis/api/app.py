from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from financial_report_analysis.api.routes import router
from financial_report_analysis.api.runtime import ApiRuntime, build_api_runtime


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


def main() -> None:
    import uvicorn

    uvicorn.run(
        "financial_report_analysis.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
