# Real PDF Ollama Fallback Gating Performance Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make real-PDF validation practical again by measuring and tightening row-label Ollama fallback so it remains a bounded ambiguity resolver instead of a broad row classifier.

**Architecture:** Keep deterministic extraction first and preserve the existing candidate/canonical/API contract. Add lightweight fallback call accounting for diagnostics, tighten row-label fallback eligibility before any Ollama call, and use a per-document safety budget only as a defensive cap. This is a Phase 1 closure blocker for Turtle Core Investor Inputs, not a Phase 2 field-expansion task.

**Tech Stack:** Python 3.12, dataclasses, pytest, Ruff, existing `financial_report_analysis` ingestion and semantic fallback stack, local Ollama HTTP API (`http://127.0.0.1:11434`, `qwen3.5:9b`), `scripts/run-real-pdf-matrix.sh`.

## Closure Note

Completed on `2026-04-21`.

- HK `09987/quarterly/2025_quarterly_q3_en.pdf` row-label fallback calls: `124` before -> `11` after.
- HK probe after fix: `{'table_kind': 3, 'row_label': 11, 'currency': 0, 'unit': 0}`, `budget_exhausted=False`, `candidate_facts=4`, `parsed_tables=3`.
- CN `601919/annual/2024_年度报告.pdf` status: completed serial probe within the 600s timeout; output `{'table_kind': 22, 'row_label': 2, 'currency': 0, 'unit': 0}`, `budget_exhausted=False`, `candidate_facts=8`, `parsed_tables=22`.
- Real-PDF Ollama opt-in node: `uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_q3_real_pdf_keeps_row_label_fallback_bounded -v -s` passed in `22.64s`.
- Default real-PDF matrix: `PER_TEST_TIMEOUT_SECONDS=600 scripts/run-real-pdf-matrix.sh -s` passed `43` nodes with marker `real_pdf and not ollama and not external`.
- Matrix collection guard: default `scripts/run-real-pdf-matrix.sh --list` excludes the Ollama node; `REAL_PDF_MARK_EXPR='real_pdf and ollama' scripts/run-real-pdf-matrix.sh --list` lists only `test_hk_09987_q3_real_pdf_keeps_row_label_fallback_bounded`.
- Remaining risks: fallback anchor `sales` remains intentionally broad for `Business sales` / `Net sales`; add specific blocklist cases if real filings expose non-revenue sales labels beyond `cost of sales` / `cost of revenue`.

---

## Related Context

- Assessment: `docs/superpowers/specs/2026-04-21-real-pdf-ollama-fallback-performance-assessment.md`
- Blocking plan: `docs/superpowers/plans/2026-04-21-financial-report-analysis-turtle-core-investor-inputs-implementation-plan.md`
- Current issue:
  - HK `09987/quarterly/2025_quarterly_q3_en.pdf` produced `row_label: 124` fallback calls for only `13` candidate facts and `3` parsed tables.
  - CN `601919/annual/2024_年度报告.pdf` did not finish a counting probe after about six minutes.
- Working hypothesis:
  - `_row_label_ambiguity_reason()` currently lets too many unsupported or clearly non-target rows reach `resolve_row_label()`.

## Scope

### In Scope

- Add test-only or runtime-light fallback call counters.
- Add row-label fallback eligibility prefilters before calling Ollama.
- Add a per-document row-label fallback budget as a safety valve.
- Re-run representative real-PDF probes and then the real-PDF matrix.

### Execution Constraint

- Do not run real-PDF or Ollama-backed tests in parallel.
- Do not dispatch multiple implementation agents for tasks that run real Ollama calls.
- Run real-PDF/Ollama verification one pytest node or one matrix command at a time.
- Unit and mocked integration tests may run normally; only live Ollama and real-PDF validation need strict serialization.

### Out Of Scope

- Removing Ollama fallback.
- Adding new Turtle Phase 2 working-capital or debt metrics.
- Letting LLM output create facts directly.
- Letting LLM canonical resolution replace deterministic registry matching.
- Expanding fallback output space beyond the currently supported row labels.

## File Map

- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
  - Owns the actual gating before `SemanticFallbackService.resolve_row_label()`.
  - Owns per-document row-label fallback budget tracking.
  - Owns diagnostic fallback call counts in `document_metadata`.
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`
  - Add mocked ingestion tests proving unsupported rows do not call row-label fallback.
  - Add budget tests proving the cap prevents runaway calls.
  - Keep a positive test proving plausible core anchors still can call fallback.
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`
  - Add real-PDF or mocked regression around fallback call count metadata.
- Read: `financial-report-analysis/scripts/run-real-pdf-matrix.sh`
  - Use the existing sequential real-PDF matrix runner and per-test timing output.
- Optional Modify: `docs/superpowers/plans/2026-04-21-financial-report-analysis-turtle-core-investor-inputs-implementation-plan.md`
  - Add a one-line cross-reference only after this plan is implemented.

---

## Task 1: Add Fallback Call Accounting

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`

### Goal

Expose per-document fallback call counts without changing candidate fact semantics.

### Steps

- [ ] **Step 1: Write a failing accounting test**

Add this test near the existing fallback tests in `financial-report-analysis/tests/integration/test_analysis_api.py`.

```python
def test_pdf_ingestion_reports_semantic_fallback_call_counts(monkeypatch) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import PdfTableStructureAdapter
    from financial_report_analysis.models import ParsedCell, ParsedColumn, ParsedRow, ParsedTable
    from financial_report_analysis.semantic_fallback import (
        RowLabelFallbackRequest,
        SemanticFallbackResult,
        SemanticFallbackService,
    )

    table = ParsedTable(
        table_id="doc:parsed-table:fallback-counts",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        statement_scope_guess="consolidated",
        semantic_ambiguity_reason=None,
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Business revenue",
                normalized_label_hint="business revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=1,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(PdfTableStructureAdapter, "extract_tables", lambda self, **kwargs: [table])
    monkeypatch.setattr(PdfIngestionAdapter, "_extract_text", lambda self, **kwargs: "")

    class _CountingFallbackService(SemanticFallbackService):
        def __init__(self) -> None:
            super().__init__(client=None)
            self.row_label_requests: list[RowLabelFallbackRequest] = []

        def resolve_row_label(self, request: RowLabelFallbackRequest) -> SemanticFallbackResult:
            self.row_label_requests.append(request)
            return SemanticFallbackResult(
                value="revenue",
                semantic_source="llm_fallback",
                semantic_confidence=0.82,
                fallback_reason=request.ambiguity_reason,
            )

    fallback_service = _CountingFallbackService()

    payload = PdfIngestionAdapter(
        semantic_fallback_service=fallback_service,
    ).extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    assert len(fallback_service.row_label_requests) == 1
    assert payload["document_metadata"]["semantic_fallback_call_counts"] == {
        "table_kind": 1,
        "row_label": 1,
        "currency": 0,
        "unit": 0,
    }
```

- [ ] **Step 2: Run the failing accounting test**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_analysis_api.py::test_pdf_ingestion_reports_semantic_fallback_call_counts -v
```

Expected: FAIL because `semantic_fallback_call_counts` is not present in `document_metadata`.

- [ ] **Step 3: Add call counter state to `PdfIngestionAdapter`**

In `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`, add an instance attribute in `PdfIngestionAdapter.__init__`:

```python
self._semantic_fallback_call_counts: dict[str, int] = {
    "table_kind": 0,
    "row_label": 0,
    "currency": 0,
    "unit": 0,
}
```

At the beginning of `extract_candidate_facts()`, reset the counters so one adapter instance can process multiple PDFs safely:

```python
self._semantic_fallback_call_counts = {
    "table_kind": 0,
    "row_label": 0,
    "currency": 0,
    "unit": 0,
}
```

- [ ] **Step 4: Increment counters only around service calls**

In `_apply_semantic_fallback()`, before `resolve_table_kind(...)`:

```python
self._semantic_fallback_call_counts["table_kind"] += 1
```

In `_apply_local_semantic_fallback()`, before `resolve_currency(...)` and `resolve_unit(...)`:

```python
self._semantic_fallback_call_counts["currency"] += 1
self._semantic_fallback_call_counts["unit"] += 1
```

In `_apply_row_label_fallback()`, increment only after eligibility and budget checks pass, immediately before `resolve_row_label(...)`:

```python
self._semantic_fallback_call_counts["row_label"] += 1
```

- [ ] **Step 5: Expose counts in document metadata**

Where `document_metadata` is assembled in `extract_candidate_facts()`, include:

```python
"semantic_fallback_call_counts": dict(self._semantic_fallback_call_counts),
```

If no semantic fallback service is configured, this should still be present with all counters at `0`.

- [ ] **Step 6: Run the accounting test**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_analysis_api.py::test_pdf_ingestion_reports_semantic_fallback_call_counts -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py \
        financial-report-analysis/tests/integration/test_analysis_api.py
git commit -m "test: expose semantic fallback call counts"
```

---

## Task 2: Add Row-Label Fallback Eligibility Prefilter

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`

### Goal

Prevent clearly unsupported or non-target rows from calling row-label fallback at all.

### Steps

- [ ] **Step 1: Write a failing negative-gating test**

Add this test near `test_pdf_ingestion_applies_row_label_fallback_for_unmapped_normalized_label`.

```python
def test_pdf_ingestion_skips_row_label_fallback_for_clear_non_target_rows(monkeypatch) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import PdfTableStructureAdapter
    from financial_report_analysis.models import ParsedCell, ParsedColumn, ParsedRow, ParsedTable
    from financial_report_analysis.semantic_fallback import (
        RowLabelFallbackRequest,
        SemanticFallbackResult,
        SemanticFallbackService,
    )

    labels = [
        "Revenue growth",
        "Gross margin",
        "Current ratio",
        "Basic earnings per share",
        "Number of restaurants",
        "Segment revenue - Mainland China",
        "Deferred revenue",
        "Contract liabilities",
    ]
    table = ParsedTable(
        table_id="doc:parsed-table:non-target",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        statement_scope_guess="consolidated",
        semantic_ambiguity_reason=None,
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id=f"row-{index}",
                row_index=index,
                label_raw=label,
                normalized_label_hint=label,
                value_cells=[
                    ParsedCell(
                        row_index=index,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=1,
                    )
                ],
            )
            for index, label in enumerate(labels, start=1)
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(PdfTableStructureAdapter, "extract_tables", lambda self, **kwargs: [table])
    monkeypatch.setattr(PdfIngestionAdapter, "_extract_text", lambda self, **kwargs: "")

    class _FailingFallbackService(SemanticFallbackService):
        def __init__(self) -> None:
            super().__init__(client=None)
            self.requests: list[RowLabelFallbackRequest] = []

        def resolve_row_label(self, request: RowLabelFallbackRequest) -> SemanticFallbackResult:
            self.requests.append(request)
            return SemanticFallbackResult(
                value="revenue",
                semantic_source="llm_fallback",
                semantic_confidence=0.82,
                fallback_reason=request.ambiguity_reason,
            )

    fallback_service = _FailingFallbackService()

    payload = PdfIngestionAdapter(
        semantic_fallback_service=fallback_service,
    ).extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    assert fallback_service.requests == []
    assert payload["document_metadata"]["semantic_fallback_call_counts"]["row_label"] == 0
    assert payload["candidate_facts"] == []
```

- [ ] **Step 2: Run the failing negative-gating test**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_analysis_api.py::test_pdf_ingestion_skips_row_label_fallback_for_clear_non_target_rows -v
```

Expected: FAIL because some unsupported rows currently reach `resolve_row_label()`.

- [ ] **Step 3: Write a positive-gating test**

Keep the existing `test_pdf_ingestion_applies_row_label_fallback_for_unmapped_normalized_label` passing, and add this focused positive test if the existing one becomes too broad:

```python
def test_pdf_ingestion_allows_row_label_fallback_for_plausible_core_anchor(monkeypatch) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import PdfTableStructureAdapter
    from financial_report_analysis.models import ParsedCell, ParsedColumn, ParsedRow, ParsedTable
    from financial_report_analysis.semantic_fallback import (
        RowLabelFallbackRequest,
        SemanticFallbackResult,
        SemanticFallbackService,
    )

    table = ParsedTable(
        table_id="doc:parsed-table:core-anchor",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        statement_scope_guess="consolidated",
        semantic_ambiguity_reason=None,
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Business revenue",
                normalized_label_hint="Business revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=1,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(PdfTableStructureAdapter, "extract_tables", lambda self, **kwargs: [table])
    monkeypatch.setattr(PdfIngestionAdapter, "_extract_text", lambda self, **kwargs: "")

    class _FallbackService(SemanticFallbackService):
        def __init__(self) -> None:
            super().__init__(client=None)
            self.requests: list[RowLabelFallbackRequest] = []

        def resolve_row_label(self, request: RowLabelFallbackRequest) -> SemanticFallbackResult:
            self.requests.append(request)
            return SemanticFallbackResult(
                value="revenue",
                semantic_source="llm_fallback",
                semantic_confidence=0.82,
                fallback_reason=request.ambiguity_reason,
            )

    fallback_service = _FallbackService()

    payload = PdfIngestionAdapter(
        semantic_fallback_service=fallback_service,
    ).extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    assert len(fallback_service.requests) == 1
    assert fallback_service.requests[0].ambiguity_reason == "unmapped_normalized_row_label"
    assert payload["candidate_facts"][0]["metric_id"] == "revenue"
```

- [ ] **Step 4: Add row-label eligibility helpers**

In `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`, add these helpers near `_row_label_ambiguity_reason()`:

```python
_ROW_LABEL_FALLBACK_BLOCKLIST_TOKENS = (
    "growth",
    "increase",
    "decrease",
    "margin",
    "ratio",
    "rate",
    "per share",
    "earnings per share",
    "eps",
    "restaurant",
    "restaurants",
    "store",
    "stores",
    "outlet",
    "outlets",
    "segment",
    "mainland china",
    "hong kong",
    "deferred revenue",
    "contract liability",
    "contract liabilities",
)

_ROW_LABEL_FALLBACK_ANCHOR_TOKENS = (
    "revenue",
    "turnover",
    "sales",
    "operating income",
    "operating profit",
    "profit from operations",
    "net profit",
    "profit attributable",
    "operating cash flow",
    "cash generated from operations",
    "cash and cash equivalents",
    "cash equivalents",
    "total assets",
    "assets total",
    "total liabilities",
    "liabilities total",
)

@staticmethod
def _is_row_label_fallback_eligible(raw_label: str, normalized_label: str | None) -> bool:
    text = " ".join(part for part in [raw_label, normalized_label] if part).casefold()
    if not text.strip():
        return False
    if any(token in text for token in PdfIngestionAdapter._ROW_LABEL_FALLBACK_BLOCKLIST_TOKENS):
        return False
    return any(token in text for token in PdfIngestionAdapter._ROW_LABEL_FALLBACK_ANCHOR_TOKENS)
```

If Chinese labels need anchor support during implementation, add only known target anchors already present in registry mappings:

```python
"营业收入",
"经营活动产生的现金流量净额",
"现金及现金等价物",
"资产总计",
"负债合计",
"利润总额",
"净利润",
```

Do not add broad Chinese words like `"收入"` alone because they can match segment and note rows too aggressively.

- [ ] **Step 5: Gate `_row_label_ambiguity_reason()` before returning an ambiguity reason**

Update `_row_label_ambiguity_reason()` so it returns `None` before fallback when the row is not eligible:

```python
if not PdfIngestionAdapter._is_row_label_fallback_eligible(
    row.label_raw,
    row.normalized_row_label,
):
    return None
```

Place this after `_is_summary_growth_or_ratio_row(...)` and before the `row.normalized_row_label is None` branch.

- [ ] **Step 6: Run the gating tests**

Run:

```bash
cd financial-report-analysis
uv run pytest \
  tests/integration/test_analysis_api.py::test_pdf_ingestion_skips_row_label_fallback_for_clear_non_target_rows \
  tests/integration/test_analysis_api.py::test_pdf_ingestion_allows_row_label_fallback_for_plausible_core_anchor \
  tests/integration/test_analysis_api.py::test_pdf_ingestion_applies_row_label_fallback_for_unmapped_normalized_label \
  -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py \
        financial-report-analysis/tests/integration/test_analysis_api.py
git commit -m "fix: gate row-label fallback to plausible core anchors"
```

---

## Task 3: Add Per-Document Row-Label Fallback Budget

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`

### Goal

Add a defensive cap so a malformed or unexpected PDF cannot trigger unbounded row-label fallback calls.

### Steps

- [ ] **Step 1: Write a failing budget test**

Add this test in `financial-report-analysis/tests/integration/test_analysis_api.py`.

```python
def test_pdf_ingestion_caps_row_label_fallback_calls_per_document(monkeypatch) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import PdfTableStructureAdapter
    from financial_report_analysis.models import ParsedCell, ParsedColumn, ParsedRow, ParsedTable
    from financial_report_analysis.semantic_fallback import (
        RowLabelFallbackRequest,
        SemanticFallbackResult,
        SemanticFallbackService,
    )

    rows = [
        ParsedRow(
            row_id=f"row-{index}",
            row_index=index,
            label_raw=f"Business revenue variant {index}",
            normalized_label_hint=f"Business revenue variant {index}",
            value_cells=[
                ParsedCell(
                    row_index=index,
                    column_index=1,
                    text_raw="1,234",
                    numeric_value=1234.0,
                    page_index=1,
                )
            ],
        )
        for index in range(1, 8)
    ]
    table = ParsedTable(
        table_id="doc:parsed-table:budget",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        statement_scope_guess="consolidated",
        semantic_ambiguity_reason=None,
        header_rows=[["Item", "2024"]],
        body_rows=rows,
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(PdfTableStructureAdapter, "extract_tables", lambda self, **kwargs: [table])
    monkeypatch.setattr(PdfIngestionAdapter, "_extract_text", lambda self, **kwargs: "")
    monkeypatch.setattr(PdfIngestionAdapter, "_max_row_label_fallback_calls_per_document", 3)

    class _FallbackService(SemanticFallbackService):
        def __init__(self) -> None:
            super().__init__(client=None)
            self.requests: list[RowLabelFallbackRequest] = []

        def resolve_row_label(self, request: RowLabelFallbackRequest) -> SemanticFallbackResult:
            self.requests.append(request)
            return SemanticFallbackResult(
                value="revenue",
                semantic_source="llm_fallback",
                semantic_confidence=0.82,
                fallback_reason=request.ambiguity_reason,
            )

    fallback_service = _FallbackService()

    payload = PdfIngestionAdapter(
        semantic_fallback_service=fallback_service,
    ).extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    assert len(fallback_service.requests) == 3
    assert payload["document_metadata"]["semantic_fallback_call_counts"]["row_label"] == 3
    assert payload["document_metadata"]["semantic_fallback_budget_exhausted"] is True
```

- [ ] **Step 2: Run the failing budget test**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_analysis_api.py::test_pdf_ingestion_caps_row_label_fallback_calls_per_document -v
```

Expected: FAIL because no row-label fallback budget exists.

- [ ] **Step 3: Add budget defaults and state**

In `PdfIngestionAdapter`, add a class attribute:

```python
_max_row_label_fallback_calls_per_document = 20
```

In `__init__`, add:

```python
self._semantic_fallback_budget_exhausted = False
```

Reset it at the beginning of `extract_candidate_facts()`:

```python
self._semantic_fallback_budget_exhausted = False
```

- [ ] **Step 4: Add a budget helper**

Add this helper near `_apply_row_label_fallback()`:

```python
def _has_row_label_fallback_budget(self) -> bool:
    if (
        self._semantic_fallback_call_counts["row_label"]
        < self._max_row_label_fallback_calls_per_document
    ):
        return True
    self._semantic_fallback_budget_exhausted = True
    return False
```

- [ ] **Step 5: Apply the budget before calling `resolve_row_label()`**

In `_apply_row_label_fallback()`, after `ambiguity_reason` is computed and before constructing `RowLabelFallbackRequest`, add:

```python
if ambiguity_reason is None:
    return row
if not self._has_row_label_fallback_budget():
    return row
```

If the current code does not yet return early when `ambiguity_reason is None`, add that return. Calling `SemanticFallbackService.resolve_row_label()` with no ambiguity reason still avoids the client, but it is still noise for instrumentation and should not happen.

- [ ] **Step 6: Expose budget status in metadata**

Where `document_metadata` is assembled, include:

```python
"semantic_fallback_budget_exhausted": self._semantic_fallback_budget_exhausted,
```

- [ ] **Step 7: Run the budget test**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_analysis_api.py::test_pdf_ingestion_caps_row_label_fallback_calls_per_document -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py \
        financial-report-analysis/tests/integration/test_analysis_api.py
git commit -m "fix: cap row-label fallback calls per document"
```

---

## Task 4: Measure Representative Real PDFs

**Files:**
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`
- Read: `financial-report-analysis/scripts/run-real-pdf-matrix.sh`

### Goal

Confirm the fix improves the known problem samples before running the full matrix.

### Execution Constraint

Run every command in this task serially. Do not use parallel shell execution, parallel pytest workers, or multiple subagents for this task because local Ollama can become overloaded by concurrent requests.

### Steps

- [ ] **Step 1: Add a gated real-PDF call-count regression for HK 09987 Q3**

Add this test to `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`.

```python
@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_09987_q3_real_pdf_keeps_row_label_fallback_bounded() -> None:
    pdf_path = _resolve_sample(
        "hk_stocks",
        "09987",
        "quarterly",
        "2025_quarterly_q3_en.pdf",
    )

    ingestion_payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    counts = ingestion_payload["document_metadata"]["semantic_fallback_call_counts"]
    assert counts["row_label"] <= 20
    assert ingestion_payload["document_metadata"]["semantic_fallback_budget_exhausted"] is False
    assert len(ingestion_payload["candidate_facts"]) >= 1
```

This threshold intentionally mirrors the budget. If this test only passes because the budget is exhausted, the gating is still too broad.

- [ ] **Step 2: Run the HK 09987 Q3 regression**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_q3_real_pdf_keeps_row_label_fallback_bounded -v
```

Expected: PASS with `row_label <= 20` and `semantic_fallback_budget_exhausted is False`.

- [ ] **Step 3: Run deterministic baseline manually for the two known samples**

Run with fallback disabled:

```bash
cd financial-report-analysis
FRA_SEMANTIC_FALLBACK_PROVIDER=disabled uv run pytest \
  tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_q3_real_pdf_keeps_row_label_fallback_bounded \
  -v
```

Expected: The test may FAIL if it asserts fallback metadata from the enabled path, but the command should return quickly enough to separate parsing time from fallback time. Record elapsed time in the final closure note.

For CN 601919 2024, run the narrowest existing real-PDF test that exercises the sample. If no exact node exists, run the matrix with a keyword filter:

```bash
cd financial-report-analysis
PER_TEST_TIMEOUT_SECONDS=600 REAL_PDF_MARK_EXPR=real_pdf scripts/run-real-pdf-matrix.sh -k '601919 and 2024' -s
```

Expected: The selected node completes within the timeout. If no node is selected, add a dedicated real-PDF call-count test for `601919/annual/2024_年度报告.pdf` using the same shape as the HK test.

- [ ] **Step 4: Run the known HK sample with real fallback enabled**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_q3_real_pdf_keeps_row_label_fallback_bounded -v -s
```

Expected: PASS and not near the prior `row_label: 124` count.

- [ ] **Step 5: Commit Task 4**

```bash
git add financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py
git commit -m "test: bound real-pdf row-label fallback calls"
```

---

## Task 5: Run Full Verification And Record Closure

**Files:**
- Modify: `docs/superpowers/plans/2026-04-21-real-pdf-ollama-fallback-gating-performance-fix-implementation-plan.md`
- Optional Modify: `docs/superpowers/plans/2026-04-21-financial-report-analysis-turtle-core-investor-inputs-implementation-plan.md`

### Goal

Prove the fix is ready to unblock Turtle Phase 1 real-PDF validation.

### Execution Constraint

Run all real-PDF and Ollama-backed commands in this task serially. The full matrix script already runs collected nodes sequentially; do not wrap it in any parallel runner.

### Steps

- [ ] **Step 1: Run focused fallback and ingestion tests**

Run:

```bash
cd financial-report-analysis
uv run pytest \
  tests/unit/test_semantic_fallback_service.py \
  tests/integration/test_analysis_api.py::test_pdf_ingestion_reports_semantic_fallback_call_counts \
  tests/integration/test_analysis_api.py::test_pdf_ingestion_skips_row_label_fallback_for_clear_non_target_rows \
  tests/integration/test_analysis_api.py::test_pdf_ingestion_allows_row_label_fallback_for_plausible_core_anchor \
  tests/integration/test_analysis_api.py::test_pdf_ingestion_caps_row_label_fallback_calls_per_document \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run Turtle Phase 1 focused regression tests**

Run:

```bash
cd financial-report-analysis
uv run pytest \
  tests/unit/test_metric_registry.py \
  tests/unit/test_table_semantics.py \
  tests/unit/test_fact_pipeline.py \
  tests/integration/test_analysis_api.py -k 'phase1_api_visible_metrics or row_label_fallback or fallback_call_counts' \
  -v
```

Expected: PASS.

- [ ] **Step 3: Run Ruff**

Run:

```bash
cd financial-report-analysis
uv run ruff check src tests
```

Expected: PASS.

- [ ] **Step 4: Run the real-PDF matrix with timeout**

Run:

```bash
cd financial-report-analysis
PER_TEST_TIMEOUT_SECONDS=600 scripts/run-real-pdf-matrix.sh -s
```

Expected:

- The matrix does not stall on HK `09987` Q3.
- The matrix does not stall on CN `601919` 2024 annual.
- Any remaining failure is a real assertion failure or sample-specific extraction issue, not runaway row-label fallback.

- [ ] **Step 5: Add closure note to this plan**

At the top of this file, under the header, add a `## Closure Note` section with concrete measured values. The section must include:

- completion date;
- HK `09987/quarterly/2025_quarterly_q3_en.pdf` row-label fallback calls before and after the fix;
- CN `601919/annual/2024_年度报告.pdf` elapsed time and result;
- exact real-PDF matrix command and result;
- remaining risks, or the sentence `No known remaining risks from fallback call volume.`

Do not add the closure note until those values are known from actual runs.

- [ ] **Step 6: Optionally cross-reference this blocker from Turtle Core plan**

Only after the fix is verified, add this bullet under the Turtle Core plan's progress/closure note:

```markdown
- Real-PDF Ollama fallback performance blocker resolved by `docs/superpowers/plans/2026-04-21-real-pdf-ollama-fallback-gating-performance-fix-implementation-plan.md`; row-label fallback is now bounded and measured before Phase 1 real-PDF matrix validation.
```

- [ ] **Step 7: Final commit**

```bash
git add docs/superpowers/plans/2026-04-21-real-pdf-ollama-fallback-gating-performance-fix-implementation-plan.md \
        docs/superpowers/plans/2026-04-21-financial-report-analysis-turtle-core-investor-inputs-implementation-plan.md
git commit -m "docs: close real-pdf fallback performance blocker"
```

If the Turtle Core plan was not modified, omit that file from `git add`.

---

## Completion Definition

This plan is complete when all of the following are true:

- `document_metadata.semantic_fallback_call_counts` reports `table_kind`, `row_label`, `currency`, and `unit`.
- Clear non-target rows do not call row-label fallback.
- Plausible core financial anchors can still call row-label fallback when deterministic mapping is ambiguous.
- Row-label fallback is capped per document.
- HK `09987` Q3 no longer triggers near-124 row-label fallback calls.
- CN `601919` 2024 annual completes within a practical timeout.
- Focused tests, Ruff, and the real-PDF matrix have been run or any remaining failures are explicitly documented with root cause.
