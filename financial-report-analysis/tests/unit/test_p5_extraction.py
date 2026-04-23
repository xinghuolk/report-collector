from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from financial_report_analysis.models.governance import ReviewPacket
from financial_report_analysis.p5.extraction import build_extracted_artifact
from financial_report_analysis.p5.models import P5ManifestEntry
from financial_report_analysis.services.validation_service import ValidationReport


class FakeIngestionAdapter:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def extract_candidate_facts(
        self,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
        market: str | None,
        min_confidence: float | None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "pdf_path": pdf_path,
                "pdf_url": pdf_url,
                "market": market,
                "min_confidence": min_confidence,
            }
        )
        return self.payload


@dataclass(frozen=True)
class FakeCanonicalFact:
    fact_id: str
    metric_id: str
    source_candidate_fact_ids: tuple[str, ...]
    quality_status: str | None = None


def _entry(tmp_path: Path) -> P5ManifestEntry:
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    return P5ManifestEntry(
        issuer_id="HK_02498",
        market="HK",
        stock_code="02498",
        fiscal_year=2022,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
        company_name="速腾聚创",
        report_language="en",
    )


def test_build_extracted_artifact_runs_ingestion_and_pipeline(
    tmp_path: Path,
) -> None:
    entry = _entry(tmp_path)
    candidate_fact = {
        "fact_id": "candidate-1",
        "metric_id": "raw_revenue",
        "table_coord": (1, 2),
    }
    ingestion = FakeIngestionAdapter(
        {
            "candidate_facts": [candidate_fact],
            "document_metadata": {
                "language": "en",
                "working_capital_missing_status": {"notes_receiv": "absent"},
                "debt_missing_status": {"short_term_borrowings": "present"},
                "asset_missing_status": {"inventory": "not_surfaced"},
                "cash_health_missing_status": {"restricted_cash": "unknown"},
            },
        }
    )
    calls: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def fake_analyze_report(
        document_ref: dict[str, Any],
        extracted_payload: dict[str, Any],
    ) -> SimpleNamespace:
        calls.append((document_ref, extracted_payload))
        return SimpleNamespace(
            quality_gate="review",
            canonical_facts=[
                FakeCanonicalFact(
                    fact_id="canonical-1",
                    metric_id="raw_revenue",
                    source_candidate_fact_ids=("candidate-1",),
                    quality_status="ok",
                )
            ],
            derived_facts=[{"fact_id": "derived-1", "metric_id": "ttm_revenue"}],
            validation_report=ValidationReport(
                overall_status="ok",
                canonical_fact_count=1,
                derived_fact_count=1,
                issues=("review_required",),
            ),
            review_packets=[
                ReviewPacket(
                    document_id="HK_02498_2022",
                    period_id="2022FY",
                    metric_id="raw_revenue",
                    entity_scope="consolidated",
                    source_kind="statement_row",
                    source_policy="supplement_only",
                    conflict_state="review_required",
                    candidate_value=100,
                    competing_candidate_values=(90,),
                    evidence_bundle_id="bundle-1",
                    resolution_reason="conflict",
                    review_reason="manual_check",
                )
            ],
        )

    artifact = build_extracted_artifact(
        entry,
        ingestion_adapter=ingestion,
        analyze_report_func=fake_analyze_report,
        now_func=lambda: "2026-04-23T12:00:00",
    )

    assert ingestion.calls == [
        {
            "pdf_path": str(entry.pdf_path),
            "pdf_url": None,
            "market": "HK",
            "min_confidence": None,
        }
    ]
    assert calls[0][0] == {
        "document_id": "HK_02498_2022",
        "pdf_path": str(entry.pdf_path),
        "market": "HK",
        "stock_code": "02498",
        "issuer_id": "HK_02498",
        "fiscal_year": 2022,
        "report_type": "annual",
        "company_name": "速腾聚创",
        "language": "en",
        "metadata": {
            "source": "report",
            "artifact_id": "HK_02498_2022",
            "report_language": "en",
        },
    }
    assert calls[0][1] is ingestion.payload
    assert artifact.artifact_id == "HK_02498_2022"
    assert artifact.artifact_version == "1.0"
    assert artifact.pipeline_version == "p5-v1"
    assert artifact.manifest_entry == entry
    assert artifact.source_pdf_path == entry.pdf_path
    assert artifact.document == calls[0][0]
    assert artifact.document_metadata == ingestion.payload["document_metadata"]
    assert artifact.candidate_facts == (
        {"fact_id": "candidate-1", "metric_id": "raw_revenue", "table_coord": [1, 2]},
    )
    assert artifact.canonical_facts == (
        {
            "fact_id": "canonical-1",
            "metric_id": "raw_revenue",
            "source_candidate_fact_ids": ["candidate-1"],
            "quality_status": "ok",
        },
    )
    assert artifact.derived_facts == (
        {"fact_id": "derived-1", "metric_id": "ttm_revenue"},
    )
    assert artifact.validation_report == {
        "overall_status": "ok",
        "canonical_fact_count": 1,
        "derived_fact_count": 1,
        "issues": ["review_required"],
    }
    assert artifact.review_packets == (
        {
            "document_id": "HK_02498_2022",
            "period_id": "2022FY",
            "metric_id": "raw_revenue",
            "entity_scope": "consolidated",
            "source_kind": "statement_row",
            "source_policy": "supplement_only",
            "conflict_state": "review_required",
            "candidate_value": 100,
            "competing_candidate_values": [90],
            "evidence_bundle_id": "bundle-1",
            "resolution_reason": "conflict",
            "review_reason": "manual_check",
        },
    )
    assert artifact.quality_gate == "review"
    assert artifact.missing_status == {
        "working_capital_missing_status": {"notes_receiv": "absent"},
        "debt_missing_status": {"short_term_borrowings": "present"},
        "asset_missing_status": {"inventory": "not_surfaced"},
        "cash_health_missing_status": {"restricted_cash": "unknown"},
    }
    assert artifact.created_at == "2026-04-23T12:00:00"


def test_build_extracted_artifact_defaults_missing_status_groups(
    tmp_path: Path,
) -> None:
    entry = _entry(tmp_path)
    ingestion = FakeIngestionAdapter({"candidate_facts": [], "document_metadata": {}})

    def fake_analyze_report(
        document_ref: dict[str, Any],
        extracted_payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "quality_gate": "review",
            "canonical_facts": [],
            "derived_facts": [],
            "validation_report": {"overall_status": "review_required"},
            "review_packets": [],
        }

    artifact = build_extracted_artifact(
        entry,
        ingestion_adapter=ingestion,
        analyze_report_func=fake_analyze_report,
        now_func=lambda: "2026-04-23T12:00:00",
    )

    assert artifact.missing_status == {
        "working_capital_missing_status": {},
        "debt_missing_status": {},
        "asset_missing_status": {},
        "cash_health_missing_status": {},
    }
