import pytest

from financial_report_analysis.registries import load_metric_registry

_P4C_METRIC_IDS = {
    "revenue",
    "operating_cost",
    "operating_profit",
    "net_profit",
    "total_assets",
    "total_liabilities",
    "equity_attributable_to_owners",
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "c_pay_to_staff",
    "c_paid_for_taxes",
}


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
    ("metric_id", "market", "table_kind", "label", "period_scope", "statement_type"),
    [
        ("revenue", "HK", "income_statement", "turnover", "duration", "income_statement"),
        (
            "operating_cost",
            "HK",
            "income_statement",
            "cost of sales",
            "duration",
            "income_statement",
        ),
        (
            "operating_profit",
            "HK",
            "income_statement",
            "profit from operations",
            "duration",
            "income_statement",
        ),
        (
            "net_profit",
            "HK",
            "income_statement",
            "net income",
            "duration",
            "income_statement",
        ),
        (
            "total_assets",
            "CN",
            "balance_sheet",
            "资产总计",
            "point_in_time",
            "balance_sheet",
        ),
        (
            "total_liabilities",
            "CN",
            "balance_sheet",
            "负债合计",
            "point_in_time",
            "balance_sheet",
        ),
        (
            "equity_attributable_to_owners",
            "CN",
            "balance_sheet",
            "归属于母公司股东权益",
            "point_in_time",
            "balance_sheet",
        ),
        (
            "operating_cash_flow",
            "CN",
            "cash_flow_statement",
            "经营活动产生的现金流量净额",
            "duration",
            "cash_flow_statement",
        ),
        (
            "investing_cash_flow",
            "HK",
            "cash_flow_statement",
            "net cash used in investing activities",
            "duration",
            "cash_flow_statement",
        ),
        (
            "financing_cash_flow",
            "CN",
            "cash_flow_statement",
            "筹资活动产生的现金流量净额",
            "duration",
            "cash_flow_statement",
        ),
        (
            "c_pay_to_staff",
            "HK",
            "cash_flow_statement",
            "cash paid to and on behalf of employees",
            "duration",
            "cash_flow_statement",
        ),
        (
            "c_paid_for_taxes",
            "CN",
            "cash_flow_statement",
            "支付的各项税费",
            "duration",
            "cash_flow_statement",
        ),
    ],
)
def test_metric_mapping_registry_matches_p4c_core_statement_fields(
    metric_id: str,
    market: str,
    table_kind: str,
    label: str,
    period_scope: str,
    statement_type: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind=table_kind,
        normalized_row_label=label,
        value_time_shape=period_scope,
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is not None
    assert definition.metric_id == metric_id
    assert definition.statement_type == statement_type
    assert definition.period_scope == period_scope


@pytest.mark.parametrize(
    ("market", "table_kind", "label", "period_scope"),
    [
        ("HK", "income_statement", "gross profit", "duration"),
        ("HK", "income_statement", "ebitda", "duration"),
        ("HK", "income_statement", "adjusted net profit", "duration"),
        (
            "HK",
            "income_statement",
            "profit for the year attributable to owners of the parent",
            "duration",
        ),
        (
            "HK",
            "income_statement",
            "profit attributable to owners of the parent",
            "duration",
        ),
        ("CN", "income_statement", "归属于母公司股东的净利润", "duration"),
        ("HK", "income_statement", "other income", "duration"),
        ("CN", "income_statement", "投资收益", "duration"),
        ("HK", "cash_flow_statement", "cash and cash equivalents", "duration"),
        ("HK", "balance_sheet", "total equity", "point_in_time"),
    ],
)
def test_metric_mapping_registry_rejects_p4c_negative_controls(
    market: str,
    table_kind: str,
    label: str,
    period_scope: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind=table_kind,
        normalized_row_label=label,
        value_time_shape=period_scope,
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is None or definition.metric_id not in _P4C_METRIC_IDS


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
            ("CN", "应收款项融资"),
            ("CN", "长期应收款"),
            ("CN", "应付职工薪酬"),
            ("CN", "应交税费"),
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


@pytest.mark.parametrize(
    ("normalized_row_label", "metric_id"),
    [
        ("accounts_receiv", "accounts_receiv"),
        ("notes_receiv", "notes_receiv"),
        ("oth_receiv", "oth_receiv"),
        ("contract_liab", "contract_liab"),
        ("adv_receipts", "adv_receipts"),
        ("acct_payable", "acct_payable"),
        ("notes_payable", "notes_payable"),
    ],
)
def test_metric_mapping_registry_matches_p2a_working_capital_token_outputs(
    normalized_row_label: str,
    metric_id: str,
) -> None:
    registry = load_metric_registry()
    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label=normalized_row_label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert definition is not None
    assert definition.metric_id == metric_id


@pytest.mark.parametrize(
    ("metric_id", "market", "label"),
    [
        ("st_borr", "CN", "\u77ed\u671f\u501f\u6b3e"),
        ("lt_borr", "CN", "\u957f\u671f\u501f\u6b3e"),
        ("bond_payable", "CN", "\u5e94\u4ed8\u503a\u5238"),
        (
            "non_cur_liab_due_1y",
            "CN",
            "\u4e00\u5e74\u5185\u5230\u671f\u7684\u975e\u6d41\u52a8\u8d1f\u503a",
        ),
        ("st_borr", "HK", "short-term borrowings"),
        ("lt_borr", "HK", "long-term borrowings"),
        ("bond_payable", "HK", "bonds payable"),
        ("non_cur_liab_due_1y", "HK", "current portion of long-term debt"),
    ],
)
def test_metric_mapping_registry_matches_p2b_debt_fields(
    metric_id: str,
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label=label,
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
    assert definition.sign_rule == "allow_negative"


@pytest.mark.parametrize(
    ("market", "label"),
    [
        ("HK", "lease liabilities"),
        ("HK", "total borrowings"),
        ("CN", "\u79df\u8d41\u8d1f\u503a"),
        ("CN", "\u501f\u6b3e\u5408\u8ba1"),
    ],
)
def test_metric_mapping_registry_rejects_p2b_negative_controls(
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label=label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is None


@pytest.mark.parametrize(
    ("market", "label"),
    [
        ("HK", "notes payable"),
        ("CN", "\u5e94\u4ed8\u7968\u636e"),
    ],
)
def test_metric_mapping_registry_keeps_notes_payable_distinct_from_bond_payable(
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label=label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is not None
    assert definition.metric_id == "notes_payable"
    assert definition.metric_id != "bond_payable"


@pytest.mark.parametrize(
    ("metric_id", "market", "label"),
    [
        ("cash", "CN", "货币资金"),
        ("trad_asset", "CN", "交易性金融资产"),
        ("inventories", "CN", "存货"),
        ("goodwill", "CN", "商誉"),
        ("intang_assets", "CN", "无形资产"),
        ("cash", "HK", "cash and cash equivalents"),
        ("trad_asset", "HK", "trading assets"),
        ("inventories", "HK", "inventories"),
        ("goodwill", "HK", "goodwill"),
        ("intang_assets", "HK", "intangible assets"),
    ],
)
def test_metric_mapping_registry_matches_p3_asset_quality_fields(
    metric_id: str,
    market: str,
    label: str,
) -> None:
    # `money_cap` is the Turtle export alias for canonical `cash`; the registry
    # keeps canonical metric identity stable for table-derived facts.
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label=label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is not None
    assert definition.metric_id == metric_id
    assert definition.statement_type == "balance_sheet"
    assert definition.period_scope == "point_in_time"


@pytest.mark.parametrize(
    ("market", "label"),
    [
        ("CN", "合同资产"),
        ("CN", "其他非流动资产"),
        ("HK", "contract assets"),
        ("HK", "other non-current assets"),
    ],
)
def test_metric_mapping_registry_does_not_promote_p3_note_only_asset_fields_into_primary_path(
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label=label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is None


@pytest.mark.parametrize(
    ("market", "label"),
    [
        ("HK", "restricted cash"),
        ("HK", "assets held for sale"),
        ("HK", "investment properties"),
        ("HK", "prepayments"),
        ("HK", "right-of-use assets"),
        ("HK", "deferred tax assets"),
        ("HK", "capitalized development costs"),
        ("HK", "total non-current assets"),
        ("CN", "受限资金"),
        ("CN", "持有待售资产"),
        ("CN", "投资性房地产"),
        ("CN", "预付款项"),
        ("CN", "使用权资产"),
        ("CN", "递延所得税资产"),
        ("CN", "开发支出"),
    ],
)
def test_metric_mapping_registry_rejects_p3_asset_negative_controls(
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label=label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is None


@pytest.mark.parametrize(
    ("metric_id", "market", "label", "statement_type", "period_scope"),
    [
        ("restricted_cash", "HK", "restricted cash", "balance_sheet", "point_in_time"),
        (
            "restricted_cash",
            "HK",
            "restricted cash and cash equivalents",
            "balance_sheet",
            "point_in_time",
        ),
        (
            "interest_paid_cash",
            "HK",
            "cash paid for interest",
            "cash_flow_statement",
            "duration",
        ),
        (
            "time_deposits_or_wealth_products",
            "HK",
            "time deposits",
            "balance_sheet",
            "point_in_time",
        ),
        (
            "time_deposits_or_wealth_products",
            "HK",
            "wealth management products",
            "balance_sheet",
            "point_in_time",
        ),
        (
            "time_deposits_or_wealth_products",
            "CN",
            "\u5b9a\u671f\u5b58\u6b3e",
            "balance_sheet",
            "point_in_time",
        ),
        (
            "time_deposits_or_wealth_products",
            "CN",
            "\u7406\u8d22\u4ea7\u54c1",
            "balance_sheet",
            "point_in_time",
        ),
    ],
)
def test_metric_mapping_registry_matches_p4b_cash_health_fields(
    metric_id: str,
    market: str,
    label: str,
    statement_type: str,
    period_scope: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="note_disclosure",
        normalized_row_label=label,
        value_time_shape=period_scope,
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is not None
    assert definition.metric_id == metric_id
    assert definition.statement_type == statement_type
    assert definition.period_scope == period_scope


@pytest.mark.parametrize(
    ("market", "label"),
    [
        ("HK", "finance costs"),
        ("HK", "interest expense"),
        ("HK", "short-term investments"),
        ("HK", "cash and cash equivalents"),
        ("CN", "\u8d22\u52a1\u8d39\u7528"),
        ("CN", "\u5229\u606f\u652f\u51fa"),
        ("CN", "\u8d27\u5e01\u8d44\u91d1"),
        ("CN", "\u4ea4\u6613\u6027\u91d1\u878d\u8d44\u4ea7"),
    ],
)
def test_metric_mapping_registry_does_not_misclassify_non_cash_health_rows(
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="note_disclosure",
        normalized_row_label=label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is None
