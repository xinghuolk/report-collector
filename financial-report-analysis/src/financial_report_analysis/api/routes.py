from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from financial_report_analysis.adapters.report_adapter import ReportAdapter
from financial_report_analysis.api.extract_write_service import (
    persist_analysis_extract_result,
)
from financial_report_analysis.p5.artifact_repository import P5ArtifactRepositoryError
from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5DatasetRow,
    P5ExtractedArtifact,
    P5ExtractedReviewSurface,
    P5ManifestEntry,
    P5RecomputeResult,
    P5TurtleExportReviewSurface,
    P5DatasetReviewSurface,
)
from financial_report_analysis.api.runtime import get_runtime
from financial_report_analysis.ingestion.pdf_ingestion import (
    PdfIngestionAdapter,
    PdfIngestionInputError,
)
from financial_report_analysis.semantic_fallback import build_semantic_fallback_service
from financial_report_analysis.api.schemas import (
    AnalysisExtractRequest,
    AnalysisExtractResponse,
    DatasetArtifactResponse,
    DatasetAuditResponse,
    DatasetReviewSurfaceResponse,
    DatasetRowResponse,
    ExtractedArtifactResponse,
    ExtractedReviewSurfaceResponse,
    HealthResponse,
    IssuerReportsResponse,
    ManifestEntryResponse,
    RecomputeDiffSummaryResponse,
    RecomputeResultResponse,
    ReportCoverageResponse,
    SourceArtifactAuditResponse,
    TurtleExportReviewSurfaceResponse,
)
from financial_report_analysis.pipeline import analyze_report

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/issuers/{issuer_id}/reports",
    response_model=IssuerReportsResponse,
)
def get_issuer_reports(
    issuer_id: str,
    request: Request,
) -> IssuerReportsResponse:
    repository = _require_storage_repository(request)
    reports = [
        _coverage_to_response(
            repository.get_report_coverage(issuer_id, fiscal_year, "annual")
        )
        for fiscal_year in repository.list_available_fiscal_years(issuer_id)
    ]
    return IssuerReportsResponse(issuer_id=issuer_id, reports=reports)


@router.get(
    "/reports/{issuer_id}/{fiscal_year}/{report_type}",
    response_model=ReportCoverageResponse,
)
def get_report_coverage(
    issuer_id: str,
    fiscal_year: int,
    report_type: str,
    request: Request,
) -> ReportCoverageResponse:
    repository = _require_storage_repository(request)
    return _coverage_to_response(
        repository.get_report_coverage(issuer_id, fiscal_year, report_type)
    )


@router.get(
    "/artifacts/{artifact_id}",
    response_model=ExtractedArtifactResponse,
)
def get_extracted_artifact(
    artifact_id: str,
    request: Request,
) -> ExtractedArtifactResponse:
    repository = _require_storage_repository(request)
    artifact = _load_or_404(repository.load_extracted_artifact, artifact_id)
    return _extracted_artifact_to_response(artifact)


@router.get(
    "/datasets/{dataset_id}",
    response_model=DatasetArtifactResponse,
)
def get_dataset_artifact(
    dataset_id: str,
    request: Request,
) -> DatasetArtifactResponse:
    repository = _require_storage_repository(request)
    dataset = _load_or_404(repository.load_dataset_artifact, dataset_id)
    return _dataset_artifact_to_response(dataset)


@router.get(
    "/datasets/{dataset_id}/audit",
    response_model=DatasetAuditResponse,
)
def get_dataset_audit(
    dataset_id: str,
    request: Request,
) -> DatasetAuditResponse:
    repository = _require_storage_repository(request)
    audit_view = _load_or_404(repository.load_dataset_audit_view, dataset_id)
    return _dataset_audit_to_response(audit_view)


@router.get(
    "/recompute-runs/{run_id}",
    response_model=RecomputeResultResponse,
)
def get_recompute_result(
    run_id: str,
    request: Request,
) -> RecomputeResultResponse:
    repository = _require_storage_repository(request)
    result = _load_or_404(repository.load_recompute_result, run_id)
    return _recompute_result_to_response(run_id, result)


@router.post(
    "/api/v1/analysis/extract",
    response_model=AnalysisExtractResponse,
    response_model_exclude_none=True,
)
def extract_analysis(
    request: AnalysisExtractRequest,
    http_request: Request,
) -> dict[str, Any]:
    runtime = get_runtime(http_request)
    pdf_path = _normalize_optional_text(request.pdf_path)
    pdf_url = _normalize_optional_text(request.pdf_url)

    if pdf_path and pdf_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="provide only one of pdf_path or pdf_url",
        )
    if not pdf_path and not pdf_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="pdf_path or pdf_url is required",
        )

    document_id = pdf_path or pdf_url
    document = {
        "document_id": document_id,
        "pdf_path": pdf_path,
        "pdf_url": pdf_url,
        "market": request.market,
        "min_confidence": request.min_confidence,
    }
    ingestion_adapter = PdfIngestionAdapter(
        semantic_fallback_service=build_semantic_fallback_service(),
    )
    try:
        extracted_payload = ingestion_adapter.extract_candidate_facts(
            pdf_path=pdf_path,
            pdf_url=pdf_url,
            market=request.market,
            min_confidence=request.min_confidence,
        )
    except PdfIngestionInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    document["language"] = extracted_payload.get("document_metadata", {}).get("language")
    document["metadata"] = extracted_payload.get("document_metadata", {})
    pipeline_result = analyze_report(
        document_ref=document,
        extracted_payload=extracted_payload,
    )
    analysis_result = ReportAdapter().build_analysis_result(
        document=document,
        pipeline_result=pipeline_result,
    )
    if request.persist_to_storage:
        if (
            runtime.storage_repository is None
            or runtime.historical_ingestion_service is None
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="storage repository is not configured",
            )
        try:
            storage_result = persist_analysis_extract_result(
                runtime=runtime,
                request=request,
                document=document,
                extracted_payload=extracted_payload,
                pipeline_result=pipeline_result,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        analysis_result["storage"] = storage_result.to_response_dict()
    return analysis_result


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _require_storage_repository(request: Request) -> Any:
    try:
        runtime = get_runtime(request)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="storage repository is not configured",
        ) from exc

    repository = runtime.storage_repository
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="storage repository is not configured",
        )
    return repository


def _load_or_404(loader: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return loader(*args, **kwargs)
    except P5ArtifactRepositoryError as exc:
        detail = str(exc)
        if not detail.startswith("missing "):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        ) from exc


def _coverage_to_response(
    coverage: Any,
) -> ReportCoverageResponse:
    return ReportCoverageResponse(
        issuer_id=coverage.issuer_id,
        fiscal_year=coverage.fiscal_year,
        report_type=coverage.report_type,
        report_registered=coverage.report_registered,
        report_id=coverage.report_id,
        pdf_path=coverage.pdf_path,
        extracted_artifact_ids=coverage.extracted_artifact_ids,
        extracted_artifact_available=coverage.extracted_artifact_available,
    )


def _manifest_entry_to_response(entry: P5ManifestEntry) -> ManifestEntryResponse:
    return ManifestEntryResponse(
        issuer_id=entry.issuer_id,
        market=entry.market,
        stock_code=entry.stock_code,
        fiscal_year=entry.fiscal_year,
        report_type=entry.report_type,
        pdf_path=str(entry.pdf_path),
        source=entry.source,
        company_name=entry.company_name,
        report_language=entry.report_language,
    )


def _dataset_row_to_response(row: P5DatasetRow) -> DatasetRowResponse:
    return DatasetRowResponse(
        issuer_id=row.issuer_id,
        market=row.market,
        stock_code=row.stock_code,
        fiscal_year=row.fiscal_year,
        metric_id=row.metric_id,
        entity_scope=row.entity_scope,
        period_scope=row.period_scope,
        statement_type=row.statement_type,
        value=row.value,
        currency=row.currency,
        unit=row.unit,
        quality_status=row.quality_status,
        missing_status=row.missing_status,
        source_fact_id=row.source_fact_id,
        source_artifact_id=row.source_artifact_id,
        evidence_bundle_id=row.evidence_bundle_id,
    )


def _extracted_artifact_to_response(
    artifact: P5ExtractedArtifact,
) -> ExtractedArtifactResponse:
    return ExtractedArtifactResponse(
        artifact_id=artifact.artifact_id,
        artifact_version=artifact.artifact_version,
        pipeline_version=artifact.pipeline_version,
        manifest_entry=_manifest_entry_to_response(artifact.manifest_entry),
        source_pdf_path=str(artifact.source_pdf_path),
        document=artifact.document,
        document_metadata=artifact.document_metadata,
        candidate_facts=list(artifact.candidate_facts),
        canonical_facts=list(artifact.canonical_facts),
        derived_facts=list(artifact.derived_facts),
        validation_report=artifact.validation_report,
        review_packets=list(artifact.review_packets),
        quality_gate=artifact.quality_gate,
        missing_status=artifact.missing_status,
        created_at=artifact.created_at,
    )


def _dataset_artifact_to_response(
    dataset: P5DatasetArtifact,
) -> DatasetArtifactResponse:
    return DatasetArtifactResponse(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        created_at=dataset.created_at,
        issuer_count=dataset.issuer_count,
        periods=list(dataset.periods),
        metrics=list(dataset.metrics),
        rows=[_dataset_row_to_response(row) for row in dataset.rows],
        quality_summary=dataset.quality_summary,
        source_artifacts=list(dataset.source_artifacts),
    )


def _extracted_review_surface_to_response(
    surface: P5ExtractedReviewSurface,
) -> ExtractedReviewSurfaceResponse:
    return ExtractedReviewSurfaceResponse(
        artifact_id=surface.artifact_id,
        artifact_version=surface.artifact_version,
        pipeline_version=surface.pipeline_version,
        source_pdf_path=surface.source_pdf_path,
        manifest_entry_key=surface.manifest_entry_key,
        quality_gate=surface.quality_gate,
        review_issue_count=surface.review_issue_count,
        missing_status_groups=surface.missing_status_groups,
        review_required_signals=surface.review_required_signals,
        duplicate_conflict_count=surface.duplicate_conflict_count,
        scope_mismatch_count=surface.scope_mismatch_count,
    )


def _dataset_review_surface_to_response(
    surface: P5DatasetReviewSurface,
) -> DatasetReviewSurfaceResponse:
    return DatasetReviewSurfaceResponse(
        dataset_id=surface.dataset_id,
        dataset_version=surface.dataset_version,
        issuer_count=surface.issuer_count,
        period_count=surface.period_count,
        pipeline_versions=surface.pipeline_versions,
        source_artifact_ids=surface.source_artifact_ids,
        present_row_count=surface.present_row_count,
        missing_row_count=surface.missing_row_count,
        review_required_artifact_ids=surface.review_required_artifact_ids,
        duplicate_conflict_count=surface.duplicate_conflict_count,
        scope_mismatch_count=surface.scope_mismatch_count,
        unknown_count=surface.unknown_count,
    )


def _turtle_export_review_surface_to_response(
    surface: P5TurtleExportReviewSurface,
) -> TurtleExportReviewSurfaceResponse:
    return TurtleExportReviewSurfaceResponse(
        dataset_id=surface.dataset_id,
        dataset_version=surface.dataset_version,
        source_artifact_ids=surface.source_artifact_ids,
        row_count=surface.row_count,
        present_row_count=surface.present_row_count,
        missing_row_count=surface.missing_row_count,
        alias_count=surface.alias_count,
        review_required_artifact_ids=surface.review_required_artifact_ids,
        duplicate_conflict_count=surface.duplicate_conflict_count,
        scope_mismatch_count=surface.scope_mismatch_count,
    )


def _dataset_audit_to_response(audit_view: Any) -> DatasetAuditResponse:
    return DatasetAuditResponse(
        dataset_id=audit_view.dataset_id,
        source_artifact_ids=audit_view.source_artifact_ids,
        source_artifacts=[
            SourceArtifactAuditResponse(
                source_artifact_id=record.source_artifact_id,
                report_id=record.report_id,
                source_pdf_path=record.source_pdf_path,
                manifest_entry_key=record.manifest_entry_key,
                extracted_review_surface=(
                    _extracted_review_surface_to_response(record.extracted_review_surface)
                    if record.extracted_review_surface is not None
                    else None
                ),
            )
            for record in audit_view.source_artifacts
        ],
        dataset_review_surface=(
            _dataset_review_surface_to_response(audit_view.dataset_review_surface)
            if audit_view.dataset_review_surface is not None
            else None
        ),
        turtle_export_review_surface=(
            _turtle_export_review_surface_to_response(
                audit_view.turtle_export_review_surface
            )
            if audit_view.turtle_export_review_surface is not None
            else None
        ),
        latest_recompute_run_id=audit_view.latest_recompute_run_id,
        latest_recompute_reason=audit_view.latest_recompute_reason,
    )


def _recompute_result_to_response(
    run_id: str,
    result: P5RecomputeResult,
) -> RecomputeResultResponse:
    return RecomputeResultResponse(
        run_id=run_id,
        manifest_id=result.manifest_id,
        extracted_artifact_ids=result.extracted_artifact_ids,
        dataset_path=str(result.dataset_path),
        turtle_export_path=str(result.turtle_export_path),
        diff_summary=RecomputeDiffSummaryResponse(
            reason=result.diff_summary.reason,
            target_artifact_ids=result.diff_summary.target_artifact_ids,
            dataset_changed=result.diff_summary.dataset_changed,
            turtle_export_changed=result.diff_summary.turtle_export_changed,
            rebuilt_dataset=result.diff_summary.rebuilt_dataset,
            rebuilt_turtle_export=result.diff_summary.rebuilt_turtle_export,
        ),
    )
