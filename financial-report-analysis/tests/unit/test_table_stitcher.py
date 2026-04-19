from financial_report_analysis.ingestion.table_stitcher import (
    bind_body_rows,
    should_merge_tables,
    stitch_tables,
)
from financial_report_analysis.models import ParsedTable


def test_should_merge_tables_for_continued_income_statement() -> None:
    previous = ParsedTable(
        table_id="doc:table:1",
        document_id="doc",
        page_range=(20, 20),
        table_kind="income_statement",
        title_text="合并利润表",
    )
    current = ParsedTable(
        table_id="doc:table:2",
        document_id="doc",
        page_range=(21, 21),
        table_kind="income_statement",
        title_text="合并利润表（续）",
    )

    assert should_merge_tables(previous, current) is True


def test_should_merge_tables_for_continued_balance_sheet() -> None:
    previous = ParsedTable(
        table_id="doc:table:3",
        document_id="doc",
        page_range=(5, 5),
        table_kind="balance_sheet",
        title_text="合并资产负债表",
    )
    current = ParsedTable(
        table_id="doc:table:4",
        document_id="doc",
        page_range=(6, 6),
        table_kind="balance_sheet",
        title_text="合并资产负债表（续）",
    )

    assert should_merge_tables(previous, current) is True


def test_should_not_merge_same_page_continued_looking_tables() -> None:
    previous = ParsedTable(
        table_id="doc:table:5",
        document_id="doc",
        page_range=(8, 8),
        table_kind="cash_flow_statement",
        title_text="合并现金流量表",
    )
    current = ParsedTable(
        table_id="doc:table:6",
        document_id="doc",
        page_range=(8, 8),
        table_kind="cash_flow_statement",
        title_text="合并现金流量表（续）",
    )

    assert should_merge_tables(previous, current) is False


def test_bind_body_rows_extracts_numeric_cells() -> None:
    rows = bind_body_rows(
        page_index=0,
        body_lines=[
            "营业收入 3,638,911,068.29 3,049,155,693.42",
            "总资产 15,444,000,000.00 13,210,000,000.00",
        ],
    )

    assert rows[0].label_raw == "营业收入"
    assert rows[0].value_cells[0].numeric_value == 3638911068.29
    assert rows[0].value_cells[1].numeric_value == 3049155693.42
    assert rows[1].label_raw == "总资产"


def test_stitch_tables_merges_continued_adjacent_income_statement_pages() -> None:
    first = ParsedTable(
        table_id="doc:table:1",
        document_id="doc",
        page_range=(20, 20),
        table_kind="income_statement",
        title_text="合并利润表",
        body_rows=bind_body_rows(
            page_index=20,
            body_lines=["营业收入 3,638,911,068.29 3,049,155,693.42"],
        ),
    )
    second = ParsedTable(
        table_id="doc:table:2",
        document_id="doc",
        page_range=(21, 21),
        table_kind="income_statement",
        title_text="合并利润表（续）",
        body_rows=bind_body_rows(
            page_index=21,
            body_lines=["营业成本 2,105,000,000.00 1,942,000,000.00"],
        ),
    )

    stitched = stitch_tables([first, second])

    assert len(stitched) == 1
    assert stitched[0].page_range == (20, 21)
    assert [row.label_raw for row in stitched[0].body_rows] == [
        "营业收入",
        "营业成本",
    ]


def test_stitch_tables_merges_continued_adjacent_balance_sheet_pages() -> None:
    first = ParsedTable(
        table_id="doc:table:7",
        document_id="doc",
        page_range=(30, 30),
        table_kind="balance_sheet",
        title_text="合并资产负债表",
        body_rows=bind_body_rows(
            page_index=30,
            body_lines=["货币资金 1,000,000.00 900,000.00"],
        ),
    )
    second = ParsedTable(
        table_id="doc:table:8",
        document_id="doc",
        page_range=(31, 31),
        table_kind="balance_sheet",
        title_text="合并资产负债表（续）",
        body_rows=bind_body_rows(
            page_index=31,
            body_lines=["应收账款 2,000,000.00 1,800,000.00"],
        ),
    )

    stitched = stitch_tables([first, second])

    assert len(stitched) == 1
    assert stitched[0].page_range == (30, 31)
    assert [row.label_raw for row in stitched[0].body_rows] == [
        "货币资金",
        "应收账款",
    ]


def test_stitch_tables_does_not_merge_same_page_continued_looking_tables() -> None:
    first = ParsedTable(
        table_id="doc:table:9",
        document_id="doc",
        page_range=(40, 40),
        table_kind="cash_flow_statement",
        title_text="合并现金流量表",
        body_rows=bind_body_rows(
            page_index=40,
            body_lines=["经营活动产生的现金流量净额 1,000.00 900.00"],
        ),
    )
    second = ParsedTable(
        table_id="doc:table:10",
        document_id="doc",
        page_range=(40, 40),
        table_kind="cash_flow_statement",
        title_text="合并现金流量表（续）",
        body_rows=bind_body_rows(
            page_index=40,
            body_lines=["投资活动产生的现金流量净额 2,000.00 1,800.00"],
        ),
    )

    stitched = stitch_tables([first, second])

    assert len(stitched) == 2
    assert [table.table_id for table in stitched] == ["doc:table:9", "doc:table:10"]
