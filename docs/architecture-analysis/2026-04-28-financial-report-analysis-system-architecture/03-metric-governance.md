# 指标治理架构

## 治理流程

```text
table semantics
-> MetricMappingRegistry.match()
-> supported candidate fact
-> FactNormalizer
   -> MetricRegistry.resolve_metric()
   -> extensions.metric_governance
-> ConflictResolver guardrails
-> provisional review item
-> review decision or lifecycle decision
-> lifecycle recompute audit
-> explicit recompute with controlled consumption
-> dataset / Turtle rows with lifecycle provenance
```

## 注册表边界

`registries/metric_mapping.py::MetricMappingRegistry` 是确定性 mapping 层。
它根据 table kind、normalized row label、period shape 和 market 映射到
supported standard metric ids。它不生成 custom ids，也不持久化 lifecycle
state。

`registries/metric_registry.py::MetricRegistry` 是 identity 层。它在可能时将
raw labels 解析到 known standard identities，否则生成稳定的
`custom::...` provisional ids。按 umbrella spec 的概念，它承担的是
`MetricIdentityRegistry` 角色。

`registries/metric_governance.py` 生成 governance metadata。Standard metrics
允许自动分析；provisional custom metrics 携带 review metadata，并被阻断进入
自动分析。

## Phase 1 护栏

`services/fact_normalizer.py::FactNormalizer.normalize_candidates` 将
`extensions.metric_governance` 写入 candidate facts。

`services/conflict_resolver.py::ConflictResolver.resolve_with_review` 阻断
provisional custom metrics 的 canonical promotion，并生成
`provisional_metric_review_required` review packets。

`adapters/report_adapter.py::ReportAdapter` 排除 `auto_analysis_allowed=false`
的 facts，防止它们进入 key facts 和下游 API 输出。

这些 guardrails 处理的主要污染路径是：

```text
unknown metric
-> provisional custom identity
-> canonical promotion
-> key facts / derived facts / Turtle
-> downstream treats it as stable
```

## Phase 2 审阅面

`services/metric_governance_review.py::MetricGovernanceReviewService` 扫描
persisted extracted artifacts 中的 provisional candidate facts，并输出
`MetricGovernanceReviewItem` records。

Phase 2 的 lightweight review decisions 使用
`models/governance.py::MetricGovernanceDecision`，decision types 包括
`keep_provisional` 和 `map_to_standard`。

这一层是 advisory，并不是 durable lifecycle state machine。

## Phase 3 生命周期注册表

`services/metric_lifecycle.py::MetricLifecycleService` 实现 durable lifecycle
state。它负责创建或加载 lifecycle entries、将 candidates 链接到 entries、
记录 decisions，并校验 actor/reason/evidence/target metric shape。

Storage tables 位于 `storage/models.py`：

- `MetricLifecycleEntryRecord`；
- `MetricLifecycleDecisionRecord`；
- `MetricLifecycleCandidateLinkRecord`。

Lifecycle states：

- `provisional`；
- `approved_custom`；
- `mapped_to_standard`；
- `deprecated`；
- `blacklisted`。

## Phase 4A 工作流 API

`api/routes.py` 暴露 review-item scoped lifecycle workflow endpoints：

- create or load lifecycle entry；
- link candidate to lifecycle entry；
- record lifecycle decision；
- read review items with embedded lifecycle state。

Phase 4A 有意不改变自动输出。

## Phase 4B 审计与受控消费

`services/metric_lifecycle_recompute.py` 构建 lifecycle recompute audit views。
它报告 linked lifecycle decisions 是否需要 recompute；在 dry-run 模式下，
还会报告 consumption 会 map、suppress、skip 还是 conflict。

`services/metric_lifecycle_consumption.py` 以 in-memory overlay 形式应用
controlled consumption。它不修改 stored extracted artifacts。

Consumption rules：

- `mapped_to_standard`：当不存在匹配 target canonical fact 时，可从 linked
  candidate 合成 standard canonical fact。
- `already_present`：不重复添加。
- `conflict`：不覆盖。
- `missing_candidate` / `missing_target`：不修改输出。
- `blacklisted`：在 governed view 中 suppression 匹配的 custom canonical facts。
- `approved_custom`、`deprecated`、`provisional`：Phase 4B 中不改变自动输出。

Controlled consumption 将 provenance 写入：

```text
extensions.metric_governance.lifecycle_consumption
```

## 当前状态

已完成：

- governance metadata contract；
- provisional custom guardrails；
- metric governance review item API；
- durable lifecycle registry；
- lifecycle workflow API；
- lifecycle recompute audit API；
- controlled consumption overlay；
- lifecycle recompute reason 与显式 fail-fast audit requirement；
- dataset/API/Turtle lifecycle provenance。

## 风险与边界

- `MetricMappingRegistry` 和 `MetricRegistry` 的名字仍容易混淆。
- Phase 2 decisions 与 lifecycle decisions 并存；Phase 2 decisions 应保持
  advisory，不应被推断为 lifecycle state。
- Lifecycle impact 只通过 explicit candidate links 传递；raw label 或 fuzzy
  matching 被有意排除。
- `approved_custom` 还没有自动输出合同。
- `blacklisted` suppression 当前使用 candidate metric id；后续可能需要更细粒度
  suppression。

## 建议的后续切片

- 对齐 `MetricMappingRegistry` 与 `MetricRegistry` 的命名和文档。
- 明确定义 `approved_custom` 输出合同，或继续保持 review-only。
- 如果输出 provenance 需要 durable run-level audit，则持久化 lifecycle
  recompute audit snapshots。
- 如果真实数据出现过度 suppression，再增加更细粒度 blacklist suppression keys。
