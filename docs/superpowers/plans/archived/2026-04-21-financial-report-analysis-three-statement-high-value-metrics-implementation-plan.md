# 财报分析三大表高价值指标实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Related Spec:** `docs/superpowers/specs/2026-04-21-financial-report-analysis-three-statement-high-value-metrics-design.md`
**Child Specs:**
- `docs/superpowers/specs/2026-04-21-financial-report-analysis-income-statement-second-batch-design.md`
- `docs/superpowers/specs/2026-04-21-financial-report-analysis-balance-sheet-equity-layer-design.md`
- `docs/superpowers/specs/2026-04-21-financial-report-analysis-cash-flow-core-completion-design.md`
- `docs/superpowers/specs/2026-04-21-financial-report-analysis-cross-statement-conflict-governance-design.md`

**Goal:** 在当前已完成的利润表核心指标与资产负债表基线能力之上，构建一个可验证、可回归、可继续扩展的三大表高价值指标层，使 `financial-report-analysis` 在三张主表上都具备稳定的 table-driven 主链路。

**Architecture:** 本轮实现采用总纲加 tranche 的方式推进，而不是三张表完全并行硬推。Tranche A 先完成利润表第二批指标，Tranche B 再进入资产负债表权益层，Tranche C 完成现金流量表三大主项闭环，Tranche D 负责把前面 tranche 中出现的局部 ranking/gating 修补统一归纳成稳定的跨表冲突治理规则，并完成总回归收口。

**Tech Stack:** Python 3.12、dataclasses、pytest、Ruff、现有 `financial_report_analysis` ingestion / semantic / registry / pipeline 架构、真实 CN/HK 年报与季度样本。

---

## 范围与边界

### 本轮纳入范围

- 利润表：
  - `gross_profit`
- 资产负债表：
  - `equity`
  - `equity_attributable_to_owners`
- 现金流量表：
  - `investing_cash_flow`
  - `financing_cash_flow`

### 本轮可选但非主验收项

- `adjusted_net_profit`

### 本轮明确不做

- 大范围 working capital 细项扩展
- 大范围附注表抽取
- 比率与衍生指标生成
- 以 LLM 直接生成 facts
- period / unit / currency 传播策略重构

### 共享样本矩阵

本计划中的 `主样本`、`reference set`、`目标样本集` 默认统一指向以下矩阵：

- CN annual primary anchor:
  - `601919/annual/2024_年度报告.pdf`
- HK annual anchors:
  - `02498/annual/2022_annual_en.pdf`
  - `06862/annual/2024_annual_en.pdf`
  - `09987/annual/2024_annual_en.pdf`
- HK quarterly supplement:
  - `09987/quarterly/2025_quarterly_q3_en.pdf`
- CN annual references:
  - `600519/annual/2024_年度报告.pdf`
  - `600519/annual/2025_年度报告.pdf`
  - `601919/annual/2025_年度报告.pdf`
  - `688008/annual/2024_年度报告.pdf`
  - `688008/annual/2025_年度报告.pdf`

各 tranche 可以定义不同测试重心，但若无特殊说明，都以这套共享矩阵为验收基线。

### 全程约束

- A/B/C 各 tranche 都允许在本 tranche 内做最小必要的 ranking/gating/provenance 修补，以保证本 tranche 的 candidate/canonical/API 收口真实有效。
- Tranche D 负责统一这些局部修补，沉淀成更稳定的跨表冲突治理规则，而不是第一次引入冲突治理。
- 各 tranche 的“已收口”以通过本 tranche 目标与共享样本矩阵为准，但进入 Tranche D 后仍允许做非破坏性的统一校准。

---

## Tranche A：利润表第二批指标

**Tranche A 收口标准**

- `gross_profit` 在 CN/HK 主样本与 reference set 上能稳定产生 candidate facts。
- `gross_profit` 能稳定进入 `canonical_facts` 与 `key_facts`。
- 不把 `gross margin`、摘要表、增长表误吸为 `gross_profit`。

**Representative Label Families**

- CN:
  - `营业毛利`
  - `毛利润`
  - `毛利`
- HK / English:
  - `gross profit`
  - `gross profit for the period`
  - `gross profit attributable to operations`

### Task A1：扩展 gross_profit registry coverage 与 normalization

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
- Modify: `financial-report-analysis/tests/unit/test_metric_registry.py`
- Modify: `financial-report-analysis/tests/unit/test_table_semantics.py`

- [ ] **Step 1: 先写失败测试，锁定 gross_profit 的 CN/HK aliases**
- [ ] **Step 2: 跑 unit tests，确认先红**
- [ ] **Step 3: 写最小实现，只补 registry 与 deterministic normalization**
- [ ] **Step 4: 再跑 tests，确认转绿**

### Task A2：验证利润表 pipeline 穿透

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py`
- Modify: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`

- [ ] **Step 1: 先写失败测试，锁定 gross_profit 能进入 canonical/key facts**
- [ ] **Step 2: 跑 pipeline 与 API tests，确认先红**
- [ ] **Step 3: 写最小实现，保持 contract 不变**
- [ ] **Step 4: 再跑 tests，确认转绿**

---

## Tranche B：资产负债表权益层

**Tranche B 收口标准**

- `equity` 与 `equity_attributable_to_owners` 在主样本上能稳定产生 candidate facts。
- consolidated / parent-only / attributable 语义不会明显串线。
- 不把净资产、每股净资产、权益比率等摘要性口径误吸成核心资产负债表指标。

**Representative Label Families**

- CN:
  - `所有者权益合计`
  - `股东权益合计`
  - `归属于母公司股东权益`
  - `归属于母公司所有者权益`
- HK / English:
  - `total equity`
  - `total shareholders' equity`
  - `equity attributable to owners of the parent`
  - `equity attributable to equity holders of the company`

### Task B1：扩展 equity registry coverage 与 statement gating

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Modify: `financial-report-analysis/tests/unit/test_metric_registry.py`
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

- [ ] **Step 1: 先写失败测试，锁定 equity 与 equity_attributable_to_owners 的 CN/HK aliases**
- [ ] **Step 2: 跑相关 unit 与 integration tests，确认先红**
- [ ] **Step 3: 写最小实现，只补 ownership-aware normalization 与 gating**
- [ ] **Step 4: 再跑 tests，确认转绿**

### Task B2：验证资产负债表权益指标的 candidate -> canonical path

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py`
- Modify: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`

- [ ] **Step 1: 先写失败测试，锁定权益指标的 provenance 与 canonical promotion**
- [ ] **Step 2: 跑 tests，确认先红**
- [ ] **Step 3: 写最小实现，保持事实层 provenance 稳定**
- [ ] **Step 4: 再跑 tests，确认转绿**

---

## Tranche C：现金流量表三大主项闭环

**Tranche C 收口标准**

- `investing_cash_flow` 与 `financing_cash_flow` 稳定进入 candidate / canonical / key facts。
- 不把现金流增减净额、自由现金流、摘要现金流口径误吸成目标指标。
- 与已存在的 `operating_cash_flow` 一起形成现金流量表三主项闭环。

**Representative Label Families**

- CN:
  - `投资活动产生的现金流量净额`
  - `筹资活动产生的现金流量净额`
- HK / English:
  - `net cash generated from investing activities`
  - `net cash used in investing activities`
  - `net cash generated from financing activities`
  - `net cash used in financing activities`

### Task C1：扩展现金流 registry 与 normalization

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
- Modify: `financial-report-analysis/tests/unit/test_metric_registry.py`
- Modify: `financial-report-analysis/tests/unit/test_table_semantics.py`

- [ ] **Step 1: 先写失败测试，锁定 investing/financing cash flow aliases**
- [ ] **Step 2: 跑 unit tests，确认先红**
- [ ] **Step 3: 写最小实现，补 registry 与 deterministic normalization**
- [ ] **Step 4: 再跑 tests，确认转绿**

### Task C2：验证现金流量表 pipeline 穿透

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py`
- Modify: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`

- [ ] **Step 1: 先写失败测试，锁定三大现金流主项进入 canonical/key facts**
- [ ] **Step 2: 跑 tests，确认先红**
- [ ] **Step 3: 写最小实现，保持 API contract 不变**
- [ ] **Step 4: 再跑 tests，确认转绿**

---

## Tranche D：跨表冲突治理与总回归

**Tranche D 收口标准**

- 扩展后的指标覆盖不会明显恶化 summary/growth/ratio/secondary-table 干扰。
- 主表优先、statement-aware ranking、semantic provenance 在更广指标集下仍稳定。
- 三大表高价值指标在主样本与 reference set 上形成可回归闭环。

### Task D1：跨表冲突与排序校准

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/services/conflict_resolver.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

- [ ] **Step 1: 先写失败测试，锁定 summary table、ratio row、secondary table 的干扰场景**
- [ ] **Step 2: 跑 tests，确认先红**
- [ ] **Step 3: 写最小实现，只做必要的 source ranking 与 gating 校准**
- [ ] **Step 4: 再跑 tests，确认转绿**

### Task D2：完整验证矩阵

- [ ] **Step 1: 跑关键 unit tests**
Run:
```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run pytest tests/unit/test_metric_registry.py tests/unit/test_table_semantics.py tests/unit/test_fact_pipeline.py -v
```

- [ ] **Step 2: 跑关键 integration tests**
Run:
```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run pytest tests/integration/test_analysis_api.py tests/integration/test_semantic_recovery_regressions.py tests/integration/test_annual_structure_recovery.py -v
```

- [ ] **Step 3: 跑 Ruff**
Run:
```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run ruff check src tests
```

- [ ] **Step 4: 最终提交并补 closure note**

---

## 交付完成定义

当以下条件同时满足时，本计划可视为收口：

- 三大表都至少新增一组高价值主指标并打通 table-driven 主链路。
- `gross_profit`、`equity`、`equity_attributable_to_owners`、`investing_cash_flow`、`financing_cash_flow` 在目标样本集上稳定。
- 已有指标不发生明显回归。
- `candidate_facts`、`canonical_facts`、`key_facts` 与 API contract 不发生破坏性变化。
- Ruff 与真实样本 integration 回归通过。

---

## 默认执行顺序

建议默认按以下顺序推进：

1. Tranche A：利润表第二批指标
2. Tranche B：资产负债表权益层
3. Tranche C：现金流量表三大主项
4. Tranche D：跨表冲突治理与总回归

这样可以先沿着当前最稳的利润表路径补深度，再逐步进入更高歧义的权益口径与现金流扩展，最后统一做跨表收口。
