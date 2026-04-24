from __future__ import annotations

from pathlib import Path

import pytest

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


def test_persist_analysis_extract_result_rejects_mismatched_identity(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    runtime = build_api_runtime(tmp_path / "storage.db")
    request = AnalysisExtractRequest(
        pdf_path=str(pdf_path),
        market="CN",
        persist_to_storage=True,
        issuer_id="HK_601919",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
    )

    with pytest.raises(ValueError, match="issuer_id must match market_stock_code"):
        persist_analysis_extract_result(
            runtime=runtime,
            request=request,
            document={"document_id": str(pdf_path), "pdf_path": str(pdf_path)},
            extracted_payload={"document_metadata": {}, "candidate_facts": []},
            pipeline_result={
                "canonical_facts": [],
                "derived_facts": [],
                "validation_report": {"overall_status": "ok", "issues": []},
                "review_packets": [],
                "quality_gate": "pass",
            },
        )

    assert runtime.storage_repository is not None
    coverage = runtime.storage_repository.get_report_coverage(
        "HK_601919", 2025, "annual"
    )
    assert coverage.report_registered is False


def test_persist_analysis_extract_result_rolls_back_when_late_write_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import financial_report_analysis.storage.repositories as repositories

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
    )

    def fail_review_surface_payload(*args: object, **kwargs: object) -> dict[str, object]:
        raise RuntimeError("late review surface failure")

    monkeypatch.setattr(
        repositories,
        "extracted_review_surface_to_payload",
        fail_review_surface_payload,
    )

    with pytest.raises(RuntimeError, match="late review surface failure"):
        persist_analysis_extract_result(
            runtime=runtime,
            request=request,
            document={"document_id": str(pdf_path), "pdf_path": str(pdf_path)},
            extracted_payload={"document_metadata": {}, "candidate_facts": []},
            pipeline_result={
                "canonical_facts": [],
                "derived_facts": [],
                "validation_report": {"overall_status": "ok", "issues": []},
                "review_packets": [],
                "quality_gate": "pass",
            },
        )

    assert runtime.storage_repository is not None
    coverage = runtime.storage_repository.get_report_coverage(
        "CN_601919", 2025, "annual"
    )
    assert coverage.report_registered is False
    assert runtime.storage_repository.extracted_artifact_exists("CN_601919_2025") is False
