from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from financial_report_analysis.p5.models import (
    P5Manifest,
    P5ManifestEntry,
    P5ManifestValidationError,
)

_SUPPORTED_MARKETS = {"CN", "HK", "US"}
_SUPPORTED_REPORT_TYPES = {"annual"}


def load_manifest(path: str | Path, *, pdf_root: str | Path | None = None) -> P5Manifest:
    manifest_path = Path(path)
    base_dir = Path(pdf_root) if pdf_root is not None else manifest_path.parent
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise P5ManifestValidationError("manifest root must be an object")

    manifest_id = _required_text(payload, "manifest_id")
    manifest_version = _required_text(payload, "manifest_version")
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise P5ManifestValidationError("entries must be a non-empty list")

    entries = tuple(_parse_entry(entry, base_dir=base_dir) for entry in raw_entries)
    seen: set[tuple[str, int, str]] = set()
    for entry in entries:
        if entry.entry_key in seen:
            raise P5ManifestValidationError(
                f"duplicate manifest entry: {entry.entry_key}"
            )
        seen.add(entry.entry_key)

    return P5Manifest(
        manifest_id=manifest_id,
        manifest_version=manifest_version,
        entries=entries,
    )


def _parse_entry(payload: Any, *, base_dir: Path) -> P5ManifestEntry:
    if not isinstance(payload, dict):
        raise P5ManifestValidationError("manifest entry must be an object")

    market = _required_text(payload, "market").upper()
    if market not in _SUPPORTED_MARKETS:
        raise P5ManifestValidationError(f"unsupported market: {market}")

    report_type = _required_text(payload, "report_type")
    if report_type not in _SUPPORTED_REPORT_TYPES:
        raise P5ManifestValidationError(f"unsupported report_type: {report_type}")

    fiscal_year = payload.get("fiscal_year")
    if not isinstance(fiscal_year, int) or fiscal_year < 1900:
        raise P5ManifestValidationError("fiscal_year must be an integer year")

    pdf_path = Path(_required_text(payload, "pdf_path")).expanduser()
    if not pdf_path.is_absolute():
        pdf_path = base_dir / pdf_path
    if not pdf_path.exists():
        raise P5ManifestValidationError(f"pdf_path does not exist: {pdf_path}")
    pdf_path = pdf_path.resolve()

    return P5ManifestEntry(
        issuer_id=_required_text(payload, "issuer_id"),
        market=market,  # type: ignore[arg-type]
        stock_code=_required_text(payload, "stock_code"),
        fiscal_year=fiscal_year,
        report_type=report_type,  # type: ignore[arg-type]
        pdf_path=pdf_path,
        source=_required_text(payload, "source"),
        company_name=_optional_text(payload, "company_name"),
        report_language=_optional_text(payload, "report_language"),
    )


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise P5ManifestValidationError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise P5ManifestValidationError(f"{key} must be a string when provided")
    normalized = value.strip()
    return normalized or None
