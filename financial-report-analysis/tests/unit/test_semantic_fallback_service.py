import httpx
from concurrent.futures import ThreadPoolExecutor
import threading
import time

from financial_report_analysis.semantic_fallback import (
    CurrencyFallbackRequest,
    DisclosureLocatorRequest,
    DisclosureLocatorResult,
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


class _DisclosureLocatorClient(_StubFallbackClient):
    def __init__(self) -> None:
        super().__init__()
        self.disclosure_locator_calls = 0

    def locate_disclosure_metric(
        self, request: DisclosureLocatorRequest
    ) -> DisclosureLocatorResult:
        self.disclosure_locator_calls += 1
        return DisclosureLocatorResult(
            metric_id="acct_payable",
            matched_label="Accounts payable",
            source_text_span="Accounts payable $ 801 $ 786",
            semantic_source="llm_fallback",
            semantic_confidence=0.9,
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


def test_semantic_fallback_service_locates_disclosure_metric_when_gated() -> None:
    client = _DisclosureLocatorClient()
    service = SemanticFallbackService(client=client)

    result = service.locate_disclosure_metric(
        DisclosureLocatorRequest(
            target_metric_ids=("acct_payable", "contract_liab"),
            local_context="Accounts payable $ 801 $ 786",
            deterministic_candidates=(),
            ambiguity_reason="missing_statement_row",
        )
    )

    assert client.disclosure_locator_calls == 1
    assert result.metric_id == "acct_payable"
    assert result.semantic_source == "llm_fallback"
    assert result.source_text_span == "Accounts payable $ 801 $ 786"


def test_semantic_fallback_service_does_not_locate_disclosure_without_gate() -> None:
    client = _DisclosureLocatorClient()
    service = SemanticFallbackService(client=client)

    result = service.locate_disclosure_metric(
        DisclosureLocatorRequest(
            target_metric_ids=("acct_payable",),
            local_context="Accounts payable $ 801 $ 786",
            deterministic_candidates=(),
            ambiguity_reason=None,
        )
    )

    assert client.disclosure_locator_calls == 0
    assert result.semantic_source == "deterministic"
    assert result.metric_id == "none"
    assert result.semantic_confidence is None
    assert result.fallback_reason is None
    assert result.matched_label == ""
    assert result.source_text_span == ""


def test_semantic_fallback_service_bounds_disclosure_metric_to_requested_subset() -> None:
    client = _DisclosureLocatorClient()
    service = SemanticFallbackService(client=client)

    result = service.locate_disclosure_metric(
        DisclosureLocatorRequest(
            target_metric_ids=("contract_liab",),
            local_context="Accounts payable $ 801 $ 786",
            deterministic_candidates=(),
            ambiguity_reason="missing_statement_row",
        )
    )

    assert client.disclosure_locator_calls == 1
    assert result.metric_id == "none"
    assert result.matched_label == ""
    assert result.source_text_span == ""


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


class _ConcurrentProbeFallbackClient(_StubFallbackClient):
    def __init__(self) -> None:
        super().__init__()
        self._active = 0
        self.max_active = 0
        self._lock = threading.Lock()

    def normalize_row_label(
        self, request: RowLabelFallbackRequest
    ) -> SemanticFallbackResult:
        with self._lock:
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        try:
            time.sleep(0.03)
            return super().normalize_row_label(request)
        finally:
            with self._lock:
                self._active -= 1


def test_semantic_fallback_service_limits_concurrent_client_calls() -> None:
    client = _ConcurrentProbeFallbackClient()
    service = SemanticFallbackService(client=client, max_concurrency=2)
    request = RowLabelFallbackRequest(
        raw_label="Business revenue",
        table_kind="income_statement",
        local_context="Consolidated statement\nBusiness revenue",
        deterministic_candidates=(),
        ambiguity_reason="unknown_row_label",
    )

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(service.resolve_row_label, [request] * 6))

    assert client.max_active <= 2
    assert client.row_label_calls == 6
    assert {result.semantic_source for result in results} == {"llm_fallback"}
