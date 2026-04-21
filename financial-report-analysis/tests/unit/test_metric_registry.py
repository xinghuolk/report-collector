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


def test_metric_mapping_registry_matches_phase1_income_statement_aliases() -> None:
    registry = load_metric_registry()

    attributable_profit = registry.match(
        table_kind="income_statement",
        normalized_row_label="归属于上市公司股东的净利润",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="CN",
    )
    finance_exp = registry.match(
        table_kind="income_statement",
        normalized_row_label="finance costs",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )
    total_profit = registry.match(
        table_kind="income_statement",
        normalized_row_label="profit before tax",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )
    income_tax = registry.match(
        table_kind="income_statement",
        normalized_row_label="所得税费用",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="CN",
    )
    minority_gain = registry.match(
        table_kind="income_statement",
        normalized_row_label="profit attributable to non-controlling interests",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert attributable_profit is not None
    assert attributable_profit.metric_id == "n_income_attr_p"
    assert finance_exp is not None
    assert finance_exp.metric_id == "finance_exp"
    assert total_profit is not None
    assert total_profit.metric_id == "total_profit"
    assert income_tax is not None
    assert income_tax.metric_id == "income_tax"
    assert minority_gain is not None
    assert minority_gain.metric_id == "minority_gain"


def test_metric_mapping_registry_models_basic_eps_as_per_share_metric() -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="income_statement",
        normalized_row_label="basic earnings per share",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert definition is not None
    assert definition.metric_id == "basic_eps"
    assert definition.value_type == "per_share"
    assert definition.unit_expectation == "per_share_amount"


def test_metric_mapping_registry_matches_phase1_cash_flow_detail_aliases() -> None:
    registry = load_metric_registry()

    capex = registry.match(
        table_kind="cash_flow_statement",
        normalized_row_label="购建固定资产、无形资产和其他长期资产支付的现金",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="CN",
    )
    depreciation = registry.match(
        table_kind="cash_flow_statement",
        normalized_row_label="depreciation of property, plant and equipment",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )
    amortisation = registry.match(
        table_kind="cash_flow_statement",
        normalized_row_label="amortisation of intangible assets",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )
    deferred_amortisation = registry.match(
        table_kind="cash_flow_statement",
        normalized_row_label="长期待摊费用摊销",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="CN",
    )
    dividends_paid = registry.match(
        table_kind="cash_flow_statement",
        normalized_row_label="dividends paid",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert capex is not None
    assert capex.metric_id == "c_pay_acq_const_fiolta"
    assert depreciation is not None
    assert depreciation.metric_id == "depr_fa_coga_dpba"
    assert amortisation is not None
    assert amortisation.metric_id == "amort_intang_assets"
    assert deferred_amortisation is not None
    assert deferred_amortisation.metric_id == "lt_amort_deferred_exp"
    assert dividends_paid is not None
    assert dividends_paid.metric_id == "c_pay_dist_dpcp_int_exp"


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
