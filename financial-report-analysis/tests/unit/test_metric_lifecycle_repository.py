from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from financial_report_analysis.models import (
    MetricLifecycleCandidateLink,
    MetricLifecycleConceptIdentity,
    MetricLifecycleDecision,
    MetricLifecycleEntry,
)
from financial_report_analysis.p5.artifact_repository import P5ArtifactRepositoryError
from financial_report_analysis.storage.database import (
    create_sqlite_engine,
    initialize_database,
)
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository


def _concept(parent_metric_id: str | None = None) -> MetricLifecycleConceptIdentity:
    return MetricLifecycleConceptIdentity(
        issuer_id="HK_09987",
        metric_id="custom::ifrs::ecommerce::balance-sheet::root::customer-deposits",
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        accounting_standard="IFRS",
        industry_slug="ecommerce",
        parent_metric_id=parent_metric_id,
    )


def _entry(
    entry_id: str = "lifecycle:001",
    *,
    parent_metric_id: str | None = None,
) -> MetricLifecycleEntry:
    return MetricLifecycleEntry(
        lifecycle_entry_id=entry_id,
        concept=_concept(parent_metric_id),
        current_status="provisional",
        mapped_standard_metric_id=None,
        created_at="2026-04-27T10:00:00+00:00",
        updated_at="2026-04-27T10:00:00+00:00",
        created_by="reviewer@example.com",
    )


def _decision(
    decision_id: str,
    *,
    effective_at: str = "2026-04-27T10:01:00+00:00",
    created_at: str = "2026-04-27T10:01:00+00:00",
) -> MetricLifecycleDecision:
    return MetricLifecycleDecision(
        decision_id=decision_id,
        lifecycle_entry_id="lifecycle:001",
        action="map_to_standard",
        previous_status="provisional",
        new_status="mapped_to_standard",
        target_metric_id="accounts_receiv",
        actor="reviewer@example.com",
        reason="Matches standard accounts receivable.",
        evidence_bundle_id="bundle:001",
        source_review_item_id="review:001",
        source_artifact_id="artifact:001",
        created_at=created_at,
        effective_at=effective_at,
    )


def _link(link_id: str = "link:001") -> MetricLifecycleCandidateLink:
    return MetricLifecycleCandidateLink(
        candidate_link_id=link_id,
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


def _repository(tmp_path: Path) -> SqlAlchemyP5ArtifactRepository:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    return SqlAlchemyP5ArtifactRepository(engine)


def test_repository_round_trips_lifecycle_entry_by_id_and_concept(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    entry = _entry()

    assert repository.save_metric_lifecycle_entry(entry) == entry.lifecycle_entry_id
    assert repository.load_metric_lifecycle_entry(entry.lifecycle_entry_id) == entry
    assert repository.load_metric_lifecycle_entry_by_concept(_concept()) == entry
    assert repository.load_metric_lifecycle_entry("missing") is None


def test_repository_reuses_existing_root_concept_identity(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    entry = _entry()
    duplicate = _entry("lifecycle:duplicate")

    assert repository.save_metric_lifecycle_entry(entry) == entry.lifecycle_entry_id
    assert repository.save_metric_lifecycle_entry(duplicate) == entry.lifecycle_entry_id

    loaded = repository.load_metric_lifecycle_entry_by_concept(_concept())
    assert loaded is not None
    assert loaded.lifecycle_entry_id == entry.lifecycle_entry_id


def test_repository_rejects_colliding_lifecycle_entry_id_for_different_concept(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    original = _entry()
    existing_other_concept = replace(
        _entry("lifecycle:other"),
        concept=_concept("metric:parent:001"),
    )
    colliding_entry = replace(
        _entry(original.lifecycle_entry_id),
        concept=existing_other_concept.concept,
        updated_at="2026-04-27T10:04:00+00:00",
    )

    repository.save_metric_lifecycle_entry(original)
    repository.save_metric_lifecycle_entry(existing_other_concept)

    with pytest.raises(P5ArtifactRepositoryError, match="lifecycle entry id"):
        repository.save_metric_lifecycle_entry(colliding_entry)

    assert repository.load_metric_lifecycle_entry(original.lifecycle_entry_id) == original
    loaded = repository.load_metric_lifecycle_entry_by_concept(
        existing_other_concept.concept
    )
    assert loaded is not None
    assert loaded.lifecycle_entry_id == existing_other_concept.lifecycle_entry_id


def test_repository_preserves_created_fields_when_updating_existing_entry(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    original = _entry()
    updated = replace(
        original,
        current_status="approved_custom",
        updated_at="2026-04-27T10:05:00+00:00",
        created_at="2026-04-27T10:05:00+00:00",
        created_by="other-reviewer@example.com",
    )

    repository.save_metric_lifecycle_entry(original)
    repository.save_metric_lifecycle_entry(updated)

    assert repository.load_metric_lifecycle_entry(original.lifecycle_entry_id) == replace(
        updated,
        created_at=original.created_at,
        created_by=original.created_by,
    )


def test_repository_round_trips_lifecycle_candidate_link(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    entry = _entry()
    link = _link()

    repository.save_metric_lifecycle_entry(entry)
    assert repository.save_metric_lifecycle_candidate_link(link) == link.candidate_link_id

    assert repository.load_metric_lifecycle_candidate_link("review:001") == link
    assert repository.list_metric_lifecycle_candidate_links(entry.lifecycle_entry_id) == (
        link,
    )
    assert repository.load_metric_lifecycle_candidate_link("missing") is None


def test_repository_rejects_candidate_link_id_reuse_for_different_review_item(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    entry = _entry()
    link = _link()
    retargeted_link = replace(
        link,
        review_item_id="review:002",
        artifact_id="artifact:002",
        fiscal_year=2026,
        evidence_bundle_id="bundle:002",
        created_at="2026-04-27T10:03:00+00:00",
    )

    repository.save_metric_lifecycle_entry(entry)
    repository.save_metric_lifecycle_candidate_link(link)

    with pytest.raises(P5ArtifactRepositoryError, match="candidate link id"):
        repository.save_metric_lifecycle_candidate_link(retargeted_link)

    assert repository.load_metric_lifecycle_candidate_link("review:001") == link
    assert repository.load_metric_lifecycle_candidate_link("review:002") is None


def test_repository_rejects_lifecycle_candidate_link_for_missing_entry(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)

    with pytest.raises(P5ArtifactRepositoryError, match="missing lifecycle entry"):
        repository.save_metric_lifecycle_candidate_link(_link())

    assert repository.load_metric_lifecycle_candidate_link("review:001") is None


def test_repository_orders_lifecycle_decisions_deterministically(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.save_metric_lifecycle_entry(_entry())
    earlier = _decision("decision:001", effective_at="2026-04-27T10:00:00+00:00")
    same_effective_lower_id = _decision(
        "decision:002",
        effective_at="2026-04-27T10:05:00+00:00",
        created_at="2026-04-27T10:05:00+00:00",
    )
    latest_by_id = _decision(
        "decision:003",
        effective_at="2026-04-27T10:05:00+00:00",
        created_at="2026-04-27T10:05:00+00:00",
    )

    repository.save_metric_lifecycle_decision(latest_by_id)
    repository.save_metric_lifecycle_decision(earlier)
    repository.save_metric_lifecycle_decision(same_effective_lower_id)

    assert repository.list_metric_lifecycle_decisions("lifecycle:001") == (
        earlier,
        same_effective_lower_id,
        latest_by_id,
    )
    assert repository.load_latest_metric_lifecycle_decision("lifecycle:001") == latest_by_id


def test_repository_rejects_lifecycle_decision_for_missing_entry(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    with pytest.raises(P5ArtifactRepositoryError, match="missing lifecycle entry"):
        repository.save_metric_lifecycle_decision(_decision("decision:missing"))

    with pytest.raises(P5ArtifactRepositoryError, match="missing lifecycle entry"):
        repository.record_metric_lifecycle_decision(
            _decision("decision:atomic-missing"),
            replace(
                _entry(),
                current_status="approved_custom",
                updated_at="2026-04-27T10:03:00+00:00",
            ),
        )

    assert repository.list_metric_lifecycle_decisions("lifecycle:001") == ()


def test_repository_rejects_atomic_decision_when_updated_entry_id_mismatches(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    repository.save_metric_lifecycle_entry(_entry())
    other_entry = _entry("lifecycle:other", parent_metric_id="metric:parent:001")
    repository.save_metric_lifecycle_entry(other_entry)

    with pytest.raises(P5ArtifactRepositoryError, match="updated lifecycle entry"):
        repository.record_metric_lifecycle_decision(
            _decision("decision:mismatch"),
            replace(
                other_entry,
                current_status="approved_custom",
                updated_at="2026-04-27T10:03:00+00:00",
            ),
        )

    assert repository.list_metric_lifecycle_decisions("lifecycle:001") == ()
    assert repository.load_metric_lifecycle_entry("lifecycle:other") == other_entry


def test_repository_records_decision_and_entry_state_atomically(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.save_metric_lifecycle_entry(_entry())
    updated_entry = replace(
        _entry(),
        current_status="approved_custom",
        updated_at="2026-04-27T10:03:00+00:00",
    )
    decision = MetricLifecycleDecision(
        decision_id="decision:atomic",
        lifecycle_entry_id="lifecycle:001",
        action="approve_custom",
        previous_status="provisional",
        new_status="approved_custom",
        target_metric_id=None,
        actor="reviewer@example.com",
        reason="Valid custom metric.",
        evidence_bundle_id="bundle:001",
        source_review_item_id="review:001",
        source_artifact_id="artifact:001",
        created_at="2026-04-27T10:03:00+00:00",
        effective_at="2026-04-27T10:03:00+00:00",
    )

    assert (
        repository.record_metric_lifecycle_decision(decision, updated_entry)
        == decision.decision_id
    )
    assert repository.load_latest_metric_lifecycle_decision("lifecycle:001") == decision
    assert repository.load_metric_lifecycle_entry("lifecycle:001") == updated_entry
