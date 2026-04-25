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


def test_report_adapter_prioritizes_api_visible_metrics_without_mutating_canonical_order() -> None:
    adapter = ReportAdapter()
    pipeline_result = {
        "canonical_fact_set_id": "doc-3b:canonical:v1",
        "derived_fact_set_id": "doc-3b:derived:v1",
        "validation_report_id": "doc-3b:validation:v1",
        "quality_gate": "pass",
        "canonical_facts": [
            {"metric_id": f"metric-{index}", "numeric_value": float(index)}
            for index in range(9)
        ]
        + [
            {"metric_id": "n_income_attr_p", "numeric_value": 123.0},
            {"metric_id": "basic_eps", "numeric_value": 1.23, "normalized_unit": "per_share_amount"},
            {"metric_id": "metric-9", "numeric_value": 9.0},
        ],
        "derived_facts": [],
        "validation_report": {"overall_status": "ok", "issues": []},
    }

    result = adapter.build_analysis_result(
        document={"document_id": "doc-3b", "market": "HK"},
        pipeline_result=pipeline_result,
    )

    assert [fact["metric_id"] for fact in result["key_facts"][:2]] == [
        "n_income_attr_p",
        "basic_eps",
    ]
    assert len(result["key_facts"]) == 10
    assert [fact["metric_id"] for fact in pipeline_result["canonical_facts"][:3]] == [
        "metric-0",
        "metric-1",
        "metric-2",
    ]


def test_report_adapter_excludes_non_auto_analysis_facts_from_key_facts() -> None:
    adapter = ReportAdapter()
    result = adapter.build_analysis_result(
        document={"document_id": "doc-3c", "market": "HK"},
        pipeline_result={
            "canonical_fact_set_id": "doc-3c:canonical:v1",
            "derived_fact_set_id": "doc-3c:derived:v1",
            "validation_report_id": "doc-3c:validation:v1",
            "quality_gate": "pass",
            "canonical_facts": [
                {
                    "metric_id": "n_income_attr_p",
                    "numeric_value": 123.0,
                    "quality_status": "ok",
                    "validation_flags": [],
                    "extensions": {
                        "metric_governance": {"auto_analysis_allowed": False}
                    },
                }
            ],
            "derived_facts": [],
            "validation_report": {"overall_status": "ok", "issues": []},
        },
    )

    assert result["key_facts"] == []


def test_report_adapter_does_not_expose_extensions_in_ttm_facts() -> None:
    adapter = ReportAdapter()
    result = adapter.build_analysis_result(
        document={"document_id": "doc-3d", "market": "HK"},
        pipeline_result={
            "canonical_fact_set_id": "doc-3d:canonical:v1",
            "derived_fact_set_id": "doc-3d:derived:v1",
            "validation_report_id": "doc-3d:validation:v1",
            "quality_gate": "pass",
            "canonical_facts": [],
            "derived_facts": [
                {
                    "fact_id": "derived::ttm::governed",
                    "metric_id": "n_income_attr_p",
                    "derivation_type": "ttm",
                    "extensions": {
                        "metric_governance": {"auto_analysis_allowed": False}
                    },
                }
            ],
            "validation_report": {"overall_status": "ok", "issues": []},
        },
    )

    assert result["ttm_facts"]
    assert "extensions" not in result["ttm_facts"][0]


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


def test_report_adapter_exposes_p4a_review_packets_and_excludes_review_facts_from_key_facts() -> (
    None
):
    adapter = ReportAdapter()
    result = adapter.build_analysis_result(
        document={"document_id": "doc-p4a", "market": "HK"},
        pipeline_result={
            "canonical_fact_set_id": "doc-p4a:canonical:v1",
            "derived_fact_set_id": "doc-p4a:derived:v1",
            "validation_report_id": "doc-p4a:validation:v1",
            "quality_gate": "review",
            "canonical_facts": [
                {
                    "metric_id": "cash",
                    "numeric_value": 100.0,
                    "quality_status": "review",
                    "validation_flags": ["source_conflict_review_required"],
                },
                {
                    "metric_id": "revenue",
                    "numeric_value": 200.0,
                    "quality_status": "ok",
                    "validation_flags": [],
                },
            ],
            "derived_facts": [],
            "validation_report": {
                "overall_status": "review_required",
                "issues": ["source_conflict"],
            },
            "review_packets": [
                {
                    "document_id": "doc-p4a",
                    "period_id": "2025FY",
                    "metric_id": "cash",
                    "entity_scope": "consolidated",
                    "source_kind": "deterministic_note_disclosure",
                    "source_policy": "review_required",
                    "conflict_state": "source_conflict",
                    "candidate_value": 120.0,
                    "competing_candidate_values": [100.0],
                    "evidence_bundle_id": "bundle-note",
                    "resolution_reason": "source_policy_review_required",
                    "review_reason": "source_conflict",
                }
            ],
        },
    )

    assert result["quality_gate"] == "review"
    assert result["key_facts"] == [
        {
            "metric_id": "revenue",
            "numeric_value": 200.0,
            "quality_status": "ok",
            "validation_flags": [],
        }
    ]
    assert result["analysis_snapshot"]["review_packets"][0]["metric_id"] == "cash"
