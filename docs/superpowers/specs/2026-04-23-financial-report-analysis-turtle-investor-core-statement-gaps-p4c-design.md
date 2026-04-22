# 财报分析 Turtle Investor Core Statement Gaps P4C 设计

> **状态:** Draft for review
> **阶段:** Turtle Post-P4 Coverage - Phase 4C
> **范围类型:** Narrow phase spec

## 1. 背景

截至当前分支状态，`financial-report-analysis` 已完成并收口：

- P1 `Core Investor Inputs`
- P2A `Working Capital Inputs`
- P2B `Debt Inputs`
- P3 `Asset Quality Inputs`
- P4A `Parent Scope / Notes Conflict Governance`
- P4B `Cash-Health Notes Bridge`

与此同时，最新的 Post-P4 路线判断已经明确：

- P5 的本质应是 multi-year dataset assembly
- P5 不应继续承担大规模补字段
- 当前真正阻塞 P5 的，首先是主表核心 coverage 仍不完整

因此，P4C 的职责不是扩广义附注，不是扩母公司整套 bridge，也不是开始做多年 dataset，而是：

**先补齐 Turtle 在多年分析里最基础、最常消费、且最适合由主表稳定抽取的核心 statement metrics。**

## 2. 目标

P4C 的目标是把以下主表字段纳入稳定 extraction contract：

### 利润表

- `revenue`
- `oper_cost`
- `operate_profit`
- `n_income`

### 资产负债表

- `total_assets`
- `total_liab`
- `total_hldr_eqy_exc_min_int`

### 现金流量表

- `n_cashflow_act`
- `n_cashflow_inv_act`
- `n_cash_flows_fnc_act`
- `c_pay_to_staff`
- `c_paid_for_taxes`

这些字段直接支撑：

- 5 年营收 CAGR
- 5 年净利润 CAGR
- 平均 ROE
- FCF / 分配能力分析
- 多年 DCF / FCF Yield

## 3. 范围

### 3.1 本轮纳入

- 三大主表 statement-row 主路径
- 目标字段的 deterministic normalization / registry mapping / candidate facts
- 必要时的 bounded semantic fallback
- focused real-PDF anchor regressions

### 3.2 本轮不纳入

- 母公司整套字段
- 广义 note/disclosure bridge
- DPS / 回购 / 文本型治理字段
- multi-year dataset schema
- 新 storage / lineage / recompute 能力

## 4. 架构边界

P4C 必须继续遵守现有主路径：

`pdf -> structure recovery -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts`

默认优先顺序：

1. deterministic structure recovery
2. deterministic table semantics
3. registry mapping
4. bounded semantic fallback only if needed

禁止：

- issuer-specific 分支
- 通过全文自由扫段落补主表 facts
- 用 note/disclosure bridge 替代本轮主表字段建模

## 5. 字段语义边界

## 5.1 利润表

### `revenue`

目标语义：

- 主营业务收入 / 营业收入 / revenue / turnover 的主口径收入行

不允许误吸：

- 其他收益
- 投资收益
- 分部收入摘要
- 非 GAAP / adjusted revenue

### `oper_cost`

目标语义：

- 营业成本 / cost of revenue / cost of sales

不允许误吸：

- 销售费用
- 管理费用
- 研发费用
- 财务费用

### `operate_profit`

目标语义：

- 营业利润 / operating profit / profit from operations

不允许误吸：

- 税前利润
- 毛利润
- EBITDA / adjusted operating profit

### `n_income`

目标语义：

- 集团净利润 / net income

不允许误吸：

- 归母净利润
- 少数股东损益
- 调整后净利润

## 5.2 资产负债表

### `total_assets`

目标语义：

- 资产总计 / total assets

### `total_liab`

目标语义：

- 负债合计 / total liabilities

### `total_hldr_eqy_exc_min_int`

目标语义：

- 归属于母公司股东权益 / equity attributable to owners of the parent

不允许误吸：

- 总权益含少数股东
- 单纯 `total equity` 但无法判明归母口径的聚合行

## 5.3 现金流量表

### `n_cashflow_act`

目标语义：

- 经营活动现金流净额 / net cash generated from operating activities

### `n_cashflow_inv_act`

目标语义：

- 投资活动现金流净额 / net cash used in investing activities

### `n_cash_flows_fnc_act`

目标语义：

- 筹资活动现金流净额 / net cash generated from financing activities

### `c_pay_to_staff`

目标语义：

- 支付给职工以及为职工支付的现金

### `c_paid_for_taxes`

目标语义：

- 支付的各项税费

## 6. 样本策略

P4C 应继续使用“样本锚点 + onboarding artifact”模式，而不是按公司修补。

建议至少覆盖：

- CN annual anchor
- HK cleaner-format annual anchor
- HK mixed-structure annual anchor

每个锚点都应记录：

- `present / absent / not_surfaced / out_of_scope`
- failure classification
- 是否需要 fallback

## 7. 缺失状态 contract

本轮应继续显式区分：

- `present`
- `absent`
- `not_surfaced`
- `out_of_scope`

原则：

- 主表明确不存在独立披露行时，使用 `absent`
- 当前样本家族可能存在，但 extraction path 尚未稳定时，使用 `not_surfaced`
- 不属于本轮目标口径时，使用 `out_of_scope`

## 8. Fallback 边界

P4C 可以使用现有 gated fallback，但必须满足：

- 仅用于 row-label / table-kind 局部歧义
- 只在 deterministic evidence 已存在但 label family 不稳定时触发
- 必须带 provenance、budget、negative controls

不允许：

- 让 fallback 自由抽数
- 让 fallback 替代 metric mapping contract
- 让 fallback 直接生成 canonical facts

## 9. 与 P5 的关系

P4C 完成后，P5 将具备更稳定的主表多年骨架，但 P4C 本身不负责：

- multi-year schema
- export shape
- fact-set versioning
- derived multi-year metrics

这些工作应留给 P5。

## 10. 验收标准

P4C 完成时，应满足：

1. 上述 12 个主表字段已进入稳定 extraction contract
2. focused anchors 上可形成 deterministic-first candidate facts
3. 不破坏 P1-P4B 既有 contract
4. 不引入 issuer-specific 分支
5. 为 P5 提供可组装的多年主表骨架

## 11. 一句话收束

P4C 的职责是：

**先补齐 Turtle 多年分析最基础的主表骨架，再把 multi-year dataset 留给 P5。**
