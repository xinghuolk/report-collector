# 龟龟投资所需字段总清单

## 1. 目的

这份文档用于从 `F:/source/git/turtle-invest/docs` 中抽取“龟龟投资”当前真实需要的字段，并按用途分层整理。

目标不是直接生成新的实现计划，而是回答三个问题：

- 龟龟投资到底需要哪些字段
- 哪些字段属于财报抽取层
- 哪些字段属于公告桥接、派生计算或外部市场输入

## 2. 参考来源

本清单主要基于以下 Turtle 文档整理：

- [龟龟投资_穿透回报率.md](F:/source/git/turtle-invest/docs/龟龟投资_穿透回报率.md)
- [龟龟投资_穿透回报率_总览.md](F:/source/git/turtle-invest/docs/龟龟投资_穿透回报率_总览.md)
- [龟龟投资_穿透回报率_评估与稳健化.md](F:/source/git/turtle-invest/docs/龟龟投资_穿透回报率_评估与稳健化.md)
- [龟龟投资_真实现金健康度测算.md](F:/source/git/turtle-invest/docs/龟龟投资_真实现金健康度测算.md)
- [龟龟投资_项目规划文档.md](F:/source/git/turtle-invest/docs/龟龟投资_项目规划文档.md)
- [开发计划_龟龟投资.md](F:/source/git/turtle-invest/docs/开发计划_龟龟投资.md)

## 3. 字段分层原则

为避免把“财报抽取字段”和“投资分析输出字段”混成一层，这里把字段分为 4 类：

1. 原始财报抽取字段  
2. 公告 / 附注桥接字段  
3. 投资分析派生字段  
4. 外部市场 / 参考输入字段  

其中：

- 第 1 类最适合由 `financial-report-analysis` 直接负责
- 第 2 类通常需要 Phase 4 级别的 note / announcement bridge
- 第 3 类不应作为原始抽取事实写回 extraction 层
- 第 4 类不属于 `financial-report-analysis` 直接负责的财报抽取范围

## 4. 原始财报抽取字段

### 4.1 利润表 / 现金流 / 估值基础输入

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

这些字段主要服务：

- 保守净利润基线
- DCF baseline
- 股息支付交叉校验
- owner earnings 近似

### 4.2 营运资本字段

- `accounts_receiv`
- `notes_receiv`
- `oth_receiv`
- `contract_liab`
- `adv_receipts`
- `acct_payable`
- `notes_payable`

这些字段主要服务：

- 真实现金收入 / 支出还原
- 应收应付质量观察
- 后续营运资本相关分析

### 4.3 有息负债字段

- `st_borr`
- `lt_borr`
- `bond_payable`
- `non_cur_liab_due_1y`

这些字段主要服务：

- 短债压力
- debt structure
- EV / WACC / 净负债基础输入

### 4.4 资产质量字段

- `money_cap`
- `trad_asset`
- `inventories`
- `goodwill`
- `intang_assets`
- `contract_assets`
- `other_non_current_assets`

这些字段主要服务：

- 现金储备质量
- 存货与经营资产质量
- 商誉 / 无形资产占比

### 4.5 Turtle 文档中明确出现、但当前阶段尚未系统纳入的原始财报字段

- `restricted_cash`
- `current_portion_lt_debt`
- `cash_and_eq`
- `ebitda`
- `net_debt`
- `interest_coverage`
- `lt_eqt_invest`
- `fix_assets`
- `cip`
- `minority_int`
- `defer_tax_assets`
- `defer_tax_liab`

这些字段里有些已经在路线图中出现，但尚未全部进入已立项的 phase spec。

## 5. 公告 / 附注桥接字段

以下字段在 Turtle 文档中是重要输入，但不属于“主表稳定抽取字段”：

- 最低股息支付率 / 分红政策下限
- 历史实际支付率序列
- 分红计划现金额
- 分红预案 / 实施状态
- 回购计划金额
- 已注销回购额
- 回购注销进度
- 回购用途
- SBC / 股权激励稀释相关净额
- 受限资金明细
- 支付的利息
- 租赁本金偿付

这些字段通常需要：

- 年报附注桥接
- 公告桥接
- parent / note conflict governance

因此它们不应被误归类为“当前主表 phase 就能全部覆盖”的字段。

## 6. 投资分析派生字段

以下字段在 Turtle 文档中大量出现，但属于计算结果，不是原始抽取事实：

- `n_cons`
- `payout_ratio_effective`
- `rcf_base`
- `rcf_conservative`
- `acr`
- `cov_div`
- `cov_dist`
- `buffer_months`
- `health_flag`
- `dividend_yield`
- `dividend_yield_sustainable`
- `buyback_yield`
- `buyback_cancelled_yield`
- `penetrating_yield`
- `target_market_cap_dividend`
- `target_price_dividend`
- `target_market_cap_pen`
- `target_price_pen`
- `target_price_4pct`

这类字段应由下游分析层、计算层或投资引擎生成，而不是由 `financial-report-analysis` 当作原始财报 facts 直接输出。

## 7. 外部市场 / 参考输入字段

以下字段不属于财报抽取本体：

- 当前市值
- 流通市值
- 总股本
- 股本变动记录
- 回购价格区间
- 行业分类
- PE / PB
- 行业景气度
- ROC / PR / IC / RankIC 等回测指标

这些字段可能在 Turtle 系统中是必要的，但其来源通常是：

- 行情数据
- 证券主数据
- 回测层
- 外部 market data

## 8. 当前结论

从 Turtle 原始文档看，“龟龟投资需要的字段”其实是三层混合需求：

1. 财报原始抽取字段
2. 公告 / 附注桥接字段
3. 派生分析与市场输入字段

当前项目下一步最重要的不是继续口头描述“需要更多字段”，而是始终先判断某个字段属于哪一层，再决定它应该进入：

- 当前 extraction phase
- 后续 note / announcement bridge
- 下游计算引擎
- 外部数据接入

一句话收束：

龟龟投资真正需要的是一整套“投资分析输入体系”，而不是单一层的财报抽取字段字典。
