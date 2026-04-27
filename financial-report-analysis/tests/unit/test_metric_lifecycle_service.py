from __future__ import annotations

import pytest

from financial_report_analysis.models import (
    MetricGovernanceDecision,
    MetricLifecycleCandidateLink,
    MetricLifecycleConceptIdentity,
    MetricLifecycleDecision,
    MetricLifecycleEntry,
)
from financial_report_analysis.registries import load_metric_registry
from financial_report_analysis.services.metric_lifecycle import (
    MetricLifecycleError,
    MetricLifecycleService,
)


class _Repository:
    def __init__(self) -> None:
        self.entries: dict[str, MetricLifecycleEntry] = {}
        self.decisions: dict[str, list[MetricLifecycleDecision]] = {}
        self.links: dict[str, MetricLifecycleCandidateLink] = {}
        self.phase2_decision: MetricGovernanceDecision | None = None

    def save_metric_lifecycle_entry(self, entry: MetricLifecycleEntry) -> str:
        self.entries[entry.lifecycle_entry_id] = entry
        return entry.lifecycle_entry_id

    def load_metric_lifecycle_entry(
        self,
        lifecycle_entry_id: str,
    ) -> MetricLifecycleEntry | None:
        return self.entries.get(lifecycle_entry_id)

    def load_metric_lifecycle_entry_by_concept(
        self,
        concept: MetricLifecycleConceptIdentity,
    ) -> MetricLifecycleEntry | None:
        for entry in self.entries.values():
            if entry.concept == concept:
                return entry
        return None

    def save_metric_lifecycle_decision(self, decision: MetricLifecycleDecision) -> str:
        self.decisions.setdefault(decision.lifecycle_entry_id, []).append(decision)
        return decision.decision_id

    def record_metric_lifecycle_decision(
        self,
        decision: MetricLifecycleDecision,
        updated_entry: MetricLifecycleEntry,
    ) -> str:
        self.decisions.setdefault(decision.lifecycle_entry_id, []).append(decision)
        self.entries[updated_entry.lifecycle_entry_id] = updated_entry
        return decision.decision_id

    def list_metric_lifecycle_decisions(
        self,
        lifecycle_entry_id: str,
    ) -> tuple[MetricLifecycleDecision, ...]:
        return tuple(
            sorted(
                self.decisions.get(lifecycle_entry_id, []),
                key=lambda item: (item.effective_at, item.created_at, item.decision_id),
            )
        )

    def load_latest_metric_lifecycle_decision(
        self,
        lifecycle_entry_id: str,
    ) -> MetricLifecycleDecision | None:
        decisions = self.list_metric_lifecycle_decisions(lifecycle_entry_id)
        return decisions[-1] if decisions else None

    def save_metric_lifecycle_candidate_link(
        self,
        link: MetricLifecycleCandidateLink,
    ) -> str:
        self.links[link.review_item_id] = link
        return link.candidate_link_id

    def load_metric_lifecycle_candidate_link(
        self,
        review_item_id: str,
    ) -> MetricLifecycleCandidateLink | None:
        return self.links.get(review_item_id)

    def list_metric_lifecycle_candidate_links(
        self,
        lifecycle_entry_id: str,
    ) -> tuple[MetricLifecycleCandidateLink, ...]:
        return tuple(
            link
            for link in self.links.values()
            if link.lifecycle_entry_id == lifecycle_entry_id
        )

    def load_latest_metric_governance_decision(
        self,
        review_item_id: str,
    ) -> MetricGovernanceDecision | None:
        del review_item_id
        return self.phase2_decision


class _FailingAtomicRepository(_Repository):
    def record_metric_lifecycle_decision(
        self,
        decision: MetricLifecycleDecision,
        updated_entry: MetricLifecycleEntry,
    ) -> str:
        del decision, updated_entry
        raise RuntimeError("atomic write failed")


def _concept() -> MetricLifecycleConceptIdentity:
    return MetricLifecycleConceptIdentity(
        issuer_id="HK_09987",
        metric_id="custom::ifrs::ecommerce::balance-sheet::root::customer-deposits",
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        accounting_standard="IFRS",
        industry_slug="ecommerce",
        parent_metric_id=None,
    )


def _entry() -> MetricLifecycleEntry:
    return MetricLifecycleEntry(
        lifecycle_entry_id="lifecycle:001",
        concept=_concept(),
        current_status="provisional",
        mapped_standard_metric_id=None,
        created_at="2026-04-27T10:00:00+00:00",
        updated_at="2026-04-27T10:00:00+00:00",
        created_by="reviewer@example.com",
    )


def _entry_with_status(
    *,
    lifecycle_entry_id: str = "lifecycle:001",
    current_status: str = "provisional",
    mapped_standard_metric_id: str | None = None,
    updated_at: str = "2026-04-27T10:00:00+00:00",
    concept: MetricLifecycleConceptIdentity | None = None,
) -> MetricLifecycleEntry:
    return MetricLifecycleEntry(
        lifecycle_entry_id=lifecycle_entry_id,
        concept=concept or _concept(),
        current_status=current_status,  # type: ignore[arg-type]
        mapped_standard_metric_id=mapped_standard_metric_id,
        created_at="2026-04-27T10:00:00+00:00",
        updated_at=updated_at,
        created_by="reviewer@example.com",
    )


def _link() -> MetricLifecycleCandidateLink:
    return MetricLifecycleCandidateLink(
        candidate_link_id="link:001",
        lifecycle_entry_id="lifecycle:001",
        review_item_id="review:001",
        artifact_id="artifact:001",
        issuer_id="HK_09987",
        fiscal_year=2025,
        report_type="annual",
        candidate_metric_id=_concept().metric_id,
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        evidence_bundle_id="bundle:001",
        created_at="2026-04-27T10:02:00+00:00",
        created_by="reviewer@example.com",
    )


def _decision(
    *,
    decision_id: str,
    action: str = "approve_custom",
    previous_status: str = "provisional",
    new_status: str = "approved_custom",
    target_metric_id: str | None = None,
    created_at: str = "2026-04-27T10:03:00+00:00",
    effective_at: str = "2026-04-27T10:03:00+00:00",
) -> MetricLifecycleDecision:
    return MetricLifecycleDecision(
        decision_id=decision_id,
        lifecycle_entry_id="lifecycle:001",
        action=action,  # type: ignore[arg-type]
        previous_status=previous_status,  # type: ignore[arg-type]
        new_status=new_status,  # type: ignore[arg-type]
        target_metric_id=target_metric_id,
        actor="reviewer@example.com",
        reason="Existing decision.",
        evidence_bundle_id="bundle:001",
        source_review_item_id="review:001",
        source_artifact_id="artifact:001",
        created_at=created_at,
        effective_at=effective_at,
    )


def test_service_records_lifecycle_decision_and_updates_entry_state() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())
    repository.save_metric_lifecycle_candidate_link(_link())

    decision = service.record_decision(
        lifecycle_entry_id="lifecycle:001",
        action="approve_custom",
        actor="reviewer@example.com",
        reason="Valid custom metric.",
        evidence_bundle_id="bundle:001",
        source_review_item_id="review:001",
        source_artifact_id="artifact:001",
        created_at="2026-04-27T10:03:00+00:00",
        effective_at="2026-04-27T10:03:00+00:00",
    )

    assert decision.previous_status == "provisional"
    assert decision.new_status == "approved_custom"
    assert repository.entries["lifecycle:001"].current_status == "approved_custom"


@pytest.mark.parametrize(
    ("action", "expected_status"),
    [
        ("approve_custom", "approved_custom"),
        ("map_to_standard", "mapped_to_standard"),
        ("deprecate", "deprecated"),
        ("blacklist", "blacklisted"),
    ],
)
def test_service_validates_all_action_status_transitions(
    action: str,
    expected_status: str,
) -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())
    repository.save_metric_lifecycle_candidate_link(_link())

    decision = service.record_decision(
        lifecycle_entry_id="lifecycle:001",
        action=action,  # type: ignore[arg-type]
        target_metric_id="accounts_receiv" if action == "map_to_standard" else None,
        actor="reviewer@example.com",
        reason="Valid lifecycle action.",
        evidence_bundle_id="bundle:001",
        source_review_item_id="review:001",
        source_artifact_id="artifact:001",
        created_at="2026-04-27T10:03:00+00:00",
        effective_at="2026-04-27T10:03:00+00:00",
    )

    assert decision.new_status == expected_status
    assert repository.entries["lifecycle:001"].current_status == expected_status


def test_service_validates_map_to_standard_target() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())
    repository.save_metric_lifecycle_candidate_link(_link())

    decision = service.record_decision(
        lifecycle_entry_id="lifecycle:001",
        action="map_to_standard",
        target_metric_id="accounts_receiv",
        actor="reviewer@example.com",
        reason="Maps to receivables.",
        evidence_bundle_id="bundle:001",
        source_review_item_id="review:001",
        source_artifact_id="artifact:001",
        created_at="2026-04-27T10:03:00+00:00",
        effective_at="2026-04-27T10:03:00+00:00",
    )

    assert decision.new_status == "mapped_to_standard"
    assert repository.entries["lifecycle:001"].mapped_standard_metric_id == "accounts_receiv"


def test_service_rejects_invalid_target_and_wrong_target_shape() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())

    with pytest.raises(MetricLifecycleError, match="target_metric_id is required"):
        service.record_decision(
            lifecycle_entry_id="lifecycle:001",
            action="map_to_standard",
            actor="reviewer@example.com",
            reason="Missing target.",
            evidence_bundle_id="bundle:001",
            created_at="2026-04-27T10:03:00+00:00",
            effective_at="2026-04-27T10:03:00+00:00",
        )

    with pytest.raises(MetricLifecycleError, match="target_metric_id is not allowed"):
        service.record_decision(
            lifecycle_entry_id="lifecycle:001",
            action="approve_custom",
            target_metric_id="accounts_receiv",
            actor="reviewer@example.com",
            reason="Wrong shape.",
            evidence_bundle_id="bundle:001",
            created_at="2026-04-27T10:03:00+00:00",
            effective_at="2026-04-27T10:03:00+00:00",
        )

    for action in ("deprecate", "blacklist"):
        with pytest.raises(MetricLifecycleError, match="target_metric_id is not allowed"):
            service.record_decision(
                lifecycle_entry_id="lifecycle:001",
                action=action,  # type: ignore[arg-type]
                target_metric_id="accounts_receiv",
                actor="reviewer@example.com",
                reason="Wrong shape.",
                evidence_bundle_id="bundle:001",
                created_at="2026-04-27T10:03:00+00:00",
                effective_at="2026-04-27T10:03:00+00:00",
            )

    with pytest.raises(MetricLifecycleError, match="supported standard metric"):
        service.record_decision(
            lifecycle_entry_id="lifecycle:001",
            action="map_to_standard",
            target_metric_id="custom_metric",
            actor="reviewer@example.com",
            reason="Unsupported target.",
            evidence_bundle_id="bundle:001",
            created_at="2026-04-27T10:03:00+00:00",
            effective_at="2026-04-27T10:03:00+00:00",
        )


def test_service_does_not_partially_write_decision_when_atomic_write_fails() -> None:
    repository = _FailingAtomicRepository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())
    repository.save_metric_lifecycle_candidate_link(_link())

    with pytest.raises(RuntimeError, match="atomic write failed"):
        service.record_decision(
            lifecycle_entry_id="lifecycle:001",
            action="approve_custom",
            actor="reviewer@example.com",
            reason="Valid custom metric.",
            evidence_bundle_id="bundle:001",
            source_review_item_id="review:001",
            source_artifact_id="artifact:001",
            created_at="2026-04-27T10:03:00+00:00",
            effective_at="2026-04-27T10:03:00+00:00",
        )

    assert repository.decisions == {}
    assert repository.entries["lifecycle:001"].current_status == "provisional"


def test_service_does_not_overwrite_denormalized_entry_state_for_backdated_decision() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(
        _entry_with_status(
            current_status="approved_custom",
            updated_at="2026-04-27T10:05:00+00:00",
        )
    )
    repository.save_metric_lifecycle_candidate_link(_link())
    repository.save_metric_lifecycle_decision(
        _decision(
            decision_id="decision:latest",
            previous_status="provisional",
            new_status="approved_custom",
            created_at="2026-04-27T10:05:00+00:00",
            effective_at="2026-04-27T10:05:00+00:00",
        )
    )

    decision = service.record_decision(
        lifecycle_entry_id="lifecycle:001",
        action="deprecate",
        actor="reviewer@example.com",
        reason="Historical correction.",
        evidence_bundle_id="bundle:001",
        source_review_item_id="review:001",
        source_artifact_id="artifact:001",
        created_at="2026-04-27T10:04:00+00:00",
        effective_at="2026-04-27T10:04:00+00:00",
    )

    state = service.load_state_by_concept(_concept())

    assert decision.new_status == "deprecated"
    assert repository.entries["lifecycle:001"].current_status == "approved_custom"
    assert state.entry is not None
    assert state.entry.current_status == "approved_custom"
    assert state.latest_decision is not None
    assert state.latest_decision.decision_id == "decision:latest"


def test_service_records_backdated_decision_previous_status_from_history_position() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(
        _entry_with_status(
            current_status="mapped_to_standard",
            mapped_standard_metric_id="accounts_receiv",
            updated_at="2026-04-27T10:05:00+00:00",
        )
    )
    repository.save_metric_lifecycle_candidate_link(_link())
    repository.save_metric_lifecycle_decision(
        _decision(
            decision_id="decision:latest",
            action="map_to_standard",
            previous_status="provisional",
            new_status="mapped_to_standard",
            target_metric_id="accounts_receiv",
            created_at="2026-04-27T10:05:00+00:00",
            effective_at="2026-04-27T10:05:00+00:00",
        )
    )

    decision = service.record_decision(
        lifecycle_entry_id="lifecycle:001",
        action="approve_custom",
        actor="reviewer@example.com",
        reason="Historical correction.",
        evidence_bundle_id="bundle:001",
        source_review_item_id="review:001",
        source_artifact_id="artifact:001",
        created_at="2026-04-27T10:04:00+00:00",
        effective_at="2026-04-27T10:04:00+00:00",
    )

    assert decision.previous_status == "provisional"
    assert decision.new_status == "approved_custom"
    assert repository.entries["lifecycle:001"].current_status == "mapped_to_standard"


def test_service_reads_state_by_concept_and_candidate_link() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())
    repository.save_metric_lifecycle_candidate_link(_link())

    state_by_concept = service.load_state_by_concept(_concept())
    state_by_review = service.load_state_by_review_item("review:001")

    assert state_by_concept.entry is not None
    assert state_by_review.entry == state_by_concept.entry
    assert state_by_review.candidate_link is not None


def test_phase2_decision_alone_does_not_create_lifecycle_state() -> None:
    repository = _Repository()
    repository.phase2_decision = MetricGovernanceDecision(
        decision_id="phase2:001",
        review_item_id="review:001",
        artifact_id="artifact:001",
        issuer_id="HK_09987",
        fiscal_year=2025,
        report_type="annual",
        metric_id=_concept().metric_id,
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        evidence_bundle_id="bundle:001",
        decision_type="map_to_standard",
        target_metric_id="accounts_receiv",
        reason="Advisory only.",
        actor="reviewer@example.com",
        created_at="2026-04-27T10:00:00+00:00",
    )
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())

    assert service.load_state_by_review_item("review:001").entry is None
    assert service.load_state_by_concept(_concept()).entry is None


def test_link_candidate_rejects_wrong_concept_binding() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())

    with pytest.raises(MetricLifecycleError, match="candidate link does not match lifecycle entry concept"):
        service.link_candidate(
            MetricLifecycleCandidateLink(
                candidate_link_id="link:bad",
                lifecycle_entry_id="lifecycle:001",
                review_item_id="review:bad",
                artifact_id="artifact:001",
                issuer_id="HK_09987",
                fiscal_year=2025,
                report_type="annual",
                candidate_metric_id="custom::other",
                raw_label="Other metric",
                normalized_label="other metric",
                statement_type="balance_sheet",
                evidence_bundle_id="bundle:001",
                created_at="2026-04-27T10:02:00+00:00",
                created_by="reviewer@example.com",
            )
        )


def test_link_candidate_rejects_rebinding_review_item_to_other_entry() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())
    other_concept = MetricLifecycleConceptIdentity(
        issuer_id="HK_09987",
        metric_id="custom::ifrs::ecommerce::balance-sheet::root::trade-payables",
        raw_label="Trade payables",
        normalized_label="trade payables",
        statement_type="balance_sheet",
        accounting_standard="IFRS",
        industry_slug="ecommerce",
        parent_metric_id=None,
    )
    repository.save_metric_lifecycle_entry(
        _entry_with_status(
            lifecycle_entry_id="lifecycle:002",
            concept=other_concept,
        )
    )
    service.link_candidate(_link())

    with pytest.raises(MetricLifecycleError, match="review item is already linked to a different lifecycle entry"):
        service.link_candidate(
            MetricLifecycleCandidateLink(
                candidate_link_id="link:002",
                lifecycle_entry_id="lifecycle:002",
                review_item_id="review:001",
                artifact_id="artifact:001",
                issuer_id="HK_09987",
                fiscal_year=2025,
                report_type="annual",
                candidate_metric_id=other_concept.metric_id,
                raw_label=other_concept.raw_label,
                normalized_label=other_concept.normalized_label,
                statement_type=other_concept.statement_type,
                evidence_bundle_id="bundle:001",
                created_at="2026-04-27T10:04:00+00:00",
                created_by="reviewer@example.com",
            )
        )


def test_service_rejects_unknown_action() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())

    with pytest.raises(MetricLifecycleError, match="unknown lifecycle action"):
        service.record_decision(
            lifecycle_entry_id="lifecycle:001",
            action="not_a_real_action",  # type: ignore[arg-type]
            actor="reviewer@example.com",
            reason="Invalid action.",
            evidence_bundle_id="bundle:001",
            created_at="2026-04-27T10:03:00+00:00",
            effective_at="2026-04-27T10:03:00+00:00",
        )


def test_service_requires_non_blank_evidence_or_source_review_item() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())

    with pytest.raises(
        MetricLifecycleError,
        match="evidence_bundle_id or source_review_item_id is required",
    ):
        service.record_decision(
            lifecycle_entry_id="lifecycle:001",
            action="approve_custom",
            actor="reviewer@example.com",
            reason="Missing usable evidence.",
            evidence_bundle_id="   ",
            source_review_item_id="",
            created_at="2026-04-27T10:03:00+00:00",
            effective_at="2026-04-27T10:03:00+00:00",
        )


def test_service_requires_source_review_item_to_link_to_same_entry() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())

    with pytest.raises(
        MetricLifecycleError,
        match="source_review_item_id must link to the lifecycle entry",
    ):
        service.record_decision(
            lifecycle_entry_id="lifecycle:001",
            action="approve_custom",
            actor="reviewer@example.com",
            reason="Unlinked review item.",
            source_review_item_id="review:missing",
            created_at="2026-04-27T10:03:00+00:00",
            effective_at="2026-04-27T10:03:00+00:00",
        )


def test_candidate_link_is_required_even_when_concept_identity_matches_phase2_decision() -> None:
    repository = _Repository()
    entry = _entry()
    repository.save_metric_lifecycle_entry(entry)
    repository.phase2_decision = MetricGovernanceDecision(
        decision_id="phase2:001",
        review_item_id="review:001",
        artifact_id="artifact:001",
        issuer_id="HK_09987",
        fiscal_year=2025,
        report_type="annual",
        metric_id=entry.concept.metric_id,
        raw_label=entry.concept.raw_label,
        normalized_label=entry.concept.normalized_label,
        statement_type=entry.concept.statement_type,
        evidence_bundle_id="bundle:001",
        decision_type="map_to_standard",
        target_metric_id="accounts_receiv",
        reason="Advisory only.",
        actor="reviewer@example.com",
        created_at="2026-04-27T10:00:00+00:00",
    )
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())

    state = service.load_state_by_review_item("review:001")

    assert state.entry is None
    assert service.load_state_by_concept(entry.concept).entry == entry
