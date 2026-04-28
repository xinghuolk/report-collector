# 财报分析 Active 文档状态收口设计

> **状态:** Active reconciliation spec
> **日期:** 2026-04-28
> **范围:** 统一路线图、metric governance umbrella、架构分析与后续最小切片的状态对齐

## 1. 目的

当前代码已经完成 DB-backed 3-5Y data provider baseline，以及 metric governance
Phase 1 到 Phase 4B。部分 active 文档仍保留较早阶段的执行口径，例如 metric
governance umbrella 顶部仍保留旧的 Phase 1-only implementation target。

这会导致后续执行者误判：

- 把已完成的 Phase 1-4B 当成待实现范围；
- 从旧的 database、availability 或 workflow umbrella 继续派生重复 plan；
- 在 governance/source precedence 边界未重新确认前，直接启动新字段覆盖；
- 把 UI、async jobs、approval workflow 或 whole-document LLM assessment 当作当前
  gap，而不是 future scope。

本 spec 的目标是只做文档状态收口，不改变运行时代码。

## 2. 当前真实基线

截至当前分支：

- Turtle P2B、P3、P4A、P4B、P4C、P4D、P4E、P5 coverage 主线已完成。
- Storage-backed query、document ledger、DB-backed extraction persistence、
  extract-to-P5/Turtle orchestration、3-5Y availability baseline 已完成。
- Metric governance Phase 1-4B 已完成：
  - Phase 1：governance metadata 与 provisional guardrails；
  - Phase 2：metric governance review surface；
  - Phase 3：durable lifecycle registry；
  - Phase 4A：lifecycle workflow/review API；
  - Phase 4B：recompute audit、dry-run、controlled consumption。
- 架构分析已落在
  `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/`。

## 3. 文档收口策略

### 3.1 Unified roadmap

`2026-04-22-financial-report-analysis-unified-roadmap.md` 继续作为 handoff 入口。
它需要明确补充：

- metric governance Phase 1-4B 已完成；
- 当前不再处于 pre-P5 coverage 或 DB baseline 建设阶段；
- 下一步应先从 governance hardening、audit persistence、DB recompute boundary 或
  one-field onboarding 中选择最小切片；
- workflow product、approval state machine、UI、async job 和 whole-document LLM
  assessment 仍是 future scope。

### 3.2 Metric governance umbrella

`2026-04-25-financial-report-analysis-metric-governance-umbrella-design.md`
保留为架构 umbrella，但需要把状态从“Phase 1 immediate target”改为“Phase
1-4B implemented baseline”。

历史阶段说明不删除，因为它仍解释了为什么 guardrails、review surface、
lifecycle registry、workflow API 和 controlled consumption 分阶段推进。需要修正的是：

- 顶部 implementation target；
- Phase 1-only immediate implementation 的描述；
- durable lifecycle / Phase 4B 仍是 future 的过期措辞；
- 推荐下一步从 Phase 1 plan 改为 post-P4B 最小切片选择。

### 3.3 Active README

`docs/superpowers/specs/active/README.md` 仍应指向统一路线图作为 handoff 入口，
同时列出本 reconciliation spec，说明它是当前状态修正层。

## 4. 下一步候选切片

完成文档收口后，后续不应马上默认扩字段。推荐按以下顺序选择：

1. **Downstream governance hardening。**
   在 P5 dataset、Turtle export 和 availability read surfaces 增加显式
   governance assertions 或 filters，避免完全依赖 upstream canonical purity。

2. **Lifecycle recompute audit persistence。**
   持久化 audit snapshots 或 run-level metadata，让每次 dataset/Turtle output
   能说明受哪些 lifecycle decisions 影响。

3. **DB-backed recompute boundary。**
   明确 recompute 是 JSON-first + DB sync，还是 DB-native，避免长期保留含糊的
   双路径。

4. **One-field post-P5 onboarding。**
   从 gap list 选择一个字段族，先执行 sample-onboarding diagnosis，再决定是否
   扩展 deterministic semantics、registry mappings 或 review surfaces。

推荐优先级是 1。原因是它直接降低 silent-pollution 风险，且范围小于 audit
persistence 或 DB recompute boundary。

## 5. 非目标

本次文档收口不做：

- 代码实现；
- 新 API；
- 测试补充；
- 旧历史文档大规模迁移；
- umbrella 全文重写或翻译；
- workflow product / UI / async jobs 设计。

## 6. 完成标准

本次收口完成时：

- active roadmap 明确 Phase 1-4B 与 DB-backed baseline 已完成；
- metric governance umbrella 不再指向 Phase 1 implementation plan 作为下一步；
- active README 能解释 roadmap 与 reconciliation spec 的关系；
- 文档不含未解决占位符；
- git diff 不含 whitespace error；
- 变更以 focused docs commit 提交。
