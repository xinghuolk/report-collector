from financial_report_analysis.registries import load_metric_registry
from financial_report_analysis.registries.metric_registry import MetricRegistry


def test_metric_registry_creates_provisional_custom_metric() -> None:
    registry = MetricRegistry(standard_metrics={"revenue": ["Revenue", "营业收入"]})

    standard = registry.resolve_metric(
        raw_label="营业收入",
        statement_type="income_statement",
        accounting_standard="HKFRS",
        industry_slug="consumer",
        parent_metric_id=None,
    )
    custom = registry.resolve_metric(
        raw_label="Other income",
        statement_type="income_statement",
        accounting_standard="HKFRS",
        industry_slug="consumer",
        parent_metric_id="revenue",
    )
    different_statement = registry.resolve_metric(
        raw_label="Other income",
        statement_type="balance_sheet",
        accounting_standard="HKFRS",
        industry_slug="consumer",
        parent_metric_id="revenue",
    )
    different_parent = registry.resolve_metric(
        raw_label="Other income",
        statement_type="income_statement",
        accounting_standard="HKFRS",
        industry_slug="consumer",
        parent_metric_id="assets",
    )

    assert standard.metric_id == "revenue"
    assert standard.is_custom is False
    assert custom.is_custom is True
    assert custom.registry_status == "provisional"
    assert custom.metric_id.startswith("custom::hkfrs::consumer::")
    assert custom.metric_id != different_statement.metric_id
    assert custom.metric_id != different_parent.metric_id


def test_metric_mapping_registry_matches_operating_cost_for_cn_income_statement() -> None:
    definition = load_metric_registry().match(
        table_kind="income_statement",
        normalized_row_label="营业成本",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="CN",
    )

    assert definition is not None
    assert definition.metric_id == "operating_cost"


def test_metric_mapping_registry_matches_net_profit_for_hk_income_statement() -> None:
    definition = load_metric_registry().match(
        table_kind="income_statement",
        normalized_row_label="profit attributable to equity holders",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert definition is not None
    assert definition.metric_id == "net_profit"


def test_metric_mapping_registry_matches_gross_profit_aliases() -> None:
    registry = load_metric_registry()

    cn_definition = registry.match(
        table_kind="income_statement",
        normalized_row_label="营业毛利",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="CN",
    )
    hk_definition = registry.match(
        table_kind="income_statement",
        normalized_row_label="gross profit attributable to operations",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert cn_definition is not None
    assert cn_definition.metric_id == "gross_profit"
    assert hk_definition is not None
    assert hk_definition.metric_id == "gross_profit"


def test_metric_mapping_registry_matches_equity_aliases() -> None:
    registry = load_metric_registry()

    total_equity = registry.match(
        table_kind="balance_sheet",
        normalized_row_label="所有者权益合计",
        value_time_shape="point",
        statement_scope_guess="consolidated",
        market="CN",
    )
    attributable_equity = registry.match(
        table_kind="balance_sheet",
        normalized_row_label="equity attributable to owners of the parent",
        value_time_shape="point",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert total_equity is not None
    assert total_equity.metric_id == "equity"
    assert attributable_equity is not None
    assert attributable_equity.metric_id == "equity_attributable_to_owners"


def test_metric_mapping_registry_does_not_accept_generic_equity_aliases() -> None:
    registry = load_metric_registry()

    generic_equity = registry.match(
        table_kind="balance_sheet",
        normalized_row_label="equity attributable to owners",
        value_time_shape="point",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert generic_equity is None


def test_metric_mapping_registry_does_not_match_gross_profit_outside_income_statement() -> None:
    definition = load_metric_registry().match(
        table_kind="key_metrics",
        normalized_row_label="gross profit",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert definition is None


def test_metric_mapping_registry_does_not_match_equity_ratio_or_book_value_rows() -> None:
    registry = load_metric_registry()

    equity_ratio = registry.match(
        table_kind="balance_sheet",
        normalized_row_label="equity ratio",
        value_time_shape="point",
        statement_scope_guess="consolidated",
        market="HK",
    )
    net_assets_per_share = registry.match(
        table_kind="balance_sheet",
        normalized_row_label="net assets per share",
        value_time_shape="point",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert equity_ratio is None
    assert net_assets_per_share is None


def test_metric_mapping_registry_matches_total_assets_cn_aliases() -> None:
    definition = load_metric_registry().match(
        table_kind="balance_sheet",
        normalized_row_label="总资产",
        value_time_shape="point",
        statement_scope_guess="consolidated",
        market="CN",
    )

    assert definition is not None
    assert definition.metric_id == "total_assets"


def test_metric_mapping_registry_matches_cash_hk_aliases() -> None:
    definition = load_metric_registry().match(
        table_kind="balance_sheet",
        normalized_row_label="cash and cash equivalents",
        value_time_shape="point",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert definition is not None
    assert definition.metric_id == "cash"


def test_metric_mapping_registry_matches_cash_flow_primary_section_aliases() -> None:
    registry = load_metric_registry()

    operating = registry.match(
        table_kind="cash_flow_statement",
        normalized_row_label="net cash from operating activities",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )
    investing = registry.match(
        table_kind="cash_flow_statement",
        normalized_row_label="net cash from investing activities",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )
    financing = registry.match(
        table_kind="cash_flow_statement",
        normalized_row_label="net cash from financing activities",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert operating is not None
    assert operating.metric_id == "operating_cash_flow"
    assert investing is not None
    assert investing.metric_id == "investing_cash_flow"
    assert financing is not None
    assert financing.metric_id == "financing_cash_flow"


def test_metric_mapping_registry_does_not_match_cash_flow_summary_rows() -> None:
    registry = load_metric_registry()

    net_increase = registry.match(
        table_kind="cash_flow_statement",
        normalized_row_label="net increase/decrease in cash and cash equivalents",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )
    free_cash_flow = registry.match(
        table_kind="cash_flow_statement",
        normalized_row_label="free cash flow",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )
    cash_flow_ratio = registry.match(
        table_kind="cash_flow_statement",
        normalized_row_label="cash flow ratio",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert net_increase is None
    assert free_cash_flow is None
    assert cash_flow_ratio is None
