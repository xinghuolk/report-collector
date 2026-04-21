from __future__ import annotations

from collections.abc import Callable
import logging
import threading

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

LOGGER = logging.getLogger(__name__)


class SemanticFallbackService:
    def __init__(
        self,
        *,
        client: SemanticFallbackClient | None = None,
        max_concurrency: int = 1,
    ) -> None:
        self._client = client
        self._max_concurrency = max(1, max_concurrency)
        self._semaphore = threading.BoundedSemaphore(self._max_concurrency)

    def resolve_table_kind(
        self,
        request: TableKindFallbackRequest,
    ) -> SemanticFallbackResult:
        return self._resolve_with_fallback(
            request=request,
            default_value="unknown",
            bound_value=_bounded_table_kind,
            invoke_client=self._client.classify_table_kind
            if self._client is not None
            else None,
        )

    def resolve_row_label(
        self,
        request: RowLabelFallbackRequest,
    ) -> SemanticFallbackResult:
        return self._resolve_with_fallback(
            request=request,
            default_value="none",
            bound_value=_bounded_row_label,
            invoke_client=self._client.normalize_row_label
            if self._client is not None
            else None,
        )

    def resolve_currency(
        self,
        request: CurrencyFallbackRequest,
    ) -> SemanticFallbackResult:
        return self._resolve_with_fallback(
            request=request,
            default_value="unknown",
            bound_value=_bounded_currency,
            invoke_client=self._client.interpret_currency
            if self._client is not None
            else None,
        )

    def resolve_unit(
        self,
        request: UnitFallbackRequest,
    ) -> SemanticFallbackResult:
        return self._resolve_with_fallback(
            request=request,
            default_value="unknown",
            bound_value=_bounded_unit,
            invoke_client=self._client.interpret_unit if self._client is not None else None,
        )

    def _resolve_with_fallback(
        self,
        *,
        request: (
            TableKindFallbackRequest
            | RowLabelFallbackRequest
            | CurrencyFallbackRequest
            | UnitFallbackRequest
        ),
        default_value: str,
        bound_value: Callable[[str], str],
        invoke_client: Callable[[object], SemanticFallbackResult] | None,
    ) -> SemanticFallbackResult:
        deterministic_result = self._deterministic_result(
            deterministic_candidates=request.deterministic_candidates,
            default_value=default_value,
            bound_value=bound_value,
        )
        if invoke_client is None or not request.ambiguity_reason:
            return deterministic_result
        try:
            with self._semaphore:
                result = invoke_client(request)
        except Exception:
            LOGGER.warning(
                "Semantic fallback invocation failed; continuing with deterministic semantics.",
                exc_info=True,
            )
            return deterministic_result
        return SemanticFallbackResult(
            value=bound_value(result.value),
            semantic_source=result.semantic_source,
            semantic_confidence=result.semantic_confidence,
            fallback_reason=result.fallback_reason,
        )

    @staticmethod
    def _deterministic_result(
        *,
        deterministic_candidates: tuple[str, ...],
        default_value: str,
        bound_value: Callable[[str], str],
    ) -> SemanticFallbackResult:
        deterministic_value = (
            deterministic_candidates[0] if deterministic_candidates else default_value
        )
        return SemanticFallbackResult(
            value=bound_value(deterministic_value),
            semantic_source="deterministic",
            semantic_confidence=None,
            fallback_reason=None,
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
