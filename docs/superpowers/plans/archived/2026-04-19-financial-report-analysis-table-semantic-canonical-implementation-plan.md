# Financial Report Analysis Table Semantic Canonical Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stable table-semantic extraction path inside `financial_report_analysis` that turns seven high-value metrics from real CN/HK samples into reliable canonical facts.

**Architecture:** Keep the existing parsed-table pipeline, but harden it so table output carries stable structural semantics (`statement_scope_guess`, conservative continuation, stable row/value bindings). Add a normalized table-semantics layer, a minimal Python-backed metric mapping registry, and a table fact builder that feeds the existing normalization/resolution pipeline without changing the `report` boundary.

**Tech Stack:** Python 3.12, dataclasses, pytest, Ruff, `pypdf`, existing `financial_report_analysis` models/services/pipeline.

---

## File Structure

### Existing files to modify

- `financial-report-analysis/src/financial_report_analysis/models/table.py`
  - Extend parsed-table models with statement-scope and continuation metadata.
- `financial-report-analysis/src/financial_report_analysis/models/__init__.py`
  - Export new table semantic models.
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
  - Emit stable title, local unit/currency, `statement_scope_guess`, and conservative continuation metadata.
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_stitcher.py`
  - Preserve “prefer-separate-when-uncertain” continuation behavior and confidence metadata.
- `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
  - Replace direct revenue-only table reading with normalized-table-semantics + table fact builder flow.
- `financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py`
  - Export semantic normalizer entry points.
- `financial-report-analysis/src/financial_report_analysis/registries/__init__.py`
  - Export the metric mapping registry loader.
- `financial-report-analysis/src/financial_report_analysis/services/__init__.py`
  - Export the table fact builder.
- `financial-report-analysis/src/financial_report_analysis/__init__.py`
  - Export newly public table-structure entry points only if intended for package-root consumption.
- `financial-report-analysis/tests/unit/test_table_models.py`
  - Lock new parsed-table model fields and naming.
- `financial-report-analysis/tests/unit/test_table_structure.py`
  - Lock `statement_scope_guess`, title stability, and local metadata behavior.
- `financial-report-analysis/tests/unit/test_table_stitcher.py`
  - Lock conservative continuation behavior.
- `financial-report-analysis/tests/unit/test_fact_pipeline.py`
  - Lock canonical output compatibility after table-driven candidate generation.
- `financial-report-analysis/tests/integration/test_analysis_api.py`
  - Lock real-sample canonical outputs and `document.metadata.parsed_tables` compatibility.

### New files to create

- `financial-report-analysis/src/financial_report_analysis/models/table_semantics.py`
  - Strongly typed normalized table semantic models.
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
  - Convert `ParsedTable` into normalized table semantics.
- `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
  - Strongly typed minimal metric mapping registry and loader.
- `financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py`
  - Build candidate facts from normalized table semantics + metric mapping registry.
- `financial-report-analysis/tests/unit/test_table_semantics.py`
  - Unit tests for semantic normalization.
- `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
  - Unit tests for metric mapping registry matching and false-positive rejection.
- `financial-report-analysis/tests/unit/test_table_fact_builder.py`
  - Unit tests for candidate-fact construction and period semantics.
- `financial-report-analysis/tests/integration/test_table_semantic_canonical_samples.py`
  - Real-sample canonical regression tests for CN annual, HK annual, and HK `09987` Q3.
- `financial-report-analysis/tests/unit/test_public_exports.py`
  - Import/export regression for the new public API surface.

---

### Task 1: Harden Parsed Table Model Contracts

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/models/table_semantics.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/models/table.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/models/__init__.py`
- Test: `financial-report-analysis/tests/unit/test_table_models.py`
- Test: `financial-report-analysis/tests/unit/test_public_exports.py`

- [ ] **Step 1: Write the failing model tests**

```python
from financial_report_analysis.models import ParsedColumn, ParsedTable


def test_parsed_table_exposes_statement_scope_and_continuation_metadata() -> None:
    table = ParsedTable(
        table_id="t-1",
        document_id="doc-1",
        page_range=(3, 4),
        table_kind="income_statement",
        title_text="Consolidated Statement of Profit or Loss",
        statement_scope_guess="consolidated",
        continuation_confidence=0.8,
        continued_from_table_id="t-0",
    )

    assert table.statement_scope_guess == "consolidated"
    assert table.continued_from_table_id == "t-0"
    assert table.continuation_confidence == 0.8


def test_parsed_column_uses_value_time_shape_not_period_scope() -> None:
    column = ParsedColumn(
        column_id="c-1",
        column_index=1,
        header_text="2025Q3",
        period_id="2025Q3_YTD",
        value_time_shape="duration",
        comparison_axis="current",
    )

    assert column.value_time_shape == "duration"
    assert not hasattr(column, "period_scope")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_models.py -v`

Expected: FAIL with errors like `TypeError: ParsedTable.__init__() got an unexpected keyword argument 'statement_scope_guess'` and missing `value_time_shape`.

- [ ] **Step 3: Write the minimal model implementation and exports**

```python
@dataclass(kw_only=True)
class ParsedColumn:
    column_id: str
    column_index: int
    header_text: str
    period_id: str | None
    value_time_shape: str | None
    comparison_axis: str | None
    is_current: bool = False
    is_comparison: bool = False


@dataclass(kw_only=True)
class ParsedTable:
    table_id: str
    document_id: str
    page_range: tuple[int, int]
    table_kind: str
    title_text: str
    statement_scope_guess: str = "unknown"
    continued_from_table_id: str | None = None
    continuation_confidence: float | None = None
    header_rows: list[list[str]] = field(default_factory=list)
    body_rows: list[ParsedRow] = field(default_factory=list)
    table_unit: str | None = None
    table_currency: str | None = None
    period_columns: list[ParsedColumn] = field(default_factory=list)
    comparison_columns: list[ParsedColumn] = field(default_factory=list)
    source_blocks: list[PageTextBlock] = field(default_factory=list)
```

```python
from financial_report_analysis.models.table_semantics import (
    NormalizedTableCellValue,
    NormalizedTableColumn,
    NormalizedTableRow,
    NormalizedTableSemantics,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_models.py tests/unit/test_public_exports.py -v`

Expected: PASS for the new model-field assertions and import/export assertions.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/models/table.py \
        financial-report-analysis/src/financial_report_analysis/models/table_semantics.py \
        financial-report-analysis/src/financial_report_analysis/models/__init__.py \
        financial-report-analysis/tests/unit/test_table_models.py \
        financial-report-analysis/tests/unit/test_public_exports.py
git commit -m "feat: extend parsed table semantic models"
```

### Task 2: Emit Stable Table Semantics from the Structure Layer

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_stitcher.py`
- Test: `financial-report-analysis/tests/unit/test_table_structure.py`
- Test: `financial-report-analysis/tests/unit/test_table_stitcher.py`

- [ ] **Step 1: Write the failing structure tests**

```python
def test_table_structure_sets_statement_scope_guess_from_title() -> None:
    table = _build_table_from_page(
        title="Consolidated Statement of Financial Position",
        page_text="Consolidated Statement of Financial Position\nUnit: RMB million",
    )

    assert table.statement_scope_guess == "consolidated"


def test_table_stitcher_prefers_separate_tables_when_continuation_is_ambiguous() -> None:
    stitched = stitch_tables([page_one_table, page_two_unrelated_table])

    assert len(stitched) == 2
    assert stitched[1].continued_from_table_id is None
    assert stitched[1].continuation_confidence is not None
    assert stitched[1].continuation_confidence < 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_structure.py tests/unit/test_table_stitcher.py -v`

Expected: FAIL because `statement_scope_guess` is not populated and ambiguous continuation currently merges too aggressively or lacks confidence metadata.

- [ ] **Step 3: Write the minimal structure/stitcher implementation**

```python
def _guess_statement_scope(title_text: str, local_context: str) -> str:
    haystack = f"{title_text}\n{local_context}".casefold()
    if "consolidated" in haystack or "合并" in haystack:
        return "consolidated"
    if "parent company" in haystack or "母公司" in haystack:
        return "parent_only"
    return "unknown"
```

```python
if continuation_match_is_ambiguous:
    next_table.continued_from_table_id = None
    next_table.continuation_confidence = 0.25
    output_tables.append(next_table)
    continue
```

```python
table = ParsedTable(
    ...,
    statement_scope_guess=_guess_statement_scope(title_text, local_context),
    continuation_confidence=continuation_confidence,
    continued_from_table_id=continued_from_table_id,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_structure.py tests/unit/test_table_stitcher.py -v`

Expected: PASS with explicit assertions for statement scope and conservative continuation behavior.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py \
        financial-report-analysis/src/financial_report_analysis/ingestion/table_stitcher.py \
        financial-report-analysis/tests/unit/test_table_structure.py \
        financial-report-analysis/tests/unit/test_table_stitcher.py
git commit -m "feat: add stable statement scope and continuation semantics"
```

### Task 3: Add the Normalized Table Semantics Layer

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
- Create: `financial-report-analysis/src/financial_report_analysis/models/table_semantics.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py`
- Test: `financial-report-analysis/tests/unit/test_table_semantics.py`
- Test: `financial-report-analysis/tests/unit/test_public_exports.py`

- [ ] **Step 1: Write the failing semantic-normalization tests**

```python
def test_normalize_table_semantics_keeps_row_hint_separate_from_metric_mapping() -> None:
    semantics = normalize_table_semantics(parsed_income_statement_table())

    revenue_row = semantics.rows[0]
    assert revenue_row.normalized_row_label == "revenue"
    assert revenue_row.metric_id is None


def test_normalize_table_semantics_emits_period_value_context() -> None:
    semantics = normalize_table_semantics(parsed_q3_table())

    assert semantics.columns[0].value_time_shape == "duration"
    assert semantics.columns[0].comparison_axis == "current"
    assert semantics.columns[0].period_id == "2025Q3_YTD"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_semantics.py -v`

Expected: FAIL with `ImportError` or missing `normalize_table_semantics`.

- [ ] **Step 3: Write the minimal semantic-layer implementation**

```python
@dataclass(frozen=True, slots=True)
class NormalizedTableColumn:
    column_id: str
    period_id: str | None
    comparison_axis: str | None
    value_time_shape: str | None
    is_current: bool
    is_comparison: bool


@dataclass(frozen=True, slots=True)
class NormalizedTableRow:
    row_id: str
    label_raw: str
    normalized_row_label: str | None
    values: list[NormalizedTableCellValue] = field(default_factory=list)
```

```python
def normalize_table_semantics(table: ParsedTable) -> NormalizedTableSemantics:
    return NormalizedTableSemantics(
        table_id=table.table_id,
        table_kind=table.table_kind,
        statement_scope_guess=table.statement_scope_guess,
        table_unit=table.table_unit,
        table_currency=table.table_currency,
        columns=[
            NormalizedTableColumn(
                column_id=column.column_id,
                period_id=column.period_id,
                comparison_axis=column.comparison_axis,
                value_time_shape=column.value_time_shape,
                is_current=column.is_current,
                is_comparison=column.is_comparison,
            )
            for column in table.period_columns
        ],
        rows=[_normalize_row(row) for row in table.body_rows],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_semantics.py tests/unit/test_public_exports.py -v`

Expected: PASS; import/export tests also confirm the new semantics module is intentionally public.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/models/table_semantics.py \
        financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py \
        financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py \
        financial-report-analysis/tests/unit/test_table_semantics.py \
        financial-report-analysis/tests/unit/test_public_exports.py
git commit -m "feat: add normalized table semantics layer"
```

### Task 4: Build the Minimal Metric Mapping Registry

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/__init__.py`
- Test: `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- Test: `financial-report-analysis/tests/unit/test_public_exports.py`

- [ ] **Step 1: Write the failing registry tests**

```python
def test_metric_mapping_registry_matches_revenue_from_income_statement_semantics() -> None:
    registry = load_metric_registry()
    definition = registry.match(
        table_kind="income_statement",
        normalized_row_label="revenue",
        value_time_shape="duration",
        market="CN",
    )

    assert definition.metric_id == "revenue"
    assert definition.statement_type == "income_statement"


def test_metric_mapping_registry_rejects_deferred_revenue_false_positive() -> None:
    registry = load_metric_registry()

    assert registry.match(
        table_kind="balance_sheet",
        normalized_row_label="deferred revenue",
        value_time_shape="point_in_time",
        market="CN",
    ) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_metric_mapping_registry.py -v`

Expected: FAIL with `ImportError` or missing `load_metric_registry`.

- [ ] **Step 3: Write the minimal registry implementation**

```python
@dataclass(frozen=True, slots=True)
class MetricMappingDefinition:
    metric_id: str
    statement_type: str
    allowed_table_kinds: tuple[str, ...]
    normalized_row_labels: tuple[str, ...]
    period_scope: str
    value_type: str
    unit_expectation: str | None
    sign_rule: str
    aliases_by_market: Mapping[str, tuple[str, ...]]
```

```python
def load_metric_registry(source: str | None = None) -> MetricMappingRegistry:
    if source is not None:
        raise NotImplementedError("external registry sources are not implemented yet")
    return MetricMappingRegistry(_DEFAULT_DEFINITIONS)
```

```python
_DEFAULT_DEFINITIONS = (
    MetricMappingDefinition(
        metric_id="revenue",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement", "metrics", "key_metrics"),
        normalized_row_labels=("revenue", "operating revenue"),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("营业收入", "营业总收入"), "HK": ("revenue", "turnover")},
    ),
    ...
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_public_exports.py -v`

Expected: PASS for positive matches and false-positive rejection.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py \
        financial-report-analysis/src/financial_report_analysis/registries/__init__.py \
        financial-report-analysis/tests/unit/test_metric_mapping_registry.py \
        financial-report-analysis/tests/unit/test_public_exports.py
git commit -m "feat: add minimal table metric mapping registry"
```

### Task 5: Build Table Candidate Facts and Wire Them into the Pipeline

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/services/__init__.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/unit_policy.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/pipeline.py`
- Test: `financial-report-analysis/tests/unit/test_table_fact_builder.py`
- Test: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Test: `financial-report-analysis/tests/integration/test_analysis_api.py`

- [ ] **Step 1: Write the failing builder/pipeline tests**

```python
def test_table_fact_builder_emits_candidate_fact_for_hk_q3_revenue() -> None:
    candidates = build_table_candidate_facts(
        [normalized_hk_q3_income_statement()],
        registry=load_metric_registry(),
        document_id="09987-q3",
        market="HK",
    )

    assert candidates[0]["metric_id"] == "revenue"
    assert candidates[0]["period_id"] == "2025Q3_YTD"


def test_analyze_report_promotes_supported_table_metrics_to_canonical_facts() -> None:
    result = analyze_report(
        {"document_id": "doc-1", "market": "CN", "language": "zh-Hans"},
        {"candidate_facts": [cn_revenue_candidate_payload()]},
    )

    assert any(f.metric_id == "revenue" for f in result.canonical_facts)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_fact_builder.py tests/unit/test_fact_pipeline.py -v`

Expected: FAIL because `build_table_candidate_facts` does not exist and the table-driven canonical path is not wired.

- [ ] **Step 3: Write the minimal fact-builder and ingestion integration**

```python
def build_table_candidate_facts(
    semantics_tables: list[NormalizedTableSemantics],
    *,
    registry: MetricMappingRegistry,
    document_id: str,
    market: str,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for table in semantics_tables:
        for row in table.rows:
            for value in row.values:
                definition = registry.match(
                    table_kind=table.table_kind,
                    normalized_row_label=row.normalized_row_label,
                    value_time_shape=value.value_time_shape,
                    market=market,
                )
                if definition is None or value.numeric_value is None:
                    continue
                candidates.append(_build_candidate_payload(...))
    return candidates
```

```python
parsed_tables = self._extract_parsed_tables(...)
semantics_tables = [normalize_table_semantics(table) for table in parsed_tables]
table_candidates = build_table_candidate_facts(
    semantics_tables,
    registry=load_metric_registry(),
    document_id=document_id,
    market=market or "CN",
)
candidate_facts = table_candidates or candidate_facts
```

```python
fact_payload["metric_id"] = definition.metric_id
fact_payload["statement_type"] = definition.statement_type
fact_payload["extensions"]["statement_scope_guess"] = table.statement_scope_guess
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_fact_builder.py tests/unit/test_fact_pipeline.py tests/integration/test_analysis_api.py -v`

Expected: PASS with canonical facts produced from the table-driven path and no regression in API contract.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py \
        financial-report-analysis/src/financial_report_analysis/services/__init__.py \
        financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py \
        financial-report-analysis/src/financial_report_analysis/unit_policy.py \
        financial-report-analysis/src/financial_report_analysis/pipeline.py \
        financial-report-analysis/tests/unit/test_table_fact_builder.py \
        financial-report-analysis/tests/unit/test_fact_pipeline.py \
        financial-report-analysis/tests/integration/test_analysis_api.py
git commit -m "feat: build canonical candidates from table semantics"
```

### Task 6: Lock Real-Sample Canonical Regressions and Public Surface

**Files:**
- Create: `financial-report-analysis/tests/integration/test_table_semantic_canonical_samples.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`
- Modify: `financial-report-analysis/tests/unit/test_public_exports.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/__init__.py`

- [ ] **Step 1: Write the failing real-sample and export regression tests**

```python
CN_ANNUAL = r"F:\source\git\report-collector\report\downloads\cn_stocks\688008\annual\2024_年度报告.pdf"
HK_ANNUAL = r"F:\source\git\report-collector\report\downloads\hk_stocks\02498\annual\2022_annual_en.pdf"
HK_Q3 = r"F:\source\git\report-collector\report\downloads\hk_stocks\09987\quarterly\2025_quarterly_q3_en.pdf"


def test_cn_annual_sample_produces_expected_canonical_metrics() -> None:
    payload = extract_analysis_payload(CN_ANNUAL, market="CN")
    metric_ids = {fact["metric_id"] for fact in payload["key_facts"]}
    assert {"revenue", "total_assets"} <= metric_ids


def test_hk_annual_sample_produces_expected_canonical_metrics() -> None:
    payload = extract_analysis_payload(HK_ANNUAL, market="HK")
    metric_ids = {fact["metric_id"] for fact in payload["key_facts"]}
    assert {"revenue", "net_profit", "cash"} <= metric_ids


def test_hk_q3_sample_preserves_ytd_period_semantics() -> None:
    payload = extract_analysis_payload(HK_Q3, market="HK")
    revenue_fact = next(f for f in payload["key_facts"] if f["metric_id"] == "revenue")
    assert revenue_fact["period_id"] == "2025Q3_YTD"
```

```python
def test_public_exports_include_semantic_registry_and_builder() -> None:
    from financial_report_analysis.ingestion import normalize_table_semantics
    from financial_report_analysis.registries import load_metric_registry
    from financial_report_analysis.services import build_table_candidate_facts

    assert callable(normalize_table_semantics)
    assert callable(load_metric_registry)
    assert callable(build_table_candidate_facts)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd financial-report-analysis && uv run pytest tests/integration/test_table_semantic_canonical_samples.py tests/unit/test_public_exports.py -v`

Expected: FAIL until the sample-driven canonical assertions and exports are fully wired.

- [ ] **Step 3: Write the minimal compatibility/export updates**

```python
from financial_report_analysis.ingestion.table_semantics import normalize_table_semantics
from financial_report_analysis.registries.metric_mapping import load_metric_registry
from financial_report_analysis.services.table_fact_builder import build_table_candidate_facts

__all__ = [
    "PdfIngestionAdapter",
    "PdfTableStructureAdapter",
    "classify_table_kind",
    "normalize_table_semantics",
    "normalize_table_title",
]
```

```python
__all__ = [
    "CandidateFact",
    "CanonicalFact",
    "PdfTableStructureAdapter",
    "PipelineResult",
    "analyze_report",
]
```

- [ ] **Step 4: Run the full verification matrix**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_models.py tests/unit/test_table_structure.py tests/unit/test_table_stitcher.py tests/unit/test_table_semantics.py tests/unit/test_metric_mapping_registry.py tests/unit/test_table_fact_builder.py tests/unit/test_fact_pipeline.py tests/unit/test_public_exports.py tests/integration/test_table_structure_ingestion.py tests/integration/test_analysis_api.py tests/integration/test_table_semantic_canonical_samples.py -v
uv run ruff check src/financial_report_analysis/models/table.py src/financial_report_analysis/models/table_semantics.py src/financial_report_analysis/ingestion/table_structure.py src/financial_report_analysis/ingestion/table_semantics.py src/financial_report_analysis/ingestion/pdf_ingestion.py src/financial_report_analysis/registries/metric_mapping.py src/financial_report_analysis/services/table_fact_builder.py tests/unit/test_public_exports.py tests/integration/test_table_semantic_canonical_samples.py
```

Expected: all selected tests PASS and `ruff check` reports `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py \
        financial-report-analysis/src/financial_report_analysis/__init__.py \
        financial-report-analysis/tests/unit/test_public_exports.py \
        financial-report-analysis/tests/integration/test_table_semantic_canonical_samples.py \
        financial-report-analysis/tests/integration/test_analysis_api.py
git commit -m "test: lock sample canonical regressions and public exports"
```

## Self-Review

### Spec coverage

- Table-structure hardening: covered by Task 1 and Task 2.
- Normalized table semantics: covered by Task 3.
- Minimal metric mapping registry: covered by Task 4.
- Seven-metric canonical closed loop: covered by Task 5.
- Real-sample anchors (`CN annual`, `HK annual`, `HK 09987 Q3`): covered by Task 6.
- Stable public surface/import regression: covered by Task 1, Task 3, Task 4, and Task 6.
- Time semantics and period/publication distinction: covered by Task 3, Task 4, and Task 5 tests around `period_id` and `value_time_shape`.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every task includes an explicit failing test, exact command, concrete implementation snippet, verification command, and commit step.

### Type consistency

- `value_time_shape` is used consistently instead of the older ambiguous `period_scope`.
- `statement_scope_guess` is introduced at the parsed-table layer and preserved into semantics/fact building.
- The registry API is consistently named `load_metric_registry`, `match`, and `MetricMappingDefinition`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-19-financial-report-analysis-table-semantic-canonical-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
