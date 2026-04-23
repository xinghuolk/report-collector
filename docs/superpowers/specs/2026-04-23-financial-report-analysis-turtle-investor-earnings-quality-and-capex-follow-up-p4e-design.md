# 财报分析 Turtle Investor Earnings Quality And Capex Follow-up P4E 设计

> **状态:** Draft for review
> **阶段:** Turtle Post-P4 Coverage - Phase 4E
> **范围类型:** Narrow phase spec

## 1. 背景

截至当前分支状态，`financial-report-analysis` 已完成并收口：

- P1 `Core Investor Inputs`
- P2A `Working Capital Inputs`
- P2B `Debt Inputs`
- P3 `Asset Quality Inputs`
- P4B `Cash-Health Notes Bridge`
- P4C `Investor Core Statement Gaps`
- P4D `Parent Scope And Notes Follow-up`

在“先不继续扩母公司范围”的前提下，P5 之前仍缺一小组会直接影响龟龟经营还原、资本开支判断与非经常性现金流入分类的字段。

因此，`P4E` 的职责不是继续做母公司，也不是开始做 multi-year dataset，而是：

**把 P5 前仍然必须补齐的经营质量与长期投入增强字段，收成一个最小、稳定、deterministic-first 的 extraction contract。**

## 2. 目标

`P4E` 只覆盖以下 7 个字段：

- `fix_assets`
- `cip`
- `rd_exp`
- `invest_income`
- `asset_disp_income`
- `n_recp_disp_fiolta`
- `c_recp_return_invest`

这些字段分别服务于：

- 长期投入质量判断
- 资本开支与扩张性投入还原
- 非经常性现金流入分类
- 经营还原与真实可支配现金估算

## 3. 与 Turtle 字段名的映射

`P4E` 应继续优先沿用当前代码 canonical ids。

本阶段目标字段与 Turtle 口径关系如下：

- `fix_assets` -> 固定资产 / property, plant and equipment
- `cip` -> 在建工程 / construction in progress
- `rd_exp` -> 研发费用 / research and development expenses
- `invest_income` -> 投资收益 / investment income
- `asset_disp_income` -> 资产处置收益 / gain on disposal of assets
- `n_recp_disp_fiolta` -> 处置固定资产、无形资产和其他长期资产收回的现金
- `c_recp_return_invest` -> 取得投资收益收到的现金

## 4. 范围

### 4.1 本轮纳入

- 目标字段的 deterministic normalization / registry mapping / candidate facts
- focused real-PDF anchor regressions
- 只在当前框架已允许的局部歧义里复用 bounded fallback

### 4.2 本轮不纳入

- 母公司 statement coverage
- `minority_int`
- `non_oper_income` / `non_oper_exp`
- `receiv_tax_refund`
- 广义附注桥接
- 文本型治理字段
- multi-year dataset schema

## 5. 架构边界

`P4E` 必须继续遵守现有主路径：

`table structure -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts`

默认优先级：

1. statement-row deterministic path
2. 已有框架内的 bounded local fallback

禁止：

- issuer-specific 分支
- 用全文自由扫段落替代主表建模
- 因为 `P4E` 扩大 note/disclosure bridge 范围

## 6. 字段语义边界

### `fix_assets`

目标语义：

- 固定资产 / property, plant and equipment 主口径

不允许误吸：

- right-of-use assets
- investment properties
- total non-current assets

### `cip`

目标语义：

- 在建工程 / construction in progress

不允许误吸：

- 开发支出
- deferred assets
- capitalized development costs

### `rd_exp`

目标语义：

- 当期费用化研发支出 / research and development expenses

不允许误吸：

- capitalized development costs
- technology amortisation
- generic operating expenses

### `invest_income`

目标语义：

- 投资收益 / investment income

不允许误吸：

- fair value changes
- interest income
- other income

### `asset_disp_income`

目标语义：

- 资产处置收益 / gain on disposal of assets

不允许误吸：

- government grants
- one-off compensation
- other non-operating income

### `n_recp_disp_fiolta`

目标语义：

- 处置固定资产、无形资产和其他长期资产收回的现金

不允许误吸：

- disposal proceeds of financial assets
- generic investing cash inflows

### `c_recp_return_invest`

目标语义：

- 取得投资收益收到的现金

不允许误吸：

- interest received
- dividends received from operations without bounded support
- disposal proceeds

## 7. 样本策略

`P4E` 应继续使用 onboarding artifact 模式。

建议至少覆盖：

- CN annual anchor with cleaner fixed-asset / investment rows
- HK cleaner-format partial-positive anchor
- mixed-format annual anchor for negative controls

每个锚点都应记录：

- 各字段 `present / absent / not_surfaced / out_of_scope`
- failure classification
- 哪些字段走 statement-row deterministic path
- 哪些字段仍不值得为本阶段打开新的 bridge path

## 8. Fallback 边界

`P4E` 只在以下情况下允许扩大 fallback：

- row-label 存在局部歧义，且 deterministic normalization 已经无法稳定区分目标字段与强负控

不应因为以下原因扩大 fallback：

- 样本本身没有独立披露
- 字段只存在于广义附注或 narrative 里
- 当前更像 bridge phase 而不是 statement-row phase

## 9. 一句话结论

`P4E` 是一个小而硬的 pre-P5 增强 phase：

**不做母公司，不做大规模附注，只把经营质量、非经常性现金流入分类和长期投入判断真正必需的 7 个字段补齐。**
