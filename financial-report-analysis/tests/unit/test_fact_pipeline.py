import pytest

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
from financial_report_analysis.ingestion.table_semantics import (
    normalize_table_semantics,
)
from financial_report_analysis.pipeline import analyze_report
from financial_report_analysis.registries import load_metric_registry
from financial_report_analysis.registries.metric_mapping import (
    MetricMappingDefinition,
    MetricMappingRegistry,
)
from financial_report_analysis.registries.metric_governance import (
    METRIC_GOVERNANCE_EXTENSION_KEY,
)
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
    entity_scope: str = "consolidated",
    currency: str = "CNY",
    raw_unit: str = "unit",
    extraction_method: str | None = None,
    extensions: dict[str, object] | None = None,
) -> CandidateFact:
    candidate_extensions = dict(extensions or {})
    return CandidateFact(
        fact_id=fact_id,
        metric_id=metric_id,
        metric_label_raw=metric_label_raw,
        statement_type=statement_type,
        entity_scope=entity_scope,
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
        extensions=candidate_extensions,
        document_id="doc-1",
        block_id="block-1",
        page_index=0,
        evidence_bundle_id="bundle-1",
        extraction_method=extraction_method,
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
            for index, (label_raw, normalized_row_label, value) in enumerate(
                rows, start=1
            )
        ],
    )


def test_pdf_ingestion_detects_hk_english_dominant_report_with_small_chinese_name() -> None:
    text = (
        "Yum China Holdings, Inc.\n"
        "百勝中國控股有限公司\n"
        "2025 Annual Report\n"
        + ("Consolidated Statements of Income Revenue Operating Profit " * 200)
    )

    assert PdfIngestionAdapter._detect_language(text, "HK") == "en"


def test_pdf_ingestion_keeps_hk_chinese_dominant_report_as_traditional_chinese() -> (
    None
):
    text = (
        "2025 年年度報告\n"
        + ("合併財務報表 營業收入 淨利潤 資產總計 " * 200)
        + "Annual Report"
    )

    assert PdfIngestionAdapter._detect_language(text, "HK") == "zh-Hant"


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


def test_fact_normalizer_adds_standard_metric_governance_metadata() -> None:
    normalizer = FactNormalizer()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-governance-standard",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=2.0,
                metric_label_raw="Revenue",
            )
        ]
    )

    assert normalized[0].metric_id == "revenue"
    assert normalized[0].extensions[METRIC_GOVERNANCE_EXTENSION_KEY] == {
        "registry_status": "standard",
        "metric_namespace": "standard",
        "review_required": False,
        "auto_analysis_allowed": True,
        "governance_reason": "standard_metric",
    }


def test_fact_normalizer_adds_provisional_custom_metric_governance_metadata() -> None:
    normalizer = FactNormalizer()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-governance-custom",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=2.0,
                metric_id="unknown",
                metric_label_raw="Issuer-specific operating sparkle",
            )
        ]
    )

    assert normalized[0].metric_id.startswith("custom::")
    assert normalized[0].extensions[METRIC_GOVERNANCE_EXTENSION_KEY] == {
        "registry_status": "provisional",
        "metric_namespace": "custom",
        "review_required": True,
        "auto_analysis_allowed": False,
        "governance_reason": "provisional_custom_metric",
    }


def test_fact_normalizer_keeps_supported_mapped_metric_governance_standard() -> None:
    normalizer = FactNormalizer()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-governance-mapped",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=2.0,
                metric_id="total_assets",
                metric_label_raw="Assets, totally weird issuer label",
                statement_type="balance_sheet",
                extensions={
                    "metric_mapping_source": "metric_mapping_registry",
                },
            )
        ]
    )

    assert normalized[0].metric_id == "total_assets"
    assert normalized[0].extensions[METRIC_GOVERNANCE_EXTENSION_KEY] == {
        "registry_status": "standard",
        "metric_namespace": "standard",
        "review_required": False,
        "auto_analysis_allowed": True,
        "governance_reason": "supported_metric_mapping",
    }


def test_fact_normalizer_does_not_preserve_unknown_metric_id_as_supported() -> None:
    normalizer = FactNormalizer()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-governance-typo",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=2.0,
                metric_id="totl_assets",
                metric_label_raw="Assets, totally weird issuer label",
                statement_type="balance_sheet",
            )
        ]
    )

    assert normalized[0].metric_id.startswith("custom::")
    assert normalized[0].metric_id != "totl_assets"
    assert normalized[0].extensions[METRIC_GOVERNANCE_EXTENSION_KEY] == {
        "registry_status": "provisional",
        "metric_namespace": "custom",
        "review_required": True,
        "auto_analysis_allowed": False,
        "governance_reason": "provisional_custom_metric",
    }


def test_fact_normalizer_recomputes_stale_standard_governance_metadata() -> None:
    normalizer = FactNormalizer()

    normalized = normalizer.normalize_candidates(
        [
            _candidate(
                fact_id="candidate-governance-stale",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=2.0,
                metric_id="unknown",
                metric_label_raw="Issuer-specific operating sparkle",
                extensions={
                    METRIC_GOVERNANCE_EXTENSION_KEY: {
                        "registry_status": "standard",
                        "metric_namespace": "standard",
                        "review_required": False,
                        "auto_analysis_allowed": True,
                        "governance_reason": "standard_metric",
                    },
                },
            )
        ]
    )

    assert normalized[0].metric_id.startswith("custom::")
    assert normalized[0].extensions[METRIC_GOVERNANCE_EXTENSION_KEY] == {
        "registry_status": "provisional",
        "metric_namespace": "custom",
        "review_required": True,
        "auto_analysis_allowed": False,
        "governance_reason": "provisional_custom_metric",
    }


def test_analyze_report_blocks_unsupported_label_with_stale_supported_metric_id() -> (
    None
):
    result = analyze_report(
        document_ref={"document_id": "doc-1", "market": "CN"},
        extracted_payload={
            "candidate_facts": [
                {
                    "fact_id": "cand-stale-supported-1",
                    "metric_id": "revenue",
                    "metric_label_raw": "Customer loyalty liabilities",
                    "statement_type": "balance_sheet",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "CNY",
                    "raw_value": "1000",
                    "numeric_value": 1000.0,
                    "raw_unit": "CNY",
                    "normalized_unit": None,
                    "precision": 2,
                    "confidence": 0.95,
                    "extensions": {
                        METRIC_GOVERNANCE_EXTENSION_KEY: {
                            "registry_status": "standard",
                            "metric_namespace": "standard",
                            "review_required": False,
                            "auto_analysis_allowed": True,
                            "governance_reason": "supported_metric_mapping",
                        },
                    },
                    "document_id": "doc-1",
                    "block_id": "block-1",
                    "table_id": "table-1",
                    "page_index": 1,
                    "table_coord": "A1",
                    "evidence_bundle_id": "bundle-1",
                    "evidence_span": "Customer loyalty liabilities 1000",
                    "snapshot_path": None,
                    "extraction_method": "table_skill",
                    "extraction_version": "v1",
                    "source_rank_hint": 1,
                }
            ]
        },
    )

    assert result.canonical_facts == []
    assert result.derived_facts == []
    assert result.quality_gate == "review"
    assert result.validation_report.overall_status == "review_required"
    assert "provisional_metric_review_required" in result.validation_report.issues
    assert len(result.review_packets) == 1
    packet = result.review_packets[0]
    assert packet.metric_id.startswith("custom::")
    assert packet.source_policy == "review_required"
    assert packet.conflict_state == "provisional_metric_review_required"


@pytest.mark.parametrize(
    ("metric_label_raw", "statement_type", "expected_metric_id"),
    [
        ("资产总计", "balance_sheet", "total_assets"),
        ("负债合计", "balance_sheet", "total_liabilities"),
        ("支付给职工以及为职工支付的现金", "cash_flow_statement", "c_pay_to_staff"),
        ("支付的各项税费", "cash_flow_statement", "c_paid_for_taxes"),
    ],
)
def test_fact_pipeline_normalizes_p4c_core_statement_labels(
    metric_label_raw: str,
    statement_type: str,
    expected_metric_id: str,
) -> None:
    normalizer = FactNormalizer()

    candidate = CandidateFact(
        **{
            **_candidate(
                fact_id=f"candidate-{expected_metric_id}",
                period_id="2024FY",
                source_rank_hint=1,
                numeric_value=100.0,
                statement_type=statement_type,
            ).__dict__,
            "metric_label_raw": metric_label_raw,
            "statement_type": statement_type,
        }
    )

    normalized = normalizer.normalize_candidates([candidate])

    assert normalized[0].metric_id == expected_metric_id


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


def test_build_table_candidate_facts_carries_phase1_eps_metadata_and_provenance() -> (
    None
):
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
    assert candidate["extensions"]["metric_mapping_source"] == "metric_mapping_registry"
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
    assert all(
        candidate["statement_type"] == "balance_sheet" for candidate in candidates
    )
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

        assert {
            candidate["metric_id"] for candidate in candidates
        } == expected_metric_ids
        assert all(
            candidate["statement_type"] == "balance_sheet" for candidate in candidates
        )
        assert all(
            candidate["extraction_method"] == "table_semantics"
            for candidate in candidates
        )


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
        assert all(
            candidate["statement_type"] == "balance_sheet" for candidate in candidates
        )
        assert all(
            candidate["extraction_method"] == "table_semantics"
            for candidate in candidates
        )


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


def test_fact_pipeline_preserves_deterministic_metric_id_when_label_alias_is_not_in_normalizer_table() -> (
    None
):
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
                    "metric_mapping_source": "metric_mapping_registry",
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


def test_conflict_resolver_keeps_business_key_order_without_phase_specific_reordering() -> (
    None
):
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
    net_income_fact = next(
        fact for fact in canonical_facts if fact.metric_id == "n_income_attr_p"
    )
    assert net_income_fact.extensions["semantic_source"] == "llm_fallback"
    assert net_income_fact.extensions["semantic_confidence"] == 0.72
    assert net_income_fact.extensions["fallback_reason"] == "owner_scope_disambiguation"


def test_conflict_resolver_preserves_statement_row_when_note_is_supplement_only() -> (
    None
):
    resolver = ConflictResolver()

    result = resolver.resolve_with_review(
        [
            _candidate(
                fact_id="statement-cash",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=100.0,
                metric_id="cash",
                metric_label_raw="Cash",
                extensions={
                    "source_kind": "statement_row",
                    "source_policy": "supplement_only",
                },
            ),
            _candidate(
                fact_id="note-cash",
                period_id="2024Q1",
                source_rank_hint=2,
                numeric_value=120.0,
                metric_id="cash",
                metric_label_raw="Cash",
                extraction_method="note_disclosure",
                extensions={
                    "source_kind": "deterministic_note_disclosure",
                    "source_policy": "supplement_only",
                },
            ),
        ]
    )

    assert len(result.canonical_facts) == 1
    canonical = result.canonical_facts[0]
    assert canonical.numeric_value == 100.0
    assert canonical.resolution_reason == "source_policy_supplement_only"
    assert result.review_packets == []


def test_conflict_resolver_allows_explicit_note_override() -> None:
    resolver = ConflictResolver()

    result = resolver.resolve_with_review(
        [
            _candidate(
                fact_id="statement-restricted-cash",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=100.0,
                metric_id="restricted_cash",
                metric_label_raw="Restricted cash",
                extensions={
                    "source_kind": "statement_row",
                    "source_policy": "supplement_only",
                },
            ),
            _candidate(
                fact_id="note-restricted-cash",
                period_id="2024Q1",
                source_rank_hint=2,
                numeric_value=120.0,
                metric_id="restricted_cash",
                metric_label_raw="Restricted cash",
                extraction_method="note_disclosure",
                extensions={
                    "source_kind": "deterministic_note_disclosure",
                    "source_policy": "override_allowed",
                },
            ),
        ]
    )

    assert len(result.canonical_facts) == 1
    canonical = result.canonical_facts[0]
    assert canonical.numeric_value == 120.0
    assert canonical.resolution_reason == "source_policy_override_allowed"
    assert canonical.validation_flags == []
    assert result.review_packets == []


def test_conflict_resolver_emits_review_packet_for_review_required_source_conflict() -> (
    None
):
    resolver = ConflictResolver()

    result = resolver.resolve_with_review(
        [
            _candidate(
                fact_id="statement-cash-review",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=100.0,
                metric_id="cash",
                metric_label_raw="Cash",
                extensions={
                    "source_kind": "statement_row",
                    "source_policy": "supplement_only",
                },
            ),
            _candidate(
                fact_id="note-cash-review",
                period_id="2024Q1",
                source_rank_hint=2,
                numeric_value=120.0,
                metric_id="cash",
                metric_label_raw="Cash",
                extraction_method="note_disclosure",
                extensions={
                    "source_kind": "deterministic_note_disclosure",
                    "source_policy": "review_required",
                },
            ),
        ]
    )

    assert len(result.canonical_facts) == 1
    canonical = result.canonical_facts[0]
    assert canonical.numeric_value == 100.0
    assert canonical.validation_flags == ["source_conflict_review_required"]
    assert len(result.review_packets) == 1
    packet = result.review_packets[0]
    assert packet.conflict_state == "source_conflict"
    assert packet.candidate_value == 120.0
    assert packet.competing_candidate_values == (100.0,)


def test_conflict_resolver_blocks_blocked_policy_candidate() -> None:
    resolver = ConflictResolver()

    result = resolver.resolve_with_review(
        [
            _candidate(
                fact_id="statement-cash-blocked",
                period_id="2024Q1",
                source_rank_hint=1,
                numeric_value=100.0,
                metric_id="cash",
                metric_label_raw="Cash",
                extensions={
                    "source_kind": "statement_row",
                    "source_policy": "supplement_only",
                },
            ),
            _candidate(
                fact_id="note-cash-blocked",
                period_id="2024Q1",
                source_rank_hint=2,
                numeric_value=120.0,
                metric_id="cash",
                metric_label_raw="Cash",
                extraction_method="note_disclosure",
                extensions={
                    "source_kind": "deterministic_note_disclosure",
                    "source_policy": "blocked",
                },
            ),
        ]
    )

    assert len(result.canonical_facts) == 1
    canonical = result.canonical_facts[0]
    assert canonical.numeric_value == 100.0
    assert canonical.validation_flags == ["blocked_competing_candidate"]
    assert len(result.review_packets) == 1
    packet = result.review_packets[0]
    assert packet.conflict_state == "blocked"


def test_pipeline_carries_p4a_review_packets_and_sets_review_quality_gate() -> None:
    result = analyze_report(
        document_ref={"document_id": "doc-p4a", "market": "HK", "language": "en"},
        extracted_payload={
            "candidate_facts": [
                {
                    "fact_id": "candidate-statement",
                    "metric_id": "total_assets",
                    "metric_label_raw": "Total assets",
                    "statement_type": "balance_sheet",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "HKD",
                    "raw_value": "100",
                    "numeric_value": 100.0,
                    "raw_unit": None,
                    "normalized_unit": None,
                    "precision": 0,
                    "confidence": 0.9,
                    "document_id": "doc-p4a",
                    "block_id": "statement:block",
                    "page_index": 1,
                    "evidence_bundle_id": "bundle-statement",
                    "extraction_method": "table_semantics",
                    "source_rank_hint": 30,
                    "extensions": {
                        "table_kind": "balance_sheet",
                        "source_kind": "statement_row",
                        "source_policy": "supplement_only",
                    },
                },
                {
                    "fact_id": "candidate-note",
                    "metric_id": "total_assets",
                    "metric_label_raw": "Total assets",
                    "statement_type": "balance_sheet",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "HKD",
                    "raw_value": "120",
                    "numeric_value": 120.0,
                    "raw_unit": None,
                    "normalized_unit": None,
                    "precision": 0,
                    "confidence": 0.9,
                    "document_id": "doc-p4a",
                    "block_id": "note:block",
                    "page_index": 20,
                    "evidence_bundle_id": "bundle-note",
                    "extraction_method": "note_disclosure",
                    "source_rank_hint": 18,
                    "extensions": {
                        "table_kind": "note_disclosure",
                        "source_kind": "deterministic_note_disclosure",
                        "source_policy": "review_required",
                    },
                },
            ]
        },
    )

    assert result.quality_gate == "review"
    assert result.validation_report.issues == ("source_conflict",)
    assert len(result.review_packets) == 1
    assert result.review_packets[0].to_dict()["metric_id"] == "total_assets"


def test_analyze_report_promotes_phase1_metrics_to_canonical_with_stable_provenance() -> (
    None
):
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
    assert {"basic_eps", "n_income_attr_p", "finance_exp"} <= set(canonical_metric_ids)
    basic_eps = next(
        fact
        for fact in pipeline_result.canonical_facts
        if fact.metric_id == "basic_eps"
    )
    assert basic_eps.normalized_unit == "per_share_amount"
    assert basic_eps.numeric_value == 1.23
    n_income_attr_p = next(
        fact
        for fact in pipeline_result.canonical_facts
        if fact.metric_id == "n_income_attr_p"
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


def test_analyze_report_blocks_provisional_custom_metric_from_canonical_facts() -> (
    None
):
    result = analyze_report(
        document_ref={"document_id": "doc-1", "market": "CN"},
        extracted_payload={
            "candidate_facts": [
                {
                    "fact_id": "cand-custom-1",
                    "metric_id": "unknown",
                    "metric_label_raw": "Customer loyalty liabilities",
                    "statement_type": "balance_sheet",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "CNY",
                    "raw_value": "1000",
                    "numeric_value": 1000.0,
                    "raw_unit": "CNY",
                    "normalized_unit": None,
                    "precision": 2,
                    "confidence": 0.95,
                    "document_id": "doc-1",
                    "block_id": "block-1",
                    "table_id": "table-1",
                    "page_index": 1,
                    "table_coord": "A1",
                    "evidence_bundle_id": "bundle-1",
                    "evidence_span": "Customer loyalty liabilities 1000",
                    "snapshot_path": None,
                    "extraction_method": "table_skill",
                    "extraction_version": "v1",
                    "source_rank_hint": 1,
                }
            ]
        },
    )

    assert result.canonical_facts == []
    assert result.derived_facts == []
    assert result.quality_gate == "review"
    assert result.validation_report.overall_status == "review_required"
    assert "provisional_metric_review_required" in result.validation_report.issues
    assert len(result.review_packets) == 1
    packet = result.review_packets[0]
    assert packet.metric_id.startswith("custom::")
    assert packet.source_policy == "review_required"
    assert packet.conflict_state == "provisional_metric_review_required"
    assert packet.competing_candidate_values == ()
    assert packet.evidence_bundle_id == "bundle-1"
    assert packet.resolution_reason == "blocked_provisional_metric"
    assert (
        packet.review_reason
        == "provisional custom metric requires review before automatic analysis"
    )


def test_provisional_custom_quarterly_candidates_do_not_produce_ttm_facts() -> (
    None
):
    result = analyze_report(
        document_ref={"document_id": "doc-1", "market": "US"},
        extracted_payload={
            "candidate_facts": [
                {
                    "fact_id": f"cand-custom-{quarter}",
                    "metric_id": "unknown",
                    "metric_label_raw": "Customer loyalty liabilities",
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": f"2025Q{quarter}",
                    "currency": "USD",
                    "raw_value": str(quarter * 100),
                    "numeric_value": float(quarter * 100),
                    "raw_unit": "USD million",
                    "normalized_unit": None,
                    "precision": 2,
                    "confidence": 0.95,
                    "extensions": {
                        "period_type": "DURATION",
                        "fiscal_year": 2025,
                        "reporting_scope": f"Q{quarter}",
                    },
                    "document_id": "doc-1",
                    "block_id": f"block-{quarter}",
                    "table_id": "table-1",
                    "page_index": 1,
                    "table_coord": f"A{quarter}",
                    "evidence_bundle_id": f"bundle-{quarter}",
                    "evidence_span": (
                        f"Customer loyalty liabilities {quarter * 100}"
                    ),
                    "snapshot_path": None,
                    "extraction_method": "table_skill",
                    "extraction_version": "v1",
                    "source_rank_hint": quarter,
                }
                for quarter in range(1, 5)
            ]
        },
    )

    assert result.canonical_facts == []
    assert result.derived_facts == []
    assert result.quality_gate == "review"
    assert "provisional_metric_review_required" in result.validation_report.issues


def test_validation_reports_provisional_metric_review_issue() -> None:
    result = analyze_report(
        document_ref={"document_id": "doc-1", "market": "CN"},
        extracted_payload={
            "candidate_facts": [
                {
                    "fact_id": "cand-custom-1",
                    "metric_id": "unknown",
                    "metric_label_raw": "Customer loyalty liabilities",
                    "statement_type": "balance_sheet",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "CNY",
                    "raw_value": "1000",
                    "numeric_value": 1000.0,
                    "raw_unit": "CNY",
                    "normalized_unit": None,
                    "precision": 2,
                    "confidence": 0.95,
                    "document_id": "doc-1",
                    "block_id": "block-1",
                    "table_id": "table-1",
                    "page_index": 1,
                    "table_coord": "A1",
                    "evidence_bundle_id": "bundle-1",
                    "evidence_span": "Customer loyalty liabilities 1000",
                    "snapshot_path": None,
                    "extraction_method": "table_skill",
                    "extraction_version": "v1",
                    "source_rank_hint": 1,
                }
            ]
        },
    )

    assert (
        result.validation_report.issues.count(
            "provisional_metric_review_required"
        )
        == 1
    )


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


def test_analyze_report_promotes_income_statement_core_metrics_to_canonical_facts() -> (
    None
):
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


def test_table_candidate_facts_emit_p4c_income_statement_candidates_with_deterministic_provenance() -> (
    None
):
    candidate_facts = build_table_candidate_facts(
        [
            normalize_table_semantics(
                ParsedTable(
                    table_id="table-p4c-income-contract",
                    document_id="doc-1",
                    page_range=(1, 1),
                    table_kind="income_statement",
                    title_text="Consolidated Statement of Profit or Loss",
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
                            row_id="row-revenue",
                            row_index=1,
                            label_raw="Turnover",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=1,
                                    column_index=1,
                                    text_raw="1,000",
                                    numeric_value=1000.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-cost",
                            row_index=2,
                            label_raw="Cost of sales",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=2,
                                    column_index=1,
                                    text_raw="800",
                                    numeric_value=800.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-operating-profit",
                            row_index=3,
                            label_raw="Profit from operations",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=3,
                                    column_index=1,
                                    text_raw="200",
                                    numeric_value=200.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-net-profit",
                            row_index=4,
                            label_raw="净利润",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=4,
                                    column_index=1,
                                    text_raw="120",
                                    numeric_value=120.0,
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
        "revenue",
        "operating_cost",
        "operating_profit",
        "net_profit",
    }
    assert all(fact["statement_type"] == "income_statement" for fact in candidate_facts)
    assert all(fact["period_id"] == "2025FY" for fact in candidate_facts)
    assert all(fact["entity_scope"] == "consolidated" for fact in candidate_facts)
    assert all(
        fact["extensions"]["table_kind"] == "income_statement"
        for fact in candidate_facts
    )
    assert all(
        fact["extensions"]["semantic_source"] == "deterministic"
        for fact in candidate_facts
    )


def test_table_candidate_facts_emit_p4c_balance_sheet_totals_with_deterministic_provenance() -> (
    None
):
    candidate_facts = build_table_candidate_facts(
        [
            normalize_table_semantics(
                ParsedTable(
                    table_id="table-p4c-balance-contract",
                    document_id="doc-1",
                    page_range=(1, 1),
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
                        )
                    ],
                    body_rows=[
                        ParsedRow(
                            row_id="row-assets",
                            row_index=1,
                            label_raw="资产总计",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=1,
                                    column_index=1,
                                    text_raw="9,000",
                                    numeric_value=9000.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-liabilities",
                            row_index=2,
                            label_raw="Total liabilities",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=2,
                                    column_index=1,
                                    text_raw="5,000",
                                    numeric_value=5000.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-owner-equity",
                            row_index=3,
                            label_raw="归属于母公司股东权益",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=3,
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
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    assert {fact["metric_id"] for fact in candidate_facts} == {
        "total_assets",
        "total_liabilities",
        "equity_attributable_to_owners",
    }
    assert all(fact["statement_type"] == "balance_sheet" for fact in candidate_facts)
    assert all(fact["period_id"] == "2025FY" for fact in candidate_facts)
    assert all(fact["entity_scope"] == "consolidated" for fact in candidate_facts)
    assert all(
        fact["extensions"]["table_kind"] == "balance_sheet"
        for fact in candidate_facts
    )
    assert all(
        fact["extensions"]["semantic_source"] == "deterministic"
        for fact in candidate_facts
    )


def test_table_candidate_facts_emit_p4d_parent_statement_candidates() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            normalize_table_semantics(
                ParsedTable(
                    table_id="table-p4d-parent-balance",
                    document_id="doc-1",
                    page_range=(1, 1),
                    table_kind="balance_sheet",
                    title_text="母公司资产负债表",
                    statement_scope_guess="parent_only",
                    table_unit="元",
                    table_currency="CNY",
                    period_columns=[
                        ParsedColumn(
                            column_id="column-1",
                            column_index=1,
                            header_text="2025年12月31日",
                            period_id="2025FY",
                            comparison_axis="current",
                            value_time_shape="point",
                            is_current=True,
                        )
                    ],
                    body_rows=[
                        ParsedRow(
                            row_id="row-cash",
                            row_index=1,
                            label_raw="货币资金",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=1,
                                    column_index=1,
                                    text_raw="800",
                                    numeric_value=800.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-lt-eqt-invest",
                            row_index=2,
                            label_raw="长期股权投资",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=2,
                                    column_index=1,
                                    text_raw="2,500",
                                    numeric_value=2500.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-equity",
                            row_index=3,
                            label_raw="所有者权益合计",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=3,
                                    column_index=1,
                                    text_raw="3,200",
                                    numeric_value=3200.0,
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
        market="CN",
    )

    assert {fact["metric_id"] for fact in candidate_facts} == {
        "cash",
        "lt_eqt_invest",
        "equity",
    }
    assert all(fact["entity_scope"] == "parent_company" for fact in candidate_facts)
    assert all(
        fact["extensions"]["statement_scope_guess"] == "parent_only"
        for fact in candidate_facts
    )


def test_analyze_report_keeps_parent_and_consolidated_facts_on_separate_tracks() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            _normalized_table_semantics(
                table_id="table-consolidated-cash",
                document_id="doc-1",
                table_kind="balance_sheet",
                period_id="2025FY",
                rows=[("货币资金", "cash and cash equivalents", 1000.0)],
                statement_scope_guess="consolidated",
            ),
            _normalized_table_semantics(
                table_id="table-parent-cash",
                document_id="doc-1",
                table_kind="balance_sheet",
                period_id="2025FY",
                rows=[
                    ("货币资金", "cash and cash equivalents", 800.0),
                    ("长期股权投资", "long-term equity investments", 2500.0),
                ],
                statement_scope_guess="parent_only",
            ),
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="CN",
    )

    result = analyze_report(
        {"document_id": "doc-1", "market": "CN", "language": "zh"},
        {"candidate_facts": candidate_facts},
    )

    cash_facts = [fact for fact in result.canonical_facts if fact.metric_id == "cash"]
    assert len(cash_facts) == 2
    assert {fact.entity_scope for fact in cash_facts} == {
        "consolidated",
        "parent_company",
    }

    parent_lte = [
        fact for fact in result.canonical_facts if fact.metric_id == "lt_eqt_invest"
    ]
    assert len(parent_lte) == 1
    assert parent_lte[0].entity_scope == "parent_company"


def test_table_candidate_facts_emit_p4e_target_candidates() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            normalize_table_semantics(
                ParsedTable(
                    table_id="table-p4e-balance",
                    document_id="doc-1",
                    page_range=(1, 1),
                    table_kind="balance_sheet",
                    title_text="Consolidated Statement of Financial Position",
                    statement_scope_guess="consolidated",
                    table_unit="元",
                    table_currency="CNY",
                    period_columns=[
                        ParsedColumn(
                            column_id="column-1",
                            column_index=1,
                            header_text="2025年12月31日",
                            period_id="2025FY",
                            comparison_axis="current",
                            value_time_shape="point",
                            is_current=True,
                        )
                    ],
                    body_rows=[
                        ParsedRow(
                            row_id="row-fix-assets",
                            row_index=1,
                            label_raw="固定资产",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=1,
                                    column_index=1,
                                    text_raw="5,000",
                                    numeric_value=5000.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-cip",
                            row_index=2,
                            label_raw="在建工程",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=2,
                                    column_index=1,
                                    text_raw="900",
                                    numeric_value=900.0,
                                    page_index=1,
                                )
                            ],
                        ),
                    ],
                )
            ),
            normalize_table_semantics(
                ParsedTable(
                    table_id="table-p4e-income",
                    document_id="doc-1",
                    page_range=(2, 2),
                    table_kind="income_statement",
                    title_text="合并利润表",
                    statement_scope_guess="consolidated",
                    table_unit="元",
                    table_currency="CNY",
                    period_columns=[
                        ParsedColumn(
                            column_id="column-1",
                            column_index=1,
                            header_text="2025年度",
                            period_id="2025FY",
                            comparison_axis="current",
                            value_time_shape="duration",
                            is_current=True,
                        )
                    ],
                    body_rows=[
                        ParsedRow(
                            row_id="row-rd",
                            row_index=1,
                            label_raw="研发费用",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=1,
                                    column_index=1,
                                    text_raw="120",
                                    numeric_value=120.0,
                                    page_index=2,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-invest-income",
                            row_index=2,
                            label_raw="投资收益",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=2,
                                    column_index=1,
                                    text_raw="80",
                                    numeric_value=80.0,
                                    page_index=2,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-asset-disp",
                            row_index=3,
                            label_raw="资产处置收益",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=3,
                                    column_index=1,
                                    text_raw="20",
                                    numeric_value=20.0,
                                    page_index=2,
                                )
                            ],
                        ),
                    ],
                )
            ),
            normalize_table_semantics(
                ParsedTable(
                    table_id="table-p4e-cash-flow",
                    document_id="doc-1",
                    page_range=(3, 3),
                    table_kind="cash_flow_statement",
                    title_text="合并现金流量表",
                    statement_scope_guess="consolidated",
                    table_unit="元",
                    table_currency="CNY",
                    period_columns=[
                        ParsedColumn(
                            column_id="column-1",
                            column_index=1,
                            header_text="2025年度",
                            period_id="2025FY",
                            comparison_axis="current",
                            value_time_shape="duration",
                            is_current=True,
                        )
                    ],
                    body_rows=[
                        ParsedRow(
                            row_id="row-disp-cash",
                            row_index=1,
                            label_raw="处置固定资产、无形资产和其他长期资产收回的现金",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=1,
                                    column_index=1,
                                    text_raw="60",
                                    numeric_value=60.0,
                                    page_index=3,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-invest-return-cash",
                            row_index=2,
                            label_raw="取得投资收益收到的现金",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=2,
                                    column_index=1,
                                    text_raw="45",
                                    numeric_value=45.0,
                                    page_index=3,
                                )
                            ],
                        ),
                    ],
                )
            ),
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="CN",
    )

    assert {fact["metric_id"] for fact in candidate_facts} == {
        "fix_assets",
        "cip",
        "rd_exp",
        "invest_income",
        "asset_disp_income",
        "n_recp_disp_fiolta",
        "c_recp_return_invest",
    }
    assert all(fact["entity_scope"] == "consolidated" for fact in candidate_facts)
    assert all(
        fact["extensions"]["semantic_source"] == "deterministic"
        for fact in candidate_facts
    )


def test_table_candidate_facts_skip_p4e_negative_controls() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            _normalized_table_semantics(
                table_id="table-p4e-negatives-balance",
                document_id="doc-1",
                table_kind="balance_sheet",
                period_id="2025FY",
                rows=[
                    ("investment properties", None, 100.0),
                    ("right-of-use assets", None, 90.0),
                    ("capitalized development costs", None, 80.0),
                ],
                statement_scope_guess="consolidated",
            ),
            NormalizedTableSemantics(
                table_id="table-p4e-negatives-income",
                document_id="doc-1",
                page_range=(2, 2),
                table_kind="income_statement",
                title_text="Consolidated Statement of Profit or Loss",
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
                        row_id="row-interest-income",
                        label_raw="interest income",
                        normalized_row_label="interest income",
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="10",
                                numeric_value=10.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                    NormalizedTableRow(
                        row_id="row-fv-gain",
                        label_raw="公允价值变动收益",
                        normalized_row_label="公允价值变动收益",
                        values=[
                            NormalizedTableCellValue(
                                row_index=2,
                                column_index=1,
                                raw_text="12",
                                numeric_value=12.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                ],
            ),
            NormalizedTableSemantics(
                table_id="table-p4e-negatives-cash-flow",
                document_id="doc-1",
                page_range=(3, 3),
                table_kind="cash_flow_statement",
                title_text="Consolidated Statement of Cash Flows",
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
                        row_id="row-investing-total",
                        label_raw="投资活动产生的现金流量净额",
                        normalized_row_label="investing cash flow",
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="150",
                                numeric_value=150.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                    NormalizedTableRow(
                        row_id="row-cash-recovered-investment",
                        label_raw="收回投资收到的现金",
                        normalized_row_label="收回投资收到的现金",
                        values=[
                            NormalizedTableCellValue(
                                row_index=2,
                                column_index=1,
                                raw_text="40",
                                numeric_value=40.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                ],
            ),
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    assert {
        fact["metric_id"]
        for fact in candidate_facts
        if fact["metric_id"]
        in {
            "fix_assets",
            "cip",
            "rd_exp",
            "invest_income",
            "asset_disp_income",
            "n_recp_disp_fiolta",
            "c_recp_return_invest",
        }
    } == set()


def test_table_candidate_facts_emit_p4c_cash_flow_detail_candidates_with_deterministic_provenance() -> (
    None
):
    candidate_facts = build_table_candidate_facts(
        [
            normalize_table_semantics(
                ParsedTable(
                    table_id="table-p4c-cash-flow-contract",
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
                        ParsedRow(
                            row_id="row-staff",
                            row_index=4,
                            label_raw="Cash paid to and on behalf of employees",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=4,
                                    column_index=1,
                                    text_raw="120",
                                    numeric_value=120.0,
                                    page_index=1,
                                )
                            ],
                        ),
                        ParsedRow(
                            row_id="row-taxes",
                            row_index=5,
                            label_raw="支付的各项税费",
                            normalized_label_hint=None,
                            value_cells=[
                                ParsedCell(
                                    row_index=5,
                                    column_index=1,
                                    text_raw="80",
                                    numeric_value=80.0,
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
        "c_pay_to_staff",
        "c_paid_for_taxes",
    }
    assert all(
        fact["statement_type"] == "cash_flow_statement" for fact in candidate_facts
    )
    assert all(fact["period_id"] == "2025FY" for fact in candidate_facts)
    assert all(fact["entity_scope"] == "consolidated" for fact in candidate_facts)
    assert all(
        fact["extensions"]["table_kind"] == "cash_flow_statement"
        for fact in candidate_facts
    )
    assert all(
        fact["extensions"]["semantic_source"] == "deterministic"
        for fact in candidate_facts
    )


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


def test_analyze_report_promotes_cash_flow_primary_sections_to_canonical_facts() -> (
    None
):
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


def test_analyze_report_promotes_equity_and_attributable_equity_to_canonical_facts() -> (
    None
):
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
    assert all(
        fact.extensions["semantic_source"] == "deterministic"
        for fact in result.canonical_facts
    )


def test_balance_sheet_english_attributable_equity_survives_to_candidate_facts() -> (
    None
):
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
    assert (
        candidate["metric_label_raw"] == "Equity attributable to owners of the parent"
    )
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
    assert (
        candidate_facts[0]["extensions"]["currency_semantic_source"] == "deterministic"
    )


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
        raise AssertionError("link_evidence_bundle_item should reject missing bundles")


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


def test_pdf_ingestion_adapter_wires_cash_health_note_candidates_and_missing_status(
    monkeypatch,
    tmp_path,
) -> None:
    adapter = PdfIngestionAdapter()
    pdf_path = tmp_path / "mock-hk-cash-health.pdf"
    pdf_path.touch()

    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text_pages",
        lambda self, *, pdf_path, pdf_url: [
                (
                    12,
                    "\n".join(
                        [
                            "2025 Annual Report",
                            "Restricted cash and cash equivalents",
                            "RMB 150 million as of December 31, 2025.",
                            "Cash paid for interest 25",
                            "Time deposits 80",
                        ]
                    ),
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
        market="HK",
        min_confidence=0.8,
    )

    metric_ids = {
        candidate["metric_id"] for candidate in payload["candidate_facts"]
    }
    assert {
        "restricted_cash",
        "interest_paid_cash",
        "time_deposits_or_wealth_products",
    }.issubset(metric_ids)
    assert payload["document_metadata"]["cash_health_missing_status"] == {
        "restricted_cash": "present",
        "interest_paid_cash": "present",
        "time_deposits_or_wealth_products": "present",
    }
