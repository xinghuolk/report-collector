from __future__ import annotations

from financial_report_analysis.p5.governance_policy import (
    DownstreamGovernanceDecision,
    evaluate_downstream_fact_consumption,
    is_downstream_consumable_fact,
)


def _fact(metric_governance: object | None) -> dict[str, object]:
    extensions: dict[str, object] = {"period_scope": "duration"}
    if metric_governance is not None:
        extensions["metric_governance"] = metric_governance
    return {
        "fact_id": "fact-1",
        "metric_id": "revenue",
        "extensions": extensions,
    }


def test_standard_metric_is_downstream_consumable() -> None:
    fact = _fact(
        {
            "registry_status": "standard",
            "metric_namespace": "standard",
            "review_required": False,
            "auto_analysis_allowed": True,
            "governance_reason": "standard_metric",
        }
    )

    decision = evaluate_downstream_fact_consumption(fact)

    assert decision == DownstreamGovernanceDecision(
        allowed=True,
        reason="auto_analysis_allowed",
        governance_metadata={
            "registry_status": "standard",
            "metric_namespace": "standard",
            "review_required": False,
            "auto_analysis_allowed": True,
            "governance_reason": "standard_metric",
        },
    )
    assert is_downstream_consumable_fact(fact) is True


def test_provisional_custom_metric_is_blocked() -> None:
    fact = _fact(
        {
            "registry_status": "provisional",
            "metric_namespace": "custom",
            "review_required": True,
            "auto_analysis_allowed": False,
            "governance_reason": "provisional_custom_metric",
        }
    )

    decision = evaluate_downstream_fact_consumption(fact)

    assert decision.allowed is False
    assert decision.reason == "auto_analysis_not_allowed"
    assert is_downstream_consumable_fact(fact) is False


def test_missing_governance_metadata_is_blocked() -> None:
    decision = evaluate_downstream_fact_consumption(_fact(None))

    assert decision == DownstreamGovernanceDecision(
        allowed=False,
        reason="missing_metric_governance",
        governance_metadata={},
    )


def test_malformed_governance_metadata_is_blocked() -> None:
    decision = evaluate_downstream_fact_consumption(_fact(["bad"]))

    assert decision == DownstreamGovernanceDecision(
        allowed=False,
        reason="malformed_metric_governance",
        governance_metadata={},
    )


def test_controlled_map_to_standard_consumption_is_allowed() -> None:
    fact = _fact(
        {
            "registry_status": "provisional",
            "metric_namespace": "custom",
            "review_required": True,
            "auto_analysis_allowed": False,
            "governance_reason": "mapped_lifecycle_decision",
            "lifecycle_consumption": {
                "source_review_item_id": "CN_601919_2025:candidate-1",
                "lifecycle_entry_id": "metric-lifecycle:1",
                "decision_id": "metric-lifecycle-decision:1",
                "decision_action": "map_to_standard",
                "source_candidate_metric_id": "custom::receivables",
                "target_metric_id": "accounts_receiv",
                "consumption_action": "map_to_standard",
            },
        }
    )

    decision = evaluate_downstream_fact_consumption(fact)

    assert decision.allowed is True
    assert decision.reason == "controlled_consumption:map_to_standard"
    assert is_downstream_consumable_fact(fact) is True


def test_blacklisted_or_deprecated_metric_is_blocked_even_with_auto_allowed_flag() -> None:
    for registry_status in ("blacklisted", "deprecated"):
        decision = evaluate_downstream_fact_consumption(
            _fact(
                {
                    "registry_status": registry_status,
                    "metric_namespace": "custom",
                    "review_required": True,
                    "auto_analysis_allowed": True,
                    "governance_reason": registry_status,
                }
            )
        )

        assert decision.allowed is False
        assert decision.reason == f"blocked_registry_status:{registry_status}"


def test_custom_namespace_is_blocked_without_controlled_consumption() -> None:
    decision = evaluate_downstream_fact_consumption(
        _fact(
            {
                "registry_status": "approved_custom",
                "metric_namespace": "custom",
                "review_required": False,
                "auto_analysis_allowed": True,
                "governance_reason": "approved_custom_metric",
            }
        )
    )

    assert decision.allowed is False
    assert decision.reason == "custom_namespace_without_controlled_consumption"
