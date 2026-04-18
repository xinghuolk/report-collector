from datetime import date

import pytest

from financial_report_analysis.models.evidence import EvidenceBundle, EvidenceItem
from financial_report_analysis.models.facts import CandidateFact, CanonicalFact
from financial_report_analysis.models.period import Period


def test_canonical_fact_business_key_matches_domain_identity() -> None:
    fact = CanonicalFact(
        metric_id="revenue",
        period_id="period-2024-fy",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        currency="CNY",
    )

    assert fact.business_key == (
        "revenue",
        "period-2024-fy",
        "consolidated",
        "current",
        "reported",
        "CNY",
    )


def test_candidate_fact_inherits_common_fact_contract() -> None:
    fact = CandidateFact(
        metric_id="revenue",
        period_id="period-2024-fy",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        currency="CNY",
    )

    assert fact.fact_kind == "candidate"
    assert fact.extensions == {}


def test_evidence_bundle_requires_primary_item_when_items_present() -> None:
    with pytest.raises(ValueError, match="primary_evidence_item_id"):
        EvidenceBundle(
            evidence_items=[EvidenceItem(evidence_item_id="item-1")],
        )


def test_evidence_bundle_requires_primary_item_to_match_contents() -> None:
    with pytest.raises(ValueError, match="primary_evidence_item_id"):
        EvidenceBundle(
            evidence_items=[EvidenceItem(evidence_item_id="item-1")],
            primary_evidence_item_id="item-2",
        )


def test_evidence_bundle_accepts_matching_primary_item() -> None:
    bundle = EvidenceBundle(
        evidence_items=[EvidenceItem(evidence_item_id="item-1")],
        primary_evidence_item_id="item-1",
    )

    assert bundle.primary_evidence_item_id == "item-1"


def test_period_point_contract_exposes_as_of_date() -> None:
    period = Period(period_type=Period.POINT, as_of_date=date(2026, 4, 19))

    assert period.period_type == Period.POINT
    assert period.as_of_date == date(2026, 4, 19)
