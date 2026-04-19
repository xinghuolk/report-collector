from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from financial_report_analysis.models.facts import CandidateFact, CanonicalFact


class ConflictResolver:
    def resolve(
        self,
        normalized_candidates: Iterable[CandidateFact],
    ) -> list[CanonicalFact]:
        grouped_candidates: dict[tuple[str, str, str, str, str, str], list[CandidateFact]] = (
            defaultdict(list)
        )
        for candidate in normalized_candidates:
            grouped_candidates[self._business_key(candidate)].append(candidate)

        canonical_facts: list[CanonicalFact] = []
        for business_key in sorted(grouped_candidates):
            winner = max(
                grouped_candidates[business_key],
                key=self._priority_key,
            )
            canonical_facts.append(
                CanonicalFact(
                    fact_id=f"canonical::{winner.fact_id}",
                    metric_id=winner.metric_id,
                    metric_label_raw=winner.metric_label_raw,
                    statement_type=winner.statement_type,
                    entity_scope=winner.entity_scope,
                    comparison_axis=winner.comparison_axis,
                    adjustment_basis=winner.adjustment_basis,
                    period_id=winner.period_id,
                    currency=winner.currency,
                    raw_value=winner.raw_value,
                    numeric_value=winner.numeric_value,
                    raw_unit=winner.raw_unit,
                    normalized_unit=winner.normalized_unit,
                    precision=winner.precision,
                    confidence=winner.confidence,
                    extensions=dict(winner.extensions),
                    source_candidate_fact_ids=[
                        candidate.fact_id for candidate in grouped_candidates[business_key]
                    ],
                    resolution_reason="highest_source_rank",
                    resolution_score=self._resolution_score(winner),
                    validation_flags=[],
                    quality_status="ok",
                    is_primary=True,
                    evidence_bundle_id=winner.evidence_bundle_id,
                )
            )
        return canonical_facts

    @staticmethod
    def _business_key(candidate: CandidateFact) -> tuple[str, str, str, str, str, str]:
        return (
            candidate.metric_id,
            candidate.period_id,
            candidate.entity_scope,
            candidate.comparison_axis,
            candidate.adjustment_basis,
            candidate.currency,
        )

    @staticmethod
    def _priority_key(candidate: CandidateFact) -> tuple[int, float, int, str]:
        source_rank_hint = candidate.source_rank_hint
        rank = source_rank_hint if source_rank_hint is not None else -1
        confidence = candidate.confidence if candidate.confidence is not None else -1.0
        return (rank, confidence, -candidate.page_index, candidate.fact_id)

    @staticmethod
    def _resolution_score(candidate: CandidateFact) -> float:
        rank = candidate.source_rank_hint if candidate.source_rank_hint is not None else 0
        confidence = candidate.confidence if candidate.confidence is not None else 0.0
        return confidence + float(rank)
