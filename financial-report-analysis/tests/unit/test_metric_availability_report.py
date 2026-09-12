from __future__ import annotations

from financial_report_analysis.p5.metric_availability_report import (
    build_metric_availability_report,
    render_metric_availability_markdown,
)


def test_metric_availability_report_marks_present_missing_and_fallback_recovery() -> None:
    payload = {
        "candidate_facts": [
            {
                "fact_id": "fact-revenue",
                "metric_id": "revenue",
                "numeric_value": 100.0,
                "currency": "USD",
                "raw_unit": "US$ millions",
                "extraction_method": "table_semantics",
                "extensions": {"semantic_source": "deterministic"},
            },
            {
                "fact_id": "fact-ar",
                "metric_id": "accounts_receiv",
                "numeric_value": 95.0,
                "currency": "USD",
                "raw_unit": "US$ millions",
                "extraction_method": "table_semantics",
                "extensions": {"semantic_source": "llm_fallback"},
            },
        ],
        "document_metadata": {
            "semantic_fallback_enabled": True,
            "semantic_fallback_call_counts": {
                "table_kind": 1,
                "row_label": 2,
                "currency": 0,
                "unit": 0,
            },
            "debt_missing_status": {"st_borr": "out_of_scope"},
            "cash_health_missing_status": {"restricted_cash": "not_surfaced"},
        },
    }

    report = build_metric_availability_report(
        payload=payload,
        expected_metric_ids=(
            "revenue",
            "accounts_receiv",
            "restricted_cash",
            "st_borr",
            "cash",
        ),
        metric_profile="turtle_investment",
        pdf_path="/reports/09987.pdf",
        market="HK",
    )

    metrics = {metric.metric_id: metric for metric in report.metrics}
    assert metrics["revenue"].status == "present"
    assert metrics["revenue"].recovered_by_fallback is False
    assert metrics["accounts_receiv"].status == "present"
    assert metrics["accounts_receiv"].recovered_by_fallback is True
    assert metrics["restricted_cash"].status == "not_surfaced"
    assert metrics["st_borr"].status == "out_of_scope"
    assert metrics["cash"].status == "absent"
    assert report.summary == {
        "present": 2,
        "absent": 1,
        "not_surfaced": 1,
        "out_of_scope": 1,
    }


def test_metric_availability_report_prefers_deterministic_candidate() -> None:
    payload = {
        "candidate_facts": [
            {
                "fact_id": "fact-revenue-fallback",
                "metric_id": "revenue",
                "numeric_value": 101.0,
                "currency": "HKD",
                "raw_unit": "HK$ million",
                "extraction_method": "table_semantics",
                "confidence": 0.99,
                "extensions": {"semantic_source": "llm_fallback"},
            },
            {
                "fact_id": "fact-revenue-deterministic",
                "metric_id": "revenue",
                "numeric_value": 100.0,
                "currency": "HKD",
                "raw_unit": "HK$ million",
                "extraction_method": "table_semantics",
                "confidence": 0.90,
                "extensions": {"semantic_source": "deterministic"},
            },
        ],
        "document_metadata": {},
    }

    report = build_metric_availability_report(
        payload=payload,
        expected_metric_ids=("revenue",),
        metric_profile="turtle_investment",
        pdf_path="/reports/00001.pdf",
        market="HK",
    )

    metric = report.metrics[0]
    assert metric.fact_id == "fact-revenue-deterministic"
    assert metric.value == 100.0
    assert metric.semantic_source == "deterministic"
    assert metric.recovered_by_fallback is False


def test_metric_availability_report_prefers_latest_period_candidate() -> None:
    payload = {
        "candidate_facts": [
            {
                "fact_id": "fact-revenue-2021",
                "metric_id": "revenue",
                "numeric_value": 62094.0,
                "period_id": "2021FY",
                "comparison_axis": "current",
                "confidence": 0.90,
                "extensions": {"semantic_source": "deterministic"},
            },
            {
                "fact_id": "fact-revenue-2025",
                "metric_id": "revenue",
                "numeric_value": 57935.0,
                "period_id": "2025FY",
                "comparison_axis": "current",
                "confidence": 0.90,
                "extensions": {"semantic_source": "deterministic"},
            },
        ],
        "document_metadata": {},
    }

    report = build_metric_availability_report(
        payload=payload,
        expected_metric_ids=("revenue",),
        metric_profile="turtle_investment",
        pdf_path="/reports/01113.pdf",
        market="HK",
    )

    assert report.metrics[0].fact_id == "fact-revenue-2025"
    assert report.metrics[0].value == 57935.0


def test_metric_availability_markdown_includes_fallback_context() -> None:
    report = build_metric_availability_report(
        payload={
            "candidate_facts": [],
            "document_metadata": {
                "semantic_fallback_enabled": False,
                "semantic_fallback_call_counts": {
                    "table_kind": 0,
                    "row_label": 0,
                    "currency": 0,
                    "unit": 0,
                },
            },
        },
        expected_metric_ids=("revenue",),
        metric_profile="turtle_investment",
        pdf_path="/reports/09987.pdf",
        market="HK",
    )

    markdown = render_metric_availability_markdown(report)

    assert "semantic_fallback_enabled: false" in markdown
    assert "semantic_fallback_call_counts: table_kind=0, row_label=0, currency=0, unit=0" in markdown
    assert "| revenue | absent |" in markdown
