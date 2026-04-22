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
    {
        "surface_patterns": (
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

__all__ = [
    "build_asset_note_candidate_facts",
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
    # For the bounded P3 asset note-only fields, we search the full extracted
    # text pages. If no note block surfaces at all, treat the metrics as absent
    # for the current document rather than a structure-level not_surfaced gap.
    missing_status = {
        metric_id: ("absent" if status == "not_surfaced" else status)
        for metric_id, status in missing_status.items()
    }
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
) -> dict[str, Any]:
    return {
        "fact_id": f"{document_id}:note-disclosure:candidate:{candidate_index}",
        "fact_kind": "candidate",
        "metric_id": metric_id,
        "metric_label_raw": label,
        "statement_type": "balance_sheet",
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
            "statement_scope_guess": "consolidated",
            "period_scope": "point_in_time",
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
