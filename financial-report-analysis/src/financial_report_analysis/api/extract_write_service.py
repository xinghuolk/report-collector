from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from financial_report_analysis.api.runtime import ApiRuntime
from financial_report_analysis.api.schemas import AnalysisExtractRequest
from financial_report_analysis.p5.extraction import build_extracted_artifact_from_result
from financial_report_analysis.p5.models import Market, P5ManifestEntry
from financial_report_analysis.p5.review import build_extracted_review_surface


@dataclass(frozen=True, slots=True)
class AnalysisExtractStorageResult:
    persisted: bool
    artifact_id: str
    report_id: int
    document_id: str
    document_version_id: str
    extraction_run_id: str
    artifact_lookup_path: str
    report_lookup_path: str

    def to_response_dict(self) -> dict[str, object]:
        return {
            "persisted": self.persisted,
            "artifact_id": self.artifact_id,
            "report_id": self.report_id,
            "document_id": self.document_id,
            "document_version_id": self.document_version_id,
            "extraction_run_id": self.extraction_run_id,
            "artifact_lookup_path": self.artifact_lookup_path,
            "report_lookup_path": self.report_lookup_path,
        }


def persist_analysis_extract_result(
    *,
    runtime: ApiRuntime,
    request: AnalysisExtractRequest,
    document: dict[str, Any],
    extracted_payload: dict[str, Any],
    pipeline_result: Any,
    now_func: Callable[[], str] | None = None,
) -> AnalysisExtractStorageResult:
    if runtime.storage_repository is None or runtime.historical_ingestion_service is None:
        raise RuntimeError("storage repository is not configured")

    entry = _manifest_entry_from_request(request)
    artifact = build_extracted_artifact_from_result(
        entry=entry,
        document=document,
        extracted_payload=extracted_payload,
        pipeline_result=pipeline_result,
        now_func=now_func,
    )
    persistence_identity = runtime.storage_repository.save_api_extract_bundle(
        artifact=artifact,
        review_surface=build_extracted_review_surface(artifact),
        document_payload=document,
        manifest_id="api_extract",
        document_version_label="api_extract",
        report_file_payload={"source": entry.source},
        document_version_payload={"artifact_id": entry.artifact_id},
        extraction_run_payload={
            "artifact_id": artifact.artifact_id,
            "quality_gate": artifact.quality_gate,
            "canonical_fact_count": len(artifact.canonical_facts),
            "candidate_fact_count": len(artifact.candidate_facts),
        },
    )

    return AnalysisExtractStorageResult(
        persisted=True,
        artifact_id=artifact.artifact_id,
        report_id=persistence_identity.report_id,
        document_id=persistence_identity.document_id,
        document_version_id=persistence_identity.document_version_id,
        extraction_run_id=persistence_identity.extraction_run_id,
        artifact_lookup_path=f"/artifacts/{artifact.artifact_id}",
        report_lookup_path=(
            f"/reports/{entry.issuer_id}/{entry.fiscal_year}/{entry.report_type}"
        ),
    )


def _manifest_entry_from_request(request: AnalysisExtractRequest) -> P5ManifestEntry:
    if request.pdf_path is None:
        raise ValueError("persist_to_storage requires pdf_path in this slice")
    issuer_id = _required_text(request.issuer_id, field_name="issuer_id")
    market = _required_text(request.market, field_name="market")
    stock_code = _required_text(request.stock_code, field_name="stock_code")
    if request.fiscal_year is None:
        raise ValueError("persist_to_storage requires fiscal_year")
    report_type = _required_text(request.report_type, field_name="report_type")
    if report_type != "annual":
        raise ValueError("persist_to_storage currently supports annual reports only")
    if market not in {"CN", "HK", "US"}:
        raise ValueError("persist_to_storage requires market to be one of CN, HK, US")
    expected_issuer_id = f"{market}_{stock_code}"
    if issuer_id != expected_issuer_id:
        raise ValueError(
            "issuer_id must match market_stock_code: "
            f"expected {expected_issuer_id}, got {issuer_id}"
        )

    return P5ManifestEntry(
        issuer_id=issuer_id,
        market=cast(Market, market),
        stock_code=stock_code,
        fiscal_year=request.fiscal_year,
        report_type="annual",
        pdf_path=Path(request.pdf_path),
        source=request.source.strip(),
        company_name=_optional_text(request.company_name),
        report_language=_optional_text(request.report_language),
    )


def _required_text(value: str | None, *, field_name: str) -> str:
    if value is None:
        raise ValueError(f"persist_to_storage requires {field_name}")
    stripped_value = value.strip()
    if not stripped_value:
        raise ValueError(f"persist_to_storage requires {field_name}")
    return stripped_value


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped_value = value.strip()
    return stripped_value or None
