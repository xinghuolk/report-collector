# 财报分析 Turtle Parent Scope And Notes Follow-up P4D 设计

> **状态:** Draft for review
> **阶段:** Turtle Post-P4 Coverage - Phase 4D
> **范围类型:** Narrow phase spec

## 1. 背景

截至当前分支状态，`financial-report-analysis` 已完成并收口：

- P1 `Core Investor Inputs`
- P2A `Working Capital Inputs`
- P2B `Debt Inputs`
- P3 `Asset Quality Inputs`
- P4A `Parent Scope / Notes Conflict Governance`
- P4B `Cash-Health Notes Bridge`
- P4C `Investor Core Statement Gaps`

其中：

- `P4C` 已优先补齐 P5 前最关键的主表核心骨架
- `P4B` 已收口 `restricted_cash` / `interest_paid_cash` / `time_deposits_or_wealth_products`
- 但 P5 仍缺一层稳定的 `parent_company` / notes bridge 增强合同

因此，`P4D` 的职责不是继续扩主表核心字段，也不是开始做 multi-year dataset，而是：

**把 P5 前仍然必需的母公司口径与高价值 notes bridge 收进一个清晰、最小、稳定的 extraction contract。**

## 2. 目标

`P4D` 的目标是补齐以下两层能力。

### 2.1 母公司 statement-row 能力

- 母公司 `money_cap`
- 母公司 `lt_eqt_invest`
- 母公司 debt families
- 母公司总资产 / 总负债 / 权益

说明：

- `equity` 是母公司主轨默认目标
- `equity_attributable_to_owners` 只在样本家族明确以母公司轨独立披露该口径时纳入，不应作为本阶段默认必备主锚点

### 2.2 已有 notes bridge 的 parent-scope / hardening 收口

- `restricted_cash`
- `time_deposits_or_wealth_products`
- `interest_paid_cash`

这里的重点不是重新设计 `P4B`，而是：

- 保持现有 notes bridge contract 不倒退
- 明确 parent statement facts 与 note/disclosure facts 的 precedence
- 让 `parent_company` 轨道能形成稳定的 deterministic statement-row contract；missing-status metadata 仅在真实实现需要时再补

## 2.1 与 Turtle 字段名的映射

`P4D` 应优先沿用当前代码中的 canonical ids；只有当前代码没有稳定 canonical id 时，才在本阶段引入最小新 id。

已有映射：

- Turtle parent `money_cap` -> current code `cash` with `entity_scope = parent_company`
- Turtle parent debt -> current code `st_borr` / `lt_borr` / `bond_payable` / `non_cur_liab_due_1y`
- Turtle parent totals -> current code `total_assets` / `total_liabilities` / `equity` / `equity_attributable_to_owners`
- notes bridge -> current code `restricted_cash` / `time_deposits_or_wealth_products` / `interest_paid_cash`

计划中的最小新增 canonical id：

- `lt_eqt_invest`

如果后续 Turtle export 仍需统一到另一套命名，应在 adapter / export 层处理，而不是在 `P4D` 里和 coverage work 混做 rename。

## 3. 范围

### 3.1 本轮纳入

- `parent_only` / separate-company statement scope 的 deterministic path
- 目标字段的 deterministic normalization / registry mapping / candidate facts
- 必要时的 bounded notes bridge hardening
- focused real-PDF anchor regressions

### 3.2 本轮不纳入

- 再次扩主表核心 consolidated metrics
- 广义文字治理字段
- DPS / buyback / capitalized R&D / capitalized interest 的全文桥接
- multi-year dataset schema
- 新 storage / lineage / recompute 能力

## 4. 架构边界

`P4D` 必须继续遵守现有主路径与优先级：

`parent/consolidated table structure -> normalized table semantics -> metric mapping registry -> candidate facts -> optional bounded note supplement`

默认优先顺序：

1. deterministic parent statement-row coverage
2. 已有 note/disclosure bridge 只补缺
3. bounded semantic fallback only if already justified by the current framework

禁止：

- issuer-specific 分支
- 让 note/disclosure silently override higher-priority parent statement facts
- 用全文自由扫段落替代母公司主表建模
- 重新打开已经在 `P4B` 收口的 base contract

## 5. 字段语义边界

## 5.1 母公司主表字段

### parent `cash`

目标语义：

- 母公司单体报表中的 `cash and cash equivalents` / `货币资金`

不允许误吸：

- consolidated `cash`
- `restricted_cash`
- 定存 / 理财 / 结构性存款

### `lt_eqt_invest`

目标语义：

- 母公司单体主表中的长期股权投资 / investments in subsidiaries / investments in associates 等长期股权投资主口径

不允许误吸：

- trading assets
- other non-current assets
- goodwill
- investment properties

### parent debt families

目标语义：

- 母公司 `st_borr`
- 母公司 `lt_borr`
- 母公司 `bond_payable`
- 母公司 `non_cur_liab_due_1y`

不允许误吸：

- 租赁负债
- aggregate borrowings summaries
- note-only debt bridge rows when statement-row fact already exists

### parent totals / equity

目标语义：

- 母公司 `total_assets`
- 母公司 `total_liabilities`
- 母公司 `equity`
- 必要时的 `equity_attributable_to_owners`

不允许误吸：

- consolidated totals
- generic total equity rows that only belong to another scope track

## 5.2 Notes bridge 字段

### `restricted_cash`

目标语义：

- 明确限定为受限现金 / restricted monetary funds

不允许误吸：

- plain cash
- unrestricted bank balances

### `time_deposits_or_wealth_products`

目标语义：

- 定存 / 理财 / structured deposits / term deposits

不允许误吸：

- trading assets
- short-term investments without bounded note support

### `interest_paid_cash`

目标语义：

- 补充披露中的现金利息支出

不允许误吸：

- finance expense
- accrued interest

## 6. Scope / Precedence Contract

`P4D` 需要显式锁住两条 precedence：

1. `consolidated` 与 `parent_company` 必须分轨保存，不能互相静默覆盖
2. statement-row facts 优先于 note/disclosure supplements

若同一 metric 同期同时存在：

- `parent_company` statement-row
- `parent_company` note supplement

则默认保留 statement-row fact 为主，note 仅作为补缺或证据增强，不覆盖已存在主事实。

## 7. 缺失状态 contract

`P4D` 应继续显式区分：

- `present`
- `absent`
- `not_surfaced`
- `out_of_scope`

如真实实现需要，可新增以下 metadata contract：

- `parent_scope_missing_status`
- 只有在本阶段真的引入新的 parent note bridge path 时，才考虑相应的 parent note missing-status contract

原则：

- 样本明确存在母公司单体报表但当前字段未稳定抽出：`not_surfaced`
- 当前样本家族无对应独立披露：`absent`
- 不属于本阶段目标：`out_of_scope`

默认不要求在 `P4D` 扩写现有 consolidated `cash_health_missing_status`。若 parent track 需要独立 notes contract，应使用单独、显式命名的 parent-scope status。

## 8. 样本策略

`P4D` 应继续使用 onboarding artifact 模式，而不是按公司修补。

建议至少覆盖：

- CN annual anchor with separate parent statements
- HK cleaner-format annual negative-control anchor
- HK mixed-structure annual anchor that stresses parent/consolidated separation

每个锚点都应记录：

- consolidated / parent 可用性
- `present / absent / not_surfaced / out_of_scope`
- failure classification
- 是否需要复用现有 fallback

## 9. Fallback 边界

`P4D` 可以复用现有 gated fallback，但必须满足：

- 只用于 row-label / table-kind / scope 局部歧义
- 不新增广义全文检索型 fallback
- 不把 fallback 当成 parent/consolidated precedence 的替代品

如果某个目标字段只能靠大范围自由文本扫描才能稳定拿到，该字段应移出 `P4D` 当前范围，而不是直接把 fallback 面扩大。

## 10. 一句话结论

`P4D` 的本质是：

**在 `P4C` 主表骨架之后，补齐 `parent_company` 轨与最小 notes bridge hardening，让 P5 之前的 scope / precedence / missing contract 完整闭环。**
