from datetime import date

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
    fact = CandidateFact(metric_id="revenue")

    assert fact.fact_kind == "candidate"
    assert fact.extensions == {}


def test_evidence_bundle_primary_evidence_item_id_uses_first_item() -> None:
    evidence_item = EvidenceItem(evidence_item_id="item-1")
    bundle = EvidenceBundle(
        evidence_items=[evidence_item],
    )

    assert bundle.primary_evidence_item_id == "item-1"


def test_period_point_contract_exposes_as_of_date() -> None:
    period = Period(period_type=Period.POINT, as_of_date=date(2026, 4, 19))

    assert period.period_type == Period.POINT
    assert period.as_of_date == date(2026, 4, 19)
