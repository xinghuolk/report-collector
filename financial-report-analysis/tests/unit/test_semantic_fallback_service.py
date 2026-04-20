import httpx

from financial_report_analysis.semantic_fallback import (
    CurrencyFallbackRequest,
    RowLabelFallbackRequest,
    SemanticFallbackResult,
    SemanticFallbackService,
    TableKindFallbackRequest,
    UnitFallbackRequest,
)


class _StubFallbackClient:
    def __init__(self) -> None:
        self.table_kind_calls = 0
        self.row_label_calls = 0
        self.currency_calls = 0
        self.unit_calls = 0

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

    def interpret_currency(self, request: CurrencyFallbackRequest) -> SemanticFallbackResult:
        self.currency_calls += 1
        return SemanticFallbackResult(
            value="HKD",
            semantic_source="llm_fallback",
            semantic_confidence=0.71,
            fallback_reason=request.ambiguity_reason,
        )

    def interpret_unit(self, request: UnitFallbackRequest) -> SemanticFallbackResult:
        self.unit_calls += 1
        return SemanticFallbackResult(
            value="million",
            semantic_source="llm_fallback",
            semantic_confidence=0.69,
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


def test_semantic_fallback_service_only_allows_supported_currency_outputs() -> None:
    service = SemanticFallbackService(client=_StubFallbackClient())

    result = service.resolve_currency(
        CurrencyFallbackRequest(
            raw_text="Currency: HKD",
            local_context="footer",
            deterministic_candidates=(),
            ambiguity_reason="ambiguous_currency_marker",
        )
    )

    assert result.semantic_source == "llm_fallback"
    assert result.value in {"CNY", "HKD", "USD", "unknown"}


def test_semantic_fallback_service_does_not_run_unit_without_ambiguity() -> None:
    client = _StubFallbackClient()
    service = SemanticFallbackService(client=client)

    result = service.resolve_unit(
        UnitFallbackRequest(
            raw_text="Unit: RMB million",
            local_context="clear unit note",
            deterministic_candidates=("million",),
            ambiguity_reason=None,
        )
    )

    assert result.semantic_source == "deterministic"
    assert result.value == "million"
    assert client.unit_calls == 0


class _TimeoutFallbackClient(_StubFallbackClient):
    def normalize_row_label(self, request: RowLabelFallbackRequest) -> SemanticFallbackResult:
        del request
        self.row_label_calls += 1
        raise httpx.ReadTimeout("timed out")


def test_semantic_fallback_service_soft_degrades_when_client_times_out() -> None:
    client = _TimeoutFallbackClient()
    service = SemanticFallbackService(client=client)

    result = service.resolve_row_label(
        RowLabelFallbackRequest(
            raw_label="利润总额",
            table_kind="income_statement",
            local_context="ambiguous row label from annual report",
            deterministic_candidates=(),
            ambiguity_reason="unknown_row_label",
        )
    )

    assert client.row_label_calls == 1
    assert result.semantic_source == "deterministic"
    assert result.value == "none"
    assert result.semantic_confidence is None
    assert result.fallback_reason is None
