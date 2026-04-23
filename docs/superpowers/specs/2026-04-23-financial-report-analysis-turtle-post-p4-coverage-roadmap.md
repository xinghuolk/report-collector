# 财报分析 Turtle Post-P4 Coverage Roadmap

> **状态:** Draft for review
> **日期:** 2026-04-23
> **范围:** 定义 P4 之后、P5 之前的剩余 Turtle 财报输入覆盖路线，明确哪些字段必须先补，哪些字段可后置增强，以及 P5 multi-year dataset 的真正前置条件。

## 1. 为什么需要这份文档

截至当前分支状态，`financial-report-analysis` 已经完成并收口：

- P1 `Core Investor Inputs`
- P2A `Working Capital Inputs`
- P2B `Debt Inputs`
- P3 `Asset Quality Inputs`
- P4A `Parent Scope / Notes Conflict Governance`
- P4B `Cash-Health Notes Bridge`

但这并不等于 Turtle 所需财报输入已经足够进入 P5。

当前仍存在两类剩余缺口：

1. 主表核心字段缺口
2. 母公司 / 附注 bridge 剩余缺口

如果不先把这两类缺口重新分层，后续很容易出现以下混乱：

- 把 P5 误做成“继续补字段”的 phase
- 把母公司 / 附注 bridge 和主表核心 coverage 混成一个大 implementation plan
- 不清楚哪些字段会阻塞 multi-year dataset
- 不清楚哪些字段应进入 canonical contract，哪些应保留为 flexible / provisional / bridge outputs

因此，需要一份 Post-P4 总纲，专门回答：

- P5 之前哪些字段必须先补
- P5 之后哪些字段再增强
- 下一轮 phase 应如何切分

## 2. 与现有文档的关系

本路线图应与以下文档一起阅读：

- [2026-04-21-financial-report-analysis-turtle-investment-input-coverage-master-plan.md](F:/source/git/report-collector/docs/superpowers/plans/2026-04-21-financial-report-analysis-turtle-investment-input-coverage-master-plan.md)
- [2026-04-22-financial-report-analysis-unified-roadmap.md](F:/source/git/report-collector/docs/superpowers/specs/2026-04-22-financial-report-analysis-unified-roadmap.md)
- [2026-04-22-turtle-v015-financial-field-gap-analysis.md](F:/source/git/report-collector/docs/architecture-analysis/2026-04-22-turtle-v015-financial-field-gap-analysis.md)
- [龟龟投资_穿透回报与估值分析_财报取数清单.md](F:/source/git/Turtle_investment_framework/docs/龟龟投资_穿透回报与估值分析_财报取数清单.md)

关系说明：

- `master plan` 仍然是 Turtle 输入覆盖的高层总纲
- `unified roadmap` 仍然是全项目协调路线图
- 本文档只负责回答 Post-P4 的剩余 coverage 分期问题
- 本文档不是 implementation plan，不应直接拿来编码到底

## 3. 当前判断

### 3.1 P5 的本质

P5 的核心目标是：

- 产出 3-5 年可消费的投资分析输入数据集
- 定义稳定的 multi-year dataset schema
- 保持 period / scope / missing / quality contract 一致
- 支撑 CAGR、平均值、多年估值与分配能力计算

因此，P5 不应承担“继续大规模补字段”的职责。

### 3.2 当前真正阻塞 P5 的缺口

当前阻塞 P5 的不是所有剩余字段，而是以下两层：

1. 主表核心骨架仍不完整
2. 少量高价值母公司 / 附注 bridge 仍未形成稳定 contract

### 3.3 默认原则

默认顺序应为：

1. 先补主表核心 coverage
2. 再补剩余 parent / notes bridge
3. 再进入 P5 multi-year dataset

不建议让 P5 同时承担：

- 继续补字段
- 大规模补 bridge 字段

这里的边界要明确：

- `P5` 需要定义并实现 multi-year dataset schema、assembly rules、quality / missing contract 与 export shape
- `P5` 不应继续承担新的大范围字段 coverage 扩张
- 换句话说，P5 是 dataset assembly phase，而不是新的 coverage phase

## 4. 字段分层

## 4.1 P5 前必须补

### Turtle 字段名与当前代码 canonical id 映射

Post-P4 路线应优先沿用当前代码中的 canonical metric ids。若下游 Turtle 仍使用旧字段名，应通过映射层处理：

- Turtle `oper_cost` -> current code `operating_cost`
- Turtle `operate_profit` -> current code `operating_profit`
- Turtle `n_income` -> current code `net_profit`
- Turtle `total_liab` -> current code `total_liabilities`
- Turtle `total_hldr_eqy_exc_min_int` -> current code `equity_attributable_to_owners`
- Turtle `n_cashflow_act` -> current code `operating_cash_flow`
- Turtle `n_cashflow_inv_act` -> current code `investing_cash_flow`
- Turtle `n_cash_flows_fnc_act` -> current code `financing_cash_flow`

以下字段应视为 `pre-P5 required coverage`：

### 利润表

- `revenue`
- `operating_cost`
- `operating_profit`
- `net_profit`

### 资产负债表

- `total_assets`
- `total_liabilities`
- `equity_attributable_to_owners`

### 现金流量表

- `operating_cash_flow`
- `investing_cash_flow`
- `financing_cash_flow`
- `c_pay_to_staff`
- `c_paid_for_taxes`

### 母公司 / 现金健康度最小增强

- 母公司 `money_cap`
- 母公司 `lt_eqt_invest`
- 母公司借款类负债
- 母公司总资产 / 总负债 / 权益
- `restricted_cash`
- 定存 / 理财 / 高流动性金融资产

这些字段之所以被归为 P5 前必须补，是因为它们直接影响：

- 5 年营收 CAGR
- 5 年净利润 CAGR
- 平均 ROE
- FCF / 分配能力
- 现金上游障碍判断
- 多年 DCF / FCF Yield

## 4.2 P5 后增强

以下字段高价值，但不必阻塞 P5 第一版 dataset：

### 利润与现金流增强

- `invest_income`
- `asset_disp_income`
- `fv_value_chg_gain`
- `non_oper_income`
- `non_oper_exp`
- `gross_profit`
- `selling_general_administrative` / SG&A 等价口径
- `n_recp_disp_fiolta`
- `c_recp_return_invest`
- `receiv_tax_refund`
- `rd_exp`
- `repurchase_of_stock`
- `change_in_receivables`
- `change_in_payables`
- `change_in_inventory`
- `stock_based_compensation`

### 资产 / 税项增强

- `defer_tax_assets`
- `defer_tax_liab`
- `other_cur_assets`
- `total_cur_assets`
- `total_cur_liab`
- `cip`
- 更完整的 `lt_eqt_invest` / `fix_assets` / `minority_int` 多年增强

### 高价值附注增强

- 资本化研发
- 资本化利息
- DPS / 分红方案
- 回购 / 注销桥接
- 账龄 / 坏账 / 关联方应收应付

### 文本 / 治理增强

- 审计意见
- MD&A
- 风险因素
- 股息政策原文

## 5. 下一阶段建议切分

本路线建议拆成三个后续阶段。

## 5.1 P4C Investor Core Statement Gaps

**目标：** 补齐 P5 前必须具备的主表核心字段。

**优先字段：**

- `revenue`
- `operating_cost`
- `operating_profit`
- `net_profit`
- `total_assets`
- `total_liabilities`
- `equity_attributable_to_owners`
- `operating_cash_flow`
- `investing_cash_flow`
- `financing_cash_flow`
- `c_pay_to_staff`
- `c_paid_for_taxes`

**默认路径：**

- statement-row deterministic path
- deterministic normalization
- bounded fallback only when already justified by current framework

**非目标：**

- 母公司整套 coverage
- 广义 notes bridge
- 文本型治理字段

## 5.2 P4D Parent Scope And Notes Follow-up

**目标：** 补齐 P5 前仍需要的母公司 / 现金健康度增强字段，并收口 P4 余下高价值 bridge。

**优先范围：**

- 母公司 `money_cap`
- 母公司 `lt_eqt_invest`
- 母公司 debt / equity
- 已完成 `P4B` 现金健康度 contract 的剩余 hardening 或 parent-scope 补充接线

说明：

- `restricted_cash`
- 定存 / 理财 / 高流动性金融资产

这条线的基础 contract 已在 `P4B Cash-Health Notes Bridge` 收口。`P4D` 不应重新打开已完成的 P4B 范围，而应只承接剩余 parent-scope、hardening 或与母公司 bridge 交叉的后续工作。

**可选收口项：**

- DPS / 分红方案
- 回购 / 注销桥接
- 资本化研发
- 资本化利息

**默认路径：**

- 继续遵守 P4A/P4B 的 precedence / review contract
- note / disclosure 只补缺，不静默覆盖 higher-priority facts

## 5.3 P5 Multi-Year Investor Dataset

**目标：** 在 P4C/P4D 的稳定字段基础上，组装多年可消费数据集。

**第一版应包含：**

- 3-5 年核心字段序列
- multi-year dataset schema
- missing / quality / version contract
- 面向 Turtle 的 export shape

**不应再承担：**

- 大规模补主表字段
- 大规模补 bridge 字段
- 广义 storage / recompute 平台化改造

## 6. P5 的前置条件

进入 P5 前，至少应满足：

1. `pre-P5 required coverage` 已有明确 contract
2. 主表核心字段能稳定形成 multi-year comparable facts
3. 母公司 / cash-health 最小增强路径可输出清晰的 missing status
4. statement / parent / note bridge 的 precedence 已在前序 phase 中收口
5. 不需要 issuer-specific 分支来拼多年度字段

如果这些条件不满足，说明应先继续做 P4C / P4D，而不是启动 P5。

## 7. P5 设计时必须回答的问题

在写 P5 子 spec 前，至少需要先回答：

1. multi-year dataset 的最小 schema 长什么样
2. point-in-time 和 duration 序列如何并存
3. consolidated 与 parent 是否分轨导出
4. `present / absent / not_surfaced / out_of_scope` 如何进入 dataset
5. multi-year 派生指标是在 dataset 层算，还是在更上层算
6. `quality_marker`、`evidence lineage`、`fact_set_version` 如何表达

## 8. 灵活字段边界

Post-P4 继续遵守已有判断：

- 龟龟核心公式直接依赖的主表字段，应优先进入 canonical contract
- 高异构附注 / 文本字段，可进入 flexible / provisional / bridge outputs
- 不应让 flexible field 机制替代主表核心建模

## 9. 一句话结论

Post-P4 的正确顺序不是“直接开始 P5”，而是：

`P4C 主表核心补齐 -> P4D 母公司与附注补齐 -> P5 多年数据集`

这样才能让 P5 真正成为 dataset assembly phase，而不是继续补字段的杂糅 phase。
