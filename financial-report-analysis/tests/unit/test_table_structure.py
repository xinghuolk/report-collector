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
        page_text="其他表 币种：美元 单位：百万元",
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
