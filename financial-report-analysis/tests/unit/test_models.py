from datetime import date

import pytest

from financial_report_analysis import CandidateFact as RootCandidateFact
from financial_report_analysis import CanonicalFact as RootCanonicalFact
from financial_report_analysis.models import DocumentBlock, DerivedFact
from financial_report_analysis.models.evidence import EvidenceBundle, EvidenceItem
from financial_report_analysis.models.facts import CandidateFact, CanonicalFact
from financial_report_analysis.models.period import Period


def test_package_root_exports_core_fact_models() -> None:
    assert RootCandidateFact is CandidateFact
    assert RootCanonicalFact is CanonicalFact


def test_canonical_fact_business_key_is_stable_string() -> None:
    fact = CanonicalFact(
        fact_id="fact-1",
        fact_kind="canonical",
        metric_id="revenue",
        metric_label_raw="Revenue",
        statement_type="income_statement",
        period_id="period-2024-fy",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        currency="CNY",
        raw_value="1000",
        numeric_value=1000.0,
        raw_unit="CNY",
        normalized_unit="CNY",
        precision=0,
        confidence=0.99,
        source_candidate_fact_ids=["cand-1"],
        resolution_reason="single best match",
        resolution_score=0.95,
        validation_flags=["validated"],
        quality_status="approved",
        is_primary=True,
        evidence_bundle_id="bundle-1",
    )

    assert fact.business_key == "revenue|period-2024-fy|consolidated|current|reported|CNY"


@pytest.mark.parametrize("entity_scope", ["parent_company", "unknown", "review_required"])
def test_fact_accepts_p4a_entity_scope_values(entity_scope: str) -> None:
    fact = CanonicalFact(
        fact_id="fact-1",
        fact_kind="canonical",
        metric_id="revenue",
        metric_label_raw="Revenue",
        statement_type="income_statement",
        period_id="period-2024-fy",
        entity_scope=entity_scope,
        comparison_axis="current",
        adjustment_basis="reported",
        currency="CNY",
        raw_value="1000",
        numeric_value=1000.0,
        raw_unit="CNY",
        normalized_unit="CNY",
        precision=0,
        confidence=0.99,
        source_candidate_fact_ids=["cand-1"],
        resolution_reason="single best match",
        resolution_score=0.95,
        validation_flags=["validated"],
        quality_status="approved",
        is_primary=True,
        evidence_bundle_id="bundle-1",
    )

    assert fact.entity_scope == entity_scope


def test_canonical_fact_business_key_distinguishes_parent_company_scope() -> None:
    fact = CanonicalFact(
        fact_id="fact-1",
        fact_kind="canonical",
        metric_id="revenue",
        metric_label_raw="Revenue",
        statement_type="income_statement",
        period_id="period-2024-fy",
        entity_scope="parent_company",
        comparison_axis="current",
        adjustment_basis="reported",
        currency="CNY",
        raw_value="1000",
        numeric_value=1000.0,
        raw_unit="CNY",
        normalized_unit="CNY",
        precision=0,
        confidence=0.99,
        source_candidate_fact_ids=["cand-1"],
        resolution_reason="single best match",
        resolution_score=0.95,
        validation_flags=["validated"],
        quality_status="approved",
        is_primary=True,
        evidence_bundle_id="bundle-1",
    )

    assert fact.business_key == "revenue|period-2024-fy|parent_company|current|reported|CNY"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("statement_type", "invalid"),
        ("entity_scope", "invalid"),
        ("comparison_axis", "invalid"),
        ("adjustment_basis", "invalid"),
    ],
)
def test_fact_enum_values_are_rejected(field_name: str, value: str) -> None:
    kwargs = {
        "fact_id": "cand-1",
        "fact_kind": "candidate",
        "metric_id": "revenue",
        "metric_label_raw": "Revenue",
        "statement_type": "income_statement",
        "period_id": "period-2024-fy",
        "entity_scope": "consolidated",
        "comparison_axis": "current",
        "adjustment_basis": "reported",
        "currency": "CNY",
        "raw_value": "1000",
        "numeric_value": 1000.0,
        "raw_unit": "CNY",
        "normalized_unit": "CNY",
        "precision": 0,
        "confidence": 0.91,
        "document_id": "doc-1",
        "block_id": "block-1",
        "page_index": 3,
        "evidence_bundle_id": "bundle-1",
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError, match="supported fact enum value"):
        CandidateFact(**kwargs)


def test_candidate_fact_supports_richer_constructor_shape() -> None:
    fact = CandidateFact(
        fact_id="cand-1",
        fact_kind="candidate",
        metric_id="revenue",
        metric_label_raw="Revenue",
        statement_type="income_statement",
        period_id="period-2024-fy",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        currency="CNY",
        raw_value="1000",
        numeric_value=1000.0,
        raw_unit="CNY",
        normalized_unit="CNY",
        precision=0,
        confidence=0.91,
        document_id="doc-1",
        block_id="block-1",
        table_id="table-1",
        page_index=3,
        table_coord="A1:B2",
        evidence_bundle_id="bundle-1",
        evidence_span="Revenue row",
        snapshot_path="/tmp/revenue.png",
        extraction_method="table_parser",
        extraction_version="1.0",
        source_rank_hint=1,
    )

    assert fact.fact_kind == "candidate"
    assert fact.fact_id == "cand-1"
    assert fact.evidence_bundle_id == "bundle-1"
    assert fact.extensions == {}


def test_candidate_fact_rejects_incompatible_fact_kind() -> None:
    with pytest.raises(ValueError, match="CandidateFact"):
        CandidateFact(
            fact_id="cand-1",
            fact_kind="canonical",
            metric_id="revenue",
            metric_label_raw="Revenue",
            statement_type="income_statement",
            period_id="period-2024-fy",
            entity_scope="consolidated",
            comparison_axis="current",
            adjustment_basis="reported",
            currency="CNY",
            raw_value="1000",
            numeric_value=1000.0,
            raw_unit="CNY",
            normalized_unit="CNY",
            precision=0,
            confidence=0.91,
            document_id="doc-1",
            block_id="block-1",
            page_index=3,
            evidence_bundle_id="bundle-1",
        )


def test_canonical_fact_rejects_incompatible_fact_kind() -> None:
    with pytest.raises(ValueError, match="CanonicalFact"):
        CanonicalFact(
            fact_id="fact-1",
            fact_kind="candidate",
            metric_id="revenue",
            metric_label_raw="Revenue",
            statement_type="income_statement",
            period_id="period-2024-fy",
            entity_scope="consolidated",
            comparison_axis="current",
            adjustment_basis="reported",
            currency="CNY",
            raw_value="1000",
            numeric_value=1000.0,
            raw_unit="CNY",
            normalized_unit="CNY",
            precision=0,
            confidence=0.99,
            source_candidate_fact_ids=["cand-1"],
        )


def test_canonical_fact_rejects_empty_sources() -> None:
    with pytest.raises(ValueError, match="source_candidate_fact_ids"):
        CanonicalFact(
            fact_id="fact-1",
            fact_kind="canonical",
            metric_id="revenue",
            metric_label_raw="Revenue",
            statement_type="income_statement",
            period_id="period-2024-fy",
            entity_scope="consolidated",
            comparison_axis="current",
            adjustment_basis="reported",
            currency="CNY",
            raw_value="1000",
            numeric_value=1000.0,
            raw_unit="CNY",
            normalized_unit="CNY",
            precision=0,
            confidence=0.99,
            source_candidate_fact_ids=[],
            evidence_bundle_id="bundle-1",
        )


def test_canonical_fact_rejects_missing_evidence_bundle_id() -> None:
    with pytest.raises(ValueError, match="evidence_bundle_id"):
        CanonicalFact(
            fact_id="fact-1",
            fact_kind="canonical",
            metric_id="revenue",
            metric_label_raw="Revenue",
            statement_type="income_statement",
            period_id="period-2024-fy",
            entity_scope="consolidated",
            comparison_axis="current",
            adjustment_basis="reported",
            currency="CNY",
            raw_value="1000",
            numeric_value=1000.0,
            raw_unit="CNY",
            normalized_unit="CNY",
            precision=0,
            confidence=0.99,
            source_candidate_fact_ids=["cand-1"],
            evidence_bundle_id=None,
        )


def test_evidence_bundle_supports_richer_constructor_shape() -> None:
    item = EvidenceItem(
        evidence_item_id="item-1",
        document_id="doc-1",
        source_type="block",
        block_id="block-1",
        table_id="table-1",
        page_no=3,
        text_excerpt="Revenue row",
        table_coord="A1:B2",
        object_uri="file:///tmp/revenue.png",
        content_hash="hash-1",
        confidence=0.92,
        created_by="parser",
        schema_version="1",
    )
    bundle = EvidenceBundle(
        evidence_bundle_id="bundle-1",
        document_id="doc-1",
        bundle_type="fact_support",
        evidence_items=[item],
        primary_evidence_item_id="item-1",
        summary="Revenue row evidence",
        bundle_confidence=0.93,
        created_at="2026-04-19T00:00:00Z",
        schema_version="1",
    )

    assert bundle.evidence_bundle_id == "bundle-1"
    assert bundle.primary_evidence_item_id == "item-1"
    assert bundle.evidence_items[0].document_id == "doc-1"


def test_document_block_supports_richer_constructor_shape() -> None:
    block = DocumentBlock(
        block_id="block-1",
        document_id="doc-1",
        page_no=3,
        bbox=(0.0, 0.0, 10.0, 10.0),
        block_type="table",
        text="Revenue row",
        structured_repr={"kind": "table"},
        table_cells=[["Revenue", "1000"]],
        reading_order=1,
    )

    assert block.block_id == "block-1"
    assert block.page_no == 3
    assert block.table_cells == [["Revenue", "1000"]]


def test_evidence_bundle_rejects_primary_item_when_items_empty() -> None:
    with pytest.raises(ValueError, match="primary_evidence_item_id"):
        EvidenceBundle(
            evidence_bundle_id="bundle-1",
            document_id="doc-1",
            bundle_type="fact_support",
            primary_evidence_item_id="item-1",
        )


def test_evidence_bundle_requires_primary_item_to_match_contents() -> None:
    with pytest.raises(ValueError, match="primary_evidence_item_id"):
        EvidenceBundle(
            evidence_bundle_id="bundle-1",
            document_id="doc-1",
            bundle_type="fact_support",
            evidence_items=[
                EvidenceItem(
                    evidence_item_id="item-1",
                    document_id="doc-1",
                    source_type="block",
                )
            ],
            primary_evidence_item_id="item-2",
        )


def test_evidence_bundle_accepts_matching_primary_item() -> None:
    bundle = EvidenceBundle(
        evidence_bundle_id="bundle-1",
        document_id="doc-1",
        bundle_type="fact_support",
        evidence_items=[
            EvidenceItem(
                evidence_item_id="item-1",
                document_id="doc-1",
                source_type="block",
            )
        ],
        primary_evidence_item_id="item-1",
    )

    assert bundle.primary_evidence_item_id == "item-1"


def test_period_exposes_richer_domain_fields() -> None:
    period = Period(
        period_id="period-2024-fy",
        period_type=Period.POINT,
        reporting_scope="FY",
        fiscal_year=2024,
        fiscal_period_index=4,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        as_of_date=date(2024, 12, 31),
        calendar_year=2024,
        adjusted_status="ORIGINAL",
        disclosure_label_raw="FY2024",
        fiscal_label="FY2024",
        accounting_standard="IFRS",
        is_stub_period=False,
        period_metadata={"source": "annual_report"},
    )

    assert period.period_id == "period-2024-fy"
    assert period.period_type == Period.POINT
    assert period.reporting_scope == "FY"
    assert period.as_of_date == date(2024, 12, 31)
    assert period.period_metadata == {"source": "annual_report"}
    assert period.calendar_year == 2024
    assert period.fiscal_label == "FY2024"
    assert period.accounting_standard == "IFRS"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("reporting_scope", "INVALID"),
        ("adjusted_status", "INVALID"),
        ("accounting_standard", "INVALID"),
    ],
)
def test_period_enum_values_are_rejected(field_name: str, value: str) -> None:
    kwargs = {
        "period_id": "period-2024-fy",
        "period_type": Period.POINT,
        "as_of_date": date(2024, 12, 31),
    }
    kwargs[field_name] = value

    with pytest.raises(ValueError, match="supported period enum value"):
        Period(**kwargs)


def test_point_period_requires_as_of_date() -> None:
    with pytest.raises(ValueError, match="as_of_date"):
        Period(period_id="period-1", period_type=Period.POINT)


def test_derived_fact_supports_minimal_constructor_shape() -> None:
    fact = DerivedFact(
        fact_id="derived-1",
        fact_kind="derived",
        metric_id="revenue",
        metric_label_raw="Revenue",
        statement_type="income_statement",
        period_id="period-2024-fy",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        currency="CNY",
        raw_value="1000",
        numeric_value=1000.0,
        raw_unit="CNY",
        normalized_unit="CNY",
        precision=0,
        confidence=0.9,
        source_canonical_fact_ids=["fact-1"],
        derivation_type="ttm",
        derivation_formula="sum",
        derivation_version="1.0",
        validation_status="validated",
        consistency_check_against_fact_id="fact-2",
        evidence_bundle_id="bundle-1",
    )

    assert fact.fact_kind == "derived"
    assert fact.source_canonical_fact_ids == ["fact-1"]


def test_derived_fact_rejects_empty_sources() -> None:
    with pytest.raises(ValueError, match="source_canonical_fact_ids"):
        DerivedFact(
            fact_id="derived-1",
            fact_kind="derived",
            metric_id="revenue",
            metric_label_raw="Revenue",
            statement_type="income_statement",
            period_id="period-2024-fy",
            entity_scope="consolidated",
            comparison_axis="current",
            adjustment_basis="reported",
            currency="CNY",
            raw_value="1000",
            numeric_value=1000.0,
            raw_unit="CNY",
            normalized_unit="CNY",
            precision=0,
            confidence=0.9,
            source_canonical_fact_ids=[],
            derivation_type="ttm",
            evidence_bundle_id="bundle-1",
        )


def test_period_rejects_invalid_period_type() -> None:
    with pytest.raises(ValueError, match="period_type"):
        Period(period_id="period-1", period_type="INVALID")
