import pytest

from financial_report_analysis.registries import load_metric_registry


def test_metric_mapping_registry_matches_revenue_from_income_statement_semantics() -> None:
    registry = load_metric_registry()
    definition = registry.match(
        table_kind="income_statement",
        normalized_row_label="revenue",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="CN",
    )

    assert definition is not None
    assert definition.metric_id == "revenue"
    assert definition.statement_type == "income_statement"


def test_metric_mapping_registry_rejects_deferred_revenue_false_positive() -> None:
    registry = load_metric_registry()

    assert (
        registry.match(
            table_kind="balance_sheet",
            normalized_row_label="deferred revenue",
            value_time_shape="point_in_time",
            statement_scope_guess="consolidated",
            market="CN",
        )
        is None
    )


def test_metric_mapping_registry_prefers_semantic_matches_over_flat_aliases() -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="income_statement",
        normalized_row_label="net profit",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert definition is not None
    assert definition.metric_id == "net_profit"


@pytest.mark.parametrize(
    ("market", "normalized_row_label", "metric_id"),
    [
        ("CN", "应收账款", "accounts_receiv"),
        ("CN", "应收票据", "notes_receiv"),
        ("CN", "其他应收款", "oth_receiv"),
        ("CN", "合同负债", "contract_liab"),
        ("CN", "预收款项", "adv_receipts"),
        ("CN", "应付账款", "acct_payable"),
        ("CN", "应付票据", "notes_payable"),
        ("HK", "accounts receivable", "accounts_receiv"),
        ("HK", "notes receivable", "notes_receiv"),
        ("HK", "other receivables", "oth_receiv"),
        ("HK", "contract liabilities", "contract_liab"),
        ("HK", "payments received in advance", "adv_receipts"),
        ("HK", "accounts payable", "acct_payable"),
        ("HK", "notes payable", "notes_payable"),
    ],
)
def test_metric_mapping_registry_matches_p2a_working_capital_rows(
    market: str,
    normalized_row_label: str,
    metric_id: str,
) -> None:
    registry = load_metric_registry()
    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label=normalized_row_label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is not None
    assert definition.metric_id == metric_id
    assert definition.statement_type == "balance_sheet"
    assert definition.period_scope == "point_in_time"
    assert definition.value_type == "amount"
    assert definition.unit_expectation == "currency_amount"


@pytest.mark.parametrize(
    ("market", "normalized_row_label"),
    [
        ("HK", "accounts receivable financing"),
        ("HK", "long-term receivables"),
        ("HK", "employee compensation payable"),
        ("HK", "taxes payable"),
        ("HK", "bonds payable"),
        ("CN", "应收款项融资"),
        ("CN", "长期应收款"),
        ("CN", "应付职工薪酬"),
        ("CN", "应交税费"),
        ("CN", "应付债券"),
    ],
)
def test_metric_mapping_registry_rejects_p2a_false_positives(
    market: str,
    normalized_row_label: str,
) -> None:
    registry = load_metric_registry()

    assert (
        registry.match(
            table_kind="balance_sheet",
            normalized_row_label=normalized_row_label,
            value_time_shape="point_in_time",
            statement_scope_guess="consolidated",
            market=market,
        )
        is None
    )
