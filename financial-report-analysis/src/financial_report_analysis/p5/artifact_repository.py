from __future__ import annotations

from dataclasses import asdict
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Protocol, cast

from financial_report_analysis.p5.models import (
    Market,
    MissingStatus,
    P5DatasetArtifact,
    P5DatasetRow,
    P5ExtractedArtifact,
    P5ManifestEntry,
    P5TurtleExport,
    ReportType,
)

_SUPPORTED_MARKETS = {"CN", "HK", "US"}
_SUPPORTED_REPORT_TYPES = {"annual"}
_SUPPORTED_MISSING_STATUSES = {
    "present",
    "absent",
    "not_surfaced",
    "out_of_scope",
    "unknown",
}
_SAFE_FILENAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class P5ArtifactRepositoryError(ValueError):
    """Raised when persisted P5 artifacts cannot be safely read or written."""


class P5ArtifactRepository(Protocol):
    def extracted_artifact_exists(self, artifact_id: str) -> bool: ...

    def save_extracted_artifact(self, artifact: P5ExtractedArtifact) -> Path | str: ...

    def load_extracted_artifact(self, artifact_id: str) -> P5ExtractedArtifact: ...

    def save_dataset_artifact(self, dataset: P5DatasetArtifact) -> Path | str: ...

    def load_dataset_artifact(self, dataset_id: str) -> P5DatasetArtifact: ...

    def save_turtle_export(self, turtle_export: P5TurtleExport) -> Path | str: ...

    def load_turtle_export(self, dataset_id: str) -> P5TurtleExport: ...

    def list_extracted_artifact_ids(
        self,
        *,
        issuer_id: str | None = None,
        fiscal_year: int | None = None,
    ) -> tuple[str, ...]: ...


class P5JsonArtifactRepository:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.extracted_dir = self.root_dir / "extracted"
        self.datasets_dir = self.root_dir / "datasets"

    def extracted_artifact_exists(self, artifact_id: str) -> bool:
        return self._extracted_path(artifact_id).exists()

    def save_extracted_artifact(self, artifact: P5ExtractedArtifact) -> Path:
        return self._write_json(
            self._extracted_path(artifact.artifact_id),
            extracted_artifact_to_payload(artifact),
        )

    def load_extracted_artifact(self, artifact_id: str) -> P5ExtractedArtifact:
        return extracted_artifact_from_payload(
            self._read_json(self._extracted_path(artifact_id))
        )

    def save_dataset_artifact(self, dataset: P5DatasetArtifact) -> Path:
        return self._write_json(
            self.dataset_artifact_path(dataset.dataset_id),
            dataset_artifact_to_payload(dataset),
        )

    def load_dataset_artifact(self, dataset_id: str) -> P5DatasetArtifact:
        return dataset_artifact_from_payload(
            self._read_json(self.dataset_artifact_path(dataset_id))
        )

    def save_turtle_export(self, turtle_export: P5TurtleExport) -> Path:
        return self._write_json(
            self.turtle_export_artifact_path(turtle_export.dataset_id),
            turtle_export_to_payload(turtle_export),
        )

    def load_turtle_export(self, dataset_id: str) -> P5TurtleExport:
        return turtle_export_from_payload(
            self._read_json(self.turtle_export_artifact_path(dataset_id))
        )

    def list_extracted_artifact_ids(
        self,
        *,
        issuer_id: str | None = None,
        fiscal_year: int | None = None,
    ) -> tuple[str, ...]:
        artifact_ids: list[str] = []
        for path in sorted(self.extracted_dir.glob("*.json")):
            artifact = self.load_extracted_artifact(path.stem)
            if issuer_id is not None and artifact.manifest_entry.issuer_id != issuer_id:
                continue
            if fiscal_year is not None and artifact.manifest_entry.fiscal_year != fiscal_year:
                continue
            artifact_ids.append(artifact.artifact_id)
        return tuple(artifact_ids)

    def extracted_artifact_path(self, artifact_id: str) -> Path:
        return self._extracted_path(artifact_id)

    def dataset_artifact_path(self, dataset_id: str) -> Path:
        return self._dataset_path(dataset_id)

    def turtle_export_artifact_path(self, dataset_id: str) -> Path:
        return self.datasets_dir / f"{self._dataset_path(dataset_id).stem}_turtle_export.json"

    def _extracted_path(self, artifact_id: str) -> Path:
        return self.extracted_dir / f"{_safe_filename(artifact_id, 'artifact_id')}.json"

    def _dataset_path(self, dataset_id: str) -> Path:
        return self.datasets_dir / f"{_safe_filename(dataset_id, 'dataset_id')}.json"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"artifact JSON root must be an object: {path}")
        return payload

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                json.dump(payload, temp_file, ensure_ascii=False, indent=2, sort_keys=True)
                temp_file.write("\n")
                temp_file.flush()
                os.fsync(temp_file.fileno())
            temp_path.replace(path)
            _fsync_directory(path.parent)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
        return path


def _entry_to_json(entry: P5ManifestEntry) -> dict[str, Any]:
    return {
        "issuer_id": entry.issuer_id,
        "market": entry.market,
        "stock_code": entry.stock_code,
        "fiscal_year": entry.fiscal_year,
        "report_type": entry.report_type,
        "pdf_path": str(entry.pdf_path),
        "source": entry.source,
        "company_name": entry.company_name,
        "report_language": entry.report_language,
    }


def _entry_from_json(payload: dict[str, Any]) -> P5ManifestEntry:
    return P5ManifestEntry(
        issuer_id=_text_from_json(payload["issuer_id"], "issuer_id"),
        market=_market_from_json(payload["market"], "market"),
        stock_code=_text_from_json(payload["stock_code"], "stock_code"),
        fiscal_year=_int_from_json(payload["fiscal_year"], "fiscal_year"),
        report_type=_report_type_from_json(payload["report_type"], "report_type"),
        pdf_path=Path(_text_from_json(payload["pdf_path"], "pdf_path")),
        source=_text_from_json(payload["source"], "source"),
        company_name=_optional_text_from_json(payload.get("company_name")),
        report_language=_optional_text_from_json(payload.get("report_language")),
    )


def extracted_artifact_to_payload(artifact: P5ExtractedArtifact) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "artifact_version": artifact.artifact_version,
        "pipeline_version": artifact.pipeline_version,
        "manifest_entry": _entry_to_json(artifact.manifest_entry),
        "source_pdf_path": str(artifact.source_pdf_path),
        "document": artifact.document,
        "document_metadata": artifact.document_metadata,
        "candidate_facts": list(artifact.candidate_facts),
        "canonical_facts": list(artifact.canonical_facts),
        "derived_facts": list(artifact.derived_facts),
        "validation_report": artifact.validation_report,
        "review_packets": list(artifact.review_packets),
        "quality_gate": artifact.quality_gate,
        "missing_status": artifact.missing_status,
        "created_at": artifact.created_at,
    }


def extracted_artifact_from_payload(payload: dict[str, Any]) -> P5ExtractedArtifact:
    return P5ExtractedArtifact(
        artifact_id=_text_from_json(payload["artifact_id"], "artifact_id"),
        artifact_version=_text_from_json(payload["artifact_version"], "artifact_version"),
        pipeline_version=_text_from_json(
            payload["pipeline_version"],
            "pipeline_version",
        ),
        manifest_entry=_entry_from_json(_object_from_json(payload["manifest_entry"])),
        source_pdf_path=Path(_text_from_json(payload["source_pdf_path"], "source_pdf_path")),
        document=_object_from_json(payload["document"]),
        document_metadata=_object_from_json(payload["document_metadata"]),
        candidate_facts=_tuple_of_objects(payload.get("candidate_facts", [])),
        canonical_facts=_tuple_of_objects(payload.get("canonical_facts", [])),
        derived_facts=_tuple_of_objects(payload.get("derived_facts", [])),
        validation_report=_object_from_json(payload["validation_report"]),
        review_packets=_tuple_of_objects(payload.get("review_packets", [])),
        quality_gate=_text_from_json(payload["quality_gate"], "quality_gate"),
        missing_status=_nested_text_mapping(payload.get("missing_status", {})),
        created_at=_text_from_json(payload["created_at"], "created_at"),
    )


def dataset_artifact_to_payload(dataset: P5DatasetArtifact) -> dict[str, Any]:
    return {
        "dataset_id": dataset.dataset_id,
        "dataset_version": dataset.dataset_version,
        "created_at": dataset.created_at,
        "issuer_count": dataset.issuer_count,
        "periods": list(dataset.periods),
        "metrics": list(dataset.metrics),
        "rows": [_row_to_json(row) for row in dataset.rows],
        "quality_summary": dataset.quality_summary,
        "source_artifacts": list(dataset.source_artifacts),
    }


def dataset_artifact_from_payload(payload: dict[str, Any]) -> P5DatasetArtifact:
    return P5DatasetArtifact(
        dataset_id=_text_from_json(payload["dataset_id"], "dataset_id"),
        dataset_version=_text_from_json(payload["dataset_version"], "dataset_version"),
        created_at=_text_from_json(payload["created_at"], "created_at"),
        issuer_count=_int_from_json(payload["issuer_count"], "issuer_count"),
        periods=tuple(
            _int_from_json(period, "periods[]")
            for period in _list_from_json(payload.get("periods", []), "periods")
        ),
        metrics=tuple(
            _text_from_json(metric, "metrics[]")
            for metric in _list_from_json(payload.get("metrics", []), "metrics")
        ),
        rows=tuple(_row_from_json(row) for row in payload.get("rows", [])),
        quality_summary=_object_from_json(payload.get("quality_summary", {})),
        source_artifacts=tuple(
            _text_from_json(item, "source_artifacts[]")
            for item in _list_from_json(
                payload.get("source_artifacts", []),
                "source_artifacts",
            )
        ),
    )


def turtle_export_to_payload(turtle_export: P5TurtleExport) -> dict[str, Any]:
    return asdict(turtle_export)


def turtle_export_from_payload(payload: dict[str, Any]) -> P5TurtleExport:
    return P5TurtleExport(
        dataset_id=_text_from_json(payload["dataset_id"], "dataset_id"),
        dataset_version=_text_from_json(payload["dataset_version"], "dataset_version"),
        created_at=_text_from_json(payload["created_at"], "created_at"),
        rows=_tuple_of_objects(payload.get("rows", [])),
        alias_map={
            _text_from_json(key, "alias_map key"): _text_from_json(value, "alias_map value")
            for key, value in _object_from_json(payload.get("alias_map", {})).items()
        },
    )


def _row_to_json(row: P5DatasetRow) -> dict[str, Any]:
    return {
        "issuer_id": row.issuer_id,
        "market": row.market,
        "stock_code": row.stock_code,
        "fiscal_year": row.fiscal_year,
        "metric_id": row.metric_id,
        "entity_scope": row.entity_scope,
        "period_scope": row.period_scope,
        "statement_type": row.statement_type,
        "value": row.value,
        "currency": row.currency,
        "unit": row.unit,
        "quality_status": row.quality_status,
        "missing_status": row.missing_status,
        "source_fact_id": row.source_fact_id,
        "source_artifact_id": row.source_artifact_id,
        "evidence_bundle_id": row.evidence_bundle_id,
    }


def _row_from_json(payload: Any) -> P5DatasetRow:
    row = _object_from_json(payload)
    return P5DatasetRow(
        issuer_id=_text_from_json(row["issuer_id"], "issuer_id"),
        market=_text_from_json(row["market"], "market"),
        stock_code=_text_from_json(row["stock_code"], "stock_code"),
        fiscal_year=_int_from_json(row["fiscal_year"], "fiscal_year"),
        metric_id=_text_from_json(row["metric_id"], "metric_id"),
        entity_scope=_text_from_json(row["entity_scope"], "entity_scope"),
        period_scope=_text_from_json(row["period_scope"], "period_scope"),
        statement_type=_text_from_json(row["statement_type"], "statement_type"),
        value=_value_from_json(row.get("value")),
        currency=_optional_text_from_json(row.get("currency")),
        unit=_optional_text_from_json(row.get("unit")),
        quality_status=_optional_text_from_json(row.get("quality_status")),
        missing_status=_missing_status_from_json(row["missing_status"]),
        source_fact_id=_optional_text_from_json(row.get("source_fact_id")),
        source_artifact_id=_text_from_json(row["source_artifact_id"], "source_artifact_id"),
        evidence_bundle_id=_optional_text_from_json(row.get("evidence_bundle_id")),
    )


def _safe_filename(value: str, field_name: str) -> str:
    if (
        not value
        or value in {".", ".."}
        or ".." in value
        or "/" in value
        or "\\" in value
        or _SAFE_FILENAME_PATTERN.fullmatch(value) is None
    ):
        raise P5ArtifactRepositoryError(f"unsafe {field_name}: {value!r}")
    return value


def _fsync_directory(path: Path) -> None:
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        try:
            os.fsync(directory_fd)
        except OSError:
            return
    finally:
        os.close(directory_fd)


def _type_error(field_name: str, expected: str, value: Any) -> P5ArtifactRepositoryError:
    return P5ArtifactRepositoryError(
        f"invalid P5 artifact JSON field {field_name}: expected {expected}, "
        f"got {type(value).__name__}",
    )


def _text_from_json(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise _type_error(field_name, "string", value)
    return value


def _int_from_json(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise _type_error(field_name, "integer", value)
    return value


def _list_from_json(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise _type_error(field_name, "list", value)
    return value


def _market_from_json(value: Any, field_name: str) -> Market:
    text = _text_from_json(value, field_name)
    if text not in _SUPPORTED_MARKETS:
        raise P5ArtifactRepositoryError(f"unsupported market in artifact JSON: {text}")
    return cast(Market, text)


def _report_type_from_json(value: Any, field_name: str) -> ReportType:
    text = _text_from_json(value, field_name)
    if text not in _SUPPORTED_REPORT_TYPES:
        raise P5ArtifactRepositoryError(f"unsupported report_type in artifact JSON: {text}")
    return cast(ReportType, text)


def _missing_status_from_json(value: Any) -> MissingStatus:
    text = _text_from_json(value, "missing_status")
    if text not in _SUPPORTED_MISSING_STATUSES:
        raise P5ArtifactRepositoryError(
            f"unsupported missing_status in artifact JSON: {text}"
        )
    return cast(MissingStatus, text)


def _optional_text_from_json(value: Any) -> str | None:
    if value is None:
        return None
    return _text_from_json(value, "optional text")


def _value_from_json(value: Any) -> int | float | None:
    if value is None or (
        isinstance(value, int | float) and not isinstance(value, bool)
    ):
        return value
    raise _type_error("value", "number or null", value)


def _object_from_json(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _type_error("object", "object", value)
    return value


def _tuple_of_objects(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        raise _type_error("list", "list", value)
    return tuple(_object_from_json(item) for item in value)


def _nested_text_mapping(value: Any) -> dict[str, dict[str, str]]:
    outer = _object_from_json(value)
    return {
        _text_from_json(key, "missing_status key"): {
            _text_from_json(inner_key, "missing_status inner key"): _text_from_json(
                inner_value,
                "missing_status inner value",
            )
            for inner_key, inner_value in _object_from_json(inner).items()
        }
        for key, inner in outer.items()
    }
