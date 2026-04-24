# 财报分析统一路线图

> **状态:** 路线图 spec
> **日期:** 2026-04-22
> **范围:** 协调 `financial-report-analysis` 的长期演进路线，包括抽取底座、Turtle 输入覆盖、fallback 控制、metric 治理、API surface、storage、lineage 与 recompute。
> **生命周期:** Active roadmap. Historical specs and plans have been moved under `docs/superpowers/specs/archived/` and `docs/superpowers/plans/archived/`; still-relevant background lives under `docs/superpowers/specs/reference/`.

## 0. 当前状态快照

本文最初写于 2026-04-22，当天的“当前优先级”描述带有明显的阶段时序假设。随着后续实现推进，需要把真实状态单独钉住，避免执行者继续按旧节点判断下一步。

截至当前分支状态：

- `Turtle P2B Debt Inputs` 已完成并收口。
- `Turtle P3 Asset Quality` 已完成并收口。
- `Turtle P4A Parent Scope / Notes Conflict Governance` 已完成并收口。
- `Turtle P4B Cash-Health Notes Bridge` 已完成并收口。
- `Turtle P4C Investor Core Statement Gaps` 已完成并收口。
- `Turtle P4D Parent Scope And Notes Follow-up` 已完成并收口。
- `Turtle P4E Investor Earnings Quality And Capex Follow-up` 已完成并收口。
- `Turtle P5 Multi-Year Investor Dataset And Minimal Persistence` 已完成并收口。
- `Storage-Backed Query And Audit` 已完成并收口。
- `Document Ledger And Extraction-Run Persistence` 已完成并收口。
- `Storage-Backed API Runtime Slice` 已完成并收口。
- `DB-Backed Extract Persistence And Lookup Slice` 已完成并收口。
- `DB-Backed Extract To P5/Turtle Orchestration` 已完成并收口。
- `3-5Y Persisted Dataset Availability View` 已完成并收口，设计文档已归档。
- 旧的 `DB-Backed Extract Write Follow-Up` plan 已被后续 persistence / orchestration plans 取代，不应作为 active plan 继续执行。
- `new-report-sample-onboarding-and-field-variance-process.md` 不再只是补充说明，而应视为后续字段 phase 的正式前置方法约束。
- `2026-04-22-turtle-v015-financial-field-gap-analysis.md` 仍然是后续 coverage 需求的重要来源，但当前分支已经不再处于 pre-P5 的字段扩张阶段。
- `docs/superpowers/specs/reference/2026-04-19-financial-report-analysis-phase2-roadmap.md` 仍是抽取底座原则参考，但不是当前执行计划。
- `docs/superpowers/specs/reference/2026-04-23-financial-report-analysis-core-database-architecture-planning.md` 仍是更长期 fact-ledger / metric-governance / DB 架构方向参考。
- `docs/superpowers/specs/reference/2026-04-23-financial-report-analysis-turtle-post-p4-coverage-roadmap.md` 仍保留 post-P5 enhancement candidates，但 pre-P5/P4C/P4D/P4E/P5 主线已经完成。

因此，当前推荐的下一步不再是继续新开 `P4x` / `P5` coverage phase，也不再是补数据库数据提供能力。当前可收口为：

`DB-backed 3-5Y data provider baseline complete`

这条已完成基线包括：

- 单年年报 PDF 经 `/api/v1/analysis/extract` 抽取并持久化。
- extracted artifact / dataset / turtle / review / lineage 可通过 storage-backed surface 查回。
- 3-5 年 read-only availability/data view 能基于已持久化 facts 返回 coverage、missing states、audit 与 lineage。
- 查询路径不触发 PDF extraction、recompute、dataset build 或 Turtle build。

同时，应把以下内容明确视为 future/out of current scope，而不是当前未完成项：

- 3-5Y workflow run / job 状态表。
- 缺失年份自动发现、自动补抽、自动 retry/rebuild。
- recompute / stale 策略落库与产品化生命周期。
- 正式 3-5Y workflow product artifact 生命周期。
- approval/review workflow 的完整状态机。
- whole-document LLM assessment / diff review。

截至当前分支，这条数据库线的 `core baseline` 已经不再是待规划项，而是已实现基线：

- durable core models
- JSON / DB repository parity
- minimal historical ingestion registry
- minimal review / lineage / recompute persistence

因此，下一步不宜再从数据库 umbrella spec、availability spec 或 workflow umbrella spec 直接写新的 implementation plan。只有当出现新的明确业务目标时，才从下面这些 future buckets 中选择一个最小切片：

- Metric governance 与 custom/provisional lifecycle：把 registry 状态、review decision、canonical promotion 的长期方向拆成小的可验证 slice。
- Post-P5 enhancement coverage：从 reference roadmap 里选择明确字段族，按样本接入流程验证是否值得进入新 coverage phase。
- Whole-document LLM assessment / diff review：只作为 review artifact，不进入 canonical facts 或 deterministic recompute 裁决链。
- 3-5Y workflow/products：只有在业务明确需要自动补齐、job 状态、product artifact 生命周期或 approval workflow 时再启动。

## 1. 目的

本文定义 `financial-report-analysis` 的顶层路线图。

需要这份路线图，是因为当前项目已经形成多条合理但相互交叠的计划线：

- Phase-2 抽取底座与 table-driven canonical facts
- Turtle 投资输入覆盖
- 受限 Ollama 语义兜底
- custom / provisional metric 治理
- API、review、storage、lineage 与 recompute 能力
- 新财报样本接入与字段差异处理

这些计划线各自都有价值，但任何单个文档都不应该被当作整个项目的唯一真相。本文作为这些文档之上的决策层，用来判断下一步到底应该继续扩字段、补底座、补治理，还是先收口当前阶段。

## 2. 总目标

`financial-report-analysis` 应该演进为一个可持续扩展的财报事实抽取与分析输入服务。

目标不是为了通过某一个样本、支持某一个公司，或不断堆孤立的 metric alias。目标是建立一条可复用、可验证、可追溯的主路径：

```text
pdf
-> structure recovery
-> normalized table semantics
-> metric mapping / metric identity governance
-> candidate facts
-> canonical facts
-> validation / derivation
-> reviewable and exportable analysis inputs
```

服务应能产出稳定、可追溯、可校验的财报事实，支撑 Turtle 等下游投资分析流程，同时保持足够通用，未来可以扩展到更多财报格式家族。

## 3. 现有计划线

### 3.1 基础架构线

主要文档：

- `docs/superpowers/specs/2026-04-18-financial-report-analysis-design.md`
- `docs/superpowers/specs/2026-04-18-financial-report-analysis-data-model-design.md`
- `docs/superpowers/specs/2026-04-18-financial-report-analysis-integration-design.md`
- `docs/superpowers/plans/2026-04-18-financial-report-analysis-implementation-plan.md`

作用：

- 建立独立 analysis service。
- 保持 `report/` 只承担 forwarding 与兼容入口职责。
- 定义 candidate、canonical、derived、validation、evidence、registry、storage 与 quality gate 等基础概念。

当前解读：

- 基础服务形态与 pipeline 主流程已经落地。
- 但更深的数据模型能力仍不完整，尤其是 custom metric lifecycle、durable registry state、review surface、lineage 与 recompute。

### 3.2 Phase-2 抽取底座线

主要文档：

- `docs/superpowers/specs/2026-04-19-financial-report-analysis-phase2-roadmap.md`
- `docs/superpowers/plans/2026-04-19-financial-report-analysis-table-structure-implementation-plan.md`
- `docs/superpowers/plans/2026-04-19-financial-report-analysis-table-semantic-canonical-implementation-plan.md`
- `docs/superpowers/plans/2026-04-20-financial-report-semantic-recovery-and-normalization-implementation-plan.md`
- `docs/superpowers/plans/2026-04-20-financial-report-extraction-and-semantic-fallback-phase2-implementation-plan.md`

作用：

- 把抽取能力从轻量文本匹配推进到 table-driven structure 与 semantics。
- 稳定 table kind、header、period、unit、currency、row label、row-value binding 与 evidence。
- 保持 LLM 只做受限语义辅助。

当前解读：

- 这是后续所有字段扩展的工程底座。
- 后续字段工作不应绕过这条主线去增加 issuer-specific 分支或全文字符串补丁。

### 3.3 Turtle 输入覆盖线

主要文档：

- `docs/superpowers/plans/2026-04-21-financial-report-analysis-turtle-investment-input-coverage-master-plan.md`
- `docs/superpowers/specs/2026-04-21-financial-report-analysis-turtle-core-investor-inputs-design.md`
- `docs/superpowers/plans/2026-04-21-financial-report-analysis-turtle-core-investor-inputs-implementation-plan.md`
- `docs/superpowers/specs/2026-04-21-financial-report-analysis-turtle-working-capital-p2a-design.md`
- `docs/superpowers/plans/2026-04-21-financial-report-analysis-turtle-working-capital-p2a-implementation-plan.md`
- `docs/superpowers/specs/2026-04-22-financial-report-analysis-turtle-debt-inputs-p2b-design.md`
- `docs/superpowers/plans/2026-04-22-financial-report-analysis-turtle-debt-inputs-p2b-implementation-plan.md`

作用：

- 把 table-driven 抽取底座转化为投资框架真正可消费的输入字段。
- 按字段族推进，而不是按公司推进。
- statement-row facts 保持主路径。
- note / disclosure supplement 只在主表路径没有露出目标 metric 时补缺。

当前解读：

- Turtle 是重要下游消费者，也是合理的优先级来源。
- 但 Turtle 不应成为唯一架构视角。Turtle 字段覆盖暴露出的 registry、review、lineage、storage 缺口，应单独规划，而不是隐藏进下一轮字段扩展。

### 3.4 Fallback 控制线

主要文档：

- `docs/superpowers/specs/2026-04-20-ollama-real-report-probe-promotion-design.md`
- `docs/superpowers/plans/2026-04-20-ollama-real-report-probe-promotion-implementation-plan.md`
- `docs/superpowers/specs/2026-04-21-real-pdf-ollama-fallback-performance-assessment.md`
- `docs/superpowers/plans/2026-04-21-real-pdf-ollama-fallback-gating-performance-fix-implementation-plan.md`

作用：

- 让 Ollama 保持为受控的语义歧义判别器。
- 统计 fallback 调用次数，避免真实 PDF 验证被 runaway fallback 拖垮。
- 只把稳定 fallback case 提升为 always-on regression。

当前解读：

- Fallback 可以辅助 table kind、row label、disclosure locator 等歧义判别。
- Fallback 不应直接抽数、不应自由传播 unit、不应生成 canonical facts，也不应替代 deterministic registry matching。

### 3.5 Governance / Review / Persistence 线

主要文档：

- `docs/superpowers/specs/2026-04-18-financial-report-analysis-data-model-design.md`
- `docs/architecture-analysis/2026-04-22-financial-report-analysis-architecture-gap-assessment.md`

作用：

- 把 provisional 与 custom metric 行为推进成受控生命周期。
- 为 unsupported 或 provisional facts 增加可 review 的 surface。
- 在有明确使用场景时，从 memory-first evidence / fact handling 逐步走向 durable lineage 与 recompute。

当前解读：

- 这不再只是远期背景架构。
- 随着字段覆盖扩大，governance 是防止 key facts 与自动分析输出被静默污染的必要护栏。

### 3.6 样本接入线

主要文档：

- `docs/architecture-analysis/new-report-sample-onboarding-and-field-variance-process.md`

作用：

- 把新公司样本视为“格式家族锚点”，而不是 issuer-specific 分支理由。
- 按 structure、semantics、registry、candidate builder、canonical promotion、API exposure 或当前 phase scope 归类失败原因。
- 保留清晰的缺失状态，例如 `present`、`absent`、`not_surfaced` 与 `out_of_scope`。

当前解读：

- 每当新真实 PDF 看起来需要特殊处理时，都应该先走这套流程。
- 这套流程应帮助判断修复应该归入当前 phase、后续 Turtle phase、governance，还是抽取底座。

## 4. 工作流划分

项目应按五条相互协调的 workstream 管理。

### 4.1 Extraction Foundation

目的：

- 以可复用方式恢复财报结构与归一化语义。
- 让 table-driven extraction 始终领先于字段级补丁。

典型交付物：

- table source recovery
- table classification
- header / period / unit / currency parsing
- row-label normalization
- table fact builder behavior
- candidate / canonical stability

### 4.2 Turtle Input Coverage

目的：

- 按现实可用的顺序提供投资分析可消费的财报输入。
- 只有当底座能在不引入公司特例的情况下支撑某个字段族时，才推进该字段族。

阶段顺序：

1. Core Investor Inputs
2. Working Capital And Debt Inputs
3. Asset Quality And Capital Allocation Inputs
4. Parent Scope And Notes Bridge
5. Multi-Year Investor Dataset

### 4.3 Metric Governance

目的：

- 区分 deterministic mapping definitions、metric identity 与 provisional custom metric lifecycle。
- 防止 unsupported 或 provisional metrics 静默进入 key facts、ratios、TTM 或自动分析。

近期重点：

- 澄清 registry 角色
- 传播 registry status
- 在自动消费前阻断或 review provisional metrics
- 暴露 provisional metric candidates 供 review

### 4.4 Fallback Control

目的：

- 保持 deterministic-first，同时允许在确定性证据存在歧义时做有限语义辅助。

必须具备的控制：

- 明确 trigger
- 受限 output space
- budget
- provenance
- real-PDF probe promotion criteria
- negative controls

### 4.5 Review / API / Storage / Lineage / Recompute

目的：

- 让抽取出的 facts 可审计、可 review、可导出，并最终可重算。

近期立场：

- 不要把 `/api/v1/analysis/extract` 变成全能 API。
- 当用例需要时，增加独立 review 或 query surface。
- 重型 storage 可以等到有具体工作流后再做，但要保留关系型概念：registry rows、pipeline runs、fact sets、evidence links、validation issues。

## 5. 当前优先级

截至当前，推荐顺序如下：

1. **先承认 pre-P5 coverage 已经完成，再切换 active phase。**
   - 当前分支里，P2B、P3、P4A、P4B、P4C、P4D、P4E、P5 都已经进入已完成状态。
   - 下一步不应继续按“还有哪个字段 phase 没开”来判断，而应转入 post-P5 基础设施阶段。

2. **承认 DB-backed data provider baseline 已完成。**
   - 当前不是“还有数据库层没做完”，而是单年抽取持久化与 3-5 年只读数据提供已经形成闭环。
   - availability view 已完成并归档；不要再围绕同一目标新开 active spec。

2.1 **把 workflow/products 明确后置为 future scope。**
   - 当前业务暂不需要 job 状态表、自动补齐、recompute 生命周期、product artifact 生命周期或 approval workflow。
   - 这些能力只在后续业务明确要求时再做 focused spec。

3. **保持 recompute core 为 deterministic。**
   - recompute 的主逻辑应只依赖 manifest、persisted extracted artifacts、dataset assembly rules 和版本化 contract。
   - LLM 不应参与 recompute 裁决，也不应直接改写 canonical facts。

4. **把 LLM whole-document assessment 作为后续扩展，而不是当前阻塞项。**
   - 如果未来需要整份 PDF 对照评估，应作为 review / diff artifact 的可插拔扩展。
   - 它可以帮助发现系统漏抽、误抽和 scope 冲突，但不应成为主事实来源。
   - 这条能力应在总路线中保留正式位置，但默认排在 review / lineage / deterministic recompute 之后。

5. **不要把 future workflow 当作当前 gap。**
   - 当前最小数据提供目标不要求 async job handle、自动 acquisition、approval workflow 或产品生命周期。
   - gap 文档中的 workflow/product 内容应作为 future bucket 参考，不作为当前阻塞项。

6. **后续新增字段 phase 必须建立在 post-P5 基础设施之上。**
   - 如果后面还要继续承接 `v0.15` gap list、parent scope 深挖或 broad notes bridge，应先有 review / lineage guardrails。
   - 否则新字段只会继续增加不可审计、不可重算的状态债务。

## 6. 暂停门槛

出现以下任一情况时，不应继续做大范围字段扩展。

### 6.1 Foundation Gate

如果出现以下情况，应暂停并修复抽取底座：

- 目标 facts 需要 issuer-specific 代码分支
- row-value binding 不稳定
- period、unit 或 currency 依赖宽泛文档上下文推断，而不是局部 table context
- table kind 或 statement scope 的歧义已经无法支撑目标字段族

### 6.2 Governance Gate

如果出现以下情况，应暂停并修复 metric governance：

- provisional 或 custom metrics 可以进入 `key_facts`
- provisional 或 custom metrics 可以在未经 review 的情况下影响 ratios、TTM、derived facts 或自动分析
- 新工作使 `MetricRegistry` 与 `MetricMappingRegistry` 的职责变得不清楚
- 新字段族需要 unsupported metric identities，但这些 identities 无法 review 或分类

### 6.3 Fallback Gate

如果出现以下情况，应暂停并修复 fallback control：

- Ollama calls 按全量 rows 扩张，而不是由明确 ambiguity trigger 触发
- fallback output space 在没有测试与 negative controls 的情况下扩大
- fallback 返回 values 或 canonical facts
- fallback 缺少 budget 或 provenance
- live real-PDF validation 因 fallback 过宽而变得不可实践

### 6.4 Source Precedence Gate

如果出现以下情况，应暂停并设计 conflict governance：

- note / disclosure candidates 覆盖 statement-row facts
- summary tables 在没有明确 precedence 规则的情况下覆盖 primary statements
- parent-company facts 与 consolidated facts 混淆
- 当前缺失状态无法区分 `absent`、`not_surfaced`、`unknown` 与 `out_of_scope`

### 6.5 API / Persistence Gate

如果出现以下情况，应暂停并设计 review 或 storage surface：

- 重要 review 决策只存在于 logs 或临时测试输出
- provisional metric candidates 需要人工或 agent review，但没有稳定 surface
- multi-year output 需要当前 extract responses 无法表达的 fact-set versioning
- recompute 或 audit 已经成为正确性声明的必要条件

## 7. 文档优先级规则

当计划文档之间出现冲突时，按以下优先级判断：

1. 本统一路线图
2. 当前选定 workstream 的 active master plan
3. active phase spec
4. active implementation plan
5. handoff prompts 与 process notes
6. historical plans 与已完成任务记录

这并不意味着旧文档失效。旧文档仍然用于理解原始意图、架构理由和已知约束。上述优先级只用于解决“两个文档暗示不同下一步”时的决策问题。

## 8. 新工作决策规则

创建新的 spec 或 implementation plan 前，先按顺序回答这些问题：

1. 当前是否已有 active phase 正在进行？
2. 该 phase 是否需要先 closeout、review 或 verification，才能开始新的字段工作？
3. 新工作是在强化 extraction foundation、扩展 Turtle coverage、增加 governance，还是增加 API/storage 能力？
4. 新工作是否触发任何 pause gate？
5. 这项工作更适合作为 field phase、foundation fix、governance phase，还是 sample-onboarding diagnosis？

默认判断：

- 如果已有 active implementation plan 且仍然自洽，先完成或明确暂停它，再启动新计划。
- 如果新样本暴露 structure recovery 失败，先修 structure，不要先加 aliases。
- 如果新样本暴露 in-scope 字段的 unsupported labels，先补 deterministic semantics 与 registry，再考虑 fallback。
- 如果字段不属于当前 phase，记录到正确的未来 phase，不要顺手塞进当前阶段。
- 如果 provisional metrics 开始影响自动输出，应优先补 governance，再继续扩字段。

## 9. 近期路线

### Milestone A: P2B Debt Inputs Closeout

预期结果：

- `st_borr`、`lt_borr`、`bond_payable` 与 `non_cur_liab_due_1y` 在选定 CN/HK 锚点上稳定。
- statement-row facts 保持 source precedence。
- HK mixed-structure note/disclosure support 只补缺失的 debt metric IDs。
- 既有 P2A 与 Phase 1 Turtle inputs 继续通过定向回归。

### Milestone B: Extension Metric Governance Phase 1

预期结果：

- registry roles 被明确命名和记录。
- candidate 与 canonical metadata 在需要时保留 registry status。
- provisional custom metrics 被阻止进入 key facts 与自动分析，或强制进入 review。
- 一个小型 review/export surface 可以带 evidence 暴露 provisional metric candidates。

### Milestone C: Turtle Phase 3 Asset Quality

预期结果：

- 只有 governance guardrails 存在后，才新增 asset-quality 与 capital-allocation 字段。
- main-statement path 保持主路径。
- 字段增加不会失控扩大 fallback。

### Milestone D: Parent Scope And Notes Bridge Design

预期结果：

- parent vs consolidated scope 有明确 contract。
- broad note/disclosure bridge 实现前，先有 conflict governance。
- source precedence 与 missing states 可测试。

### Milestone D1: Cash-Health Notes Bridge

预期结果：

- 在 P4A 治理 contract 之上，先引入受限的现金健康度附注桥接字段。
- 第一批字段限定为 `restricted_cash`、`interest_paid_cash`、`time_deposits_or_wealth_products`。
- 每个字段都必须带有 sample onboarding expectation、source policy、missing/conflict expectation 与 negative controls。
- 不在这一里程碑里顺手扩张成 broad parent-scope statement coverage 或 narrative policy parsing。

### Milestone E: Multi-Year Dataset Readiness

预期结果：

- 在实现 multi-year extraction 前，先定义 export schema、period semantics、fact-set versioning、quality markers 与最小 persistence。

### Milestone F: Post-P5 Review / Lineage / Recompute Foundation

预期结果：

- extracted artifact、dataset artifact 与 Turtle export 都有可审阅的 review surface。
- artifact 之间存在清晰的 lineage contract，可回答“这条 dataset row 来自哪些 extracted artifacts / source PDFs / pipeline versions”。
- recompute 使用 deterministic contract，可在 manifest、artifact version 或 pipeline version 变化时稳定重建目标 artifact。
- 当前 JSON repository 之上已有足够的 review / lineage / recompute 结构，不必先引入数据库。
- 若未来引入 whole-document LLM assessment，它只能作为 review / diff 扩展，不进入 recompute 主裁决链路。

### Milestone F1: Post-P5 Foundation Closeout As Storage Prerequisite

预期结果：

- `review surface`、`lineage contract` 与 `recompute diff / target-selection contract` 达到数据库阶段可复用的稳定形态。
- 当前 JSON repository 仍然是实现载体，但 contract 层已经足够稳定，可以被未来数据库 repository 直接承接。
- phase 输出应能明确回答：
  - 哪些 artifact / row / export objects 需要持久化
  - 哪些 review / lineage / recompute fields 是 durable schema 的必备字段
  - 哪些字段仍然只是可选增强，不应阻塞 storage 阶段

### Milestone F2: Durable Storage And Query Foundation

预期结果：

- 在不改写上层 contract 的前提下，引入数据库或更重的 durable storage abstraction。
- repository / query / audit / recompute 入口切换到底层持久化实现时，不改变 review / lineage / recompute 的业务规则。
- storage 层开始承接关系型概念：
  - pipeline runs
  - extracted artifacts
  - dataset artifacts
  - export artifacts
  - review surfaces
  - lineage links
  - recompute events / diff summaries

当前状态：

- 已完成 DB-backed extract persistence / lookup、document ledger、storage-backed API runtime、query/audit、extract-to-P5/Turtle opt-in build，以及 3-5Y persisted dataset availability view。
- 对当前“单纯数据提供”业务而言，Durable Storage And Query Foundation 已经足够收口。

### Milestone F3: 3-5Y Persisted Data Provider Closeout

当前状态：

- 单年年报 PDF 可以抽取并持久化为 extracted artifacts。
- 已持久化的 dataset / turtle / review / lineage surface 可以读回。
- 3-5Y availability/data view 可以按 issuer/year range 返回 persisted facts、missing states、coverage explanation 与 lineage。
- 该里程碑不包含 workflow run/job 状态、自动补齐、recompute 生命周期、正式 workflow product artifact 生命周期或 approval workflow。

### Milestone G: Whole-Document LLM Assessment Extension

预期结果：

- 能对整份 PDF 形成受限的 `assessment / comparison artifact`。
- 能把系统抽取结果与 LLM 文档级观察做结构化 diff。
- 该能力只服务 review、gap detection 与差异摘要，不直接改写 canonical facts。
- 该能力不进入 deterministic recompute 主链，只作为可插拔评估扩展存在。

## 10. 非目标

本文不做以下事情：

- 不替代当前 active P2B plan。
- 不要求立即实现所有 workstreams。
- 不要求在下一个字段 phase 前做大型 storage 重写。
- 不要求现在就详细规划所有 Turtle phases。
- 不让 Ollama 成为主抽取器。
- 不授权 issuer-specific 分支。
- 不把 `report/` 重新变成 financial analysis 的实现 owner。

## 11. 执行原则

项目应按这个可重复循环推进：

```text
pick one active phase
-> verify it still aligns with the unified roadmap
-> implement or close the phase
-> run focused verification
-> check pause gates
-> either continue field coverage or pay down the blocking foundation / governance gap
```

最重要的纪律是：不要把“下一个字段族”误认为“下一步最合理的工程动作”。只有当 extraction foundation、governance、fallback controls 与 review surfaces 足够稳时，字段覆盖才应该快速推进。

## 12. 当前最小全流程验证定义

截至 2026-04-24，单报告级的 `HTTP -> DB -> dataset/turtle -> readback` 竖切和 3-5 年 persisted dataset availability view 都已经完成。当前最小全流程定义为已实现基线，而不是新的 active spec 输入。

已完成的最小全流程为：

```text
issuer + fiscal-year range
-> availability planning
-> reuse existing persisted extracted artifacts
-> identify missing / stale / recompute-needed years
-> assemble available 3-5Y data view
-> return facts, missing states, audit, lineage
-> read back through storage-backed API/read surface
```

该验证的核心不是“所有年份都必须已经可抽取”，而是系统必须清楚说明：

- 哪些年份已经覆盖。
- 哪些年份缺少 report 或 extracted artifact。
- 哪些年份需要 recompute。
- 哪些 source artifact / audit / lineage 对象已经持久化并可查回。

这一轮真实 PDF 仍然重要，但只作为 seed 输入。推荐 anchor 是 `01810`、`09987` 和 `601919`：先从这些 PDF 预提取并写入持久化层，再用 availability view 查询已持久化数据。

`financial-report-analysis-3-5y-persisted-dataset-availability-view-design` 已完成并归档。真实 PDF 可继续作为 seed smoke test，但 availability correctness 的第一层验证应使用 seeded DB / mocked extracted artifacts，避免每次收口都被完整 real-PDF matrix 和 Ollama fallback 成本拖住。

在没有新增业务目标前，不需要新的 active implementation plan。
