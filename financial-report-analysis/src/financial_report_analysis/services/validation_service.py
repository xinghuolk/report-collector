from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from financial_report_analysis.models.facts import CanonicalFact, DerivedFact


@dataclass(frozen=True, slots=True)
class ValidationReport:
    overall_status: str
    canonical_fact_count: int
    derived_fact_count: int
    issues: tuple[str, ...] = ()


class ValidationService:
    def validate(
        self,
        canonical_facts: Iterable[CanonicalFact],
        derived_facts: Iterable[DerivedFact],
    ) -> ValidationReport:
        canonical_list = list(canonical_facts)
        derived_list = list(derived_facts)
        canonical_fact_ids = {fact.fact_id for fact in canonical_list}
        issues: list[str] = []

        if len({fact.fact_id for fact in canonical_list}) != len(canonical_list):
            issues.append("duplicate_canonical_fact_ids")
        if len({fact.fact_id for fact in derived_list}) != len(derived_list):
            issues.append("duplicate_derived_fact_ids")
        if any(not fact.source_candidate_fact_ids for fact in canonical_list):
            issues.append("canonical_fact_missing_lineage")
        if any(not fact.source_canonical_fact_ids for fact in derived_list):
            issues.append("derived_fact_missing_lineage")
        if any(
            source_id not in canonical_fact_ids
            for fact in derived_list
            for source_id in fact.source_canonical_fact_ids
        ):
            issues.append("derived_fact_references_missing_canonical_fact")

        if issues:
            overall_status = "review_required"
        elif canonical_list or derived_list:
            overall_status = "ok"
        else:
            overall_status = "review_required"

        return ValidationReport(
            overall_status=overall_status,
            canonical_fact_count=len(canonical_list),
            derived_fact_count=len(derived_list),
            issues=tuple(issues),
        )
