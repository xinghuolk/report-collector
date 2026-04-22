from financial_report_analysis.ingestion import (
    build_working_capital_note_candidate_facts,
)
from financial_report_analysis.semantic_fallback import DisclosureLocatorResult


_PAYABLE_NOTE_PAGE = (
    178,
    """
    Accounts Payable and Other Current Liabilities 2024 2023
    Accounts payable $ 801 $ 786
    Contract liabilities 196 196
    Accounts payable and other current liabilities $ 2,080 $ 2,164
    """,
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
