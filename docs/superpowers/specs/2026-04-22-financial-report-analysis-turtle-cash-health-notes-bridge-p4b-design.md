# 财报分析 Turtle 现金健康度附注桥接 P4B 设计

> **Status:** Draft for review
> **Phase:** Turtle Investment Input Coverage - Phase 4B
> **Scope Type:** Narrow phase spec

## 1. 背景

截至当前分支状态，`financial-report-analysis` 已经完成并收口：

- Phase 1 的 core investor inputs
- Phase 2A 的 working capital inputs
- Phase 2B 的 debt inputs
- Phase 3 的 asset quality inputs
- Phase 4A 的 parent-scope / notes conflict governance

P4A 已经把本阶段最重要的治理前提钉住：

- `statement_row > deterministic_note_disclosure > llm_locator_assisted_note_disclosure`
- note/disclosure 默认只补缺，不覆盖已有 statement-row 事实
- parent / consolidated scope 不能混淆
- conflict / review / blocked 必须有显式表达，而不是静默裁决

与此同时，统一路线图和 `v0.15` 差距分析已经指向同一个结论：

- 下一步最有价值的财报内缺口，不是再扩主表骨架
- 而是先补 Turtle 现金健康度判断所需的高价值附注桥接字段

本轮 P4B 不应被理解成“广义 Phase 4 全量字段扩张”。它是一个窄范围、受治理约束的 cash-health bridge phase。

## 2. 目标

本轮 P4B 的目标是为 Turtle 现金健康度判断建立一条可追溯、可验证、可 review 的附注桥接输入层，优先支持以下字段：

- `restricted_cash`
- `interest_paid_cash`
- `time_deposits_or_wealth_products`

这三个字段的价值在于它们直接影响：

- 真实可动用现金判断
- 现金回报率与股东回报安全边界
- 现金健康度相关下游指标，如 `RCF`、`ACR`、`Cov_div`、`Buffer_months`

本轮目标不是做完整的 narrative policy parsing，也不是做母公司单体报表整套桥接，而是先把“财报内、可结构化、可 bounded 处理”的现金健康度字段打通。

## 3. 范围

### 3.1 本轮纳入的字段

- `restricted_cash`
- `interest_paid_cash`
- `time_deposits_or_wealth_products`

### 3.2 本轮允许的来源

- 现金流量表补充披露行
- 受限 note / disclosure blocks
- 定存 / 长短期银行存款 / 理财产品相关附注表或受限披露片段

### 3.3 本轮明确不纳入

- 母公司单体报表整套字段
- 广义 parent-scope coverage
- 分红政策 / 回购进度 / narrative policy 文本解析
- 租赁本金、资本化利息、坏账准备、账龄分析、关联交易等其他高价值附注主题
- broad notes bridge 平台化扩张
- 多年序列
- 新的持久化层或 review API 重写

## 4. 样本锚点与 phase-entry 结论

本轮固定使用以下三份样本：

- CN：`report/downloads/cn_stocks/601919/annual/2025_年度报告.pdf`
- HK cleaner-format anchor：`report/downloads/hk_stocks/02498/annual/2022_annual_en.pdf`
- HK mixed-structure anchor：`report/downloads/hk_stocks/09987/annual/2025_annual_en.pdf`

本轮同时采用独立 onboarding artifact：

- [2026-04-22-turtle-cash-health-p4b-sample-onboarding.md](F:/source/git/report-collector/docs/architecture-analysis/2026-04-22-turtle-cash-health-p4b-sample-onboarding.md)

### 4.1 当前 phase-entry 判断

- `601919 2025`
  - 当前仍视为 `CN diagnostics / not_surfaced guardrail anchor`
  - 不是本轮第一版的正实现锚点
- `02498 2022`
  - 当前可作为 `restricted_cash` 的正锚点
- `09987 2025`
  - 当前可作为 `interest_paid_cash` 和 `time_deposits_or_wealth_products` 的正锚点
  - `restricted_cash` 也已有较强正锚点证据

### 4.2 为什么 CN 先作为 diagnostics anchor

这并不表示 CN 不需要支持，而是表示：

- 当前轻量 probe 尚未稳定命中 `601919 2025` 中这三类字段的中文 note 证据
- 现阶段更像 `not_surfaced`，而不是已确认 `present`
- 如果本轮一开始就承诺 CN 与 HK 同步正实现，P4B 很容易被拖成“先补中文附注结构恢复”的 phase

因此，本轮更稳的策略是：

- HK 先作为正实现锚点，建立 bridge contract
- CN 先作为 diagnostics / guardrail anchor
- 如果 P4B 期间进一步诊断证明 CN note path 稳定可行，可在不改变 phase 边界的前提下把 CN 升级为正锚点

## 5. 与统一路线图和样本接入流程的关系

本轮 P4B 必须同时遵守：

- [2026-04-22-financial-report-analysis-unified-roadmap.md](F:/source/git/report-collector/docs/superpowers/specs/2026-04-22-financial-report-analysis-unified-roadmap.md)
- [new-report-sample-onboarding-and-field-variance-process.md](F:/source/git/report-collector/docs/architecture-analysis/new-report-sample-onboarding-and-field-variance-process.md)

具体体现为：

- P4B 是 `Phase 4 Parent Scope And Notes Bridge` 下面的第一段窄 phase，而不是整个 Phase 4
- 每个锚点都必须有 sample onboarding metadata、expected missing status 与 failure classification
- 任何新样本问题都先按：
  - `structure_recovery_gap`
  - `semantic_normalization_gap`
  - `metric_mapping_gap`
  - `note_disclosure_supplement_gap`
  归类，而不是直接写 issuer-specific 分支

## 6. 架构边界

本轮继续沿用结构化主链路：

`pdf -> structure recovery -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts`

补充链路为：

`statement_row / cash-flow supplement miss -> deterministic note/disclosure supplement -> gated semantic locator -> candidate facts`

### 6.1 source precedence

本轮继续遵守 P4A：

1. `statement_row`
2. `deterministic_note_disclosure`
3. `llm_locator_assisted_note_disclosure`

note/disclosure 只补缺，不覆盖 higher-priority source。  
如果某个字段未来真的需要 `override_allowed`，必须在后续单独 spec 中显式声明；P4B 默认不引入 override。

### 6.2 deterministic-first

本轮优先顺序固定为：

1. structure recovery
2. deterministic table / note semantics
3. metric mapping registry
4. deterministic note/disclosure supplement
5. gated semantic locator

禁止：

- 把现金健康度字段直接交给 LLM 自由抽数
- 让 LLM 直接生成 canonical facts
- 用全文泛扫替代 bounded disclosure matching

### 6.3 bounded note bridge

本轮只允许在以下前提下进入 note/disclosure bridge：

- 目标字段属于 `restricted_cash`、`interest_paid_cash`、`time_deposits_or_wealth_products`
- 存在明确 note/disclosure title、supplemental cash-flow row、或可界定的局部表块
- 该来源能给出稳定的 `evidence_bundle_id` / `page_index` / `source_text_span`

不允许：

- narrative 段落大范围自由搜索后直接产出事实
- 没有 title / local context 的泛扫描
- 借本轮顺手把 broad notes bridge 全部打开

## 7. 字段语义

### 7.1 `restricted_cash`

目标语义：

- 明确指受限现金、受限货币资金、已受限用途的现金与现金等价物
- 可以来自主表补充披露、现金流量表 supplementary row、或附注明细

允许的语义近邻：

- `restricted cash`
- `restricted cash and cash equivalents`
- `restricted deposits`
- `restricted monetary funds`
- `pledged cash` / `pledged deposits`，但前提是语义明确落在“现金受限”而不是纯担保概念说明

不允许误吸：

- 普通 `cash and cash equivalents`
- 总货币资金但没有受限语义
- 仅描述“资产受限”但没有现金数值披露的段落

### 7.2 `interest_paid_cash`

目标语义：

- 明确指现金流口径下“支付的利息”或等价 supplemental cash-flow disclosure

允许来源：

- `cash paid for interest`
- `支付的利息`
- 现金流量表附注中的补充现金流信息

不允许误吸：

- `interest expense`
- `finance expense`
- `interest payable`
- narrative 中提到“付息安排”但没有现金支付数值

### 7.3 `time_deposits_or_wealth_products`

目标语义：

- 明确指短期或长期定期存款、银行存款类金融产品、理财产品、结构性存款等现金管理型资产
- 本轮将其作为一个窄范围 bridge identity，不在第一版里继续拆成多条更细 canonical identities

允许来源：

- `time deposits`
- `term deposits`
- `long-term bank deposits and notes`
- `structured deposits`
- `wealth management products`
- 中文中的 `定期存款`、`结构性存款`、`理财产品`

不允许误吸：

- 一般 `short-term investments` 全量汇总
- 不可等价看作现金管理资产的股权或债券投资
- narrative 中对投资策略的描述

## 8. 缺失状态与锚点 contract

本轮必须显式区分：

- `present`
- `absent`
- `not_surfaced`
- `out_of_scope`

### 8.1 当前锚点 contract

- `601919 2025`
  - `restricted_cash = not_surfaced`
  - `interest_paid_cash = not_surfaced`
  - `time_deposits_or_wealth_products = not_surfaced`
- `02498 2022`
  - `restricted_cash = present`
  - `interest_paid_cash = absent`
  - `time_deposits_or_wealth_products = absent`
- `09987 2025`
  - `restricted_cash = present`
  - `interest_paid_cash = present`
  - `time_deposits_or_wealth_products = present`

如果后续 phase-entry diagnostics 或 focused implementation 发现这些状态判断不准确，必须先更新 onboarding artifact，再推进实现或回归测试。

## 9. Failure Classification

本轮问题应优先归类为：

- `structure_recovery_gap`
- `semantic_normalization_gap`
- `metric_mapping_gap`
- `note_disclosure_supplement_gap`

默认修复顺序：

1. 先修结构与局部 block 恢复
2. 再修语义归一化
3. 再修 registry mapping
4. 最后才进入 note/disclosure supplement 或 gated locator

如果某个锚点的失败本质上属于：

- broad parent-scope coverage
- narrative policy parsing
- review/storage/persistence redesign

则应暂停并重分类到后续 phase，而不是强行塞进 P4B。

## 10. Fallback 边界

P4B 允许使用 gated semantic locator，但只能用于：

- 受限 local context 中的字段判别
- note/disclosure block 是否属于目标 3 字段之一的歧义裁决

返回必须带：

- `metric_id`
- `matched_label`
- `source_text_span`
- `semantic_confidence`
- `fallback_reason`

禁止：

- 直接返回最终数值事实
- 单位/币种自由推断后直接传播
- 让 locator 变成默认主路径

## 11. 验收标准

本轮 P4B 完成时，应满足：

- `02498 2022` 能稳定给出 `restricted_cash`
- `09987 2025` 能稳定给出 `interest_paid_cash`
- `09987 2025` 能稳定给出 `time_deposits_or_wealth_products`
- `09987 2025` 中 `restricted_cash` 至少能以 bounded bridge 或补充披露方式稳定 surfaced
- `601919 2025` 至少被稳定记录为 `not_surfaced` guardrail，不被误判成 `absent`
- 所有 bridge 输出都保留 source provenance 与 missing/conflict semantics
- 不破坏 P2B、P3、P4A 的既有 precedence / review contract

## 12. 非目标

本轮明确不做：

- CN 全量正锚点承诺
- broad parent-company statement extraction
- 分红政策 / 回购进度 / narrative policy parsing
- 现金健康度下游公式实现
- broad note bridge 平台化
- 为单家公司写 issuer-specific 条件分支

## 13. 下一步

P4B implementation plan 应建立在以下输入之上：

- 本 spec
- P4A governance contract
- P4B sample onboarding artifact
- `v0.15` 财报字段差距分析

implementation plan 的第一阶段应优先围绕：

- HK 正锚点实现
- CN diagnostics / guardrail 验证
- bounded note/disclosure bridge
- precise missing-status regression

而不是一开始就承诺 CN/HK 三锚点同步正实现。
