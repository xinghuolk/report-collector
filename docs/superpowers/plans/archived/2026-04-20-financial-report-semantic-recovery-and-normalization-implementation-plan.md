# Financial Report Semantic Recovery and Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable semantic-recovery path for CN/HK financial reports that first restores usable annual-report structure and normalized semantics, then upgrades semantic mapping and gated Ollama fallback without breaking the current candidate/canonical contract.

**Architecture:** Execute this work in two phases. **Phase A** stabilizes annual-report structure recovery and normalized table semantics for CN/HK anchors. **Phase B** builds on that stable substrate to upgrade registry mapping, table fact building, and a tightly gated Ollama fallback used only for `table kind` and `row label` ambiguity, with provenance preserved end-to-end.

**Tech Stack:** Python 3.12, dataclasses, pytest, Ruff, `pypdf`, local Ollama HTTP API, existing `financial_report_analysis` models/ingestion/pipeline stack.

---

## File Structure

### Existing files to modify

- `financial-report-analysis/src/financial_report_analysis/ingestion/table_source.py`
  - Improve raw table block recovery so annual core statements retain usable row-label and header structure.
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
  - Preserve richer structure metadata and emit ambiguity markers instead of silent collapse.
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py`
  - Strengthen multi-row header handling and preserve explicit ambiguity.
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
  - Extend normalized semantics with ambiguity/provenance-ready fields.
- `financial-report-analysis/src/financial_report_analysis/models/table.py`
  - Add lightweight ambiguity/provenance fields needed for structure recovery handoff.
- `financial-report-analysis/src/financial_report_analysis/models/table_semantics.py`
  - Add typed semantic ambiguity/provenance fields.
- `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
  - Upgrade from alias-like matching to semantic mapping entry points.
- `financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py`
  - Consume richer semantics and preserve semantic provenance into candidate facts.
- `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
  - Wire recovered semantics and, later, gated fallback into the existing analysis path.
- `financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py`
  - Export intentional semantic-recovery and fallback entry points.
- `financial-report-analysis/src/financial_report_analysis/__init__.py`
  - Only widen package-root exports if the final surface is intentionally public.

### New files to create

- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py`
  - Shared fallback request/response/provenance models.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/client.py`
  - Provider-agnostic semantic fallback client protocol.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/ollama_client.py`
  - Local Ollama implementation for the first fallback phase.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py`
  - Gated fallback orchestration for `table kind` and `row label`.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/__init__.py`
  - Export intentionally public fallback APIs.
- `financial-report-analysis/tests/integration/test_annual_structure_recovery.py`
  - Real-sample annual structure smoke regressions for CN/HK primary anchors.
- `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`
  - Target-level regressions for normalized semantics, semantic provenance, and key-fact path stability.
- `financial-report-analysis/tests/unit/test_semantic_fallback_models.py`
  - Lock request/response/provenance schema.
- `financial-report-analysis/tests/unit/test_semantic_fallback_service.py`
  - Lock gating behavior and restricted output sets.
- `financial-report-analysis/tests/unit/test_ollama_client.py`
  - Lock Ollama prompt/response parsing through mocked HTTP calls.

### Existing tests to extend

- `financial-report-analysis/tests/unit/test_table_source.py`
- `financial-report-analysis/tests/unit/test_table_structure.py`
- `financial-report-analysis/tests/unit/test_table_header_parser.py`
- `financial-report-analysis/tests/unit/test_table_semantics.py`
- `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- `financial-report-analysis/tests/unit/test_table_fact_builder.py`
- `financial-report-analysis/tests/unit/test_public_exports.py`
- `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- `financial-report-analysis/tests/integration/test_analysis_api.py`
- `financial-report-analysis/tests/integration/test_table_structure_ingestion.py`

---

## Phase A: Structure and Semantic Recovery

**Exit criteria for Phase A**

- CN annual and HK annual primary anchors expose usable recovered structure for the three core statements.
- Recovered output no longer fails primarily because row labels and header structure collapse upstream.
- Normalized table semantics become stable enough to support later registry matching without issuer-specific branches.
- No requirement yet that the target metrics must already complete the canonical closed loop.

### Task A1: Add Annual Sample Characterization and Smoke Regressions

**Files:**
- Create: `financial-report-analysis/tests/integration/test_annual_structure_recovery.py`
- Modify: `financial-report-analysis/tests/integration/test_table_structure_ingestion.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`

- [ ] **Step 1: Write the failing smoke-level annual recovery tests**

```python
CN_ANNUAL = r"F:\source\git\report-collector\report\downloads\cn_stocks\601919\annual\2024_年度报告.pdf"
HK_02498_ANNUAL = r"F:\source\git\report-collector\report\downloads\hk_stocks\02498\annual\2022_annual_en.pdf"


def test_hk_annual_anchor_exposes_non_empty_statement_rows() -> None:
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=HK_02498_ANNUAL,
        pdf_url=None,
        market="HK",
    )

    income_tables = [table for table in tables if table.table_kind == "income_statement"]
    assert income_tables
    assert any(table.body_rows for table in income_tables)
    assert any(any(row.label_raw.strip() for row in table.body_rows) for table in income_tables)


def test_cn_annual_anchor_exposes_non_empty_period_columns() -> None:
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=CN_ANNUAL,
        pdf_url=None,
        market="CN",
    )

    assert any(table.period_columns for table in tables)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_annual_structure_recovery.py tests/integration/test_table_structure_ingestion.py -v
```

Expected: FAIL on at least one HK annual anchor because the current structure recovery collapses row labels and/or period columns.

- [ ] **Step 3: Add stable sample helpers and smoke-only scaffolding**

```python
def _resolve_cn_primary_anchor() -> Path:
    return REPO_ROOT / "report" / "downloads" / "cn_stocks" / "601919" / "annual" / "2024_年度报告.pdf"


def _resolve_hk_annual_anchors() -> list[Path]:
    return [
        REPO_ROOT / "report" / "downloads" / "hk_stocks" / "02498" / "annual" / "2022_annual_en.pdf",
        REPO_ROOT / "report" / "downloads" / "hk_stocks" / "06862" / "annual" / "2024_annual_en.pdf",
        REPO_ROOT / "report" / "downloads" / "hk_stocks" / "09987" / "annual" / "2024_annual_en.pdf",
    ]
```

- [ ] **Step 4: Run tests to confirm the intended red state is stable**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_annual_structure_recovery.py -v
```

Expected: deterministic failure on capability gaps, not fixture-resolution noise.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/tests/integration/test_annual_structure_recovery.py \
        financial-report-analysis/tests/integration/test_table_structure_ingestion.py \
        financial-report-analysis/tests/integration/test_analysis_api.py
git commit -m "test: add annual structure recovery smoke regressions"
```

### Task A2: Recover HK/CN Annual Statement Structure

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_source.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_stitcher.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/models/table.py`
- Test: `financial-report-analysis/tests/unit/test_table_source.py`
- Test: `financial-report-analysis/tests/unit/test_table_structure.py`
- Test: `financial-report-analysis/tests/unit/test_table_stitcher.py`
- Test: `financial-report-analysis/tests/integration/test_annual_structure_recovery.py`

- [ ] **Step 1: Write the failing annual-structure unit tests**

```python
def test_normalize_rows_preserves_sparse_annual_header_and_row_labels() -> None:
    rows = _normalize_rows([
        ["Item", "", "2024", "", "2023"],
        ["Revenue", "", "1,234", "", "1,111"],
    ])

    assert rows[0] == ["Item", "", "2024", "", "2023"]
    assert rows[1][0] == "Revenue"


def test_build_parsed_table_marks_semantic_ambiguity_when_headers_are_weak() -> None:
    table = adapter._build_parsed_table(
        block=weak_hk_annual_block,
        market="HK",
        document_id="doc",
        table_index=1,
    )

    assert table is not None
    assert table.semantic_ambiguity_reason is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_source.py tests/unit/test_table_structure.py tests/unit/test_table_stitcher.py tests/integration/test_annual_structure_recovery.py -v
```

Expected: FAIL because annual-report structure currently degrades before semantic normalization.

- [ ] **Step 3: Write the minimal structure-recovery implementation**

```python
@dataclass(kw_only=True)
class ParsedTable:
    ...
    semantic_ambiguity_reason: str | None = None
```

```python
def _normalize_rows(rows: list[list[str | None]]) -> list[list[str]]:
    normalized: list[list[str]] = []
    for row in rows:
        cleaned = [cell if cell is not None else "" for cell in row]
        if any(str(cell).strip() for cell in cleaned):
            normalized.append([str(cell).strip() for cell in cleaned])
    return normalized
```

```python
if _looks_like_numeric_only_statement_block(block.rows):
    recovered_rows = _recover_row_labels_from_local_context(block.rows, block.page_text)
    ambiguity_reason = "numeric_only_statement_block"
else:
    recovered_rows = block.rows
    ambiguity_reason = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_source.py tests/unit/test_table_structure.py tests/unit/test_table_stitcher.py tests/integration/test_annual_structure_recovery.py -v
```

Expected: PASS with annual anchors exposing usable row labels or explicit ambiguity markers instead of silent collapse.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/table_source.py \
        financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py \
        financial-report-analysis/src/financial_report_analysis/ingestion/table_stitcher.py \
        financial-report-analysis/src/financial_report_analysis/models/table.py \
        financial-report-analysis/tests/unit/test_table_source.py \
        financial-report-analysis/tests/unit/test_table_structure.py \
        financial-report-analysis/tests/unit/test_table_stitcher.py \
        financial-report-analysis/tests/integration/test_annual_structure_recovery.py
git commit -m "feat: recover annual statement structure"
```

### Task A3: Harden Semantic Normalization for Annual Reports

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/models/table_semantics.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py`
- Test: `financial-report-analysis/tests/unit/test_table_semantics.py`
- Test: `financial-report-analysis/tests/unit/test_table_header_parser.py`
- Create: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

- [ ] **Step 1: Write the failing semantic-normalization tests**

```python
def test_normalized_table_semantics_preserve_statement_scope_and_ambiguity() -> None:
    semantics = normalize_table_semantics(parsed_annual_balance_sheet())

    assert semantics.statement_scope_guess == "consolidated"
    assert semantics.semantic_ambiguity_reason in {None, "weak_header_hierarchy"}


def test_cn_annual_row_label_normalization_strips_numbering_prefixes() -> None:
    semantics = normalize_table_semantics(parsed_cn_annual_income_statement())

    labels = {row.normalized_row_label for row in semantics.rows}
    assert "revenue" in labels or "operating_revenue" in labels
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_semantics.py tests/unit/test_table_header_parser.py tests/integration/test_semantic_recovery_regressions.py -v
```

Expected: FAIL because current semantics are too thin to preserve annual ambiguity/provenance and CN numbering cleanup.

- [ ] **Step 3: Write the minimal semantic-normalization implementation**

```python
@dataclass(frozen=True, slots=True)
class NormalizedTableSemantics:
    ...
    semantic_source: str = "deterministic"
    semantic_confidence: float | None = None
    semantic_ambiguity_reason: str | None = None
```

```python
def _normalize_label(raw_label: str) -> str | None:
    normalized = re.sub(r"^[一二三四五六七八九十\\d、\\.\\(\\)（）]+", "", raw_label)
    normalized = re.sub(r"\\s+", " ", normalized).strip().casefold()
    return normalized or None
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_semantics.py tests/unit/test_table_header_parser.py tests/integration/test_semantic_recovery_regressions.py -v
```

Expected: PASS with stronger annual semantics and preserved ambiguity metadata.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/models/table_semantics.py \
        financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py \
        financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py \
        financial-report-analysis/tests/unit/test_table_semantics.py \
        financial-report-analysis/tests/unit/test_table_header_parser.py \
        financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py
git commit -m "feat: harden annual semantic normalization"
```

---

## Phase B: Semantic Mapping, Controlled Fallback, and Business Closure

**Exit criteria for Phase B**

- The registry operates as a semantic mapping entry point, not a flat alias-only table.
- Table fact building preserves semantic provenance into candidate facts.
- Gated Ollama fallback exists only for `table kind` and `row label` ambiguity.
- Candidate/canonical outputs and API contract remain compatible.
- Only after the above is true do the main target regressions become binding.

### Task B1: Upgrade Registry and Fact Builder to Consume Semantic Recovery Outputs

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/__init__.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/services/__init__.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Test: `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- Test: `financial-report-analysis/tests/unit/test_table_fact_builder.py`
- Test: `financial-report-analysis/tests/unit/test_fact_pipeline.py`

- [ ] **Step 1: Write the failing registry/fact-builder tests**

```python
def test_metric_mapping_registry_prefers_semantic_matches_over_flat_aliases() -> None:
    definition = load_metric_registry().match(
        table_kind="income_statement",
        normalized_row_label="net profit",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert definition is not None
    assert definition.metric_id == "net_profit"


def test_table_fact_builder_preserves_semantic_provenance_into_candidates() -> None:
    candidate = build_table_candidate_facts(...)[0]
    assert candidate["extensions"]["semantic_source"] == "deterministic"
    assert "semantic_confidence" in candidate["extensions"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_fact_builder.py tests/unit/test_fact_pipeline.py -v
```

Expected: FAIL because current registry/fact builder do not consume richer semantic inputs or provenance.

- [ ] **Step 3: Write the minimal registry/fact-builder upgrade**

```python
def match(
    self,
    *,
    table_kind: str,
    normalized_row_label: str | None,
    value_time_shape: str | None,
    statement_scope_guess: str,
    market: str,
) -> MetricMappingDefinition | None:
    ...
```

```python
candidate["extensions"].update(
    {
        "semantic_source": row.semantic_source,
        "semantic_confidence": row.semantic_confidence,
        "fallback_reason": row.fallback_reason,
    }
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_fact_builder.py tests/unit/test_fact_pipeline.py -v
```

Expected: PASS with semantic-aware registry matching and provenance-preserving candidate facts.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py \
        financial-report-analysis/src/financial_report_analysis/registries/__init__.py \
        financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py \
        financial-report-analysis/src/financial_report_analysis/services/__init__.py \
        financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py \
        financial-report-analysis/tests/unit/test_metric_mapping_registry.py \
        financial-report-analysis/tests/unit/test_table_fact_builder.py \
        financial-report-analysis/tests/unit/test_fact_pipeline.py
git commit -m "feat: connect semantic recovery outputs to fact building"
```

### Task B2: Introduce Provider-Abstracted, Gated Ollama Semantic Fallback

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py`
- Create: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/client.py`
- Create: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/ollama_client.py`
- Create: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py`
- Create: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/__init__.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Test: `financial-report-analysis/tests/unit/test_semantic_fallback_models.py`
- Test: `financial-report-analysis/tests/unit/test_ollama_client.py`
- Test: `financial-report-analysis/tests/unit/test_semantic_fallback_service.py`
- Test: `financial-report-analysis/tests/unit/test_public_exports.py`

- [ ] **Step 1: Write the failing fallback model/service tests**

```python
def test_semantic_fallback_service_only_allows_supported_table_kind_outputs() -> None:
    result = service.resolve_table_kind(ambiguous_table_payload())

    assert result.semantic_source == "llm_fallback"
    assert result.value in {
        "income_statement",
        "balance_sheet",
        "cash_flow_statement",
        "key_metrics",
        "unknown",
    }


def test_semantic_fallback_service_does_not_run_without_ambiguity() -> None:
    result = service.resolve_row_label(
        raw_label="Revenue",
        deterministic_candidates=["revenue"],
        ambiguity_reason=None,
    )

    assert result.semantic_source == "deterministic"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_semantic_fallback_models.py tests/unit/test_ollama_client.py tests/unit/test_semantic_fallback_service.py tests/unit/test_public_exports.py -v
```

Expected: FAIL because the fallback abstraction does not exist yet.

- [ ] **Step 3: Write the minimal provider abstraction and Ollama client**

```python
@dataclass(frozen=True, slots=True)
class SemanticFallbackResult:
    value: str
    semantic_source: str
    semantic_confidence: float | None
    fallback_reason: str | None
```

```python
class SemanticFallbackClient(Protocol):
    def classify_table_kind(self, payload: dict[str, str]) -> SemanticFallbackResult: ...
    def normalize_row_label(self, payload: dict[str, str]) -> SemanticFallbackResult: ...
```

```python
class OllamaSemanticFallbackClient:
    def __init__(self, *, base_url: str = "http://localhost:11434", model: str = "qwen3:8b") -> None:
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_semantic_fallback_models.py tests/unit/test_ollama_client.py tests/unit/test_semantic_fallback_service.py tests/unit/test_public_exports.py -v
```

Expected: PASS with constrained outputs, gated behavior, and provenance-preserving results.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/semantic_fallback \
        financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py \
        financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py \
        financial-report-analysis/tests/unit/test_semantic_fallback_models.py \
        financial-report-analysis/tests/unit/test_ollama_client.py \
        financial-report-analysis/tests/unit/test_semantic_fallback_service.py \
        financial-report-analysis/tests/unit/test_public_exports.py
git commit -m "feat: add gated ollama semantic fallback"
```

### Task B3: Re-enable Meaningful Target Regressions

**Files:**
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`
- Modify: `financial-report-analysis/tests/unit/test_public_exports.py`

- [ ] **Step 1: Write the failing target-level recovery regressions**

```python
def test_hk_annual_anchor_surfaces_non_empty_key_fact_path() -> None:
    payload = extract_analysis_payload(HK_02498_ANNUAL, market="HK")
    assert payload["key_facts"]


def test_hk_q3_anchor_preserves_complex_semantics_without_forcing_fallback_everywhere() -> None:
    payload = extract_analysis_payload(HK_09987_Q3, market="HK")
    assert payload["document"]["metadata"]["parsed_tables"]
    assert any(
        table.get("semantic_source") in {"deterministic", "llm_fallback"}
        for table in payload["document"]["metadata"]["parsed_tables"]
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_semantic_recovery_regressions.py tests/integration/test_analysis_api.py -v
```

Expected: FAIL until the semantic-recovery path and gated fallback are fully wired into the service output.

- [ ] **Step 3: Write the minimal compatibility/output updates**

```python
payload["document"]["metadata"]["parsed_tables"] = [
    {
        **table_payload,
        "semantic_source": table_payload.get("semantic_source", "deterministic"),
        "semantic_confidence": table_payload.get("semantic_confidence"),
        "fallback_reason": table_payload.get("fallback_reason"),
    }
    for table_payload in serialized_tables
]
```

- [ ] **Step 4: Run the full verification matrix**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_models.py tests/unit/test_table_source.py tests/unit/test_table_structure.py tests/unit/test_table_stitcher.py tests/unit/test_table_header_parser.py tests/unit/test_table_semantics.py tests/unit/test_metric_mapping_registry.py tests/unit/test_table_fact_builder.py tests/unit/test_semantic_fallback_models.py tests/unit/test_ollama_client.py tests/unit/test_semantic_fallback_service.py tests/unit/test_public_exports.py tests/unit/test_fact_pipeline.py tests/integration/test_annual_structure_recovery.py tests/integration/test_table_structure_ingestion.py tests/integration/test_semantic_recovery_regressions.py tests/integration/test_analysis_api.py -v
uv run ruff check src/financial_report_analysis/ingestion src/financial_report_analysis/models src/financial_report_analysis/registries src/financial_report_analysis/services src/financial_report_analysis/semantic_fallback tests/unit/test_public_exports.py tests/integration/test_annual_structure_recovery.py tests/integration/test_semantic_recovery_regressions.py
```

Expected: all selected tests PASS and Ruff reports `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py \
        financial-report-analysis/tests/integration/test_analysis_api.py \
        financial-report-analysis/tests/unit/test_public_exports.py
git commit -m "test: restore semantic recovery target regressions"
```

## Self-Review

### Spec coverage

- HK annual blocker recovery: covered by Phase A Task A1 and Task A2.
- CN annual as a same-tier target: covered by Phase A Task A1, Task A2, and Task A3.
- Unified architecture instead of issuer-specific branches: reflected in Phase A structure/semantic tasks and Phase B mapping/fallback tasks.
- Registry as a semantic mapping entry point: covered by Phase B Task B1.
- Limited Ollama fallback (`table kind`, `row label` only): covered by Phase B Task B2.
- Provenance (`semantic_source`, `semantic_confidence`, `fallback_reason`): covered by Phase A Task A3 and Phase B Task B2/B3.
- Current candidate/canonical contract preservation: covered by Phase B Task B1 and Task B3.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every task includes explicit failing tests, concrete implementation snippets, exact commands, and commit steps.

### Type consistency

- `value_time_shape` remains the column/value-shape term across the plan.
- `semantic_source`, `semantic_confidence`, and `fallback_reason` are used consistently from semantic normalization through fallback and fact building.
- `load_metric_registry()` remains the registry loader entry point.
- Ollama fallback remains constrained to `table kind` and `row label`, not period/unit/currency semantics.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-20-financial-report-semantic-recovery-and-normalization-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
