from __future__ import annotations

import re
from pathlib import Path

from financial_report_analysis.ingestion.table_classifier import (
    classify_table_kind,
)
from financial_report_analysis.ingestion.table_header_parser import (
    detect_table_currency,
    detect_table_unit,
    parse_header_rows,
)
from financial_report_analysis.ingestion.table_source import PdfTableSource, RawTableBlock
from financial_report_analysis.ingestion.table_stitcher import bind_body_rows, stitch_tables
from financial_report_analysis.models import PageTextBlock, ParsedTable
from financial_report_analysis.models.table import ParsedColumn


class PdfTableStructureAdapter:
    def __init__(self, *, table_source: PdfTableSource | None = None) -> None:
        self._table_source = table_source or PdfTableSource()

    def extract_tables(
        self,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
        market: str | None,
    ) -> list[ParsedTable]:
        raw_blocks = self._table_source.extract_raw_table_blocks(
            pdf_path=pdf_path,
            pdf_url=pdf_url,
        )
        parsed_tables = [
            self._build_parsed_table(
                block=block,
                market=market,
                document_id=self._document_id(pdf_path, pdf_url),
                table_index=index,
            )
            for index, block in enumerate(raw_blocks, start=1)
        ]
        return stitch_tables([table for table in parsed_tables if table is not None])

    def _build_parsed_table(
        self,
        *,
        block: RawTableBlock,
        market: str | None,
        document_id: str,
        table_index: int,
    ) -> ParsedTable | None:
        title_text = self._infer_table_title(block, market=market)
        table_kind = classify_table_kind(title_text, market=market)
        if table_kind == "unknown":
            return None

        header_rows = self._select_header_rows(block.rows)
        body_rows = block.rows[len(header_rows) :]
        body_lines = [" ".join(cell for cell in row if cell).strip() for row in body_rows]
        local_context = "\n".join(
            line
            for line in [
                title_text.strip(),
                *[
                    " ".join(cell for cell in row if cell).strip()
                    for row in header_rows
                ],
                *body_lines,
            ]
            if line
        )

        return ParsedTable(
            table_id=f"{document_id}:parsed-table:{table_index}",
            document_id=document_id,
            page_range=block.page_range,
            table_kind=table_kind,
            title_text=title_text,
            header_rows=header_rows,
            body_rows=bind_body_rows(
                page_index=block.page_index,
                body_lines=[line for line in body_lines if line],
            ),
            table_unit=detect_table_unit(local_context),
            table_currency=detect_table_currency(local_context, market=market),
            period_columns=self._parse_period_columns(
                title_text=title_text,
                header_rows=header_rows,
                market=market,
                rows=block.rows,
            ),
            comparison_columns=[],
            source_blocks=[
                PageTextBlock(
                    page_index=block.page_index,
                    lines=block.rows and [" ".join(cell for cell in row if cell).strip() for row in block.rows] or [],
                    raw_text="\n".join(block.rows and [" ".join(cell for cell in row if cell).strip() for row in block.rows] or []),
                )
            ],
        )

    def _infer_table_title(self, block: RawTableBlock, *, market: str | None) -> str:
        page_text = re.sub(r"\s+", " ", block.page_text).lower()
        candidates = self._TITLE_PATTERNS_BY_MARKET.get(market or "", self._TITLE_PATTERNS)
        for _title, patterns in candidates:
            if any(re.search(pattern, page_text, re.IGNORECASE) for pattern in patterns):
                return block.page_text.strip() or " ".join(
                    cell for row in block.rows for cell in row if cell
                )

        for row in block.rows[:2]:
            row_text = re.sub(r"\s+", " ", " ".join(cell for cell in row if cell)).lower()
            for _title, patterns in self._TITLE_PATTERNS:
                if any(re.search(pattern, row_text, re.IGNORECASE) for pattern in patterns):
                    return " ".join(cell for cell in row if cell)

        return block.rows[0][0] if block.rows and block.rows[0] else block.page_text

    @staticmethod
    def _select_header_rows(rows: list[list[str]]) -> list[list[str]]:
        for index, row in enumerate(rows):
            if PdfTableStructureAdapter._looks_like_header_row(row):
                return [row]
        return rows[:1]

    @staticmethod
    def _looks_like_header_row(row: list[str]) -> bool:
        non_empty = [cell for cell in row if cell.strip()]
        if len(non_empty) < 2:
            return False
        joined = " ".join(non_empty)
        return bool(
            re.search(r"20\d{2}", joined)
            or "年度" in joined
            or "months ended" in joined.lower()
            or "month ended" in joined.lower()
        )

    def _parse_period_columns(
        self,
        *,
        title_text: str,
        header_rows: list[list[str]],
        market: str | None,
        rows: list[list[str]],
    ) -> list[ParsedColumn]:
        parsed_columns = parse_header_rows(
            title_text=title_text,
            header_rows=header_rows,
            market=market,
        )
        if parsed_columns or market != "HK":
            return parsed_columns
        return self._fallback_hk_period_columns(rows)

    @staticmethod
    def _fallback_hk_period_columns(rows: list[list[str]]) -> list[ParsedColumn]:
        columns: list[ParsedColumn] = []
        seen_period_ids: set[str] = set()
        for row in rows[:2]:
            for column_index, cell in enumerate(row):
                period_id = PdfTableStructureAdapter._hk_period_id_from_date(cell)
                if period_id is None or period_id in seen_period_ids:
                    continue
                seen_period_ids.add(period_id)
                columns.append(
                    ParsedColumn(
                        column_id=f"column-{column_index}",
                        column_index=column_index,
                        header_text=cell,
                        period_id=period_id,
                        period_scope="duration",
                        comparison_axis="current" if not columns else "prior",
                        is_current=not columns,
                        is_comparison=bool(columns),
                    )
                )
        return columns

    @staticmethod
    def _hk_period_id_from_date(raw_text: str) -> str | None:
        match = re.search(r"(\d{1,2})/(\d{1,2})/(20\d{2})", raw_text)
        if match is None:
            return None
        month = int(match.group(1))
        day = int(match.group(2))
        year = match.group(3)
        quarter = {
            (3, 31): "Q1",
            (6, 30): "Q2",
            (9, 30): "Q3",
            (12, 31): "Q4",
        }.get((month, day))
        if quarter is None:
            return None
        return f"{year}{quarter}"

    @staticmethod
    def _document_id(pdf_path: str | None, pdf_url: str | None) -> str:
        if pdf_path:
            return str(Path(pdf_path))
        if pdf_url:
            return pdf_url
        return "unknown-document"

    _TITLE_PATTERNS = (
        (
            "income_statement",
            (
                r"利润表",
                r"损益表",
                r"income statement",
                r"statements of income",
                r"statement of income",
                r"profit or loss",
            ),
        ),
        ("balance_sheet", (r"资产负债表", r"financial position", r"balance sheet")),
        ("cash_flow_statement", (r"现金流量表", r"cash flows", r"cash flow")),
    )

    _TITLE_PATTERNS_BY_MARKET = {
        "CN": _TITLE_PATTERNS,
        "HK": (
            (
                "income_statement",
                (
                    r"statements of income",
                    r"statement of income",
                    r"profit or loss",
                    r"income statement",
                ),
            ),
            ("balance_sheet", (r"financial position", r"balance sheet")),
            ("cash_flow_statement", (r"cash flows", r"cash flow")),
        ),
    }
