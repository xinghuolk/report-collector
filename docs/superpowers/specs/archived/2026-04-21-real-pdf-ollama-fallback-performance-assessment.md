# Real PDF Ollama Fallback Performance Assessment

## Context

During Phase 2 real-PDF validation, the `financial-report-analysis/scripts/run-real-pdf-matrix.sh`
matrix became impractically slow once local Ollama fallback was available again.

The script itself is functional under Git Bash and collects 43 `real_pdf` pytest nodes.
The slowdown appears to come from excessive semantic fallback calls on some real PDFs,
not from Git Bash or Ollama connectivity.

## Confirmed Observations

### Ollama Connectivity

Local Ollama is reachable at:

```text
http://127.0.0.1:11434
```

The configured model is:

```text
qwen3.5:9b
```

Ollama server logs show successful requests:

```text
GET  /api/tags     -> 200
POST /api/generate -> 200
```

Typical generation latency observed in the server logs was around 2.0-2.5 seconds per call.

### HK 09987 Q3 Probe

For:

```text
report/downloads/hk_stocks/09987/quarterly/2025_quarterly_q3_en.pdf
```

Observed fallback call counts:

```text
table_kind: 0
row_label: 124
currency: 0
unit: 0
```

Output shape:

```text
candidate_facts: 13
parsed_tables: 3
```

Interpretation:

- The PDF does not fail structurally.
- Candidate facts are still produced.
- However, row-label fallback is triggered too frequently for a single PDF.
- At roughly 2 seconds per Ollama generation, 124 calls alone can add several minutes.

### CN 601919 2024 Annual Probe

For:

```text
report/downloads/cn_stocks/601919/annual/2024_年度报告.pdf
```

A counting probe with Ollama enabled was interrupted after roughly 6 minutes without returning.

Interpretation:

- This sample is likely heavier than HK 09987 Q3.
- The cause may be a combination of PDF parsing cost and excessive row-label fallback calls.
- The exact fallback count is still unknown because the probe did not complete.

### Post-Fix Timing Probe

After tightening row-label fallback gating and adding concurrency controls, a focused timing probe
was run with live Ollama enabled.

Environment:

```text
base_url: http://127.0.0.1:11434
model: qwen3.5:9b
FRA_SEMANTIC_FALLBACK_MAX_CONCURRENCY: 1 unless noted
```

Pure promoted real-report row-label probe:

```text
calls: 12
total_seconds: 7.96
average_seconds: 0.66
median_seconds: 0.67
min_seconds: 0.58
max_seconds: 0.75
accuracy: 12/12
```

Real PDF path for:

```text
report/downloads/hk_stocks/09987/quarterly/2025_quarterly_q3_en.pdf
```

Observed with live Ollama fallback:

```text
total_seconds: 20.72
ollama_seconds: 8.11
non_ollama_estimate_seconds: 12.61
candidate_facts: 4
fallback_calls: table_kind=3, row_label=12, currency=0, unit=0
```

Interpretation:

- Ollama accounted for roughly 39% of this real-PDF run.
- PDF/table extraction plus deterministic pipeline work accounted for roughly 61%.
- The expensive live fallback path was row-label fallback.
- Table-kind fallback was counted but contributed negligible measured latency in this probe.

Pure Ollama concurrency probe with:

```text
FRA_SEMANTIC_FALLBACK_MAX_CONCURRENCY=2
```

For 8 promoted row-label requests submitted concurrently:

```text
wall_seconds: 4.03
accuracy: 8/8
```

Interpretation:

- `max_concurrency=2` can improve wall-clock time on this local setup.
- The improvement is not linear, likely due to local Ollama/model resource contention.
- The default should remain `1`; `2` is useful for local profiling or explicitly opted-in runs.

## Current Diagnosis

The original issue was likely not Git Bash, pytest collection, or Ollama connectivity.

The original root cause was:

```text
row-label fallback gating is too broad.
```

In practice, many rows that are either clearly non-target rows or unsupported metrics appear to
reach the LLM fallback path. This makes fallback behave less like a limited ambiguity resolver and
more like a broad row-label classifier over large table bodies.

This conflicts with the intended Phase 2 boundary:

- deterministic extraction and normalization should run first;
- LLM fallback should only run for selected ambiguous cases;
- fallback should not become the default interpretation path for every unmatched row.

After the gating fix, the remaining performance picture is split:

- Ollama row-label fallback remains material but bounded.
- PDF/table recovery and deterministic ingestion are also a major part of wall-clock time.
- Future performance work should profile `table_source/pdfplumber`, table-structure recovery,
  candidate building, and live Ollama fallback separately rather than treating the whole API call
  as one opaque timeout.

## Risk

If left unchanged:

- the 43-node real-PDF matrix may take an impractically long time;
- local validation becomes hard to run regularly;
- developers may interrupt tests before useful results are available;
- Ollama fallback becomes a performance bottleneck instead of a targeted semantic aid;
- model variability affects more rows than necessary.

## Recommended Next Steps

### 1. Measure Deterministic Baseline

Run selected heavy samples with semantic fallback disabled.

Goal:

- determine how much time is spent in PDF/table parsing alone;
- separate extraction cost from LLM fallback cost.

Suggested samples:

- `cn_stocks/601919/annual/2024_年度报告.pdf`
- `hk_stocks/09987/quarterly/2025_quarterly_q3_en.pdf`

### 2. Add Fallback Call Instrumentation

Add temporary or test-only counters for:

- `table_kind`
- `row_label`
- `currency`
- `unit`

Goal:

- report per-PDF fallback call counts;
- identify which table/row families trigger excessive fallback.

### 3. Tighten Row-Label Fallback Gating

Before calling Ollama for a row label, apply deterministic prefilters.

Rows should not call fallback when they are clearly non-target examples such as:

- growth rows;
- margin rows;
- ratio rows;
- EPS rows;
- store count / restaurant count rows;
- segment-only rows;
- deferred revenue / contract liability rows.

Rows should be eligible for fallback only when they have plausible anchors for the target metrics:

- revenue / turnover / sales;
- operating profit / operating income;
- net profit / profit attributable;
- operating cash flow;
- cash and cash equivalents;
- total assets;
- total liabilities.

### 4. Add a Per-Document Fallback Budget

Consider a defensive cap for local fallback calls per PDF or per table.

Example:

```text
max_row_label_fallback_calls_per_document = 20
```

This should be treated as a safety valve, not the primary fix.

### 5. Re-run Real PDF Matrix After Gating Fix

Only after gating is tightened:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' -lc 'cd /f/source/git/report-collector/financial-report-analysis && scripts/run-real-pdf-matrix.sh 2>&1 | tee real-pdf-matrix.log'
```

Expected improvement:

- HK 09987 Q3 should trigger far fewer than 124 row-label fallback calls.
- CN 601919 2024 annual should return within a practical time budget.

## Non-Goals

This note does not propose removing Ollama fallback.

The desired direction remains:

- deterministic extraction first;
- gated semantic fallback only for ambiguity;
- provenance-preserving fallback output;
- no LLM-based canonical resolution;
- no LLM direct fact generation.

