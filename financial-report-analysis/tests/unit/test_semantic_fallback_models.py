from financial_report_analysis.semantic_fallback import (
    RowLabelFallbackRequest,
    SemanticFallbackResult,
    TableKindFallbackRequest,
    supported_row_label_outputs,
    supported_table_kind_outputs,
)


def test_semantic_fallback_models_expose_expected_output_sets() -> None:
    assert supported_table_kind_outputs() == (
        "income_statement",
        "balance_sheet",
        "cash_flow_statement",
        "key_metrics",
        "unknown",
    )
    assert "gross_profit" in supported_row_label_outputs()
    assert "equity" in supported_row_label_outputs()
    assert "equity_attributable_to_owners" in supported_row_label_outputs()
    assert "investing_cash_flow" in supported_row_label_outputs()
    assert "financing_cash_flow" in supported_row_label_outputs()
    assert supported_row_label_outputs()[-1] == "none"


def test_semantic_fallback_request_and_result_shapes_are_stable() -> None:
    table_request = TableKindFallbackRequest(
        title_text="Consolidated Statement of Profit or Loss",
        local_context="ambiguous page fragment",
        deterministic_candidates=("income_statement", "key_metrics"),
        ambiguity_reason="weak_title_match",
    )
    row_request = RowLabelFallbackRequest(
        raw_label="Profit for the period",
        table_kind="income_statement",
        local_context="statement snippet",
        deterministic_candidates=("net_profit",),
        ambiguity_reason="multiple_metric_candidates",
    )
    result = SemanticFallbackResult(
        value="net_profit",
        semantic_source="llm_fallback",
        semantic_confidence=0.81,
        fallback_reason="multiple_metric_candidates",
    )

    assert table_request.ambiguity_reason == "weak_title_match"
    assert row_request.raw_label == "Profit for the period"
    assert result.semantic_source == "llm_fallback"
