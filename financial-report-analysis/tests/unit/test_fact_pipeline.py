from financial_report_analysis.models.evidence import EvidenceBundle, EvidenceItem
from financial_report_analysis.models.facts import CandidateFact
from financial_report_analysis.models.facts import CanonicalFact
from financial_report_analysis.models.facts import DerivedFact
from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
from financial_report_analysis.models import (
    ParsedCell,
    ParsedColumn,
    ParsedRow,
    ParsedTable,
    NormalizedTableCellValue,
    NormalizedTableColumn,
    NormalizedTableRow,
    NormalizedTableSemantics,
)
from financial_report_analysis.ingestion.table_semantics import normalize_table_semantics
from financial_report_analysis.pipeline import analyze_report
from financial_report_analysis.registries import load_metric_registry
from financial_report_analysis.registries.metric_mapping import MetricMappingDefinition, MetricMappingRegistry
from financial_report_analysis.services.conflict_resolver import ConflictResolver
from financial_report_analysis.services.derivation_service import DerivationService
from financial_report_analysis.services.fact_normalizer import FactNormalizer
from financial_report_analysis.services.table_fact_builder import (
    build_table_candidate_facts,
)
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
    metric_id: str = "raw_revenue",
    metric_label_raw: str = "Revenue",
    statement_type: str = "income_statement",
    currency: str = "CNY",
    raw_unit: str = "unit",
    extensions: dict[str, object] | None = None,
) -> CandidateFact:
    return CandidateFact(
        fact_id=fact_id,
        metric_id=metric_id,
        metric_label_raw=metric_label_raw,
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


def _normalized_table_semantics(
    *,
    table_id: str,
    document_id: str,
    table_kind: str,
    period_id: str,
    rows: list[tuple[str, str | None, float]],
    table_unit: str = "元",
    table_currency: str = "CNY",
    statement_scope_guess: str = "consolidated",
) -> NormalizedTableSemantics:
    return NormalizedTableSemantics(
        table_id=table_id,
        document_id=document_id,
        page_range=(1, 1),
        table_kind=table_kind,
        title_text="Balance Sheet",
        statement_scope_guess=statement_scope_guess,
        table_unit=table_unit,
        table_currency=table_currency,
        rows=[
            NormalizedTableRow(
                row_id=f"row-{index}",
                label_raw=label_raw,
                normalized_row_label=normalized_row_label,
                values=[
                    NormalizedTableCellValue(
                        row_index=index,
                        column_index=1,
                        raw_text=str(value),
                        numeric_value=value,
                        period_id=period_id,
                        comparison_axis="current",
                        value_time_shape="point_in_time",
                    )
                ],
            )
            for index, (label_raw, normalized_row_label, value) in enumerate(rows, start=1)
        ],
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


def test_fact_pipeline_normalizes_common_cn_units() -> None:
    normalizer = FactNormalizer()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-cn-unit-1",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=100.0,
                raw_unit="万元",
            )
        ]
    )

    fact = normalized[0]
    assert fact.numeric_value == 1_000_000.0
    assert fact.currency == "CNY"
    assert fact.normalized_unit == "CNY"


def test_build_table_candidate_facts_carries_phase1_eps_metadata_and_provenance() -> None:
    registry = MetricMappingRegistry(
        [
            MetricMappingDefinition(
                metric_id="basic_eps",
                statement_type="income_statement",
                allowed_table_kinds=("income_statement",),
                normalized_row_labels=("basic earnings per share",),
                period_scope="duration",
                value_type="per_share",
                unit_expectation="per_share_amount",
                sign_rule="allow_negative",
                aliases_by_market={"CN": ("基本每股收益",)},
            )
        ]
    )
    semantics_table = NormalizedTableSemantics(
        table_id="table-1",
        document_id="doc-1",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Income Statement",
        statement_scope_guess="consolidated",
        table_unit="元/股",
        table_currency="CNY",
        rows=[
            NormalizedTableRow(
                row_id="row-1",
                label_raw="基本每股收益",
                normalized_row_label="basic earnings per share",
                semantic_source="llm_fallback",
                semantic_confidence=0.61,
                fallback_reason="eps_block_disambiguation",
                values=[
                    NormalizedTableCellValue(
                        row_index=1,
                        column_index=1,
                        raw_text="1.23",
                        numeric_value=1.23,
                        period_id="2024FY",
                        comparison_axis="current",
                        value_time_shape="duration",
                    )
                ],
            )
        ],
    )

    candidates = build_table_candidate_facts(
        [semantics_table],
        registry=registry,
        document_id="doc-1",
        market="CN",
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["metric_id"] == "basic_eps"
    assert candidate["extensions"]["value_type"] == "per_share"
    assert candidate["extensions"]["unit_expectation"] == "per_share_amount"
    assert candidate["extensions"]["semantic_source"] == "llm_fallback"
    assert candidate["extensions"]["semantic_confidence"] == 0.61
    assert candidate["extensions"]["fallback_reason"] == "eps_block_disambiguation"


def test_table_fact_builder_emits_p2a_working_capital_candidate_facts() -> None:
    semantics = _normalized_table_semantics(
        table_id="table-p2a",
        document_id="doc:p2a",
        table_kind="balance_sheet",
        period_id="2025FY",
        rows=[
            ("应收账款", "accounts receivables", 11.0),
            ("应收票据", "notes receivable", 12.0),
            ("其他应收款", "other receivables", 13.0),
            ("合同负债", "contract liabilities", 14.0),
            ("预收款项", "advances from customers", 15.0),
            ("应付账款", "accounts payable", 16.0),
            ("应付票据", "notes payable", 17.0),
        ],
    )

    candidates = build_table_candidate_facts(
        [semantics],
        registry=load_metric_registry(),
        document_id="doc:p2a",
        market="CN",
    )

    assert {candidate["metric_id"] for candidate in candidates} == {
        "accounts_receiv",
        "notes_receiv",
        "oth_receiv",
        "contract_liab",
        "adv_receipts",
        "acct_payable",
        "notes_payable",
    }
    assert all(candidate["statement_type"] == "balance_sheet" for candidate in candidates)
    assert all(candidate["period_id"] == "2025FY" for candidate in candidates)


def test_table_fact_builder_rejects_p2a_negative_control_rows() -> None:
    semantics = _normalized_table_semantics(
        table_id="table-p2a-negative",
        document_id="doc:p2a-negative",
        table_kind="balance_sheet",
        period_id="2025FY",
        rows=[
            ("accounts receivable financing", None, 1.0),
            ("long-term receivables", None, 2.0),
            ("employee compensation payable", None, 3.0),
            ("taxes payable", None, 4.0),
            ("bonds payable", None, 5.0),
        ],
        table_currency="HKD",
    )

    assert (
        build_table_candidate_facts(
            [semantics],
            registry=load_metric_registry(),
            document_id="doc:p2a-negative",
            market="HK",
        )
        == []
    )


def test_table_fact_builder_emits_p2b_debt_candidate_facts() -> None:
    cases = [
        (
            "CN",
            "doc:p2b-cn",
            "CNY",
            [
                ("短期借款", "short-term borrowings", 11.0),
                ("长期借款", "long-term borrowings", 12.0),
                ("应付债券", "bonds payable", 13.0),
                ("一年内到期的非流动负债", "current portion of long-term debt", 14.0),
            ],
            {
                "st_borr",
                "lt_borr",
                "bond_payable",
                "non_cur_liab_due_1y",
            },
        ),
        (
            "HK",
            "doc:p2b-hk",
            "HKD",
            [
                ("Short-term borrowings", "short-term borrowings", 21.0),
                ("Long-term borrowings", "long-term borrowings", 22.0),
                ("Bonds payable", "bonds payable", 23.0),
                (
                    "Current portion of long-term debt",
                    "current portion of long-term debt",
                    24.0,
                ),
            ],
            {
                "st_borr",
                "lt_borr",
                "bond_payable",
                "non_cur_liab_due_1y",
            },
        ),
    ]

    for market, document_id, table_currency, rows, expected_metric_ids in cases:
        semantics = _normalized_table_semantics(
            table_id=f"table-{market.lower()}-p2b",
            document_id=document_id,
            table_kind="balance_sheet",
            period_id="2025FY",
            rows=rows,
            table_currency=table_currency,
        )

        candidates = build_table_candidate_facts(
            [semantics],
            registry=load_metric_registry(),
            document_id=document_id,
            market=market,
        )

        assert {candidate["metric_id"] for candidate in candidates} == expected_metric_ids
        assert all(candidate["statement_type"] == "balance_sheet" for candidate in candidates)
        assert all(candidate["extraction_method"] == "table_semantics" for candidate in candidates)


def test_table_fact_builder_emits_p3_statement_row_asset_candidates() -> None:
    cases = [
        (
            "CN",
            "doc:p3-cn",
            "CNY",
            [
                ("货币资金", "cash and cash equivalents", 11.0),
                ("交易性金融资产", "trading assets", 12.0),
                ("存货", "inventories", 13.0),
                ("商誉", "goodwill", 14.0),
                ("无形资产", "intangible assets", 15.0),
            ],
        ),
        (
            "HK",
            "doc:p3-hk",
            "HKD",
            [
                ("Cash and cash equivalents", "cash and cash equivalents", 21.0),
                ("Trading assets", "trading assets", 22.0),
                ("Inventories", "inventories", 23.0),
                ("Goodwill", "goodwill", 24.0),
                ("Intangible assets", "intangible assets", 25.0),
            ],
        ),
    ]

    for market, document_id, table_currency, rows in cases:
        semantics = _normalized_table_semantics(
            table_id=f"table-{market.lower()}-p3",
            document_id=document_id,
            table_kind="balance_sheet",
            period_id="2025FY",
            rows=rows,
            table_currency=table_currency,
        )

        candidates = build_table_candidate_facts(
            [semantics],
            registry=load_metric_registry(),
            document_id=document_id,
            market=market,
        )

        assert {candidate["metric_id"] for candidate in candidates} == {
            "cash",
            "trad_asset",
            "inventories",
            "goodwill",
            "intang_assets",
        }
        assert all(candidate["statement_type"] == "balance_sheet" for candidate in candidates)
        assert all(candidate["extraction_method"] == "table_semantics" for candidate in candidates)


def test_table_fact_builder_rejects_p3_asset_negative_control_rows() -> None:
    semantics = _normalized_table_semantics(
        table_id="table-p3-negative",
        document_id="doc:p3-negative",
        table_kind="balance_sheet",
        period_id="2025FY",
        rows=[
            ("restricted cash", None, 1.0),
            ("assets held for sale", None, 2.0),
            ("investment properties", None, 3.0),
            ("prepayments", None, 4.0),
            ("right-of-use assets", None, 5.0),
            ("deferred tax assets", None, 6.0),
            ("capitalized development costs", None, 7.0),
            ("total non-current assets", None, 8.0),
            ("contract assets", None, 9.0),
            ("other non-current assets", None, 10.0),
        ],
        table_currency="HKD",
    )

    assert (
        build_table_candidate_facts(
            [semantics],
            registry=load_metric_registry(),
            document_id="doc:p3-negative",
            market="HK",
        )
        == []
    )


def test_fact_pipeline_normalizes_basic_eps_as_per_share_metric() -> None:
    normalizer = FactNormalizer()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-basic-eps",
                period_id="2024FY",
                source_rank_hint=1,
                numeric_value=1.23,
                metric_id="basic_eps",
                metric_label_raw="Basic EPS",
                raw_unit="元/股",
                extensions={
                    "value_type": "per_share",
                    "unit_expectation": "per_share_amount",
                },
            )
        ]
    )

    fact = normalized[0]
    assert fact.metric_id == "basic_eps"
    assert fact.numeric_value == 1.23
    assert fact.currency == "CNY"
    assert fact.normalized_unit == "per_share_amount"
    assert fact.extensions["value_type"] == "per_share"
    assert fact.extensions["unit_expectation"] == "per_share_amount"


def test_fact_pipeline_preserves_deterministic_metric_id_when_label_alias_is_not_in_normalizer_table() -> None:
    normalizer = FactNormalizer()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-capex",
                period_id="2024FY",
                source_rank_hint=1,
                numeric_value=80.0,
                metric_id="c_pay_acq_const_fiolta",
                metric_label_raw="Payments for acquisition of property, plant and equipment",
                statement_type="cash_flow_statement",
                currency="HKD",
                raw_unit="million",
                extensions={
                    "value_type": "amount",
                    "unit_expectation": "currency_amount",
                },
            )
        ]
    )

    fact = normalized[0]
    assert fact.metric_id == "c_pay_acq_const_fiolta"
    assert not fact.metric_id.startswith("custom::")
    assert fact.numeric_value == 80_000_000.0
    assert fact.normalized_unit == "HKD"


def test_fact_pipeline_normalizes_basic_eps_from_cent_per_share_units() -> None:
    normalizer = FactNormalizer()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-basic-eps-cents",
                period_id="2024FY",
                source_rank_hint=1,
                numeric_value=123.0,
                metric_id="basic_eps",
                metric_label_raw="Basic EPS",
                statement_type="income_statement",
                currency="HKD",
                raw_unit="HK cents/share",
                extensions={
                    "value_type": "per_share",
                    "unit_expectation": "per_share_amount",
                },
            )
        ]
    )

    fact = normalized[0]
    assert fact.metric_id == "basic_eps"
    assert fact.numeric_value == 1.23
    assert fact.currency == "HKD"
    assert fact.normalized_unit == "per_share_amount"


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


def test_conflict_resolver_keeps_business_key_order_without_phase_specific_reordering() -> None:
    normalizer = FactNormalizer()
    resolver = ConflictResolver()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-revenue",
                period_id="2024FY",
                source_rank_hint=1,
                numeric_value=100.0,
                metric_id="raw_revenue",
                metric_label_raw="Revenue",
            ),
            _candidate(
                fact_id="candidate-net-income",
                period_id="2024FY",
                source_rank_hint=1,
                numeric_value=200.0,
                metric_id="n_income_attr_p",
                metric_label_raw="Net profit attributable to owners of the parent",
                extensions={
                    "semantic_source": "llm_fallback",
                    "semantic_confidence": 0.72,
                    "fallback_reason": "owner_scope_disambiguation",
                },
            ),
            _candidate(
                fact_id="candidate-basic-eps",
                period_id="2024FY",
                source_rank_hint=1,
                numeric_value=1.11,
                metric_id="basic_eps",
                metric_label_raw="Basic EPS",
                raw_unit="元/股",
                extensions={
                    "value_type": "per_share",
                    "unit_expectation": "per_share_amount",
                },
            ),
        ]
    )

    canonical_facts = resolver.resolve(normalized)

    assert [fact.metric_id for fact in canonical_facts] == [
        "basic_eps",
        "n_income_attr_p",
        "revenue",
    ]
    net_income_fact = next(fact for fact in canonical_facts if fact.metric_id == "n_income_attr_p")
    assert net_income_fact.extensions["semantic_source"] == "llm_fallback"
    assert net_income_fact.extensions["semantic_confidence"] == 0.72
    assert net_income_fact.extensions["fallback_reason"] == "owner_scope_disambiguation"


def test_analyze_report_promotes_phase1_metrics_to_canonical_with_stable_provenance() -> None:
    extracted_payload = {
        "candidate_facts": [
            {
                "fact_id": "doc-1:candidate:1",
                "metric_id": "n_income_attr_p",
                "metric_label_raw": "Net profit attributable to owners of the parent",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "comparison_axis": "current",
                "adjustment_basis": "reported",
                "period_id": "2024FY",
                "currency": "CNY",
                "raw_value": "123",
                "numeric_value": 123.0,
                "raw_unit": "CNY",
                "normalized_unit": None,
                "precision": 0,
                "confidence": 0.9,
                "extensions": {
                    "semantic_source": "llm_fallback",
                    "semantic_confidence": 0.8,
                    "fallback_reason": "owner_scope_disambiguation",
                },
                "document_id": "doc-1",
                "block_id": "block-1",
                "page_index": 0,
                "evidence_bundle_id": "bundle-1",
                "source_rank_hint": 30,
            },
            {
                "fact_id": "doc-1:candidate:2",
                "metric_id": "basic_eps",
                "metric_label_raw": "Basic EPS",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "comparison_axis": "current",
                "adjustment_basis": "reported",
                "period_id": "2024FY",
                "currency": "CNY",
                "raw_value": "1.23",
                "numeric_value": 1.23,
                "raw_unit": "元/股",
                "normalized_unit": None,
                "precision": 2,
                "confidence": 0.9,
                "extensions": {
                    "value_type": "per_share",
                    "unit_expectation": "per_share_amount",
                },
                "document_id": "doc-1",
                "block_id": "block-2",
                "page_index": 0,
                "evidence_bundle_id": "bundle-2",
                "source_rank_hint": 30,
            },
            {
                "fact_id": "doc-1:candidate:3",
                "metric_id": "finance_exp",
                "metric_label_raw": "Finance costs",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "comparison_axis": "current",
                "adjustment_basis": "reported",
                "period_id": "2024FY",
                "currency": "CNY",
                "raw_value": "45",
                "numeric_value": 45.0,
                "raw_unit": "CNY",
                "normalized_unit": None,
                "precision": 0,
                "confidence": 0.9,
                "extensions": {},
                "document_id": "doc-1",
                "block_id": "block-3",
                "page_index": 0,
                "evidence_bundle_id": "bundle-3",
                "source_rank_hint": 30,
            },
        ]
    }

    pipeline_result = analyze_report(
        document_ref={"document_id": "doc-1", "market": "CN"},
        extracted_payload=extracted_payload,
    )

    canonical_metric_ids = [fact.metric_id for fact in pipeline_result.canonical_facts]
    assert {"basic_eps", "n_income_attr_p", "finance_exp"} <= set(
        canonical_metric_ids
    )
    basic_eps = next(fact for fact in pipeline_result.canonical_facts if fact.metric_id == "basic_eps")
    assert basic_eps.normalized_unit == "per_share_amount"
    assert basic_eps.numeric_value == 1.23
    n_income_attr_p = next(
        fact for fact in pipeline_result.canonical_facts if fact.metric_id == "n_income_attr_p"
    )
    assert n_income_attr_p.extensions["semantic_source"] == "llm_fallback"
    assert n_income_attr_p.extensions["semantic_confidence"] == 0.8
    assert n_income_attr_p.extensions["fallback_reason"] == "owner_scope_disambiguation"


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
    assert result.canonical_facts[0].numeric_value == 10_000_000.0
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


def test_analyze_report_promotes_supported_table_metrics_to_canonical_facts() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            NormalizedTableSemantics(
                table_id="table-1",
                document_id="doc-1",
                page_range=(1, 1),
                table_kind="income_statement",
                title_text="Consolidated Income Statement",
                statement_scope_guess="consolidated",
                table_unit="thousand",
                table_currency="HKD",
                unit_semantic_source="deterministic",
                currency_semantic_source="deterministic",
                columns=[
                    NormalizedTableColumn(
                        column_id="column-1",
                        header_text="2025",
                        period_id="2025FY",
                        comparison_axis="current",
                        value_time_shape="duration",
                        is_current=True,
                        is_comparison=False,
                    )
                ],
                rows=[
                    NormalizedTableRow(
                        row_id="row-1",
                        label_raw="Revenue",
                        normalized_row_label="revenue",
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="1,000",
                                numeric_value=1000.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    )
                ],
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    result = analyze_report(
        {"document_id": "doc-1", "market": "HK", "language": "en"},
        {"candidate_facts": candidate_facts},
    )

    assert any(f.metric_id == "revenue" for f in result.canonical_facts)


def test_table_candidate_facts_preserve_unit_currency_semantic_provenance() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            NormalizedTableSemantics(
                table_id="table-1",
                document_id="doc-1",
                page_range=(1, 1),
                table_kind="income_statement",
                title_text="Consolidated Income Statement",
                statement_scope_guess="consolidated",
                table_unit="million",
                table_currency="HKD",
                unit_semantic_source="deterministic",
                currency_semantic_source="deterministic",
                columns=[
                    NormalizedTableColumn(
                        column_id="column-1",
                        header_text="2025",
                        period_id="2025FY",
                        comparison_axis="current",
                        value_time_shape="duration",
                        is_current=True,
                        is_comparison=False,
                    )
                ],
                rows=[
                    NormalizedTableRow(
                        row_id="row-1",
                        label_raw="Revenue",
                        normalized_row_label="revenue",
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="1,000",
                                numeric_value=1000.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    )
                ],
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    assert candidate_facts[0]["extensions"]["unit_semantic_source"] == "deterministic"
    assert (
        candidate_facts[0]["extensions"]["currency_semantic_source"] == "deterministic"
    )


def test_table_candidate_facts_preserve_table_level_llm_provenance() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            NormalizedTableSemantics(
                table_id="table-1",
                document_id="doc-1",
                page_range=(1, 1),
                table_kind="income_statement",
                title_text="Consolidated Income Statement",
                statement_scope_guess="consolidated",
                table_unit="million",
                table_currency="HKD",
                semantic_source="llm_fallback",
                semantic_confidence=0.81,
                semantic_ambiguity_reason="ambiguous_table_kind",
                unit_semantic_source="deterministic",
                currency_semantic_source="deterministic",
                columns=[
                    NormalizedTableColumn(
                        column_id="column-1",
                        header_text="2025",
                        period_id="2025FY",
                        comparison_axis="current",
                        value_time_shape="duration",
                        is_current=True,
                        is_comparison=False,
                    )
                ],
                rows=[
                    NormalizedTableRow(
                        row_id="row-1",
                        label_raw="Revenue",
                        normalized_row_label="revenue",
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="1,000",
                                numeric_value=1000.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    )
                ],
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    assert candidate_facts[0]["extensions"]["semantic_source"] == "llm_fallback"
    assert candidate_facts[0]["extensions"]["semantic_confidence"] == 0.81
    assert candidate_facts[0]["extensions"]["fallback_reason"] == "ambiguous_table_kind"


def test_table_candidate_facts_match_income_statement_core_metric_aliases() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            NormalizedTableSemantics(
                table_id="table-income-core",
                document_id="doc-1",
                page_range=(1, 1),
                table_kind="income_statement",
                title_text="Consolidated Income Statement",
                statement_scope_guess="consolidated",
                table_unit="thousand",
                table_currency="HKD",
                unit_semantic_source="deterministic",
                currency_semantic_source="deterministic",
                columns=[
                    NormalizedTableColumn(
                        column_id="column-1",
                        header_text="2025",
                        period_id="2025FY",
                        comparison_axis="current",
                        value_time_shape="duration",
                        is_current=True,
                        is_comparison=False,
                    )
                ],
                rows=[
                    NormalizedTableRow(
                        row_id="row-cost",
                        label_raw="Cost of sales",
                        normalized_row_label="cost of sales",
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="800",
                                numeric_value=800.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                    NormalizedTableRow(
                        row_id="row-operating-profit",
                        label_raw="Profit from operations",
                        normalized_row_label="profit from operations",
                        values=[
                            NormalizedTableCellValue(
                                row_index=2,
                                column_index=1,
                                raw_text="200",
                                numeric_value=200.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                    NormalizedTableRow(
                        row_id="row-net-profit",
                        label_raw="Profit attributable to equity holders",
                        normalized_row_label="profit attributable to equity holders",
                        values=[
                            NormalizedTableCellValue(
                                row_index=3,
                                column_index=1,
                                raw_text="120",
                                numeric_value=120.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                ],
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    assert {fact["metric_id"] for fact in candidate_facts} == {
        "operating_cost",
        "operating_profit",
        "net_profit",
    }


def test_analyze_report_promotes_income_statement_core_metrics_to_canonical_facts() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            NormalizedTableSemantics(
                table_id="table-income-pipeline",
                document_id="doc-1",
                page_range=(1, 1),
                table_kind="income_statement",
                title_text="Consolidated Income Statement",
                statement_scope_guess="consolidated",
                table_unit="thousand",
                table_currency="HKD",
                unit_semantic_source="deterministic",
                currency_semantic_source="deterministic",
                columns=[
                    NormalizedTableColumn(
                        column_id="column-1",
                        header_text="2025",
                        period_id="2025FY",
                        comparison_axis="current",
                        value_time_shape="duration",
                        is_current=True,
                        is_comparison=False,
                    )
                ],
                rows=[
                    NormalizedTableRow(
                        row_id="row-revenue",
                        label_raw="Revenue",
                        normalized_row_label="revenue",
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="1,000",
                                numeric_value=1000.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                    NormalizedTableRow(
                        row_id="row-cost",
                        label_raw="Cost of sales",
                        normalized_row_label="cost of sales",
                        values=[
                            NormalizedTableCellValue(
                                row_index=2,
                                column_index=1,
                                raw_text="800",
                                numeric_value=800.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                    NormalizedTableRow(
                        row_id="row-net-profit",
                        label_raw="Profit attributable to equity holders",
                        normalized_row_label="profit attributable to equity holders",
                        values=[
                            NormalizedTableCellValue(
                                row_index=3,
                                column_index=1,
                                raw_text="120",
                                numeric_value=120.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                ],
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    result = analyze_report(
        {"document_id": "doc-1", "market": "HK", "language": "en"},
        {"candidate_facts": candidate_facts},
    )

    assert {fact.metric_id for fact in result.canonical_facts} >= {
        "revenue",
        "operating_cost",
        "net_profit",
    }


def test_table_candidate_facts_match_cash_flow_primary_section_aliases() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            normalize_table_semantics(
                ParsedTable(
                    table_id="table-cash-flow-core",
                    document_id="doc-1",
                    page_range=(1, 1),
                    table_kind="cash_flow_statement",
                    title_text="Consolidated Statement of Cash Flows",
                    statement_scope_guess="consolidated",
                    table_unit="thousand",
                    table_currency="HKD",
                    period_columns=[
                        ParsedColumn(
                            column_id="column-1",
                            column_index=1,
                            header_text="2025",
                            period_id="2025FY",
                            comparison_axis="current",
                            value_time_shape="duration",
                            is_current=True,
                        )
                    ],
                    body_rows=[
                        ParsedRow(
                            row_id="row-operating",
                            row_index=1,
                            label_raw="Net cash generated from operating activities",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=1,
                                    column_index=1,
                                    text_raw="500",
                                    numeric_value=500.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-investing",
                            row_index=2,
                            label_raw="net cash from investing activities",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=2,
                                    column_index=1,
                                    text_raw="-200",
                                    numeric_value=-200.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-financing",
                            row_index=3,
                            label_raw="net cash from financing activities",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=3,
                                    column_index=1,
                                    text_raw="-100",
                                    numeric_value=-100.0,
                                    page_index=1,
                                )
                            ],
                        ),
                    ],
                )
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    assert {fact["metric_id"] for fact in candidate_facts} == {
        "operating_cash_flow",
        "investing_cash_flow",
        "financing_cash_flow",
    }


def test_analyze_report_promotes_gross_profit_to_canonical_facts() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            NormalizedTableSemantics(
                table_id="table-income-gross-profit",
                document_id="doc-1",
                page_range=(1, 1),
                table_kind="income_statement",
                title_text="Consolidated Income Statement",
                statement_scope_guess="consolidated",
                table_unit="thousand",
                table_currency="HKD",
                unit_semantic_source="deterministic",
                currency_semantic_source="deterministic",
                columns=[
                    NormalizedTableColumn(
                        column_id="column-1",
                        header_text="2025",
                        period_id="2025FY",
                        comparison_axis="current",
                        value_time_shape="duration",
                        is_current=True,
                        is_comparison=False,
                    )
                ],
                rows=[
                    NormalizedTableRow(
                        row_id="row-gross-profit",
                        label_raw="Gross profit for the period",
                        normalized_row_label="gross profit",
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="250",
                                numeric_value=250.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                ],
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    result = analyze_report(
        {"document_id": "doc-1", "market": "HK", "language": "en"},
        {"candidate_facts": candidate_facts},
    )

    assert {fact.metric_id for fact in result.canonical_facts} >= {"gross_profit"}


def test_analyze_report_promotes_cash_flow_primary_sections_to_canonical_facts() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            normalize_table_semantics(
                ParsedTable(
                    table_id="table-cash-flow-pipeline",
                    document_id="doc-1",
                    page_range=(1, 1),
                    table_kind="cash_flow_statement",
                    title_text="Consolidated Statement of Cash Flows",
                    statement_scope_guess="consolidated",
                    table_unit="thousand",
                    table_currency="HKD",
                    period_columns=[
                        ParsedColumn(
                            column_id="column-1",
                            column_index=1,
                            header_text="2025",
                            period_id="2025FY",
                            comparison_axis="current",
                            value_time_shape="duration",
                            is_current=True,
                        )
                    ],
                    body_rows=[
                        ParsedRow(
                            row_id="row-operating",
                            row_index=1,
                            label_raw="Net cash generated from operating activities",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=1,
                                    column_index=1,
                                    text_raw="500",
                                    numeric_value=500.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-investing",
                            row_index=2,
                            label_raw="net cash from investing activities",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=2,
                                    column_index=1,
                                    text_raw="-200",
                                    numeric_value=-200.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-financing",
                            row_index=3,
                            label_raw="net cash from financing activities",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=3,
                                    column_index=1,
                                    text_raw="-100",
                                    numeric_value=-100.0,
                                    page_index=1,
                                )
                            ],
                        ),
                    ],
                )
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    result = analyze_report(
        {"document_id": "doc-1", "market": "HK", "language": "en"},
        {"candidate_facts": candidate_facts},
    )

    assert {fact.metric_id for fact in result.canonical_facts} >= {
        "operating_cash_flow",
        "investing_cash_flow",
        "financing_cash_flow",
    }


def test_analyze_report_skips_cash_flow_summary_style_rows() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            normalize_table_semantics(
                ParsedTable(
                    table_id="table-cash-flow-summary",
                    document_id="doc-1",
                    page_range=(1, 1),
                    table_kind="cash_flow_statement",
                    title_text="Consolidated Statement of Cash Flows",
                    statement_scope_guess="consolidated",
                    table_unit="thousand",
                    table_currency="HKD",
                    period_columns=[
                        ParsedColumn(
                            column_id="column-1",
                            column_index=1,
                            header_text="2025",
                            period_id="2025FY",
                            comparison_axis="current",
                            value_time_shape="duration",
                            is_current=True,
                        )
                    ],
                    body_rows=[
                        ParsedRow(
                            row_id="row-free-cash-flow",
                            row_index=1,
                            label_raw="Free cash flow",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=1,
                                    column_index=1,
                                    text_raw="300",
                                    numeric_value=300.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-net-increase",
                            row_index=2,
                            label_raw="Net increase/decrease in cash and cash equivalents",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=2,
                                    column_index=1,
                                    text_raw="150",
                                    numeric_value=150.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-ratio",
                            row_index=3,
                            label_raw="Cash flow ratio",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=3,
                                    column_index=1,
                                    text_raw="1.2",
                                    numeric_value=1.2,
                                    page_index=1,
                                )
                            ],
                        ),
                    ],
                )
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    result = analyze_report(
        {"document_id": "doc-1", "market": "HK", "language": "en"},
        {"candidate_facts": candidate_facts},
    )

    assert candidate_facts == []
    assert result.canonical_facts == []


def test_analyze_report_skips_summary_style_gross_profit_rows() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            NormalizedTableSemantics(
                table_id="table-income-gross-profit-summary",
                document_id="doc-1",
                page_range=(1, 1),
                table_kind="income_statement",
                title_text="Consolidated Income Statement",
                statement_scope_guess="consolidated",
                table_unit="thousand",
                table_currency="HKD",
                unit_semantic_source="deterministic",
                currency_semantic_source="deterministic",
                columns=[
                    NormalizedTableColumn(
                        column_id="column-1",
                        header_text="2025",
                        period_id="2025FY",
                        comparison_axis="current",
                        value_time_shape="duration",
                        is_current=True,
                        is_comparison=False,
                    )
                ],
                rows=[
                    NormalizedTableRow(
                        row_id="row-gross-profit-summary",
                        label_raw="Gross profit summary",
                        normalized_row_label=None,
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="250",
                                numeric_value=250.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                ],
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    result = analyze_report(
        {"document_id": "doc-1", "market": "HK", "language": "en"},
        {"candidate_facts": candidate_facts},
    )

    assert candidate_facts == []
    assert result.canonical_facts == []


def test_analyze_report_promotes_equity_and_attributable_equity_to_canonical_facts() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            NormalizedTableSemantics(
                table_id="table-balance-equity",
                document_id="doc-1",
                page_range=(2, 2),
                table_kind="balance_sheet",
                title_text="Consolidated Statement of Financial Position",
                statement_scope_guess="consolidated",
                table_unit="thousand",
                table_currency="HKD",
                unit_semantic_source="deterministic",
                currency_semantic_source="deterministic",
                columns=[
                    NormalizedTableColumn(
                        column_id="column-1",
                        header_text="2025",
                        period_id="2025FY",
                        comparison_axis="current",
                        value_time_shape="point",
                        is_current=True,
                        is_comparison=False,
                    )
                ],
                rows=[
                    NormalizedTableRow(
                        row_id="row-equity",
                        label_raw="所有者权益合计",
                        normalized_row_label="equity",
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="3,500",
                                numeric_value=3500.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="point",
                            )
                        ],
                    ),
                    NormalizedTableRow(
                        row_id="row-attributable-equity",
                        label_raw="归属于母公司股东权益",
                        normalized_row_label="equity attributable to owners of the parent",
                        values=[
                            NormalizedTableCellValue(
                                row_index=2,
                                column_index=1,
                                raw_text="3,100",
                                numeric_value=3100.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="point",
                            )
                        ],
                    ),
                    NormalizedTableRow(
                        row_id="row-equity-ratio",
                        label_raw="权益比率",
                        normalized_row_label=None,
                        values=[
                            NormalizedTableCellValue(
                                row_index=3,
                                column_index=1,
                                raw_text="43%",
                                numeric_value=43.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="point",
                            )
                        ],
                    ),
                ],
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    result = analyze_report(
        {"document_id": "doc-1", "market": "HK", "language": "en"},
        {"candidate_facts": candidate_facts},
    )

    assert {fact.metric_id for fact in result.canonical_facts} == {
        "equity",
        "equity_attributable_to_owners",
    }
    assert all(
        fact.extensions["statement_scope_guess"] == "consolidated"
        for fact in result.canonical_facts
    )
    assert all(fact.entity_scope == "consolidated" for fact in result.canonical_facts)
    assert all(fact.extensions["semantic_source"] == "deterministic" for fact in result.canonical_facts)


def test_balance_sheet_english_attributable_equity_survives_to_candidate_facts() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="table-balance-equity-en",
            document_id="doc-1",
            page_range=(2, 2),
            table_kind="balance_sheet",
            title_text="Consolidated Statement of Financial Position",
            statement_scope_guess="consolidated",
            table_unit="thousand",
            table_currency="HKD",
            period_columns=[
                ParsedColumn(
                    column_id="column-1",
                    column_index=1,
                    header_text="2025",
                    period_id="2025FY",
                    comparison_axis="current",
                    value_time_shape="point",
                    is_current=True,
                    is_comparison=False,
                )
            ],
            body_rows=[
                ParsedRow(
                    row_id="row-attributable-equity",
                    row_index=1,
                    label_raw="Equity attributable to owners of the parent",
                    normalized_label_hint=None,
                    value_cells=[
                        ParsedCell(
                            row_index=1,
                            column_index=1,
                            text_raw="3,100",
                            numeric_value=3100.0,
                            page_index=1,
                        )
                    ],
                ),
            ],
        )
    )

    candidate_facts = build_table_candidate_facts(
        [semantics],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    assert len(candidate_facts) == 1
    candidate = candidate_facts[0]
    assert candidate["metric_id"] == "equity_attributable_to_owners"
    assert candidate["metric_label_raw"] == "Equity attributable to owners of the parent"
    assert candidate["extensions"]["statement_scope_guess"] == "consolidated"


def test_table_candidate_facts_skip_equity_ratio_and_per_share_rows() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            NormalizedTableSemantics(
                table_id="table-balance-equity-false-positives",
                document_id="doc-1",
                page_range=(2, 2),
                table_kind="balance_sheet",
                title_text="Consolidated Statement of Financial Position",
                statement_scope_guess="consolidated",
                table_unit="thousand",
                table_currency="HKD",
                unit_semantic_source="deterministic",
                currency_semantic_source="deterministic",
                columns=[
                    NormalizedTableColumn(
                        column_id="column-1",
                        header_text="2025",
                        period_id="2025FY",
                        comparison_axis="current",
                        value_time_shape="point",
                        is_current=True,
                        is_comparison=False,
                    )
                ],
                rows=[
                    NormalizedTableRow(
                        row_id="row-equity-ratio",
                        label_raw="权益比率",
                        normalized_row_label=None,
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="43%",
                                numeric_value=43.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="point",
                            )
                        ],
                    ),
                    NormalizedTableRow(
                        row_id="row-net-assets-per-share",
                        label_raw="每股净资产",
                        normalized_row_label=None,
                        values=[
                            NormalizedTableCellValue(
                                row_index=2,
                                column_index=1,
                                raw_text="5.2",
                                numeric_value=5.2,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="point",
                            )
                        ],
                    ),
                    NormalizedTableRow(
                        row_id="row-book-value",
                        label_raw="book value per share",
                        normalized_row_label=None,
                        values=[
                            NormalizedTableCellValue(
                                row_index=3,
                                column_index=1,
                                raw_text="7.1",
                                numeric_value=7.1,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="point",
                            )
                        ],
                    ),
                ],
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    assert candidate_facts == []


def test_table_candidate_facts_do_not_fabricate_market_default_currency() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            NormalizedTableSemantics(
                table_id="table-unknown-currency",
                document_id="doc-1",
                page_range=(1, 1),
                table_kind="income_statement",
                title_text="Consolidated Income Statement",
                statement_scope_guess="consolidated",
                table_unit="unknown",
                table_currency="unknown",
                unit_semantic_source="deterministic",
                currency_semantic_source="deterministic",
                columns=[
                    NormalizedTableColumn(
                        column_id="column-1",
                        header_text="2025",
                        period_id="2025FY",
                        comparison_axis="current",
                        value_time_shape="duration",
                        is_current=True,
                        is_comparison=False,
                    )
                ],
                rows=[
                    NormalizedTableRow(
                        row_id="row-1",
                        label_raw="Revenue",
                        normalized_row_label="revenue",
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="1,000",
                                numeric_value=1000.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    )
                ],
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    assert candidate_facts[0]["currency"] == "unknown"
    assert candidate_facts[0]["raw_unit"] == "unknown"
    assert candidate_facts[0]["extensions"]["currency_semantic_source"] == "deterministic"


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
    repository.save_evidence_bundle(
        EvidenceBundle(
            evidence_bundle_id="bundle-1",
            document_id="doc-1",
            bundle_type="fact_support",
        )
    )

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


def test_evidence_repository_rejects_linking_items_to_missing_bundles() -> None:
    repository = InMemoryEvidenceRepository()
    repository.save_evidence_item(
        EvidenceItem(
            evidence_item_id="item-1",
            document_id="doc-1",
            source_type="block",
        )
    )

    try:
        repository.link_evidence_bundle_item(
            evidence_bundle_id="missing-bundle",
            evidence_item_id="item-1",
            sort_order=0,
        )
    except ValueError as exc:
        assert "missing-bundle" in str(exc)
    else:
        raise AssertionError(
            "link_evidence_bundle_item should reject missing bundles"
        )


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

def test_pdf_ingestion_adapter_extracts_revenue_candidate_from_text(
    monkeypatch,
    tmp_path,
) -> None:
    adapter = PdfIngestionAdapter()
    pdf_path = tmp_path / "mock.pdf"
    pdf_path.touch()

    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text_pages",
        lambda self, *, pdf_path, pdf_url: [
            (1, "2024 Annual Report\nRevenue 2,500 RMB'000\n")
        ],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_parsed_tables",
        lambda self, *, pdf_path, pdf_url, market: [],
    )

    payload = adapter.extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="CN",
        min_confidence=0.8,
    )

    candidate = payload["candidate_facts"][0]
    assert candidate["document_id"] == str(pdf_path)
    assert candidate["metric_label_raw"] == "Revenue"
    assert candidate["statement_type"] == "income_statement"
    assert candidate["period_id"] == "2024FY"
    assert candidate["numeric_value"] == 2500.0
    assert candidate["raw_unit"] == "RMB'000"
    assert candidate["confidence"] == 0.9


def test_pdf_ingestion_adapter_handles_spaced_cn_annual_title_and_local_context(
    monkeypatch,
    tmp_path,
) -> None:
    adapter = PdfIngestionAdapter()
    pdf_path = tmp_path / "mock-cn-annual.pdf"
    pdf_path.touch()

    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text_pages",
        lambda self, *, pdf_path, pdf_url: [
            (
                1,
                "2024 \u5e74\u5e74\u5ea6\u62a5\u544a\n"
                "\u5408\u5e76\u5229\u6da6\u8868\n"
                "\u8425\u4e1a\u6536\u5165 1,234\n"
                "\u5355\u4f4d\uff1a\u5143 \u5e01\u79cd\uff1a\u4eba\u6c11\u5e01\n"
                "\u9644\u6ce8\uff1a\u6e2f\u5143\u3001\u7f8e\u5143\u4ec5\u7528\u4e8e\u8bf4\u660e\n",
            )
        ],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_parsed_tables",
        lambda self, *, pdf_path, pdf_url, market: [],
    )

    payload = adapter.extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="CN",
        min_confidence=0.8,
    )

    assert payload["candidate_facts"], "expected a revenue candidate"
    candidate = payload["candidate_facts"][0]
    assert candidate["period_id"] == "2024FY"
    assert candidate["currency"] == "CNY"
    assert candidate["raw_unit"] == "\u5143"
    assert candidate["metric_label_raw"] == "\u8425\u4e1a\u6536\u5165"


def test_pdf_ingestion_adapter_handles_spaced_cn_quarterly_title_and_local_context(
    monkeypatch,
    tmp_path,
) -> None:
    adapter = PdfIngestionAdapter()
    pdf_path = tmp_path / "mock-cn-quarterly.pdf"
    pdf_path.touch()

    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text_pages",
        lambda self, *, pdf_path, pdf_url: [
            (
                1,
                "2025 \u5e74\u7b2c\u4e09\u5b63\u5ea6\u62a5\u544a\n"
                "\u5408\u5e76\u5229\u6da6\u8868\n"
                "\u8425\u4e1a\u6536\u5165 9,876\n"
                "\u5355\u4f4d\uff1a\u5143 \u5e01\u79cd\uff1a\u4eba\u6c11\u5e01\n"
                "\u9644\u6ce8\uff1a\u6e2f\u5143\u3001\u7f8e\u5143\u4ec5\u7528\u4e8e\u8bf4\u660e\n",
            )
        ],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_parsed_tables",
        lambda self, *, pdf_path, pdf_url, market: [],
    )

    payload = adapter.extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="CN",
        min_confidence=0.8,
    )

    assert payload["candidate_facts"], "expected a revenue candidate"
    candidate = payload["candidate_facts"][0]
    assert candidate["period_id"] == "2025Q3"
    assert candidate["currency"] == "CNY"
    assert candidate["raw_unit"] == "\u5143"
    assert candidate["metric_label_raw"] == "\u8425\u4e1a\u6536\u5165"
