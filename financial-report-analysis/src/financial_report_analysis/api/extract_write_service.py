from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from financial_report_analysis.api.runtime import ApiRuntime
from financial_report_analysis.api.schemas import AnalysisExtractRequest
from financial_report_analysis.p5.extraction import build_extracted_artifact_from_result
from financial_report_analysis.p5.models import P5ManifestEntry
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
    registration = runtime.historical_ingestion_service.register_report(
        entry,
        manifest_id="api_extract",
    )
    document_identity = runtime.storage_repository.ensure_document_version(
        report_id=registration.report_id,
        file_path=str(entry.pdf_path),
        version_label="api_extract",
        report_file_payload={"source": entry.source},
        document_payload=document,
        document_version_payload={"artifact_id": entry.artifact_id},
    )
    artifact = build_extracted_artifact_from_result(
        entry=entry,
        document=document,
        extracted_payload=extracted_payload,
        pipeline_result=pipeline_result,
        now_func=now_func,
    )
    extraction_run = runtime.storage_repository.save_extraction_run(
        document_version_id=document_identity.document_version_id,
        pipeline_version=artifact.pipeline_version,
        status=artifact.quality_gate,
        payload={
            "artifact_id": artifact.artifact_id,
            "quality_gate": artifact.quality_gate,
            "canonical_fact_count": len(artifact.canonical_facts),
            "candidate_fact_count": len(artifact.candidate_facts),
        },
    )
    runtime.storage_repository.save_extracted_artifact(artifact)
    runtime.storage_repository.save_extracted_review_surface(
        build_extracted_review_surface(artifact)
    )

    return AnalysisExtractStorageResult(
        persisted=True,
        artifact_id=artifact.artifact_id,
        report_id=registration.report_id,
        document_id=document_identity.document_id,
        document_version_id=document_identity.document_version_id,
        extraction_run_id=extraction_run.extraction_run_id,
        artifact_lookup_path=f"/artifacts/{artifact.artifact_id}",
        report_lookup_path=(
            f"/reports/{entry.issuer_id}/{entry.fiscal_year}/{entry.report_type}"
        ),
    )


def _manifest_entry_from_request(request: AnalysisExtractRequest) -> P5ManifestEntry:
    if request.pdf_path is None:
        raise ValueError("persist_to_storage requires pdf_path in this slice")
    if request.issuer_id is None:
        raise ValueError("persist_to_storage requires issuer_id")
    if request.stock_code is None:
        raise ValueError("persist_to_storage requires stock_code")
    if request.fiscal_year is None:
        raise ValueError("persist_to_storage requires fiscal_year")
    if request.report_type != "annual":
        raise ValueError("persist_to_storage currently supports annual reports only")
    if request.market not in {"CN", "HK", "US"}:
        raise ValueError("persist_to_storage requires market to be one of CN, HK, US")

    return P5ManifestEntry(
        issuer_id=request.issuer_id,
        market=request.market,
        stock_code=request.stock_code,
        fiscal_year=request.fiscal_year,
        report_type="annual",
        pdf_path=Path(request.pdf_path),
        source=request.source,
        company_name=request.company_name,
        report_language=request.report_language,
    )
