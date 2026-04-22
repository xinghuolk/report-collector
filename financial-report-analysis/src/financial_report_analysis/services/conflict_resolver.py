from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from financial_report_analysis.models.facts import CandidateFact, CanonicalFact
from financial_report_analysis.models.governance import (
    ConflictState,
    ReviewPacket,
    SourcePolicy,
    candidate_source_kind,
    candidate_source_policy,
)


@dataclass(frozen=True, slots=True)
class ConflictResolutionResult:
    canonical_facts: list[CanonicalFact]
    review_packets: list[ReviewPacket]


class ConflictResolver:
    def resolve(
        self,
        normalized_candidates: Iterable[CandidateFact],
    ) -> list[CanonicalFact]:
        return self.resolve_with_review(normalized_candidates).canonical_facts

    def resolve_with_review(
        self,
        normalized_candidates: Iterable[CandidateFact],
    ) -> ConflictResolutionResult:
        grouped_candidates: dict[
            tuple[str, str, str, str, str, str], list[CandidateFact]
        ] = defaultdict(list)
        for candidate in normalized_candidates:
            grouped_candidates[self._business_key(candidate)].append(candidate)

        canonical_facts: list[CanonicalFact] = []
        review_packets: list[ReviewPacket] = []
        for business_key in sorted(grouped_candidates):
            winner, resolution_reason, validation_flags, packets = self._resolve_group(
                grouped_candidates[business_key]
            )
            canonical_facts.append(
                self._build_canonical_fact(
                    winner=winner,
                    source_candidate_fact_ids=[
                        candidate.fact_id
                        for candidate in grouped_candidates[business_key]
                    ],
                    resolution_reason=resolution_reason,
                    validation_flags=validation_flags,
                )
            )
            review_packets.extend(packets)
        return ConflictResolutionResult(
            canonical_facts=canonical_facts,
            review_packets=review_packets,
        )

    def _resolve_group(
        self,
        candidates: list[CandidateFact],
    ) -> tuple[CandidateFact, str, list[str], list[ReviewPacket]]:
        if len(candidates) == 1:
            winner = candidates[0]
            return winner, "highest_source_rank", [], []

        policies = {
            candidate.fact_id: candidate_source_policy(candidate)
            for candidate in candidates
        }
        kinds = {
            candidate.fact_id: candidate_source_kind(candidate)
            for candidate in candidates
        }
        blocked_candidates = [
            candidate
            for candidate in candidates
            if policies[candidate.fact_id] == "blocked"
        ]
        active_candidates = [
            candidate
            for candidate in candidates
            if policies[candidate.fact_id] != "blocked"
        ]

        if active_candidates:
            winner, resolution_reason, validation_flags, packets = (
                self._resolve_active_group(
                    candidates=candidates,
                    active_candidates=active_candidates,
                    blocked_candidates=blocked_candidates,
                    policies=policies,
                    kinds=kinds,
                )
            )
            return winner, resolution_reason, validation_flags, packets

        winner = self._best_candidate(candidates)
        return winner, "highest_source_rank", [], []

    def _resolve_active_group(
        self,
        *,
        candidates: list[CandidateFact],
        active_candidates: list[CandidateFact],
        blocked_candidates: list[CandidateFact],
        policies: dict[str, str],
        kinds: dict[str, str],
    ) -> tuple[CandidateFact, str, list[str], list[ReviewPacket]]:
        review_required_candidates = [
            candidate
            for candidate in active_candidates
            if policies[candidate.fact_id] == "review_required"
        ]
        override_allowed_candidates = [
            candidate
            for candidate in active_candidates
            if policies[candidate.fact_id] == "override_allowed"
        ]
        statement_candidates = [
            candidate
            for candidate in active_candidates
            if kinds[candidate.fact_id] == "statement_row"
        ]
        non_statement_active_candidates = [
            candidate
            for candidate in active_candidates
            if kinds[candidate.fact_id] != "statement_row"
        ]

        review_packets: list[ReviewPacket] = []
        validation_flags: list[str] = []

        if override_allowed_candidates:
            winner = self._best_candidate(override_allowed_candidates)
            resolution_reason = "source_policy_override_allowed"
        elif statement_candidates and non_statement_active_candidates:
            winner = self._best_candidate(statement_candidates)
            if review_required_candidates:
                validation_flags.append("source_conflict_review_required")
                resolution_reason = "source_conflict_review_required"
                review_packets.extend(
                    self._build_review_packets(
                        review_required_candidates,
                        competing_candidates=statement_candidates,
                        conflict_state="source_conflict",
                        resolution_reason=resolution_reason,
                        review_reason="review_required candidate conflicts with statement row",
                        policies=policies,
                    )
                )
            else:
                resolution_reason = "source_policy_supplement_only"
        elif review_required_candidates:
            non_review_active_candidates = [
                candidate
                for candidate in active_candidates
                if policies[candidate.fact_id] != "review_required"
            ]
            if non_review_active_candidates:
                winner = self._best_candidate(non_review_active_candidates)
                resolution_reason = self._resolution_reason_for_candidate(
                    winner,
                    policies,
                    statement_present=False,
                )
            else:
                winner = self._best_candidate(active_candidates)
                resolution_reason = "source_conflict_review_required"
        else:
            winner = self._best_candidate(active_candidates)
            resolution_reason = self._resolution_reason_for_candidate(
                winner,
                policies,
                statement_present=False,
            )

        if blocked_candidates and any(
            candidate not in blocked_candidates for candidate in candidates
        ):
            validation_flags.append("blocked_competing_candidate")
            review_packets.extend(
                self._build_review_packets(
                    blocked_candidates,
                    competing_candidates=[
                        candidate
                        for candidate in candidates
                        if candidate not in blocked_candidates
                    ],
                    conflict_state="blocked",
                    resolution_reason=resolution_reason,
                    review_reason="blocked candidate conflicted with eligible candidate",
                    policies=policies,
                )
            )
        elif blocked_candidates and not active_candidates:
            winner = self._best_candidate(blocked_candidates)
            resolution_reason = "highest_source_rank"

        return winner, resolution_reason, validation_flags, review_packets

    def _build_canonical_fact(
        self,
        *,
        winner: CandidateFact,
        source_candidate_fact_ids: list[str],
        resolution_reason: str,
        validation_flags: list[str],
    ) -> CanonicalFact:
        return CanonicalFact(
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
            source_candidate_fact_ids=source_candidate_fact_ids,
            resolution_reason=resolution_reason,
            resolution_score=self._resolution_score(winner),
            validation_flags=list(validation_flags),
            quality_status="review" if validation_flags else "ok",
            is_primary=not validation_flags,
            evidence_bundle_id=winner.evidence_bundle_id,
        )

    def _build_review_packets(
        self,
        candidates: list[CandidateFact],
        *,
        competing_candidates: list[CandidateFact],
        conflict_state: ConflictState,
        resolution_reason: str,
        review_reason: str,
        policies: dict[str, SourcePolicy],
    ) -> list[ReviewPacket]:
        competing_values = tuple(
            candidate.numeric_value for candidate in competing_candidates
        )
        packets: list[ReviewPacket] = []
        for candidate in candidates:
            packets.append(
                ReviewPacket(
                    document_id=candidate.document_id,
                    period_id=candidate.period_id,
                    metric_id=candidate.metric_id,
                    entity_scope=candidate.entity_scope,
                    source_kind=candidate_source_kind(candidate),
                    source_policy=policies[candidate.fact_id],
                    conflict_state=conflict_state,
                    candidate_value=candidate.numeric_value,
                    competing_candidate_values=competing_values,
                    evidence_bundle_id=candidate.evidence_bundle_id,
                    resolution_reason=resolution_reason,
                    review_reason=review_reason,
                )
            )
        return packets

    @staticmethod
    def _resolution_reason_for_candidate(
        candidate: CandidateFact,
        policies: dict[str, SourcePolicy],
        *,
        statement_present: bool,
    ) -> str:
        source_policy = policies[candidate.fact_id]
        if source_policy == "override_allowed":
            return "source_policy_override_allowed"
        if source_policy == "supplement_only":
            return (
                "source_policy_supplement_only"
                if statement_present
                else "highest_source_rank"
            )
        if source_policy == "review_required":
            return "source_conflict_review_required"
        return "highest_source_rank"

    @staticmethod
    def _best_candidate(candidates: list[CandidateFact]) -> CandidateFact:
        return max(candidates, key=ConflictResolver._priority_key)

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
    def _priority_key(
        candidate: CandidateFact,
    ) -> tuple[int, int, int, float, int, str]:
        source_rank_hint = candidate.source_rank_hint
        rank = source_rank_hint if source_rank_hint is not None else -1
        statement_rank = ConflictResolver._statement_rank(candidate)
        semantic_rank = ConflictResolver._semantic_rank(candidate)
        confidence = candidate.confidence if candidate.confidence is not None else -1.0
        return (
            rank,
            statement_rank,
            semantic_rank,
            confidence,
            -candidate.page_index,
            candidate.fact_id,
        )

    @staticmethod
    def _resolution_score(candidate: CandidateFact) -> float:
        rank = (
            candidate.source_rank_hint if candidate.source_rank_hint is not None else 0
        )
        statement_rank = ConflictResolver._statement_rank(candidate)
        semantic_rank = ConflictResolver._semantic_rank(candidate)
        confidence = candidate.confidence if candidate.confidence is not None else 0.0
        return (
            confidence
            + float(rank)
            + (statement_rank / 100.0)
            + (semantic_rank / 1000.0)
        )

    @staticmethod
    def _statement_rank(candidate: CandidateFact) -> int:
        table_kind = str(
            candidate.extensions.get("table_kind") or candidate.statement_type
        )
        if table_kind == "income_statement":
            return 40
        if table_kind == "cash_flow_statement":
            return 30
        if table_kind == "balance_sheet":
            return 20
        if table_kind in {"key_metrics", "metrics"}:
            return 10
        return 0

    @staticmethod
    def _semantic_rank(candidate: CandidateFact) -> int:
        semantic_source = str(candidate.extensions.get("semantic_source") or "")
        if semantic_source == "deterministic":
            return 2
        if semantic_source == "llm_fallback":
            return 1
        return 0
