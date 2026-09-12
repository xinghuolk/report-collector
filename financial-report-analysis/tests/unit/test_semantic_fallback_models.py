from financial_report_analysis.semantic_fallback import (
    DisclosureLocatorResult,
    RowLabelFallbackRequest,
    SemanticFallbackResult,
    TableKindFallbackRequest,
    supported_disclosure_metric_outputs,
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


def test_disclosure_locator_supported_outputs_are_p2a_bounded() -> None:
    assert supported_disclosure_metric_outputs() == (
        "accounts_receiv",
        "notes_receiv",
        "oth_receiv",
        "contract_liab",
        "adv_receipts",
        "acct_payable",
        "notes_payable",
        "none",
    )


def test_disclosure_locator_result_carries_span_and_provenance() -> None:
    result = DisclosureLocatorResult(
        metric_id="acct_payable",
        matched_label="Accounts payable",
        source_text_span="Accounts payable $ 801 $ 786",
        semantic_source="llm_fallback",
        semantic_confidence=0.91,
        fallback_reason="missing_statement_row",
    )

    assert result.metric_id == "acct_payable"
    assert result.source_text_span.startswith("Accounts payable")
