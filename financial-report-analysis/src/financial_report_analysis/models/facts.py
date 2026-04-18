from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from financial_report_analysis.models.common import Extensions


@dataclass(kw_only=True)
class BaseFact:
    fact_kind: str
    metric_id: str
    period_id: str
    entity_scope: str
    comparison_axis: str
    adjustment_basis: str
    currency: str
    extensions: Extensions = field(default_factory=dict)


@dataclass(kw_only=True)
class CandidateFact(BaseFact):
    fact_kind: Literal["candidate"] = "candidate"

    def __post_init__(self) -> None:
        if self.fact_kind != "candidate":
            raise ValueError("fact_kind must be candidate for CandidateFact")


@dataclass(kw_only=True)
class CanonicalFact(BaseFact):
    fact_kind: Literal["canonical"] = "canonical"

    def __post_init__(self) -> None:
        if self.fact_kind != "canonical":
            raise ValueError("fact_kind must be canonical for CanonicalFact")

    @property
    def business_key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.metric_id,
            self.period_id,
            self.entity_scope,
            self.comparison_axis,
            self.adjustment_basis,
            self.currency,
        )
