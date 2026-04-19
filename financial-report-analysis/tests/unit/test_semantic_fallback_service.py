from financial_report_analysis.semantic_fallback import (
    RowLabelFallbackRequest,
    SemanticFallbackResult,
    SemanticFallbackService,
    TableKindFallbackRequest,
)


class _StubFallbackClient:
    def __init__(self) -> None:
        self.table_kind_calls = 0
        self.row_label_calls = 0

    def classify_table_kind(self, request: TableKindFallbackRequest) -> SemanticFallbackResult:
        self.table_kind_calls += 1
        return SemanticFallbackResult(
            value="balance_sheet",
            semantic_source="llm_fallback",
            semantic_confidence=0.8,
            fallback_reason=request.ambiguity_reason,
        )

    def normalize_row_label(self, request: RowLabelFallbackRequest) -> SemanticFallbackResult:
        self.row_label_calls += 1
        return SemanticFallbackResult(
            value="net_profit",
            semantic_source="llm_fallback",
            semantic_confidence=0.77,
            fallback_reason=request.ambiguity_reason,
        )


def test_semantic_fallback_service_only_allows_supported_table_kind_outputs() -> None:
    service = SemanticFallbackService(client=_StubFallbackClient())

    result = service.resolve_table_kind(
        TableKindFallbackRequest(
            title_text="Statement of Financial Position",
            local_context="ambiguous page fragment",
            deterministic_candidates=("unknown",),
            ambiguity_reason="weak_title_match",
        )
    )

    assert result.semantic_source == "llm_fallback"
    assert result.value in {
        "income_statement",
        "balance_sheet",
        "cash_flow_statement",
        "key_metrics",
        "unknown",
    }


def test_semantic_fallback_service_does_not_run_without_ambiguity() -> None:
    client = _StubFallbackClient()
    service = SemanticFallbackService(client=client)

    result = service.resolve_row_label(
        RowLabelFallbackRequest(
            raw_label="Revenue",
            table_kind="income_statement",
            local_context="clear row label",
            deterministic_candidates=("revenue",),
            ambiguity_reason=None,
        )
    )

    assert result.semantic_source == "deterministic"
    assert result.value == "revenue"
    assert client.row_label_calls == 0
