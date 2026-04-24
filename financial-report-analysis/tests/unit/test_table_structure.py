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
    assert table.table_unit == "万元"
    assert table.table_currency == "CNY"


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


def test_hk_income_statement_header_only_block_recovers_rows_from_page_text() -> None:
    adapter = PdfTableStructureAdapter()
    block = RawTableBlock(
        block_id="doc:page:153:table:1",
        page_index=153,
        page_range=(153, 153),
        rows=[["2025", "2024", "2023"]],
        page_text="\n".join(
            [
                "Consolidated Statements of Income",
                "Years ended December 31, 2025, 2024 and 2023",
                "(in US$ millions, except per share data)",
                "2025 2024 2023",
                "Total revenues 11,797 11,303 10,978",
                "Operating Profit 1,290 1,162 1,106",
                "Net Income - Yum China Holdings, Inc. $ 929 $ 911 $ 827",
                "Basic Earnings Per Common Share $ 2.52 $ 2.34 $ 1.99",
                "See accompanying Notes to Consolidated Financial Statements.",
            ]
        ),
        local_context="2025 2024 2023",
    )

    table = adapter._build_parsed_table(
        block=block,
        market="HK",
        document_id="doc",
        table_index=1,
    )

    assert table is not None
    assert table.table_kind == "income_statement"
    assert [
        (column.column_index, column.period_id) for column in table.period_columns
    ] == [
        (1, "2025FY"),
        (2, "2024FY"),
        (3, "2023FY"),
    ]
    assert [row.label_raw for row in table.body_rows] == [
        "Total revenues",
        "Operating Profit",
        "Net Income - Yum China Holdings, Inc.",
        "Basic Earnings Per Common Share",
    ]
    assert table.table_currency == "USD"
    assert table.table_unit == "US$ millions"


def test_hk_balance_sheet_header_only_block_recovers_point_rows_from_page_text() -> None:
    adapter = PdfTableStructureAdapter()
    block = RawTableBlock(
        block_id="doc:page:156:table:1",
        page_index=156,
        page_range=(156, 156),
        rows=[["2025", "2024"]],
        page_text="\n".join(
            [
                "Consolidated Balance Sheets",
                "December 31, 2025 and 2024",
                "(in US$ millions)",
                "2025 2024",
                "Cash and cash equivalents $ 506 $ 723",
                "Total Assets 10,783 11,121",
                "Short-term borrowings 30 127",
                "Total Liabilities 4,684 4,694",
                "Total Equity 6,099 6,414",
                "See accompanying Notes to Consolidated Financial Statements.",
            ]
        ),
        local_context="2025 2024",
    )

    table = adapter._build_parsed_table(
        block=block,
        market="HK",
        document_id="doc",
        table_index=1,
    )

    assert table is not None
    assert table.table_kind == "balance_sheet"
    assert [
        (column.column_index, column.period_id, column.value_time_shape)
        for column in table.period_columns
    ] == [
        (1, "2025FY", "point"),
        (2, "2024FY", "point"),
    ]
    assert [row.label_raw for row in table.body_rows] == [
        "Cash and cash equivalents",
        "Total Assets",
        "Short-term borrowings",
        "Total Liabilities",
        "Total Equity",
    ]


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


def test_statement_scope_does_not_treat_owners_of_parent_label_as_parent_company() -> None:
    scope = PdfTableStructureAdapter._guess_statement_scope(
        title_text="Consolidated Statement of Profit or Loss",
        local_context="Profit attributable to owners of the parent 100 90",
    )

    assert scope == "consolidated"


def test_statement_scope_detects_separate_company_statement_as_parent_company() -> None:
    scope = PdfTableStructureAdapter._guess_statement_scope(
        title_text="Company Statement of Financial Position",
        local_context="Unit: HKD million",
    )

    assert scope == "parent_only"


def test_statement_scope_detects_separate_statement_as_parent_company() -> None:
    scope = PdfTableStructureAdapter._guess_statement_scope(
        title_text="Separate Statement of Financial Position",
        local_context="Unit: HKD million",
    )

    assert scope == "parent_only"


def test_statement_scope_prefers_parent_title_over_consolidated_local_context() -> None:
    scope = PdfTableStructureAdapter._guess_statement_scope(
        title_text="Company Statement of Financial Position",
        local_context=(
            "Notes to the consolidated financial statements\n"
            "Consolidated Statement of Financial Position"
        ),
    )

    assert scope == "parent_only"


def test_statement_scope_detects_parent_scope_from_explicit_local_context() -> None:
    scope = PdfTableStructureAdapter._guess_statement_scope(
        title_text="Statement of Financial Position",
        local_context="Company Statement of Financial Position\nItem 2024",
    )

    assert scope == "parent_only"


def test_statement_scope_ignores_narrative_separate_statement_mentions() -> None:
    scope = PdfTableStructureAdapter._guess_statement_scope(
        title_text="Statement of Financial Position",
        local_context="See separate statement in the following pages.",
    )

    assert scope == "unknown"


def test_statement_scope_ignores_narrative_consolidated_mentions() -> None:
    scope = PdfTableStructureAdapter._guess_statement_scope(
        title_text="Statement of Financial Position",
        local_context="Notes to the consolidated financial statements.",
    )

    assert scope == "unknown"


def test_statement_scope_does_not_treat_attributable_owner_label_as_parent_company() -> None:
    scope = PdfTableStructureAdapter._guess_statement_scope(
        title_text="Statement of Financial Position",
        local_context="Equity attributable to owners of the parent 100 90",
    )

    assert scope == "unknown"


def test_statement_scope_detects_explicit_consolidated_local_context() -> None:
    scope = PdfTableStructureAdapter._guess_statement_scope(
        title_text="Statement of Financial Position",
        local_context="Consolidated Statement of Financial Position\nItem 2024",
    )

    assert scope == "consolidated"


def test_build_parsed_table_preserves_consolidated_and_parent_scopes_in_mixed_document() -> (
    None
):
    adapter = PdfTableStructureAdapter()
    consolidated_block = RawTableBlock(
        block_id="doc:page:10:table:1",
        page_index=10,
        page_range=(10, 10),
        rows=[
            ["Consolidated Statement of Financial Position"],
            ["Item", "2024"],
            ["Cash and cash equivalents", "1,000"],
        ],
        page_text=(
            "Consolidated Statement of Financial Position\n"
            "Item 2024\n"
            "Cash and cash equivalents 1,000"
        ),
    )
    parent_block = RawTableBlock(
        block_id="doc:page:10:table:2",
        page_index=10,
        page_range=(10, 10),
        rows=[
            ["Company Statement of Financial Position"],
            ["Item", "2024"],
            ["Cash and cash equivalents", "800"],
        ],
        page_text=(
            "Consolidated Statement of Financial Position\n"
            "Company Statement of Financial Position\n"
            "Item 2024\n"
            "Cash and cash equivalents 800"
        ),
        local_context=(
            "Company Statement of Financial Position\n"
            "Item 2024\n"
            "Cash and cash equivalents 800"
        ),
    )

    consolidated_table = adapter._build_parsed_table(
        block=consolidated_block,
        market="HK",
        document_id="doc",
        table_index=1,
    )
    parent_table = adapter._build_parsed_table(
        block=parent_block,
        market="HK",
        document_id="doc",
        table_index=2,
    )

    assert consolidated_table is not None
    assert consolidated_table.statement_scope_guess == "consolidated"
    assert parent_table is not None
    assert parent_table.statement_scope_guess == "parent_only"


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
