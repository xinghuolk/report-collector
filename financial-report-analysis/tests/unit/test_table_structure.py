from __future__ import annotations

from financial_report_analysis.ingestion.table_source import RawTableBlock
from financial_report_analysis.ingestion.table_structure import PdfTableStructureAdapter


def test_build_parsed_table_prefers_table_local_unit_and_currency_context() -> None:
    adapter = PdfTableStructureAdapter()
    block = RawTableBlock(
        block_id="doc:page:1:table:1",
        page_index=1,
        page_range=(1, 1),
        rows=[
            ["合并利润表"],
            ["项目", "2024年度"],
            ["单位：万元", "币种：人民币"],
            ["营业收入", "363,891.11"],
        ],
        page_text="Other page context\n单位：百万元\n币种：美元\nUSD million should not win",
    )

    table = adapter._build_parsed_table(
        block=block,
        market="CN",
        document_id="doc",
        table_index=1,
    )

    assert table is not None
    assert table.table_unit is not None
    assert table.table_currency == "CNY"
    assert table.source_blocks[0].raw_text.startswith("合并利润表")
    assert "单位：百万元" not in table.source_blocks[0].raw_text
    assert "USD million" not in table.source_blocks[0].raw_text


def test_build_parsed_table_preserves_local_context_in_source_block() -> None:
    adapter = PdfTableStructureAdapter()
    block = RawTableBlock(
        block_id="doc:page:2:table:1",
        page_index=2,
        page_range=(2, 2),
        rows=[
            ["Condensed Consolidated Statement of Profit or Loss"],
            ["Item", "Three months ended 30 September 2025"],
            ["Revenue", "10,000"],
        ],
        page_text=(
            "Quarterly Report Context\n"
            "Prepared by management\n"
            "Condensed Consolidated Statement of Profit or Loss\n"
            "Item Three months ended 30 September 2025\n"
            "Revenue 10,000"
        ),
    )

    table = adapter._build_parsed_table(
        block=block,
        market="HK",
        document_id="doc",
        table_index=1,
    )

    assert table is not None
    assert table.source_blocks
    assert table.source_blocks[0].raw_text.startswith(
        "Condensed Consolidated Statement of Profit or Loss"
    )
    assert "Quarterly Report Context" not in table.source_blocks[0].raw_text
    assert "Three months ended 30 September 2025" in table.source_blocks[0].raw_text


def test_infer_table_title_prefers_title_row_over_full_page_text() -> None:
    adapter = PdfTableStructureAdapter()
    block = RawTableBlock(
        block_id="doc:page:2:table:1",
        page_index=2,
        page_range=(2, 2),
        rows=[
            ["Condensed Consolidated Statement of Profit or Loss"],
            ["Item", "Three months ended 30 September 2025"],
            ["Revenue", "10,000"],
        ],
        page_text=(
            "Narrative introduction. Condensed Consolidated Statement of Profit or Loss "
            "Additional notes and discussion for the page."
        ),
    )

    title = adapter._infer_table_title(block, market="HK")

    assert title == "Condensed Consolidated Statement of Profit or Loss"


def test_build_parsed_table_sets_statement_scope_guess_from_title() -> None:
    adapter = PdfTableStructureAdapter()
    block = RawTableBlock(
        block_id="doc:page:3:table:1",
        page_index=3,
        page_range=(3, 3),
        rows=[
            ["Consolidated Statement of Financial Position"],
            ["Item", "2024"],
            ["Cash and cash equivalents", "1,000"],
        ],
        page_text="Consolidated Statement of Financial Position\nUnit: HKD million",
    )

    table = adapter._build_parsed_table(
        block=block,
        market="HK",
        document_id="doc",
        table_index=1,
    )

    assert table is not None
    assert table.statement_scope_guess == "consolidated"


def test_build_parsed_table_recovers_rows_from_numeric_only_statement_page_text() -> None:
    adapter = PdfTableStructureAdapter()
    block = RawTableBlock(
        block_id="doc:page:134:table:1",
        page_index=134,
        page_range=(134, 134),
        rows=[
            ["689,022,322.44"],
            ["607,645,160.15"],
            ["981,111,286.02"],
            ["754,316,996.75"],
        ],
        page_text=(
            "31 December 2022\n"
            "Prepared by: Triumph New Energy Company Limited Consolidated Balance Sheet\n"
            "Unit: Yuan Currency: RMB\n"
            "Item Note 31 December 2022 31 December 2021\n"
            "Monetary funds VII.1 689,022,322.44 1,116,571,580.99\n"
            "Notes receivable VII.2 607,645,160.15 204,999,510.62\n"
            "Accounts receivable VII.3 981,111,286.02 438,504,721.48\n"
            "133\n"
        ),
    )

    table = adapter._build_parsed_table(
        block=block,
        market="HK",
        document_id="doc",
        table_index=1,
    )

    assert table is not None
    assert table.semantic_ambiguity_reason == "numeric_only_statement_block"
    assert table.table_kind == "balance_sheet"
    assert table.header_rows == [["Item Note", "31 December 2022", "31 December 2021"]]
    assert [row.label_raw for row in table.body_rows[:2]] == [
        "Monetary funds VII.1",
        "Notes receivable VII.2",
    ]
    assert [
        (column.column_index, column.period_id, column.value_time_shape)
        for column in table.period_columns
    ] == [
        (1, "2022FY", "point"),
        (2, "2021FY", "point"),
    ]
    first_row_period_ids = {
        cell.column_index: next(
            (
                column.period_id
                for column in table.period_columns
                if column.column_index == cell.column_index
            ),
            None,
        )
        for cell in table.body_rows[0].value_cells
    }
    assert first_row_period_ids == {
        1: "2022FY",
        2: "2021FY",
    }
