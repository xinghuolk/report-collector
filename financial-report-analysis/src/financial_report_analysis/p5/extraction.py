from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.pipeline import analyze_report

_ARTIFACT_VERSION = "1.0"
_PIPELINE_VERSION = "p5-v1"
_MISSING_STATUS_KEYS = (
    "working_capital_missing_status",
    "debt_missing_status",
    "asset_missing_status",
    "cash_health_missing_status",
)
_SUPPORTED_MISSING_STATUS_VALUES = frozenset(
    {"present", "absent", "not_surfaced", "out_of_scope", "unknown"}
)


class P5ExtractionError(ValueError):
    """Raised when P5 extraction payload validation fails."""


def build_extracted_artifact(
    entry: P5ManifestEntry,
    ingestion_adapter: Any | None = None,
    analyze_report_func: Callable[[dict[str, Any], dict[str, Any]], Any] = analyze_report,
    now_func: Callable[[], str] | None = None,
) -> P5ExtractedArtifact:
    adapter = ingestion_adapter or PdfIngestionAdapter()
    extracted_payload = adapter.extract_candidate_facts(
        pdf_path=str(entry.pdf_path),
        pdf_url=None,
        market=entry.market,
        min_confidence=None,
    )
    document_metadata = _json_object(
        extracted_payload.get("document_metadata", {}),
        field_name="document_metadata",
    )
    document_ref = _build_document_ref(entry, document_metadata=document_metadata)
    pipeline_result = analyze_report_func(document_ref, extracted_payload)

    return build_extracted_artifact_from_result(
        entry=entry,
        document=document_ref,
        extracted_payload=extracted_payload,
        pipeline_result=pipeline_result,
        now_func=now_func,
    )


def build_extracted_artifact_from_result(
    *,
    entry: P5ManifestEntry,
    document: dict[str, Any],
    extracted_payload: dict[str, Any],
    pipeline_result: Any,
    now_func: Callable[[], str] | None = None,
) -> P5ExtractedArtifact:
    document_metadata = _json_object(
        extracted_payload.get("document_metadata", {}),
        field_name="document_metadata",
    )
    missing_status = _missing_status_from_metadata(document_metadata)
    document_ref = _json_object(document, field_name="document")

    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version=_ARTIFACT_VERSION,
        pipeline_version=_PIPELINE_VERSION,
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document=document_ref,
        document_metadata=document_metadata,
        candidate_facts=_json_object_tuple(extracted_payload.get("candidate_facts", [])),
        canonical_facts=_json_object_tuple(_result_value(pipeline_result, "canonical_facts", [])),
        derived_facts=_json_object_tuple(_result_value(pipeline_result, "derived_facts", [])),
        validation_report=_json_object(
            _result_value(pipeline_result, "validation_report", {}),
            field_name="validation_report",
        ),
        review_packets=_json_object_tuple(
            _result_value(pipeline_result, "review_packets", []),
        ),
        quality_gate=str(_result_value(pipeline_result, "quality_gate", "review")),
        missing_status=missing_status,
        created_at=now_func() if now_func is not None else _utc_now_iso(),
    )


def _build_document_ref(
    entry: P5ManifestEntry,
    *,
    document_metadata: dict[str, Any],
) -> dict[str, Any]:
    language = document_metadata.get("language") or entry.report_language
    return {
        "document_id": str(entry.pdf_path),
        "pdf_path": str(entry.pdf_path),
        "market": entry.market,
        "stock_code": entry.stock_code,
        "issuer_id": entry.issuer_id,
        "fiscal_year": entry.fiscal_year,
        "report_type": entry.report_type,
        "company_name": entry.company_name,
        "language": language,
        "metadata": {
            "source": entry.source,
            "artifact_id": entry.artifact_id,
            "report_language": entry.report_language,
        },
    }


def _result_value(result: Any, key: str, default: Any) -> Any:
    if isinstance(result, Mapping):
        return result.get(key, default)
    return getattr(result, key, default)


def _json_object_tuple(value: Any) -> tuple[dict[str, Any], ...]:
    json_value = _to_json_like(value)
    if json_value is None:
        return ()
    if not isinstance(json_value, list):
        raise TypeError("expected a list of objects")
    return tuple(_json_object(item, field_name="object list item") for item in json_value)


def _json_object(value: Any, *, field_name: str) -> dict[str, Any]:
    json_value = _to_json_like(value)
    if not isinstance(json_value, dict):
        raise TypeError(f"{field_name} must be an object")
    return json_value


def _missing_status_from_metadata(
    document_metadata: dict[str, Any],
) -> dict[str, dict[str, str]]:
    return {
        key: _missing_status_group(document_metadata, key)
        for key in _MISSING_STATUS_KEYS
    }


def _missing_status_group(
    document_metadata: dict[str, Any],
    key: str,
) -> dict[str, str]:
    if key not in document_metadata:
        return {}
    json_value = _to_json_like(document_metadata[key])
    if not isinstance(json_value, dict):
        raise P5ExtractionError(f"{key} must be an object of metric status values")

    result: dict[str, str] = {}
    for metric_key, status_value in json_value.items():
        if not isinstance(metric_key, str) or not metric_key:
            raise P5ExtractionError(f"{key} metric keys must be non-empty strings")
        if status_value not in _SUPPORTED_MISSING_STATUS_VALUES:
            raise P5ExtractionError(
                f"{key}.{metric_key} has unsupported missing status: {status_value!r}"
            )
        result[metric_key] = status_value
    return result


def _to_json_like(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _to_json_like(to_dict())
    if is_dataclass(value) and not isinstance(value, type):
        return _to_json_like(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _to_json_like(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_to_json_like(item) for item in value]
    object_dict = getattr(value, "__dict__", None)
    if isinstance(object_dict, dict):
        return _to_json_like(object_dict)
    return str(value)


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()
