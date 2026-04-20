# 财报分析利润表核心指标与资产负债表基线实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Related Spec:** `docs/superpowers/specs/2026-04-20-financial-report-analysis-income-statement-core-metrics-with-balance-sheet-baseline-design.md`

**Goal:** 在当前已完成的表格结构恢复、语义归一化、gated fallback 与 candidate/canonical/API 合约稳定的基础上，把 `financial-report-analysis` 从“少量高价值指标可穿透”推进到“利润表核心链路可用”，同时对资产负债表做一层轻量基线补强。

**Architecture:** 本轮工作分为两个并行但主次明确的工作流。**Phase A** 以利润表为主线，扩展 deterministic semantic normalization、metric mapping registry、candidate fact building 与 canonical promotion，使收入、成本、营业利润、净利润形成一条稳定主链路。**Phase B** 以资产负债表为轻量并行基线，只强化 `cash`、`total_assets`、`total_liabilities` 三个低歧义高价值指标，不引入更复杂的权益口径治理。

**Tech Stack:** Python 3.12、dataclasses、pytest、Ruff、现有 `financial_report_analysis` ingestion / semantic / registry / pipeline 架构、真实 CN/HK 年报与 HK Q3 回归样本。

---

## 文件结构

### 需要修改的现有文件

- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\registries\metric_mapping.py`
  - 扩展利润表核心指标与资产负债表基线指标的 registry coverage、label families、market aliases。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_semantics.py`
  - 加强 deterministic row-label normalization，使 registry 能消费更多真实利润表 / 资产负债表标签。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\pdf_ingestion.py`
  - 继续强化 summary table / growth table / ratio table 的干扰抑制，并确保 table-driven facts 优先来自主表。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\table_fact_builder.py`
  - 确保新增指标的 statement type、semantic provenance、source rank 与 evidence path 保持稳定。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\fact_normalizer.py`
  - 仅在必要时补充 legacy normalizer 的标准 metric 别名，避免 table-driven path 与 Phase-1 fallback path 漂移。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\conflict_resolver.py`
  - 如有需要，校准新增指标在 canonical promotion 中的稳定排序，但不改变当前总体冲突裁决模型。

### 需要扩展的测试文件

- `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_semantics.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_fact_pipeline.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_metric_registry.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_semantic_recovery_regressions.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_analysis_api.py`

---

## 范围与边界

### 本轮纳入范围

**利润表主线指标**

- `revenue`
- `operating_cost`
- `operating_profit`
- `net_profit`

**资产负债表轻量基线指标**

- `cash`
- `total_assets`
- `total_liabilities`

### 本轮明确不做

- `gross_profit`
- `gross_margin`
- `adjusted_net_profit`
- `equity attributable to owners`
- `book value`
- `period semantics fallback`
- `unit propagation strategy`
- `currency propagation strategy`
- 以 `Ollama` 为主链路的指标扩展

---

## Phase A：利润表核心指标主线

**Phase A 收口标准**

- 利润表核心指标在 CN/HK 主样本与 reference set 上能够通过 table-driven path 稳定产生 candidate facts。
- `revenue`、`operating_cost`、`operating_profit`、`net_profit` 中至少前三项在 anchor 样本上能够稳定进入 `canonical_facts` / `key_facts`。
- 不因为新增 aliases 而误吸 summary table、增长率表、比率表或非主表披露。
- candidate / canonical / API contract 保持不变。

### Task A1：扩展利润表 registry coverage 与 label families

**Files:**
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_metric_registry.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_fact_pipeline.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\registries\metric_mapping.py`

- [ ] **Step 1: 先写失败测试，锁定利润表核心指标与 market aliases**

```python
def test_metric_mapping_registry_matches_operating_cost_for_cn_income_statement() -> None:
    definition = load_metric_registry().match(
        table_kind="income_statement",
        normalized_row_label="营业成本",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="CN",
    )

    assert definition is not None
    assert definition.metric_id == "operating_cost"


def test_metric_mapping_registry_matches_net_profit_for_hk_income_statement() -> None:
    definition = load_metric_registry().match(
        table_kind="income_statement",
        normalized_row_label="profit attributable to equity holders",
        value_time_shape="duration",
        statement_scope_guess="consolidated",
        market="HK",
    )

    assert definition is not None
    assert definition.metric_id == "net_profit"
```

- [ ] **Step 2: 运行测试，确认先红**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_metric_registry.py tests/unit/test_fact_pipeline.py -v
```

Expected: FAIL，说明 registry 仍未覆盖利润表核心指标。

- [ ] **Step 3: 写最小实现，只扩 coverage，不改整体 registry 模型**

至少补齐：

- `operating_cost`
- `operating_profit`
- `net_profit`

建议 label families：

- CN:
  - `营业成本`
  - `营业利润`
  - `净利润`
- HK:
  - `cost of sales`
  - `cost of revenue`
  - `profit from operations`
  - `profit for the period`
  - `profit attributable to shareholders`
  - `profit attributable to equity holders`

- [ ] **Step 4: 再跑测试，确认转绿**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_metric_registry.py tests/unit/test_fact_pipeline.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```powershell
git add F:\source\git\report-collector\financial-report-analysis\tests\unit\test_metric_registry.py F:\source\git\report-collector\financial-report-analysis\tests\unit\test_fact_pipeline.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\registries\metric_mapping.py
git commit -m "feat: extend income statement metric registry coverage"
```

### Task A2：强化利润表 deterministic normalization 与主表优先级

**Files:**
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_semantics.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_semantic_recovery_regressions.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_analysis_api.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_semantics.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\pdf_ingestion.py`

- [ ] **Step 1: 先写失败测试，锁定真实利润表标签归一与主表抑噪**

```python
def test_normalize_table_semantics_maps_operating_cost_variants() -> None:
    semantics = normalize_table_semantics(parsed_income_statement_with_cost_of_sales())
    assert any(row.normalized_row_label == "operating cost" for row in semantics.rows)


def test_extract_endpoint_does_not_promote_growth_ratio_rows_as_profit_metrics() -> None:
    payload = client.post(...).json()
    assert all(
        fact["metric_id"] != "operating_profit"
        for fact in payload["candidate_facts"]
        if "growth" in fact["metric_label_raw"].lower()
    )
```

- [ ] **Step 2: 运行测试，确认先红**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_table_semantics.py tests/integration/test_analysis_api.py tests/integration/test_semantic_recovery_regressions.py -v
```

Expected: FAIL，说明 row-label normalization 与主表抑噪仍不够稳。

- [ ] **Step 3: 写最小实现，只补 deterministic normalization 与 table gating**

建议方向：

- 利润表标签归一增加：
  - `cost of sales` -> `operating cost`
  - `cost of revenue` -> `operating cost`
  - `profit attributable to equity holders` -> `net profit`
- 对增长率 / 利润率 / 摘要指标维持 `none`
- 保持主表优先，不让 `key_metrics` 抢占利润表核心项

- [ ] **Step 4: 再跑测试，确认转绿**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_table_semantics.py tests/integration/test_analysis_api.py tests/integration/test_semantic_recovery_regressions.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```powershell
git add F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_semantics.py F:\source\git\report-collector\financial-report-analysis\tests\integration\test_analysis_api.py F:\source\git\report-collector\financial-report-analysis\tests\integration\test_semantic_recovery_regressions.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_semantics.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\pdf_ingestion.py
git commit -m "feat: harden income statement semantic normalization"
```

### Task A3：验证利润表 candidate -> canonical -> key_facts 主链路

**Files:**
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_fact_pipeline.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_analysis_api.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\table_fact_builder.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\fact_normalizer.py`

- [ ] **Step 1: 先写失败测试，锁定利润表核心指标能进入 canonical/key facts**

```python
def test_table_candidate_facts_include_operating_cost_and_net_profit() -> None:
    candidate_facts = build_table_candidate_facts(...)
    assert {fact["metric_id"] for fact in candidate_facts} >= {
        "revenue",
        "operating_cost",
        "operating_profit",
        "net_profit",
    }


def test_extract_endpoint_promotes_income_statement_core_metrics_to_key_facts() -> None:
    payload = client.post(...).json()
    assert any(fact["metric_id"] == "operating_cost" for fact in payload["key_facts"])
    assert any(fact["metric_id"] == "net_profit" for fact in payload["key_facts"])
```

- [ ] **Step 2: 运行测试，确认先红**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py tests/integration/test_analysis_api.py -v
```

Expected: FAIL，说明新增指标尚未稳定穿透到 canonical / API。

- [ ] **Step 3: 写最小实现，保持现有 pipeline contract**

注意：

- 不改 `PipelineResult` 与 API response schema
- 只补 candidate 生成、normalizer alias 对齐与 canonical promotion 稳定性
- 如需排序调整，仅做最小 source-rank 校准

- [ ] **Step 4: 再跑测试，确认转绿**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py tests/integration/test_analysis_api.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```powershell
git add F:\source\git\report-collector\financial-report-analysis\tests\unit\test_fact_pipeline.py F:\source\git\report-collector\financial-report-analysis\tests\integration\test_analysis_api.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\table_fact_builder.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\fact_normalizer.py
git commit -m "feat: promote income statement core metrics through pipeline"
```

---

## Phase B：资产负债表轻量并行基线

**Phase B 收口标准**

- `cash`、`total_assets`、`total_liabilities` 三个指标在 CN/HK 主样本与 reference set 上保持稳定。
- 时点值语义保持稳定，不被 `duration` 表误匹配。
- 不把母公司表、摘要表或权益明细误吸成核心资产负债表指标。

### Task B1：补强资产负债表 registry aliases 与 deterministic gating

**Files:**
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_metric_registry.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_semantic_recovery_regressions.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\registries\metric_mapping.py`

- [ ] **Step 1: 先写失败测试，锁定资产负债表基线指标的 CN/HK aliases**

```python
def test_metric_mapping_registry_matches_total_assets_cn_aliases() -> None:
    definition = load_metric_registry().match(...)
    assert definition is not None
    assert definition.metric_id == "total_assets"


def test_metric_mapping_registry_matches_cash_hk_aliases() -> None:
    definition = load_metric_registry().match(...)
    assert definition is not None
    assert definition.metric_id == "cash"
```

- [ ] **Step 2: 运行测试，确认先红**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_metric_registry.py tests/integration/test_semantic_recovery_regressions.py -v
```

Expected: FAIL，说明资产负债表 aliases 与 gating 仍有缺口。

- [ ] **Step 3: 写最小实现，只补 aliases 与 point-in-time 稳定性**

建议 focus：

- CN:
  - `货币资金`
  - `资产总计`
  - `负债合计`
- HK:
  - `cash and cash equivalents`
  - `total assets`
  - `total liabilities`

- [ ] **Step 4: 再跑测试，确认转绿**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_metric_registry.py tests/integration/test_semantic_recovery_regressions.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```powershell
git add F:\source\git\report-collector\financial-report-analysis\tests\unit\test_metric_registry.py F:\source\git\report-collector\financial-report-analysis\tests\integration\test_semantic_recovery_regressions.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\registries\metric_mapping.py
git commit -m "feat: strengthen balance sheet baseline metric coverage"
```

---

## 完整验证矩阵

- [ ] **Step 1: 跑利润表与资产负债表 unit tests**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_metric_registry.py tests/unit/test_table_semantics.py tests/unit/test_fact_pipeline.py -v
```

Expected: PASS

- [ ] **Step 2: 跑真实样本 integration**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/integration/test_analysis_api.py tests/integration/test_semantic_recovery_regressions.py tests/integration/test_annual_structure_recovery.py -v
```

Expected: PASS

- [ ] **Step 3: 跑 Ruff**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run ruff check src tests
```

Expected: PASS

- [ ] **Step 4: 最终提交**

```powershell
git add F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\registries\metric_mapping.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_semantics.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\pdf_ingestion.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\table_fact_builder.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\fact_normalizer.py F:\source\git\report-collector\financial-report-analysis\tests\unit\test_metric_registry.py F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_semantics.py F:\source\git\report-collector\financial-report-analysis\tests\unit\test_fact_pipeline.py F:\source\git\report-collector\financial-report-analysis\tests\integration\test_analysis_api.py F:\source\git\report-collector\financial-report-analysis\tests\integration\test_semantic_recovery_regressions.py F:\source\git\report-collector\financial-report-analysis\tests\integration\test_annual_structure_recovery.py
git commit -m "feat: extend income statement core metrics with balance sheet baseline"
```

---

## 交付完成定义

当以下条件同时满足时，本计划可视为收口：

- 利润表主线四个核心指标具备稳定 table-driven candidate path。
- 资产负债表三项基线指标在 selected sample set 上稳定。
- `canonical_facts` 与 `key_facts` 的 contract 未发生破坏性变化。
- 新增 coverage 没有明显扩大 summary/growth/ratio table 的误匹配。
- Ruff 与真实样本 integration 回归通过。

---

## 下一步衔接

本计划完成后，再决定是否进入以下任一方向：

1. 利润表第二批指标：
   - `gross_profit`
   - `adjusted_net_profit`
2. 资产负债表第二批指标：
   - `equity`
   - `equity_attributable_to_owners`
3. 现金流量表扩展：
   - `investing_cash_flow`
   - `financing_cash_flow`

默认建议：优先继续完成利润表第二批指标，再考虑更复杂的权益口径治理。
