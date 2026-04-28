# Post-P5 Profit Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic post-P5 profit enhancement coverage for SG&A direct-combined rows, fair-value change gain/loss, non-operating income, and non-operating expenses.

**Architecture:** Extend the existing statement-row pipeline rather than adding a new extraction path. New fields enter through table semantics, metric mapping, standard governance metadata, canonical facts, and then flow unchanged into P5 dataset and Turtle export.

**Tech Stack:** Python 3, pytest, Ruff, Pydantic/FastAPI schemas already present, `financial_report_analysis` table semantics, metric registry, fact pipeline, P5 dataset/Turtle modules.

---

## File Structure

- Modify `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`: add direct-row aliases for four profit enhancement metrics and keep broad labels unnormalized.
- Modify `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`: add four `MetricMappingDefinition` entries scoped to income statement duration rows.
- Modify `financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py`: add the same four metrics to the standard metric list so governance metadata is `standard`.
- Modify `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`: add positive and negative registry tests.
- Modify `financial-report-analysis/tests/unit/test_table_semantics.py`: add normalization and negative-control tests.
- Modify `financial-report-analysis/tests/unit/test_fact_pipeline.py`: add canonical promotion and standard-governance tests.
- Modify `financial-report-analysis/tests/unit/test_p5_dataset.py`: add downstream dataset guardrail coverage for the new metrics.
- Modify `financial-report-analysis/tests/unit/test_p5_turtle_export.py`: add Turtle export passthrough coverage for the new metrics.
- Modify `docs/architecture-analysis/2026-04-22-turtle-v015-financial-field-gap-analysis.md`: update profit-enhancement status after implementation.
- Modify `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md`: record the stage as the current active focused slice after implementation starts.

---

### Task 1: Metric Mapping Registry Coverage

**Files:**
- Modify: `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`

- [ ] **Step 1: Write failing registry tests**

Append these tests to `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`:

```python
@pytest.mark.parametrize(
    ("metric_id", "market", "label"),
    [
        (
            "selling_general_administrative",
            "HK",
            "selling, general and administrative expenses",
        ),
        (
            "selling_general_administrative",
            "HK",
            "selling and distribution expenses and administrative expenses",
        ),
        ("selling_general_administrative", "CN", "销售及行政开支"),
        ("fv_value_chg_gain", "CN", "公允价值变动收益"),
        ("fv_value_chg_gain", "HK", "fair value gains and losses"),
        ("non_oper_income", "CN", "营业外收入"),
        ("non_oper_income", "HK", "non-operating income"),
        ("non_oper_exp", "CN", "营业外支出"),
        ("non_oper_exp", "HK", "non-operating expenses"),
    ],
)
def test_metric_mapping_registry_matches_post_p5_profit_enhancement_fields(
    metric_id: str,
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="income_statement",
        normalized_row_label=label,
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is not None
    assert definition.metric_id == metric_id
    assert definition.statement_type == "income_statement"
    assert definition.period_scope == "duration"


@pytest.mark.parametrize(
    ("label", "market"),
    [
        ("selling expenses", "HK"),
        ("administrative expenses", "HK"),
        ("销售费用", "CN"),
        ("管理费用", "CN"),
        ("other income", "HK"),
        ("other gains and losses", "HK"),
        ("other expenses", "HK"),
    ],
)
def test_metric_mapping_registry_rejects_broad_profit_enhancement_false_positives(
    label: str,
    market: str,
) -> None:
    registry = load_metric_registry()

    assert (
        registry.match(
            table_kind="income_statement",
            normalized_row_label=label,
            value_time_shape="duration",
            statement_scope_guess="consolidated",
            market=market,
        )
        is None
    )


def test_metric_mapping_registry_rejects_fair_value_profit_metric_outside_income_statement() -> None:
    registry = load_metric_registry()

    assert (
        registry.match(
            table_kind="balance_sheet",
            normalized_row_label="fair value gains and losses",
            value_time_shape="point_in_time",
            statement_scope_guess="consolidated",
            market="HK",
        )
        is None
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/test_metric_mapping_registry.py -q
```

Expected: the new positive cases fail because the four target metric definitions do not exist.

- [ ] **Step 3: Add metric mapping definitions**

In `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`, add these definitions after the existing `gross_profit` definition:

```python
    MetricMappingDefinition(
        metric_id="selling_general_administrative",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=(
            "selling, general and administrative expenses",
            "selling general and administrative expenses",
            "selling and administrative expenses",
            "selling and distribution expenses and administrative expenses",
            "销售及行政开支",
            "销售及分销开支及行政开支",
        ),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("销售及行政开支", "销售及分销开支及行政开支"),
            "HK": (
                "selling, general and administrative expenses",
                "selling general and administrative expenses",
                "selling and administrative expenses",
                "selling and distribution expenses and administrative expenses",
            ),
        },
    ),
    MetricMappingDefinition(
        metric_id="fv_value_chg_gain",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=(
            "fair value change gain",
            "fair value changes",
            "fair value gains and losses",
            "net fair value gains on financial assets",
            "fair value changes of financial instruments",
            "公允价值变动收益",
        ),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("公允价值变动收益",),
            "HK": (
                "fair value change gain",
                "fair value changes",
                "fair value gains and losses",
                "net fair value gains on financial assets",
                "fair value changes of financial instruments",
            ),
        },
    ),
    MetricMappingDefinition(
        metric_id="non_oper_income",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=("non-operating income", "营业外收入"),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("营业外收入",),
            "HK": ("non-operating income",),
        },
    ),
    MetricMappingDefinition(
        metric_id="non_oper_exp",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=("non-operating expenses", "non-operating expense", "营业外支出"),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("营业外支出",),
            "HK": ("non-operating expenses", "non-operating expense"),
        },
    ),
```

- [ ] **Step 4: Run registry tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/test_metric_mapping_registry.py -q
```

Expected: all tests in `test_metric_mapping_registry.py` pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py financial-report-analysis/tests/unit/test_metric_mapping_registry.py
git commit -m "feat: add post-p5 profit metric mappings"
```

---

### Task 2: Table Semantics Normalization And Negative Controls

**Files:**
- Modify: `financial-report-analysis/tests/unit/test_table_semantics.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`

- [ ] **Step 1: Write failing table semantics tests**

Append these tests to `financial-report-analysis/tests/unit/test_table_semantics.py`:

```python
def test_normalize_table_semantics_maps_post_p5_profit_enhancement_rows() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:profit-enhancement",
            document_id="doc",
            page_range=(18, 18),
            table_kind="income_statement",
            title_text="Consolidated Statement of Profit or Loss",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-sga",
                    row_index=1,
                    label_raw="Selling, general and administrative expenses",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-fv",
                    row_index=2,
                    label_raw="Fair value gains and losses",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-non-oper-income",
                    row_index=3,
                    label_raw="营业外收入",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-non-oper-exp",
                    row_index=4,
                    label_raw="营业外支出",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        "selling, general and administrative expenses",
        "fair value gains and losses",
        "non-operating income",
        "non-operating expenses",
    ]


def test_normalize_table_semantics_keeps_profit_enhancement_false_positives_unmapped() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:profit-enhancement-negative",
            document_id="doc",
            page_range=(19, 19),
            table_kind="income_statement",
            title_text="Consolidated Statement of Profit or Loss",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-selling",
                    row_index=1,
                    label_raw="Selling expenses",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-admin",
                    row_index=2,
                    label_raw="Administrative expenses",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-other-income",
                    row_index=3,
                    label_raw="Other income",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        "selling expenses",
        "administrative expenses",
        "other income",
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/test_table_semantics.py::test_normalize_table_semantics_maps_post_p5_profit_enhancement_rows tests/unit/test_table_semantics.py::test_normalize_table_semantics_keeps_profit_enhancement_false_positives_unmapped -q
```

Expected: the positive test fails because aliases are not normalized to the intended labels.

- [ ] **Step 3: Add semantics aliases**

In `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`, add these entries to `_ROW_LABEL_ALIASES`:

```python
    "selling, general and administrative expenses": "selling, general and administrative expenses",
    "selling general and administrative expenses": "selling, general and administrative expenses",
    "selling and administrative expenses": "selling and administrative expenses",
    "selling and distribution expenses and administrative expenses": "selling and distribution expenses and administrative expenses",
    "销售及行政开支": "销售及行政开支",
    "销售及分销开支及行政开支": "销售及分销开支及行政开支",
    "fair value change gain": "fair value change gain",
    "fair value changes": "fair value changes",
    "fair value gains and losses": "fair value gains and losses",
    "net fair value gains on financial assets": "net fair value gains on financial assets",
    "fair value changes of financial instruments": "fair value changes of financial instruments",
    "公允价值变动收益": "公允价值变动收益",
    "non-operating income": "non-operating income",
    "营业外收入": "non-operating income",
    "non-operating expenses": "non-operating expenses",
    "non-operating expense": "non-operating expenses",
    "营业外支出": "non-operating expenses",
```

Do not add aliases for standalone `selling expenses`, `administrative expenses`, `销售费用`, `管理费用`, `other income`, `other expenses`, or `other gains and losses`.

- [ ] **Step 4: Run table semantics tests**

Run:

```bash
uv run pytest tests/unit/test_table_semantics.py -q
```

Expected: all table semantics tests pass, including existing `gross_profit` summary-row suppression.

- [ ] **Step 5: Commit Task 2**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py financial-report-analysis/tests/unit/test_table_semantics.py
git commit -m "feat: normalize post-p5 profit labels"
```

---

### Task 3: Canonical Promotion And Standard Governance

**Files:**
- Modify: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py`

- [ ] **Step 1: Write failing pipeline test**

Append this test to `financial-report-analysis/tests/unit/test_fact_pipeline.py` near the existing `gross_profit` pipeline tests:

```python
def test_analyze_report_promotes_post_p5_profit_enhancement_to_canonical_facts() -> None:
    candidate_facts = build_table_candidate_facts(
        [
            NormalizedTableSemantics(
                table_id="table-income-profit-enhancement",
                document_id="doc-1",
                page_range=(1, 1),
                table_kind="income_statement",
                title_text="Consolidated Income Statement",
                statement_scope_guess="consolidated",
                table_unit="thousand",
                table_currency="HKD",
                unit_semantic_source="deterministic",
                currency_semantic_source="deterministic",
                columns=[
                    NormalizedTableColumn(
                        column_id="column-1",
                        header_text="2025",
                        period_id="2025FY",
                        comparison_axis="current",
                        value_time_shape="duration",
                        is_current=True,
                        is_comparison=False,
                    )
                ],
                rows=[
                    NormalizedTableRow(
                        row_id="row-sga",
                        row_index=1,
                        label_raw="Selling, general and administrative expenses",
                        normalized_row_label="selling, general and administrative expenses",
                        values=[
                            NormalizedTableCellValue(
                                row_index=1,
                                column_index=1,
                                raw_text="-120",
                                numeric_value=-120.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                    NormalizedTableRow(
                        row_id="row-fv",
                        row_index=2,
                        label_raw="Fair value gains and losses",
                        normalized_row_label="fair value gains and losses",
                        values=[
                            NormalizedTableCellValue(
                                row_index=2,
                                column_index=1,
                                raw_text="18",
                                numeric_value=18.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                    NormalizedTableRow(
                        row_id="row-non-oper-income",
                        row_index=3,
                        label_raw="Non-operating income",
                        normalized_row_label="non-operating income",
                        values=[
                            NormalizedTableCellValue(
                                row_index=3,
                                column_index=1,
                                raw_text="6",
                                numeric_value=6.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                    NormalizedTableRow(
                        row_id="row-non-oper-exp",
                        row_index=4,
                        label_raw="Non-operating expenses",
                        normalized_row_label="non-operating expenses",
                        values=[
                            NormalizedTableCellValue(
                                row_index=4,
                                column_index=1,
                                raw_text="-3",
                                numeric_value=-3.0,
                                period_id="2025FY",
                                comparison_axis="current",
                                value_time_shape="duration",
                            )
                        ],
                    ),
                ],
            )
        ],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    result = analyze_report(
        {"document_id": "doc-1", "market": "HK", "language": "en"},
        {"candidate_facts": candidate_facts},
    )

    canonical_by_metric = {fact.metric_id: fact for fact in result.canonical_facts}
    assert set(canonical_by_metric) >= {
        "selling_general_administrative",
        "fv_value_chg_gain",
        "non_oper_income",
        "non_oper_exp",
    }
    for metric_id in (
        "selling_general_administrative",
        "fv_value_chg_gain",
        "non_oper_income",
        "non_oper_exp",
    ):
        metadata = canonical_by_metric[metric_id].extensions["metric_governance"]
        assert metadata["registry_status"] == "standard"
        assert metadata["auto_analysis_allowed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/test_fact_pipeline.py::test_analyze_report_promotes_post_p5_profit_enhancement_to_canonical_facts -q
```

Expected: test fails until the new metric ids are registered as standard metrics in the normalizer.

- [ ] **Step 3: Add standard metric labels**

In `financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py`, add these entries to `_DEFAULT_STANDARD_METRICS`:

```python
    "selling_general_administrative": [
        "Selling, general and administrative expenses",
        "Selling general and administrative expenses",
        "Selling and administrative expenses",
        "Selling and distribution expenses and administrative expenses",
        "销售及行政开支",
        "销售及分销开支及行政开支",
    ],
    "fv_value_chg_gain": [
        "Fair value change gain",
        "Fair value changes",
        "Fair value gains and losses",
        "Net fair value gains on financial assets",
        "Fair value changes of financial instruments",
        "公允价值变动收益",
    ],
    "non_oper_income": [
        "Non-operating income",
        "营业外收入",
    ],
    "non_oper_exp": [
        "Non-operating expenses",
        "Non-operating expense",
        "营业外支出",
    ],
```

- [ ] **Step 4: Run pipeline and governance-related tests**

Run:

```bash
uv run pytest tests/unit/test_fact_pipeline.py tests/unit/test_metric_governance.py tests/unit/test_report_adapter.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py financial-report-analysis/tests/unit/test_fact_pipeline.py
git commit -m "feat: promote post-p5 profit facts as standard metrics"
```

---

### Task 4: P5 Dataset And Turtle Export Coverage

**Files:**
- Modify: `financial-report-analysis/tests/unit/test_p5_dataset.py`
- Modify: `financial-report-analysis/tests/unit/test_p5_turtle_export.py`

- [ ] **Step 1: Write P5 dataset test**

Append this test to `financial-report-analysis/tests/unit/test_p5_dataset.py`:

```python
def test_assemble_dataset_includes_post_p5_profit_enhancement_rows(
    tmp_path: Path,
) -> None:
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(
            {
                "fact_id": "fact-sga",
                "metric_id": "selling_general_administrative",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": -120.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-sga",
                "extensions": _standard_extensions("duration"),
            },
            {
                "fact_id": "fact-fv",
                "metric_id": "fv_value_chg_gain",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 18.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-fv",
                "extensions": _standard_extensions("duration"),
            },
            {
                "fact_id": "fact-non-oper-income",
                "metric_id": "non_oper_income",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 6.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-non-oper-income",
                "extensions": _standard_extensions("duration"),
            },
            {
                "fact_id": "fact-non-oper-exp",
                "metric_id": "non_oper_exp",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": -3.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-non-oper-exp",
                "extensions": _standard_extensions("duration"),
            },
        ),
    )

    dataset = assemble_dataset(
        dataset_id="profit_enhancement",
        artifacts=(artifact,),
        now_func=lambda: "2026-04-28T00:00:00+00:00",
    )

    present = {row.metric_id: row for row in dataset.rows if row.missing_status == "present"}
    assert set(present) >= {
        "selling_general_administrative",
        "fv_value_chg_gain",
        "non_oper_income",
        "non_oper_exp",
    }
    assert present["selling_general_administrative"].value == -120.0
    assert present["fv_value_chg_gain"].statement_type == "income_statement"
```

- [ ] **Step 2: Write Turtle export test**

Append this test to `financial-report-analysis/tests/unit/test_p5_turtle_export.py`:

```python
def test_build_turtle_export_passes_through_post_p5_profit_fields() -> None:
    dataset = P5DatasetArtifact(
        dataset_id="profit_enhancement",
        dataset_version="1.0",
        created_at="2026-04-28T00:00:00",
        issuer_count=1,
        periods=(2025,),
        metrics=(
            "selling_general_administrative",
            "fv_value_chg_gain",
            "non_oper_income",
            "non_oper_exp",
        ),
        rows=(
            P5DatasetRow(
                issuer_id="HK_09987",
                market="HK",
                stock_code="09987",
                fiscal_year=2025,
                metric_id="selling_general_administrative",
                entity_scope="consolidated",
                period_scope="duration",
                statement_type="income_statement",
                value=-120.0,
                currency="HKD",
                unit="HKD",
                quality_status="ok",
                missing_status="present",
                source_fact_id="fact-sga",
                source_artifact_id="HK_09987_2025",
                evidence_bundle_id="bundle-sga",
            ),
            P5DatasetRow(
                issuer_id="HK_09987",
                market="HK",
                stock_code="09987",
                fiscal_year=2025,
                metric_id="fv_value_chg_gain",
                entity_scope="consolidated",
                period_scope="duration",
                statement_type="income_statement",
                value=18.0,
                currency="HKD",
                unit="HKD",
                quality_status="ok",
                missing_status="present",
                source_fact_id="fact-fv",
                source_artifact_id="HK_09987_2025",
                evidence_bundle_id="bundle-fv",
            ),
        ),
        quality_summary={},
        source_artifacts=("HK_09987_2025",),
    )

    export = build_turtle_export(dataset)

    rows = {row["canonical_metric_id"]: row for row in export.rows}
    assert rows["selling_general_administrative"]["turtle_field"] == "selling_general_administrative"
    assert rows["fv_value_chg_gain"]["turtle_field"] == "fv_value_chg_gain"
```

- [ ] **Step 3: Run tests to verify current behavior**

Run:

```bash
uv run pytest tests/unit/test_p5_dataset.py tests/unit/test_p5_turtle_export.py -q
```

Expected: tests pass. The dataset test uses `_standard_extensions("duration")`, so production governance policy remains unchanged.

- [ ] **Step 4: Commit Task 4**

```bash
git add financial-report-analysis/tests/unit/test_p5_dataset.py financial-report-analysis/tests/unit/test_p5_turtle_export.py
git commit -m "test: cover post-p5 profit dataset export"
```

---

### Task 5: Documentation And Verification Closeout

**Files:**
- Modify: `docs/architecture-analysis/2026-04-22-turtle-v015-financial-field-gap-analysis.md`
- Modify: `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md`
- Move: `docs/superpowers/specs/active/2026-04-28-financial-report-analysis-post-p5-profit-enhancement-design.md` to `docs/superpowers/specs/archived/2026-04-28-financial-report-analysis-post-p5-profit-enhancement-design.md`
- Move: `docs/superpowers/plans/active/2026-04-28-financial-report-analysis-post-p5-profit-enhancement.md` to `docs/superpowers/plans/archived/2026-04-28-financial-report-analysis-post-p5-profit-enhancement.md`
- Modify: `docs/superpowers/specs/README.md`
- Modify: `docs/superpowers/specs/active/README.md`
- Modify: `docs/superpowers/plans/README.md`
- Modify: `docs/superpowers/plans/active/README.md`

- [ ] **Step 1: Update Turtle gap status**

In `docs/architecture-analysis/2026-04-22-turtle-v015-financial-field-gap-analysis.md`, update section `0. 2026-04-28 状态更新` after implementation to say:

```markdown
- 利润增强最小切片已完成：`selling_general_administrative` direct-combined rows、`fv_value_chg_gain`、`non_oper_income`、`non_oper_exp` 已进入 deterministic statement-row coverage；`gross_profit` 继续作为既有基线回归保护。CN 单独 `销售费用` / `管理费用` 求和仍保持 future scope。
```

- [ ] **Step 2: Update architecture roadmap**

In `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md`, update “建议的后续切片” after implementation to mark the profit slice complete and move the next recommendation to either asset/liability enhancement or HTTP-triggered recompute/job boundary if product workflow requirements appear.

- [ ] **Step 3: Run targeted tests**

Run:

```bash
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py tests/unit/test_fact_pipeline.py tests/unit/test_p5_dataset.py tests/unit/test_p5_turtle_export.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run integration smoke tests**

Run:

```bash
uv run pytest tests/integration/test_analysis_api.py tests/integration/test_semantic_recovery_regressions.py -q
```

Expected: all selected integration tests pass. If this is slow, keep the full command output and report runtime.

- [ ] **Step 5: Run lint and diff checks**

Run:

```bash
uv run ruff check src/financial_report_analysis/ingestion/table_semantics.py src/financial_report_analysis/registries/metric_mapping.py src/financial_report_analysis/services/fact_normalizer.py tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py tests/unit/test_fact_pipeline.py tests/unit/test_p5_dataset.py tests/unit/test_p5_turtle_export.py
git diff --check
```

Expected: Ruff reports `All checks passed!`; `git diff --check` exits with no output.

- [ ] **Step 6: Archive completed spec and plan**

Run:

```bash
git mv docs/superpowers/specs/active/2026-04-28-financial-report-analysis-post-p5-profit-enhancement-design.md docs/superpowers/specs/archived/2026-04-28-financial-report-analysis-post-p5-profit-enhancement-design.md
git mv docs/superpowers/plans/active/2026-04-28-financial-report-analysis-post-p5-profit-enhancement.md docs/superpowers/plans/archived/2026-04-28-financial-report-analysis-post-p5-profit-enhancement.md
```

Update `docs/superpowers/specs/README.md` so current active entries no longer include the profit enhancement spec and archived entries include:

```markdown
- `archived/2026-04-28-financial-report-analysis-post-p5-profit-enhancement-design.md`
```

Update `docs/superpowers/specs/active/README.md` so current active specs no longer include the profit enhancement spec and the `Current focused implementation stage` section is removed.

Update `docs/superpowers/plans/README.md` so current active implementation plans are:

```markdown
- None.
```

Update `docs/superpowers/plans/active/README.md` to:

```markdown
# Active Plans

There are no active implementation plans after the 2026-04-28 post-P5 profit
enhancement closeout.
```

- [ ] **Step 7: Commit Task 5**

```bash
git add docs/architecture-analysis/2026-04-22-turtle-v015-financial-field-gap-analysis.md docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md docs/superpowers/specs/README.md docs/superpowers/specs/active/README.md docs/superpowers/specs/archived/2026-04-28-financial-report-analysis-post-p5-profit-enhancement-design.md docs/superpowers/plans/README.md docs/superpowers/plans/active/README.md docs/superpowers/plans/archived/2026-04-28-financial-report-analysis-post-p5-profit-enhancement.md
git commit -m "docs: close post-p5 profit enhancement plan"
```

---

## Self-Review

- Spec coverage: Tasks 1-3 cover deterministic mapping, normalization, standard governance, and canonical promotion. Task 4 covers P5/Turtle downstream consumption. Task 5 covers documentation and verification.
- Scope control: The plan does not add HTTP recompute/job infrastructure, DB-native executor, whole-document LLM assessment, or note/text bridge fields.
- Negative controls: SG&A component rows, broad `other income`, and non-income-statement fair-value rows are explicitly rejected.
- Type consistency: Metric ids are consistently `selling_general_administrative`, `fv_value_chg_gain`, `non_oper_income`, and `non_oper_exp`.
