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
