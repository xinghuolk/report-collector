# Turtle Working Capital P2A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Phase 2A Turtle working-capital extraction for seven balance-sheet fields across CN annual reports, HK statement-row annual reports, and HK note/disclosure annual reports.

**Architecture:** Keep the deterministic table path as the main path: table semantics -> metric registry -> table candidate facts -> canonical resolver. Add a narrow HK note/disclosure supplement path for `09987 2025`, with Ollama used only as a gated semantic locator and never as the direct source of canonical financial facts. Split deterministic statement-row closure from note/disclosure closure so the harder HK supplement path does not destabilize CN/HK standard statement rows.

**Tech Stack:** Python 3.12, pytest, Ruff, pypdf, existing `financial_report_analysis` registry / table semantics / semantic fallback modules, optional local Ollama through the existing semantic fallback client.

---

## Scope Check

The approved spec covers one coherent subsystem: Turtle Phase 2A working-capital extraction. It has two implementation phases inside the same plan:

- Phase A: deterministic CN + HK statement-row support.
- Phase B: HK `09987 2025` note/disclosure supplement support with gated semantic locator.

Debt and deferred tax are explicitly excluded and must not be implemented in this plan.

## Source Precedence Policy

All implementation tasks must preserve this precedence:

1. Primary statement-row candidates win.
2. Deterministic note/disclosure candidates fill missing P2A metric IDs only.
3. Ollama-assisted disclosure locator candidates fill missing P2A metric IDs only after deterministic note parsing fails.

Neither note/disclosure candidates nor Ollama locator candidates may overwrite an existing statement-row candidate for the same `metric_id` in the same document. This plan does not change `ConflictResolver` precedence rules; it prevents lower-priority duplicate candidates from being emitted in the first place.

## File Structure

Modify existing files:

- `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
  - Add seven P2A `MetricMappingDefinition` entries.
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
  - Normalize CN/HK working-capital row labels and suppress negative controls.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py`
  - Add P2A row-label fallback outputs and disclosure-locator request/result models.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/client.py`
  - Extend the protocol with a disclosure locator method.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/ollama_client.py`
  - Add the constrained locator prompt and P2A row-label mappings.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py`
  - Add bounded disclosure locator service method.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/__init__.py`
  - Export new request/result types used by ingestion/tests.
- `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
  - Add page-preserving text extraction and append note/disclosure candidates after table candidates.

Create new files:

- `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
  - Locate and parse note/disclosure working-capital rows into candidate facts.
- `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`
  - Unit-test deterministic note parsing, locator gating, and absent/not-surfaced behavior.

Modify tests:

- `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- `financial-report-analysis/tests/unit/test_table_semantics.py`
- `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- `financial-report-analysis/tests/unit/test_semantic_fallback_models.py`
- `financial-report-analysis/tests/unit/test_semantic_fallback_service.py`
- `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

---

### Task 1: Lock P2A Registry And Normalization Contract With Failing Tests

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- Modify: `financial-report-analysis/tests/unit/test_table_semantics.py`

- [ ] **Step 1: Add registry tests for seven positive P2A mappings**

Append this test to `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`:

```python
import pytest


@pytest.mark.parametrize(
    ("metric_id", "market", "label"),
    [
        ("accounts_receiv", "CN", "应收账款"),
        ("notes_receiv", "CN", "应收票据"),
        ("oth_receiv", "CN", "其他应收款"),
        ("contract_liab", "CN", "合同负债"),
        ("adv_receipts", "CN", "预收款项"),
        ("acct_payable", "CN", "应付账款"),
        ("notes_payable", "CN", "应付票据"),
        ("accounts_receiv", "HK", "accounts receivable"),
        ("notes_receiv", "HK", "notes receivable"),
        ("oth_receiv", "HK", "other receivables"),
        ("contract_liab", "HK", "contract liabilities"),
        ("adv_receipts", "HK", "payments received in advance"),
        ("acct_payable", "HK", "accounts payable"),
        ("notes_payable", "HK", "notes payable"),
    ],
)
def test_metric_mapping_registry_matches_p2a_working_capital_fields(
    metric_id: str,
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label=label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is not None
    assert definition.metric_id == metric_id
    assert definition.statement_type == "balance_sheet"
    assert definition.period_scope == "point_in_time"
    assert definition.value_type == "amount"
    assert definition.unit_expectation == "currency_amount"
```

- [ ] **Step 2: Add registry negative-control tests**

Append this test to `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`:

```python
@pytest.mark.parametrize(
    ("market", "label"),
    [
        ("HK", "accounts receivable financing"),
        ("HK", "long-term receivables"),
        ("HK", "employee compensation payable"),
        ("HK", "taxes payable"),
        ("HK", "bonds payable"),
        ("CN", "应收款项融资"),
        ("CN", "长期应收款"),
        ("CN", "应付职工薪酬"),
        ("CN", "应交税费"),
        ("CN", "应付债券"),
    ],
)
def test_metric_mapping_registry_rejects_p2a_negative_controls(
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label=label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is None
```

- [ ] **Step 3: Add table-semantics normalization tests**

Append this helper and test to `financial-report-analysis/tests/unit/test_table_semantics.py`:

```python
from financial_report_analysis.ingestion import normalize_table_semantics
from financial_report_analysis.models import ParsedCell, ParsedColumn, ParsedRow, ParsedTable


def _balance_sheet_table_with_row(label: str) -> ParsedTable:
    return ParsedTable(
        table_id="table:p2a",
        document_id="doc:p2a",
        page_range=(1, 1),
        table_kind="balance_sheet",
        title_text="Consolidated Balance Sheet",
        statement_scope_guess="consolidated",
        table_unit="million",
        table_currency="USD",
        header_rows=[["", "2025"]],
        period_columns=[
            ParsedColumn(
                column_id="col:1",
                column_index=1,
                header_text="2025",
                period_id="2025FY",
                comparison_axis="current",
                value_time_shape="point_in_time",
                is_current=True,
                is_comparison=False,
            )
        ],
        comparison_columns=[],
        body_rows=[
            ParsedRow(
                row_id="row:1",
                row_index=1,
                label_raw=label,
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="123",
                        numeric_value=123.0,
                        page_index=1,
                    )
                ],
            )
        ],
    )


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("应收账款 七、", "accounts receivables"),
        ("应收票据", "notes receivable"),
        ("其他应收款 十九、", "other receivables"),
        ("合同负债", "contract liabilities"),
        ("预收款项", "advances from customers"),
        ("应付账款", "accounts payable"),
        ("应付票据", "notes payable"),
        ("Accounts receivable, net", "accounts receivable"),
        ("Accounts payable", "accounts payable"),
        ("Contract liabilities", "contract liabilities"),
    ],
)
def test_table_semantics_normalizes_p2a_working_capital_labels(
    label: str,
    expected: str,
) -> None:
    semantics = normalize_table_semantics(_balance_sheet_table_with_row(label))

    assert semantics.rows[0].normalized_row_label == expected
```

- [ ] **Step 4: Add table-semantics negative-control tests**

Append this test to `financial-report-analysis/tests/unit/test_table_semantics.py`:

```python
@pytest.mark.parametrize(
    "label",
    [
        "accounts receivable financing",
        "long-term receivables",
        "employee compensation payable",
        "taxes payable",
        "bonds payable",
        "Changes in accounts receivable",
        "应收款项融资",
        "长期应收款",
        "应付职工薪酬",
        "应交税费",
        "应付债券",
        "经营性应收项目的减少（增加以“－”号填列）",
    ],
)
def test_table_semantics_suppresses_p2a_negative_controls(label: str) -> None:
    semantics = normalize_table_semantics(_balance_sheet_table_with_row(label))

    assert semantics.rows[0].normalized_row_label is None
```

- [ ] **Step 5: Run tests and verify they fail**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py -q -o addopts=
```

Expected: failures for missing P2A registry mappings and missing normalization/negative-control behavior.

---

### Task 2: Implement Deterministic P2A Registry And Row Semantics

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/ollama_client.py`

- [ ] **Step 1: Add P2A metric definitions**

Insert these definitions in `_DEFAULT_DEFINITIONS` after the existing `cash` balance-sheet definition in `metric_mapping.py`:

```python
    MetricMappingDefinition(
        metric_id="accounts_receiv",
        statement_type="balance_sheet",
        allowed_table_kinds=("balance_sheet",),
        normalized_row_labels=("accounts receivable", "accounts receivables"),
        period_scope="point_in_time",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("应收账款",), "HK": ("accounts receivable", "accounts receivable, net")},
    ),
    MetricMappingDefinition(
        metric_id="notes_receiv",
        statement_type="balance_sheet",
        allowed_table_kinds=("balance_sheet",),
        normalized_row_labels=("notes receivable",),
        period_scope="point_in_time",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("应收票据",), "HK": ("notes receivable", "notes receivables")},
    ),
    MetricMappingDefinition(
        metric_id="oth_receiv",
        statement_type="balance_sheet",
        allowed_table_kinds=("balance_sheet",),
        normalized_row_labels=("other receivables", "other receivable"),
        period_scope="point_in_time",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("其他应收款",), "HK": ("other receivables", "other receivable")},
    ),
    MetricMappingDefinition(
        metric_id="contract_liab",
        statement_type="balance_sheet",
        allowed_table_kinds=("balance_sheet",),
        normalized_row_labels=("contract liabilities", "contract liability"),
        period_scope="point_in_time",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("合同负债",), "HK": ("contract liabilities", "contract liability")},
    ),
    MetricMappingDefinition(
        metric_id="adv_receipts",
        statement_type="balance_sheet",
        allowed_table_kinds=("balance_sheet",),
        normalized_row_labels=("advances from customers", "payments received in advance"),
        period_scope="point_in_time",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("预收款项",), "HK": ("payments received in advance", "advances from customers")},
    ),
    MetricMappingDefinition(
        metric_id="acct_payable",
        statement_type="balance_sheet",
        allowed_table_kinds=("balance_sheet",),
        normalized_row_labels=("accounts payable",),
        period_scope="point_in_time",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("应付账款",), "HK": ("accounts payable",)},
    ),
    MetricMappingDefinition(
        metric_id="notes_payable",
        statement_type="balance_sheet",
        allowed_table_kinds=("balance_sheet",),
        normalized_row_labels=("notes payable",),
        period_scope="point_in_time",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("应付票据",), "HK": ("notes payable",)},
    ),
```

- [ ] **Step 2: Add deterministic row aliases**

Add these entries to `_ROW_LABEL_ALIASES` in `table_semantics.py`:

```python
    "应收账款": "accounts receivables",
    "应收票据": "notes receivable",
    "其他应收款": "other receivables",
    "合同负债": "contract liabilities",
    "预收款项": "advances from customers",
    "应付账款": "accounts payable",
    "应付票据": "notes payable",
    "accounts receivable": "accounts receivable",
    "accounts receivable net": "accounts receivable",
    "accounts receivable, net": "accounts receivable",
    "notes receivable": "notes receivable",
    "notes receivables": "notes receivable",
    "other receivable": "other receivables",
    "other receivables": "other receivables",
    "contract liability": "contract liabilities",
    "contract liabilities": "contract liabilities",
    "payments received in advance": "payments received in advance",
    "advances from customers": "advances from customers",
    "accounts payable": "accounts payable",
    "notes payable": "notes payable",
```

- [ ] **Step 3: Strip common CN note-reference suffixes before alias lookup**

In `_normalize_label()` in `table_semantics.py`, after the whitespace normalization line, add:

```python
    normalized = re.sub(r"\s+(七|八|九|十|十一|十二|十三|十四|十五|十六|十七|十八|十九|二十)、?$", "", normalized)
    normalized = re.sub(r"\s+[-–—]$", "", normalized)
    normalized = re.sub(r"\s+\b[ivxlcdm]+\.\d+\b$", "", normalized, flags=re.IGNORECASE)
```

- [ ] **Step 4: Add negative controls to summary suppression**

Add these patterns to `_SUPPRESSED_SUMMARY_PATTERNS` in `table_semantics.py`:

```python
    re.compile(r"\baccounts receivable financing\b", re.IGNORECASE),
    re.compile(r"\blong-term receivables?\b", re.IGNORECASE),
    re.compile(r"\bemployee compensation payable\b", re.IGNORECASE),
    re.compile(r"\btaxes payable\b", re.IGNORECASE),
    re.compile(r"\bbonds payable\b", re.IGNORECASE),
    re.compile(r"\bchanges? in accounts receivable\b", re.IGNORECASE),
    re.compile(r"应收款项融资"),
    re.compile(r"长期应收款"),
    re.compile(r"应付职工薪酬"),
    re.compile(r"应交税费"),
    re.compile(r"应付债券"),
    re.compile(r"经营性应收项目"),
    re.compile(r"经营性应付项目"),
```

- [ ] **Step 5: Extend fallback row-label output set without making it a primary path**

Add the seven P2A labels to `_ROW_LABEL_OUTPUTS` in `semantic_fallback/models.py` before `"none"`:

```python
    "accounts_receiv",
    "notes_receiv",
    "oth_receiv",
    "contract_liab",
    "adv_receipts",
    "acct_payable",
    "notes_payable",
```

In `ollama_client.py`, extend the row-label prompt mapping section with:

```python
            "- accounts receivable, accounts receivable net -> accounts_receiv\n"
            "- notes receivable -> notes_receiv\n"
            "- other receivables -> oth_receiv\n"
            "- contract liabilities, contract liability -> contract_liab\n"
            "- payments received in advance, advances from customers -> adv_receipts\n"
            "- accounts payable -> acct_payable\n"
            "- notes payable -> notes_payable\n"
```

Also extend the negative-control text with:

```python
            "- accounts receivable financing, long-term receivables, employee compensation payable, taxes payable, bonds payable -> none\n"
            "- changes in accounts receivable or cash-flow working-capital adjustment rows -> none\n"
```

- [ ] **Step 6: Run deterministic unit tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py tests/unit/test_semantic_fallback_models.py -q -o addopts=
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 1-2**

Run:

```powershell
git add financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py financial-report-analysis/src/financial_report_analysis/semantic_fallback/ollama_client.py financial-report-analysis/tests/unit/test_metric_mapping_registry.py financial-report-analysis/tests/unit/test_table_semantics.py
git commit -m "feat: add turtle working capital registry semantics"
```

---

### Task 3: Prove P2A Candidate Fact Building And Negative Controls

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Inspect: `financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py`

- [ ] **Step 1: Add a table candidate fact test for the seven fields**

Append this test to `test_fact_pipeline.py`, reusing or adapting existing table helper objects already in that file:

```python
def test_table_fact_builder_emits_p2a_working_capital_candidate_facts() -> None:
    semantics = _normalized_table_semantics(
        table_kind="balance_sheet",
        rows=[
            ("应收账款", "accounts receivables", 11.0),
            ("应收票据", "notes receivable", 12.0),
            ("其他应收款", "other receivables", 13.0),
            ("合同负债", "contract liabilities", 14.0),
            ("预收款项", "advances from customers", 15.0),
            ("应付账款", "accounts payable", 16.0),
            ("应付票据", "notes payable", 17.0),
        ],
        value_time_shape="point_in_time",
        period_id="2025FY",
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
```

If `test_fact_pipeline.py` does not have a helper matching this shape, add a focused helper in the test file:

```python
def _normalized_table_semantics(
    *,
    table_kind: str,
    rows: list[tuple[str, str | None, float]],
    value_time_shape: str,
    period_id: str,
) -> NormalizedTableSemantics:
    return NormalizedTableSemantics(
        table_id="table:p2a",
        document_id="doc:p2a",
        page_range=(1, 1),
        table_kind=table_kind,
        title_text="Balance Sheet",
        statement_scope_guess="consolidated",
        table_unit="million",
        table_currency="CNY",
        columns=[],
        rows=[
            NormalizedTableRow(
                row_id=f"row:{index}",
                label_raw=raw_label,
                normalized_row_label=normalized_label,
                values=[
                    NormalizedTableCellValue(
                        row_index=index,
                        column_index=1,
                        raw_text=str(value),
                        numeric_value=value,
                        period_id=period_id,
                        comparison_axis="current",
                        value_time_shape=value_time_shape,
                    )
                ],
            )
            for index, (raw_label, normalized_label, value) in enumerate(rows, start=1)
        ],
    )
```

- [ ] **Step 2: Add a negative-control candidate test**

Append:

```python
def test_table_fact_builder_rejects_p2a_negative_control_rows() -> None:
    semantics = _normalized_table_semantics(
        table_kind="balance_sheet",
        rows=[
            ("accounts receivable financing", None, 1.0),
            ("long-term receivables", None, 2.0),
            ("employee compensation payable", None, 3.0),
            ("taxes payable", None, 4.0),
            ("bonds payable", None, 5.0),
        ],
        value_time_shape="point_in_time",
        period_id="2025FY",
    )

    candidates = build_table_candidate_facts(
        [semantics],
        registry=load_metric_registry(),
        document_id="doc:p2a",
        market="HK",
    )

    assert candidates == []
```

- [ ] **Step 3: Run tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py -q -o addopts=
```

Expected: pass. Add these imports to `test_fact_pipeline.py` before running if the file does not already import them:

```python
from financial_report_analysis.models import NormalizedTableCellValue, NormalizedTableRow, NormalizedTableSemantics
from financial_report_analysis.registries import load_metric_registry
from financial_report_analysis.services import build_table_candidate_facts
```

- [ ] **Step 4: Commit Task 3**

Run:

```powershell
git add financial-report-analysis/tests/unit/test_fact_pipeline.py financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py
git commit -m "test: cover turtle working capital candidate facts"
```

---

### Task 4: Close Deterministic Real-PDF Anchors For CN 601919 And HK 02498

**Files:**

- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`
- Inspect on failure: `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
- Inspect on failure: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`

- [ ] **Step 1: Add integration helpers for metric assertions**

Append or reuse these helpers in `test_semantic_recovery_regressions.py`:

```python
def _metric_ids_from_candidates(payload: dict[str, object]) -> set[str]:
    return {
        str(candidate["metric_id"])
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict)
    }


def _extract_payload_for_pdf(pdf_path: Path, *, market: str) -> dict[str, object]:
    return PdfIngestionAdapter().extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market=market,
        min_confidence=None,
    )
```

- [ ] **Step 2: Add CN 601919 deterministic real-PDF floor**

Append:

```python
def test_cn_601919_2025_surfaces_p2a_working_capital_candidates() -> None:
    pdf_path = _resolve_sample("cn_stocks", "601919", "annual", "2025_年度报告.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="CN")

    assert {
        "accounts_receiv",
        "notes_receiv",
        "oth_receiv",
        "acct_payable",
        "notes_payable",
    }.issubset(_metric_ids_from_candidates(payload))
```

Keep `contract_liab` and `adv_receipts` out of this CN hard subset unless a pre-test inspection confirms they are independently disclosed in the primary balance sheet. They may still appear in the payload; they are not required by this specific test.

- [ ] **Step 3: Add HK 02498 deterministic statement-row floor**

Append:

```python
def test_hk_02498_2022_surfaces_p2a_statement_row_candidates() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")

    assert {
        "accounts_receiv",
        "notes_receiv",
        "oth_receiv",
        "contract_liab",
        "adv_receipts",
        "acct_payable",
        "notes_payable",
    }.issubset(_metric_ids_from_candidates(payload))
```

- [ ] **Step 4: Add negative-control real-PDF guard**

Append:

```python
def test_hk_02498_2022_does_not_promote_p2a_negative_control_rows() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    labels_by_metric = {
        str(candidate["metric_id"]): str(candidate.get("metric_label_raw", "")).casefold()
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict)
    }

    assert "accounts receivable financing" not in labels_by_metric.get("accounts_receiv", "")
    assert "long-term receivables" not in labels_by_metric.get("oth_receiv", "")
    assert "bonds payable" not in labels_by_metric.get("notes_payable", "")
```

- [ ] **Step 5: Run deterministic real-PDF tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_cn_601919_2025_surfaces_p2a_working_capital_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_surfaces_p2a_statement_row_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_does_not_promote_p2a_negative_control_rows -q -o addopts=
```

Expected: pass after Task 2. If a test fails because column period binding is missing, fix `table_structure.py` so recovered balance-sheet rows keep point-in-time column bindings instead of adding a test workaround.

- [ ] **Step 6: Commit Task 4**

Run:

```powershell
git add financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py
git commit -m "test: cover p2a deterministic real pdf anchors"
```

---

### Task 5: Add Note/Disclosure Candidate Builder For HK 09987

**Files:**

- Create: `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py`
- Create: `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`

- [ ] **Step 1: Write failing deterministic note parser test**

Create `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`:

```python
from financial_report_analysis.ingestion.note_disclosure import (
    build_working_capital_note_candidate_facts,
)


def test_note_disclosure_builder_extracts_09987_accounts_payable_note_rows() -> None:
    pages = [
        (
            178,
            """
            Accounts Payable and Other Current Liabilities 2024 2023
            Accounts payable $ 801 $ 786
            Contract liabilities 196 196
            Accounts payable and other current liabilities $ 2,080 $ 2,164
            """,
        )
    ]

    candidates = build_working_capital_note_candidate_facts(
        pages=pages,
        document_id="doc:09987",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert {
        candidate["metric_id"]
        for candidate in candidates
    } == {"acct_payable", "contract_liab"}
    assert {candidate["numeric_value"] for candidate in candidates} == {801.0, 196.0}
    assert all(candidate["extraction_method"] == "note_disclosure" for candidate in candidates)
    assert all(
        candidate["extensions"]["semantic_source"] == "deterministic"
        for candidate in candidates
    )
```

- [ ] **Step 2: Write absent/not-surfaced guard test**

Append:

```python
def test_note_disclosure_builder_does_not_create_missing_notes_receivable_or_payable() -> None:
    pages = [
        (
            178,
            """
            Accounts Payable and Other Current Liabilities 2024 2023
            Accounts payable $ 801 $ 786
            Contract liabilities 196 196
            """,
        )
    ]

    candidates = build_working_capital_note_candidate_facts(
        pages=pages,
        document_id="doc:09987",
        period_id="2024FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    metric_ids = {candidate["metric_id"] for candidate in candidates}
    assert "notes_receiv" not in metric_ids
    assert "notes_payable" not in metric_ids
```

- [ ] **Step 3: Write missing-status metadata test**

Append:

```python
def test_note_disclosure_builder_reports_absent_missing_status() -> None:
    pages = [
        (
            178,
            """
            Accounts Payable and Other Current Liabilities 2024 2023
            Accounts payable $ 801 $ 786
            Contract liabilities 196 196
            """,
        )
    ]

    candidates, missing_status = build_working_capital_note_candidate_facts(
        pages=pages,
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
    assert missing_status["notes_receiv"] == "absent"
    assert missing_status["notes_payable"] == "absent"
    assert missing_status["adv_receipts"] == "not_surfaced"
```

- [ ] **Step 4: Run tests and verify they fail**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_note_disclosure_ingestion.py -q -o addopts=
```

Expected: import failure because `note_disclosure.py` does not exist yet.

- [ ] **Step 5: Create the note/disclosure builder**

Create `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py` with this initial implementation:

```python
from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any

from financial_report_analysis.semantic_fallback import SemanticFallbackService

_TARGET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("accounts_receiv", re.compile(r"^accounts receivable,?\s+net\s+\$?\s*([0-9][0-9,]*(?:\.\d+)?)", re.IGNORECASE)),
    ("acct_payable", re.compile(r"^accounts payable\s+\$?\s*([0-9][0-9,]*(?:\.\d+)?)", re.IGNORECASE)),
    ("contract_liab", re.compile(r"^contract liabilities\s+\$?\s*([0-9][0-9,]*(?:\.\d+)?)", re.IGNORECASE)),
)


def build_working_capital_note_candidate_facts(
    *,
    pages: Iterable[tuple[int, str]],
    document_id: str,
    period_id: str | None,
    market: str,
    existing_metric_ids: set[str],
    semantic_fallback_service: SemanticFallbackService | None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    del semantic_fallback_service
    if market.upper() != "HK" or period_id is None:
        return ([], {})

    candidates: list[dict[str, Any]] = []
    found_metric_ids = set(existing_metric_ids)
    for page_index, text in pages:
        for line in _iter_candidate_lines(text):
            for metric_id, pattern in _TARGET_PATTERNS:
                if metric_id in found_metric_ids:
                    continue
                match = pattern.search(line)
                if match is None:
                    continue
                candidates.append(
                    _candidate_fact(
                        document_id=document_id,
                        metric_id=metric_id,
                        label=_label_from_line(line),
                        raw_value=match.group(1),
                        period_id=period_id,
                        page_index=page_index,
                        market=market,
                        semantic_source="deterministic",
                        semantic_confidence=None,
                        fallback_reason=None,
                    )
                )
                found_metric_ids.add(metric_id)
    return (candidates, _working_capital_missing_status(found_metric_ids))


def _iter_candidate_lines(text: str) -> Iterable[str]:
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if line:
            yield line


def _label_from_line(line: str) -> str:
    return re.split(r"\s+\$?\s*[0-9]", line, maxsplit=1)[0].strip()


def _working_capital_missing_status(found_metric_ids: set[str]) -> dict[str, str]:
    status: dict[str, str] = {}
    absent_when_missing = {"notes_receiv", "notes_payable"}
    not_surfaced_when_missing = {"adv_receipts"}
    for metric_id in sorted(absent_when_missing | not_surfaced_when_missing):
        if metric_id in found_metric_ids:
            status[metric_id] = "present"
        elif metric_id in absent_when_missing:
            status[metric_id] = "absent"
        else:
            status[metric_id] = "not_surfaced"
    return status


def _candidate_fact(
    *,
    document_id: str,
    metric_id: str,
    label: str,
    raw_value: str,
    period_id: str,
    page_index: int,
    market: str,
    semantic_source: str,
    semantic_confidence: float | None,
    fallback_reason: str | None,
) -> dict[str, Any]:
    numeric_value = float(raw_value.replace(",", ""))
    return {
        "fact_id": f"{document_id}:note-disclosure:{metric_id}",
        "fact_kind": "candidate",
        "metric_id": metric_id,
        "metric_label_raw": label,
        "statement_type": "balance_sheet",
        "entity_scope": "consolidated",
        "comparison_axis": "current",
        "adjustment_basis": "reported",
        "period_id": period_id,
        "currency": "USD",
        "raw_value": raw_value,
        "numeric_value": numeric_value,
        "raw_unit": "million",
        "normalized_unit": None,
        "precision": 0,
        "confidence": 0.82 if semantic_source == "deterministic" else 0.74,
        "extensions": {
            "market": market,
            "accounting_standard": "OTHER",
            "table_kind": "note_disclosure",
            "period_scope": "point_in_time",
            "value_type": "amount",
            "unit_expectation": "currency_amount",
            "sign_rule": "allow_negative",
            "semantic_source": semantic_source,
            "semantic_confidence": semantic_confidence,
            "fallback_reason": fallback_reason,
        },
        "document_id": document_id,
        "block_id": f"{document_id}:note-disclosure:{page_index}:{metric_id}",
        "page_index": page_index,
        "table_id": f"{document_id}:note-disclosure:{page_index}",
        "table_coord": None,
        "evidence_bundle_id": f"{document_id}:bundle:note-disclosure",
        "extraction_method": "note_disclosure",
        "extraction_version": "v1",
        "source_rank_hint": 18,
    }
```

Update the first two tests in this task to unpack the tuple:

```python
candidates, missing_status = build_working_capital_note_candidate_facts(...)
```

Keep using `candidates` for candidate assertions.

- [ ] **Step 6: Export the note builder**

Add this export to `financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py`:

```python
from financial_report_analysis.ingestion.note_disclosure import (
    build_working_capital_note_candidate_facts,
)
```

If the file has an `__all__` tuple, add `"build_working_capital_note_candidate_facts"` to that tuple.

- [ ] **Step 7: Run note-disclosure unit tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_note_disclosure_ingestion.py -q -o addopts=
```

Expected: pass.

- [ ] **Step 8: Commit Task 5**

Run:

```powershell
git add financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py
git commit -m "feat: add hk working capital note disclosure builder"
```

---

### Task 6: Add Gated Ollama Disclosure Locator Contract

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/client.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/ollama_client.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/__init__.py`
- Modify: `financial-report-analysis/tests/unit/test_semantic_fallback_models.py`
- Modify: `financial-report-analysis/tests/unit/test_semantic_fallback_service.py`

- [ ] **Step 1: Add model tests for disclosure locator outputs**

Append to `test_semantic_fallback_models.py`:

```python
from financial_report_analysis.semantic_fallback import (
    DisclosureLocatorRequest,
    DisclosureLocatorResult,
    supported_disclosure_metric_outputs,
)


def test_disclosure_locator_supported_outputs_are_p2a_bounded() -> None:
    assert supported_disclosure_metric_outputs() == (
        "accounts_receiv",
        "notes_receiv",
        "oth_receiv",
        "contract_liab",
        "adv_receipts",
        "acct_payable",
        "notes_payable",
        "none",
    )


def test_disclosure_locator_result_carries_span_and_provenance() -> None:
    result = DisclosureLocatorResult(
        metric_id="acct_payable",
        matched_label="Accounts payable",
        source_text_span="Accounts payable $ 801 $ 786",
        semantic_source="llm_fallback",
        semantic_confidence=0.91,
        fallback_reason="missing_statement_row",
    )

    assert result.metric_id == "acct_payable"
    assert result.source_text_span.startswith("Accounts payable")
```

- [ ] **Step 2: Add service tests with a fake client**

Append to `test_semantic_fallback_service.py`:

```python
class _DisclosureLocatorClient:
    def locate_disclosure_metric(self, request: DisclosureLocatorRequest) -> DisclosureLocatorResult:
        return DisclosureLocatorResult(
            metric_id="acct_payable",
            matched_label="Accounts payable",
            source_text_span="Accounts payable $ 801 $ 786",
            semantic_source="llm_fallback",
            semantic_confidence=0.9,
            fallback_reason=request.ambiguity_reason,
        )


def test_semantic_fallback_service_locates_disclosure_metric_when_gated() -> None:
    service = SemanticFallbackService(client=_DisclosureLocatorClient())

    result = service.locate_disclosure_metric(
        DisclosureLocatorRequest(
            target_metric_ids=("acct_payable", "contract_liab"),
            local_context="Accounts payable $ 801 $ 786",
            deterministic_candidates=(),
            ambiguity_reason="missing_statement_row",
        )
    )

    assert result.metric_id == "acct_payable"
    assert result.semantic_source == "llm_fallback"


def test_semantic_fallback_service_does_not_locate_disclosure_without_gate() -> None:
    service = SemanticFallbackService(client=_DisclosureLocatorClient())

    result = service.locate_disclosure_metric(
        DisclosureLocatorRequest(
            target_metric_ids=("acct_payable",),
            local_context="Accounts payable $ 801 $ 786",
            deterministic_candidates=(),
            ambiguity_reason=None,
        )
    )

    assert result.metric_id == "none"
    assert result.semantic_source == "deterministic"
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_semantic_fallback_models.py tests/unit/test_semantic_fallback_service.py -q -o addopts=
```

Expected: import or attribute failures for the new locator model/service.

- [ ] **Step 4: Add locator models**

In `semantic_fallback/models.py`, add:

```python
_DISCLOSURE_METRIC_OUTPUTS = (
    "accounts_receiv",
    "notes_receiv",
    "oth_receiv",
    "contract_liab",
    "adv_receipts",
    "acct_payable",
    "notes_payable",
    "none",
)


@dataclass(frozen=True, slots=True)
class DisclosureLocatorRequest:
    target_metric_ids: tuple[str, ...]
    local_context: str
    deterministic_candidates: tuple[str, ...]
    ambiguity_reason: str | None


@dataclass(frozen=True, slots=True)
class DisclosureLocatorResult:
    metric_id: str
    matched_label: str
    source_text_span: str
    semantic_source: str
    semantic_confidence: float | None
    fallback_reason: str | None


def supported_disclosure_metric_outputs() -> tuple[str, ...]:
    return _DISCLOSURE_METRIC_OUTPUTS
```

- [ ] **Step 5: Extend client protocol**

In `semantic_fallback/client.py`, import the new types and add this method to `SemanticFallbackClient`:

```python
    def locate_disclosure_metric(
        self,
        request: DisclosureLocatorRequest,
    ) -> DisclosureLocatorResult: ...
```

- [ ] **Step 6: Extend fallback service**

In `semantic_fallback/service.py`, import the new types and add:

```python
    def locate_disclosure_metric(
        self,
        request: DisclosureLocatorRequest,
    ) -> DisclosureLocatorResult:
        if self._client is None or not request.ambiguity_reason:
            return DisclosureLocatorResult(
                metric_id="none",
                matched_label="",
                source_text_span="",
                semantic_source="deterministic",
                semantic_confidence=None,
                fallback_reason=None,
            )
        try:
            with self._semaphore:
                result = self._client.locate_disclosure_metric(request)
        except Exception:
            LOGGER.warning(
                "Disclosure semantic locator failed; continuing without locator result.",
                exc_info=True,
            )
            return DisclosureLocatorResult(
                metric_id="none",
                matched_label="",
                source_text_span="",
                semantic_source="deterministic",
                semantic_confidence=None,
                fallback_reason=None,
            )
        metric_id = _bounded_disclosure_metric(result.metric_id)
        return DisclosureLocatorResult(
            metric_id=metric_id,
            matched_label=result.matched_label if metric_id != "none" else "",
            source_text_span=result.source_text_span if metric_id != "none" else "",
            semantic_source=result.semantic_source,
            semantic_confidence=result.semantic_confidence,
            fallback_reason=result.fallback_reason,
        )
```

Also add:

```python
def _bounded_disclosure_metric(value: str) -> str:
    normalized = value.strip().casefold()
    return normalized if normalized in supported_disclosure_metric_outputs() else "none"
```

- [ ] **Step 7: Implement Ollama locator prompt**

In `semantic_fallback/ollama_client.py`, add imports for the locator types and implement:

```python
    def locate_disclosure_metric(
        self,
        request: DisclosureLocatorRequest,
    ) -> DisclosureLocatorResult:
        prompt = (
            "You are locating working-capital disclosure rows in a financial report. "
            "Choose exactly one metric_id from this set: "
            f"{', '.join(supported_disclosure_metric_outputs())}.\n"
            "Return none if the text does not independently disclose the target metric.\n"
            "Do not infer missing notes receivable or notes payable from aggregate rows.\n"
            "Allowed meanings:\n"
            "- accounts_receiv: accounts receivable or accounts receivable, net\n"
            "- notes_receiv: notes receivable only\n"
            "- oth_receiv: other receivables only\n"
            "- contract_liab: contract liabilities or contract liability\n"
            "- adv_receipts: payments received in advance or advances from customers\n"
            "- acct_payable: accounts payable only\n"
            "- notes_payable: notes payable only\n"
            "Negative controls: accounts payable and other current liabilities aggregate, "
            "bonds payable, taxes payable, employee compensation payable, long-term receivables.\n"
            f"Target metric ids: {', '.join(request.target_metric_ids)}\n"
            f"Context: {request.local_context}\n"
            'Return exactly JSON like {"metric_id":"acct_payable","matched_label":"Accounts payable","source_text_span":"Accounts payable $ 801 $ 786","confidence":0.95}.'
        )
        payload = self._invoke(prompt)
        metric_id = _normalize_choice(
            payload.get("metric_id", payload.get("value", "")),
            allowed=supported_disclosure_metric_outputs(),
            default="none",
        )
        return DisclosureLocatorResult(
            metric_id=metric_id,
            matched_label=str(payload.get("matched_label", "")),
            source_text_span=str(payload.get("source_text_span", "")),
            semantic_source="llm_fallback",
            semantic_confidence=_parse_confidence(payload.get("confidence")),
            fallback_reason=request.ambiguity_reason,
        )
```

- [ ] **Step 8: Export new semantic fallback types**

Update `semantic_fallback/__init__.py` so tests can import:

```python
from financial_report_analysis.semantic_fallback.models import (
    DisclosureLocatorRequest,
    DisclosureLocatorResult,
    supported_disclosure_metric_outputs,
)
```

- [ ] **Step 9: Run fallback tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_semantic_fallback_models.py tests/unit/test_semantic_fallback_service.py -q -o addopts=
```

Expected: pass.

- [ ] **Step 10: Commit Task 6**

Run:

```powershell
git add financial-report-analysis/src/financial_report_analysis/semantic_fallback financial-report-analysis/tests/unit/test_semantic_fallback_models.py financial-report-analysis/tests/unit/test_semantic_fallback_service.py
git commit -m "feat: add working capital disclosure semantic locator"
```

---

### Task 7: Wire Note/Disclosure Candidates Into PdfIngestionAdapter And Close HK 09987

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`
- Modify: `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`

- [ ] **Step 1: Add page-preserving text extraction tests through integration**

Append this integration test:

```python
def test_hk_09987_2025_surfaces_p2a_note_disclosure_candidates_without_hallucination() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    metric_ids = _metric_ids_from_candidates(payload)

    assert {"accounts_receiv", "acct_payable", "contract_liab"}.issubset(metric_ids)
    assert "notes_receiv" not in metric_ids
    assert "notes_payable" not in metric_ids
    missing_status = payload.get("document_metadata", {}).get(
        "working_capital_missing_status",
        {},
    )
    assert missing_status["notes_receiv"] == "absent"
    assert missing_status["notes_payable"] == "absent"
    assert missing_status["adv_receipts"] == "not_surfaced"
```

- [ ] **Step 2: Add provenance assertion for 09987 note path**

Append:

```python
def test_hk_09987_2025_note_disclosure_candidates_keep_note_provenance() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    p2a_candidates = [
        candidate
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict)
        and candidate.get("metric_id") in {"accounts_receiv", "acct_payable", "contract_liab"}
    ]

    assert p2a_candidates
    assert any(
        candidate.get("extraction_method") == "note_disclosure"
        for candidate in p2a_candidates
    )
    assert all(
        candidate.get("extensions", {}).get("semantic_source") in {"deterministic", "llm_fallback"}
        for candidate in p2a_candidates
    )
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_p2a_note_disclosure_candidates_without_hallucination tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_note_disclosure_candidates_keep_note_provenance -q -o addopts=
```

Expected: fail because note/disclosure candidates are not wired into ingestion yet.

- [ ] **Step 4: Add page-preserving text extraction in PdfIngestionAdapter**

In `pdf_ingestion.py`, add:

```python
    def _extract_text_pages(
        self,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
    ) -> list[tuple[int, str]]:
        if pdf_path:
            path = Path(pdf_path)
            if not path.exists():
                raise PdfIngestionInputError("pdf_path does not exist")
            reader = PdfReader(str(path))
            return [
                (page_index + 1, page.extract_text() or "")
                for page_index, page in enumerate(reader.pages)
            ]

        if pdf_url:
            response = httpx.get(pdf_url, timeout=30.0)
            response.raise_for_status()
            reader = PdfReader(BytesIO(response.content))
            return [
                (page_index + 1, page.extract_text() or "")
                for page_index, page in enumerate(reader.pages)
            ]

        return []
```

Then change `_extract_text()` to:

```python
    def _extract_text(self, *, pdf_path: str | None, pdf_url: str | None) -> str:
        return "\n".join(
            page_text for _, page_text in self._extract_text_pages(pdf_path=pdf_path, pdf_url=pdf_url)
        )
```

- [ ] **Step 5: Append note/disclosure candidates after table candidates**

Import the note builder:

```python
from financial_report_analysis.ingestion.note_disclosure import (
    build_working_capital_note_candidate_facts,
)
```

In `extract_candidate_facts()`, call `_extract_text_pages()` once near the start and derive `text` from that page list:

```python
        text_pages = self._extract_text_pages(pdf_path=pdf_path, pdf_url=pdf_url)
        text = "\n".join(page_text for _, page_text in text_pages)
```

Then avoid calling `_extract_text()` separately in this method.

After `candidate_facts = self._prefer_main_income_statement_facts(candidate_facts)`, add:

```python
        existing_metric_ids = {
            str(candidate.get("metric_id"))
            for candidate in candidate_facts
            if candidate.get("metric_id") is not None
        }
        note_candidates, working_capital_missing_status = (
            build_working_capital_note_candidate_facts(
                pages=text_pages,
                document_id=document_id,
                period_id=period_id,
                market=market or "CN",
                existing_metric_ids=existing_metric_ids,
                semantic_fallback_service=self._semantic_fallback_service,
            )
        )
        candidate_facts.extend(note_candidates)
```

Add the status into returned metadata:

```python
                "working_capital_missing_status": working_capital_missing_status,
```

- [ ] **Step 6: Extend note builder with locator-assisted matching**

In `note_disclosure.py`, use `semantic_fallback_service.locate_disclosure_metric()` only when deterministic patterns do not find all possible target rows in an explicit note/disclosure table block. Do not call the locator for ordinary pages that merely contain broad terms such as `accounts receivable` or `contract liabilities`.

Add this module constant and helper:

```python
_MAX_DISCLOSURE_LOCATOR_CALLS_PER_DOCUMENT = 3


def _should_call_locator(
    text: str,
    existing_metric_ids: set[str],
    locator_call_count: int,
) -> bool:
    if locator_call_count >= _MAX_DISCLOSURE_LOCATOR_CALLS_PER_DOCUMENT:
        return False
    if {"accounts_receiv", "acct_payable", "contract_liab"}.issubset(existing_metric_ids):
        return False
    lowered = text.casefold()
    has_explicit_note_title = any(
        title in lowered
        for title in (
            "accounts payable and other current liabilities",
            "accounts receivable, net",
            "accounts receivable 2024 2023",
            "contract liabilities at december 31",
            "contract liabilities 2024 2023",
        )
    )
    has_period_header = re.search(r"\b20\d{2}\s+20\d{2}\b", lowered) is not None
    has_value_row = re.search(
        r"\b(accounts payable|accounts receivable,?\s+net|contract liabilities)\b\s+\$?\s*[0-9]",
        lowered,
    ) is not None
    return has_explicit_note_title and has_period_header and has_value_row
```

Track `locator_call_count` inside `build_working_capital_note_candidate_facts()` and increment only when `semantic_fallback_service.locate_disclosure_metric()` is actually called.

Pass only missing target metric IDs to the locator:

```python
target_metric_ids = tuple(
    metric_id
    for metric_id in ("accounts_receiv", "acct_payable", "contract_liab")
    if metric_id not in found_metric_ids
)
```

Call the locator only if `target_metric_ids` is non-empty:

```python
result = semantic_fallback_service.locate_disclosure_metric(
    DisclosureLocatorRequest(
        target_metric_ids=target_metric_ids,
        local_context=text[:4000],
        deterministic_candidates=(),
        ambiguity_reason="missing_statement_row",
    )
)
```

Use the locator result only if:

```python
result.metric_id != "none"
and result.metric_id in target_metric_ids
and result.metric_id not in found_metric_ids
and result.source_text_span
```

Then parse the numeric value from `result.source_text_span` with the same line parser. If no numeric value can be parsed from the returned span, ignore the locator result.

- [ ] **Step 7: Run 09987 tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_note_disclosure_ingestion.py tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_p2a_note_disclosure_candidates_without_hallucination tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_note_disclosure_candidates_keep_note_provenance -q -o addopts=
```

Expected: pass.

- [ ] **Step 8: Commit Task 7**

Run:

```powershell
git add financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py
git commit -m "feat: wire hk working capital note disclosure ingestion"
```

---

### Task 8: Final P2A Verification And Plan Closeout

**Files:**

- Inspect: `docs/superpowers/plans/2026-04-21-financial-report-analysis-turtle-working-capital-p2a-implementation-plan.md`

- [ ] **Step 1: Run focused unit suite**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py tests/unit/test_fact_pipeline.py tests/unit/test_note_disclosure_ingestion.py tests/unit/test_semantic_fallback_models.py tests/unit/test_semantic_fallback_service.py -q -o addopts=
```

Expected: all selected unit tests pass.

- [ ] **Step 2: Run focused integration suite**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_cn_601919_2025_surfaces_p2a_working_capital_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_surfaces_p2a_statement_row_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_does_not_promote_p2a_negative_control_rows tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_p2a_note_disclosure_candidates_without_hallucination tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_note_disclosure_candidates_keep_note_provenance -q -o addopts=
```

Expected: all focused integration tests pass.

- [ ] **Step 3: Run existing non-regression tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_surfaces_phase1_api_visible_metrics tests/integration/test_semantic_recovery_regressions.py::test_phase1_investor_inputs_survive_mocked_statement_pipeline_without_noise tests/integration/test_semantic_recovery_regressions.py::test_hk_anchor_candidate_facts_do_not_map_growth_margin_ratio_rows -q -o addopts=
```

Expected: all pass.

- [ ] **Step 4: Run Ruff**

Run:

```powershell
cd financial-report-analysis
uv run ruff check src tests
```

Expected: no Ruff errors.

- [ ] **Step 5: Run live Ollama smoke for locator only when the environment is available**

Run this command only when Ollama is healthy on `127.0.0.1:11434` and the local model is available:

```powershell
cd financial-report-analysis
$env:FRA_RUN_OLLAMA_SMOKE='1'
$env:FRA_SEMANTIC_FALLBACK_BASE_URL='http://127.0.0.1:11434'
$env:FRA_SEMANTIC_FALLBACK_MODEL='qwen3.5:9b'
uv run pytest tests/integration/test_semantic_recovery_regressions.py -k "09987 and ollama" -q -o addopts=
```

Expected: pass when a live Ollama locator test exists; otherwise pytest should report no selected tests. Do not make live Ollama a default closure requirement.

- [ ] **Step 6: Commit final closeout edits**

Run this command if Task 8 changed docs or tests:

```powershell
git add docs/superpowers/plans/2026-04-21-financial-report-analysis-turtle-working-capital-p2a-implementation-plan.md financial-report-analysis/tests
git commit -m "test: close turtle working capital p2a verification"
```

---

## Completion Criteria

P2A is complete only when:

- All seven working-capital metric IDs exist in the metric registry with point-in-time balance-sheet semantics.
- CN `601919 2025` produces deterministic working-capital candidate facts from standard balance-sheet rows.
- HK `02498 2022` produces deterministic working-capital candidate facts from statement rows.
- HK `09987 2025` produces only independently disclosed note/disclosure facts such as `accounts_receiv`, `acct_payable`, and `contract_liab`.
- `09987 2025` does not hallucinate `notes_receiv` or `notes_payable` when they are not independently disclosed.
- Ollama locator output is bounded, gated, provenance-carrying, and never directly becomes canonical facts.
- Existing Phase 1 Turtle investor inputs and prior high-value metrics continue to pass.
