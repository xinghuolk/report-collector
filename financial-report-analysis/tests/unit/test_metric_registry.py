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
