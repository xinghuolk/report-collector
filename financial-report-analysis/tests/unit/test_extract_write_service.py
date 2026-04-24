from __future__ import annotations

from pathlib import Path

from financial_report_analysis.api.extract_write_service import (
    persist_analysis_extract_result,
)
from financial_report_analysis.api.runtime import build_api_runtime
from financial_report_analysis.api.schemas import AnalysisExtractRequest


def test_persist_analysis_extract_result_writes_report_artifact_and_review_surface(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    runtime = build_api_runtime(tmp_path / "storage.db")
    request = AnalysisExtractRequest(
        pdf_path=str(pdf_path),
        market="CN",
        persist_to_storage=True,
        issuer_id="CN_601919",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        company_name="COSCO SHIPPING Holdings",
        report_language="zh",
        source="api",
    )
    document = {
        "document_id": str(pdf_path),
        "pdf_path": str(pdf_path),
        "pdf_url": None,
        "market": "CN",
        "metadata": {"language": "zh"},
    }
    extracted_payload = {
        "document_metadata": {"language": "zh"},
        "candidate_facts": [{"fact_id": "candidate-1", "metric_id": "revenue"}],
    }
    pipeline_result = {
        "canonical_facts": [{"fact_id": "canonical-1", "metric_id": "revenue"}],
        "derived_facts": [],
        "validation_report": {"overall_status": "ok", "issues": []},
        "review_packets": [],
        "quality_gate": "pass",
    }

    result = persist_analysis_extract_result(
        runtime=runtime,
        request=request,
        document=document,
        extracted_payload=extracted_payload,
        pipeline_result=pipeline_result,
        now_func=lambda: "2026-04-24T00:00:00+00:00",
    )

    assert result.persisted is True
    assert result.artifact_id == "CN_601919_2025"
    assert result.report_id is not None
    assert result.document_id
    assert result.document_version_id
    assert result.extraction_run_id
    assert result.artifact_lookup_path == "/artifacts/CN_601919_2025"
    assert result.report_lookup_path == "/reports/CN_601919/2025/annual"

    assert runtime.storage_repository is not None
    artifact = runtime.storage_repository.load_extracted_artifact("CN_601919_2025")
    surface = runtime.storage_repository.load_extracted_review_surface(
        "CN_601919_2025"
    )
    coverage = runtime.storage_repository.get_report_coverage(
        "CN_601919", 2025, "annual"
    )

    assert artifact.canonical_facts == (
        {"fact_id": "canonical-1", "metric_id": "revenue"},
    )
    assert surface.quality_gate == "pass"
    assert coverage.extracted_artifact_available is True
    assert coverage.extracted_artifact_ids == ("CN_601919_2025",)
