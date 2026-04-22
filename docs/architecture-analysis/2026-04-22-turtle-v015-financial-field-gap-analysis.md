# 龟龟投资策略 v0.15 财报字段差距分析

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

## 5. 当前项目已较好覆盖的部分

### 5.1 已覆盖的主表核心字段

当前项目已经较稳定覆盖的，主要是 Turtle phase 中明确定义过的字段：

#### P1

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

#### P2A

- `accounts_receiv`
- `notes_receiv`
- `oth_receiv`
- `contract_liab`
- `adv_receipts`
- `acct_payable`
- `notes_payable`

#### P2B

- `st_borr`
- `lt_borr`
- `bond_payable`
- `non_cur_liab_due_1y`

#### 当前 P3 active scope

- `money_cap`
- `trad_asset`
- `inventories`
- `goodwill`
- `intang_assets`
- `contract_assets`
- `other_non_current_assets`

### 5.2 对 v0.15 的对应关系

这些字段已经覆盖了 v0.15 财报需求中的一条核心主干：

- 归母利润 / EPS / 税前利润 / 所得税 / 少数股东损益
- 资本开支 / 折旧摊销 / 股息支付现金
- 应收应付 / 合同负债 / 营运资本核心项
- 短债 / 长债 / 债券 / 一年内到期长债
- 现金 / 交易性金融资产 / 存货 / 商誉 / 无形资产

也就是说，当前项目已经能支撑 v0.15 所需财报字段中的“主表骨架”。

## 6. 当前项目与 v0.15 的主要差距

### 6.1 主表字段仍不完整

v0.15 需要，但当前项目还没有系统进入 active extraction coverage 的主表字段包括：

- `Total Revenue`
- `Cost of Revenue`
- `Gross Profit`
- `Research Development`
- `Selling General Administrative`
- `Operating Income`
- `Net Income`
- `Other Current Assets`
- `Total Current Assets`
- `Long Term Investments`
- `Property Plant Equipment`
- `Total Assets`
- `Deferred Revenue`
- `Total Current Liabilities`
- `Total Liabilities`
- `Total Stockholder Equity`
- `Total Cash From Investing Activities`
- `Total Cash From Financing Activities`
- `Repurchase of Stock`
- `Change in Receivables`
- `Change in Payables`
- `Change in Inventory`
- `Stock Based Compensation`

其中有些字段在 Turtle 路线图里已经隐含存在，但还没有被正式拆成 active phase。

### 6.2 现金健康度关键口径字段仍缺

v0.15 很强调以下字段，但当前项目还没有形成正式 extraction / bridge 承接：

- `restricted_cash`
- `interest_paid_cash`
- `lease_principal`
- `current_portion_lt_debt` / `cpltd`
- 定期存款 / 理财产品

这些字段会直接影响：

- `RCF`
- `ACR`
- `Cov_div`
- `Buffer_months`

所以它们不是边缘字段，而是穿透回报率框架里的关键输入。

### 6.3 母公司单体报表基本没进入当前路线

v0.15 的 PDF 解析明确要求提取母公司单体资产负债表中的现金、负债、对子公司投资、往来款。

而当前项目：

- 还没有 active phase 正式承接 parent-company scope
- unified roadmap 里把这件事放在更后的 Phase 4

这意味着：

**母公司单体报表是当前项目与 v0.15 的最大结构性差距之一。**

### 6.4 附注深挖字段还缺一整层

当前项目虽然已经开始做 bounded note/disclosure supplement，但与 v0.15 的 PDF 深挖要求相比，仍然差一整层：

- 账龄分析
- 坏账准备与政策
- 关联交易
- 资本化利息
- 或有负债与承诺
- 定期存款 / 理财产品明细
- 租赁负债分层
- 分部业务表
- 股息政策与支付率原文
- 回购注销进度

这类字段很多不适合直接塞进当前 statement-row 主路径，通常需要：

- note / disclosure bridge
- parent / consolidated conflict governance
- reviewable provenance

### 6.5 财报文本型字段还未进入当前 extraction contract

v0.15 把很多年报文本内容也作为数据包的一部分：

- MD&A 原文摘要
- 股息政策原文
- 回购计划原文
- 审计意见
- 风险因素

当前项目并没有把这些文本信息纳入主 extraction contract。  
这不代表路线错误，而是说明：

**当前项目更偏财务事实抽取系统，v0.15 更偏完整分析报告数据包。**

## 7. 结论

### 7.1 当前项目已经覆盖到哪里

当前项目已经覆盖了 v0.15 所需财报字段中的：

- 三大表主表核心骨架
- 营运资本核心项
- 有息负债核心项
- 资产质量第一批字段

这部分足以支撑一部分标准化、结构化的 Turtle 分析输入。

### 7.2 当前项目还缺什么

和 v0.15 相比，当前项目最主要缺的是三层：

1. 更完整的三大表主表字段覆盖
2. 母公司单体报表与附注深挖字段
3. 财报文本型桥接字段

其中最关键的不是“再多补几个主表字段”，而是：

- `restricted_cash`
- `interest_paid_cash`
- `current_portion_lt_debt`
- 母公司单体报表
- 股息 / 回购政策与进度

这些字段直接影响 v0.15 的核心计算链，但当前项目尚未正式承接。

### 7.3 一句话收束

如果把 v0.15 看成“完整投资分析报告的数据包需求”，那么当前项目已经覆盖了主表结构化骨架，但距离 v0.15 真正需要的财报输入层，还差母公司单体报表、现金健康度关键口径字段、以及一整层附注深挖与文本桥接能力。

## 8. 与当前路线图的三栏对照

为方便后续排期，可以把 v0.15 / 龟龟取数清单中的字段与当前路线图拆成三栏：

### 8.1 已覆盖

这些字段已经在当前路线中明确纳入，且 P1-P3 已形成 active extraction coverage 或已完成阶段实现：

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
- `money_cap`
- `trad_asset`
- `inventories`
- `goodwill`
- `intang_assets`
- `contract_assets`
- `other_non_current_assets`

### 8.2 已计划但未完全落地

这些字段在当前总路线图中已经有位置，但还没有完整进入 active extraction，或只停留在 master plan / 后续 phase 级别：

- `lt_eqt_invest`
- `fix_assets`
- `cip`
- `minority_int`
- `defer_tax_assets`
- `defer_tax_liab`
- 母公司 `money_cap`
- 母公司 `lt_eqt_invest`
- 母公司借款类负债
- 母公司总资产 / 总负债 / 权益
- `restricted_cash`
- 定存 / 理财 / 高流动性金融资产
- DPS / 分红方案
- 回购 / 注销
- 资本化研发
- 资本化利息
- 投资收益拆分
- 资产处置收益拆分
- 子公司现金归集限制
- 3-5 年字段序列
- 面向 Turtle 的导出 schema

### 8.3 v0.15 有，但当前规划还没正式纳入

这些字段在 v0.15 或龟龟投资取数清单中已经是直接消费项，但当前总路线图还没有把它们正式拆成 active phase：

- `revenue`
- `oper_cost`
- `gross_profit`
- `rd_exp`
- `sell_exp` / `admin_exp` 或等价 SG&A
- `operate_profit`
- `n_income`
- `invest_income`
- `asset_disp_income`
- `fv_value_chg_gain`
- `non_oper_income`
- `non_oper_exp`
- `total_assets`
- `total_liab`
- `total_hldr_eqy_exc_min_int`
- `total_cur_assets`
- `other_cur_assets`
- `n_cashflow_act`
- `n_cashflow_inv_act`
- `n_cash_flows_fnc_act`
- `c_pay_to_staff`
- `c_paid_for_taxes`
- `n_recp_disp_fiolta`
- `c_recp_return_invest`
- `receiv_tax_refund`
- `stock_based_compensation`
- `change in receivables`
- `change in payables`
- `change in inventory`
- MD&A 回顾 / 前瞻 / 风险因素
- 股息政策原文
- 审计意见
- 审计师更换历史

## 9. 建议优先级

如果目标是把当前路线和龟龟投资的真实计算收益尽快对齐，建议按以下顺序补齐：

### 9.1 建议优先纳入 P4 的核心缺口

这组字段对穿透回报、分配能力、资产负债约束和现金上游障碍判断最直接：

- `revenue`
- `oper_cost`
- `operate_profit`
- `n_income`
- `total_assets`
- `total_liab`
- `total_hldr_eqy_exc_min_int`
- `n_cashflow_act`
- `n_cashflow_inv_act`
- `n_cash_flows_fnc_act`
- `c_pay_to_staff`
- `c_paid_for_taxes`
- 母公司 `money_cap`
- 母公司 `lt_eqt_invest`
- 母公司借款类负债
- 母公司总资产 / 总负债 / 权益
- `restricted_cash`
- 定存 / 理财 / 高流动性金融资产

### 9.2 建议作为 P4 后半段或 P5 前置增强

这组字段更偏“增强版的非经常性现金流入识别、资本开支去伪和分红意愿判断”：

- `invest_income`
- `asset_disp_income`
- `fv_value_chg_gain`
- `non_oper_income`
- `non_oper_exp`
- `n_recp_disp_fiolta`
- `c_recp_return_invest`
- `receiv_tax_refund`
- `lt_eqt_invest`
- `fix_assets`
- `cip`
- `minority_int`
- 资本化研发
- 资本化利息
- DPS / 分红方案
- 回购 / 注销桥接

### 9.3 建议后置，不要抢当前主线

这些字段有价值，但对当前财报抽取底座的收益不如前两组直接，且歧义更高、治理成本更大：

- `stock_based_compensation`
- `change in receivables`
- `change in payables`
- `change in inventory`
- MD&A 回顾 / 前瞻 / 风险因素
- 股息政策原文
- 审计意见
- 审计师更换历史

### 9.4 推荐执行方式

如果需要把当前路线进一步和 v0.15 对齐，最稳的方式不是直接进入完整 P4，而是先做一个较小的 `P4-lite`：

1. 先补 `revenue` / `oper_cost` / `operate_profit` / `n_income`
2. 再补 `total_assets` / `total_liab` / `total_hldr_eqy_exc_min_int`
3. 再补 `n_cashflow_act` / `n_cashflow_inv_act` / `n_cash_flows_fnc_act`
4. 然后进入母公司关键字段与 `restricted_cash` 桥接

这样能先把龟龟投资当前最直接消费的主表和现金质量输入补齐，再进入更高歧义的附注和文本层。

## 10. 哪些字段应进入灵活字段设计

并不是所有 v0.15 中出现的字段都适合直接写死为 canonical metrics。更稳的做法是把字段分成三层：

1. 应写死为 canonical fields
2. 应先进入灵活字段 / provisional fields
3. 先灵活承接、后续再视稳定性收编

### 10.1 应写死为 canonical fields

这类字段满足以下特征：

- 下游公式会反复直接消费
- 跨公司和跨市场复用性较强
- 口径相对稳定
- 适合长期进入 tests、export schema 和 multi-year dataset

建议继续作为主路线中的正式字段推进，而不是放进灵活字段池：

- `revenue`
- `oper_cost`
- `operate_profit`
- `n_income`
- `total_assets`
- `total_liab`
- `total_hldr_eqy_exc_min_int`
- `n_cashflow_act`
- `n_cashflow_inv_act`
- `n_cash_flows_fnc_act`
- `money_cap`
- `st_borr`
- `lt_borr`
- `bond_payable`
- `accounts_receiv`
- `acct_payable`
- `inventories`

这些字段如果长期停留在灵活字段层，会直接削弱：

- 下游公式的可复用性
- 缺失治理的一致性
- 多年序列的可比性
- regression tests 的稳定边界

### 10.2 适合进入灵活字段 / provisional fields

这类字段高价值，但通常异构性强、附注依赖重、公司间写法不稳定，更适合作为可审阅的灵活字段承接：

- `restricted_cash`
- 定存 / 理财 / 高流动性金融资产拆分
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

这类字段更接近：

- reviewable extracted signals
- note / disclosure facts
- text-bridge outputs

而不是应立即写死到主表 canonical fact contract 中。

### 10.3 适合先灵活承接、后续再视稳定性收编

还有一批字段位于中间地带，建议先进入 provisional / flexible field 设计，等样本稳定后再决定是否升级为 canonical fields：

- `c_pay_to_staff`
- `c_paid_for_taxes`
- `n_recp_disp_fiolta`
- `c_recp_return_invest`
- `receiv_tax_refund`
- `rd_exp`
- `stock_based_compensation`
- `change in receivables`
- `change in payables`
- `change in inventory`
- `invest_income`
- `asset_disp_income`
- `fv_value_chg_gain`
- `non_oper_income`
- `non_oper_exp`

这类字段的共同特点通常是：

- 不同市场披露口径差异较大
- 容易与摘要行、调整行、补充披露行混淆
- 对下游有用，但还没有证明值得立即升级为主 contract

### 10.4 建议的设计原则

如果后续引入灵活字段机制，建议不要让它变成“所有还没想清楚字段的收容所”，而应遵守以下边界：

1. 龟龟核心公式直接依赖的主表字段，优先进入 canonical contract
2. 附注桥接、文本桥接和高异构字段，优先进入灵活字段层
3. 中间地带字段走 `provisional -> stable -> canonical` 的升级路径
4. 灵活字段必须保留 provenance、scope 和 reviewability，避免和主表事实混淆

一句话说，灵活字段设计应服务于“高价值但高异构”的输入承接，而不应替代 Turtle 核心财务字段的正式建模。
