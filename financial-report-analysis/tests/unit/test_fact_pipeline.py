from financial_report_analysis.models.evidence import EvidenceBundle, EvidenceItem
from financial_report_analysis.models.facts import CandidateFact
from financial_report_analysis.models.facts import CanonicalFact
from financial_report_analysis.models.facts import DerivedFact
from financial_report_analysis.pipeline import analyze_report
from financial_report_analysis.services.conflict_resolver import ConflictResolver
from financial_report_analysis.services.derivation_service import DerivationService
from financial_report_analysis.services.fact_normalizer import FactNormalizer
from financial_report_analysis.services.validation_service import ValidationService
from financial_report_analysis.storage.repositories import (
    EvidenceBundleItemLink,
    InMemoryEvidenceRepository,
)


def _candidate(
    *,
    fact_id: str,
    period_id: str,
    source_rank_hint: int | None,
    numeric_value: float,
    statement_type: str = "income_statement",
    currency: str = "CNY",
    raw_unit: str = "unit",
    extensions: dict[str, object] | None = None,
) -> CandidateFact:
    return CandidateFact(
        fact_id=fact_id,
        metric_id="raw_revenue",
        metric_label_raw="Revenue",
        statement_type=statement_type,
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        period_id=period_id,
        currency=currency,
        raw_value=numeric_value,
        numeric_value=numeric_value,
        raw_unit=raw_unit,
        normalized_unit=None,
        precision=0,
        confidence=0.9,
        extensions=extensions or {},
        document_id="doc-1",
        block_id="block-1",
        page_index=0,
        evidence_bundle_id="bundle-1",
        source_rank_hint=source_rank_hint,
    )


def test_fact_pipeline_normalizes_metric_and_unit() -> None:
    normalizer = FactNormalizer()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-1",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=2.0,
                raw_unit="RMB'000",
            )
        ]
    )

    fact = normalized[0]
    assert fact.metric_id == "revenue"
    assert fact.numeric_value == 2000.0
    assert fact.currency == "CNY"
    assert fact.normalized_unit == "CNY"


def test_fact_pipeline_normalizes_chinese_revenue_label() -> None:
    normalizer = FactNormalizer()

    chinese_candidate = CandidateFact(
        **{
            **_candidate(
                fact_id="candidate-cn-1",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=100.0,
            ).__dict__,
            "metric_label_raw": "营业收入",
        }
    )

    normalized = normalizer.normalize_candidates([chinese_candidate])

    assert normalized[0].metric_id == "revenue"


def test_conflict_resolver_keeps_highest_priority_candidate() -> None:
    normalizer = FactNormalizer()
    resolver = ConflictResolver()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-low",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=100.0,
            ),
            _candidate(
                fact_id="candidate-high",
                period_id="2024Q1",
                source_rank_hint=5,
                numeric_value=200.0,
            ),
        ]
    )

    canonical_facts = resolver.resolve(normalized)
    assert len(canonical_facts) == 1
    canonical = canonical_facts[0]
    assert canonical.numeric_value == 200.0
    assert canonical.fact_id == "canonical::candidate-high"
    assert canonical.source_candidate_fact_ids == ["candidate-low", "candidate-high"]
    assert canonical.resolution_reason == "highest_source_rank"
    assert canonical.quality_status == "ok"
    assert canonical.evidence_bundle_id == "bundle-1"


def test_derivation_service_yields_ttm_fact_with_lineage() -> None:
    normalizer = FactNormalizer()
    resolver = ConflictResolver()
    derivation_service = DerivationService()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-q1",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=100.0,
            ),
            _candidate(
                fact_id="candidate-q2",
                period_id="2024Q2",
                source_rank_hint=1,
                numeric_value=200.0,
            ),
            _candidate(
                fact_id="candidate-q3",
                period_id="2024Q3",
                source_rank_hint=1,
                numeric_value=300.0,
            ),
            _candidate(
                fact_id="candidate-q4",
                period_id="2024Q4",
                source_rank_hint=1,
                numeric_value=400.0,
            ),
        ]
    )

    canonical_facts = resolver.resolve(normalized)
    derived_facts = derivation_service.derive_ttm(canonical_facts)

    assert len(derived_facts) == 1
    derived = derived_facts[0]
    assert derived.derivation_type == "ttm"
    assert derived.derivation_formula == "sum(last_4_quarters)"
    assert derived.derivation_version == "v1"
    assert derived.validation_status == "ok"
    assert derived.numeric_value == 1000.0
    assert derived.source_canonical_fact_ids == [
        "canonical::candidate-q1",
        "canonical::candidate-q2",
        "canonical::candidate-q3",
        "canonical::candidate-q4",
    ]


def test_derivation_service_rejects_mixed_period_shapes_for_ttm() -> None:
    normalizer = FactNormalizer()
    resolver = ConflictResolver()
    derivation_service = DerivationService()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-q1",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=100.0,
            ),
            _candidate(
                fact_id="candidate-h1",
                period_id="2024H1",
                source_rank_hint=1,
                numeric_value=200.0,
            ),
            _candidate(
                fact_id="candidate-q3",
                period_id="2024Q3",
                source_rank_hint=1,
                numeric_value=300.0,
            ),
            _candidate(
                fact_id="candidate-fy",
                period_id="2024FY",
                source_rank_hint=1,
                numeric_value=400.0,
            ),
        ]
    )

    canonical_facts = resolver.resolve(normalized)
    derived_facts = derivation_service.derive_ttm(canonical_facts)

    assert derived_facts == []


def test_derivation_service_uses_latest_valid_four_quarter_window() -> None:
    normalizer = FactNormalizer()
    resolver = ConflictResolver()
    derivation_service = DerivationService()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-2023q4",
                period_id="2023Q4",
                source_rank_hint=1,
                numeric_value=10.0,
            ),
            _candidate(
                fact_id="candidate-2024q1",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=20.0,
            ),
            _candidate(
                fact_id="candidate-2024q2",
                period_id="2024Q2",
                source_rank_hint=1,
                numeric_value=30.0,
            ),
            _candidate(
                fact_id="candidate-2024q3",
                period_id="2024Q3",
                source_rank_hint=1,
                numeric_value=40.0,
            ),
            _candidate(
                fact_id="candidate-2024q4",
                period_id="2024Q4",
                source_rank_hint=1,
                numeric_value=50.0,
            ),
        ]
    )

    canonical_facts = resolver.resolve(normalized)
    derived_facts = derivation_service.derive_ttm(canonical_facts)

    assert len(derived_facts) == 1
    derived = derived_facts[0]
    assert derived.numeric_value == 140.0
    assert derived.source_canonical_fact_ids == [
        "canonical::candidate-2024q1",
        "canonical::candidate-2024q2",
        "canonical::candidate-2024q3",
        "canonical::candidate-2024q4",
    ]


def test_derivation_service_accepts_registry_period_ids_with_period_metadata() -> None:
    normalizer = FactNormalizer()
    resolver = ConflictResolver()
    derivation_service = DerivationService()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-q1",
                period_id="duration::ifrs::2024::q1::2024-01-01::2024-03-31",
                source_rank_hint=1,
                numeric_value=10.0,
                extensions={
                    "period_type": "DURATION",
                    "reporting_scope": "Q1",
                    "fiscal_year": 2024,
                },
            ),
            _candidate(
                fact_id="candidate-q2",
                period_id="duration::ifrs::2024::q2::2024-04-01::2024-06-30",
                source_rank_hint=1,
                numeric_value=20.0,
                extensions={
                    "period_type": "DURATION",
                    "reporting_scope": "Q2",
                    "fiscal_year": 2024,
                },
            ),
            _candidate(
                fact_id="candidate-q3",
                period_id="duration::ifrs::2024::q3::2024-07-01::2024-09-30",
                source_rank_hint=1,
                numeric_value=30.0,
                extensions={
                    "period_type": "DURATION",
                    "reporting_scope": "Q3",
                    "fiscal_year": 2024,
                },
            ),
            _candidate(
                fact_id="candidate-q4",
                period_id="duration::ifrs::2024::fy::2024-01-01::2024-12-31",
                source_rank_hint=1,
                numeric_value=40.0,
                extensions={
                    "period_type": "DURATION",
                    "reporting_scope": "FY",
                    "fiscal_year": 2024,
                    "period_variant": "single_quarter",
                },
            ),
        ]
    )

    canonical_facts = resolver.resolve(normalized)
    derived_facts = derivation_service.derive_ttm(canonical_facts)

    assert len(derived_facts) == 1
    assert derived_facts[0].numeric_value == 100.0


def test_derivation_service_rejects_point_periods_and_mixed_statements() -> None:
    normalizer = FactNormalizer()
    resolver = ConflictResolver()
    derivation_service = DerivationService()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-q1",
                period_id="duration::ifrs::2024::q1::2024-01-01::2024-03-31",
                source_rank_hint=1,
                numeric_value=10.0,
                extensions={
                    "period_type": "DURATION",
                    "reporting_scope": "Q1",
                    "fiscal_year": 2024,
                },
            ),
            _candidate(
                fact_id="candidate-q2",
                period_id="duration::ifrs::2024::q2::2024-04-01::2024-06-30",
                source_rank_hint=1,
                numeric_value=20.0,
                extensions={
                    "period_type": "DURATION",
                    "reporting_scope": "Q2",
                    "fiscal_year": 2024,
                },
            ),
            _candidate(
                fact_id="candidate-point",
                period_id="duration::ifrs::2024::q3::2024-07-01::2024-09-30",
                source_rank_hint=1,
                numeric_value=30.0,
                statement_type="balance_sheet",
                extensions={
                    "period_type": "POINT",
                    "reporting_scope": "Q3",
                    "fiscal_year": 2024,
                },
            ),
            _candidate(
                fact_id="candidate-q4",
                period_id="duration::ifrs::2024::fy::2024-01-01::2024-12-31",
                source_rank_hint=1,
                numeric_value=40.0,
                extensions={
                    "period_type": "DURATION",
                    "reporting_scope": "FY",
                    "fiscal_year": 2024,
                    "period_variant": "single_quarter",
                },
            ),
        ]
    )

    canonical_facts = resolver.resolve(normalized)
    derived_facts = derivation_service.derive_ttm(canonical_facts)

    assert derived_facts == []


def test_validation_service_returns_stable_report_shape() -> None:
    normalizer = FactNormalizer()
    resolver = ConflictResolver()
    derivation_service = DerivationService()
    validation_service = ValidationService()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-q1",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=100.0,
            ),
            _candidate(
                fact_id="candidate-q2",
                period_id="2024Q2",
                source_rank_hint=1,
                numeric_value=200.0,
            ),
            _candidate(
                fact_id="candidate-q3",
                period_id="2024Q3",
                source_rank_hint=1,
                numeric_value=300.0,
            ),
            _candidate(
                fact_id="candidate-q4",
                period_id="2024Q4",
                source_rank_hint=1,
                numeric_value=400.0,
            ),
        ]
    )

    canonical_facts = resolver.resolve(normalized)
    derived_facts = derivation_service.derive_ttm(canonical_facts)
    report = validation_service.validate(canonical_facts, derived_facts)

    assert report.overall_status == "ok"
    assert report.canonical_fact_count == 4
    assert report.derived_fact_count == 1
    assert report.issues == ()


def test_validation_service_requires_review_for_empty_input() -> None:
    report = ValidationService().validate(canonical_facts=[], derived_facts=[])

    assert report.overall_status == "review_required"
    assert report.canonical_fact_count == 0
    assert report.derived_fact_count == 0
    assert report.issues == ()


def test_validation_service_requires_review_for_dangling_derived_reference() -> None:
    canonical_fact = CanonicalFact(
        fact_id="canonical::candidate-q1",
        metric_id="revenue",
        metric_label_raw="Revenue",
        statement_type="income_statement",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        period_id="2024Q1",
        currency="CNY",
        raw_value=100.0,
        numeric_value=100.0,
        raw_unit="RMB'000",
        normalized_unit="CNY",
        precision=0,
        confidence=0.9,
        extensions={},
        source_candidate_fact_ids=["candidate-q1"],
        resolution_reason="highest_source_rank",
        resolution_score=1.0,
        validation_flags=[],
        quality_status="ok",
        is_primary=True,
        evidence_bundle_id="bundle-1",
    )
    dangling_derived_fact = DerivedFact(
        fact_id="derived::ttm::canonical::candidate-q1",
        metric_id="revenue",
        metric_label_raw="Revenue",
        statement_type="income_statement",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        period_id="ttm::2024Q4",
        currency="CNY",
        raw_value=100.0,
        numeric_value=100.0,
        raw_unit="RMB'000",
        normalized_unit="CNY",
        precision=0,
        confidence=0.9,
        extensions={},
        source_canonical_fact_ids=["canonical::candidate-q1", "canonical::missing"],
        derivation_type="ttm",
        derivation_formula="sum(last_4_quarters)",
        derivation_version="v1",
        validation_status="ok",
        evidence_bundle_id="bundle-1",
    )

    report = ValidationService().validate(
        canonical_facts=[canonical_fact],
        derived_facts=[dangling_derived_fact],
    )

    assert report.overall_status == "review_required"


def test_pipeline_returns_fact_sets_and_quality_gate() -> None:
    result = analyze_report(
        document_ref={"document_id": "doc-1", "market": "CN"},
        extracted_payload={
            "candidate_facts": [
                {
                    "fact_id": "cand-1",
                    "metric_id": "unknown",
                    "metric_label_raw": "营业收入",
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "CNY",
                    "raw_value": "1000",
                    "numeric_value": 1000.0,
                    "raw_unit": "万元",
                    "normalized_unit": None,
                    "precision": 2,
                    "confidence": 0.95,
                    "document_id": "doc-1",
                    "block_id": "block-1",
                    "table_id": "table-1",
                    "page_index": 1,
                    "table_coord": "A1",
                    "evidence_bundle_id": "bundle-1",
                    "evidence_span": "营业收入 1000",
                    "snapshot_path": None,
                    "extraction_method": "table_skill",
                    "extraction_version": "v1",
                    "source_rank_hint": 1,
                }
            ]
        },
    )

    assert result.canonical_fact_set_id == "doc-1:canonical:v1"
    assert result.derived_fact_set_id == "doc-1:derived:v1"
    assert result.validation_report_id == "doc-1:validation:v1"
    assert result.quality_gate == "pass"
    assert len(result.canonical_facts) == 1
    assert result.canonical_facts[0].metric_id == "revenue"
    assert result.canonical_facts[0].numeric_value == 1000.0
    assert result.canonical_facts[0].source_candidate_fact_ids == ["cand-1"]
    assert result.derived_facts == []
    assert result.validation_report.overall_status == "ok"


def test_pipeline_rejects_mismatched_candidate_document_id() -> None:
    try:
        analyze_report(
            document_ref={"document_id": "doc-1", "market": "CN"},
            extracted_payload={
                "candidate_facts": [
                    {
                        "fact_id": "cand-1",
                        "metric_id": "unknown",
                        "metric_label_raw": "营业收入",
                        "statement_type": "income_statement",
                        "entity_scope": "consolidated",
                        "comparison_axis": "current",
                        "adjustment_basis": "reported",
                        "period_id": "2025FY",
                        "currency": "CNY",
                        "raw_value": "1000",
                        "numeric_value": 1000.0,
                        "raw_unit": "万元",
                        "precision": 2,
                        "confidence": 0.95,
                        "document_id": "doc-2",
                        "block_id": "block-1",
                        "table_id": "table-1",
                        "page_index": 1,
                        "table_coord": "A1",
                        "evidence_bundle_id": "bundle-1",
                        "evidence_span": "营业收入 1000",
                        "snapshot_path": None,
                        "extraction_method": "table_skill",
                        "extraction_version": "v1",
                        "source_rank_hint": 1,
                    }
                ]
            },
        )
    except ValueError as exc:
        assert "document_id" in str(exc)
    else:
        raise AssertionError("analyze_report should reject mismatched document_id")


def test_evidence_repository_round_trips_bundle_through_links() -> None:
    item = EvidenceItem(
        evidence_item_id="item-1",
        document_id="doc-1",
        source_type="block",
        block_id="block-1",
        page_no=1,
        text_excerpt="营业收入 1000",
    )
    bundle = EvidenceBundle(
        evidence_bundle_id="bundle-1",
        document_id="doc-1",
        bundle_type="fact_support",
        evidence_items=[item],
        primary_evidence_item_id="item-1",
        summary="Revenue support",
    )

    repository = InMemoryEvidenceRepository()
    repository.save_evidence_bundle(bundle)

    assert repository.list_evidence_bundle_item_links("bundle-1") == (
        EvidenceBundleItemLink(
            evidence_bundle_id="bundle-1",
            evidence_item_id="item-1",
            sort_order=0,
        ),
    )

    loaded_bundle = repository.get_evidence_bundle("bundle-1")
    assert loaded_bundle is not None
    assert loaded_bundle.evidence_items[0].evidence_item_id == "item-1"
    assert loaded_bundle.primary_evidence_item_id == "item-1"


def test_evidence_repository_rejects_linking_missing_items() -> None:
    repository = InMemoryEvidenceRepository()

    try:
        repository.link_evidence_bundle_item(
            evidence_bundle_id="bundle-1",
            evidence_item_id="missing-item",
            sort_order=0,
        )
    except ValueError as exc:
        assert "missing-item" in str(exc)
    else:
        raise AssertionError("link_evidence_bundle_item should reject missing items")


def test_evidence_repository_rejects_missing_linked_items_on_read() -> None:
    repository = InMemoryEvidenceRepository()
    item = EvidenceItem(
        evidence_item_id="item-1",
        document_id="doc-1",
        source_type="block",
    )
    bundle = EvidenceBundle(
        evidence_bundle_id="bundle-1",
        document_id="doc-1",
        bundle_type="fact_support",
        evidence_items=[item],
        primary_evidence_item_id="item-1",
    )
    repository.save_evidence_bundle(bundle)
    repository._evidence_items.pop("item-1")

    try:
        repository.get_evidence_bundle("bundle-1")
    except ValueError as exc:
        assert "missing linked evidence item" in str(exc)
    else:
        raise AssertionError("get_evidence_bundle should reject missing linked items")
