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


@dataclass(frozen=True, slots=True)
class OllamaSemanticProbeCase:
    market: str
    report_family: str
    semantic_kind: str
    title_text: str
    raw_text: str
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
        market="HK",
        report_family="annual",
        table_kind="cash_flow_statement",
        title_text="Consolidated Statement of Cash Flows",
        raw_label="Net cash from operating activities",
        local_context=(
            "Consolidated Statement of Cash Flows\n"
            "Net cash from operating activities"
        ),
        expected_value="operating_cash_flow",
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
    OllamaRowLabelProbeCase(
        market="HK",
        report_family="annual",
        table_kind="income_statement",
        title_text="Consolidated Statement of Profit or Loss",
        raw_label="Gross margin",
        local_context="Consolidated Statement of Profit or Loss\nGross margin",
        expected_value="none",
        expectation_type="negative",
    ),
)

PROMOTED_REAL_REPORT_PROBE_IDENTITIES: tuple[
    tuple[str, str, str, str, str], ...
] = (
    ("HK", "annual", "income_statement", "Business revenue", "revenue"),
    ("HK", "annual", "income_statement", "Operating income", "operating_profit"),
    (
        "HK",
        "annual",
        "income_statement",
        "Profit attributable to owners",
        "net_profit",
    ),
    ("HK", "annual", "balance_sheet", "Cash and cash equivalents", "cash"),
    ("CN", "annual", "income_statement", "Revenue growth", "none"),
    ("HK", "annual", "income_statement", "Gross margin", "none"),
)


def promoted_real_report_probe_cases() -> tuple[OllamaRowLabelProbeCase, ...]:
    case_index = {
        (
            case.market,
            case.report_family,
            case.table_kind,
            case.raw_label,
            case.expected_value,
        ): case
        for case in REAL_REPORT_ROW_LABEL_PROBE_CASES
    }
    return tuple(case_index[identity] for identity in PROMOTED_REAL_REPORT_PROBE_IDENTITIES)


PROMOTED_REAL_REPORT_PROBE_CASES: tuple[OllamaRowLabelProbeCase, ...] = (
    promoted_real_report_probe_cases()
)


REAL_REPORT_SEMANTIC_PROBE_CASES: tuple[OllamaSemanticProbeCase, ...] = (
    OllamaSemanticProbeCase(
        market="HK",
        report_family="annual",
        semantic_kind="currency",
        title_text="Consolidated Statement of Financial Position",
        raw_text="HK$ million",
        local_context=(
            "Consolidated Statement of Financial Position\n"
            "Presented in HK$ million unless otherwise stated"
        ),
        expected_value="HKD",
        expectation_type="positive",
    ),
    OllamaSemanticProbeCase(
        market="HK",
        report_family="annual",
        semantic_kind="unit",
        title_text="Consolidated Statement of Financial Position",
        raw_text="HK$'000",
        local_context=(
            "Consolidated Statement of Financial Position\n"
            "Amounts expressed in thousands of Hong Kong dollars"
        ),
        expected_value="thousand",
        expectation_type="positive",
    ),
    OllamaSemanticProbeCase(
        market="CN",
        report_family="annual",
        semantic_kind="currency",
        title_text="Consolidated Income Statement",
        raw_text="not specified",
        local_context=(
            "Consolidated Income Statement\n"
            "Currency is not specified in this excerpt"
        ),
        expected_value="unknown",
        expectation_type="negative",
    ),
    OllamaSemanticProbeCase(
        market="HK",
        report_family="quarterly",
        semantic_kind="unit",
        title_text="Condensed Consolidated Statement of Profit or Loss",
        raw_text="items",
        local_context=(
            "Condensed Consolidated Statement of Profit or Loss\n"
            "Counts of stores and employees, not monetary units"
        ),
        expected_value="unknown",
        expectation_type="negative",
    ),
)

PROMOTED_REAL_REPORT_SEMANTIC_PROBE_IDENTITIES: tuple[
    tuple[str, str, str, str, str], ...
] = (
    ("HK", "annual", "currency", "HK$ million", "HKD"),
    ("HK", "annual", "unit", "HK$'000", "thousand"),
)


def promoted_real_report_semantic_probe_cases() -> tuple[OllamaSemanticProbeCase, ...]:
    case_index = {
        (
            case.market,
            case.report_family,
            case.semantic_kind,
            case.raw_text,
            case.expected_value,
        ): case
        for case in REAL_REPORT_SEMANTIC_PROBE_CASES
    }
    return tuple(
        case_index[identity] for identity in PROMOTED_REAL_REPORT_SEMANTIC_PROBE_IDENTITIES
    )


PROMOTED_REAL_REPORT_SEMANTIC_PROBE_CASES: tuple[OllamaSemanticProbeCase, ...] = (
    promoted_real_report_semantic_probe_cases()
)
