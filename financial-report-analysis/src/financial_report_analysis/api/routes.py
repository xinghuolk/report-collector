from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from financial_report_analysis.adapters.report_adapter import ReportAdapter
from financial_report_analysis.api.schemas import (
    AnalysisExtractRequest,
    AnalysisExtractResponse,
    HealthResponse,
)
from financial_report_analysis.pipeline import analyze_report

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post(
    "/api/v1/analysis/extract",
    response_model=AnalysisExtractResponse,
)
def extract_analysis(request: AnalysisExtractRequest) -> dict[str, Any]:
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
    pipeline_result = analyze_report(
        document_ref={"document_id": document_id},
        extracted_payload={"candidate_facts": []},
    )
    return ReportAdapter().build_analysis_result(
        document=document,
        pipeline_result=pipeline_result,
    )


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
