from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from financial_report_analysis.semantic_fallback import (
    DisclosureLocatorRequest,
    SemanticFallbackService,
)


_MAX_DISCLOSURE_LOCATOR_CALLS_PER_DOCUMENT = 3
_TARGET_DISCLOSURE_METRIC_IDS: tuple[str, ...] = (
    "accounts_receiv",
    "acct_payable",
    "contract_liab",
)
_ASSET_NOTE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "surface_patterns": (
            re.compile(
                r"\bcontract\s+assets\b[^\n]{0,120}\b20\d{2}\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bother\s+non[-\s]+current\s+assets\b[^\n]{0,120}\b20\d{2}\b",
                re.IGNORECASE,
            ),
        ),
        "metrics": (
            {
                "metric_id": "contract_assets",
                "label": "Contract assets",
                "row_pattern": re.compile(
                    r"(?mi)^\s*contract\s+assets\b(?:\s*\([^)]+\))?\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
            {
                "metric_id": "other_non_current_assets",
                "label": "Other non-current assets",
                "row_pattern": re.compile(
                    r"(?mi)^\s*other\s+non[-\s]+current\s+assets\b(?:\s*\([^)]+\))?\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
        ),
    },
)

_DEBT_NOTE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "surface_patterns": (
            re.compile(
                r"\b(?:borrowings|credit\s+facilities\s+and\s+short-term\s+borrowings)\b[^\n]{0,120}\b20\d{2}\b[^\n]{0,40}\b20\d{2}\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:short-term\s+borrowings|long-term\s+borrowings|bonds?\s+payable|current\s+portion\s+of\s+long-term\s+(?:debt|borrowings))\b[^\n]{0,120}\b20\d{2}\b[^\n]{0,40}\b20\d{2}\b",
                re.IGNORECASE,
            ),
        ),
        "metrics": (
            {
                "metric_id": "st_borr",
                "label": "Short-term borrowings",
                "row_pattern": re.compile(
                    r"(?mi)^\s*(?:short[-\s]+term(?:\s+bank)?\s+borrowings)\b(?:\s*\([^)]+\))?\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
            {
                "metric_id": "lt_borr",
                "label": "Long-term borrowings",
                "row_pattern": re.compile(
                    r"(?mi)^\s*long[-\s]+term borrowings\b(?:\s*\([^)]+\))?\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
            {
                "metric_id": "bond_payable",
                "label": "Bonds payable",
                "row_pattern": re.compile(
                    r"(?mi)^\s*bonds?\s+payable\b(?:\s*\([^)]+\))?\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
            {
                "metric_id": "non_cur_liab_due_1y",
                "label": "Current portion of long-term debt",
                "row_pattern": re.compile(
                    r"(?mi)^\s*(?:current\s+portion\s+of\s+long[-\s]+term\s+(?:debt|borrowings)|current\s+portion\s+due\s+within\s+one\s+year)\b(?:\s*\([^)]+\))?\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
        ),
        "continuation_patterns": (
            re.compile(
                r"(?mi)^\s*(?:short[-\s]+term(?:\s+bank)?\s+borrowings|long[-\s]+term borrowings|bonds?\s+payable|current\s+portion\s+of\s+long[-\s]+term\s+(?:debt|borrowings)|current\s+portion\s+due\s+within\s+one\s+year)\b"
            ),
        ),
    },
)


_NOTE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "surface_patterns": (
            re.compile(
                r"\baccounts\s+receivable,?\s+net\s+20\d{2}\s+20\d{2}\b",
                re.IGNORECASE,
            ),
        ),
        "metrics": (
            {
                "metric_id": "accounts_receiv",
                "label": "Accounts receivable",
                "row_pattern": re.compile(
                    r"(?mi)^\s*accounts\s+receivable,?\s+net\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
        ),
    },
    {
        "surface_patterns": (
            re.compile(
                r"\baccounts\s+payable\s+and\s+other\s+current\s+liabilities\s+20\d{2}\s+20\d{2}\b",
                re.IGNORECASE,
            ),
        ),
        "metrics": (
            {
                "metric_id": "acct_payable",
                "label": "Accounts payable",
                "row_pattern": re.compile(
                    r"(?mi)^\s*accounts\s+payable\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
            {
                "metric_id": "contract_liab",
                "label": "Contract liabilities",
                "row_pattern": re.compile(
                    r"(?mi)^\s*contract\s+liabilities\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
            {
                "metric_id": "notes_receiv",
                "label": "Notes receivable",
                "row_pattern": re.compile(
                    r"(?mi)^\s*notes\s+receivable\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
            {
                "metric_id": "notes_payable",
                "label": "Notes payable",
                "row_pattern": re.compile(
                    r"(?mi)^\s*notes\s+payable\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
        ),
    },
    {
        "surface_patterns": (
            re.compile(
                r"\b(?:payments\s+received\s+in\s+advance|advances\s+from\s+customers)\b",
                re.IGNORECASE,
            ),
        ),
        "metrics": (
            {
                "metric_id": "adv_receipts",
                "label": "Payments received in advance",
                "row_pattern": re.compile(
                    r"(?mi)^\s*(?:payments\s+received\s+in\s+advance|advances\s+from\s+customers)\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
        ),
    },
)

_CASH_HEALTH_RESTRICTED_CASH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)\brestricted\s+cash(?:\s+and\s+cash\s+equivalents)?\b[^0-9\n]{0,40}(?:HK\$|US\$|RMB|CNY|￥|\$)\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)"
    ),
    re.compile(
        r"(?i)\brestricted\s+monetary\s+funds\b[^0-9\n]{0,40}(?:HK\$|US\$|RMB|CNY|￥|\$)\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)"
    ),
    re.compile(
        r"受限货币资金[^0-9\n]{0,40}(?:人民币|RMB|CNY|HK\$|US\$|￥|元)\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)"
    ),
    re.compile(
        r"已抵押存款[^\n]{0,40}(?:受限|restricted|受限货币资金|restricted\s+cash)[^0-9\n]{0,40}(?:HK\$|US\$|RMB|CNY|￥|\$)\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)",
        re.IGNORECASE,
    ),
)

_CASH_HEALTH_INTEREST_PAID_LABEL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(cash paid for interest)\b"),
    re.compile(r"(支付的利息)"),
)

_CASH_HEALTH_TIME_DEPOSITS_LABEL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(time deposits)\b"),
    re.compile(r"(?i)\b(term deposits)\b"),
    re.compile(r"(?i)\b(wealth management products)\b"),
    re.compile(r"(?i)\b(long-term bank deposits and notes)\b"),
    re.compile(r"(定期存款)"),
    re.compile(r"(结构性存款)"),
    re.compile(r"(理财产品)"),
)

_CASH_HEALTH_ROW_VALUE_PATTERN = re.compile(r"(?<!\d)(\d[\d,]*(?:\.\d+)?)(?!\d)")
_CASH_HEALTH_DATE_CONTEXT_PATTERN = re.compile(
    r"(?i)\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\b"
)

__all__ = [
    "build_asset_note_candidate_facts",
    "build_cash_health_note_candidate_facts",
    "build_debt_note_candidate_facts",
    "build_working_capital_note_candidate_facts",
]


def build_asset_note_candidate_facts(
    *,
    pages: Iterable[tuple[int, str]],
    document_id: str,
    period_id: str | None,
    market: str,
    existing_metric_ids: set[str],
    semantic_fallback_service: SemanticFallbackService | None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    del semantic_fallback_service
    if market.upper() != "HK" or period_id is None:
        return ([], {})

    candidates, missing_status, _, _ = _build_note_candidate_facts(
        pages=list(pages),
        document_id=document_id,
        period_id=period_id,
        market=market,
        existing_metric_ids=existing_metric_ids,
        note_definitions=_ASSET_NOTE_DEFINITIONS,
    )
    return candidates, missing_status


def build_working_capital_note_candidate_facts(
    *,
    pages: Iterable[tuple[int, str]],
    document_id: str,
    period_id: str | None,
    market: str,
    existing_metric_ids: set[str],
    semantic_fallback_service: SemanticFallbackService | None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if market.upper() != "HK" or period_id is None:
        return ([], {})

    normalized_pages = list(pages)
    candidates, missing_status, candidate_index, found_metric_ids = (
        _build_note_candidate_facts(
            pages=normalized_pages,
            document_id=document_id,
            period_id=period_id,
            market=market,
            existing_metric_ids=existing_metric_ids,
            note_definitions=_NOTE_DEFINITIONS,
        )
    )
    locator_call_count = 0

    for note_definition in _NOTE_DEFINITIONS:
        surfaced_pages = _searchable_pages_for_note_definition(
            pages=normalized_pages,
            surface_patterns=note_definition["surface_patterns"],
            continuation_patterns=note_definition.get("continuation_patterns", ()),
        )
        if semantic_fallback_service is None or not surfaced_pages:
            continue

        for page_index, text in surfaced_pages:
            target_metric_ids = tuple(
                metric_id
                for metric_id in _TARGET_DISCLOSURE_METRIC_IDS
                if metric_id not in found_metric_ids
            )
            if not target_metric_ids:
                break
            if not _should_call_locator(text, found_metric_ids, locator_call_count):
                continue

            locator_call_count += 1
            result = semantic_fallback_service.locate_disclosure_metric(
                DisclosureLocatorRequest(
                    target_metric_ids=target_metric_ids,
                    local_context=text[:4000],
                    deterministic_candidates=(),
                    ambiguity_reason="missing_statement_row",
                )
            )
            if (
                result.metric_id == "none"
                or result.metric_id not in target_metric_ids
                or result.metric_id in found_metric_ids
                or not result.source_text_span
            ):
                continue

            metric_definition = _metric_definition(result.metric_id)
            if metric_definition is None:
                continue

            line_match = _match_metric_in_text(
                text=result.source_text_span,
                pattern=metric_definition["row_pattern"],
            )
            if line_match is None:
                continue

            line, match = line_match
            candidate_index += 1
            found_metric_ids.add(result.metric_id)
            missing_status[result.metric_id] = "present"
            candidates.append(
                _build_candidate_payload(
                    candidate_index=candidate_index,
                    document_id=document_id,
                    label=_label_from_line(line) or result.matched_label,
                    metric_id=result.metric_id,
                    period_id=period_id,
                    page_index=page_index,
                    raw_value=match.group(1),
                    market=market,
                    semantic_source=result.semantic_source,
                    semantic_confidence=result.semantic_confidence,
                    fallback_reason=result.fallback_reason,
                )
            )

    return (candidates, missing_status)


def build_debt_note_candidate_facts(
    *,
    pages: Iterable[tuple[int, str]],
    document_id: str,
    period_id: str | None,
    market: str,
    existing_metric_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if market.upper() != "HK" or period_id is None:
        return ([], {})

    normalized_pages = list(pages)
    candidates, missing_status, _, _ = _build_note_candidate_facts(
        pages=normalized_pages,
        document_id=document_id,
        period_id=period_id,
        market=market,
        existing_metric_ids=existing_metric_ids,
        note_definitions=_DEBT_NOTE_DEFINITIONS,
    )
    return (candidates, missing_status)


def build_cash_health_note_candidate_facts(
    *,
    pages: Iterable[tuple[int, str]],
    document_id: str,
    period_id: str | None,
    market: str,
    existing_metric_ids: set[str],
    semantic_fallback_service: SemanticFallbackService | None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    del semantic_fallback_service
    if market.upper() != "HK" or period_id is None:
        return ([], {})

    normalized_pages = list(pages)
    candidates: list[dict[str, Any]] = []
    missing_status: dict[str, str] = {}
    candidate_index = 0
    found_metric_ids = set(existing_metric_ids)

    for page_index, text in normalized_pages:
        candidate_lines = list(_iter_candidate_lines(text))
        for line_index, line in enumerate(candidate_lines):
            next_line = (
                candidate_lines[line_index + 1]
                if line_index + 1 < len(candidate_lines)
                else None
            )

            restricted_match = _match_restricted_cash_line(line, next_line=next_line)
            if restricted_match is not None and "restricted_cash" not in found_metric_ids:
                candidate_index += 1
                found_metric_ids.add("restricted_cash")
                missing_status["restricted_cash"] = "present"
                candidates.append(
                    _build_candidate_payload(
                        candidate_index=candidate_index,
                        document_id=document_id,
                        label=_label_from_line(line),
                        metric_id="restricted_cash",
                        period_id=period_id,
                        page_index=page_index,
                        raw_value=restricted_match.group(1),
                        market=market,
                        semantic_source="deterministic",
                        semantic_confidence=None,
                        fallback_reason=None,
                    )
                )

            interest_match = _match_cash_health_label_line(
                line=line,
                next_line=next_line,
                label_patterns=_CASH_HEALTH_INTEREST_PAID_LABEL_PATTERNS,
            )
            if interest_match is not None and "interest_paid_cash" not in found_metric_ids:
                label, raw_value = interest_match
                candidate_index += 1
                found_metric_ids.add("interest_paid_cash")
                missing_status["interest_paid_cash"] = "present"
                candidates.append(
                    _build_candidate_payload(
                        candidate_index=candidate_index,
                        document_id=document_id,
                        label=label,
                        metric_id="interest_paid_cash",
                        period_id=period_id,
                        page_index=page_index,
                        raw_value=raw_value,
                        market=market,
                        semantic_source="deterministic",
                        semantic_confidence=None,
                        fallback_reason=None,
                        statement_type="cash_flow_statement",
                        period_scope="duration",
                    )
                )

            time_deposits_match = _match_cash_health_label_line(
                line=line,
                next_line=next_line,
                label_patterns=_CASH_HEALTH_TIME_DEPOSITS_LABEL_PATTERNS,
                require_line_start=True,
            )
            if (
                time_deposits_match is not None
                and "time_deposits_or_wealth_products" not in found_metric_ids
            ):
                label, raw_value = time_deposits_match
                candidate_index += 1
                found_metric_ids.add("time_deposits_or_wealth_products")
                missing_status["time_deposits_or_wealth_products"] = "present"
                candidates.append(
                    _build_candidate_payload(
                        candidate_index=candidate_index,
                        document_id=document_id,
                        label=label,
                        metric_id="time_deposits_or_wealth_products",
                        period_id=period_id,
                        page_index=page_index,
                        raw_value=raw_value,
                        market=market,
                        semantic_source="deterministic",
                        semantic_confidence=None,
                        fallback_reason=None,
                    )
                )

    if not candidates and "restricted_cash" not in found_metric_ids:
        return ([], {"restricted_cash": "not_surfaced"})

    for metric_id in existing_metric_ids:
        if metric_id in {
            "restricted_cash",
            "interest_paid_cash",
            "time_deposits_or_wealth_products",
        }:
            missing_status.setdefault(metric_id, "present")

    return (candidates, missing_status)


def _build_note_candidate_facts(
    *,
    pages: list[tuple[int, str]],
    document_id: str,
    period_id: str,
    market: str,
    existing_metric_ids: set[str],
    note_definitions: tuple[dict[str, Any], ...],
) -> tuple[list[dict[str, Any]], dict[str, str], int, set[str]]:
    candidates: list[dict[str, Any]] = []
    missing_status: dict[str, str] = {}
    candidate_index = 0
    found_metric_ids = set(existing_metric_ids)

    for note_definition in note_definitions:
        surfaced_pages = _searchable_pages_for_note_definition(
            pages=pages,
            surface_patterns=note_definition["surface_patterns"],
            continuation_patterns=note_definition.get("continuation_patterns", ()),
        )

        for metric in note_definition["metrics"]:
            metric_id = metric["metric_id"]

            if metric_id in found_metric_ids:
                missing_status[metric_id] = "present"
                continue

            if not surfaced_pages:
                missing_status[metric_id] = "not_surfaced"
                continue

            page_index, line, match = _first_metric_match(
                pages=surfaced_pages,
                pattern=metric["row_pattern"],
            )
            if page_index is None or line is None or match is None:
                missing_status[metric_id] = "absent"
                continue

            candidate_index += 1
            found_metric_ids.add(metric_id)
            missing_status[metric_id] = "present"
            candidates.append(
                _build_candidate_payload(
                    candidate_index=candidate_index,
                    document_id=document_id,
                    label=_label_from_line(line),
                    metric_id=metric_id,
                    period_id=period_id,
                    page_index=page_index,
                    raw_value=match.group(1),
                    market=market,
                    semantic_source="deterministic",
                    semantic_confidence=None,
                    fallback_reason=None,
                )
            )

    return (candidates, missing_status, candidate_index, found_metric_ids)


def _should_call_locator(
    text: str,
    existing_metric_ids: set[str],
    locator_call_count: int,
) -> bool:
    if locator_call_count >= _MAX_DISCLOSURE_LOCATOR_CALLS_PER_DOCUMENT:
        return False
    if set(_TARGET_DISCLOSURE_METRIC_IDS).issubset(existing_metric_ids):
        return False

    return _has_target_value_row(text)


def _searchable_pages_for_note_definition(
    *,
    pages: list[tuple[int, str]],
    surface_patterns: tuple[re.Pattern[str], ...],
    continuation_patterns: tuple[re.Pattern[str], ...] = (),
) -> list[tuple[int, str]]:
    surfaced_index = next(
        (
            index
            for index, (_, page_text) in enumerate(pages)
            if any(pattern.search(page_text) for pattern in surface_patterns)
        ),
        None,
    )
    if surfaced_index is None:
        return []
    searchable_pages: list[tuple[int, str]] = []
    for page in pages[surfaced_index:]:
        page_text = page[1]
        if not searchable_pages:
            searchable_pages.append(page)
            continue
        if not _looks_like_note_continuation_page(
            text=page_text,
            surface_patterns=surface_patterns,
            continuation_patterns=continuation_patterns,
        ):
            break
        searchable_pages.append(page)
    return searchable_pages


def _looks_like_note_continuation_page(
    *,
    text: str,
    surface_patterns: tuple[re.Pattern[str], ...],
    continuation_patterns: tuple[re.Pattern[str], ...] = (),
) -> bool:
    if any(pattern.search(text) for pattern in surface_patterns):
        return True
    if _has_table_like_title(text):
        return False
    return _has_target_value_row(text, continuation_patterns=continuation_patterns)


def _has_target_value_row(
    text: str,
    continuation_patterns: tuple[re.Pattern[str], ...] = (),
) -> bool:
    if continuation_patterns and any(pattern.search(text) for pattern in continuation_patterns):
        return True
    lowered = text.casefold()
    return (
        re.search(
            r"\b(accounts payable|accounts receivable,?\s+net|contract liabilities)\b\s+\$?\s*[0-9]",
            lowered,
        )
        is not None
    )


def _has_table_like_title(text: str) -> bool:
    for line in _iter_candidate_lines(text):
        if re.search(r"\b20\d{2}\s+20\d{2}\b", line) is None:
            continue
        if re.search(r"\$\s*[0-9]", line) is not None:
            continue
        return True
    return False


def _first_metric_match(
    *,
    pages: list[tuple[int, str]],
    pattern: re.Pattern[str],
) -> tuple[int | None, str | None, re.Match[str] | None]:
    for page_index, page_text in pages:
        line_match = _match_metric_in_text(text=page_text, pattern=pattern)
        if line_match is not None:
            line, match = line_match
            return (page_index, line, match)
    return (None, None, None)


def _match_metric_in_text(
    *,
    text: str,
    pattern: re.Pattern[str],
) -> tuple[str, re.Match[str]] | None:
    for line in _iter_candidate_lines(text):
        match = pattern.search(line)
        if match is not None:
            if _is_year_header_line(line):
                continue
            return (line, match)
    return None


def _metric_definition(metric_id: str) -> dict[str, Any] | None:
    for note_definition in _NOTE_DEFINITIONS:
        for metric in note_definition["metrics"]:
            if metric["metric_id"] == metric_id:
                return metric
    return None


def _match_restricted_cash_line(
    line: str,
    *,
    next_line: str | None = None,
) -> re.Match[str] | None:
    for pattern in _CASH_HEALTH_RESTRICTED_CASH_PATTERNS:
        match = pattern.search(line)
        if match is not None:
            return match
        if next_line is not None and _looks_like_restricted_cash_continuation_line(
            next_line
        ):
            match = pattern.search(f"{line} {next_line}")
            if match is not None:
                return match
    return None


def _looks_like_restricted_cash_continuation_line(line: str) -> bool:
    return re.match(
        r"(?i)^\s*(?:HK\$|US\$|RMB|CNY|￥|\$|人民币|\d)",
        line,
    ) is not None


def _match_cash_health_label_line(
    *,
    line: str,
    next_line: str | None,
    label_patterns: tuple[re.Pattern[str], ...],
    require_line_start: bool = False,
) -> tuple[str, str] | None:
    if _is_year_header_line(line):
        return None

    for pattern in label_patterns:
        match = pattern.search(line)
        if match is None:
            continue
        if require_line_start and line[: match.start()].strip():
            continue

        value = _extract_cash_health_amount(
            tail=line[match.end() :],
            next_line=next_line,
        )
        if value is None:
            continue

        return (match.group(1), value)

    return None


def _extract_cash_health_amount(
    *,
    tail: str,
    next_line: str | None,
) -> str | None:
    if _looks_like_cash_health_date_context(tail):
        return None

    for value_match in _CASH_HEALTH_ROW_VALUE_PATTERN.finditer(tail):
        value = value_match.group(1)
        if _is_year_like_cash_health_value(value):
            continue
        return value

    if next_line is None:
        return None
    if _is_year_header_line(next_line):
        return None
    if not _looks_like_cash_health_continuation_line(next_line):
        return None

    combined = f"{tail} {next_line}"
    if _looks_like_cash_health_date_context(combined):
        return None

    for value_match in _CASH_HEALTH_ROW_VALUE_PATTERN.finditer(combined):
        value = value_match.group(1)
        if _is_year_like_cash_health_value(value):
            continue
        return value

    return None


def _looks_like_cash_health_date_context(text: str) -> bool:
    return _CASH_HEALTH_DATE_CONTEXT_PATTERN.search(text) is not None


def _is_year_like_cash_health_value(value: str) -> bool:
    return re.fullmatch(r"(?:19|20)\d{2}", value) is not None


def _match_cash_health_continuation_value(
    *,
    line: str,
    next_line: str,
    pattern: re.Pattern[str],
) -> re.Match[str] | None:
    if not _looks_like_cash_health_continuation_line(next_line):
        return None

    combined = f"{line} {next_line}"
    match = pattern.search(combined)
    if match is None:
        return None

    return _CASH_HEALTH_ROW_VALUE_PATTERN.search(combined[match.end() :])


def _looks_like_cash_health_continuation_line(line: str) -> bool:
    return re.match(
        r"(?i)^\s*(?:HK\$|US\$|RMB|CNY|人民币|\$|\(?\d)",
        line,
    ) is not None


def _iter_candidate_lines(text: str) -> Iterable[str]:
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if line:
            yield line


def _label_from_line(line: str) -> str:
    return re.split(r"\s+\$?\s*[0-9]", line, maxsplit=1)[0].strip()


def _is_year_header_line(line: str) -> bool:
    if re.search(r"[$(),]", line) is not None:
        return False
    numbers = re.findall(r"\b\d+\b", line)
    return len(numbers) >= 2 and all(
        len(number) == 4 and number.startswith("20") for number in numbers
    )


def _build_candidate_payload(
    *,
    candidate_index: int,
    document_id: str,
    label: str,
    metric_id: str,
    period_id: str,
    page_index: int,
    raw_value: str,
    market: str,
    semantic_source: str,
    semantic_confidence: float | None,
    fallback_reason: str | None,
    statement_type: str = "balance_sheet",
    period_scope: str = "point_in_time",
) -> dict[str, Any]:
    source_kind = (
        "llm_locator_assisted_note_disclosure"
        if semantic_source == "llm_fallback"
        else "deterministic_note_disclosure"
    )
    return {
        "fact_id": f"{document_id}:note-disclosure:candidate:{candidate_index}",
        "fact_kind": "candidate",
        "metric_id": metric_id,
        "metric_label_raw": label,
        "statement_type": statement_type,
        "entity_scope": "consolidated",
        "comparison_axis": "current",
        "adjustment_basis": "reported",
        "period_id": period_id,
        "currency": "HKD",
        "raw_value": raw_value,
        "numeric_value": _parse_number(raw_value),
        "raw_unit": None,
        "normalized_unit": None,
        "precision": _precision(raw_value),
        "confidence": 0.9,
        "extensions": {
            "market": market,
            "accounting_standard": "OTHER",
            "table_kind": "note_disclosure",
            "source_kind": source_kind,
            "source_policy": "supplement_only",
            "statement_scope_guess": "consolidated",
            "period_scope": period_scope,
            "value_type": "amount",
            "unit_expectation": "currency_amount",
            "sign_rule": "allow_negative",
            "semantic_source": semantic_source,
            "semantic_confidence": semantic_confidence,
            "fallback_reason": fallback_reason,
        },
        "document_id": document_id,
        "block_id": f"{document_id}:note-disclosure:page:{page_index}:{metric_id}",
        "page_index": page_index,
        "table_id": None,
        "table_coord": None,
        "evidence_bundle_id": f"{document_id}:bundle:note-disclosure",
        "extraction_method": "note_disclosure",
        "extraction_version": "v1",
        "source_rank_hint": 18,
    }


def _parse_number(raw_value: str) -> float:
    normalized = raw_value.strip().replace(",", "")
    if normalized.startswith("(") and normalized.endswith(")"):
        return -float(normalized[1:-1])
    return float(normalized)


def _precision(raw_value: str) -> int:
    normalized = raw_value.strip().strip("()").replace(",", "")
    if "." not in normalized:
        return 0
    return len(normalized.split(".", maxsplit=1)[1].rstrip("0"))
