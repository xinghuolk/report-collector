from __future__ import annotations

from fastapi import FastAPI

from financial_report_analysis.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Financial Report Analysis API",
        version="0.1.0",
    )
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
