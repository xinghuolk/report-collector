# HK00001 Remaining Main Statement Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 HK.00001 2025 年报剩余主报表关键字段在禁用 semantic fallback 时可复现地产出 deterministic availability，或被明确归类为 not_surfaced/absent。

**Architecture:** 先补 E2E 脚本 deterministic-only 报告模式，让验证可复现；再按 structure -> semantics -> mapping -> fact builder 顺序修字段。实现必须复用通用 HK 主报表规则和 registry aliases，不允许按股票代码硬编码。

**Tech Stack:** Python 3.12, pytest, Bash, existing `PdfIngestionAdapter`, `MetricMappingRegistry`, `report_metric_availability.py`, real PDF fixtures under `report/downloads/hk_stocks`.

---

## Context

Spec: `financial-report-analysis/docs/superpowers/specs/2026-04-29-hk00001-remaining-main-statement-metrics-design.md`

Current evidence:

- Deterministic focused report currently has `revenue`, `total_profit`, `cash`, `fix_assets`, `goodwill` present and `inventory` absent.
- Slow path report currently has `total=32`, `present=4`, `absent=25`, `not_surfaced=3`.
- Spec reviewer blocked previous phase because `operating_cost`, `total_assets`, `operating_cash_flow` were not deterministic present or explicitly classified.

Guardrails:

- Do not add issuer-specific branches.
- Do not map “cash generated from operating activities before interest expenses, other finance costs, tax paid, and changes in working capital” to `operating_cash_flow`.
- Do not map `total assets less current liabilities` to `total_assets`.
- Do not use Ollama fallback for deterministic acceptance.
- Preserve existing HK anchors: `02498`, `06862`, `09987`, and HK00001 structure recovery.

---

## Files

- Modify: `financial-report-analysis/scripts/run-real-pdf-e2e-evaluation.sh`
  - Add deterministic-only availability mode and expected metric list support.
- Modify: `financial-report-analysis/tests/unit/test_real_pdf_e2e_evaluation_script.py`
  - Cover dry-run output for deterministic-only paths and expected metric parsing.
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
  - Add only verified generic HK aliases needed for remaining fields.
- Modify: `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
  - Add positive and negative mapping tests.
- Modify: `financial-report-analysis/tests/integration/test_table_structure_ingestion.py`
  - Add real-PDF structure assertions for exact labels required by remaining metrics.
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`
  - Add deterministic candidate/availability regression for HK00001 remaining metrics.
- Modify: `docs/architecture-analysis/2026-04-22-turtle-v015-financial-field-gap-analysis.md`
  - Record final classification and verification output.

---

### Task 1: Add Deterministic-Only E2E Report Mode

**Files:**
- Modify: `financial-report-analysis/scripts/run-real-pdf-e2e-evaluation.sh`
- Modify: `financial-report-analysis/tests/unit/test_real_pdf_e2e_evaluation_script.py`

- [ ] **Step 1: Add failing dry-run unit test**

Append this test to `financial-report-analysis/tests/unit/test_real_pdf_e2e_evaluation_script.py`:

```python
def test_real_pdf_e2e_evaluation_script_supports_deterministic_report_mode(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    sample_pdf = (
        project_root.parent
        / "report"
        / "downloads"
        / "hk_stocks"
        / "00001"
        / "annual"
        / "2025_annual_en.pdf"
    )
    sample_pdf.parent.mkdir(parents=True, exist_ok=True)
    sample_pdf.touch()

    env = os.environ.copy()
    env["FRA_E2E_DETERMINISTIC_ONLY"] = "true"
    env["FRA_E2E_EXPECTED_METRIC_IDS"] = (
        "revenue,operating_cost,total_assets,operating_cash_flow"
    )
    env["FRA_E2E_OUTPUT_DIR"] = str(tmp_path / "reports")

    result = subprocess.run(
        [str(project_root / "scripts" / "run-real-pdf-e2e-evaluation.sh"), "--dry-run"],
        cwd=project_root,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert "deterministic_only=true" in result.stdout
    assert "expected_metric_ids=revenue,operating_cost,total_assets,operating_cash_flow" in result.stdout
    assert (
        "metric_report="
        f"{tmp_path}/reports/HK_00001_2025_annual_deterministic_metric_availability.md"
    ) in result.stdout
    assert (
        "summary="
        f"{tmp_path}/reports/HK_00001_2025_annual_deterministic_summary.txt"
    ) in result.stdout
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_real_pdf_e2e_evaluation_script.py -q
```

Expected: the new test fails because dry-run output does not include `deterministic_only`, `expected_metric_ids`, or deterministic output paths.

- [ ] **Step 3: Implement deterministic-only mode**

In `financial-report-analysis/scripts/run-real-pdf-e2e-evaluation.sh`, add variables after `OUTPUT_DIR`:

```bash
DETERMINISTIC_ONLY="${FRA_E2E_DETERMINISTIC_ONLY:-false}"
EXPECTED_METRIC_IDS="${FRA_E2E_EXPECTED_METRIC_IDS:-}"
REPORT_SUFFIX="metric_availability"
SUMMARY_SUFFIX="summary"
if [[ "$DETERMINISTIC_ONLY" == "true" ]]; then
  REPORT_SUFFIX="deterministic_metric_availability"
  SUMMARY_SUFFIX="deterministic_summary"
fi
```

Replace the report path definitions with:

```bash
REPORT_PATH="${OUTPUT_DIR}/${MARKET}_${STOCK_CODE}_${FISCAL_YEAR}_${REPORT_TYPE}_${REPORT_SUFFIX}.md"
SUMMARY_PATH="${OUTPUT_DIR}/${MARKET}_${STOCK_CODE}_${FISCAL_YEAR}_${REPORT_TYPE}_${SUMMARY_SUFFIX}.txt"
```

Add these lines to `print_config()`:

```bash
  printf 'deterministic_only=%s\n' "$DETERMINISTIC_ONLY"
  printf 'expected_metric_ids=%s\n' "$EXPECTED_METRIC_IDS"
```

Before the report generation command, build CLI args:

```bash
EXPECTED_METRIC_ARGS=()
if [[ -n "$EXPECTED_METRIC_IDS" ]]; then
  IFS=',' read -r -a EXPECTED_METRIC_ARRAY <<< "$EXPECTED_METRIC_IDS"
  for metric_id in "${EXPECTED_METRIC_ARRAY[@]}"; do
    metric_id="${metric_id//[[:space:]]/}"
    if [[ -n "$metric_id" ]]; then
      EXPECTED_METRIC_ARGS+=(--expected-metric-id "$metric_id")
    fi
  done
fi
```

Replace the report command with deterministic env support:

```bash
if [[ "$DETERMINISTIC_ONLY" == "true" ]]; then
  FRA_SEMANTIC_FALLBACK_ENABLED=false uv run python scripts/report_metric_availability.py \
    --pdf-path "$PDF_PATH" \
    --market "$MARKET" \
    "${EXPECTED_METRIC_ARGS[@]}" \
    --output "$REPORT_PATH"
else
  uv run python scripts/report_metric_availability.py \
    --pdf-path "$PDF_PATH" \
    --market "$MARKET" \
    "${EXPECTED_METRIC_ARGS[@]}" \
    --output "$REPORT_PATH"
fi
```

- [ ] **Step 4: Run script unit test**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_real_pdf_e2e_evaluation_script.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Run dry-run verification**

Run:

```bash
cd financial-report-analysis
FRA_E2E_DETERMINISTIC_ONLY=true \
FRA_E2E_EXPECTED_METRIC_IDS=revenue,operating_cost,total_assets,operating_cash_flow \
scripts/run-real-pdf-e2e-evaluation.sh --dry-run
```

Expected output includes:

```text
deterministic_only=true
expected_metric_ids=revenue,operating_cost,total_assets,operating_cash_flow
metric_report=.e2e-evaluation-reports/HK_00001_2025_annual_deterministic_metric_availability.md
summary=.e2e-evaluation-reports/HK_00001_2025_annual_deterministic_summary.txt
```

- [ ] **Step 6: Commit**

Run:

```bash
git add financial-report-analysis/scripts/run-real-pdf-e2e-evaluation.sh \
  financial-report-analysis/tests/unit/test_real_pdf_e2e_evaluation_script.py
git commit -m "test: add deterministic PDF availability mode"
```

---

### Task 2: Add Registry Positive and Negative Tests

**Files:**
- Modify: `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`

- [ ] **Step 1: Add failing registry tests**

Append these tests to `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`:

```python
def test_metric_mapping_registry_matches_hk_cost_of_inventories_sold() -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="income_statement",
        normalized_row_label="cost of inventories sold",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert definition is not None
    assert definition.metric_id == "operating_cost"


def test_metric_mapping_registry_does_not_map_total_assets_less_current_liabilities() -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label="total assets less current liabilities",
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert definition is None


def test_metric_mapping_registry_does_not_map_cash_before_working_capital_to_operating_cash_flow() -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="cash_flow_statement",
        normalized_row_label=(
            "cash generated from operating activities before interest expenses, "
            "other finance costs, tax paid, and changes in working capital"
        ),
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert definition is None
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_mapping_registry.py -q
```

Expected: only the `cost of inventories sold` test fails; negative tests should pass. If a negative test fails, stop and fix over-broad aliases before continuing.

- [ ] **Step 3: Add HK operating cost alias**

In `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`, update the `operating_cost` HK aliases from:

```python
"HK": ("cost of sales", "cost of revenue"),
```

to:

```python
"HK": ("cost of sales", "cost of revenue", "cost of inventories sold"),
```

- [ ] **Step 4: Run registry tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_mapping_registry.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py \
  financial-report-analysis/tests/unit/test_metric_mapping_registry.py
git commit -m "fix: map HK inventory cost rows"
```

---

### Task 3: Diagnose HK00001 Remaining Structure Rows

**Files:**
- Modify: `financial-report-analysis/tests/integration/test_table_structure_ingestion.py`
- Possible Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`

- [ ] **Step 1: Add focused structure visibility test**

Append this test near `test_hk00001_2025_dual_currency_main_statement_labels_are_recovered()`:

```python
@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk00001_2025_remaining_main_statement_labels_are_classified() -> None:
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(_hk_annual_anchor("00001", "2025_annual_en.pdf")),
        pdf_url=None,
        market="HK",
    )

    income_labels = _flatten_labels(
        [table for table in tables if table.table_kind == "income_statement"]
    )
    balance_labels = _flatten_labels(
        [table for table in tables if table.table_kind == "balance_sheet"]
    )
    cash_flow_labels = _flatten_labels(
        [table for table in tables if table.table_kind == "cash_flow_statement"]
    )

    assert "cost of inventories sold" in income_labels
    assert "total assets less current liabilities" in balance_labels
    assert "total assets" not in balance_labels
    assert "tax paid" in cash_flow_labels
    assert (
        "cash generated from operating activities before interest expenses, other finance costs, tax paid, and changes in working capital"
        in cash_flow_labels
    )
```

- [ ] **Step 2: Run focused structure test**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_table_structure_ingestion.py::test_hk00001_2025_remaining_main_statement_labels_are_classified -q
```

Expected:

- Pass if `total_assets` is not structurally present and cash-flow visible rows are only intermediate/tax rows.
- If it fails because `total assets` is present, update the assertion and use Task 4 to require deterministic `total_assets`.
- If it fails because labels are visibly present in page text but absent from parsed labels, fix `table_structure.py` with a focused unit test before continuing.

- [ ] **Step 3: Commit diagnostic structure test**

If Step 2 passes without production changes:

```bash
git add financial-report-analysis/tests/integration/test_table_structure_ingestion.py
git commit -m "test: classify HK00001 remaining statement labels"
```

If production changes were required, commit both files:

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py \
  financial-report-analysis/tests/integration/test_table_structure_ingestion.py
git commit -m "fix: expose HK00001 remaining statement labels"
```

---

### Task 4: Add Deterministic Candidate Regression

**Files:**
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`
- Possible Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Possible Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`

- [ ] **Step 1: Add failing deterministic candidate test**

Append this test after `test_hk00001_2025_main_statement_metrics_are_deterministic()`:

```python
@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk00001_2025_remaining_main_statement_metrics_are_classified() -> None:
    pdf_path = _resolve_sample("hk_stocks", "00001", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    deterministic_candidates = [
        candidate
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict)
        and candidate.get("period_id") == "2025FY"
        and candidate.get("entity_scope") == "consolidated"
        and candidate.get("extraction_method") == "table_semantics"
        and isinstance(candidate.get("extensions"), dict)
        and candidate["extensions"].get("semantic_source") == "deterministic"
    ]
    by_metric = {
        str(candidate.get("metric_id")): candidate
        for candidate in deterministic_candidates
    }

    assert by_metric["operating_cost"]["statement_type"] == "income_statement"
    assert by_metric["operating_cost"]["numeric_value"] == -113608.0

    assert "operating_cash_flow" not in by_metric
    assert "total_assets" not in by_metric

    assert by_metric["c_paid_for_taxes"]["statement_type"] == "cash_flow_statement"
    assert by_metric["c_paid_for_taxes"]["numeric_value"] is not None
    assert float(by_metric["c_paid_for_taxes"]["numeric_value"]) < 0
```

Note: If Task 3 proves `total_assets` is structurally present as an exact row, change the `total_assets` assertion to:

```python
assert by_metric["total_assets"]["statement_type"] == "balance_sheet"
assert by_metric["total_assets"]["numeric_value"] is not None
```

- [ ] **Step 2: Run the new test and inspect failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_hk00001_2025_remaining_main_statement_metrics_are_classified -q
```

Expected initial failure:

- `operating_cost` missing until Task 2 alias is present.
- `c_paid_for_taxes` may already pass because `tax paid` is mapped.
- `operating_cash_flow` and `total_assets` should remain absent unless exact rows are structurally visible.

- [ ] **Step 3: Fix only proven gaps**

Apply these rules:

- If `operating_cost` is missing and Task 2 alias was not applied, add `cost of inventories sold` HK alias as described in Task 2.
- If `c_paid_for_taxes` is missing but `tax paid` structure is visible, inspect whether `sign_rule="non_negative"` is filtering negative cash outflow. If filtered, adjust fact builder sign handling only for cash-flow outflow metrics with explicit negative source values and add a unit test in `tests/unit/test_table_fact_builder.py`.
- If `total_assets` exact row is not visible, do not create a mapping workaround. Keep it absent/not_surfaced.
- If `operating_cash_flow` exact final cash flow row is not visible, do not map the intermediate “before interest/tax/working capital” row.

- [ ] **Step 4: Run focused semantic regression**

Run:

```bash
cd financial-report-analysis
uv run pytest \
  tests/integration/test_semantic_recovery_regressions.py::test_hk00001_2025_main_statement_metrics_are_deterministic \
  tests/integration/test_semantic_recovery_regressions.py::test_hk00001_2025_remaining_main_statement_metrics_are_classified \
  -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py \
  financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py \
  financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py \
  financial-report-analysis/tests/unit/test_table_fact_builder.py
git commit -m "test: classify HK00001 remaining deterministic metrics"
```

If some listed files were not changed, omit them from `git add`.

---

### Task 5: Run Deterministic Report and Update Docs

**Files:**
- Modify: `docs/architecture-analysis/2026-04-22-turtle-v015-financial-field-gap-analysis.md`
- Modify: `financial-report-analysis/docs/superpowers/plans/2026-04-29-hk00001-remaining-main-statement-metrics.md`

- [x] **Step 1: Run focused unit tests**

Run:

```bash
cd financial-report-analysis
uv run pytest \
  tests/unit/test_real_pdf_e2e_evaluation_script.py \
  tests/unit/test_metric_mapping_registry.py \
  tests/unit/test_table_fact_builder.py \
  -q
```

Expected: all tests pass.

Actual evidence from previous worker: `174 passed in 0.32s`.

- [x] **Step 2: Run focused integration tests**

Run:

```bash
cd financial-report-analysis
uv run pytest \
  tests/integration/test_table_structure_ingestion.py::test_hk00001_2025_dual_currency_main_statement_labels_are_recovered \
  tests/integration/test_table_structure_ingestion.py::test_hk00001_2025_remaining_main_statement_labels_are_classified \
  tests/integration/test_semantic_recovery_regressions.py::test_hk00001_2025_main_statement_metrics_are_deterministic \
  tests/integration/test_semantic_recovery_regressions.py::test_hk00001_2025_remaining_main_statement_metrics_are_classified \
  -q
```

Expected: all tests pass.

Actual evidence from previous worker: `4 passed in 104.31s`.

- [x] **Step 3: Generate deterministic availability report**

Run:

```bash
cd financial-report-analysis
FRA_E2E_DETERMINISTIC_ONLY=true \
FRA_E2E_EXPECTED_METRIC_IDS=revenue,operating_cost,operating_profit,total_assets,total_liabilities,cash,operating_cash_flow,c_paid_for_taxes \
FRA_E2E_MARKET=HK \
FRA_E2E_STOCK_CODE=00001 \
FRA_E2E_FISCAL_YEAR=2025 \
FRA_E2E_REPORT_TYPE=annual \
FRA_E2E_PDF_PATH=../report/downloads/hk_stocks/00001/annual/2025_annual_en.pdf \
FRA_E2E_OUTPUT_DIR=/tmp/hk00001_2025_remaining_metrics \
scripts/run-real-pdf-e2e-evaluation.sh
```

Expected:

- extract/persist/readback E2E passes.
- Ollama fallback E2E may still run because this script verifies the full flow; deterministic-only only affects report generation.
- deterministic summary is written to:
  `/tmp/hk00001_2025_remaining_metrics/HK_00001_2025_annual_deterministic_summary.txt`
- deterministic report is written to:
  `/tmp/hk00001_2025_remaining_metrics/HK_00001_2025_annual_deterministic_metric_availability.md`

Actual evidence from mainline full E2E:

- Step 1 real PDF extract/persist/readback E2E: `1 passed in 317.23s (0:05:17)`
- Step 2 real PDF Ollama fallback E2E: `1 passed in 291.16s (0:04:51)`
- Step 3 deterministic report generated successfully
- summary: `total=8`, `present=5`, `absent=3`, `not_surfaced=0`
- semantic fallback call counts: `table_kind=0`, `row_label=0`, `currency=0`, `unit=0`
- deterministic present: `revenue=280036.0`, `operating_cost=-113608.0`, `cash=143748.0`, `operating_cash_flow=62567.0`, `c_paid_for_taxes=-5571.0`
- deterministic absent: `operating_profit`, `total_assets`, `total_liabilities`

- [x] **Step 4: Update Turtle gap document**

Add a dated subsection under the existing HK.00001 update in
`docs/architecture-analysis/2026-04-22-turtle-v015-financial-field-gap-analysis.md`:

```markdown
### 2026-04-29 HK.00001 Remaining Main Statement Metrics Follow-up

本轮在 deterministic/no-fallback 模式下复查 HK.00001 2025 剩余主报表字段：

- report: `/tmp/hk00001_2025_remaining_metrics/HK_00001_2025_annual_deterministic_metric_availability.md`
- summary: 写入实际 `present/absent/not_surfaced` 计数
- deterministic present: 写入实际 present metric ids
- explicitly not surfaced: 本轮实际 `not_surfaced=0`；`operating_cash_flow` 已 deterministic present，`total_assets` classified as absent
- negative controls: `total assets less current liabilities` 未映射 `total_assets`；`cash generated ... before interest/tax/working capital` 未映射 `operating_cash_flow`

结论：写明哪些字段已修成 deterministic 主路径，哪些字段需要下一轮 structure recovery 或附注/披露路径。
```

Actual documentation result: 已在 Turtle gap document 的 `2026-04-29 HK.00001 Remaining Main Statement Metrics Follow-up` 小节记录 report path、summary path、present/absent 明细、`operating_cash_flow=62567.0` 纠偏和两个负控结论。

- [x] **Step 5: Mark plan checkboxes**

In this plan file, mark completed steps with `[x]` and record actual command results under each task.

Actual plan result: Task 5 Steps 1-6 标记为完成；实际验证证据写入本 Task 5 段落。

- [x] **Step 6: Commit docs and plan update**

Run:

```bash
git add docs/architecture-analysis/2026-04-22-turtle-v015-financial-field-gap-analysis.md \
  financial-report-analysis/docs/superpowers/plans/2026-04-29-hk00001-remaining-main-statement-metrics.md
git commit -m "docs: record HK00001 remaining metric classification"
```

---

## Final Verification

- [x] **Step 1: Run all focused checks**

Run:

```bash
cd financial-report-analysis
uv run pytest \
  tests/unit/test_real_pdf_e2e_evaluation_script.py \
  tests/unit/test_metric_mapping_registry.py \
  tests/unit/test_table_fact_builder.py \
  tests/integration/test_table_structure_ingestion.py::test_hk00001_2025_dual_currency_main_statement_labels_are_recovered \
  tests/integration/test_table_structure_ingestion.py::test_hk00001_2025_remaining_main_statement_labels_are_classified \
  tests/integration/test_semantic_recovery_regressions.py::test_hk00001_2025_main_statement_metrics_are_deterministic \
  tests/integration/test_semantic_recovery_regressions.py::test_hk00001_2025_remaining_main_statement_metrics_are_classified \
  -q
```

Expected: all tests pass.

Actual result from mainline verification: `178 passed in 104.25s (0:01:44)`.

- [x] **Step 2: Check worktree**

Run:

```bash
git status --short
```

Expected: clean worktree after commits.

Actual result after Task 5 docs commit: `git status --short` produced no output.

- [x] **Step 3: Final review**

Dispatch two reviewers:

- Spec compliance reviewer: check this plan against the design spec and final docs.
- Code quality reviewer: check script changes, registry aliases, negative controls, and tests.

Do not merge or start the next field family until both reviewers pass or their blocking feedback is fixed.

Actual final review:

- Spec compliance reviewer: PASS, no blockers.
- Code/document quality reviewer: PASS, no critical or important issues.
- Non-blocking residual risks: HK page-title fallback still lacks focused synthetic unit coverage; deterministic-only script behavior is mainly covered by dry-run plus full report fallback counts.
