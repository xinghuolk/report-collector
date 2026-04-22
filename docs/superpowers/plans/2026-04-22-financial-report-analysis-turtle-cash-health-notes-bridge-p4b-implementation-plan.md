# P4B Turtle Cash-Health Notes Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a narrow cash-health bridge for `restricted_cash`, `interest_paid_cash`, and `time_deposits_or_wealth_products`, using bounded note/disclosure and supplemental cash-flow extraction without widening Phase 4 into broad parent-scope or narrative-policy work.

**Architecture:** Preserve the existing P4A precedence contract: `statement_row > deterministic_note_disclosure > llm_locator_assisted_note_disclosure`. Prefer deterministic note/disclosure parsing and cash-flow supplement parsing first, and only add a bounded semantic locator extension if deterministic parsing cannot stably classify a local disclosure row inside the anchored report families.

**Tech Stack:** Python 3.12, pytest, Ruff, pypdf, existing `financial_report_analysis` registry / note-disclosure / pdf-ingestion / semantic-fallback modules.

---

## Scope Check

This plan covers one narrow subsystem: P4B cash-health note bridging for three metrics only:

- `restricted_cash`
- `interest_paid_cash`
- `time_deposits_or_wealth_products`

It does **not** cover:

- broad parent-company statement coverage
- dividend policy / buyback policy parsing
- broad notes bridge platform work
- new storage surfaces
- CN positive-anchor promise in the first implementation

## Source Precedence Policy

All tasks in this plan must preserve the following precedence:

1. `statement_row`
2. `deterministic_note_disclosure`
3. `llm_locator_assisted_note_disclosure`

Lower-priority sources may fill missing P4B metric IDs only. They must not overwrite an existing higher-priority fact for the same metric and period.

## Onboarding / Missing-Status Requirement

This plan must stay aligned with:

- `docs/architecture-analysis/2026-04-22-turtle-cash-health-p4b-sample-onboarding.md`
- `docs/architecture-analysis/new-report-sample-onboarding-and-field-variance-process.md`

Every new regression must reflect the current anchor contract:

- `601919 2025`
  - `restricted_cash = not_surfaced`
  - `interest_paid_cash = not_surfaced`
  - `time_deposits_or_wealth_products = not_surfaced`
- `02498 2022`
  - `restricted_cash = absent`
  - `interest_paid_cash = absent`
  - `time_deposits_or_wealth_products = absent`
- `09987 2025`
  - `restricted_cash = present`
  - `interest_paid_cash = present`
  - `time_deposits_or_wealth_products = present`

If focused diagnostics change these expectations, update the onboarding artifact before changing the implementation contract.

## Execution Note

This plan is designed for subagent-driven execution, but Tasks 2, 3, and 5 must run serially because they all touch:

- `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
- `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

Do not dispatch those tasks in parallel.

## File Structure

Modify existing files:

- `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
  - Add metric definitions for the three P4B metrics.
  - Keep their scope narrow and note/disclosure oriented; do not re-open broad parent-scope behavior.
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
  - Add only the deterministic row-label normalization needed for stable P4B metric identities when a bounded disclosure row is already recovered.
- `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
  - Add bounded parsing helpers for restricted-cash note rows, cash-paid-for-interest supplemental rows, and time-deposit / wealth-product rows.
- `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
  - Wire P4B note candidates and `cash_health_missing_status` into document metadata while preserving P4A precedence.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py`
  - Extend locator output space only if deterministic parsing is insufficient.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py`
  - Gate any P4B locator use behind bounded note/disclosure contexts and explicit budget.
- `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- `financial-report-analysis/tests/unit/test_table_semantics.py`
- `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`
- `financial-report-analysis/tests/unit/test_semantic_fallback_models.py`
- `financial-report-analysis/tests/unit/test_semantic_fallback_service.py`
- `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

No new API surface is planned in this phase.

---

### Task 0: Reconfirm P4B Onboarding Contract

**Files:**

- Modify: `docs/architecture-analysis/2026-04-22-turtle-cash-health-p4b-sample-onboarding.md`

- [ ] **Step 1: Re-read the onboarding artifact against the current P4B spec**

Open:

- `docs/architecture-analysis/2026-04-22-turtle-cash-health-p4b-sample-onboarding.md`
- `docs/superpowers/specs/2026-04-22-financial-report-analysis-turtle-cash-health-notes-bridge-p4b-design.md`

Confirm that the anchor contract still matches the current plan header:

- `601919 2025` -> all three metrics `not_surfaced`
- `02498 2022` -> all three metrics `absent`
- `09987 2025` -> all three metrics `present`

- [ ] **Step 2: Update the onboarding artifact only if diagnostics changed**

If any focused probe since spec writing changed `present / absent / not_surfaced`, edit the markdown artifact before touching code. If nothing changed, leave the file untouched and record in the task notes that the onboarding artifact remains current.

- [ ] **Step 3: Commit onboarding confirmation if changed**

If the artifact changed:

```bash
git add docs/architecture-analysis/2026-04-22-turtle-cash-health-p4b-sample-onboarding.md
git commit -m "docs: refresh turtle cash health p4b onboarding"
```

If no file changed, skip this commit step and proceed to Task 1.

---

### Task 1: Lock Registry And Semantic Contract For P4B Metrics

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- Modify: `financial-report-analysis/tests/unit/test_table_semantics.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`

- [ ] **Step 1: Add failing registry tests for the three P4B metrics**

Append these tests to `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`:

```python
import pytest


@pytest.mark.parametrize(
    ("metric_id", "market", "label"),
    [
        ("restricted_cash", "HK", "restricted cash"),
        ("restricted_cash", "HK", "restricted cash and cash equivalents"),
        ("interest_paid_cash", "HK", "cash paid for interest"),
        ("time_deposits_or_wealth_products", "HK", "time deposits"),
        ("time_deposits_or_wealth_products", "HK", "wealth management products"),
        ("time_deposits_or_wealth_products", "CN", "\u5b9a\u671f\u5b58\u6b3e"),
        ("time_deposits_or_wealth_products", "CN", "\u7406\u8d22\u4ea7\u54c1"),
    ],
)
def test_metric_mapping_registry_matches_p4b_cash_health_fields(
    metric_id: str,
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="note_disclosure",
        normalized_row_label=label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is not None
    assert definition.metric_id == metric_id
```

- [ ] **Step 2: Add failing negative-control tests for non-P4B labels**

Append this test to `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`:

```python
@pytest.mark.parametrize(
    ("market", "label"),
    [
        ("HK", "finance costs"),
        ("HK", "interest expense"),
        ("HK", "short-term investments"),
        ("HK", "cash and cash equivalents"),
        ("CN", "\u8d22\u52a1\u8d39\u7528"),
        ("CN", "\u5229\u606f\u652f\u51fa"),
        ("CN", "\u8d27\u5e01\u8d44\u91d1"),
        ("CN", "\u4ea4\u6613\u6027\u91d1\u878d\u8d44\u4ea7"),
    ],
)
def test_metric_mapping_registry_does_not_misclassify_non_cash_health_rows(
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="note_disclosure",
        normalized_row_label=label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is None
```

- [ ] **Step 3: Add failing row-normalization tests**

Append these tests to `financial-report-analysis/tests/unit/test_table_semantics.py`:

```python
import pytest


@pytest.mark.parametrize(
    ("raw_label", "market", "expected"),
    [
        ("Restricted cash", "HK", "restricted cash"),
        ("Restricted cash and cash equivalents", "HK", "restricted cash and cash equivalents"),
        ("Cash paid for interest", "HK", "cash paid for interest"),
        ("Time deposits", "HK", "time deposits"),
        ("Wealth management products", "HK", "wealth management products"),
        ("\u53d7\u9650\u8d27\u5e01\u8d44\u91d1", "CN", "\u53d7\u9650\u8d27\u5e01\u8d44\u91d1"),
        ("\u652f\u4ed8\u7684\u5229\u606f", "CN", "\u652f\u4ed8\u7684\u5229\u606f"),
        ("\u7ed3\u6784\u6027\u5b58\u6b3e", "CN", "\u7ed3\u6784\u6027\u5b58\u6b3e"),
    ],
)
def test_normalize_row_label_supports_p4b_cash_health_families(
    raw_label: str,
    market: str,
    expected: str,
) -> None:
    assert normalize_row_label(raw_label, market=market) == expected
```

- [ ] **Step 4: Run the new tests and confirm they fail**

Run from `financial-report-analysis/`:

```bash
uv run pytest tests/unit/test_metric_mapping_registry.py::test_metric_mapping_registry_matches_p4b_cash_health_fields tests/unit/test_metric_mapping_registry.py::test_metric_mapping_registry_does_not_misclassify_non_cash_health_rows tests/unit/test_table_semantics.py::test_normalize_row_label_supports_p4b_cash_health_families -q
```

Expected: FAIL because the three P4B metrics and their row families are not yet registered.

- [ ] **Step 5: Add minimal registry and normalization support**

In `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`, add three `MetricMappingDefinition` entries with:

- `metric_id="restricted_cash"`
  - `statement_type="balance_sheet"`
  - `period_scope="point_in_time"`
  - `normalized_row_labels` including:
    - `"restricted cash"`
    - `"restricted cash and cash equivalents"`
    - `"\u53d7\u9650\u8d27\u5e01\u8d44\u91d1"`
- `metric_id="interest_paid_cash"`
  - `statement_type="cash_flow_statement"`
  - `period_scope="duration"`
  - `normalized_row_labels` including:
    - `"cash paid for interest"`
    - `"\u652f\u4ed8\u7684\u5229\u606f"`
- `metric_id="time_deposits_or_wealth_products"`
  - `statement_type="balance_sheet"`
  - `period_scope="point_in_time"`
  - `normalized_row_labels` including:
    - `"time deposits"`
    - `"term deposits"`
    - `"wealth management products"`
    - `"structured deposits"`
    - `"\u5b9a\u671f\u5b58\u6b3e"`
    - `"\u7406\u8d22\u4ea7\u54c1"`
    - `"\u7ed3\u6784\u6027\u5b58\u6b3e"`

In `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`, add only the normalization rules needed to preserve these labels as stable row families. Do not collapse them into existing broad labels such as `cash`, `interest expense`, or `short-term investments`.

- [ ] **Step 6: Re-run the focused unit tests**

Run:

```bash
uv run pytest tests/unit/test_metric_mapping_registry.py::test_metric_mapping_registry_matches_p4b_cash_health_fields tests/unit/test_metric_mapping_registry.py::test_metric_mapping_registry_does_not_misclassify_non_cash_health_rows tests/unit/test_table_semantics.py::test_normalize_row_label_supports_p4b_cash_health_families -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py financial-report-analysis/tests/unit/test_metric_mapping_registry.py financial-report-analysis/tests/unit/test_table_semantics.py
git commit -m "feat: add turtle p4b cash health registry semantics"
```

---

### Task 2: Add Deterministic Restricted-Cash Note Parsing

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`

- [ ] **Step 1: Add failing restricted-cash parsing tests**

Append these tests to `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`:

```python
def test_build_cash_health_note_candidates_extracts_restricted_cash_from_hk_note() -> None:
    note_text = (
        "Restricted cash and restricted monetary funds were RMB 123 million and "
        "RMB 98 million as of December 31, 2022 and 2021, respectively."
    )

    candidates, missing_status = build_cash_health_note_candidate_facts(
        pdf_text=note_text,
        market="HK",
        document_id="doc-02498",
        period_id="2022FY",
        currency="RMB",
    )

    metric_ids = {candidate["metric_id"] for candidate in candidates}

    assert "restricted_cash" in metric_ids
    assert missing_status["restricted_cash"] == "present"


def test_build_cash_health_note_candidates_does_not_treat_plain_cash_as_restricted_cash() -> None:
    note_text = "Cash and cash equivalents were RMB 500 million as of December 31, 2022."

    candidates, missing_status = build_cash_health_note_candidate_facts(
        pdf_text=note_text,
        market="HK",
        document_id="doc-cash",
        period_id="2022FY",
        currency="RMB",
    )

    assert [candidate["metric_id"] for candidate in candidates] == []
    assert missing_status["restricted_cash"] in {"absent", "not_surfaced"}
```

- [ ] **Step 2: Run the new restricted-cash tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_note_disclosure_ingestion.py::test_build_cash_health_note_candidates_extracts_restricted_cash_from_hk_note tests/unit/test_note_disclosure_ingestion.py::test_build_cash_health_note_candidates_does_not_treat_plain_cash_as_restricted_cash -q
```

Expected: FAIL because the cash-health note builder does not exist yet.

- [ ] **Step 3: Implement a bounded restricted-cash note builder**

In `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`:

- add a new public helper:
  - `build_cash_health_note_candidate_facts(...)`
- keep the implementation parallel to the existing asset / debt / working-capital helpers
- add a bounded metric-definition family for:
  - `restricted_cash`
- only parse local rows or sentences that include explicit restricted-cash language such as:
  - `"restricted cash"`
  - `"restricted cash and cash equivalents"`
  - `"restricted monetary funds"`
  - `"\u53d7\u9650\u8d27\u5e01\u8d44\u91d1"`
  - `"\u5df2\u62b5\u62bc\u5b58\u6b3e"` when the local context clearly indicates restricted cash, not general collateral narrative
- set candidate metadata:
  - `source_kind="deterministic_note_disclosure"`
  - `source_policy="supplement_only"`
  - note/disclosure provenance extensions matching the existing note builders

Do not parse plain cash rows, generic deposit descriptions, or broad asset-restriction narrative into `restricted_cash`.

- [ ] **Step 4: Re-run the restricted-cash tests**

Run:

```bash
uv run pytest tests/unit/test_note_disclosure_ingestion.py::test_build_cash_health_note_candidates_extracts_restricted_cash_from_hk_note tests/unit/test_note_disclosure_ingestion.py::test_build_cash_health_note_candidates_does_not_treat_plain_cash_as_restricted_cash -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py
git commit -m "feat: add restricted cash note disclosure parsing"
```

---

### Task 3: Add Deterministic Interest-Paid And Time-Deposit Parsing

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`

- [ ] **Step 1: Add failing tests for `interest_paid_cash` and `time_deposits_or_wealth_products`**

Append these tests to `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`:

```python
def test_build_cash_health_note_candidates_extracts_interest_paid_cash_from_cash_flow_supplement() -> None:
    note_text = "Supplemental cash flow disclosure: Cash paid for interest was US$42 million."

    candidates, missing_status = build_cash_health_note_candidate_facts(
        pdf_text=note_text,
        market="HK",
        document_id="doc-09987",
        period_id="2025FY",
        currency="USD",
    )

    by_metric = {candidate["metric_id"]: candidate for candidate in candidates}

    assert by_metric["interest_paid_cash"]["numeric_value"] == 42.0
    assert missing_status["interest_paid_cash"] == "present"


def test_build_cash_health_note_candidates_extracts_time_deposit_family() -> None:
    note_text = (
        "Time deposits and long-term bank deposits and notes were US$180 million "
        "and US$95 million as of December 31, 2025 and 2024."
    )

    candidates, missing_status = build_cash_health_note_candidate_facts(
        pdf_text=note_text,
        market="HK",
        document_id="doc-09987",
        period_id="2025FY",
        currency="USD",
    )

    metric_ids = {candidate["metric_id"] for candidate in candidates}

    assert "time_deposits_or_wealth_products" in metric_ids
    assert missing_status["time_deposits_or_wealth_products"] == "present"


def test_build_cash_health_note_candidates_does_not_map_interest_expense_to_interest_paid_cash() -> None:
    note_text = "Finance costs included interest expense of US$42 million."

    candidates, _ = build_cash_health_note_candidate_facts(
        pdf_text=note_text,
        market="HK",
        document_id="doc-negative",
        period_id="2025FY",
        currency="USD",
    )

    assert "interest_paid_cash" not in {candidate["metric_id"] for candidate in candidates}
```

- [ ] **Step 2: Run the new tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_note_disclosure_ingestion.py::test_build_cash_health_note_candidates_extracts_interest_paid_cash_from_cash_flow_supplement tests/unit/test_note_disclosure_ingestion.py::test_build_cash_health_note_candidates_extracts_time_deposit_family tests/unit/test_note_disclosure_ingestion.py::test_build_cash_health_note_candidates_does_not_map_interest_expense_to_interest_paid_cash -q
```

Expected: FAIL because the current bounded note builder does not yet cover these metric families.

- [ ] **Step 3: Extend the bounded note builder**

In `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`:

- extend `build_cash_health_note_candidate_facts(...)` to cover:
  - `interest_paid_cash`
    - only from local cash-flow supplement or explicit `cash paid for interest` wording
  - `time_deposits_or_wealth_products`
    - from bounded local rows including:
      - `"time deposits"`
      - `"term deposits"`
      - `"wealth management products"`
      - `"long-term bank deposits and notes"`
      - `"\u5b9a\u671f\u5b58\u6b3e"`
      - `"\u7ed3\u6784\u6027\u5b58\u6b3e"`
      - `"\u7406\u8d22\u4ea7\u54c1"`
- keep `time_deposits_or_wealth_products` as one bridge identity in P4B; do not split it into multiple canonical metrics
- keep the parser bounded to local note/disclosure context and supplemental cash-flow rows only

Do not parse:

- `interest expense`
- generic financing costs
- broad `short-term investments`
- narrative deposit strategy text with no local numeric disclosure

- [ ] **Step 4: Re-run the focused note-ingestion tests**

Run:

```bash
uv run pytest tests/unit/test_note_disclosure_ingestion.py::test_build_cash_health_note_candidates_extracts_interest_paid_cash_from_cash_flow_supplement tests/unit/test_note_disclosure_ingestion.py::test_build_cash_health_note_candidates_extracts_time_deposit_family tests/unit/test_note_disclosure_ingestion.py::test_build_cash_health_note_candidates_does_not_map_interest_expense_to_interest_paid_cash -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py
git commit -m "feat: add turtle cash health note disclosure parsing"
```

---

### Task 4: Wire P4B Candidates Into PDF Ingestion And Missing Status

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`

- [ ] **Step 1: Add failing pipeline tests for precedence and missing status**

Append these tests to `financial-report-analysis/tests/unit/test_fact_pipeline.py`:

```python
def test_pdf_ingestion_adds_cash_health_missing_status_to_document_metadata(
    monkeypatch,
    tmp_path,
) -> None:
    adapter = PdfIngestionAdapter()
    pdf_path = tmp_path / "cash-health.pdf"
    pdf_path.touch()

    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text_pages",
        lambda self, *, pdf_path, pdf_url: [
            (
                1,
                "Supplemental cash flow disclosure: Cash paid for interest was US$42 million.\n"
                "Time deposits were US$180 million.\n"
                "Restricted cash was US$12 million.\n",
            )
        ],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_parsed_tables",
        lambda self, *, pdf_path, pdf_url, market: [],
    )

    result = adapter.extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
        min_confidence=None,
    )

    assert result["document_metadata"]["cash_health_missing_status"] == {
        "restricted_cash": "present",
        "interest_paid_cash": "present",
        "time_deposits_or_wealth_products": "present",
    }


def test_cash_health_note_candidates_do_not_override_statement_row_fact() -> None:
    resolver = ConflictResolver()

    statement_candidate = CandidateFact(
        candidate_fact_id="candidate::statement-row",
        metric_id="restricted_cash",
        metric_label_raw="Restricted cash",
        statement_type="balance_sheet",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        period_id="2025FY",
        currency="USD",
        raw_value="10",
        numeric_value=10.0,
        raw_unit=None,
        normalized_unit=None,
        precision=0,
        confidence=0.9,
        evidence_bundle_id="bundle::statement",
        extensions={"source_kind": "statement_row", "source_policy": "default"},
    )
    note_candidate = CandidateFact(
        candidate_fact_id="candidate::note",
        metric_id="restricted_cash",
        metric_label_raw="Restricted cash",
        statement_type="balance_sheet",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        period_id="2025FY",
        currency="USD",
        raw_value="12",
        numeric_value=12.0,
        raw_unit=None,
        normalized_unit=None,
        precision=0,
        confidence=0.8,
        evidence_bundle_id="bundle::note",
        extensions={
            "source_kind": "deterministic_note_disclosure",
            "source_policy": "supplement_only",
        },
    )

    result = resolver.resolve_with_review([statement_candidate, note_candidate])

    assert result.canonical_facts[0].numeric_value == 10.0
```

- [ ] **Step 2: Run the new tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_fact_pipeline.py::test_pdf_ingestion_adds_cash_health_missing_status_to_document_metadata tests/unit/test_fact_pipeline.py::test_cash_health_note_candidates_do_not_override_statement_row_fact -q
```

Expected: FAIL because `cash_health_missing_status` is not wired and the new candidate family is not yet threaded through ingestion.

- [ ] **Step 3: Wire P4B candidates into ingestion**

In `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`:

- import `build_cash_health_note_candidate_facts`
- call it after table-derived candidates and alongside existing working-capital / debt / asset note builders
- append the returned note candidates without disturbing candidate order for higher-priority statement-row facts
- add:
  - `cash_health_missing_status`
to `document_metadata`

Follow the same pattern already used for:

- `working_capital_missing_status`
- `debt_missing_status`
- `asset_missing_status`

- [ ] **Step 4: Re-run the focused pipeline tests**

Run:

```bash
uv run pytest tests/unit/test_fact_pipeline.py::test_pdf_ingestion_adds_cash_health_missing_status_to_document_metadata tests/unit/test_fact_pipeline.py::test_cash_health_note_candidates_do_not_override_statement_row_fact -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py financial-report-analysis/tests/unit/test_fact_pipeline.py
git commit -m "feat: wire turtle p4b cash health candidates"
```

---

### Task 5: Add Bounded Integration Regressions For The Three Anchors

**Files:**

- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

- [ ] **Step 1: Add a failing HK `02498` regression for the current absent baseline**

Append this test to `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`:

```python
def test_hk_02498_2022_keeps_p4b_cash_health_absent() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")

    assert not _candidate_facts_for_metric(payload, "restricted_cash")
    assert not _candidate_facts_for_metric(payload, "interest_paid_cash")
    assert not _candidate_facts_for_metric(payload, "time_deposits_or_wealth_products")
    assert payload.get("document_metadata", {}).get("cash_health_missing_status") == {
        "restricted_cash": "absent",
        "interest_paid_cash": "absent",
        "time_deposits_or_wealth_products": "absent",
    }
```

- [ ] **Step 2: Add a failing HK `09987` regression for the full P4B family**

Append this test to the same file:

```python
def test_hk_09987_2025_surfaces_only_p4b_cash_health_note_candidates() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")

    metric_ids = {fact["metric_id"] for fact in payload["candidate_facts"]}

    assert {"restricted_cash", "interest_paid_cash", "time_deposits_or_wealth_products"} <= metric_ids
    assert payload.get("document_metadata", {}).get("cash_health_missing_status") == {
        "restricted_cash": "present",
        "interest_paid_cash": "present",
        "time_deposits_or_wealth_products": "present",
    }
```

- [ ] **Step 3: Add a failing CN `601919` guardrail regression**

Append this test to the same file:

```python
def test_cn_601919_2025_keeps_p4b_cash_health_as_not_surfaced_guardrail() -> None:
    pdf_path = _resolve_sample("cn_stocks", "601919", "annual", "2025_\u5e74\u5ea6\u62a5\u544a.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="CN")

    assert payload.get("document_metadata", {}).get("cash_health_missing_status") == {
        "restricted_cash": "not_surfaced",
        "interest_paid_cash": "not_surfaced",
        "time_deposits_or_wealth_products": "not_surfaced",
    }
```

- [ ] **Step 4: Run the three new integration tests and confirm failure**

Run:

```bash
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_keeps_p4b_cash_health_absent tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_only_p4b_cash_health_note_candidates tests/integration/test_semantic_recovery_regressions.py::test_cn_601919_2025_keeps_p4b_cash_health_as_not_surfaced_guardrail -q -o addopts=
```

Expected: FAIL because the P4B candidate family and its missing-status metadata are not fully wired yet.

- [ ] **Step 5: Make the minimal implementation changes needed for the three anchors**

Adjust `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py` and `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py` only as needed so that:

- `02498 2022` remains correctly classified as all three metrics `absent`
- `09987 2025` surfaces all three P4B metric candidates
- `601919 2025` remains `not_surfaced`, not `absent`

Do not introduce:

- issuer-code branches
- broad full-text scanning
- narrative policy parsing

- [ ] **Step 6: Re-run the three integration regressions**

Run:

```bash
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_keeps_p4b_cash_health_absent tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_only_p4b_cash_health_note_candidates tests/integration/test_semantic_recovery_regressions.py::test_cn_601919_2025_keeps_p4b_cash_health_as_not_surfaced_guardrail -q -o addopts=
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py
git commit -m "feat: add turtle p4b cash health anchor regressions"
```

---

### Task 6: Add Locator Support Only If Deterministic Parsing Still Leaves An Anchor Unstable

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_semantic_fallback_models.py`
- Modify: `financial-report-analysis/tests/unit/test_semantic_fallback_service.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py`

- [ ] **Step 1: Decide whether this task is needed**

Before editing code, run the Task 5 integration regressions again. If all three anchors are stable with deterministic parsing, mark Task 6 `not needed` and skip to Task 7.

Current note: if the three-anchor deterministic regression passes with:

- `02498 2022` classified as all three metrics `absent`
- `09987 2025` classified as all three metrics `present`
- `601919 2025` classified as all three metrics `not_surfaced`

then Task 6 remains `not needed`.

- [ ] **Step 2: If needed, add failing locator-output tests**

Append this test to `financial-report-analysis/tests/unit/test_semantic_fallback_models.py`:

```python
def test_p4b_locator_output_schema_allows_only_cash_health_metric_ids() -> None:
    result = DisclosureLocatorResult(
        metric_id="restricted_cash",
        matched_label="restricted cash",
        source_text_span="restricted cash was US$12 million",
        confidence=0.81,
        reason="explicit restricted cash wording",
    )

    assert result.metric_id == "restricted_cash"
```

Append this test to `financial-report-analysis/tests/unit/test_semantic_fallback_service.py`:

```python
def test_cash_health_locator_budget_defaults_to_zero_when_disabled() -> None:
    service = SemanticFallbackService(
        config=SemanticFallbackConfig(enable_disclosure_locator=False),
    )

    assert service._should_attempt_cash_health_locator(
        local_context="restricted time deposits were US$12 million",
        candidate_metric_ids={"restricted_cash"},
        attempts_for_document=0,
    ) is False
```

- [ ] **Step 3: Run the locator tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_semantic_fallback_models.py::test_p4b_locator_output_schema_allows_only_cash_health_metric_ids tests/unit/test_semantic_fallback_service.py::test_cash_health_locator_budget_defaults_to_zero_when_disabled -q
```

Expected: FAIL if the bounded P4B locator surface does not exist yet.

- [ ] **Step 4: Implement the minimum bounded locator support**

In `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py` and `service.py`:

- restrict the P4B locator output space to:
  - `restricted_cash`
  - `interest_paid_cash`
  - `time_deposits_or_wealth_products`
- require:
  - local bounded disclosure context
  - explicit candidate metric shortlist
  - per-document attempt budget
  - provenance fields already used by existing locator flows
- keep the default disabled unless deterministic parsing left a positive anchor unstable

Do not allow:

- direct numeric extraction by the locator
- document-wide semantic scanning
- locator promotion over an existing deterministic fact

- [ ] **Step 5: Re-run the focused locator tests**

Run:

```bash
uv run pytest tests/unit/test_semantic_fallback_models.py::test_p4b_locator_output_schema_allows_only_cash_health_metric_ids tests/unit/test_semantic_fallback_service.py::test_cash_health_locator_budget_defaults_to_zero_when_disabled -q
```

Expected: PASS.

- [ ] **Step 6: Commit only if this task was necessary**

```bash
git add financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py financial-report-analysis/tests/unit/test_semantic_fallback_models.py financial-report-analysis/tests/unit/test_semantic_fallback_service.py
git commit -m "feat: add bounded p4b cash health locator support"
```

Skip this commit if Task 6 was not needed.

---

### Task 7: Close Out P4B With Focused Verification

**Files:**

- Modify: `docs/superpowers/plans/2026-04-22-financial-report-analysis-turtle-cash-health-notes-bridge-p4b-implementation-plan.md`

- [ ] **Step 1: Run the focused unit regression**

Run:

```bash
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py tests/unit/test_note_disclosure_ingestion.py tests/unit/test_fact_pipeline.py tests/unit/test_semantic_fallback_models.py tests/unit/test_semantic_fallback_service.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the focused real-PDF integration regression**

Run:

```bash
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_keeps_p4b_cash_health_absent tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_p4b_cash_health_candidates tests/integration/test_semantic_recovery_regressions.py::test_cn_601919_2025_keeps_p4b_cash_health_as_not_surfaced -q -o addopts=
```

Expected: PASS.

- [ ] **Step 3: Run non-regression checks for prior Turtle phases**

Run:

```bash
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_only_missing_p2b_note_disclosure_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_only_missing_p3_note_only_asset_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_debt_note_disclosure_supplement_preserves_statement_row_precedence tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_note_disclosure_candidates_keep_note_provenance -q -o addopts=
```

Expected: PASS.

- [ ] **Step 4: Run Ruff**

Run:

```bash
uv run ruff check src tests
```

Expected: all checks passed.

- [ ] **Step 5: Optionally run live-Ollama smoke only if Task 6 was required**

If Task 6 introduced or changed locator behavior, run:

```bash
$env:FRA_RUN_OLLAMA_SMOKE='1'; uv run pytest tests/unit/test_semantic_fallback_service.py::test_live_ollama_smoke -q
```

Expected: PASS if local Ollama at `127.0.0.1:11434` is healthy; otherwise record that the smoke test was skipped or failed due to local environment health and do not treat it as a closeout blocker unless P4B depended on live fallback.

- [ ] **Step 6: Add a completion note to this plan**

At the top of this plan, add a completion note in the same style used by the P4A plan:

```markdown
> **Completion Note:** Implemented in commits `<first>..<last>`. Verified with focused unit regression (`<result>`), focused real-PDF regression (`<result>`), non-regression suite (`<result>`), and `uv run ruff check src tests`.
```

- [ ] **Step 7: Commit the closeout note**

```bash
git add docs/superpowers/plans/2026-04-22-financial-report-analysis-turtle-cash-health-notes-bridge-p4b-implementation-plan.md
git commit -m "docs: close turtle cash health p4b implementation plan"
```

---

## Self-Review

### Spec coverage

This plan covers the P4B spec sections by task:

- narrow scope and three metrics -> Tasks 1-5
- onboarding / missing-status contract -> Task 0 and Task 5
- deterministic-first note bridge -> Tasks 2-5
- precedence preservation -> Task 4 and Task 5
- optional locator only as fallback -> Task 6
- focused verification and closeout -> Task 7

### Placeholder scan

The plan contains no `TODO`, `TBD`, or “similar to previous task” placeholders. Conditional behavior is limited to Task 6, which explicitly defines the skip rule.

### Type consistency

The metric IDs are consistent throughout the plan:

- `restricted_cash`
- `interest_paid_cash`
- `time_deposits_or_wealth_products`

The missing-status metadata key is also consistent throughout the plan:

- `cash_health_missing_status`

---

Plan complete and saved to `docs/superpowers/plans/2026-04-22-financial-report-analysis-turtle-cash-health-notes-bridge-p4b-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
