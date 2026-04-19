from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Iterable

from financial_report_analysis.models.facts import CanonicalFact, DerivedFact


@dataclass(frozen=True, slots=True)
class _QuarterlyFact:
    year: int
    quarter: int
    fact: CanonicalFact


class DerivationService:
    def derive_ttm(
        self,
        canonical_facts: Iterable[CanonicalFact],
    ) -> list[DerivedFact]:
        grouped_facts: dict[
            tuple[str, str, str, str, str, str],
            list[CanonicalFact],
        ] = defaultdict(list)
        for fact in canonical_facts:
            grouped_facts[self._ttm_group_key(fact)].append(fact)

        derived_facts: list[DerivedFact] = []
        for group_key in sorted(grouped_facts):
            quarterly_facts = self._quarterly_facts(grouped_facts[group_key])
            window = self._latest_valid_quarter_window(quarterly_facts)
            if window is None:
                continue
            ordered_facts = [quarterly_fact.fact for quarterly_fact in window]
            numeric_value = sum(fact.numeric_value or 0 for fact in ordered_facts)
            derived_facts.append(
                DerivedFact(
                    fact_id=f"derived::ttm::{ordered_facts[-1].fact_id}",
                    metric_id=ordered_facts[-1].metric_id,
                    metric_label_raw=ordered_facts[-1].metric_label_raw,
                    statement_type=ordered_facts[-1].statement_type,
                    entity_scope=ordered_facts[-1].entity_scope,
                    comparison_axis=ordered_facts[-1].comparison_axis,
                    adjustment_basis=ordered_facts[-1].adjustment_basis,
                    period_id=f"ttm::{ordered_facts[-1].period_id}",
                    currency=ordered_facts[-1].currency,
                    raw_value=numeric_value,
                    numeric_value=numeric_value,
                    raw_unit=ordered_facts[-1].raw_unit,
                    normalized_unit=ordered_facts[-1].normalized_unit,
                    precision=ordered_facts[-1].precision,
                    confidence=ordered_facts[-1].confidence,
                    extensions=dict(ordered_facts[-1].extensions),
                    source_canonical_fact_ids=[fact.fact_id for fact in ordered_facts],
                    derivation_type="ttm",
                    derivation_formula="sum(last_4_quarters)",
                    derivation_version="v1",
                    validation_status="ok",
                    evidence_bundle_id=ordered_facts[-1].evidence_bundle_id,
                )
            )
        return derived_facts

    @staticmethod
    def _ttm_group_key(fact: CanonicalFact) -> tuple[str, str, str, str, str, str]:
        return (
            fact.metric_id,
            fact.entity_scope,
            fact.comparison_axis,
            fact.adjustment_basis,
            fact.currency,
            fact.normalized_unit or "",
        )

    @staticmethod
    def _quarterly_facts(canonical_facts: list[CanonicalFact]) -> list[_QuarterlyFact]:
        quarterly_facts: list[_QuarterlyFact] = []
        for fact in canonical_facts:
            parsed = DerivationService._parse_quarter_period_id(fact.period_id)
            if parsed is None:
                return []
            quarterly_facts.append(
                _QuarterlyFact(year=parsed[0], quarter=parsed[1], fact=fact)
            )
        return quarterly_facts

    @staticmethod
    def _latest_valid_quarter_window(
        quarterly_facts: list[_QuarterlyFact],
    ) -> list[_QuarterlyFact] | None:
        ordered_quarters = sorted(quarterly_facts, key=lambda fact: (fact.year, fact.quarter))
        if len(ordered_quarters) < 4:
            return None

        for start_index in range(len(ordered_quarters) - 4, -1, -1):
            window = ordered_quarters[start_index : start_index + 4]
            if DerivationService._is_contiguous_quarter_window(window):
                return window
        return None

    @staticmethod
    def _is_contiguous_quarter_window(quarterly_window: list[_QuarterlyFact]) -> bool:
        if len(quarterly_window) != 4:
            return False
        for previous, current in zip(quarterly_window, quarterly_window[1:]):
            previous_index = previous.year * 4 + previous.quarter
            current_index = current.year * 4 + current.quarter
            if current_index - previous_index != 1:
                return False
        return True

    @staticmethod
    def _parse_quarter_period_id(period_id: str) -> tuple[int, int] | None:
        match = re.fullmatch(r"(?P<year>\d{4})Q(?P<quarter>[1-4])", period_id)
        if match is None:
            return None
        return int(match.group("year")), int(match.group("quarter"))
