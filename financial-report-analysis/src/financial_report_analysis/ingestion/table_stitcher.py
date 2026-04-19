from __future__ import annotations

from dataclasses import replace
import re

from financial_report_analysis.models import ParsedCell, ParsedRow, ParsedTable

_NUMBER_PATTERN = re.compile(
    r"(?<!\w)-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
)
_CONTINUABLE_TABLE_KINDS = {
    "income_statement",
    "balance_sheet",
    "cash_flow_statement",
}


def should_merge_tables(previous: ParsedTable, current: ParsedTable) -> bool:
    if previous.table_kind != current.table_kind:
        return False
    if previous.table_kind not in _CONTINUABLE_TABLE_KINDS:
        return False

    page_gap = current.page_range[0] - previous.page_range[1]
    if page_gap != 1:
        return False

    return _is_continuation_title(current.title_text)


def bind_body_rows(*, page_index: int, body_lines: list[str]) -> list[ParsedRow]:
    rows: list[ParsedRow] = []
    for row_index, raw_line in enumerate(body_lines):
        line = raw_line.strip()
        if not line:
            continue

        matches = list(_NUMBER_PATTERN.finditer(line))
        if matches:
            label_raw = line[: matches[0].start()].strip()
        else:
            label_raw = line

        value_cells = [
            ParsedCell(
                row_index=row_index,
                column_index=column_index,
                text_raw=match.group(0),
                numeric_value=float(match.group(0).replace(",", "")),
                bbox=None,
                page_index=page_index,
            )
            for column_index, match in enumerate(matches, start=1)
        ]

        rows.append(
            ParsedRow(
                row_id=f"row-{page_index}-{row_index}",
                row_index=row_index,
                label_raw=label_raw,
                normalized_label_hint=None,
                value_cells=value_cells,
                indent_level=0,
                is_subtotal=False,
                is_total=False,
            )
        )
    return rows


def stitch_tables(tables: list[ParsedTable]) -> list[ParsedTable]:
    stitched_tables: list[ParsedTable] = []
    for table in tables:
        if stitched_tables and should_merge_tables(stitched_tables[-1], table):
            stitched_tables[-1] = _merge_tables(stitched_tables[-1], table)
            continue
        stitched_tables.append(table)
    return stitched_tables


def _merge_tables(previous: ParsedTable, current: ParsedTable) -> ParsedTable:
    return replace(
        previous,
        page_range=(previous.page_range[0], current.page_range[1]),
        body_rows=[*previous.body_rows, *current.body_rows],
        source_blocks=[*previous.source_blocks, *current.source_blocks],
    )


def _is_continuation_title(title_text: str) -> bool:
    normalized = re.sub(r"\s+", "", title_text).lower()
    return "continued" in normalized or "续" in normalized
