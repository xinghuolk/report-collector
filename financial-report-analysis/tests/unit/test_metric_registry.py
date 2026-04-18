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
