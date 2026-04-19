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
    _DURATION_STATEMENT_TYPES = {
        "income_statement",
        "cash_flow_statement",
        "metrics",
    }

    def derive_ttm(
        self,
        canonical_facts: Iterable[CanonicalFact],
    ) -> list[DerivedFact]:
        grouped_facts: dict[
            tuple[str, str, str, str, str, str, str],
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
    def _ttm_group_key(
        fact: CanonicalFact,
    ) -> tuple[str, str, str, str, str, str, str]:
        return (
            fact.metric_id,
            fact.statement_type,
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
            parsed = DerivationService._parse_quarterly_fact(fact)
            if parsed is None:
                return []
            quarterly_facts.append(parsed)
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
    def _parse_quarterly_fact(fact: CanonicalFact) -> _QuarterlyFact | None:
        if fact.statement_type not in DerivationService._DURATION_STATEMENT_TYPES:
            return None

        metadata = fact.extensions
        period_type = str(metadata.get("period_type", "")).upper()
        if period_type and period_type != "DURATION":
            return None

        metadata_year = metadata.get("fiscal_year")
        metadata_scope = str(metadata.get("reporting_scope", "")).upper()
        metadata_quarter = DerivationService._quarter_from_metadata(
            year=metadata_year,
            reporting_scope=metadata_scope,
            period_type=period_type,
            metadata=metadata,
            fact=fact,
        )
        if metadata_quarter is not None:
            return metadata_quarter

        parsed = DerivationService._parse_legacy_period_id(fact.period_id)
        if parsed is not None:
            return _QuarterlyFact(year=parsed[0], quarter=parsed[1], fact=fact)

        parsed = DerivationService._parse_registry_period_id(fact)
        if parsed is not None:
            return _QuarterlyFact(year=parsed[0], quarter=parsed[1], fact=fact)

        return None

    @staticmethod
    def _quarter_from_metadata(
        *,
        year: object,
        reporting_scope: str,
        period_type: str,
        metadata: dict[str, object],
        fact: CanonicalFact,
    ) -> _QuarterlyFact | None:
        if not reporting_scope or year is None:
            return None

        quarter = DerivationService._scope_to_single_quarter(
            reporting_scope=reporting_scope,
            metadata=metadata,
        )
        if quarter is None:
            return None

        try:
            parsed_year = int(year)
        except (TypeError, ValueError):
            return None

        return _QuarterlyFact(year=parsed_year, quarter=quarter, fact=fact)

    @staticmethod
    def _parse_legacy_period_id(period_id: str) -> tuple[int, int] | None:
        match = re.fullmatch(r"(?P<year>\d{4})Q(?P<quarter>[1-4])(?:_SINGLE)?", period_id)
        if match is None:
            return None
        return int(match.group("year")), int(match.group("quarter"))

    @staticmethod
    def _parse_registry_period_id(fact: CanonicalFact) -> tuple[int, int] | None:
        match = re.fullmatch(
            r"duration::[^:]+::(?P<year>\d{4})::(?P<scope>[a-z0-9_]+)::[^:]+::[^:]+",
            fact.period_id,
        )
        if match is None:
            return None

        quarter = DerivationService._scope_to_single_quarter(
            reporting_scope=match.group("scope").upper(),
            metadata=fact.extensions,
        )
        if quarter is None:
            return None

        return int(match.group("year")), quarter

    @staticmethod
    def _scope_to_single_quarter(
        *,
        reporting_scope: str,
        metadata: dict[str, object],
    ) -> int | None:
        if reporting_scope in {"Q1", "Q2", "Q3", "Q4"}:
            return int(reporting_scope[-1])

        if reporting_scope == "FY" and DerivationService._is_single_quarter_metadata(
            metadata
        ):
            return 4

        return None

    @staticmethod
    def _is_single_quarter_metadata(metadata: dict[str, object]) -> bool:
        single_quarter_keys = (
            metadata.get("is_single_quarter"),
            metadata.get("single_quarter"),
            metadata.get("is_single_quarter_delta"),
            metadata.get("period_variant"),
        )
        return any(
            value is True or str(value).lower() == "single_quarter"
            for value in single_quarter_keys
        )
