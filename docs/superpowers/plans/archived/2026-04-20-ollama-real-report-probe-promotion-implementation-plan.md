# Ollama Real-Report Probe Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real-report Ollama evaluation layer for the seven target fields, then promote only the most stable cases into hard regressions before resuming the previous Task 6 work.

**Architecture:** Keep the existing limited Ollama fallback unchanged, expand the real-report probe dataset to cover the seven target fields plus negative controls, and split verification into two layers: a gated evaluation test and a smaller always-on promotion set. Use the evaluation results to choose stable positive and negative cases for hard integration regressions.

**Tech Stack:** Python, pytest, Ruff, local Ollama (`http://127.0.0.1:11434`), `qwen3.5:9b`

---

### Task 1: Expand The Real-Report Probe Dataset

**Files:**
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\fixtures\ollama_real_report_probes.py`
- Test: `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_ollama_real_report_probes.py`

- [ ] **Step 1: Write the failing dataset coverage test**

```python
from tests.integration.fixtures.ollama_real_report_probes import (
    REAL_REPORT_ROW_LABEL_PROBE_CASES,
)


def test_real_report_probe_dataset_covers_all_target_metrics() -> None:
    expected = {
        "revenue",
        "operating_profit",
        "net_profit",
        "operating_cash_flow",
        "cash",
        "total_assets",
        "total_liabilities",
    }
    actual = {
        case.expected_label
        for case in REAL_REPORT_ROW_LABEL_PROBE_CASES
        if case.expected_label != "none"
    }
    assert expected <= actual
```

- [ ] **Step 2: Run the failing test**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/integration/test_ollama_real_report_probes.py::test_real_report_probe_dataset_covers_all_target_metrics -v
```

Expected: FAIL because the current probe set does not yet cover all seven target metrics with realistic annual-report labels.

- [ ] **Step 3: Expand the dataset with real-report style labels**

Add realistic positive and negative cases to `REAL_REPORT_ROW_LABEL_PROBE_CASES`, keeping the existing dataclass shape:

```python
OllamaRowLabelProbeCase(
    market="HK",
    report_family="annual",
    table_kind="cash_flow_statement",
    title_text="Consolidated Statement of Cash Flows",
    raw_label="Net cash generated from operating activities",
    local_context="Cash flow statement annual rows",
    expected_label="operating_cash_flow",
)
```

Also add at least:

- one `cash` case
- one `total_assets` case
- one `total_liabilities` case
- one `operating_cash_flow` case
- one additional negative control from a ratio/margin family

- [ ] **Step 4: Run the dataset coverage test again**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/integration/test_ollama_real_report_probes.py::test_real_report_probe_dataset_covers_all_target_metrics -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add F:\source\git\report-collector\financial-report-analysis\tests\integration\fixtures\ollama_real_report_probes.py F:\source\git\report-collector\financial-report-analysis\tests\integration\test_ollama_real_report_probes.py
git commit -m "test: expand ollama real-report probe coverage"
```

### Task 2: Add A Gated Evaluation Summary Test

**Files:**
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_ollama_real_report_probes.py`

- [ ] **Step 1: Write the failing evaluation summary test**

Add a gated test that checks positive and negative hit counts explicitly:

```python
def test_real_report_probe_evaluation_reports_positive_and_negative_hit_rates() -> None:
    results = run_real_probe_evaluation()
    assert results.positive_total >= 7
    assert results.negative_total >= 4
    assert results.positive_hits >= 5
    assert results.negative_hits >= 3
```

- [ ] **Step 2: Run the failing test with real Ollama enabled**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
$env:FRA_RUN_OLLAMA_REAL_REPORT_PROBES='1'
uv run pytest tests/integration/test_ollama_real_report_probes.py::test_real_report_probe_evaluation_reports_positive_and_negative_hit_rates -v
```

Expected: FAIL because the summary helper does not exist yet.

- [ ] **Step 3: Add a small evaluation helper and assertions**

Refactor the probe test file to include a helper and typed summary object, for example:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ProbeEvaluationSummary:
    positive_total: int
    positive_hits: int
    negative_total: int
    negative_hits: int


def run_real_probe_evaluation() -> ProbeEvaluationSummary:
    ...
```

Keep the existing gated behavior (`FRA_RUN_OLLAMA_REAL_REPORT_PROBES=1`) unchanged.

- [ ] **Step 4: Run the gated evaluation tests**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
$env:FRA_RUN_OLLAMA_REAL_REPORT_PROBES='1'
uv run pytest tests/integration/test_ollama_real_report_probes.py -v
```

Expected: PASS, with both dataset coverage and hit-rate assertions green on the supported local model.

- [ ] **Step 5: Commit**

```powershell
git add F:\source\git\report-collector\financial-report-analysis\tests\integration\test_ollama_real_report_probes.py
git commit -m "test: add ollama probe evaluation summary"
```

### Task 3: Promote Stable Cases Into Always-On Regressions

**Files:**
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_ollama_smoke.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\fixtures\ollama_real_report_probes.py`

- [ ] **Step 1: Write the failing promotion-set regression test**

Add a test that draws only from a small promoted subset:

```python
def test_local_ollama_promoted_real_report_cases() -> None:
    promoted = promoted_probe_cases()
    assert promoted
    for case in promoted:
        result = resolve_row_label_with_real_ollama(case)
        assert result.normalized_label == case.expected_label
```

- [ ] **Step 2: Run the failing promotion test**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/integration/test_ollama_smoke.py::test_local_ollama_promoted_real_report_cases -v
```

Expected: FAIL because the promoted subset is not defined yet.

- [ ] **Step 3: Add a small promotion subset**

Expose a promoted subset in the fixture file, for example:

```python
PROMOTED_REAL_REPORT_PROBE_CASES = [
    ...,
]
```

Choose:

- 2-4 stable positive cases
- 1-2 stable negative controls

Only use cases that already proved stable in the gated evaluation.

- [ ] **Step 4: Run the always-on smoke and promotion regressions**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/integration/test_ollama_smoke.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add F:\source\git\report-collector\financial-report-analysis\tests\integration\test_ollama_smoke.py F:\source\git\report-collector\financial-report-analysis\tests\integration\fixtures\ollama_real_report_probes.py
git commit -m "test: promote stable ollama real-report cases"
```

### Task 4: Verify The Promotion Layer Before Returning To Task 6

**Files:**
- Verify only

- [ ] **Step 1: Run the always-on regression layer**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/integration/test_ollama_smoke.py tests/integration/test_analysis_api.py::test_extract_endpoint_uses_real_ollama_fallback_for_ambiguous_table_smoke -v
```

Expected: PASS

- [ ] **Step 2: Run the gated evaluation layer**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
$env:FRA_RUN_OLLAMA_REAL_REPORT_PROBES='1'
uv run pytest tests/integration/test_ollama_real_report_probes.py -v
```

Expected: PASS

- [ ] **Step 3: Run Ruff on touched files**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run ruff check tests/integration/test_ollama_smoke.py tests/integration/test_ollama_real_report_probes.py tests/integration/fixtures/ollama_real_report_probes.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Record exit status for returning to the previous Task 6**

Confirm in notes or final handoff:

```text
Seven target metrics are represented in the evaluation set.
Promoted real-report cases are passing in always-on regression tests.
Gated real-report evaluation passes on the supported local Ollama model.
Task 6 can resume with smoke plus promotion coverage in place.
```

- [ ] **Step 5: Commit**

```powershell
git commit --allow-empty -m "chore: verify ollama probe promotion readiness"
```
