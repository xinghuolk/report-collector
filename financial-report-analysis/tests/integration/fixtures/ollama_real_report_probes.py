from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OllamaRowLabelProbeCase:
    market: str
    report_family: str
    table_kind: str
    title_text: str
    raw_label: str
    local_context: str
    expected_value: str
    expectation_type: str


REAL_REPORT_ROW_LABEL_PROBE_CASES: tuple[OllamaRowLabelProbeCase, ...] = (
    OllamaRowLabelProbeCase(
        market="HK",
        report_family="annual",
        table_kind="income_statement",
        title_text="Consolidated Statement of Profit or Loss",
        raw_label="Business revenue",
        local_context="Consolidated Statement of Profit or Loss\nBusiness revenue",
        expected_value="revenue",
        expectation_type="positive",
    ),
    OllamaRowLabelProbeCase(
        market="HK",
        report_family="annual",
        table_kind="income_statement",
        title_text="Consolidated Statement of Profit or Loss",
        raw_label="Operating income",
        local_context="Consolidated Statement of Profit or Loss\nOperating income",
        expected_value="operating_profit",
        expectation_type="positive",
    ),
    OllamaRowLabelProbeCase(
        market="HK",
        report_family="annual",
        table_kind="income_statement",
        title_text="Consolidated Statement of Profit or Loss",
        raw_label="Profit attributable to owners",
        local_context="Consolidated Statement of Profit or Loss\nProfit attributable to owners",
        expected_value="net_profit",
        expectation_type="positive",
    ),
    OllamaRowLabelProbeCase(
        market="HK",
        report_family="annual",
        table_kind="balance_sheet",
        title_text="Consolidated Statement of Financial Position",
        raw_label="Cash and cash equivalents",
        local_context="Consolidated Statement of Financial Position\nCash and cash equivalents",
        expected_value="cash",
        expectation_type="positive",
    ),
    OllamaRowLabelProbeCase(
        market="HK",
        report_family="annual",
        table_kind="balance_sheet",
        title_text="Consolidated Statement of Financial Position",
        raw_label="Total assets",
        local_context="Consolidated Statement of Financial Position\nTotal assets",
        expected_value="total_assets",
        expectation_type="positive",
    ),
    OllamaRowLabelProbeCase(
        market="HK",
        report_family="annual",
        table_kind="balance_sheet",
        title_text="Consolidated Statement of Financial Position",
        raw_label="Total liabilities",
        local_context="Consolidated Statement of Financial Position\nTotal liabilities",
        expected_value="total_liabilities",
        expectation_type="positive",
    ),
    OllamaRowLabelProbeCase(
        market="CN",
        report_family="annual",
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        raw_label="Revenue growth",
        local_context="Consolidated Income Statement\nRevenue growth",
        expected_value="none",
        expectation_type="negative",
    ),
    OllamaRowLabelProbeCase(
        market="HK",
        report_family="annual",
        table_kind="balance_sheet",
        title_text="Consolidated Statement of Financial Position",
        raw_label="Deferred revenue",
        local_context="Consolidated Statement of Financial Position\nDeferred revenue",
        expected_value="none",
        expectation_type="negative",
    ),
    OllamaRowLabelProbeCase(
        market="HK",
        report_family="annual",
        table_kind="balance_sheet",
        title_text="Consolidated Statement of Financial Position",
        raw_label="Net assets",
        local_context="Consolidated Statement of Financial Position\nNet assets",
        expected_value="none",
        expectation_type="negative",
    ),
)
