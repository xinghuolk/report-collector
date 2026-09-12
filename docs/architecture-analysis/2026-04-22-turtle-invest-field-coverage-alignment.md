# 龟龟投资字段覆盖对齐表

## 0. 2026-04-24 状态更新

本文最初写于 P3/P4/P5 主线完成之前。下文中关于 `active_phase`、`future_phase`、P3 后续、P4 现金健康度、母公司范围、P5 多年数据集的判断，有一部分已经被后续实现推进。

截至当前分支，以下路线已经完成并收口：

- P2B Debt Inputs
- P3 Asset Quality Inputs
- P4A Parent Scope / Notes Conflict Governance
- P4B Cash-Health Notes Bridge
- P4C Investor Core Statement Gaps
- P4D Parent Scope And Notes Follow-up
- P4E Investor Earnings Quality And Capex Follow-up
- P5 Multi-Year Investor Dataset And Minimal Persistence
- DB-backed extract persistence and opt-in DB-backed P5/Turtle build

因此，本文现在应作为“字段分层与原始 Turtle 需求来源”的参考，而不是当前覆盖状态的唯一真相。

当前仍有参考价值的结论是：

- Turtle 字段必须继续分为原始抽取字段、附注/公告桥接字段、派生分析字段、外部市场字段。
- 下游派生计算结果仍不应写回 extraction facts。
- 新 coverage phase 仍应先走样本接入与字段差异处理流程。
- post-P5 enhancement candidates 应从 `docs/superpowers/specs/reference/2026-04-23-financial-report-analysis-turtle-post-p4-coverage-roadmap.md` 和 `2026-04-22-turtle-v015-financial-field-gap-analysis.md` 中挑最小字段族重开 focused spec。

当前仍开放的字段/能力方向主要是：

- gross profit / SG&A / non-operating income-expense / fair-value gain 等利润增强
- total/current assets and liabilities、deferred tax、other current assets 等资产负债增强
- stock-based compensation、working-capital cash-flow change rows 等现金流增强
- dividend / buyback / cancellation / DPS bridge
- MD&A、审计意见、风险因素、股息政策原文等文本型 review artifact
- market / share-count / valuation 输入的下游集成边界

## 1. 目的

这份文档用于把两侧内容对齐：

- Turtle 文档中真实需要的字段
- 当前 `report-collector` 已有 roadmap / phase spec / active plan 中已覆盖或已规划的字段

目标是明确：

- 哪些字段已经覆盖
- 哪些字段已经进入 active phase
- 哪些字段属于未来 phase
- 哪些字段不应由 `financial-report-analysis` 直接负责

## 2. 当前对照基线

本对齐表主要参考以下当前项目文档：

- [2026-04-22-financial-report-analysis-unified-roadmap.md](F:/source/git/report-collector/docs/superpowers/specs/2026-04-22-financial-report-analysis-unified-roadmap.md)
- [2026-04-21-financial-report-analysis-turtle-core-investor-inputs-design.md](F:/source/git/report-collector/docs/superpowers/specs/2026-04-21-financial-report-analysis-turtle-core-investor-inputs-design.md)
- [2026-04-21-financial-report-analysis-turtle-working-capital-p2a-design.md](F:/source/git/report-collector/docs/superpowers/specs/2026-04-21-financial-report-analysis-turtle-working-capital-p2a-design.md)
- [2026-04-22-financial-report-analysis-turtle-debt-inputs-p2b-design.md](F:/source/git/report-collector/docs/superpowers/specs/2026-04-22-financial-report-analysis-turtle-debt-inputs-p2b-design.md)
- [2026-04-22-financial-report-analysis-turtle-asset-quality-p3-design.md](F:/source/git/report-collector/docs/superpowers/specs/2026-04-22-financial-report-analysis-turtle-asset-quality-p3-design.md)
- [new-report-sample-onboarding-and-field-variance-process.md](F:/source/git/report-collector/docs/architecture-analysis/new-report-sample-onboarding-and-field-variance-process.md)

## 3. 对齐状态说明

字段状态统一分为：

- `covered`: 已有 phase 完成并进入当前体系
- `active_phase`: 已进入当前 active spec/plan，但尚未收口
- `future_phase`: 已在 roadmap 中，但未进入 active phase
- `needs_new_design`: Turtle 明确需要，但当前 roadmap / phase 还未正式承接
- `downstream_only`: 属于下游计算、公告桥接或市场数据，不应当作当前 extraction facts

## 4. 已覆盖字段

### 4.1 Phase 1 已覆盖

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

结论：

- 这些字段和 Turtle 文档里的“保守净利润、DCF、股息交叉校验、owner earnings”需求基本一致。

### 4.2 Phase 2A 已覆盖

- `accounts_receiv`
- `notes_receiv`
- `oth_receiv`
- `contract_liab`
- `adv_receipts`
- `acct_payable`
- `notes_payable`

结论：

- 这些字段和 Turtle 文档里“真实现金收入/支出还原、营运资本质量观察”的需求一致。

### 4.3 Phase 2B 已覆盖

- `st_borr`
- `lt_borr`
- `bond_payable`
- `non_cur_liab_due_1y`

结论：

- 这些字段和 Turtle 文档里“短债压力、债务结构、净负债/EV/WACC基础输入”的核心需求一致。

## 5. 已进入 active phase 的字段

### 5.1 Phase 3 active scope

- `money_cap`
- `trad_asset`
- `inventories`
- `goodwill`
- `intang_assets`
- `contract_assets`
- `other_non_current_assets`

结论：

- 这组字段与 Turtle 文档里“资产质量与现金储备质量”方向是一致的。
- 但当前 P3 的 note-only 边界是收紧的：
  - `contract_assets`
  - `other_non_current_assets`
  只能作为 bounded supplement，不等于广义 notes bridge。

## 6. 已在 roadmap 中、但尚未进入 active phase 的字段

### 6.1 Phase 3 roadmap 里有、当前 P3 还未纳入

- `lt_eqt_invest`
- `fix_assets`
- `cip`
- `minority_int`

结论：

- 这些字段在 unified roadmap 的 Phase 3 里已经出现。
- 当前 active P3 选择先做更窄的第一批，因此这几项属于 `future_phase`，不是遗漏，而是主动拆小。

### 6.2 Phase 2 debt-and-tax 延伸

- `defer_tax_assets`
- `defer_tax_liab`

结论：

- Turtle 文档有使用空间，但当前 active 路线没有把它们纳入已完成的 P2B。
- 它们属于 `future_phase` 或 `needs_new_design` 之间的边界项，取决于后续是否仍归在扩展 debt-and-tax。

## 7. Turtle 需要、但当前还未被正式承接的关键字段

以下字段在 Turtle 文档中很关键，但当前 `report-collector` 还没有被明确承接为 active extraction workstream：

### 7.1 现金健康度关键口径字段

- `restricted_cash`
- `interest_paid_cash`
- `lease_principal`
- `current_portion_lt_debt` 或 `cpltd`

分析：

- 这些字段直接影响：
  - `RCF`
  - `ACR`
  - `Cov_div`
  - `Buffer_months`
- 其中：
  - `current_portion_lt_debt` 与 P2B 已有 `non_cur_liab_due_1y` 在语义上强相关，但 Turtle 文档采用的是更计算化命名
  - `restricted_cash` 明确被当前 P3 负控排除，说明它被有意识后移了
  - `interest_paid_cash`、`lease_principal` 更像现金流附注桥接字段，尚未进入 active phase

当前结论：

- 这组字段属于 `needs_new_design`
- 很可能应进入未来的 Phase 4 note / announcement bridge，或单独的现金健康度输入阶段

### 7.2 回购 / 分红政策桥接字段

- 公告最低支付率
- 历史实际支付率序列
- 现金分红计划
- 回购计划金额
- 已注销回购额
- 回购注销进度
- 回购用途
- SBC / 稀释净额

分析：

- 这些字段不是标准三大表主路径字段。
- 它们对 Turtle 穿透回报率至关重要，但属于明显的：
  - announcement bridge
  - note bridge
  - governance / review-sensitive inputs

当前结论：

- 这组字段应归类为 `downstream_only` 或 `needs_new_design`
- 不应误认为当前 P1/P2/P3 extraction phase 已经在覆盖

## 8. 明确属于下游计算层的字段

以下字段虽然在 Turtle 文档里高频出现，但不应进入当前 extraction facts 范围：

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
- `buyback_yield`
- `penetrating_yield`
- `target_market_cap_dividend`
- `target_price_dividend`
- `target_market_cap_pen`
- `target_price_pen`

这些字段统一归类为：

- `downstream_only`

原因：

- 它们是投资分析计算结果，不是财报原始事实。
- 它们应由 Turtle 计算引擎、分析层或 reviewable calculation layer 生成。

## 9. 不属于 financial-report-analysis 直接负责的字段

以下字段更适合放在外部市场 / 主数据层：

- 当前市值
- 流通市值
- 总股本
- 股本变动记录
- 行业分类
- PE / PB
- 景气度
- 回测收益 / IC / RankIC / ROC / PR

这些字段统一归类为：

- `downstream_only`

## 10. 当前总体判断

### 10.1 一致的部分

当前 `report-collector` 的 Turtle 路线和 `turtle-invest/docs` 的方法论主线是一致的：

- 先做三大表主路径高价值输入
- 再做 working capital / debt / asset quality
- 再进入 note bridge、parent scope、multi-year
- 不把 LLM 作为主抽取路径

### 10.2 还未完全一致的部分

当前 `turtle-invest/docs` 里的字段需求，实际上混合了四层内容：

1. 财报原始抽取字段
2. 附注 / 公告桥接字段
3. 派生分析字段
4. 外部市场字段

而当前 `report-collector` phase spec 主要只在稳定覆盖第 1 层，并开始有限接触第 2 层。

### 10.3 最重要的结论

当前项目不是“字段方向错了”，而是“还缺一张统一字段地图”。

这张地图至少要持续回答两个问题：

- 这个 Turtle 字段是原始抽取字段，还是桥接字段，还是派生字段
- 它应该进入哪个 phase，而不是被顺手塞进当前 active phase

一句话收束：

`report-collector` 当前对 Turtle 的支持已经覆盖了主干 extraction inputs，但距离 Turtle 真正完整消费的投资分析输入体系，还差公告桥接、现金健康度关键口径字段、以及派生计算层的正式分层。 
