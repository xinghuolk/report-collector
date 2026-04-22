import re

import pytest

from financial_report_analysis.ingestion import note_disclosure as note_disclosure_module
from financial_report_analysis.ingestion import (
    build_asset_note_candidate_facts,
    build_debt_note_candidate_facts,
    build_working_capital_note_candidate_facts,
)
from financial_report_analysis.semantic_fallback import DisclosureLocatorResult


# HK 09987 2025 annual note/disclosure rows independently disclose short-term
# borrowings only. Long-term borrowings, bonds payable, and current portion of
# long-term debt are not separately disclosed in the sampled note rows.
_HK_09987_2025_DEBT_NOTE_TITLE_PAGE = (
    153,
    """
    Borrowings 2024 2023
    """,
)

_HK_09987_2025_DEBT_NOTE_PAGE = (
    154,
    """
    Short-term borrowings 127 168
    Non-current operating lease liabilities 1,816 1,899
    Non-current finance lease liabilities 49 44
    """,
)

_DEBT_METRIC_IDS = {
    "st_borr",
    "lt_borr",
    "bond_payable",
    "non_cur_liab_due_1y",
}


_PAYABLE_NOTE_PAGE = (
    178,
    """
    Accounts Payable and Other Current Liabilities 2024 2023
    Accounts payable $ 801 $ 786
    Contract liabilities 196 196
    Accounts payable and other current liabilities $ 2,080 $ 2,164
    """,
)

_P3_ASSET_NOTE_DEFINITIONS = (
    {
        "surface_patterns": (
            re.compile(r"\bcontract\s+assets\b[^\n]{0,120}\b20\d{2}\b", re.IGNORECASE),
            re.compile(
                r"\bother\s+non[-\s]+current\s+assets\b[^\n]{0,120}\b20\d{2}\b",
                re.IGNORECASE,
            ),
        ),
        "metrics": (
            {
                "metric_id": "contract_assets",
                "label": "Contract assets",
                "row_pattern": re.compile(
                    r"(?mi)^\s*contract\s+assets\b(?:\s*\([^)]+\))?\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
            {
                "metric_id": "other_non_current_assets",
                "label": "Other non-current assets",
                "row_pattern": re.compile(
                    r"(?mi)^\s*other\s+non[-\s]+current\s+assets\b(?:\s*\([^)]+\))?\s+(?:HK\$|\$)?\s*([\(]?\d[\d,]*(?:\.\d+)?\)?)(?:\s|$)"
                ),
            },
        ),
    },
)


class _StubSemanticFallbackService:
    def __init__(self, *results: DisclosureLocatorResult) -> None:
        self._results = list(results)
        self.requests = []

    def locate_disclosure_metric(self, request: object) -> DisclosureLocatorResult:
        self.requests.append(request)
        if not self._results:
            raise AssertionError("locator called without a queued result")
        return self._results.pop(0)


def _build_p3_asset_note_candidate_facts(
    *,
    pages: list[tuple[int, str]],
) -> tuple[list[dict[str, object]], dict[str, str]]:
    candidates, missing_status, _, _ = note_disclosure_module._build_note_candidate_facts(
        pages=pages,
        document_id="doc:09987",
        period_id="2025FY",
        market="HK",
        existing_metric_ids=set(),
        note_definitions=_P3_ASSET_NOTE_DEFINITIONS,
    )
    return candidates, missing_status


def test_build_working_capital_note_candidate_facts_extracts_hk_09987_candidates() -> None:
    candidates, missing_status = build_working_capital_note_candidate_facts(
        pages=[_PAYABLE_NOTE_PAGE],
        document_id="doc:09987",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert {candidate["metric_id"] for candidate in candidates} == {
        "acct_payable",
        "contract_liab",
    }
    assert {candidate["numeric_value"] for candidate in candidates} == {801.0, 196.0}
    assert all(
        candidate["extraction_method"] == "note_disclosure" for candidate in candidates
    )
    assert all(
        candidate["extensions"]["semantic_source"] == "deterministic"
        for candidate in candidates
    )
    assert missing_status["acct_payable"] == "present"
    assert missing_status["contract_liab"] == "present"


def test_build_working_capital_note_candidate_facts_does_not_create_notes_candidates() -> None:
    candidates, _ = build_working_capital_note_candidate_facts(
        pages=[_PAYABLE_NOTE_PAGE],
        document_id="doc:09987",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    metric_ids = {candidate["metric_id"] for candidate in candidates}

    assert "notes_receiv" not in metric_ids
    assert "notes_payable" not in metric_ids


def test_build_p3_asset_note_candidate_facts_extracts_contract_assets_from_bounded_fragment() -> (
    None
):
    candidates, missing_status = build_asset_note_candidate_facts(
        pages=[
            (
                301,
                """
                Contract assets 2024 2023
                Contract assets 80 65
                """,
            )
        ],
        document_id="doc:09987",
        period_id="2025FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert {candidate["metric_id"] for candidate in candidates} == {"contract_assets"}
    assert candidates[0]["metric_label_raw"] == "Contract assets"
    assert candidates[0]["numeric_value"] == 80.0
    assert candidates[0]["extraction_method"] == "note_disclosure"
    assert candidates[0]["extensions"]["semantic_source"] == "deterministic"
    assert missing_status == {
        "contract_assets": "present",
        "other_non_current_assets": "absent",
    }


def test_build_p3_asset_note_candidate_facts_extracts_other_non_current_assets_from_bounded_fragment() -> (
    None
):
    candidates, missing_status = build_asset_note_candidate_facts(
        pages=[
            (
                302,
                """
                Other non-current assets 2024 2023
                Other non-current assets 120 95
                """,
            )
        ],
        document_id="doc:09987",
        period_id="2025FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert {candidate["metric_id"] for candidate in candidates} == {
        "other_non_current_assets"
    }
    assert candidates[0]["metric_label_raw"] == "Other non-current assets"
    assert candidates[0]["numeric_value"] == 120.0
    assert candidates[0]["extraction_method"] == "note_disclosure"
    assert candidates[0]["extensions"]["semantic_source"] == "deterministic"
    assert missing_status == {
        "contract_assets": "absent",
        "other_non_current_assets": "present",
    }


def test_build_p3_asset_note_candidate_facts_ignores_negative_control_asset_rows() -> None:
    candidates, missing_status = build_asset_note_candidate_facts(
        pages=[
            (
                303,
                """
                Contract assets 2024 2023
                Restricted cash 33 21
                Investment properties 44 40
                Prepayments 18 17
                Deferred tax assets 27 24
                Capitalized development costs 61 59
                Total non-current assets 999 888
                """,
            )
        ],
        document_id="doc:09987",
        period_id="2025FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert candidates == []
    assert missing_status == {
        "contract_assets": "absent",
        "other_non_current_assets": "absent",
    }


def test_build_p3_asset_note_candidate_facts_preserves_existing_metric_precedence() -> (
    None
):
    candidates, missing_status = build_asset_note_candidate_facts(
        pages=[
            (
                305,
                """
                Contract assets 2024 2023
                Contract assets 80 65
                Other non-current assets 120 95
                """,
            )
        ],
        document_id="doc:09987",
        period_id="2025FY",
        market="HK",
        existing_metric_ids={"contract_assets"},
        semantic_fallback_service=None,
    )

    assert {candidate["metric_id"] for candidate in candidates} == {
        "other_non_current_assets"
    }
    assert candidates[0]["numeric_value"] == 120.0
    assert missing_status == {
        "contract_assets": "present",
        "other_non_current_assets": "present",
    }


def test_build_p3_asset_note_candidate_facts_keeps_not_surfaced_without_asset_note_block() -> (
    None
):
    candidates, missing_status = build_asset_note_candidate_facts(
        pages=[
            (
                304,
                """
                Intangible assets 2024 2023
                Goodwill 44 40
                Inventories 18 17
                """,
            )
        ],
        document_id="doc:09987",
        period_id="2025FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert candidates == []
    assert missing_status == {
        "contract_assets": "not_surfaced",
        "other_non_current_assets": "not_surfaced",
    }


def test_build_debt_note_candidate_facts_extracts_hk_09987_2025_subset() -> None:
    candidates, missing_status = build_debt_note_candidate_facts(
        pages=[_HK_09987_2025_DEBT_NOTE_TITLE_PAGE, _HK_09987_2025_DEBT_NOTE_PAGE],
        document_id="doc:09987",
        period_id="2025FY",
        market="HK",
        existing_metric_ids=set(),
    )

    metric_ids = {candidate["metric_id"] for candidate in candidates}

    assert metric_ids == {"st_borr"}
    assert candidates[0]["numeric_value"] == 127.0
    assert all(
        candidate["extraction_method"] == "note_disclosure" for candidate in candidates
    )
    assert missing_status["st_borr"] == "present"
    assert missing_status["lt_borr"] == "absent"
    assert missing_status["bond_payable"] == "absent"
    assert missing_status["non_cur_liab_due_1y"] == "absent"
    assert "bond_payable" not in metric_ids


def test_build_debt_note_candidate_facts_extracts_multiple_debt_rows() -> None:
    candidates, missing_status = build_debt_note_candidate_facts(
        pages=[
            (
                178,
                """
                Borrowings 2024 2023
                Short-term borrowings 120 110
                Long-term borrowings 560 600
                Current portion of long-term debt 80 75
                """,
            )
        ],
        document_id="doc:debt",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
    )

    assert {candidate["metric_id"] for candidate in candidates} == {
        "st_borr",
        "lt_borr",
        "non_cur_liab_due_1y",
    }
    assert {candidate["numeric_value"] for candidate in candidates} == {120.0, 560.0, 80.0}
    assert all(
        candidate["extraction_method"] == "note_disclosure" for candidate in candidates
    )
    assert missing_status["bond_payable"] == "absent"


def test_build_debt_note_candidate_facts_reads_continuation_pages_without_repeated_surface_title() -> (
    None
):
    candidates, missing_status = build_debt_note_candidate_facts(
        pages=[
            (
                210,
                """
                Borrowings 2024 2023
                """,
            ),
            (
                211,
                """
                Long-term borrowings 560 600
                Current portion of long-term debt 80 75
                """,
            ),
        ],
        document_id="doc:debt",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
    )

    assert {candidate["metric_id"] for candidate in candidates} == {
        "lt_borr",
        "non_cur_liab_due_1y",
    }
    assert {candidate["page_index"] for candidate in candidates} == {211}
    assert missing_status["st_borr"] == "absent"
    assert missing_status["bond_payable"] == "absent"


def test_build_debt_note_candidate_facts_surfaces_long_term_only_debt_notes() -> None:
    candidates, missing_status = build_debt_note_candidate_facts(
        pages=[
            (
                220,
                """
                Long-term borrowings 2024 2023
                """,
            ),
            (
                221,
                """
                Long-term borrowings 560 600
                """,
            )
        ],
        document_id="doc:debt",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
    )

    assert {candidate["metric_id"] for candidate in candidates} == {"lt_borr"}
    assert candidates[0]["numeric_value"] == 560.0
    assert candidates[0]["page_index"] == 221
    assert missing_status["lt_borr"] == "present"
    assert missing_status["st_borr"] == "absent"


def test_build_debt_note_candidate_facts_ignores_non_debt_liability_rows() -> None:
    candidates, _ = build_debt_note_candidate_facts(
        pages=[
            (
                178,
                """
                Accounts payable and other current liabilities 2024 2023
                Accounts payable 801 786
                Operating lease liabilities 417 426
                Contract liabilities 196 196
                """,
            )
        ],
        document_id="doc:debt",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
    )

    assert candidates == []


def test_build_debt_note_candidate_facts_does_not_activate_without_debt_disclosure_block() -> None:
    candidates, missing_status = build_debt_note_candidate_facts(
        pages=[
            (
                230,
                """
                Discussion of financing strategy
                Short-term borrowings 127 168
                """,
            )
        ],
        document_id="doc:debt",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
    )

    assert candidates == []
    assert missing_status == {
        "st_borr": "not_surfaced",
        "lt_borr": "not_surfaced",
        "bond_payable": "not_surfaced",
        "non_cur_liab_due_1y": "not_surfaced",
    }


def test_build_working_capital_note_candidate_facts_tracks_note_statuses() -> None:
    _, missing_status = build_working_capital_note_candidate_facts(
        pages=[_PAYABLE_NOTE_PAGE],
        document_id="doc:09987",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert missing_status["notes_receiv"] == "absent"
    assert missing_status["notes_payable"] == "absent"
    assert missing_status["adv_receipts"] == "not_surfaced"


def test_build_working_capital_note_candidate_facts_supports_parenthesized_values() -> None:
    candidates, _ = build_working_capital_note_candidate_facts(
        pages=[
            (
                178,
                """
                Accounts Payable and Other Current Liabilities 2024 2023
                Accounts payable $ (801) $ 786
                Contract liabilities (196) 196
                """,
            )
        ],
        document_id="doc:09987",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert {candidate["metric_id"] for candidate in candidates} == {
        "acct_payable",
        "contract_liab",
    }
    assert {candidate["numeric_value"] for candidate in candidates} == {-801.0, -196.0}


def test_build_working_capital_note_candidate_facts_reads_follow_on_pages_after_surface() -> None:
    candidates, _ = build_working_capital_note_candidate_facts(
        pages=[
            (
                178,
                """
                Accounts Payable and Other Current Liabilities 2024 2023
                """,
            ),
            (
                179,
                """
                Accounts payable $ 801 $ 786
                Contract liabilities 196 196
                """,
            ),
        ],
        document_id="doc:09987",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert {candidate["metric_id"] for candidate in candidates} == {
        "acct_payable",
        "contract_liab",
    }
    assert {candidate["page_index"] for candidate in candidates} == {179}


def test_build_working_capital_note_candidate_facts_uses_locator_on_continuation_page() -> (
    None
):
    service = _StubSemanticFallbackService(
        DisclosureLocatorResult(
            metric_id="contract_liab",
            matched_label="Contract liabilities",
            source_text_span="Contract liabilities 196 196",
            semantic_source="llm_fallback",
            semantic_confidence=0.91,
            fallback_reason="missing_statement_row",
        )
    )

    candidates, missing_status = build_working_capital_note_candidate_facts(
        pages=[
            (
                178,
                """
                Accounts Payable and Other Current Liabilities 2024 2023
                """,
            ),
            (
                179,
                """
                Accounts payable $ 801 $ 786
                Accounts payable and other current liabilities $ 2,080 $ 2,164
                """,
            ),
        ],
        document_id="doc:09987",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=service,
    )

    assert len(service.requests) == 1
    assert "Accounts payable $ 801 $ 786" in service.requests[0].local_context
    assert {candidate["metric_id"] for candidate in candidates} == {
        "acct_payable",
        "contract_liab",
    }
    contract_liab = next(
        candidate
        for candidate in candidates
        if candidate["metric_id"] == "contract_liab"
    )
    assert contract_liab["page_index"] == 179
    assert contract_liab["extensions"]["semantic_source"] == "llm_fallback"
    assert missing_status["contract_liab"] == "present"


def test_build_working_capital_note_candidate_facts_uses_locator_for_missing_target_metric() -> (
    None
):
    service = _StubSemanticFallbackService(
        DisclosureLocatorResult(
            metric_id="contract_liab",
            matched_label="Contract liabilities",
            source_text_span="Contract liabilities 196 196",
            semantic_source="llm_fallback",
            semantic_confidence=0.91,
            fallback_reason="missing_statement_row",
        )
    )

    candidates, missing_status = build_working_capital_note_candidate_facts(
        pages=[
            (
                178,
                """
                Accounts Payable and Other Current Liabilities 2024 2023
                Accounts payable $ 801 $ 786
                Accounts payable and other current liabilities $ 2,080 $ 2,164
                """,
            )
        ],
        document_id="doc:09987",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=service,
    )

    assert len(service.requests) == 1
    assert {candidate["metric_id"] for candidate in candidates} == {
        "acct_payable",
        "contract_liab",
    }
    contract_liab = next(
        candidate
        for candidate in candidates
        if candidate["metric_id"] == "contract_liab"
    )
    assert contract_liab["extensions"]["semantic_source"] == "llm_fallback"
    assert contract_liab["extensions"]["fallback_reason"] == "missing_statement_row"
    assert missing_status["contract_liab"] == "present"


def test_build_working_capital_note_candidate_facts_ignores_unparseable_locator_span() -> (
    None
):
    service = _StubSemanticFallbackService(
        DisclosureLocatorResult(
            metric_id="contract_liab",
            matched_label="Contract liabilities",
            source_text_span="Contract liabilities disclosed above",
            semantic_source="llm_fallback",
            semantic_confidence=0.91,
            fallback_reason="missing_statement_row",
        )
    )

    candidates, missing_status = build_working_capital_note_candidate_facts(
        pages=[
            (
                178,
                """
                Accounts Payable and Other Current Liabilities 2024 2023
                Accounts payable $ 801 $ 786
                Accounts payable and other current liabilities $ 2,080 $ 2,164
                """,
            )
        ],
        document_id="doc:09987",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=service,
    )

    assert len(service.requests) == 1
    assert {candidate["metric_id"] for candidate in candidates} == {"acct_payable"}
    assert missing_status["contract_liab"] == "absent"


def test_build_working_capital_note_candidate_facts_does_not_scan_pages_after_note_block() -> (
    None
):
    candidates, missing_status = build_working_capital_note_candidate_facts(
        pages=[
            (
                178,
                """
                Accounts Payable and Other Current Liabilities 2024 2023
                """,
            ),
            (
                179,
                """
                Accounts payable $ 801 $ 786
                """,
            ),
            (
                180,
                """
                Inventories 2024 2023
                Contract liabilities 999 888
                """,
            ),
        ],
        document_id="doc:09987",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert {candidate["metric_id"] for candidate in candidates} == {"acct_payable"}
    assert {candidate["page_index"] for candidate in candidates} == {179}
    assert missing_status["contract_liab"] == "absent"


def test_note_disclosure_candidates_emit_p4a_source_metadata() -> None:
    candidates, _ = build_debt_note_candidate_facts(
        pages=[
            (
                40,
                """
                Borrowings 2025 2024
                Short-term borrowings 100 90
                """,
            )
        ],
        document_id="doc-note",
        period_id="2025FY",
        market="HK",
        existing_metric_ids=set(),
    )

    assert candidates[0]["extensions"]["source_kind"] == (
        "deterministic_note_disclosure"
    )
    assert candidates[0]["extensions"]["source_policy"] == "supplement_only"


def test_build_cash_health_note_candidate_facts_extracts_restricted_cash_only() -> None:
    candidates, missing_status = note_disclosure_module.build_cash_health_note_candidate_facts(
        pages=[
            (
                12,
                """
                Restricted cash and restricted monetary funds were RMB 123 million
                as of December 31, 2022.
                """,
            )
        ],
        document_id="doc:restricted-cash",
        period_id="2022FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert {candidate["metric_id"] for candidate in candidates} == {"restricted_cash"}
    assert candidates[0]["numeric_value"] == 123.0
    assert candidates[0]["extensions"]["source_kind"] == (
        "deterministic_note_disclosure"
    )
    assert candidates[0]["extensions"]["source_policy"] == "supplement_only"
    assert missing_status == {"restricted_cash": "present"}


def test_build_cash_health_note_candidate_facts_extracts_wrapped_restricted_cash_amount() -> None:
    candidates, missing_status = note_disclosure_module.build_cash_health_note_candidate_facts(
        pages=[
            (
                13,
                """
                Restricted cash and cash equivalents
                RMB 123 million as of December 31, 2022.
                """,
            )
        ],
        document_id="doc:wrapped-restricted-cash",
        period_id="2022FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert {candidate["metric_id"] for candidate in candidates} == {"restricted_cash"}
    assert candidates[0]["numeric_value"] == 123.0
    assert missing_status == {"restricted_cash": "present"}


def test_build_cash_health_note_candidate_facts_does_not_bind_neighboring_row_amount() -> None:
    candidates, missing_status = note_disclosure_module.build_cash_health_note_candidate_facts(
        pages=[
            (
                14,
                """
                Restricted cash and cash equivalents
                Other receivables 123 million as of December 31, 2022.
                """,
            )
        ],
        document_id="doc:neighboring-row",
        period_id="2022FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert candidates == []
    assert missing_status == {"restricted_cash": "not_surfaced"}


def test_build_cash_health_note_candidate_facts_ignores_plain_cash_and_collateral_narrative() -> None:
    candidates, missing_status = note_disclosure_module.build_cash_health_note_candidate_facts(
        pages=[
            (
                18,
                """
                Cash and cash equivalents were RMB 500 million as of December 31, 2022.
                已抵押存款主要用于为银行授信提供担保。
                """,
            )
        ],
        document_id="doc:plain-cash",
        period_id="2022FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert candidates == []
    assert missing_status == {"restricted_cash": "not_surfaced"}


def test_build_cash_health_note_candidate_facts_extracts_explicit_chinese_restricted_cash() -> None:
    candidates, missing_status = note_disclosure_module.build_cash_health_note_candidate_facts(
        pages=[
            (
                19,
                """
                受限货币资金为人民币 88 万元。
                """,
            )
        ],
        document_id="doc:restricted-cash-cn",
        period_id="2022FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert {candidate["metric_id"] for candidate in candidates} == {"restricted_cash"}
    assert candidates[0]["numeric_value"] == 88.0
    assert missing_status == {"restricted_cash": "present"}


def test_build_cash_health_note_candidate_facts_extracts_interest_paid_cash_from_cash_flow_supplement() -> None:
    candidates, missing_status = note_disclosure_module.build_cash_health_note_candidate_facts(
        pages=[
            (
                21,
                """
                Cash flows from operating activities
                Cash paid for interest RMB 42 million
                Finance costs 999
                """,
            )
        ],
        document_id="doc:interest-paid",
        period_id="2022FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert {candidate["metric_id"] for candidate in candidates} == {
        "interest_paid_cash"
    }
    assert candidates[0]["numeric_value"] == 42.0
    assert candidates[0]["statement_type"] == "cash_flow_statement"
    assert candidates[0]["extensions"]["period_scope"] == "duration"
    assert missing_status == {"interest_paid_cash": "present"}


@pytest.mark.parametrize(
    ("raw_row", "expected_label"),
    [
        ("Time deposits RMB 321 million", "Time deposits"),
        ("Term deposits RMB 287 million", "Term deposits"),
        (
            "Long-term bank deposits and notes RMB 145 million",
            "Long-term bank deposits and notes",
        ),
        ("Wealth management products RMB 88 million", "Wealth management products"),
        ("定期存款 人民币 66 百万元", "定期存款"),
        ("结构性存款 人民币 77 百万元", "结构性存款"),
        ("理财产品 人民币 99 百万元", "理财产品"),
    ],
)
def test_build_cash_health_note_candidate_facts_extracts_time_deposits_or_wealth_products_from_bounded_rows(
    raw_row: str,
    expected_label: str,
) -> None:
    candidates, missing_status = note_disclosure_module.build_cash_health_note_candidate_facts(
        pages=[
            (
                22,
                f"""
                Cash and cash equivalents
                {raw_row}
                Narrative deposit strategy with no numeric disclosure
                """,
            )
        ],
        document_id=f"doc:{expected_label}",
        period_id="2022FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert {candidate["metric_id"] for candidate in candidates} == {
        "time_deposits_or_wealth_products"
    }
    assert candidates[0]["metric_label_raw"] == expected_label
    assert candidates[0]["numeric_value"] > 0
    assert missing_status == {"time_deposits_or_wealth_products": "present"}


@pytest.mark.parametrize(
    "page_text",
    [
        """
        Finance costs RMB 42 million
        Interest expense RMB 39 million
        """,
        """
        Short-term investments RMB 120 million
        We continue to maintain a flexible deposit strategy.
        """,
        """
        The group invests excess liquidity in time deposits and wealth products.
        """,
    ],
)
def test_build_cash_health_note_candidate_facts_ignores_non_local_or_narrative_text(
    page_text: str,
) -> None:
    candidates, missing_status = note_disclosure_module.build_cash_health_note_candidate_facts(
        pages=[(23, page_text)],
        document_id="doc:negative-controls",
        period_id="2022FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert candidates == []
    assert missing_status == {"restricted_cash": "not_surfaced"}


def test_build_cash_health_note_candidate_facts_does_not_parse_narrative_date_as_time_deposit_value() -> (
    None
):
    candidates, missing_status = note_disclosure_module.build_cash_health_note_candidate_facts(
        pages=[
            (
                24,
                """
                The group invests excess liquidity in time deposits and wealth products.
                As of 31 December 2022, the portfolio remained diversified.
                """,
            )
        ],
        document_id="doc:narrative-date",
        period_id="2022FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert candidates == []
    assert missing_status == {"restricted_cash": "not_surfaced"}


def test_build_cash_health_note_candidate_facts_does_not_parse_prose_date_as_time_deposit_value() -> (
    None
):
    candidates, missing_status = note_disclosure_module.build_cash_health_note_candidate_facts(
        pages=[
            (
                25,
                """
                The group invests excess liquidity in time deposits and wealth products on 31 December 2022.
                """,
            )
        ],
        document_id="doc:prose-date",
        period_id="2022FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert candidates == []
    assert missing_status == {"restricted_cash": "not_surfaced"}


def test_build_cash_health_note_candidate_facts_does_not_parse_date_after_time_deposit_label() -> (
    None
):
    candidates, missing_status = note_disclosure_module.build_cash_health_note_candidate_facts(
        pages=[
            (
                26,
                """
                Time deposits on 31 December 2022
                """,
            )
        ],
        document_id="doc:date-after-label",
        period_id="2022FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert candidates == []
    assert missing_status == {"restricted_cash": "not_surfaced"}


def test_build_cash_health_note_candidate_facts_does_not_parse_year_only_continuation_as_time_deposit_value() -> (
    None
):
    candidates, missing_status = note_disclosure_module.build_cash_health_note_candidate_facts(
        pages=[
            (
                27,
                """
                Time deposits
                2024 2023
                """,
            )
        ],
        document_id="doc:year-only-continuation",
        period_id="2022FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert candidates == []
    assert missing_status == {"restricted_cash": "not_surfaced"}
