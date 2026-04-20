from __future__ import annotations

from financial_report_analysis.semantic_fallback.client import SemanticFallbackClient
from financial_report_analysis.semantic_fallback.models import (
    CurrencyFallbackRequest,
    RowLabelFallbackRequest,
    SemanticFallbackResult,
    TableKindFallbackRequest,
    UnitFallbackRequest,
    supported_currency_outputs,
    supported_row_label_outputs,
    supported_table_kind_outputs,
    supported_unit_outputs,
)


class SemanticFallbackService:
    def __init__(self, *, client: SemanticFallbackClient | None = None) -> None:
        self._client = client

    def resolve_table_kind(
        self,
        request: TableKindFallbackRequest,
    ) -> SemanticFallbackResult:
        if self._client is None or not request.ambiguity_reason:
            deterministic_value = (
                request.deterministic_candidates[0]
                if request.deterministic_candidates
                else "unknown"
            )
            return SemanticFallbackResult(
                value=_bounded_table_kind(deterministic_value),
                semantic_source="deterministic",
                semantic_confidence=None,
                fallback_reason=None,
            )
        result = self._client.classify_table_kind(request)
        return SemanticFallbackResult(
            value=_bounded_table_kind(result.value),
            semantic_source=result.semantic_source,
            semantic_confidence=result.semantic_confidence,
            fallback_reason=result.fallback_reason,
        )

    def resolve_row_label(
        self,
        request: RowLabelFallbackRequest,
    ) -> SemanticFallbackResult:
        if self._client is None or not request.ambiguity_reason:
            deterministic_value = (
                request.deterministic_candidates[0]
                if request.deterministic_candidates
                else "none"
            )
            return SemanticFallbackResult(
                value=_bounded_row_label(deterministic_value),
                semantic_source="deterministic",
                semantic_confidence=None,
                fallback_reason=None,
            )
        result = self._client.normalize_row_label(request)
        return SemanticFallbackResult(
            value=_bounded_row_label(result.value),
            semantic_source=result.semantic_source,
            semantic_confidence=result.semantic_confidence,
            fallback_reason=result.fallback_reason,
        )

    def resolve_currency(
        self,
        request: CurrencyFallbackRequest,
    ) -> SemanticFallbackResult:
        if self._client is None or not request.ambiguity_reason:
            deterministic_value = (
                request.deterministic_candidates[0]
                if request.deterministic_candidates
                else "unknown"
            )
            return SemanticFallbackResult(
                value=_bounded_currency(deterministic_value),
                semantic_source="deterministic",
                semantic_confidence=None,
                fallback_reason=None,
            )
        result = self._client.interpret_currency(request)
        return SemanticFallbackResult(
            value=_bounded_currency(result.value),
            semantic_source=result.semantic_source,
            semantic_confidence=result.semantic_confidence,
            fallback_reason=result.fallback_reason,
        )

    def resolve_unit(
        self,
        request: UnitFallbackRequest,
    ) -> SemanticFallbackResult:
        if self._client is None or not request.ambiguity_reason:
            deterministic_value = (
                request.deterministic_candidates[0]
                if request.deterministic_candidates
                else "unknown"
            )
            return SemanticFallbackResult(
                value=_bounded_unit(deterministic_value),
                semantic_source="deterministic",
                semantic_confidence=None,
                fallback_reason=None,
            )
        result = self._client.interpret_unit(request)
        return SemanticFallbackResult(
            value=_bounded_unit(result.value),
            semantic_source=result.semantic_source,
            semantic_confidence=result.semantic_confidence,
            fallback_reason=result.fallback_reason,
        )


def _bounded_table_kind(value: str) -> str:
    normalized = value.strip().casefold()
    return normalized if normalized in supported_table_kind_outputs() else "unknown"


def _bounded_row_label(value: str) -> str:
    normalized = value.strip().casefold()
    return normalized if normalized in supported_row_label_outputs() else "none"


def _bounded_currency(value: str) -> str:
    normalized = value.strip().upper()
    return normalized if normalized in supported_currency_outputs() else "unknown"


def _bounded_unit(value: str) -> str:
    normalized = value.strip().casefold()
    return normalized if normalized in supported_unit_outputs() else "unknown"
