# 财报分析 Parent Scope 与 Notes Conflict Governance P4A 设计

> **Status:** Draft for review
> **Phase:** Turtle Investment Input Coverage - Phase 4A
> **Scope Type:** Governance contract spec

## 1. 背景

`financial-report-analysis` 的 Turtle 输入覆盖路线已经完成或进入收口的阶段包括：

- Phase 1 的 core investor inputs
- Phase 2A 的 working capital core
- Phase 2B 的 debt inputs core
- Phase 3 的 asset quality inputs

这些阶段主要围绕合并口径三大主表与受限 note/disclosure supplement 展开。到 Phase 3 为止，默认 source precedence 仍然可以保持为：

```text
statement_row > deterministic_note_disclosure > llm_locator_assisted_note_disclosure
```

并且 note/disclosure path 默认只补缺，不覆盖 statement-row fact。

Phase 4 开始进入母公司口径与高价值附注桥接。这个阶段的风险明显高于 P1-P3：

- 母公司报表事实和合并报表事实可能拥有相同或相似 metric label。
- 英文报表中 `parent` 可能出现在合并口径项目里，例如 `profit attributable to owners of the parent`，不能据此判断为母公司报表。
- 某些高价值附注字段的权威来源天然在 note/disclosure 中，而不是主表 statement row。
- 如果没有明确 conflict governance，后续字段扩展会把 scope、source priority 和 review policy 混在字段规则里。

统一路线图明确要求：Turtle Phase 4 之前，应先设计 parent-scope 与 note/disclosure conflict governance。本文即为 Phase 4A 的窄范围治理设计。P4A 不负责完整实现 P4B 字段覆盖，而是为 P4B 建立必须遵守的 contract。

## 2. 目标

P4A 的目标是建立一套可测试、可审阅、可复用的治理契约，用于回答以下问题：

- 一个 fact 是合并口径、母公司口径，还是 scope 不足以自动判断？
- note/disclosure fact 只能补缺，还是可以作为某些字段的权威来源覆盖 statement-row fact？
- 当 parent/consolidated scope 或 statement/note source 出现冲突时，系统如何表达 review 或 blocked，而不是静默选一个事实？
- P4B 新字段如何按统一 policy 接入，避免 issuer-specific 分支和字段补丁式开发？

P4A 完成后，P4B 可以在不重新定义治理规则的前提下，开始规划母公司字段和高价值附注字段。

## 3. 非目标

P4A 明确不做以下事情：

- 不实现 P4B 的完整字段集。
- 不承诺抽取所有母公司报表字段。
- 不承诺抽取所有高价值附注字段。
- 不做多年 dataset schema。
- 不做大型 storage 重写。
- 不让 LLM 直接抽取母公司或附注数值。
- 不把 `/api/v1/analysis/extract` 扩成全能 review API。
- 不把 `report/` forwarding 层改成 financial analysis 业务实现 owner。
- 不为单个公司、股票代码、文件名或页面坐标写 issuer-specific 分支。

P4A 可以使用少量 synthetic case、已有测试片段或真实样本片段作为 contract tests，但这些测试只用于证明治理规则成立，不代表 P4B 字段覆盖已完成。

## 4. 与统一路线图的关系

P4A 属于统一路线图中的 Turtle Input Coverage workstream，同时也触发 Review / API / Storage / Lineage workstream 的最小 review surface 需求。

P4A 必须遵守以下路线图约束：

- 不把“下一个字段族”误认为“下一步最合理的工程动作”。
- broad note/disclosure bridge 实现前，先有 conflict governance。
- parent vs consolidated scope 必须有明确 contract。
- source precedence 与 missing states 必须可测试。
- 当前缺失状态不能把 `not_surfaced` 误当作 `absent`。
- note/disclosure candidates 不能在没有明确 policy 的情况下覆盖 statement-row facts。
- parent-company facts 不能与 consolidated facts 混淆。

## 5. Scope Contract

### 5.1 Entity Scope Values

P4A 规范以下 `entity_scope` 语义：

- `consolidated`: 合并口径事实。
- `parent_company`: 母公司、公司本部或 company-level 单体报表事实。
- `unknown`: 证据不足以判断 entity scope。
- `review_required`: 候选事实存在 scope 冲突或误导风险，不能自动进入下游生产级消费。

`unknown` 表示系统还没有足够 evidence；`review_required` 表示已经发现风险或冲突。两者不能混用。

### 5.2 Parent Scope 识别原则

`parent_company` 必须来自明确的报表级或区块级 scope evidence，例如：

- 表标题明确为母公司资产负债表、母公司利润表、母公司现金流量表。
- 英文表标题明确为 company statement、separate statement、parent company statement 或等价表达。
- 上下文 metadata 明确标识该表属于 parent/company/separate financial statements。

不能仅凭以下信号判断为 `parent_company`：

- metric label 中出现 `parent`。
- metric label 中出现 `owners of the parent`。
- `equity attributable to owners of the parent`、`profit attributable to owners of the parent` 等合并口径归母项目。
- 某个 note/disclosure 段落提到 parent company，但没有证明当前数字属于母公司报表口径。

### 5.3 Consolidated Scope 识别原则

`consolidated` 可以来自：

- 表标题明确为合并资产负债表、合并利润表、合并现金流量表。
- 英文表标题明确为 consolidated statement。
- 当前 report family 的主表结构已经稳定识别为 consolidated primary statement。

如果一个表既可能是 consolidated，又可能是 parent/company scope，且没有稳定上下文证明，候选事实应进入 `unknown` 或 `review_required`，不能默认归入 consolidated。

## 6. Source Conflict Policy

### 6.1 Source Kinds

P4A 使用以下 source kind 作为 policy 输入：

- `statement_row`
- `deterministic_note_disclosure`
- `llm_locator_assisted_note_disclosure`
- `summary_table`
- `derived`

P4A 不要求一次性重构所有现有 source 标识，但 implementation plan 必须确保候选事实和 canonical promotion 至少能区分 statement-row、deterministic note/disclosure 与 locator-assisted note/disclosure。

### 6.2 Policy Modes

每个需要进入 P4B 的 metric 或 metric family 必须声明 source policy。默认 policy 是 `supplement_only`。

- `supplement_only`
  - note/disclosure 只能在同一 business key 下没有更高优先级 statement-row fact 时补缺。
  - 这是 P1-P3 已有行为的默认延续。
- `override_allowed`
  - note/disclosure 是该字段的权威披露来源，可以优先于或覆盖 statement-row candidate。
  - 必须由字段 spec 显式声明。
  - 必须保留被覆盖 source 的 evidence 与 conflict reason。
- `review_required`
  - 多个来源都可能合理，但语义、scope、期间或单位不完全等价。
  - 系统应输出 review packet 或 validation issue，不能静默 promotion。
- `blocked`
  - source scope、字段语义、单位、期间或证据链不可靠。
  - 候选事实不能进入 canonical/key Turtle input。

### 6.3 默认 Precedence

在没有字段级 explicit policy 时，P4A 继续采用默认 precedence：

```text
statement_row > deterministic_note_disclosure > llm_locator_assisted_note_disclosure
```

`summary_table` 默认不允许覆盖 primary statement。`derived` 不能覆盖 direct reported fact，除非后续单独设计 derivation policy。

### 6.4 Override 的最低门槛

一个字段只有同时满足以下条件，才能在 P4B spec 中声明 `override_allowed`：

- 字段语义天然以 note/disclosure 为权威来源。
- statement-row fact 不是同一语义口径，或只是聚合/摘要。
- note/disclosure block 有明确 title、table context 或稳定 locator evidence。
- period、unit、currency 和 entity scope 可追踪。
- override 行为有 positive test 和 negative-control test。
- 被覆盖或降级的 candidate 仍可在 review/debug 输出中追踪。

如果这些条件不满足，只能使用 `supplement_only` 或 `review_required`。

## 7. Missing 与 Conflict States

P4A 继续沿用已有 missing states：

- `present`
- `absent`
- `not_surfaced`
- `out_of_scope`

并为 P4 场景增加以下状态或等价表达：

- `scope_not_surfaced`
  - 目标字段可能存在，但当前 structure/semantics 层没有稳定识别目标 entity scope 的表或区块。
- `scope_conflict`
  - 同一 metric/period 下存在 parent/consolidated 混淆风险。
- `source_conflict`
  - statement 与 note/disclosure 都有候选，但 policy 不允许自动裁决。
- `review_required`
  - 需要人工或 agent review 才能进入下游消费。
- `blocked`
  - 已确认违反 policy，不能进入 canonical/key facts。

这些状态的用途不是增加流程复杂度，而是避免用 candidate omission 掩盖事实：没有产出 fact 可能是不存在、未露出、scope 未识别、冲突待审，或明确被阻断。

## 8. Review Surface 最小要求

P4A 不要求完整 UI，也不要求 durable review workflow。但必须定义一个最小可审阅 surface，供 implementation plan 落地。

最小 review packet 应包含：

- `document_id`
- `period_id`
- `metric_id`
- `entity_scope`
- `source_kind`
- `source_policy`
- `conflict_state`
- `candidate_value`
- `competing_candidate_values`
- `evidence_bundle_id` 或等价 evidence reference
- `resolution_reason`
- `review_reason`

第一版可以是 internal service output、test-visible structure、CLI/export helper 或只读 HTTP endpoint。不要为了 P4A 提前设计大而全 review API。

## 9. P4B 字段接入规则

P4B 规划字段时，必须为每个字段或字段族声明：

- canonical metric identity
- Turtle alias
- expected entity scope
- allowed source kinds
- source policy mode
- missing/conflict state expectations
- positive evidence requirement
- negative controls
- 是否允许 locator-assisted note/disclosure

P4B 不得绕过 P4A policy 直接新增 note/disclosure extractor。

## 10. 建议 P4B 字段族

P4A 不实现这些字段，但为 P4B 预留以下字段族：

### 10.1 母公司口径字段

- 母公司 `cash` / Turtle alias `money_cap`
- 母公司 `lt_eqt_invest`
- 母公司借款类负债
- 母公司 `total_assets`
- 母公司 `total_liabilities`
- 母公司 `total_equity`

### 10.2 高价值附注桥接字段

- DPS / 分红方案
- 回购 / 注销
- 受限资金
- 定存 / 理财 / 高流动性金融资产
- 投资收益拆分
- 资产处置收益拆分
- 资本化研发
- 资本化利息
- 子公司现金归集限制

这些字段族进入 P4B 时，应优先选择少量最高频、最可验证、scope 最清楚的字段，不应一次性铺开。

## 11. 架构边界

P4A implementation plan 应优先落在以下边界，而不是新增孤立字段补丁：

- table model / table semantics
  - 识别或传播 statement scope。
- candidate fact builder
  - 保留 `entity_scope`、`statement_scope_guess`、source kind、source policy metadata。
- conflict resolver
  - 按 `metric_id + period_id + entity_scope + source_policy` 裁决。
- validation / quality gate
  - scope conflict、forbidden override、blocked candidate 不应被标记为生产级 pass。
- review/export surface
  - 暴露 P4A conflict packet。

不应把 P4A 逻辑塞进 `report/` forwarding 层。

## 12. Fallback 边界

P4A 允许保留 gated semantic locator，但边界比 P3 更严格：

允许：

- 判断一个已定位 note/disclosure block 是否属于受支持的 P4A/P4B source context。
- 在 bounded block 内辅助识别目标 metric label。
- 输出受限 JSON，包括 `metric_id`、`matched_label`、`source_text_span`、`semantic_confidence`、`fallback_reason`。

禁止：

- LLM 直接抽数。
- LLM 直接判断 final canonical fact。
- LLM 自由决定 parent vs consolidated scope。
- LLM 自由覆盖 statement-row fact。
- 全文泛扫后产出财务事实。

如果 fallback 参与 P4B 字段，必须有 trigger、budget、provenance 和 negative controls。

## 13. 测试策略

P4A 的测试应以 contract tests 为主：

- parent/consolidated scope classification tests
- `owners of the parent` negative-control tests
- source policy resolution tests
- supplement-only regression tests
- override-required-but-missing-policy blocked tests
- review packet shape tests
- P1-P3 statement-row precedence regression tests

真实 PDF 验证应聚焦少量已有锚点或明确新增的 P4A scope sample，不应在 P4A 阶段扩成大型 real-PDF matrix。

## 14. 验收标准

P4A 视为完成，仅当以下条件同时满足：

- parent vs consolidated 的 scope contract 已实现或至少可由 implementation plan 精确落地。
- `profit attributable to owners of the parent`、`equity attributable to owners of the parent` 等合并口径项目不会被误判成母公司报表口径。
- note/disclosure 默认只补缺。
- override 必须由字段 policy 显式开启。
- 未声明 override 的 note/disclosure conflict 会进入 `review_required`、`source_conflict` 或 `blocked`，不能静默 canonical promotion。
- scope 不稳定的 parent-field candidate 不进入 key Turtle input。
- P1-P3 的 statement-row precedence 和 note/disclosure supplement 回归不被破坏。
- 存在最小 review packet 或等价 surface，可审阅 scope/source conflict。
- P4B 可以基于本 spec 直接写字段 spec 与 implementation plan。

## 15. 建议实施顺序

后续 implementation plan 建议按以下顺序展开：

1. 建立 P4A policy model 与测试 fixture。
2. 补 entity scope contract tests，先压住 `owners of the parent` negative controls。
3. 传播 source kind 与 source policy metadata。
4. 更新 conflict resolver，使其按 policy 裁决 supplement、override、review 和 blocked。
5. 增加 validation / quality gate 对 scope/source conflict 的处理。
6. 暴露最小 review packet。
7. 跑 P1-P3 focused regressions，确认既有字段路径不回退。

## 16. 一句话收束

P4A 不是字段扩张阶段，而是进入母公司口径和高价值附注桥接前的治理契约阶段。只有 parent scope、source precedence、override policy、missing/conflict states 与 review surface 足够清楚，P4B 才应该开始扩字段。
