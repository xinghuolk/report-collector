from financial_report_analysis.models import (
    NormalizedTableCellValue,
    NormalizedTableColumn,
    NormalizedTableRow,
    NormalizedTableSemantics,
)
from financial_report_analysis.registries import load_metric_registry
from financial_report_analysis.services.table_fact_builder import (
    build_table_candidate_facts,
)


def test_table_fact_builder_emits_candidate_fact_for_hk_q3_revenue() -> None:
    candidates = build_table_candidate_facts(
        [
            NormalizedTableSemantics(
                table_id="table-1",
                document_id="09987-q3",
                table_kind="income_statement",
                title_text="Condensed Consolidated Statements of Income",
                statement_scope_guess="consolidated",
                table_unit="thousand",
                table_currency="HKD",
                semantic_source="deterministic",
                semantic_confidence=None,
                semantic_ambiguity_reason=None,
                columns=[
                    NormalizedTableColumn(
                        column_id="column-1",
                        header_text="Three months ended 30 September 2025",
                        period_id="2025Q3_YTD",
                        comparison_axis="current",
                        value_time_shape="duration",
                        is_current=True,
                        is_comparison=False,
                    )
                ],
                rows=[
                    NormalizedTableRow(
                        row_id="row-1",
                        label_raw="Revenue",
                        normalized_row_label="revenue",
                        semantic_source="deterministic",
                        semantic_confidence=None,
                        fallback_reason=None,
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="1,234",
                                numeric_value=1234.0,
                                period_id="2025Q3_YTD",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    )
                ],
            )
        ],
        registry=load_metric_registry(),
        document_id="09987-q3",
        market="HK",
    )

    assert len(candidates) == 1
    assert candidates[0]["metric_id"] == "revenue"
    assert candidates[0]["period_id"] == "2025Q3_YTD"
    assert candidates[0]["statement_type"] == "income_statement"
    assert candidates[0]["extensions"]["semantic_source"] == "deterministic"
    assert "semantic_confidence" in candidates[0]["extensions"]
    assert "fallback_reason" in candidates[0]["extensions"]
    assert candidates[0]["extensions"]["statement_scope_guess"] == "consolidated"
