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
