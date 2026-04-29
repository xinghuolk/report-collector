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
from financial_report_analysis.models import PageTextBlock, ParsedCell, ParsedRow, ParsedTable
from financial_report_analysis.models.table import ParsedColumn

_NUMERIC_CELL_PATTERN = re.compile(
    r"(?<![\w.])(?:-?\d{1,3}(?:,\d{3})+|-?\d+)(?:\.\d+)?"
)
_HK_ANNUAL_DATE_PATTERN = re.compile(
    r"\d{1,2}\s+[A-Za-z]+\s+20\d{2}",
    re.IGNORECASE,
)
_CN_POINT_IN_TIME_DATE_PATTERN = re.compile(
    r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
)
_DUAL_CURRENCY_NUMERIC_PATTERN = re.compile(
    r"(?<![\w.])\(-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)"
    r"|(?<![\w.(])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
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
            main_statement_kind = self._main_statement_kind_from_title(title_text)
            if main_statement_kind is not None:
                table_kind = main_statement_kind
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

        parsed_body_rows = (
            self._bind_dual_currency_body_rows(
                page_index=block.page_index,
                rows=body_rows,
            )
            if semantic_ambiguity_reason == "dual_currency_statement_block"
            else bind_body_rows(
                page_index=block.page_index,
                body_lines=[line for line in body_lines if line],
            )
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
            body_rows=parsed_body_rows,
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
        if table_kind not in {"income_statement", "balance_sheet", "cash_flow_statement"}:
            return block.rows, None

        recovered_rows = self._recover_dual_currency_rows_from_page_text(
            page_text=block.page_text,
            title_text=title_text,
            table_kind=table_kind,
        )
        if recovered_rows:
            return recovered_rows, "dual_currency_statement_block"

        if self._looks_like_header_only_statement_block(block.rows):
            recovered_rows = self._recover_rows_from_page_text(
                page_text=block.page_text,
                title_text=title_text,
            )
            if recovered_rows:
                return recovered_rows, "header_only_statement_block"

        if not self._looks_like_numeric_only_statement_block(block.rows):
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
    def _looks_like_header_only_statement_block(rows: list[list[str]]) -> bool:
        non_empty_rows = [row for row in rows if any(cell.strip() for cell in row)]
        if len(non_empty_rows) != 1:
            return False
        non_empty_cells = [cell.strip() for cell in non_empty_rows[0] if cell.strip()]
        if len(non_empty_cells) < 2:
            return False
        return all(re.fullmatch(r"20\d{2}", cell) for cell in non_empty_cells)

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
        saw_header = False
        for line in lines[start_index:]:
            if PdfTableStructureAdapter._is_statement_footer_line(line):
                break
            if line.startswith("Prepared by:") or line.startswith("Unit:") or line == title_text:
                continue
            if line.startswith("(in ") or line.startswith("(In "):
                continue
            if line.startswith("II. ") or line.startswith("I. "):
                continue
            header_row = PdfTableStructureAdapter._recover_bare_year_header_row(line)
            if header_row is not None:
                rows.append(header_row)
                saw_header = True
                continue
            if not saw_header and PdfTableStructureAdapter._looks_like_statement_period_context(
                line
            ):
                continue
            recovered_row = PdfTableStructureAdapter._recover_structured_row(line)
            if (
                not saw_header
                and len(recovered_row) >= 2
                and any(_HK_ANNUAL_DATE_PATTERN.search(cell) for cell in recovered_row[1:])
            ):
                rows.append(recovered_row)
                saw_header = True
                continue
            if recovered_row and (
                saw_header or PdfTableStructureAdapter._row_has_numeric_value(recovered_row)
            ):
                rows.append(recovered_row)
        return rows

    @staticmethod
    def _recover_dual_currency_rows_from_page_text(
        *,
        page_text: str,
        title_text: str,
        table_kind: str,
    ) -> list[list[str]]:
        if table_kind not in {
            "income_statement",
            "balance_sheet",
            "cash_flow_statement",
        }:
            return []
        if not PdfTableStructureAdapter._is_main_statement_title(title_text):
            return []
        if not PdfTableStructureAdapter._has_dual_currency_million_context(page_text):
            return []

        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        unit_index = next(
            (
                index
                for index, line in enumerate(lines)
                if PdfTableStructureAdapter._has_dual_currency_million_context(line)
            ),
            -1,
        )
        if unit_index < 0:
            return []

        header_row = PdfTableStructureAdapter._recover_dual_currency_header_row(
            lines=lines,
            unit_index=unit_index,
        )
        if header_row is None:
            return []

        value_count = len(header_row) - 1
        body_rows: list[list[str]] = []
        for line in lines[unit_index + 1 :]:
            if PdfTableStructureAdapter._is_statement_footer_line(line):
                break
            recovered_row = PdfTableStructureAdapter._recover_dual_currency_body_row(
                line=line,
                value_count=value_count,
            )
            if recovered_row is not None:
                body_rows.append(recovered_row)

        if not body_rows:
            return []
        return [header_row, *body_rows]

    @staticmethod
    def _recover_dual_currency_header_row(
        *,
        lines: list[str],
        unit_index: int,
    ) -> list[str] | None:
        unit_line = lines[unit_index]
        hk_value_count = len(
            re.findall(r"\bHK\$\s*million[s]?\b", unit_line, re.IGNORECASE)
        )
        for line in reversed(lines[:unit_index]):
            years_source = line.split("#", maxsplit=1)[1] if "#" in line else line
            years = re.findall(r"\b20\d{2}\b", years_source)
            if len(years) >= 2:
                if hk_value_count > 0 and len(years) > hk_value_count:
                    years = years[-hk_value_count:]
                return ["", *years]
        return None

    @staticmethod
    def _recover_dual_currency_body_row(
        *,
        line: str,
        value_count: int,
    ) -> list[str] | None:
        matches = list(_DUAL_CURRENCY_NUMERIC_PATTERN.finditer(line))
        if len(matches) < value_count + 1:
            return None
        if line[: matches[0].start()].strip():
            return None
        if line[matches[-1].end() :].strip():
            return None

        trailing_matches = PdfTableStructureAdapter._trailing_numeric_matches(
            line=line,
            matches=matches,
        )
        if len(trailing_matches) > value_count:
            trailing_matches = trailing_matches[-value_count:]
        if len(trailing_matches) != value_count:
            return None

        label_raw = line[matches[0].end() : trailing_matches[0].start()].strip()
        label_raw = re.sub(r"\s+\d+[A-Za-z]?$", "", label_raw).strip()
        if not label_raw:
            return None

        return [label_raw, *(match.group(0) for match in trailing_matches)]

    @staticmethod
    def _trailing_numeric_matches(
        *,
        line: str,
        matches: list[re.Match[str]],
    ) -> list[re.Match[str]]:
        trailing_start = len(matches) - 1
        for index in range(len(matches) - 2, -1, -1):
            between_matches = line[matches[index].end() : matches[index + 1].start()]
            if between_matches.strip():
                break
            trailing_start = index
        return matches[trailing_start:]

    @staticmethod
    def _bind_dual_currency_body_rows(
        *,
        page_index: int,
        rows: list[list[str]],
    ) -> list[ParsedRow]:
        parsed_rows: list[ParsedRow] = []
        for row_index, row in enumerate(rows):
            if not row or not row[0].strip():
                continue
            parsed_rows.append(
                ParsedRow(
                    row_id=f"row-{page_index}-{row_index}",
                    row_index=row_index,
                    label_raw=row[0].strip(),
                    normalized_label_hint=None,
                    value_cells=[
                        ParsedCell(
                            row_index=row_index,
                            column_index=column_index,
                            text_raw=value.strip(),
                            numeric_value=PdfTableStructureAdapter._numeric_value_from_text(
                                value
                            ),
                            bbox=None,
                            page_index=page_index,
                        )
                        for column_index, value in enumerate(row[1:], start=1)
                        if value.strip()
                    ],
                    indent_level=0,
                    is_subtotal=False,
                    is_total=False,
                )
            )
        return parsed_rows

    @staticmethod
    def _numeric_value_from_text(raw_text: str) -> float:
        text = raw_text.strip().replace(",", "")
        if text.startswith("(") and text.endswith(")"):
            text = f"-{text[1:-1]}"
        return float(text)

    @staticmethod
    def _recover_structured_row(line: str) -> list[str]:
        annual_dates = _HK_ANNUAL_DATE_PATTERN.findall(line)
        if annual_dates:
            prefix = line[: line.find(annual_dates[0])].strip()
            if prefix:
                return [prefix, *annual_dates]

        normalized_line = re.sub(r"\$\s*", "", line)
        normalized_line = re.sub(
            r"\((\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\)",
            lambda match: f"-{match.group(1)}"
            + (f".{match.group(2)}" if match.group(2) else ""),
            normalized_line,
        )
        matches = list(_NUMERIC_CELL_PATTERN.finditer(normalized_line))
        if not matches:
            return [line]

        label_raw = normalized_line[: matches[0].start()].strip()
        if not label_raw:
            return [line]
        return [label_raw, *(match.group(0) for match in matches)]

    @staticmethod
    def _recover_bare_year_header_row(line: str) -> list[str] | None:
        cells = re.findall(r"\b20\d{2}\b", line)
        if len(cells) < 2:
            return None
        without_years = re.sub(r"\b20\d{2}\b", "", line)
        if without_years.strip():
            return None
        return ["", *cells]

    @staticmethod
    def _looks_like_statement_period_context(line: str) -> bool:
        lowered = line.casefold()
        return (
            "years ended" in lowered
            or "year ended" in lowered
            or re.match(r"^december\s+31,\s+20\d{2}", lowered) is not None
        )

    @staticmethod
    def _is_statement_footer_line(line: str) -> bool:
        lowered = line.casefold()
        return (
            re.fullmatch(r"\d+", line) is not None
            or ("annual report" in lowered and not any(char.isdigit() for char in line))
            or line.startswith("See accompanying Notes")
        )

    @staticmethod
    def _has_dual_currency_million_context(text: str) -> bool:
        return bool(
            re.search(r"\bUS\$\s*million[s]?\b", text, re.IGNORECASE)
            and re.search(r"\bHK\$\s*million[s]?\b", text, re.IGNORECASE)
        )

    @staticmethod
    def _is_main_statement_title(title_text: str) -> bool:
        return PdfTableStructureAdapter._main_statement_kind_from_title(title_text) is not None

    @staticmethod
    def _main_statement_kind_from_title(title_text: str) -> str | None:
        normalized = re.sub(r"\s+", " ", title_text).strip().casefold()
        if re.search(r"\bincome statement\b", normalized) or re.search(
            r"\bstatements? of income\b",
            normalized,
        ):
            return "income_statement"
        if (
            "statement of financial position" in normalized
            or "balance sheet" in normalized
        ):
            return "balance_sheet"
        if re.search(r"\bstatements? of cash flows?\b", normalized) or re.search(
            r"\bcash flow statement\b",
            normalized,
        ):
            return "cash_flow_statement"
        return None

    @staticmethod
    def _row_has_numeric_value(row: list[str]) -> bool:
        return any(
            re.fullmatch(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", cell)
            for cell in row[1:]
        )

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
        for line in block.page_text.splitlines():
            stripped_line = line.strip()
            if stripped_line.startswith("(in ") or stripped_line.startswith("(In "):
                add_segment(stripped_line)
        add_segment(title_text)
        for row in header_rows:
            add_segment(" ".join(cell for cell in row if cell).strip())
        for line in body_lines:
            add_segment(line)
        return "\n".join(segments)

    @staticmethod
    def _guess_statement_scope(*, title_text: str, local_context: str) -> str:
        title_haystack = title_text.casefold()
        parent_patterns = (
            r"company statement of financial position",
            r"separate statement of financial position",
            r"statement of financial position of the company",
            r"separate statement",
            r"company statement",
        )
        if "母公司" in title_text or any(
            re.search(pattern, title_haystack) for pattern in parent_patterns
        ):
            return "parent_only"
        if "consolidated" in title_haystack or "合并" in title_text:
            return "consolidated"

        local_haystack = local_context.casefold()
        if "母公司" in local_context or re.search(
            r"(^|\n)\s*(company|separate) statement of\b",
            local_haystack,
        ) or re.search(
            r"(^|\n)\s*statement of .* of the company\b",
            local_haystack,
        ):
            return "parent_only"
        if re.search(
            r"(^|\n)\s*(?:condensed\s+)?consolidated statement of\b",
            local_haystack,
        ) or re.search(r"(^|\n)\s*合并", local_context):
            return "consolidated"
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
        fallback_annual_columns = self._fallback_hk_annual_statement_period_columns(
            title_text=title_text,
            table_kind=table_kind,
            header_rows=header_rows,
        )
        if fallback_annual_columns:
            return fallback_annual_columns
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
    def _fallback_hk_annual_statement_period_columns(
        *,
        title_text: str,
        table_kind: str,
        header_rows: list[list[str]],
    ) -> list[ParsedColumn]:
        if not PdfTableStructureAdapter._is_main_statement_title(title_text):
            return []
        value_time_shape = "point" if table_kind == "balance_sheet" else "duration"
        columns: list[ParsedColumn] = []
        for row in header_rows:
            for column_index, cell in enumerate(row):
                if not re.fullmatch(r"20\d{2}", cell.strip()):
                    continue
                columns.append(
                    ParsedColumn(
                        column_id=f"column-{column_index}",
                        column_index=column_index,
                        header_text=cell,
                        period_id=f"{cell}FY",
                        value_time_shape=value_time_shape,
                        comparison_axis="current" if not columns else "prior",
                        is_current=not columns,
                        is_comparison=bool(columns),
                    )
                )
            if columns:
                return columns
        return []

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
