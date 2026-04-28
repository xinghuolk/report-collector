from __future__ import annotations

from pathlib import Path

from financial_report_analysis.models import (
    MetricLifecycleRecomputeAudit,
    MetricLifecycleRecomputeAuditItem,
    MetricLifecycleRecomputeAuditSummary,
)
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.services.metric_governance_review import (
    build_review_item_id,
)
from financial_report_analysis.services.metric_lifecycle_consumption import (
    apply_metric_lifecycle_consumption,
)


def test_mapped_to_standard_creates_governed_canonical_fact() -> None:
    review_item_id = build_review_item_id("CN_601919_2025", "candidate-custom")
    candidate = _candidate_fact(
        "candidate-custom",
        metric_id="custom::cn::general::balance-sheet::root::deposit",
        numeric_value=100,
    )
    artifact = _artifact(candidate_facts=(candidate,), canonical_facts=())

    governed = apply_metric_lifecycle_consumption(
        artifact=artifact,
        audit=_audit(
            _audit_item(
                review_item_id,
                consumption_action="map_to_standard",
                target_metric_id="accounts_receiv",
            ),
        ),
    )

    assert governed is not artifact
    assert artifact.canonical_facts == ()
    assert len(governed.canonical_facts) == 1
    fact = governed.canonical_facts[0]
    assert fact["metric_id"] == "accounts_receiv"
    assert fact["numeric_value"] == 100
    assert fact["currency"] == "CNY"
    assert fact["raw_unit"] == "RMB'000"
    assert fact["normalized_unit"] == "currency_amount"
    assert fact["statement_type"] == "balance_sheet"
    assert fact["source_page"] == 12
    assert fact["source_table_id"] == "table-1"
    assert fact["evidence_bundle_id"] == "bundle-candidate-custom"
    assert fact["extensions"]["period_scope"] == "fy"
    assert fact["extensions"]["metric_governance"]["lifecycle_consumption"] == (
        _expected_provenance(review_item_id)
    )


def test_already_present_audit_items_do_not_duplicate_canonical_facts() -> None:
    review_item_id = build_review_item_id("CN_601919_2025", "candidate-custom")
    existing = _canonical_fact("accounts_receiv", numeric_value=100)
    artifact = _artifact(
        candidate_facts=(_candidate_fact("candidate-custom", numeric_value=100),),
        canonical_facts=(existing,),
    )

    governed = apply_metric_lifecycle_consumption(
        artifact=artifact,
        audit=_audit(
            _audit_item(
                review_item_id,
                consumption_action="already_present",
                conflict_state="already_present",
                target_metric_id="accounts_receiv",
            ),
        ),
    )

    assert governed.canonical_facts == (existing,)


def test_conflict_missing_candidate_and_missing_target_do_not_modify_facts() -> None:
    review_item_id = build_review_item_id("CN_601919_2025", "candidate-custom")
    conflict_id = build_review_item_id("CN_601919_2025", "candidate-conflict")
    missing_candidate_id = build_review_item_id("CN_601919_2025", "candidate-missing")
    missing_target_id = build_review_item_id("CN_601919_2025", "candidate-target")
    existing = _canonical_fact("accounts_receiv", numeric_value=999)
    artifact = _artifact(
        candidate_facts=(
            _candidate_fact("candidate-custom", numeric_value=100),
            _candidate_fact("candidate-conflict", numeric_value=200),
            _candidate_fact("candidate-target", numeric_value=300),
        ),
        canonical_facts=(existing,),
    )

    governed = apply_metric_lifecycle_consumption(
        artifact=artifact,
        audit=_audit(
            _audit_item(
                conflict_id,
                consumption_action="conflict",
                conflict_state="conflict",
                target_metric_id="accounts_receiv",
            ),
            _audit_item(
                missing_candidate_id,
                consumption_action="conflict",
                conflict_state="missing_candidate",
                target_metric_id="accounts_receiv",
            ),
            _audit_item(
                missing_target_id,
                consumption_action="conflict",
                conflict_state="missing_target",
                target_metric_id=None,
            ),
            _audit_item(
                review_item_id,
                consumption_action="none",
                target_metric_id="accounts_receiv",
            ),
        ),
    )

    assert governed.canonical_facts == (existing,)


def test_map_to_standard_does_not_overwrite_matching_target_canonical_fact() -> None:
    review_item_id = build_review_item_id("CN_601919_2025", "candidate-custom")
    existing = _canonical_fact("accounts_receiv", numeric_value=999)
    artifact = _artifact(
        candidate_facts=(_candidate_fact("candidate-custom", numeric_value=100),),
        canonical_facts=(existing,),
    )

    governed = apply_metric_lifecycle_consumption(
        artifact=artifact,
        audit=_audit(
            _audit_item(
                review_item_id,
                consumption_action="map_to_standard",
                target_metric_id="accounts_receiv",
            ),
        ),
    )

    assert governed.canonical_facts == (existing,)


def test_blacklisted_suppresses_matching_custom_canonical_facts() -> None:
    custom_metric_id = "custom::cn::general::income-statement::root::bad"
    review_item_id = build_review_item_id("CN_601919_2025", "candidate-bad")
    suppressed = _canonical_fact(
        custom_metric_id,
        numeric_value=100,
        statement_type="income_statement",
    )
    unrelated = _canonical_fact("accounts_receiv", numeric_value=200)
    artifact = _artifact(
        candidate_facts=(
            _candidate_fact(
                "candidate-bad",
                metric_id=custom_metric_id,
                numeric_value=100,
                statement_type="income_statement",
            ),
        ),
        canonical_facts=(suppressed, unrelated),
    )

    governed = apply_metric_lifecycle_consumption(
        artifact=artifact,
        audit=_audit(
            _audit_item(
                review_item_id,
                candidate_metric_id=custom_metric_id,
                consumption_action="suppress_blacklisted",
                target_metric_id=None,
            ),
        ),
    )

    assert governed.canonical_facts == (unrelated,)
    assert artifact.canonical_facts == (suppressed, unrelated)


def test_returns_new_artifact_and_does_not_mutate_original_nested_extensions() -> None:
    review_item_id = build_review_item_id("CN_601919_2025", "candidate-custom")
    candidate = _candidate_fact("candidate-custom", numeric_value=100)
    artifact = _artifact(candidate_facts=(candidate,), canonical_facts=())

    governed = apply_metric_lifecycle_consumption(
        artifact=artifact,
        audit=_audit(
            _audit_item(
                review_item_id,
                consumption_action="map_to_standard",
                target_metric_id="accounts_receiv",
            ),
        ),
    )

    assert governed is not artifact
    assert governed.candidate_facts == artifact.candidate_facts
    assert governed.derived_facts == artifact.derived_facts
    assert governed.validation_report == artifact.validation_report
    assert governed.review_packets == artifact.review_packets
    assert governed.quality_gate == artifact.quality_gate
    assert governed.missing_status == artifact.missing_status
    assert "lifecycle_consumption" not in candidate["extensions"]["metric_governance"]
    assert governed.canonical_facts[0]["extensions"] is not candidate["extensions"]
    assert governed.canonical_facts[0]["extensions"]["metric_governance"] is not (
        candidate["extensions"]["metric_governance"]
    )


def _expected_provenance(review_item_id: str) -> dict[str, str | None]:
    return {
        "source_review_item_id": review_item_id,
        "lifecycle_entry_id": "lifecycle:receivables",
        "decision_id": "decision:map",
        "decision_action": "map_to_standard",
        "source_candidate_metric_id": (
            "custom::cn::general::balance-sheet::root::deposit"
        ),
        "target_metric_id": "accounts_receiv",
        "consumption_action": "map_to_standard",
    }


def _audit(*items: MetricLifecycleRecomputeAuditItem) -> MetricLifecycleRecomputeAudit:
    return MetricLifecycleRecomputeAudit(
        items=items,
        summary=MetricLifecycleRecomputeAuditSummary(
            review_item_count=len(items),
            artifact_count=1,
            recompute_needed_count=len(items),
            dry_run_conflict_count=sum(
                1 for item in items if item.conflict_state == "conflict"
            ),
        ),
    )


def _audit_item(
    review_item_id: str,
    *,
    candidate_metric_id: str = "custom::cn::general::balance-sheet::root::deposit",
    consumption_action: str,
    target_metric_id: str | None,
    conflict_state: str = "none",
) -> MetricLifecycleRecomputeAuditItem:
    return MetricLifecycleRecomputeAuditItem(
        review_item_id=review_item_id,
        artifact_id="CN_601919_2025",
        issuer_id="CN_601919",
        fiscal_year=2025,
        report_type="annual",
        candidate_metric_id=candidate_metric_id,
        raw_label="Customer deposits",
        lifecycle_entry_id="lifecycle:receivables",
        current_status="mapped_to_standard",
        latest_decision_id="decision:map",
        latest_decision_action="map_to_standard",
        target_metric_id=target_metric_id,
        recompute_needed=True,
        consumption_action=consumption_action,  # type: ignore[arg-type]
        conflict_state=conflict_state,  # type: ignore[arg-type]
        reason="lifecycle decision affects automatic outputs",
    )


def _artifact(
    *,
    candidate_facts: tuple[dict[str, object], ...],
    canonical_facts: tuple[dict[str, object], ...],
) -> P5ExtractedArtifact:
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=Path("/tmp/CN_601919_2025.pdf"),
        source="fixture",
    )
    return P5ExtractedArtifact(
        artifact_id="CN_601919_2025",
        artifact_version="p5-v1",
        pipeline_version="pipeline-v1",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={},
        document_metadata={},
        candidate_facts=candidate_facts,
        canonical_facts=canonical_facts,
        derived_facts=({"fact_id": "derived-1"},),
        validation_report={"status": "ok"},
        review_packets=({"packet_id": "packet-1"},),
        quality_gate="pass",
        missing_status={"working_capital_missing_status": {"revenue": "present"}},
        created_at="2026-04-28T10:00:00+00:00",
    )


def _candidate_fact(
    fact_id: str,
    *,
    numeric_value: int,
    metric_id: str = "custom::cn::general::balance-sheet::root::deposit",
    statement_type: str = "balance_sheet",
) -> dict[str, object]:
    return {
        "fact_id": fact_id,
        "metric_id": metric_id,
        "numeric_value": numeric_value,
        "currency": "CNY",
        "raw_unit": "RMB'000",
        "normalized_unit": "currency_amount",
        "entity_scope": "consolidated",
        "statement_type": statement_type,
        "source_page": 12,
        "source_table_id": "table-1",
        "evidence_bundle_id": f"bundle-{fact_id}",
        "extensions": {
            "period_scope": "fy",
            "semantic_source": "deterministic",
            "metric_governance": {
                "registry_status": "provisional",
                "review_reason": "custom metric",
            },
        },
    }


def _canonical_fact(
    metric_id: str,
    *,
    numeric_value: int,
    statement_type: str = "balance_sheet",
) -> dict[str, object]:
    return {
        "fact_id": f"canonical-{metric_id}-{numeric_value}",
        "metric_id": metric_id,
        "numeric_value": numeric_value,
        "currency": "CNY",
        "raw_unit": "RMB'000",
        "normalized_unit": "currency_amount",
        "entity_scope": "consolidated",
        "statement_type": statement_type,
        "evidence_bundle_id": f"bundle-{metric_id}",
        "extensions": {"period_scope": "fy"},
    }
