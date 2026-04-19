from __future__ import annotations

import re

from financial_report_analysis.models.table import ParsedColumn

_CN_ANNUAL_HEADER_RE = re.compile(
    r"(20\d{2})(?:\s*年)?(?:\s*\d{1,2}月\s*\d{1,2}日)?\s*(?:止)?\s*年度"
)
_HK_QUARTER_HEADER_RE = re.compile(
    r"three\s+months\s+ended\s+(\d{1,2})\s+([a-z]+)\s+(20\d{2})",
    re.IGNORECASE,
)
_HK_ANNUAL_HEADER_RE = re.compile(
    r"(\d{1,2})\s+([a-z]+)\s+(20\d{2})",
    re.IGNORECASE,
)
_CURRENCY_PATTERN = re.compile(r"币种[:：]\s*(\S+)")
_UNIT_PATTERN = re.compile(r"单位[:：]\s*(\S+)")


def parse_header_rows(
    *,
    title_text: str,
    header_rows: list[list[str]],
    market: str | None,
) -> list[ParsedColumn]:
    columns: list[ParsedColumn] = []
    max_columns = max((len(row) for row in header_rows), default=0)

    for column_index in range(max_columns):
        header_text = ""
        for row in header_rows:
            if column_index >= len(row):
                continue
            candidate_text = _normalize_header_text(row[column_index])
            if candidate_text:
                header_text = candidate_text
                break

        if not header_text:
            continue

        period_id, value_time_shape = _parse_period_from_header(
            header_text,
            title_text=title_text,
            market=market,
        )
        if period_id is None:
            continue

        is_current = not columns
        columns.append(
            ParsedColumn(
                column_id=f"column-{column_index}",
                column_index=column_index,
                header_text=header_text,
                period_id=period_id,
                value_time_shape=value_time_shape,
                comparison_axis="current" if is_current else "prior",
                is_current=is_current,
                is_comparison=not is_current,
            )
        )

    return columns


def detect_table_currency(local_context: str, *, market: str | None) -> str:
    text = local_context.strip()
    upper_text = text.upper()

    currency_match = _CURRENCY_PATTERN.search(text)
    if currency_match is not None:
        currency = currency_match.group(1)
        if currency in {"人民币", "RMB", "CNY"}:
            return "CNY"
        if currency in {"港元", "HKD"}:
            return "HKD"
        if currency in {"美元", "USD"}:
            return "USD"

    if "币种：人民币" in text or "币种:人民币" in text:
        return "CNY"
    if "币种：港元" in text or "币种:港元" in text:
        return "HKD"
    if "币种：美元" in text or "币种:美元" in text:
        return "USD"
    if "HK$" in text or "HKD" in upper_text or "港元" in text:
        return "HKD"
    if "US$" in text or "USD" in upper_text or "美元" in text:
        return "USD"
    if "RMB" in upper_text or "CNY" in upper_text or "人民币" in text:
        return "CNY"
    if market == "HK":
        return "HKD"
    if market == "US":
        return "USD"
    return "CNY"


def detect_table_unit(local_context: str) -> str | None:
    text = local_context.strip()
    unit_match = _UNIT_PATTERN.search(text)
    if unit_match is not None:
        return unit_match.group(1)

    if "万元" in text:
        return "万元"
    if "千元" in text:
        return "千元"
    if "百万元" in text:
        return "百万元"
    if "亿元" in text:
        return "亿元"
    return None


def _parse_period_from_header(
    header_text: str,
    *,
    title_text: str,
    market: str | None,
) -> tuple[str | None, str | None]:
    if market == "CN" or "年度" in header_text or "年报" in title_text:
        annual_match = _CN_ANNUAL_HEADER_RE.search(header_text)
        if annual_match is not None:
            return f"{annual_match.group(1)}FY", "duration"

    if market == "HK" or "Three months ended" in header_text:
        quarter_match = _HK_QUARTER_HEADER_RE.search(header_text)
        if quarter_match is not None:
            day = int(quarter_match.group(1))
            month = quarter_match.group(2).lower()
            year = quarter_match.group(3)
            quarter = _hk_quarter_from_end_date(day, month)
            if quarter is not None:
                return f"{year}{quarter}", "duration"

    if market == "HK":
        annual_match = _HK_ANNUAL_HEADER_RE.search(header_text)
        if annual_match is not None:
            day = int(annual_match.group(1))
            month = annual_match.group(2).lower()
            year = annual_match.group(3)
            if day == 31 and month == "december":
                value_time_shape = (
                    "point"
                    if "balance sheet" in title_text.casefold()
                    or "financial position" in title_text.casefold()
                    else "duration"
                )
                return f"{year}FY", value_time_shape

    return None, None


def _normalize_header_text(raw_text: str) -> str:
    return re.sub(r"\s+", " ", raw_text).strip()


def _hk_quarter_from_end_date(day: int, month: str) -> str | None:
    if month == "march" and day == 31:
        return "Q1"
    if month == "june" and day == 30:
        return "Q2"
    if month == "september" and day == 30:
        return "Q3"
    if month == "december" and day == 31:
        return "Q4"
    return None
