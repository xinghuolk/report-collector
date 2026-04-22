from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from financial_report_analysis.models.facts import CandidateFact

SourceKind = Literal[
    "statement_row",
    "deterministic_note_disclosure",
    "llm_locator_assisted_note_disclosure",
    "summary_table",
    "derived",
]
SourcePolicy = Literal["supplement_only", "override_allowed", "review_required", "blocked"]
ConflictState = Literal[
    "none",
    "scope_not_surfaced",
    "scope_conflict",
    "source_conflict",
    "review_required",
    "blocked",
]

_SOURCE_KINDS: set[str] = {
    "statement_row",
    "deterministic_note_disclosure",
    "llm_locator_assisted_note_disclosure",
    "summary_table",
    "derived",
}
_SOURCE_POLICIES: set[str] = {
    "supplement_only",
    "override_allowed",
    "review_required",
    "blocked",
}


@dataclass(frozen=True, slots=True)
class ReviewPacket:
    document_id: str
    period_id: str
    metric_id: str
    entity_scope: str
    source_kind: SourceKind
    source_policy: SourcePolicy
    conflict_state: ConflictState
    candidate_value: float | int | None
    competing_candidate_values: tuple[float | int | None, ...]
    evidence_bundle_id: str | None
    resolution_reason: str
    review_reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "period_id": self.period_id,
            "metric_id": self.metric_id,
            "entity_scope": self.entity_scope,
            "source_kind": self.source_kind,
            "source_policy": self.source_policy,
            "conflict_state": self.conflict_state,
            "candidate_value": self.candidate_value,
            "competing_candidate_values": list(self.competing_candidate_values),
            "evidence_bundle_id": self.evidence_bundle_id,
            "resolution_reason": self.resolution_reason,
            "review_reason": self.review_reason,
        }


def candidate_source_kind(candidate: CandidateFact) -> SourceKind:
    extension_source_kind = candidate.extensions.get("source_kind")
    if isinstance(extension_source_kind, str) and extension_source_kind in _SOURCE_KINDS:
        return cast(SourceKind, extension_source_kind)

    table_kind = candidate.extensions.get("table_kind")
    semantic_source = candidate.extensions.get("semantic_source")

    if candidate.extraction_method == "note_disclosure" or table_kind == "note_disclosure":
        if semantic_source == "llm_fallback":
            return "llm_locator_assisted_note_disclosure"
        return "deterministic_note_disclosure"

    if table_kind in {"key_metrics", "metrics", "summary_table"}:
        return "summary_table"

    return "statement_row"


def candidate_source_policy(candidate: CandidateFact) -> SourcePolicy:
    extension_source_policy = candidate.extensions.get("source_policy")
    if isinstance(extension_source_policy, str) and extension_source_policy in _SOURCE_POLICIES:
        return cast(SourcePolicy, extension_source_policy)
    return "supplement_only"

