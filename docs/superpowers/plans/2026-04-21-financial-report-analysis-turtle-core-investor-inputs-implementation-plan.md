# 财报分析 Turtle Core Investor Inputs 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Related Master Plan:** `docs/superpowers/plans/2026-04-21-financial-report-analysis-turtle-investment-input-coverage-master-plan.md`
**Related Spec:** `docs/superpowers/specs/2026-04-21-financial-report-analysis-turtle-core-investor-inputs-design.md`

**Goal:** 在当前三大表高价值指标底座之上，补齐 Turtle 投资框架最核心的一批主表输入字段，使 `financial-report-analysis` 能稳定输出归母净利润、EPS、财务费用、税前利润、所得税费用、少数股东损益、Capex、D&A 与已付股息现金流等基础输入。

**Architecture:** 本阶段只处理“最适合由三大主表稳定提取”的核心 investor inputs。默认先补 deterministic normalization 与 registry，再打通 candidate/canonical/API 路径，最后做与 Turtle 相关的轻量回归。不要在本阶段扩展到 working capital 细项、母公司口径或附注桥接。

**Tech Stack:** Python 3.12、dataclasses、pytest、Ruff、现有 `financial_report_analysis` ingestion / semantic / registry / pipeline 架构、CN/HK 年报与季度样本。

---

## 范围与边界

### 本阶段纳入范围

**利润表**

- `n_income_attr_p`
- `basic_eps`
- `finance_exp`
- `total_profit`
- `income_tax`
- `minority_gain`

**现金流量表**

- `c_pay_acq_const_fiolta`
- `depr_fa_coga_dpba`
- `amort_intang_assets`
- `lt_amort_deferred_exp`
- `c_pay_dist_dpcp_int_exp`

### 本阶段明确不做

- 应收/预收/应付等 working capital 细项
- 借款类负债结构
- 母公司报表字段
- DPS / 分红方案附注抽取
- 回购/注销桥接
- 受限资金与附注桥接
- 多年序列导出 schema

### 共享样本矩阵

本阶段默认沿用当前项目已建立的 CN/HK 共享样本矩阵：

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

### Representative Label Families

**CN**

- `归属于母公司股东的净利润`
- `归属于上市公司股东的净利润`
- `基本每股收益`
- `财务费用`
- `利润总额`
- `所得税费用`
- `少数股东损益`
- `购建固定资产、无形资产和其他长期资产支付的现金`
- `固定资产折旧`
- `无形资产摊销`
- `长期待摊费用摊销`
- `分配股利、利润或偿付利息支付的现金`

**HK / English**

- `profit attributable to owners of the parent`
- `profit attributable to equity holders of the company`
- `basic earnings per share`
- `finance costs`
- `profit before tax`
- `income tax expense`
- `profit attributable to non-controlling interests`
- `payments for acquisition of property, plant and equipment`
- `depreciation of property, plant and equipment`
- `amortisation of intangible assets`
- `amortisation of long-term deferred expenses`
- `dividends paid`

### 字段-样本命中预期

本阶段不要求每个字段在共享矩阵的每一个样本里都出现。最低命中预期如下：

- `n_income_attr_p`、`finance_exp`、`total_profit`、`income_tax`
  - 必须命中：
    - `601919/annual/2024_年度报告.pdf`
    - HK annual anchors
  - 并在 CN annual references 中至少命中一部分样本
- `basic_eps`
  - 必须命中：
    - `601919/annual/2024_年度报告.pdf`
    - HK annual anchors
  - 不要求在每个 quarterly 或 reduced-disclosure 样本中都出现
- `minority_gain`
  - 只要求在明确披露少数股东损益的样本中命中
  - 不要求对所有发行人强行构造命中
- `c_pay_acq_const_fiolta`、`depr_fa_coga_dpba`、`amort_intang_assets`、`lt_amort_deferred_exp`、`c_pay_dist_dpcp_int_exp`
  - 主要要求在 annual-report 样本命中
  - 不要求在 `09987/quarterly/2025_quarterly_q3_en.pdf` 上全部齐备

实现和 review 都应以上述命中预期判断“稳定”，而不是默认要求每个字段在完整共享矩阵全命中。

### 字段分层目标

**Must Reach Candidate**

- `n_income_attr_p`
- `basic_eps`
- `finance_exp`
- `total_profit`
- `income_tax`
- `minority_gain`
- `c_pay_acq_const_fiolta`
- `depr_fa_coga_dpba`
- `amort_intang_assets`
- `lt_amort_deferred_exp`
- `c_pay_dist_dpcp_int_exp`

**Must Reach Canonical**

- `n_income_attr_p`
- `basic_eps`
- `finance_exp`
- `total_profit`
- `income_tax`
- `minority_gain`

**Must Be API Visible**

- `n_income_attr_p`
- `basic_eps`

其余现金流细项本阶段允许停留在 candidate-visible，只要 provenance 稳定、下游可消费即可。

### EPS 数据模型约束

`basic_eps` 不应被当作普通金额型主表字段处理。本阶段默认约束为：

- `value_type = per_share`
- `unit_expectation = per_share_amount`
- 优先来源为主利润表
- 只有在 provenance 明确且不会压过主利润表来源时，才允许来自 `key_metrics` 或每股收益区块

---

## Task A：扩展 registry 与 deterministic normalization

**Task A 收口标准**

- 新字段可通过 deterministic normalization + registry 在目标 statement/table kind 下稳定识别。
- 不把 diluted EPS、adjusted EPS、non-GAAP EPS、摘要表利润口径或 narrative cash-flow rows 误吸为目标字段。

### A1：先写失败测试，锁定 Phase-1 字段 coverage

**Files:**
- Modify: `financial-report-analysis/tests/unit/test_metric_registry.py`
- Modify: `financial-report-analysis/tests/unit/test_table_semantics.py`

- [ ] **Step 1: 为利润表字段补 registry 匹配测试**
- [ ] **Step 2: 为现金流细项字段补 registry 匹配测试**
- [ ] **Step 3: 为 EPS / profit attribution / cash-flow detail 补 normalization 与误匹配抑制测试**

### A2：实现最小 coverage

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`

- [ ] **Step 1: 只补最小 registry definitions 与 alias families**
- [ ] **Step 2: 只补最小 deterministic normalization**
- [ ] **Step 3: 必要时补 statement-aware gating，避免摘要表或 secondary rows 抢占**

### A3：验证 Task A

- [ ] **Step 1: 跑 unit tests，确认从红转绿**
Run:
```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run pytest tests/unit/test_metric_registry.py tests/unit/test_table_semantics.py -v
```

---

## Task B：打通 candidate -> canonical -> API 主链路

**Task B 收口标准**

- 目标字段能进入 candidate facts。
- 必须进入 canonical/API 的字段保持稳定穿透。
- provenance 不丢失，不因新字段扩展而把旧字段链路打乱。

### B1：先写失败测试，锁定 investor inputs 的主链路

**Files:**
- Modify: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`

- [ ] **Step 1: 为 candidate facts 补字段存在性测试**
- [ ] **Step 2: 为 must-reach-canonical 与 must-be-api-visible 字段补显式测试**
- [ ] **Step 3: 为 attribution / EPS / cash-flow detail 补 provenance 稳定性测试**

### B2：实现最小 pipeline 支撑

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/services/conflict_resolver.py`

- [ ] **Step 1: 只补必要的 candidate fact builder 支撑**
- [ ] **Step 2: 只补必要的 canonical alias / normalizer 对齐**
- [ ] **Step 3: 如有需要，做最小 ranking/provenance 修补**

### B3：验证 Task B

- [ ] **Step 1: 跑 unit + integration tests，确认主链路转绿**
Run:
```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py tests/integration/test_analysis_api.py -v
```

---

## Task C：面向 Turtle 核心输入的轻量回归

**Task C 收口标准**

- Phase-1 字段在共享样本矩阵上不出现明显 statement drift。
- 现有高价值指标不发生明显回归。
- 可以明确说明 Turtle 哪些核心计算已经得到支撑，哪些仍留到 Phase 2+。

### C1：补轻量回归测试与样本断言

**Files:**
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`

- [ ] **Step 1: 为 profit attribution / EPS / D&A / dividends paid 增加真实样本断言**
- [ ] **Step 2: 为 summary/growth/non-GAAP/secondary-table 干扰增加抑制断言**

### C2：整理阶段收口说明

**Files:**
- Modify: `docs/superpowers/plans/2026-04-21-financial-report-analysis-turtle-core-investor-inputs-implementation-plan.md`

- [ ] **Step 1: 在计划顶部补 completion note**
- [ ] **Step 2: 记录本阶段已覆盖的 Turtle 计算输入**
- [ ] **Step 3: 明确留给 Phase 2 的缺口**

---

## 完整验证矩阵

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
uv run pytest tests/integration/test_analysis_api.py tests/integration/test_semantic_recovery_regressions.py -v
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

- `n_income_attr_p`、`basic_eps`、`finance_exp`、`total_profit`、`income_tax`、`minority_gain`、`c_pay_acq_const_fiolta`、`depr_fa_coga_dpba`、`amort_intang_assets`、`lt_amort_deferred_exp`、`c_pay_dist_dpcp_int_exp` 按本计划定义的字段-样本命中预期具备稳定主链路。
- attributable profit、basic EPS、D&A、Capex、已付股息现金流的语义稳定。
- must-reach-candidate / must-reach-canonical / must-be-api-visible 分层目标满足。
- 现有高价值指标不明显回归。
- candidate / canonical / API contract 不发生破坏性变化。
- Ruff 与关键 integration 回归通过。

---

## 下一步衔接

本计划完成后，默认进入：

1. Phase 2：Working Capital And Debt Inputs

下一阶段会重点补：

- 应收/预收/应付细项
- 借款类负债
- 递延税

以支撑 Turtle 的现金收入还原、经营性现金支出还原和债务口径估值。
