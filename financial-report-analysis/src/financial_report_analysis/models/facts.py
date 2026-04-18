from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from financial_report_analysis.models.common import Extensions

FactKind = Literal["candidate", "canonical", "derived"]
StatementType = Literal[
    "income_statement",
    "balance_sheet",
    "cash_flow_statement",
    "metrics",
]
EntityScope = Literal["consolidated", "parent", "segment", "other"]
ComparisonAxis = Literal["current", "prior", "period_end", "period_begin"]
AdjustmentBasis = Literal[
    "reported",
    "adjusted",
    "deducted",
    "parent_attributable",
    "other",
]


@dataclass(kw_only=True)
class BaseFact:
    fact_id: str
    fact_kind: FactKind
    metric_id: str
    metric_label_raw: str
    statement_type: StatementType
    entity_scope: EntityScope
    comparison_axis: ComparisonAxis
    adjustment_basis: AdjustmentBasis
    period_id: str
    currency: str
    raw_value: str | int | float | None
    numeric_value: int | float | None
    raw_unit: str | None
    normalized_unit: str | None
    precision: int | None
    confidence: float | None
    extensions: Extensions = field(default_factory=dict)


@dataclass(kw_only=True)
class CandidateFact(BaseFact):
    fact_kind: Literal["candidate"] = "candidate"
    document_id: str
    block_id: str
    page_index: int
    evidence_bundle_id: str
    table_id: str | None = None
    table_coord: str | None = None
    evidence_span: str | None = None
    snapshot_path: str | None = None
    extraction_method: str | None = None
    extraction_version: str | None = None
    source_rank_hint: int | None = None

    def __post_init__(self) -> None:
        if self.fact_kind != "candidate":
            raise ValueError("fact_kind must be candidate for CandidateFact")


@dataclass(kw_only=True)
class CanonicalFact(BaseFact):
    fact_kind: Literal["canonical"] = "canonical"
    source_candidate_fact_ids: list[str] = field(default_factory=list)
    resolution_reason: str | None = None
    resolution_score: float | None = None
    validation_flags: list[str] = field(default_factory=list)
    quality_status: str | None = None
    is_primary: bool = False
    evidence_bundle_id: str | None = None

    def __post_init__(self) -> None:
        if self.fact_kind != "canonical":
            raise ValueError("fact_kind must be canonical for CanonicalFact")

    @property
    def business_key(self) -> str:
        return "|".join(
            [
                self.metric_id,
                self.period_id,
                self.entity_scope,
                self.comparison_axis,
                self.adjustment_basis,
                self.currency,
            ]
        )
