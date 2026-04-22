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

_NUMERIC_CELL_PATTERN = re.compile(
    r"(?<![\w.])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
)
_HK_ANNUAL_DATE_PATTERN = re.compile(
    r"\d{1,2}\s+[A-Za-z]+\s+20\d{2}",
    re.IGNORECASE,
)
_CN_POINT_IN_TIME_DATE_PATTERN = re.compile(
    r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
)


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
            continuation_title = self._infer_statement_continuation_title(
                block=block,
                market=market,
            )
            if continuation_title is not None:
                title_text = continuation_title
                table_kind = classify_table_kind(title_text, market=market)
        if table_kind == "unknown":
            return None

        recovered_rows, semantic_ambiguity_reason = self._recover_rows_for_statement_block(
            block=block,
            title_text=title_text,
            table_kind=table_kind,
        )
        header_rows = self._select_header_rows(recovered_rows)
        body_rows = recovered_rows[len(header_rows) :]
        body_lines = [" ".join(cell for cell in row if cell).strip() for row in body_rows]
        local_context = self._table_local_context(
            block=block,
            title_text=title_text,
            header_rows=header_rows,
            body_lines=body_lines,
        )

        return ParsedTable(
            table_id=f"{document_id}:parsed-table:{table_index}",
            document_id=document_id,
            page_range=block.page_range,
            table_kind=table_kind,
            title_text=title_text,
            statement_scope_guess=self._guess_statement_scope(
                title_text=title_text,
                local_context=local_context,
            ),
            semantic_ambiguity_reason=semantic_ambiguity_reason,
            header_rows=header_rows,
            body_rows=bind_body_rows(
                page_index=block.page_index,
                body_lines=[line for line in body_lines if line],
            ),
            table_unit=detect_table_unit(local_context),
            table_currency=detect_table_currency(local_context, market=market),
            period_columns=self._parse_period_columns(
                title_text=title_text,
                table_kind=table_kind,
                header_rows=header_rows,
                market=market,
                rows=recovered_rows,
            ),
            comparison_columns=[],
            source_blocks=[
                PageTextBlock(
                    page_index=block.page_index,
                    lines=local_context.splitlines(),
                    raw_text=local_context,
                )
            ],
        )

    def _recover_rows_for_statement_block(
        self,
        *,
        block: RawTableBlock,
        title_text: str,
        table_kind: str,
    ) -> tuple[list[list[str]], str | None]:
        if not self._looks_like_numeric_only_statement_block(block.rows):
            return block.rows, None
        if table_kind not in {"income_statement", "balance_sheet", "cash_flow_statement"}:
            return block.rows, None

        recovered_rows = self._recover_rows_from_page_text(
            page_text=block.page_text,
            title_text=title_text,
        )
        if recovered_rows:
            return recovered_rows, "numeric_only_statement_block"
        return block.rows, None

    def _infer_table_title(self, block: RawTableBlock, *, market: str | None) -> str:
        page_text = re.sub(r"\s+", " ", block.page_text).lower()
        candidates = self._TITLE_PATTERNS_BY_MARKET.get(market or "", self._TITLE_PATTERNS)
        for _title, patterns in candidates:
            if any(re.search(pattern, page_text, re.IGNORECASE) for pattern in patterns):
                for row in block.rows:
                    row_text = " ".join(cell for cell in row if cell).strip()
                    normalized_row_text = re.sub(r"\s+", " ", row_text).lower()
                    if any(
                        re.search(pattern, normalized_row_text, re.IGNORECASE)
                        for pattern in patterns
                    ):
                        return row_text
                for line in block.page_text.splitlines():
                    line_text = line.strip()
                    normalized_line_text = re.sub(r"\s+", " ", line_text).lower()
                    if any(
                        re.search(pattern, normalized_line_text, re.IGNORECASE)
                        for pattern in patterns
                    ):
                        return line_text
                return self._first_non_empty_row_text(block) or block.page_text.strip()

        for row in block.rows[:2]:
            row_text = re.sub(r"\s+", " ", " ".join(cell for cell in row if cell)).lower()
            for _title, patterns in self._TITLE_PATTERNS:
                if any(re.search(pattern, row_text, re.IGNORECASE) for pattern in patterns):
                    return " ".join(cell for cell in row if cell)

        return self._first_non_empty_row_text(block) or block.page_text

    @staticmethod
    def _first_non_empty_row_text(block: RawTableBlock) -> str:
        for row in block.rows:
            row_text = " ".join(cell for cell in row if cell).strip()
            if row_text:
                return row_text
        return ""

    @staticmethod
    def _looks_like_numeric_only_statement_block(rows: list[list[str]]) -> bool:
        non_empty_rows = [row for row in rows if any(cell.strip() for cell in row)]
        if not non_empty_rows:
            return False
        if len(non_empty_rows) < 3:
            return False
        numeric_like_count = 0
        for row in non_empty_rows[:12]:
            if len(row) != 1:
                return False
            cell = row[0].replace(",", "").strip()
            if re.fullmatch(r"-?\d+(?:\.\d+)?", cell):
                numeric_like_count += 1
        return numeric_like_count >= min(len(non_empty_rows[:12]), 3)

    @staticmethod
    def _recover_rows_from_page_text(*, page_text: str, title_text: str) -> list[list[str]]:
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        if not lines:
            return []

        title_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.casefold() == title_text.casefold()
            ),
            -1,
        )
        start_index = title_index + 1 if title_index >= 0 else 0

        rows: list[list[str]] = []
        footer_pattern = re.compile(r"^\d+$")
        for line in lines[start_index:]:
            lowered = line.casefold()
            if footer_pattern.fullmatch(line):
                break
            if "annual report" in lowered and not any(char.isdigit() for char in line):
                break
            if line.startswith("Prepared by:") or line.startswith("Unit:") or line == title_text:
                continue
            if line.startswith("II. ") or line.startswith("I. "):
                continue
            recovered_row = PdfTableStructureAdapter._recover_structured_row(line)
            if recovered_row:
                rows.append(recovered_row)
        return rows

    @staticmethod
    def _recover_structured_row(line: str) -> list[str]:
        annual_dates = _HK_ANNUAL_DATE_PATTERN.findall(line)
        if annual_dates:
            prefix = line[: line.find(annual_dates[0])].strip()
            if prefix:
                return [prefix, *annual_dates]

        matches = list(_NUMERIC_CELL_PATTERN.finditer(line))
        if not matches:
            return [line]

        label_raw = line[: matches[0].start()].strip()
        if not label_raw:
            return [line]
        return [label_raw, *(match.group(0) for match in matches)]

    @staticmethod
    def _table_local_context(
        *,
        block: RawTableBlock,
        title_text: str,
        header_rows: list[list[str]],
        body_lines: list[str],
    ) -> str:
        segments: list[str] = []
        seen: set[str] = set()

        def add_segment(segment: str) -> None:
            cleaned = segment.strip()
            if not cleaned or cleaned in seen:
                return
            seen.add(cleaned)
            segments.append(cleaned)

        for line in block.local_context.splitlines():
            add_segment(line)
        add_segment(title_text)
        for row in header_rows:
            add_segment(" ".join(cell for cell in row if cell).strip())
        for line in body_lines:
            add_segment(line)
        return "\n".join(segments)

    @staticmethod
    def _guess_statement_scope(*, title_text: str, local_context: str) -> str:
        haystack = f"{title_text}\n{local_context}".casefold()
        if "consolidated" in haystack or "合并" in haystack:
            return "consolidated"
        if "parent company" in haystack or "母公司" in haystack:
            return "parent_only"
        return "unknown"

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
        table_kind: str,
        header_rows: list[list[str]],
        market: str | None,
        rows: list[list[str]],
    ) -> list[ParsedColumn]:
        parsed_columns = parse_header_rows(
            title_text=title_text,
            header_rows=header_rows,
            market=market,
        )
        if market == "CN" and table_kind == "balance_sheet":
            if parsed_columns:
                for column in parsed_columns:
                    column.value_time_shape = "point"
                return parsed_columns
            fallback_columns = self._fallback_cn_balance_sheet_period_columns(
                header_rows=header_rows,
            )
            if fallback_columns:
                return fallback_columns
        if parsed_columns or market != "HK":
            return parsed_columns
        return self._fallback_hk_period_columns(rows)

    def _infer_statement_continuation_title(
        self,
        *,
        block: RawTableBlock,
        market: str | None,
    ) -> str | None:
        header_start_index, header_rows = self._select_continuation_header_rows(block.rows)
        if not header_rows:
            return None
        if self._looks_like_numbered_section_heading(
            local_context=block.local_context,
            page_text=block.page_text,
        ) and not self._has_explicit_continuation_marker(
            local_context=block.local_context,
            page_text=block.page_text,
        ):
            return None

        body_rows = block.rows[header_start_index + len(header_rows) :]
        body_text = "\n".join(
            " ".join(cell for cell in row if cell).strip()
            for row in body_rows
            if any(cell.strip() for cell in row)
        )
        if not body_text:
            return None

        table_kind = self._statement_kind_from_continuation_body(body_text)
        if table_kind is None:
            return None

        parsed_columns = parse_header_rows(
            title_text="",
            header_rows=header_rows,
            market=market,
        )
        if not parsed_columns and not (
            market == "CN"
            and table_kind == "balance_sheet"
            and self._fallback_cn_balance_sheet_period_columns(
                header_rows=header_rows,
            )
        ):
            return None

        return self._continuation_title_for_kind(table_kind, market=market)

    @staticmethod
    def _select_continuation_header_rows(
        rows: list[list[str]],
    ) -> tuple[int, list[list[str]]]:
        for index, row in enumerate(rows[:2]):
            if PdfTableStructureAdapter._looks_like_continuation_header_row(row):
                return index, [row]
        return 0, []

    @staticmethod
    def _looks_like_continuation_header_row(row: list[str]) -> bool:
        non_empty = [cell.strip() for cell in row if cell.strip()]
        if len(non_empty) < 3:
            return False

        period_like_cells = sum(
            1
            for cell in non_empty
            if PdfTableStructureAdapter._looks_like_period_header_cell(cell)
        )
        if period_like_cells >= 2:
            return True

        header_marker_cells = sum(
            1
            for cell in non_empty
            if PdfTableStructureAdapter._looks_like_statement_header_marker(cell)
        )
        return period_like_cells >= 1 and header_marker_cells >= 1

    @staticmethod
    def _looks_like_period_header_cell(cell: str) -> bool:
        normalized = re.sub(r"\s+", " ", cell).strip().casefold()
        return bool(
            re.search(r"20\d{2}", normalized)
            or "month ended" in normalized
            or "months ended" in normalized
            or "as at" in normalized
            or "at " in normalized
            or "年度" in normalized
        )

    @staticmethod
    def _looks_like_statement_header_marker(cell: str) -> bool:
        normalized = re.sub(r"\s+", "", cell).casefold()
        return normalized in {"项目", "附注", "item", "items", "note", "notes"}

    @staticmethod
    def _has_explicit_continuation_marker(
        *,
        local_context: str,
        page_text: str,
    ) -> bool:
        candidate_lines = [
            line.strip()
            for line in "\n".join((local_context, page_text)).splitlines()
            if line.strip()
        ]
        marker_pattern = re.compile(r"(（续）|续表|\(continued\)|continued)$", re.IGNORECASE)
        return any(marker_pattern.search(line) for line in candidate_lines[:6])

    @staticmethod
    def _looks_like_numbered_section_heading(
        *,
        local_context: str,
        page_text: str,
    ) -> bool:
        first_line = next(
            (
                line.strip()
                for line in (local_context or page_text).splitlines()
                if line.strip()
            ),
            "",
        )
        return bool(
            re.match(r"^\d+\s*[.、．)]", first_line)
            or re.match(r"^[IVXLCDM]+\.\s+", first_line)
        )

    @staticmethod
    def _continuation_title_for_kind(
        table_kind: str,
        *,
        market: str | None,
    ) -> str | None:
        if market == "CN":
            return {
                "income_statement": "利润表（续）",
                "balance_sheet": "资产负债表（续）",
                "cash_flow_statement": "现金流量表（续）",
            }.get(table_kind)

        return {
            "income_statement": "Statement of Income (continued)",
            "balance_sheet": "Balance Sheet (continued)",
            "cash_flow_statement": "Statement of Cash Flows (continued)",
        }.get(table_kind)

    @staticmethod
    def _statement_kind_from_continuation_body(body_text: str) -> str | None:
        normalized_body = re.sub(r"\s+", "", body_text).casefold()
        if PdfTableStructureAdapter._has_balance_sheet_continuation_signals(
            normalized_body
        ):
            return "balance_sheet"

        income_statement_matches = sum(
            token in normalized_body
            for token in (
                "营业收入",
                "营业成本",
                "净利润",
                "财务费用",
                "其他收益",
                "投资收益",
                "公允价值变动收益",
                "信用减值损失",
                "资产减值损失",
                "basicearningspershare",
                "revenue",
                "financecosts",
                "otherincome",
                "investmentincome",
                "fairvaluegains",
                "creditimpairmentlosses",
                "assetimpairmentlosses",
                "operatingprofit",
                "profitfortheyear",
            )
        )
        if income_statement_matches >= 2:
            return "income_statement"

        cash_flow_matches = sum(
            token in normalized_body
            for token in (
                "经营活动产生的现金流量净额",
                "投资活动产生的现金流量净额",
                "筹资活动产生的现金流量净额",
                "现金及现金等价物净增加额",
                "netcashgeneratedfromoperatingactivities",
                "netcashusedininvestingactivities",
                "netcashgeneratedfromfinancingactivities",
                "cashandcashequivalents",
            )
        )
        if cash_flow_matches >= 2:
            return "cash_flow_statement"

        return None

    @staticmethod
    def _fallback_cn_balance_sheet_period_columns(
        *,
        header_rows: list[list[str]],
    ) -> list[ParsedColumn]:
        columns: list[ParsedColumn] = []
        seen_period_ids: set[str] = set()
        for row in header_rows:
            for column_index, cell in enumerate(row):
                period_id = PdfTableStructureAdapter._cn_balance_sheet_period_id_from_date(
                    cell
                )
                if period_id is None or period_id in seen_period_ids:
                    continue
                seen_period_ids.add(period_id)
                columns.append(
                    ParsedColumn(
                        column_id=f"column-{column_index}",
                        column_index=column_index,
                        header_text=cell,
                        period_id=period_id,
                        value_time_shape="point",
                        comparison_axis="current" if not columns else "prior",
                        is_current=not columns,
                        is_comparison=bool(columns),
                    )
                )
        return columns

    @staticmethod
    def _has_balance_sheet_continuation_signals(normalized_body: str) -> bool:
        tail_markers = (
            "非流动资产合计",
            "资产总计",
            "负债合计",
            "totalassets",
            "totalliabilities",
        )
        next_section_markers = (
            "流动负债",
            "非流动负债",
            "所有者权益",
            "股东权益",
            "currentliabilities",
            "non-currentliabilities",
            "equityattributable",
        )
        return any(token in normalized_body for token in tail_markers) and any(
            token in normalized_body for token in next_section_markers
        )

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
                        value_time_shape="duration",
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
    def _cn_balance_sheet_period_id_from_date(raw_text: str) -> str | None:
        match = _CN_POINT_IN_TIME_DATE_PATTERN.search(raw_text)
        if match is None:
            return None
        month = int(match.group(2))
        day = int(match.group(3))
        if (month, day) != (12, 31):
            return None
        return f"{match.group(1)}FY"

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
