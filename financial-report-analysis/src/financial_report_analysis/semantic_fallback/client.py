from __future__ import annotations

from typing import Protocol

from financial_report_analysis.semantic_fallback.models import (
    RowLabelFallbackRequest,
    SemanticFallbackResult,
    TableKindFallbackRequest,
)


class SemanticFallbackClient(Protocol):
    def classify_table_kind(
        self,
        request: TableKindFallbackRequest,
    ) -> SemanticFallbackResult: ...

    def normalize_row_label(
        self,
        request: RowLabelFallbackRequest,
    ) -> SemanticFallbackResult: ...
