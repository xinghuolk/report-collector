# 龟龟投资策略 v0.15 财报字段差距分析

## 0. 2026-04-28 状态更新

本文最初写于 P4C/P4D/P4E/P5 完成之前。当前分支已经完成 post-P5
基础设施、storage-backed read surfaces、metric governance Phase 1-4B，以及多轮
Turtle 字段覆盖实现。下文保留 v0.15 原始需求地图，但当前覆盖状态必须按
2026-04-28 的 implemented baseline 理解。

截至当前分支，以下原先的关键缺口已经完成或显著收窄，不应再作为待启动
P4/P5 缺口处理：

- 主表核心骨架：`revenue`、`operating_cost`、`operating_profit`、`net_profit`、`total_assets`、`total_liabilities`、`equity_attributable_to_owners`、`operating_cash_flow`、`investing_cash_flow`、`financing_cash_flow`、`c_pay_to_staff`、`c_paid_for_taxes`
- 现金健康度 / bridge baseline：`restricted_cash`、`interest_paid_cash`、`time_deposits_or_wealth_products`
- 母公司范围 baseline：parent `cash`、`lt_eqt_invest`、parent debt/equity/asset/liability families
- 经营质量与 capex follow-up baseline：`fix_assets`、`cip`、`rd_exp`、`invest_income`、`asset_disp_income`、`n_recp_disp_fiolta`、`c_recp_return_invest`
- 利润增强最小切片已完成：`selling_general_administrative` direct-combined rows、`fv_value_chg_gain`、`non_oper_income`、`non_oper_exp` 已进入 deterministic statement-row coverage；`gross_profit` 继续作为既有基线回归保护。CN 单独 `销售费用` / `管理费用` 求和仍保持 future scope。
- P5 multi-year investor dataset、Turtle export、storage-backed lookup、review、
  lineage、recompute 和 3-5Y availability baseline

因此，本文现在应作为 v0.15 原始需求地图和 post-P5 enhancement backlog 的参考。
如果本文后续段落与 active roadmap 或 2026-04-28 架构分析冲突，以 active
roadmap、reconciliation spec 和当前代码为准。

当前仍开放、且更适合进入后续 focused specs 的差距主要是：

1. 资产负债增强：`total_cur_assets`、`other_cur_assets`、`total_cur_liab`、`defer_tax_assets`、`defer_tax_liab`
2. 现金流增强：`stock_based_compensation`、`change_in_receivables`、`change_in_payables`、`change_in_inventory`、`receiv_tax_refund`
3. CN 单独 `销售费用` / `管理费用` 求和等非最小切片利润细化
4. 附注/公告桥接：DPS、分红方案、回购/注销、资本化研发、资本化利息、账龄/坏账、关联方应收应付
5. 文本型 review artifact：MD&A、审计意见、风险因素、股息政策原文

新阶段不应恢复旧 P4/P5 计划，而应从这些开放方向里挑一个最小字段族，按样本接入流程重新写 focused spec / plan。

## 1. 目的

这份文档只回答两个问题：

1. `F:/source/git/Stock_Analyze_Prompts/turtle_framework/龟龟投资策略_v0.15` 中，哪些属于“财报需要提取”的字段  
2. 这些字段与当前 `report-collector` 项目的覆盖状态相比，还差什么  

这里不讨论：

- 市场行情字段
- WebSearch 获取的治理/行业/竞争信息
- 下游派生计算结果

只讨论“财报抽取层”本身。

## 2. 参考来源

本分析主要基于以下 v0.15 文档：

- [coordinator.md](F:/source/git/Stock_Analyze_Prompts/turtle_framework/龟龟投资策略_v0.15/coordinator.md)
- [phase1_数据采集.md](F:/source/git/Stock_Analyze_Prompts/turtle_framework/龟龟投资策略_v0.15/phase1_数据采集.md)
- [phase2_PDF解析.md](F:/source/git/Stock_Analyze_Prompts/turtle_framework/龟龟投资策略_v0.15/phase2_PDF解析.md)
- [phase3_分析与报告.md](F:/source/git/Stock_Analyze_Prompts/turtle_framework/龟龟投资策略_v0.15/phase3_分析与报告.md)

并对照当前项目文档：

- [2026-04-21-financial-report-analysis-turtle-core-investor-inputs-design.md](F:/source/git/report-collector/docs/superpowers/specs/2026-04-21-financial-report-analysis-turtle-core-investor-inputs-design.md)
- [2026-04-21-financial-report-analysis-turtle-working-capital-p2a-design.md](F:/source/git/report-collector/docs/superpowers/specs/2026-04-21-financial-report-analysis-turtle-working-capital-p2a-design.md)
- [2026-04-22-financial-report-analysis-turtle-debt-inputs-p2b-design.md](F:/source/git/report-collector/docs/superpowers/specs/2026-04-22-financial-report-analysis-turtle-debt-inputs-p2b-design.md)
- [2026-04-22-financial-report-analysis-turtle-asset-quality-p3-design.md](F:/source/git/report-collector/docs/superpowers/specs/2026-04-22-financial-report-analysis-turtle-asset-quality-p3-design.md)
- [2026-04-22-turtle-invest-required-field-inventory.md](F:/source/git/report-collector/docs/architecture-analysis/2026-04-22-turtle-invest-required-field-inventory.md)
- [2026-04-22-turtle-invest-field-coverage-alignment.md](F:/source/git/report-collector/docs/architecture-analysis/2026-04-22-turtle-invest-field-coverage-alignment.md)

## 3. 什么算“财报需要提取的字段”

本分析把 v0.15 中的财报字段分成 3 类：

1. 三大表主表字段
2. 年报附注 / PDF 深挖字段
3. 财报文本型字段

其中：

- 第 1 类最适合由当前 `financial-report-analysis` 主路径承接
- 第 2 类通常需要 note / disclosure / parent-scope bridge
- 第 3 类虽然也来自年报，但更接近文本桥接和治理层，不等于标准 statement facts

## 4. v0.15 中属于财报提取的字段

### 4.1 三大表主表字段

#### 利润表

- `Total Revenue`
- `Cost of Revenue`
- `Gross Profit`
- `Research Development`
- `Selling General Administrative`
- `Operating Income`
- `Other Income/Expense`
- `Income Before Tax`
- `Income Tax Expense`
- `Net Income`
- `Net Income Applicable To Common Shares`
- `Minority Interest / Noncontrolling Interest`
- `Depreciation & Amortization`
- `Stock Based Compensation`

#### 资产负债表

- `Cash and Cash Equivalents`
- `Short Term Investments`
- `Net Receivables`
- `Inventory`
- `Other Current Assets`
- `Total Current Assets`
- `Long Term Investments`
- `Property Plant Equipment`
- `Goodwill`
- `Intangible Assets`
- `Total Assets`
- `Short Long Term Debt`
- `Long Term Debt`
- `Accounts Payable`
- `Deferred Revenue`
- `Total Current Liabilities`
- `Total Liabilities`
- `Total Stockholder Equity`
- `Minority Interest`

#### 现金流量表

- `Total Cash From Operating Activities`
- `Capital Expenditures`
- `Total Cash From Investing Activities`
- `Total Cash From Financing Activities`
- `Dividends Paid`
- `Repurchase of Stock`
- `Depreciation`
- `Change in Receivables`
- `Change in Payables`
- `Change in Inventory`

### 4.2 年报附注 / PDF 深挖字段

#### 母公司单体报表

- 母公司现金及等价物
- 母公司短期投资 / 定期存款
- 母公司短期借款 / 短债
- 母公司长期借款 / 长债
- 母公司应付债券
- 关联方借款
- 对子公司长期股权投资
- 对子公司应收往来款

#### 附注明细

- `restricted_cash` 明细
- 应收账款账龄分布
- 坏账准备
- 关联交易明细
- 资本化利息
- 或有负债
- 资本承诺
- 定期存款 / 理财产品明细
- 租赁负债分层
- 分部业务收入 / 利润
- 支付的利息
- 全年股息总额
- 全年 DPS
- 支付率

### 4.3 财报文本型字段

这些也来自年报，但更接近“文本桥接信息”：

- MD&A 经营回顾
- MD&A 前瞻指引
- MD&A 资本配置意图
- MD&A 风险因素
- 股息政策原文
- 回购计划 / 注销进度
- 审计意见
- 审计师更换历史

## 5. 当前项目已覆盖的 v0.15 财报输入

当前项目已经不只是 P1-P3 主表骨架。P4C/P4D/P4E/P5、storage-backed
query、review/lineage/recompute 和 metric governance 完成后，v0.15 所需财报输入
中的核心结构化层已经形成 baseline。

### 5.1 当前代码 canonical id 映射说明

为避免 Turtle 字段名和当前代码 contract 混淆，以下字段在本文中应按当前代码
canonical ids 理解：

- Turtle `oper_cost` -> current code `operating_cost`
- Turtle `operate_profit` -> current code `operating_profit`
- Turtle `n_income` -> current code `net_profit`
- Turtle `total_liab` -> current code `total_liabilities`
- Turtle `total_hldr_eqy_exc_min_int` -> current code `equity_attributable_to_owners`
- Turtle `n_cashflow_act` -> current code `operating_cash_flow`
- Turtle `n_cashflow_inv_act` -> current code `investing_cash_flow`
- Turtle `n_cash_flows_fnc_act` -> current code `financing_cash_flow`

### 5.2 已覆盖或已有 baseline 的字段族

以下字段族已经在当前路线中明确纳入，并通过已完成阶段形成 baseline。它们不应再被
列为“当前未覆盖”的 v0.15 缺口。

#### 核心利润表 / 现金流 / 资产负债骨架

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

#### 早期 Turtle 主表字段

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
- `accounts_receiv`
- `notes_receiv`
- `oth_receiv`
- `contract_liab`
- `adv_receipts`
- `acct_payable`
- `notes_payable`
- `st_borr`
- `lt_borr`
- `bond_payable`
- `non_cur_liab_due_1y`
- `cash` / Turtle `money_cap`
- `trad_asset`
- `inventories`
- `goodwill`
- `intang_assets`
- `contract_assets`
- `other_non_current_assets`

#### 现金健康度、母公司范围与附注 bridge baseline

- `lt_eqt_invest`
- parent `cash`
- parent `lt_eqt_invest`
- parent debt/equity/asset/liability families
- `restricted_cash`
- `interest_paid_cash`
- `time_deposits_or_wealth_products`

#### 经营质量与 capex follow-up baseline

- `fix_assets`
- `cip`
- `rd_exp`
- `invest_income`
- `asset_disp_income`
- `n_recp_disp_fiolta`
- `c_recp_return_invest`

#### 多年数据与导出能力

- P5 multi-year investor dataset
- Turtle export
- storage-backed extracted artifact / dataset / Turtle lookup
- review、lineage、recompute、availability read surfaces

## 6. 当前仍开放的 post-P5 enhancement backlog

当前缺口已经从“主表骨架不完整”转为“更细的利润质量、资产负债增强、现金流拆分、
附注桥接和文本型 review artifact”。这些字段应按 focused specs 推进，而不是恢复
旧 P4/P5 大阶段。

### 6.1 利润增强

- `gross_profit`
- `selling_general_administrative` / SG&A 等价口径
- `fv_value_chg_gain`
- `non_oper_income`
- `non_oper_exp`

这些字段更适合优先做一个 statement-row focused slice。原因是它们比附注/文本桥接
更接近现有 table semantics 主路径，同时能直接改善利润质量判断。

### 6.2 资产负债增强

- `total_cur_assets`
- `other_cur_assets`
- `total_cur_liab`
- `defer_tax_assets`
- `defer_tax_liab`
- `minority_int` / noncontrolling interest 的 balance-sheet 表达

这些字段有利于流动性、递延税项和权益结构分析，但应先确认不同市场 row labels 与
statement scope，避免把摘要行、父公司行或注释行误并入 consolidated facts。

### 6.3 现金流增强

- `stock_based_compensation`
- `change_in_receivables`
- `change_in_payables`
- `change_in_inventory`
- `receiv_tax_refund`
- `repurchase_of_stock`

这组字段更容易依赖补充披露或现金流附表，建议后于利润增强和资产负债增强。若要推进，
应先明确它们是 canonical statement facts、note facts，还是 reviewable signals。

### 6.4 附注 / 公告桥接

- DPS
- 分红方案
- 回购 / 注销进度
- 资本化研发
- 资本化利息
- 账龄 / 坏账
- 关联方应收应付
- 或有负债与承诺
- 租赁负债分层
- 分部业务收入 / 利润

这类字段不应直接塞进 statement-row 主路径。它们需要 note/disclosure bridge、
scope/provenance、reviewability，以及必要时的 lifecycle/governance guardrails。

### 6.5 文本型 review artifact

- MD&A 回顾 / 前瞻 / 风险因素
- 股息政策原文
- 审计意见
- 审计师更换历史

这些内容属于完整投资分析数据包的一部分，但不是当前 canonical financial facts
主路径。它们更适合作为 review/diff artifact 或 text bridge，不应进入 deterministic
recompute 裁决链。

## 7. 更新后的结论

### 7.1 当前项目已经覆盖到哪里

当前项目已经覆盖了 v0.15 财报输入中的主要结构化 baseline：

- 三大表核心骨架；
- 营运资本、有息负债、资产质量与 capex 关键字段；
- 现金健康度 / 母公司范围的第一层 bridge；
- P5 multi-year dataset 与 Turtle export；
- storage-backed review、lineage、recompute 与 availability surfaces；
- metric governance Phase 1-4B。

这意味着当前系统已经可以支撑标准化、可追溯、可多年读取的 Turtle 财报事实输入。

### 7.2 当前项目还缺什么

当前剩余差距主要不是“能不能抽出主表核心字段”，而是三类 post-P5 enhancement：

1. 更细的利润质量与非经常性项目拆分；
2. 流动资产/负债、递延税项、现金流变动项等增强字段；
3. 附注、公告和文本型 review artifact。

这些差距仍有价值，但需要按最小字段族推进，并继续遵守 governance、source
precedence、fallback 和 reviewability 边界。

### 7.3 一句话收束

如果把 v0.15 看成“完整投资分析报告的数据包需求”，当前项目已经完成结构化财报事实
baseline；下一步应做 post-P5 focused enhancement，而不是重启旧 P4/P5 coverage
路线。

## 8. 建议优先级

如果目标是继续完善龟龟投资需要的字段，推荐顺序如下。

### 8.1 第一优先级：利润增强最小切片

推荐先做：

- `gross_profit`
- `selling_general_administrative` / SG&A 等价口径
- `fv_value_chg_gain`
- `non_oper_income`
- `non_oper_exp`

理由：

- 最贴近现有 income statement table semantics；
- 对利润质量、毛利率、期间费用和非经常性损益判断价值直接；
- 比附注/文本桥接更容易做 deterministic tests 和 negative controls；
- 不需要先引入 UI、async jobs 或 workflow product。

### 8.2 第二优先级：资产负债增强

推荐在利润增强之后做：

- `total_cur_assets`
- `other_cur_assets`
- `total_cur_liab`
- `defer_tax_assets`
- `defer_tax_liab`

这一组有助于补充流动性与税项口径，但需要先锁定 consolidated/parent scope 与
summary row negative controls。

### 8.3 第三优先级：现金流增强

推荐后置：

- `stock_based_compensation`
- `change_in_receivables`
- `change_in_payables`
- `change_in_inventory`
- `receiv_tax_refund`
- `repurchase_of_stock`

这一组通常更依赖现金流附表或补充披露，容易跨 statement-row、note 和 text bridge
边界，应在前两组稳定后推进。

### 8.4 不应马上做的方向

- 不要把整份 v0.15 gap 一次性打开。
- 不要把 MD&A、审计意见、股息政策原文直接纳入 canonical facts。
- 不要让 Ollama 生成 values 或 canonical facts。
- 不要在没有 source precedence 与 reviewability 的情况下扩展附注桥接。
- 不要把 UI、async jobs 或 approval workflow 当成字段覆盖的前置条件。

## 9. 哪些字段应进入灵活字段设计

并不是所有 v0.15 中出现的字段都适合直接写死为 canonical metrics。当前更稳的做法
仍是把字段分成三层：

1. 已经或应继续作为 canonical contract；
2. post-P5 focused enhancement candidate；
3. reviewable / flexible / text-bridge signal。

### 9.1 已经或应继续作为 canonical contract

这类字段满足以下特征：

- 下游公式会反复直接消费
- 跨公司和跨市场复用性较强
- 口径相对稳定
- 适合长期进入 tests、export schema 和 multi-year dataset

这些字段已经进入当前 baseline，或应继续保持在正式字段 contract 中，而不是退回
灵活字段池：

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
- `money_cap`
- `st_borr`
- `lt_borr`
- `bond_payable`
- `accounts_receiv`
- `acct_payable`
- `inventories`
- `restricted_cash`
- `interest_paid_cash`
- `time_deposits_or_wealth_products`
- `fix_assets`
- `cip`
- `rd_exp`
- `invest_income`
- `asset_disp_income`
- `n_recp_disp_fiolta`
- `c_recp_return_invest`

这些字段如果退回灵活字段层，会直接削弱：

- 下游公式的可复用性
- 缺失治理的一致性
- 多年序列的可比性
- regression tests 的稳定边界

### 9.2 适合 post-P5 focused enhancement

这类字段高价值，且有机会进入 canonical contract，但应先通过 focused spec、样本接入
诊断、negative controls 和 review surface 检查：

- `gross_profit`
- `selling_general_administrative`
- `fv_value_chg_gain`
- `non_oper_income`
- `non_oper_exp`
- `total_cur_assets`
- `other_cur_assets`
- `total_cur_liab`
- `defer_tax_assets`
- `defer_tax_liab`
- `stock_based_compensation`
- `change_in_receivables`
- `change_in_payables`
- `change_in_inventory`
- `receiv_tax_refund`
- `repurchase_of_stock`

### 9.3 适合 reviewable / flexible / text-bridge signal

这类字段高价值，但通常异构性强、附注依赖重、公司间写法不稳定，更适合作为可审阅的
灵活字段或文本桥接承接：

- 资本化利息
- 资本化研发
- 投资收益构成
- 资产处置收益构成
- 子公司现金归集限制
- 回购用途与注销进度
- 股息方案原文
- 审计意见
- 审计师更换历史
- MD&A 回顾 / 前瞻 / 风险因素
- 账龄 / 坏账 / 关联方应收应付

### 9.4 建议的设计原则

如果后续引入灵活字段机制，建议不要让它变成“所有还没想清楚字段的收容所”，而应遵守以下边界：

1. 已稳定的 Turtle 核心公式字段保持 canonical contract。
2. statement-row 增强字段先走 focused spec，不直接混入 flexible bucket。
3. 附注桥接、文本桥接和高异构字段优先进入 reviewable signal 层。
4. 中间地带字段走 `provisional -> stable -> canonical` 的升级路径。
5. 灵活字段必须保留 provenance、scope 和 reviewability，避免和主表事实混淆。

一句话说，灵活字段设计应服务于“高价值但高异构”的输入承接，而不应替代 Turtle 核心财务字段的正式建模。
