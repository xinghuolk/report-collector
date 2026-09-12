from __future__ import annotations

from financial_report_analysis.models import MetricGovernanceDecision
from financial_report_analysis.storage.database import (
    create_sqlite_engine,
    initialize_database,
)
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository


def _decision(
    decision_id: str,
    *,
    review_item_id: str = "review:item:001",
    created_at: str = "2026-04-27T09:00:00+00:00",
) -> MetricGovernanceDecision:
    return MetricGovernanceDecision(
        decision_id=decision_id,
        review_item_id=review_item_id,
        artifact_id="artifact:CN_601919:2025:annual",
        issuer_id="CN_601919",
        fiscal_year=2025,
        report_type="annual",
        metric_id="metric:provisional:revenue_like",
        raw_label="营业总收入",
        normalized_label="total_revenue",
        statement_type="income_statement",
        evidence_bundle_id="evidence:bundle:001",
        decision_type="map_to_standard",
        target_metric_id="revenue",
        reason="Matches standard revenue line item.",
        actor="analyst@example.com",
        created_at=created_at,
    )


def test_repository_round_trips_metric_governance_decisions(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)
    first = _decision("decision:001")
    second = _decision(
        "decision:002",
        created_at="2026-04-27T10:00:00+00:00",
    )
    other_review_item = _decision(
        "decision:other",
        review_item_id="review:item:other",
        created_at="2026-04-27T11:00:00+00:00",
    )

    assert repository.save_metric_governance_decision(first) == first.decision_id
    assert repository.save_metric_governance_decision(second) == second.decision_id
    repository.save_metric_governance_decision(other_review_item)

    assert repository.list_metric_governance_decisions(first.review_item_id) == (
        first,
        second,
    )


def test_repository_loads_latest_metric_governance_decision_by_created_at_and_id(
    tmp_path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)
    earlier = _decision("decision:001", created_at="2026-04-27T09:00:00+00:00")
    lower_id_same_timestamp = _decision(
        "decision:002",
        created_at="2026-04-27T10:00:00+00:00",
    )
    later_by_id_same_timestamp = _decision(
        "decision:003",
        created_at="2026-04-27T10:00:00+00:00",
    )

    repository.save_metric_governance_decision(later_by_id_same_timestamp)
    repository.save_metric_governance_decision(earlier)
    repository.save_metric_governance_decision(lower_id_same_timestamp)

    assert (
        repository.load_latest_metric_governance_decision(earlier.review_item_id)
        == later_by_id_same_timestamp
    )
    assert repository.load_latest_metric_governance_decision("missing") is None
