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
FactFieldValue = str | int | float | None

_STATEMENT_TYPES = {
    "income_statement",
    "balance_sheet",
    "cash_flow_statement",
    "metrics",
}
_ENTITY_SCOPES = {"consolidated", "parent", "segment", "other"}
_COMPARISON_AXES = {"current", "prior", "period_end", "period_begin"}
_ADJUSTMENT_BASES = {
    "reported",
    "adjusted",
    "deducted",
    "parent_attributable",
    "other",
}


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
    raw_value: FactFieldValue
    numeric_value: int | float | None
    raw_unit: str | None
    normalized_unit: str | None
    precision: int | None
    confidence: float | None
    extensions: Extensions = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.statement_type not in _STATEMENT_TYPES:
            raise ValueError("statement_type is not a supported fact enum value")
        if self.entity_scope not in _ENTITY_SCOPES:
            raise ValueError("entity_scope is not a supported fact enum value")
        if self.comparison_axis not in _COMPARISON_AXES:
            raise ValueError("comparison_axis is not a supported fact enum value")
        if self.adjustment_basis not in _ADJUSTMENT_BASES:
            raise ValueError("adjustment_basis is not a supported fact enum value")


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
        super().__post_init__()
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
        super().__post_init__()
        if self.fact_kind != "canonical":
            raise ValueError("fact_kind must be canonical for CanonicalFact")
        if not self.source_candidate_fact_ids:
            raise ValueError("source_candidate_fact_ids must not be empty")
        if self.evidence_bundle_id is None:
            raise ValueError("evidence_bundle_id is required for CanonicalFact")

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


@dataclass(kw_only=True)
class DerivedFact(BaseFact):
    fact_kind: Literal["derived"] = "derived"
    source_canonical_fact_ids: list[str] = field(default_factory=list)
    derivation_type: str | None = None
    derivation_formula: str | None = None
    derivation_version: str | None = None
    validation_status: str | None = None
    consistency_check_against_fact_id: str | None = None
    evidence_bundle_id: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.fact_kind != "derived":
            raise ValueError("fact_kind must be derived for DerivedFact")
