"""
Lightweight migration script for v2 extraction cache table.

Usage:
    uv run python scripts/migrate_v2_cache_table.py
    uv run python scripts/migrate_v2_cache_table.py --db-url sqlite+aiosqlite:///./downloads/reports.db
"""

from __future__ import annotations

import argparse
from typing import List

from sqlalchemy import create_engine, text

from src.config import Config


DDL_STATEMENTS: List[str] = [
    """
    CREATE TABLE IF NOT EXISTS extracted_financial_data_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_hash VARCHAR(64) NOT NULL,
        schema_version VARCHAR(20) NOT NULL DEFAULT 'v2',
        document_json TEXT,
        periods_json TEXT,
        facts_json TEXT,
        evidence_json TEXT,
        quality_json TEXT,
        compat_payload_json TEXT,
        metadata_json TEXT,
        extraction_summary TEXT,
        extracted_at DATETIME,
        extractor_version VARCHAR(20) NOT NULL,
        extraction_duration_ms INTEGER,
        fields_extracted INTEGER DEFAULT 0,
        UNIQUE(file_hash, schema_version)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_extracted_financial_data_v2_file_hash ON extracted_financial_data_v2(file_hash)",
]


def normalize_db_url(db_url: str) -> str:
    """Use sync driver for migration script."""
    if db_url.startswith("sqlite+aiosqlite://"):
        return db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return db_url


def run_migration(db_url: str) -> None:
    engine = create_engine(normalize_db_url(db_url))
    with engine.begin() as conn:
        for ddl in DDL_STATEMENTS:
            conn.execute(text(ddl))
    print("Migration completed: extracted_financial_data_v2 is ready.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create v2 extraction cache table.")
    parser.add_argument(
        "--db-url",
        default=Config.DATABASE_URL,
        help="Database URL. Default: Config.DATABASE_URL",
    )
    args = parser.parse_args()
    run_migration(args.db_url)


if __name__ == "__main__":
    main()
