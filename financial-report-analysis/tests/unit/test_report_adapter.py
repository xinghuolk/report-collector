from __future__ import annotations

from financial_report_analysis.services.validation_service import ValidationReport
from financial_report_analysis.adapters.report_adapter import ReportAdapter


def test_report_adapter_exposes_only_curated_fields() -> None:
    adapter = ReportAdapter()
    result = adapter.build_analysis_result(
        document={"document_id": "doc-1", "market": "HK"},
        pipeline_result={
            "canonical_fact_set_id": "doc-1:canonical:v1",
            "derived_fact_set_id": "doc-1:derived:v1",
            "validation_report_id": "doc-1:validation:v1",
            "quality_gate": "pass",
            "canonical_facts": [{"metric_id": "revenue", "numeric_value": 100.0}],
            "derived_facts": [],
            "validation_report": {"overall_status": "ok", "issues": []},
        },
    )

    assert set(result) == {
        "document",
        "canonical_fact_set_id",
        "derived_fact_set_id",
        "validation_report_id",
        "quality_gate",
        "key_facts",
        "ttm_facts",
        "analysis_snapshot",
        "blocked_items",
    }
    assert result["document"] == {"document_id": "doc-1", "market": "HK"}
    assert result["canonical_fact_set_id"] == "doc-1:canonical:v1"
    assert result["derived_fact_set_id"] == "doc-1:derived:v1"
    assert result["validation_report_id"] == "doc-1:validation:v1"
    assert result["quality_gate"] == "pass"
    assert "candidate_facts" not in result
    assert result["key_facts"][0]["metric_id"] == "revenue"
    assert result["analysis_snapshot"]["summary"] == ""


def test_report_adapter_curates_ttm_facts_and_blocked_items() -> None:
    adapter = ReportAdapter()
    result = adapter.build_analysis_result(
        document={"document_id": "doc-2", "market": "CN"},
        pipeline_result={
            "canonical_fact_set_id": "doc-2:canonical:v1",
            "derived_fact_set_id": "doc-2:derived:v1",
            "validation_report_id": "doc-2:validation:v1",
            "quality_gate": "review",
            "canonical_facts": [
                {
                    "metric_id": "revenue",
                    "numeric_value": 100.0,
                    "candidate_facts": [{"fact_id": "candidate-1"}],
                }
            ],
            "derived_facts": [
                {
                    "fact_id": "derived::ttm::1",
                    "derivation_type": "ttm",
                    "candidate_facts": [{"fact_id": "candidate-ttm-1"}],
                },
                {"fact_id": "derived::delta::1", "derivation_type": "delta"},
            ],
            "validation_report": {
                "overall_status": "review_required",
                "issues": ["duplicate_canonical_fact_ids"],
            },
        },
    )

    assert result["quality_gate"] == "review"
    assert result["key_facts"] == [{"metric_id": "revenue", "numeric_value": 100.0}]
    assert result["ttm_facts"] == [{"fact_id": "derived::ttm::1", "derivation_type": "ttm"}]
    assert result["blocked_items"] == [
        {"code": "duplicate_canonical_fact_ids", "status": "review_required"}
    ]
    assert result["analysis_snapshot"]["blocked_items"] == result["blocked_items"]


def test_report_adapter_caps_key_facts_and_keeps_document() -> None:
    adapter = ReportAdapter()
    pipeline_result = {
        "canonical_fact_set_id": "doc-3:canonical:v1",
        "derived_fact_set_id": "doc-3:derived:v1",
        "validation_report_id": "doc-3:validation:v1",
        "quality_gate": "pass",
        "canonical_facts": [{"metric_id": f"metric-{index}"} for index in range(12)],
        "derived_facts": [],
        "validation_report": {"overall_status": "ok", "issues": []},
    }

    result = adapter.build_analysis_result(
        document={"document_id": "doc-3", "market": "US"},
        pipeline_result=pipeline_result,
    )

    assert result["document"] == {"document_id": "doc-3", "market": "US"}
    assert len(result["key_facts"]) == 10
    assert result["key_facts"][-1]["metric_id"] == "metric-9"


def test_report_adapter_preserves_pipeline_quality_gate() -> None:
    adapter = ReportAdapter()

    result = adapter.build_analysis_result(
        document={"document_id": "doc-4", "market": "CN"},
        pipeline_result={
            "canonical_fact_set_id": "doc-4:canonical:v1",
            "derived_fact_set_id": "doc-4:derived:v1",
            "validation_report_id": "doc-4:validation:v1",
            "quality_gate": "pass",
            "canonical_facts": [],
            "derived_facts": [],
            "validation_report": ValidationReport(
                overall_status="review_required",
                canonical_fact_count=0,
                derived_fact_count=0,
                issues=("duplicate_canonical_fact_ids",),
            ),
        },
    )

    assert result["quality_gate"] == "pass"
    assert result["blocked_items"] == [
        {"code": "duplicate_canonical_fact_ids", "status": "review_required"}
    ]


def test_report_adapter_derives_quality_gate_when_pipeline_value_missing() -> None:
    adapter = ReportAdapter()

    result = adapter.build_analysis_result(
        document={"document_id": "doc-4b", "market": "CN"},
        pipeline_result={
            "canonical_fact_set_id": "doc-4b:canonical:v1",
            "derived_fact_set_id": "doc-4b:derived:v1",
            "validation_report_id": "doc-4b:validation:v1",
            "canonical_facts": [],
            "derived_facts": [],
            "validation_report": ValidationReport(
                overall_status="review_required",
                canonical_fact_count=0,
                derived_fact_count=0,
                issues=("duplicate_canonical_fact_ids",),
            ),
        },
    )

    assert result["quality_gate"] == "review"


def test_report_adapter_treats_scalar_issue_payload_as_single_blocker() -> None:
    adapter = ReportAdapter()

    result = adapter.build_analysis_result(
        document={"document_id": "doc-5", "market": "HK"},
        pipeline_result={
            "canonical_fact_set_id": "doc-5:canonical:v1",
            "derived_fact_set_id": "doc-5:derived:v1",
            "validation_report_id": "doc-5:validation:v1",
            "canonical_facts": [],
            "derived_facts": [],
            "validation_report": {
                "overall_status": "review_required",
                "issues": "missing_lineage",
            },
        },
    )

    assert result["quality_gate"] == "review"
    assert result["blocked_items"] == [
        {"code": "missing_lineage", "status": "review_required"}
    ]
