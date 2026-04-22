from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import re
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader

from financial_report_analysis.ingestion.note_disclosure import (
    build_working_capital_note_candidate_facts,
)
from financial_report_analysis.ingestion.table_semantics import (
    normalize_table_semantics,
)
from financial_report_analysis.ingestion.table_structure import PdfTableStructureAdapter
from financial_report_analysis.models import (
    NormalizedTableRow,
    NormalizedTableSemantics,
    ParsedRow,
    ParsedTable,
)
from financial_report_analysis.registries import load_metric_registry
from financial_report_analysis.semantic_fallback import (
    CurrencyFallbackRequest,
    RowLabelFallbackRequest,
    SemanticFallbackService,
    TableKindFallbackRequest,
    UnitFallbackRequest,
)
from financial_report_analysis.services import build_table_candidate_facts


class PdfIngestionInputError(ValueError):
    """Raised when ingestion input cannot be read as requested."""


class PdfIngestionAdapter:
    _max_row_label_fallback_calls_per_document = 20
    _INCOME_STATEMENT_CORE_METRICS: tuple[str, ...] = (
        "revenue",
        "operating_cost",
        "operating_profit",
        "net_profit",
    )
    _ROW_LABEL_FALLBACK_BLOCKLIST_TOKENS: tuple[str, ...] = (
        "growth",
        "increase",
        "decrease",
        "margin",
        "ratio",
        "rate",
        "per share",
        "earnings per share",
        "eps",
        "restaurant",
        "restaurants",
        "store",
        "stores",
        "outlet",
        "outlets",
        "segment",
        "mainland china",
        "hong kong",
        "deferred revenue",
        "contract liability",
        "contract liabilities",
        "cost of sales",
        "cost of revenue",
    )
    _ROW_LABEL_FALLBACK_ANCHOR_TOKENS: tuple[str, ...] = (
        "revenue",
        "turnover",
        "sales",
        "operating income",
        "operating profit",
        "profit from operations",
        "net profit",
        "profit attributable",
        "operating cash flow",
        "cash generated from operations",
        "net cash generated from operating activities",
        "cash and cash equivalents",
        "cash equivalents",
        "total assets",
        "assets total",
        "total liabilities",
        "liabilities total",
        "total equity",
        "equity attributable",
        "gross profit",
        "net cash from investing activities",
        "net cash from financing activities",
    )
    _REVENUE_TABLE_KINDS: tuple[str, ...] = (
        "income_statement",
        "key_metrics",
        "metrics",
    )
    _PRIMARY_REVENUE_LABELS: tuple[str, ...] = (
        "revenue",
        "turnover",
        "operating revenue",
        "营业收入",
        "营业总收入",
    )
    _REVENUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        (
            "Revenue",
            re.compile(
                r"\bRevenue\b[^\d\-()]*([0-9][0-9,]*(?:\.\d+)?)",
                re.IGNORECASE,
            ),
        ),
        (
            "Turnover",
            re.compile(
                r"\bTurnover\b[^\d\-()]*([0-9][0-9,]*(?:\.\d+)?)",
                re.IGNORECASE,
            ),
        ),
        (
            "\u8425\u4e1a\u6536\u5165",
            re.compile(
                r"\u8425\u4e1a\u603b?\u6536\u5165[^\d\-()]*([0-9][0-9,]*(?:\.\d+)?)"
            ),
        ),
    )
    _REVENUE_LABEL_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"\bRevenue\b", re.IGNORECASE),
        re.compile(r"\bTurnover\b", re.IGNORECASE),
        re.compile(r"\u8425\u4e1a\u6536\u5165"),
        re.compile(r"\u8425\u4e1a\u603b\u6536\u5165"),
    )

    def __init__(
        self,
        *,
        semantic_fallback_service: SemanticFallbackService | None = None,
    ) -> None:
        self._table_adapter = PdfTableStructureAdapter()
        self._semantic_fallback_service = semantic_fallback_service
        self._semantic_fallback_call_counts = self._new_semantic_fallback_call_counts()
        self._semantic_fallback_budget_exhausted = False

    @staticmethod
    def _new_semantic_fallback_call_counts() -> dict[str, int]:
        return {
            "table_kind": 0,
            "row_label": 0,
            "currency": 0,
            "unit": 0,
        }

    def extract_candidate_facts(
        self,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
        market: str | None,
        min_confidence: float | None,
    ) -> dict[str, Any]:
        document_id = pdf_path or pdf_url or "unknown-document"
        self._semantic_fallback_call_counts = self._new_semantic_fallback_call_counts()
        self._semantic_fallback_budget_exhausted = False
        text_pages = self._extract_text_pages(pdf_path=pdf_path, pdf_url=pdf_url)
        text = "\n".join(page_text for _, page_text in text_pages)
        parsed_tables = self._extract_parsed_tables(
            pdf_path=pdf_path,
            pdf_url=pdf_url,
            market=market,
        )
        language = self._detect_language(text, market)
        period_id = self._detect_period_id_from_tables(
            parsed_tables
        ) or self._detect_period_id(
            text,
        )

        registry = load_metric_registry()
        normalized_tables = [
            self._apply_semantic_fallback(
                normalize_table_semantics(table),
                market=market or "CN",
                registry=registry,
            )
            for table in parsed_tables
        ]
        candidate_facts = build_table_candidate_facts(
            normalized_tables,
            registry=registry,
            document_id=document_id,
            market=market or "CN",
        )
        candidate_facts = self._prefer_main_income_statement_facts(candidate_facts)
        existing_metric_ids = {
            str(candidate.get("metric_id"))
            for candidate in candidate_facts
            if candidate.get("metric_id") is not None
        }
        note_candidates, working_capital_missing_status = (
            build_working_capital_note_candidate_facts(
                pages=text_pages,
                document_id=document_id,
                period_id=period_id,
                market=market or "CN",
                existing_metric_ids=existing_metric_ids,
                semantic_fallback_service=self._semantic_fallback_service,
            )
        )
        candidate_facts.extend(note_candidates)
        if not candidate_facts:
            revenue_fact = self._extract_revenue_fact_from_text(
                document_id=document_id,
                text=text,
                period_id=period_id,
                market=market,
            )
            if revenue_fact is not None:
                candidate_facts = [revenue_fact]

        if min_confidence is not None:
            candidate_facts = [
                fact
                for fact in candidate_facts
                if fact.get("confidence") is not None
                and float(fact["confidence"]) >= min_confidence
            ]

        return {
            "candidate_facts": candidate_facts,
            "document_metadata": {
                "language": language,
                "parsed_tables": [
                    self._serialize_parsed_table(table) for table in normalized_tables
                ],
                "semantic_fallback_call_counts": dict(
                    self._semantic_fallback_call_counts
                ),
                "semantic_fallback_budget_exhausted": (
                    self._semantic_fallback_budget_exhausted
                ),
                "working_capital_missing_status": working_capital_missing_status,
            },
        }

    def _extract_text_pages(
        self,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
    ) -> list[tuple[int, str]]:
        if pdf_path:
            path = Path(pdf_path)
            if not path.exists():
                raise PdfIngestionInputError("pdf_path does not exist")
            reader = PdfReader(str(path))
            return [
                (page_index + 1, page.extract_text() or "")
                for page_index, page in enumerate(reader.pages)
            ]

        if pdf_url:
            response = httpx.get(pdf_url, timeout=30.0)
            response.raise_for_status()
            reader = PdfReader(BytesIO(response.content))
            return [
                (page_index + 1, page.extract_text() or "")
                for page_index, page in enumerate(reader.pages)
            ]

        return []

    def _extract_text(self, *, pdf_path: str | None, pdf_url: str | None) -> str:
        return "\n".join(
            page_text
            for _, page_text in self._extract_text_pages(
                pdf_path=pdf_path,
                pdf_url=pdf_url,
            )
        )

    def _extract_parsed_tables(
        self,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
        market: str | None,
    ) -> list[ParsedTable]:
        try:
            return self._table_adapter.extract_tables(
                pdf_path=pdf_path,
                pdf_url=pdf_url,
                market=market,
            )
        except (OSError, ValueError, TypeError):
            return []

    def _extract_revenue_fact_from_tables(
        self,
        parsed_tables: list[ParsedTable],
        *,
        period_id: str | None,
        market: str | None,
    ) -> dict[str, Any] | None:
        for table in self._ordered_revenue_tables(parsed_tables):
            if table.table_kind not in self._REVENUE_TABLE_KINDS:
                continue
            revenue_row = self._find_revenue_row(table)
            if revenue_row is None or not revenue_row.value_cells:
                continue
            value_cell = self._first_numeric_value_cell(revenue_row)
            if value_cell is None:
                continue
            raw_value = value_cell.text_raw
            numeric_value = value_cell.numeric_value
            if numeric_value is None:
                try:
                    numeric_value = self._parse_number(raw_value)
                except ValueError:
                    continue
            resolved_period_id = self._first_period_id(table) or period_id
            if resolved_period_id is None:
                continue
            context = self._table_context(table, revenue_row)
            return self._build_candidate_fact(
                document_id=table.document_id,
                label=self._normalize_revenue_label(revenue_row.label_raw),
                numeric_value=numeric_value,
                raw_value=raw_value,
                period_id=resolved_period_id,
                currency=table.table_currency or self._detect_currency(context, market),
                raw_unit=table.table_unit or self._detect_raw_unit(context),
                statement_type=table.table_kind
                if table.table_kind != "key_metrics"
                else "metrics",
                table_kind=table.table_kind,
                page_index=value_cell.page_index or table.page_range[0],
                table_coord=(value_cell.row_index, value_cell.column_index),
                extraction_method="table_structure",
                evidence_bundle_suffix="table",
                market=market,
                table_id=table.table_id,
            )
        return None

    def _extract_revenue_fact_from_text(
        self,
        *,
        document_id: str,
        text: str,
        period_id: str | None,
        market: str | None,
    ) -> dict[str, Any] | None:
        if period_id is None:
            return None

        revenue_facts = self._extract_revenue_facts(text)
        if not revenue_facts:
            return None

        label, numeric_value, span = revenue_facts[0]
        revenue_context = self._extract_revenue_context(text, span)
        return self._build_candidate_fact(
            document_id=document_id,
            label=label,
            numeric_value=numeric_value,
            raw_value=str(numeric_value),
            period_id=period_id,
            currency=self._detect_currency(revenue_context, market),
            raw_unit=self._detect_raw_unit(revenue_context),
            statement_type="income_statement",
            table_kind="text_regex",
            page_index=0,
            table_coord=None,
            extraction_method="pdf_text_regex",
            evidence_bundle_suffix="text",
            market=market,
            table_id=None,
        )

    def _build_candidate_fact(
        self,
        *,
        document_id: str,
        label: str,
        numeric_value: float,
        raw_value: str,
        period_id: str,
        currency: str,
        raw_unit: str | None,
        statement_type: str,
        table_kind: str | None,
        page_index: int,
        table_coord: tuple[int, int] | None,
        extraction_method: str,
        evidence_bundle_suffix: str,
        market: str | None,
        table_id: str | None,
    ) -> dict[str, Any]:
        fact: dict[str, Any] = {
            "fact_id": f"{document_id}:candidate:1",
            "fact_kind": "candidate",
            "metric_id": "raw_revenue",
            "metric_label_raw": label,
            "statement_type": statement_type,
            "entity_scope": "consolidated",
            "comparison_axis": "current",
            "adjustment_basis": "reported",
            "period_id": period_id,
            "currency": currency,
            "raw_value": raw_value,
            "numeric_value": numeric_value,
            "raw_unit": raw_unit,
            "normalized_unit": None,
            "precision": self._precision(numeric_value),
            "confidence": 0.9,
            "extensions": {
                "market": market or "CN",
                "accounting_standard": "OTHER",
                "table_kind": table_kind,
            },
            "document_id": document_id,
            "block_id": f"{document_id}:block:1",
            "page_index": page_index,
            "evidence_bundle_id": f"{document_id}:bundle:{evidence_bundle_suffix}",
            "table_coord": table_coord,
            "extraction_method": extraction_method,
            "extraction_version": "v2"
            if extraction_method == "table_structure"
            else "v1",
            "source_rank_hint": 1,
        }
        if table_id is not None:
            fact["table_id"] = table_id
        return fact

    def _extract_revenue_facts(
        self, text: str
    ) -> list[tuple[str, float, tuple[int, int]]]:
        facts: list[tuple[str, float, tuple[int, int]]] = []
        for label, pattern in self._REVENUE_PATTERNS:
            match = pattern.search(text)
            if match is None:
                continue
            facts.append((label, self._parse_number(match.group(1)), match.span()))
            break
        return facts

    @staticmethod
    def _extract_revenue_context(text: str, revenue_span: tuple[int, int]) -> str:
        start, end = revenue_span
        context_start = max(0, start - 400)
        context_end = min(len(text), end + 120)
        return text[context_start:context_end]

    @staticmethod
    def _detect_period_id(text: str) -> str | None:
        annual_match = re.search(r"\b(20\d{2})\s+Annual Report\b", text, re.IGNORECASE)
        if annual_match:
            return f"{annual_match.group(1)}FY"

        quarter_match = re.search(r"\b(20\d{2})\s*Q([1-4])\b", text, re.IGNORECASE)
        if quarter_match:
            return f"{quarter_match.group(1)}Q{quarter_match.group(2)}"

        chinese_annual = re.search(
            r"(20\d{2})\s*\u5e74\s*\u5e74\u5ea6\u62a5\u544a",
            text,
        )
        if chinese_annual:
            return f"{chinese_annual.group(1)}FY"

        chinese_quarter = re.search(
            r"(20\d{2})\s*\u5e74\s*\u7b2c\s*([\u4e00\u4e8c\u4e09\u56db])\s*\u5b63\u5ea6\u62a5\u544a",
            text,
        )
        if chinese_quarter:
            quarter_map = {
                "\u4e00": "1",
                "\u4e8c": "2",
                "\u4e09": "3",
                "\u56db": "4",
            }
            return f"{chinese_quarter.group(1)}Q{quarter_map[chinese_quarter.group(2)]}"

        return None

    @staticmethod
    def _detect_language(text: str, market: str | None) -> str:
        if re.search(r"[\u4e00-\u9fff]", text):
            return "zh-Hant" if market == "HK" else "zh-Hans"
        return "en"

    def _detect_period_id_from_tables(
        self, parsed_tables: list[ParsedTable]
    ) -> str | None:
        for table in parsed_tables:
            for column in table.period_columns:
                if column.period_id is not None:
                    return column.period_id
        return None

    @staticmethod
    def _first_period_id(table: ParsedTable) -> str | None:
        for column in table.period_columns:
            if column.period_id is not None:
                return column.period_id
        return None

    def _find_revenue_row(self, table: ParsedTable) -> ParsedRow | None:
        for row in table.body_rows:
            label = row.label_raw.strip()
            if self._is_revenue_label(label, table_kind=table.table_kind):
                return row
        return None

    def _is_revenue_label(self, label: str, *, table_kind: str) -> bool:
        normalized = re.sub(r"\s+", " ", label).strip()
        english_label = normalized.lower()
        if table_kind in {"key_metrics", "metrics"}:
            return (
                english_label in self._PRIMARY_REVENUE_LABELS
                or normalized in self._PRIMARY_REVENUE_LABELS
            )
        if "revenue" in english_label or "turnover" in english_label:
            return True
        return any(
            pattern.search(normalized) for pattern in self._REVENUE_LABEL_PATTERNS
        )

    def _ordered_revenue_tables(
        self,
        parsed_tables: list[ParsedTable],
    ) -> list[ParsedTable]:
        kind_priority = {
            "income_statement": 0,
            "key_metrics": 1,
            "metrics": 2,
        }
        return sorted(
            parsed_tables,
            key=lambda table: (
                kind_priority.get(table.table_kind, 99),
                table.page_range[0],
                table.table_id,
            ),
        )

    @staticmethod
    def _normalize_revenue_label(label: str) -> str:
        normalized = re.sub(r"^[\s\d\u3001\.\-:：]+", "", label).strip()
        if "\u8425\u4e1a\u603b\u6536\u5165" in normalized:
            return "\u8425\u4e1a\u6536\u5165"
        return normalized

    @staticmethod
    def _first_numeric_value_cell(row: ParsedRow) -> Any | None:
        for cell in row.value_cells:
            if cell.numeric_value is not None:
                return cell
        return row.value_cells[0] if row.value_cells else None

    @staticmethod
    def _table_context(table: ParsedTable, row: ParsedRow) -> str:
        header_text = "\n".join(
            " ".join(cell for cell in header_row if cell).strip()
            for header_row in table.header_rows
            if any(header_row)
        )
        body_text = " ".join(cell.text_raw for cell in row.value_cells if cell.text_raw)
        return "\n".join(
            part
            for part in [table.title_text, header_text, row.label_raw, body_text]
            if part
        )

    def _apply_semantic_fallback(
        self,
        table: NormalizedTableSemantics,
        *,
        market: str,
        registry: Any,
    ) -> NormalizedTableSemantics:
        if self._semantic_fallback_service is None:
            return table

        local_context = self._normalized_table_context(table)
        self._semantic_fallback_call_counts["table_kind"] += 1
        table_kind_result = self._semantic_fallback_service.resolve_table_kind(
            TableKindFallbackRequest(
                title_text=table.title_text,
                local_context=local_context,
                deterministic_candidates=(table.table_kind,),
                ambiguity_reason=table.semantic_ambiguity_reason,
            )
        )
        table_with_kind = replace(
            table,
            table_kind=table_kind_result.value,
            semantic_source=table_kind_result.semantic_source,
            semantic_confidence=self._merged_confidence(
                table.semantic_confidence,
                table_kind_result.semantic_confidence,
            ),
            semantic_ambiguity_reason=(
                table_kind_result.fallback_reason or table.semantic_ambiguity_reason
            ),
        )
        table_with_local_semantics = self._apply_local_semantic_fallback(
            table=table_with_kind,
            local_context=local_context,
        )

        rows = [
            self._apply_row_label_fallback(
                table=table_with_local_semantics,
                row=row,
                local_context=local_context,
                market=market,
                registry=registry,
            )
            for row in table_with_local_semantics.rows
        ]

        return replace(
            table_with_local_semantics,
            semantic_source=self._table_semantic_source(
                table=table_with_local_semantics,
                rows=rows,
            ),
            semantic_confidence=self._table_semantic_confidence(
                table=table_with_local_semantics,
                rows=rows,
            ),
            semantic_ambiguity_reason=self._table_fallback_reason(
                table=table_with_local_semantics,
                rows=rows,
            ),
            rows=rows,
        )

    def _apply_local_semantic_fallback(
        self,
        *,
        table: NormalizedTableSemantics,
        local_context: str,
    ) -> NormalizedTableSemantics:
        currency_ambiguity_reason = self._currency_ambiguity_reason(table)
        if currency_ambiguity_reason is not None:
            self._semantic_fallback_call_counts["currency"] += 1
            currency_result = self._semantic_fallback_service.resolve_currency(
                CurrencyFallbackRequest(
                    raw_text=table.table_currency or "unknown",
                    local_context=local_context,
                    deterministic_candidates=tuple(
                        candidate
                        for candidate in [table.table_currency]
                        if candidate is not None
                    ),
                    ambiguity_reason=currency_ambiguity_reason,
                )
            )
            table = replace(
                table,
                table_currency=currency_result.value,
                currency_semantic_source=currency_result.semantic_source,
                semantic_confidence=self._merged_confidence(
                    table.semantic_confidence,
                    currency_result.semantic_confidence,
                ),
            )

        unit_ambiguity_reason = self._unit_ambiguity_reason(table)
        if unit_ambiguity_reason is not None:
            self._semantic_fallback_call_counts["unit"] += 1
            unit_result = self._semantic_fallback_service.resolve_unit(
                UnitFallbackRequest(
                    raw_text=table.table_unit or "unknown",
                    local_context=local_context,
                    deterministic_candidates=tuple(
                        candidate
                        for candidate in [table.table_unit]
                        if candidate is not None
                    ),
                    ambiguity_reason=unit_ambiguity_reason,
                )
            )
            table = replace(
                table,
                table_unit=unit_result.value,
                unit_semantic_source=unit_result.semantic_source,
                semantic_confidence=self._merged_confidence(
                    table.semantic_confidence,
                    unit_result.semantic_confidence,
                ),
            )

        return table

    def _apply_row_label_fallback(
        self,
        *,
        table: NormalizedTableSemantics,
        row: NormalizedTableRow,
        local_context: str,
        market: str,
        registry: Any,
    ) -> NormalizedTableRow:
        ambiguity_reason = self._row_label_ambiguity_reason(
            table=table,
            row=row,
            market=market,
            registry=registry,
        )
        if ambiguity_reason is None:
            return row
        if not self._has_row_label_fallback_budget():
            return row
        self._semantic_fallback_call_counts["row_label"] += 1
        result = self._semantic_fallback_service.resolve_row_label(
            RowLabelFallbackRequest(
                raw_label=row.label_raw,
                table_kind=table.table_kind,
                local_context="\n".join([local_context, row.label_raw]).strip(),
                deterministic_candidates=tuple(
                    candidate
                    for candidate in [row.normalized_row_label]
                    if candidate is not None
                ),
                ambiguity_reason=ambiguity_reason,
            )
        )
        if result.semantic_source != "llm_fallback":
            return row
        return replace(
            row,
            normalized_row_label=result.value,
            semantic_source=result.semantic_source,
            semantic_confidence=result.semantic_confidence,
            fallback_reason=result.fallback_reason,
        )

    def _has_row_label_fallback_budget(self) -> bool:
        if (
            self._semantic_fallback_call_counts["row_label"]
            < self._max_row_label_fallback_calls_per_document
        ):
            return True
        self._semantic_fallback_budget_exhausted = True
        return False

    @staticmethod
    def _row_label_ambiguity_reason(
        *,
        table: NormalizedTableSemantics,
        row: NormalizedTableRow,
        market: str,
        registry: Any,
    ) -> str | None:
        if PdfIngestionAdapter._is_summary_growth_or_ratio_row(row.label_raw):
            return None

        if PdfIngestionAdapter._row_matches_metric_registry(
            table=table,
            row=row,
            market=market,
            registry=registry,
        ):
            return None

        if not PdfIngestionAdapter._is_row_label_fallback_eligible(
            row.label_raw,
            row.normalized_row_label,
        ):
            return None

        if row.normalized_row_label is None:
            return table.semantic_ambiguity_reason or "unknown_row_label"

        return table.semantic_ambiguity_reason or "unmapped_normalized_row_label"

    @staticmethod
    def _currency_ambiguity_reason(table: NormalizedTableSemantics) -> str | None:
        if table.table_currency != "unknown" or table.semantic_ambiguity_reason is None:
            return None
        return table.semantic_ambiguity_reason or "unknown_table_currency"

    @staticmethod
    def _unit_ambiguity_reason(table: NormalizedTableSemantics) -> str | None:
        if table.table_unit != "unknown" or table.semantic_ambiguity_reason is None:
            return None
        return table.semantic_ambiguity_reason or "unknown_table_unit"

    @staticmethod
    def _is_row_label_fallback_eligible(
        raw_label: str,
        normalized_label: str | None,
    ) -> bool:
        combined_label = (
            re.sub(
                r"\s+",
                " ",
                " ".join(part for part in [raw_label, normalized_label or ""] if part),
            )
            .strip()
            .casefold()
        )
        if not combined_label:
            return False
        if any(
            PdfIngestionAdapter._contains_fallback_token(combined_label, token)
            for token in PdfIngestionAdapter._ROW_LABEL_FALLBACK_BLOCKLIST_TOKENS
        ):
            return False
        return any(
            PdfIngestionAdapter._contains_fallback_token(combined_label, token)
            for token in PdfIngestionAdapter._ROW_LABEL_FALLBACK_ANCHOR_TOKENS
        )

    @staticmethod
    def _contains_fallback_token(text: str, token: str) -> bool:
        if token.isascii():
            pattern = rf"(?<!\w){re.escape(token)}(?!\w)"
            return re.search(pattern, text) is not None
        return token in text

    @staticmethod
    def _row_matches_metric_registry(
        *,
        table: NormalizedTableSemantics,
        row: NormalizedTableRow,
        market: str,
        registry: Any,
    ) -> bool:
        if row.normalized_row_label is None:
            return False

        return any(
            registry.match(
                table_kind=table.table_kind,
                normalized_row_label=row.normalized_row_label,
                value_time_shape=value.value_time_shape,
                statement_scope_guess=table.statement_scope_guess,
                market=market,
            )
            is not None
            for value in row.values
        )

    @staticmethod
    def _merged_confidence(*confidences: float | None) -> float | None:
        resolved = [confidence for confidence in confidences if confidence is not None]
        return max(resolved, default=None)

    @staticmethod
    def _table_semantic_source(
        *,
        table: NormalizedTableSemantics,
        rows: list[NormalizedTableRow],
    ) -> str:
        if (
            table.semantic_source == "llm_fallback"
            or table.unit_semantic_source == "llm_fallback"
            or table.currency_semantic_source == "llm_fallback"
            or any(row.semantic_source == "llm_fallback" for row in rows)
        ):
            return "llm_fallback"
        return "deterministic"

    @staticmethod
    def _table_semantic_confidence(
        *,
        table: NormalizedTableSemantics,
        rows: list[NormalizedTableRow],
    ) -> float | None:
        return max(
            [
                confidence
                for confidence in [
                    table.semantic_confidence,
                    *[row.semantic_confidence for row in rows],
                ]
                if confidence is not None
            ],
            default=None,
        )

    @staticmethod
    def _table_fallback_reason(
        *,
        table: NormalizedTableSemantics,
        rows: list[NormalizedTableRow],
    ) -> str | None:
        for reason in [
            *[row.fallback_reason for row in rows if row.fallback_reason is not None],
            table.semantic_ambiguity_reason,
        ]:
            if reason is not None:
                return reason
        return None

    @staticmethod
    def _normalized_table_context(table: NormalizedTableSemantics) -> str:
        header_text = "\n".join(
            column.header_text for column in table.columns if column.header_text
        )
        row_labels = "\n".join(
            row.label_raw for row in table.rows[:10] if row.label_raw
        )
        return "\n".join(
            part for part in [table.title_text, header_text, row_labels] if part
        )

    @classmethod
    def _prefer_main_income_statement_facts(
        cls,
        candidate_facts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        best_income_statement_rank: dict[tuple[str, str, str, str], int] = {}
        for fact in candidate_facts:
            if not cls._is_income_statement_core_fact(fact):
                continue
            key = cls._income_statement_fact_key(fact)
            rank = int(fact.get("source_rank_hint", 0))
            current_best = best_income_statement_rank.get(key)
            if current_best is None or rank > current_best:
                best_income_statement_rank[key] = rank

        prioritized_facts: list[dict[str, Any]] = []
        seen_income_statement_keys: set[tuple[str, str, str, str]] = set()
        for fact in candidate_facts:
            if not cls._is_income_statement_core_fact(fact):
                prioritized_facts.append(fact)
                continue

            key = cls._income_statement_fact_key(fact)
            best_rank = best_income_statement_rank.get(key, 0)
            rank = int(fact.get("source_rank_hint", 0))
            if best_rank > rank:
                continue
            if best_rank >= 30 and key in seen_income_statement_keys:
                continue
            prioritized_facts.append(fact)
            if best_rank >= 30:
                seen_income_statement_keys.add(key)

        return prioritized_facts

    @classmethod
    def _is_income_statement_core_fact(cls, fact: dict[str, Any]) -> bool:
        return (
            fact.get("extraction_method") == "table_semantics"
            and fact.get("statement_type") == "income_statement"
            and fact.get("metric_id") in cls._INCOME_STATEMENT_CORE_METRICS
        )

    @staticmethod
    def _income_statement_fact_key(fact: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            str(fact.get("metric_id") or ""),
            str(fact.get("period_id") or ""),
            str(fact.get("comparison_axis") or "current"),
            str(fact.get("entity_scope") or "other"),
        )

    @staticmethod
    def _is_summary_growth_or_ratio_row(label_raw: str) -> bool:
        normalized = re.sub(r"\s+", " ", label_raw).strip().casefold()
        if not normalized:
            return False
        if (
            (
                "earnings per share" in normalized
                or re.search(r"\bbasic eps\b", normalized)
            )
            and "basic" in normalized
        ) or (
            ("每股收益" in normalized or "每股盈利" in normalized)
            and "基本" in normalized
        ):
            return False
        return (
            re.search(r"\b(growth|margin|ratio)\b", normalized, re.IGNORECASE)
            is not None
            or re.search(
                r"\b(?:diluted|adjusted|non[- ]gaap|non[- ]ifrs|headline)\b.*\b(?:per share|eps)\b",
                normalized,
                re.IGNORECASE,
            )
            is not None
            or re.search(r"\b(?:per share|eps)\b", normalized, re.IGNORECASE)
            is not None
            or re.search(r"\bbook value\b", normalized, re.IGNORECASE) is not None
            or re.search(
                r"\banalysis of balances? of cash and cash equivalents\b",
                normalized,
                re.IGNORECASE,
            )
            is not None
            or re.search(
                r"\bcash flows? before (?:changes|movements) in working capital\b",
                normalized,
                re.IGNORECASE,
            )
            is not None
            or re.search(
                r"\bcash generated from operations before (?:changes|movements) in working capital\b",
                normalized,
                re.IGNORECASE,
            )
            is not None
            or re.search(r"(增长率|增长|比率|利润率|毛利率)", normalized) is not None
            or re.search(
                r"(稀释|调整后|非公认会计准则|非国际财务报告准则).*(每股|每股收益|每股盈利)",
                normalized,
            )
            is not None
            or re.search(r"每股", normalized) is not None
            or re.search(r"小计", normalized) is not None
        )

    @staticmethod
    def _serialize_parsed_table(table: NormalizedTableSemantics) -> dict[str, Any]:
        return {
            "table_id": table.table_id,
            "document_id": table.document_id,
            "table_kind": table.table_kind,
            "title_text": table.title_text,
            "page_range": list(table.page_range),
            "table_unit": table.table_unit,
            "table_currency": table.table_currency,
            "period_columns": [
                {
                    "column_id": column.column_id,
                    "header_text": column.header_text,
                    "period_id": column.period_id,
                    "comparison_axis": column.comparison_axis,
                    "is_current": column.is_current,
                    "is_comparison": column.is_comparison,
                }
                for column in table.columns
            ],
            "unit_semantic_source": table.unit_semantic_source,
            "currency_semantic_source": table.currency_semantic_source,
            "semantic_source": table.semantic_source,
            "semantic_confidence": table.semantic_confidence,
            "fallback_reason": table.semantic_ambiguity_reason,
        }

    @staticmethod
    def _detect_currency(text: str, market: str | None) -> str:
        upper_text = text.upper()
        if re.search(r"\u5e01\u79cd[:\uFF1A]\s*\u6e2f\u5143", text):
            return "HKD"
        if re.search(r"\u5e01\u79cd[:\uFF1A]\s*\u7f8e\u5143", text):
            return "USD"
        if re.search(r"\u5e01\u79cd[:\uFF1A]\s*\u4eba\u6c11\u5e01", text):
            return "CNY"
        if "HK$" in text or "HKD" in upper_text or "\u6e2f\u5143" in text:
            return "HKD"
        if "US$" in text or "USD" in upper_text or "\u7f8e\u5143" in text:
            return "USD"
        if "RMB" in upper_text or "CNY" in upper_text or "\u4eba\u6c11\u5e01" in text:
            return "CNY"
        if market == "HK":
            return "HKD"
        if market == "US":
            return "USD"
        return "CNY"

    @staticmethod
    def _detect_raw_unit(text: str) -> str | None:
        unit_match = re.search(r"\u5355\u4f4d[:\uFF1A]\s*([^\s\n]+)", text)
        if unit_match:
            return unit_match.group(1)
        thousand_match = re.search(
            r"(RMB|CNY|USD|HKD|HK\$|US\$)\s*['` ]?0{3}",
            text,
            re.IGNORECASE,
        )
        if thousand_match:
            currency = thousand_match.group(1).upper().replace("$", "")
            return f"{currency}'000"
        if "\u4ebf\u5143" in text or "\u4ebf" in text:
            return "\u4ebf\u5143"
        if "\u767e\u4e07\u5143" in text or "\u767e\u4e07" in text:
            return "\u767e\u4e07\u5143"
        if "\u4e07\u5143" in text:
            return "\u4e07\u5143"
        return None

    @staticmethod
    def _parse_number(raw_number: str) -> float:
        return float(raw_number.replace(",", ""))

    @staticmethod
    def _precision(numeric_value: float) -> int:
        text = f"{numeric_value}"
        if "." not in text:
            return 0
        return len(text.split(".", maxsplit=1)[1].rstrip("0"))
