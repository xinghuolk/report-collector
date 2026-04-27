from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import uuid4

from financial_report_analysis.models import (
    MetricLifecycleAction,
    MetricLifecycleCandidateLink,
    MetricLifecycleConceptIdentity,
    MetricLifecycleDecision,
    MetricLifecycleEntry,
    MetricLifecycleState,
    MetricLifecycleStatus,
)
from financial_report_analysis.registries import MetricMappingRegistry, load_metric_registry

ACTION_STATUS_MAP: dict[MetricLifecycleAction, MetricLifecycleStatus] = {
    "approve_custom": "approved_custom",
    "map_to_standard": "mapped_to_standard",
    "deprecate": "deprecated",
    "blacklist": "blacklisted",
}


class MetricLifecycleError(ValueError):
    pass


class MetricLifecycleRepository(Protocol):
    def save_metric_lifecycle_entry(self, entry: MetricLifecycleEntry) -> str: ...

    def load_metric_lifecycle_entry(
        self,
        lifecycle_entry_id: str,
    ) -> MetricLifecycleEntry | None: ...

    def load_metric_lifecycle_entry_by_concept(
        self,
        concept: MetricLifecycleConceptIdentity,
    ) -> MetricLifecycleEntry | None: ...

    def save_metric_lifecycle_decision(self, decision: MetricLifecycleDecision) -> str: ...

    def record_metric_lifecycle_decision(
        self,
        decision: MetricLifecycleDecision,
        updated_entry: MetricLifecycleEntry,
    ) -> str: ...

    def list_metric_lifecycle_decisions(
        self,
        lifecycle_entry_id: str,
    ) -> tuple[MetricLifecycleDecision, ...]: ...

    def load_latest_metric_lifecycle_decision(
        self,
        lifecycle_entry_id: str,
    ) -> MetricLifecycleDecision | None: ...

    def save_metric_lifecycle_candidate_link(
        self,
        link: MetricLifecycleCandidateLink,
    ) -> str: ...

    def load_metric_lifecycle_candidate_link(
        self,
        review_item_id: str,
    ) -> MetricLifecycleCandidateLink | None: ...

    def list_metric_lifecycle_candidate_links(
        self,
        lifecycle_entry_id: str,
    ) -> tuple[MetricLifecycleCandidateLink, ...]: ...


class MetricLifecycleService:
    def __init__(
        self,
        repository: MetricLifecycleRepository,
        *,
        metric_registry: MetricMappingRegistry | None = None,
    ) -> None:
        self._repository = repository
        self._metric_registry = metric_registry or load_metric_registry()

    def create_or_load_entry(
        self,
        *,
        concept: MetricLifecycleConceptIdentity,
        actor: str | None,
        created_at: str | None = None,
    ) -> MetricLifecycleEntry:
        existing = self._repository.load_metric_lifecycle_entry_by_concept(concept)
        if existing is not None:
            return existing
        timestamp = created_at or _utc_now()
        entry = MetricLifecycleEntry(
            lifecycle_entry_id=build_metric_lifecycle_entry_id(concept),
            concept=concept,
            current_status="provisional",
            mapped_standard_metric_id=None,
            created_at=timestamp,
            updated_at=timestamp,
            created_by=actor,
        )
        self._repository.save_metric_lifecycle_entry(entry)
        return entry

    def link_candidate(self, link: MetricLifecycleCandidateLink) -> str:
        entry = self._repository.load_metric_lifecycle_entry(link.lifecycle_entry_id)
        if entry is None:
            raise MetricLifecycleError("lifecycle entry does not exist")
        if not _candidate_link_matches_entry(link, entry):
            raise MetricLifecycleError(
                "candidate link does not match lifecycle entry concept"
            )
        existing_link = self._repository.load_metric_lifecycle_candidate_link(
            link.review_item_id
        )
        if (
            existing_link is not None
            and existing_link.lifecycle_entry_id != link.lifecycle_entry_id
        ):
            raise MetricLifecycleError(
                "review item is already linked to a different lifecycle entry"
            )
        return self._repository.save_metric_lifecycle_candidate_link(link)

    def record_decision(
        self,
        *,
        lifecycle_entry_id: str,
        action: MetricLifecycleAction,
        actor: str,
        reason: str,
        target_metric_id: str | None = None,
        evidence_bundle_id: str | None = None,
        source_review_item_id: str | None = None,
        source_artifact_id: str | None = None,
        created_at: str | None = None,
        effective_at: str | None = None,
    ) -> MetricLifecycleDecision:
        entry = self._repository.load_metric_lifecycle_entry(lifecycle_entry_id)
        if entry is None:
            raise MetricLifecycleError("lifecycle entry does not exist")
        self._validate_decision_shape(
            action=action,
            target_metric_id=target_metric_id,
            actor=actor,
            reason=reason,
            evidence_bundle_id=evidence_bundle_id,
            source_review_item_id=source_review_item_id,
        )
        normalized_evidence_bundle_id = _normalized_optional_text(evidence_bundle_id)
        normalized_source_review_item_id = _normalized_optional_text(source_review_item_id)
        if normalized_source_review_item_id is not None:
            source_link = self._repository.load_metric_lifecycle_candidate_link(
                normalized_source_review_item_id
            )
            if (
                source_link is None
                or source_link.lifecycle_entry_id != lifecycle_entry_id
            ):
                raise MetricLifecycleError(
                    "source_review_item_id must link to the lifecycle entry"
                )
        timestamp = created_at or _utc_now()
        effective = effective_at or timestamp
        new_status = ACTION_STATUS_MAP[action]
        decision_id = f"metric-lifecycle-decision:{uuid4().hex}"
        decision_key = (effective, timestamp, decision_id)
        history = self._repository.list_metric_lifecycle_decisions(lifecycle_entry_id)
        decision = MetricLifecycleDecision(
            decision_id=decision_id,
            lifecycle_entry_id=lifecycle_entry_id,
            action=action,
            previous_status=_previous_status_for_decision(history, decision_key),
            new_status=new_status,
            target_metric_id=target_metric_id,
            actor=actor,
            reason=reason,
            evidence_bundle_id=normalized_evidence_bundle_id,
            source_review_item_id=normalized_source_review_item_id,
            source_artifact_id=source_artifact_id,
            created_at=timestamp,
            effective_at=effective,
        )
        latest = self._repository.load_latest_metric_lifecycle_decision(lifecycle_entry_id)
        if latest is None or _decision_sort_key(decision) > _decision_sort_key(latest):
            updated_entry = MetricLifecycleEntry(
                lifecycle_entry_id=entry.lifecycle_entry_id,
                concept=entry.concept,
                current_status=new_status,
                mapped_standard_metric_id=(
                    target_metric_id if new_status == "mapped_to_standard" else None
                ),
                created_at=entry.created_at,
                updated_at=timestamp,
                created_by=entry.created_by,
            )
        else:
            updated_entry = entry
        self._repository.record_metric_lifecycle_decision(decision, updated_entry)
        return decision

    def load_state_by_concept(
        self,
        concept: MetricLifecycleConceptIdentity,
    ) -> MetricLifecycleState:
        entry = self._repository.load_metric_lifecycle_entry_by_concept(concept)
        return self._state_for_entry(entry, candidate_link=None)

    def load_state_by_review_item(self, review_item_id: str) -> MetricLifecycleState:
        link = self._repository.load_metric_lifecycle_candidate_link(review_item_id)
        if link is None:
            return MetricLifecycleState(
                entry=None,
                latest_decision=None,
                candidate_link=None,
                decision_history=(),
            )
        entry = self._repository.load_metric_lifecycle_entry(link.lifecycle_entry_id)
        return self._state_for_entry(entry, candidate_link=link)

    def _state_for_entry(
        self,
        entry: MetricLifecycleEntry | None,
        *,
        candidate_link: MetricLifecycleCandidateLink | None,
    ) -> MetricLifecycleState:
        if entry is None:
            return MetricLifecycleState(
                entry=None,
                latest_decision=None,
                candidate_link=candidate_link,
                decision_history=(),
            )
        history = self._repository.list_metric_lifecycle_decisions(
            entry.lifecycle_entry_id,
        )
        latest = self._repository.load_latest_metric_lifecycle_decision(
            entry.lifecycle_entry_id,
        )
        return MetricLifecycleState(
            entry=entry,
            latest_decision=latest,
            candidate_link=candidate_link,
            decision_history=history,
        )

    def _validate_decision_shape(
        self,
        *,
        action: MetricLifecycleAction,
        target_metric_id: str | None,
        actor: str,
        reason: str,
        evidence_bundle_id: str | None,
        source_review_item_id: str | None,
    ) -> None:
        if action not in ACTION_STATUS_MAP:
            raise MetricLifecycleError("unknown lifecycle action")
        if not actor.strip():
            raise MetricLifecycleError("actor is required")
        if not reason.strip():
            raise MetricLifecycleError("reason is required")
        if (
            _normalized_optional_text(evidence_bundle_id) is None
            and _normalized_optional_text(source_review_item_id) is None
        ):
            raise MetricLifecycleError(
                "evidence_bundle_id or source_review_item_id is required"
            )
        if action == "map_to_standard":
            if target_metric_id is None:
                raise MetricLifecycleError("target_metric_id is required")
            if self._metric_registry.get_metric_definition(target_metric_id) is None:
                raise MetricLifecycleError(
                    "target_metric_id must be a supported standard metric"
                )
            return
        if target_metric_id is not None:
            raise MetricLifecycleError("target_metric_id is not allowed")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _normalized_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _candidate_link_matches_entry(
    link: MetricLifecycleCandidateLink,
    entry: MetricLifecycleEntry,
) -> bool:
    concept = entry.concept
    return (
        link.issuer_id == concept.issuer_id
        and link.candidate_metric_id == concept.metric_id
        and link.raw_label == concept.raw_label
        and link.normalized_label == concept.normalized_label
        and link.statement_type == concept.statement_type
    )


def _decision_sort_key(decision: MetricLifecycleDecision) -> tuple[str, str, str]:
    return (decision.effective_at, decision.created_at, decision.decision_id)


def _previous_status_for_decision(
    history: tuple[MetricLifecycleDecision, ...],
    decision_key: tuple[str, str, str],
) -> MetricLifecycleStatus:
    earlier_decisions = [
        decision for decision in history if _decision_sort_key(decision) < decision_key
    ]
    if not earlier_decisions:
        return "provisional"
    return earlier_decisions[-1].new_status


def build_metric_lifecycle_entry_id(concept: MetricLifecycleConceptIdentity) -> str:
    payload = {
        "issuer_id": concept.issuer_id,
        "metric_id": concept.metric_id,
        "statement_type": concept.statement_type,
        "accounting_standard": concept.accounting_standard,
        "industry_slug": concept.industry_slug,
        "parent_metric_key": concept.parent_metric_id or "root",
    }
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"metric-lifecycle:{digest}"
