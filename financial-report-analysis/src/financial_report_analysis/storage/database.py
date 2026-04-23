from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from financial_report_analysis.storage.models import Base


def create_sqlite_engine(path: str | Path) -> Engine:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", future=True)


def initialize_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
