# 财报分析 Downstream Governance Hardening 设计

> **状态:** Active design spec
> **日期:** 2026-04-28
> **范围:** P5 dataset、Turtle export、3-5Y availability 的 metric governance 消费边界

## 1. 目的

当前系统已经完成 metric governance Phase 1-4B。上游路径已经能为 facts 附加
`extensions.metric_governance`，并能通过 lifecycle recompute controlled
consumption 显式改写 output。

剩余风险在下游消费层：

```text
polluted canonical fact
-> P5 dataset present row
-> Turtle export row
-> availability present metric
-> downstream treats value as stable input
```

当前 `ReportAdapter` 会排除 `auto_analysis_allowed=false` 的 facts，但
`p5/dataset.py`、`p5/turtle_export.py` 和 `p5/availability.py` 仍主要信任
`canonical_facts`。如果 polluted canonical fact 通过其他路径进入 extracted
artifact，下游仍可能把它当成 `present`。

本 spec 的目标是增加显式 downstream governance guardrails。它不新增字段，不改变
extraction，不引入 UI / async jobs / approval workflow。

## 2. 当前消费路径

### 2.1 P5 dataset

`p5/dataset.py::assemble_dataset` 当前从每个 artifact 的 `canonical_facts` 直接生成
`P5DatasetRow(missing_status="present")`。它会传播
`metric_governance.lifecycle_consumption`，但没有先验证该 fact 是否允许自动分析。

### 2.2 Turtle export

`p5/turtle_export.py::build_turtle_export` 当前从 dataset rows 直接生成 Turtle rows，
并做 canonical metric id 到 Turtle field 的 alias mapping。它没有独立治理策略。

### 2.3 Availability

`p5/availability.py::build_multi_year_availability_view` 当前扫描 persisted
`canonical_facts`，只要 required metric id 命中，就把 metric 标记为 `present`。
它没有检查 `metric_governance.auto_analysis_allowed` 或 lifecycle suppression。

## 3. 设计原则

1. **Dataset 是主要消费门。**
   P5 dataset 是 Turtle export 的上游，应在 dataset assembly 处先过滤不允许自动消费
   的 facts。

2. **Turtle 不重新裁决治理。**
   Turtle export 应继承 dataset rows，不直接读取 extracted artifact 或自行判断
   lifecycle state。它可以增加防御性断言，但不应成为第二套治理引擎。

3. **Availability 必须独立防御。**
   Availability 不一定经过 dataset assembly，因此它也必须在 present 判定前检查
   fact 是否允许自动分析。

4. **缺少 governance metadata 默认不允许。**
   新路径应 fail closed。没有 `metric_governance` metadata 的 fact 不应被当成
   自动分析可用值，除非实现明确处于 backward-compatibility mode，并把该模式写入
   quality summary / warning。

5. **Controlled consumption 是唯一允许的 lifecycle output overlay。**
   `mapped_to_standard`、`blacklisted` 等 lifecycle 影响只能通过 Phase 4B 的显式
   recompute/audit/consumption provenance 进入下游。下游不得从 raw labels、review
   decisions 或 metric id prefix 自行推断 lifecycle impact。

## 4. 方案对比

### 4.1 方案 A：在 dataset、Turtle、availability 各自实现过滤

优点是局部直观，改动小。缺点是三处规则容易漂移，后续 lifecycle state 增加时容易
漏更新。

### 4.2 方案 B：新增共享 downstream policy helper，三处调用

优点是规则集中、测试清晰、未来可扩展。P5 dataset 和 availability 都调用同一个
`is_downstream_consumable_fact(...)`；Turtle export 只对 dataset rows 做防御性检查。

缺点是会新增一个小的 policy module，需要明确它只消费 fact metadata，不访问
repository 或 lifecycle service。

### 4.3 方案 C：只依赖 upstream canonical purity

优点是零改动。缺点是它正是当前风险来源，无法抵御 polluted canonical fact 进入
artifact 的情况。

推荐采用 **方案 B**。

## 5. 目标行为

### 5.1 Consumable fact 判断

新增共享 policy helper，输入为 canonical fact dict，输出为：

- `allowed: bool`
- `reason: str`
- `governance_metadata: dict`

允许条件：

- `extensions.metric_governance.auto_analysis_allowed is True`；或
- 存在 Phase 4B `lifecycle_consumption` provenance，且 consumption action 明确是
  允许输出的 action，例如 `map_to_standard`。

阻断条件：

- `auto_analysis_allowed is False`；
- `metric_namespace == "custom"` 且未经过明确 controlled consumption；
- `registry_status in {"provisional", "deprecated", "blacklisted"}` 且未经过明确
  allowed overlay；
- 缺少或 malformed `metric_governance` metadata。

### 5.2 P5 dataset 行为

`assemble_dataset` 应只把 consumable facts 生成 `present` rows。

被阻断 facts 不应消失在审计之外。dataset `quality_summary` 应增加 blocked
governance 摘要，例如：

```text
governance_blocked_fact_count
governance_blocked_by_metric
governance_blocked_by_reason
governance_blocked_source_fact_ids
```

如果 required metric 只有 blocked fact，没有 consumable fact，则 missing row 应按现有
missing_status 逻辑生成；若 artifact metadata 声称该 metric `present`，仍应降为
`not_surfaced`，不能输出 `present` row。

### 5.3 Turtle export 行为

Turtle export 继续只消费 dataset rows。

防御性规则：

- 不导出 `missing_status != "present"` 的值类 row 为稳定值；
- 如果 dataset row 带有 governance blocked marker，则拒绝导出或保留为 non-present
  diagnostic row；
- 保留 `lifecycle_consumption` provenance。

Turtle export 不应读取 raw artifact，也不应重新执行 lifecycle lookup。

### 5.4 Availability 行为

Availability 在 required metric present 判定前必须调用同一 policy helper。

如果 required metric 只有 blocked fact：

- 不返回 `status="present"`；
- 返回 `status="unknown"` 或 `missing_metric`，优先沿用 artifact missing status；
- 在后续 implementation plan 中可以选择增加 blocked reason diagnostic，但本 slice 的
  最小目标是先防止 false-present。

### 5.5 Backward compatibility

当前测试 fixtures 里可能存在没有 `metric_governance` metadata 的 canonical facts。实现
计划需要显式决定：

- 生产路径 fail closed；
- 测试 fixtures 更新为带 standard governance metadata；
- 如需短期兼容旧 artifacts，只允许在显式参数或 migration helper 下打开，不作为默认
  dataset / availability 行为。

## 6. 非目标

本 slice 不做：

- 新 Turtle 字段；
- `gross_profit` / SG&A / 非经常性损益覆盖；
- lifecycle approval workflow；
- async job orchestration；
- UI；
- DB-native recompute 重构；
- historical artifact migration；
- LLM 判断 fact 是否可用。

## 7. 测试策略

需要覆盖三层：

1. **Policy unit tests。**
   覆盖 standard allowed、provisional/custom blocked、missing metadata blocked、
   malformed metadata blocked、controlled consumption allowed、blacklisted/deprecated
   blocked。

2. **P5 dataset tests。**
   验证 blocked canonical fact 不生成 present row，quality summary 记录 blocked
   摘要，required metric missing row 不被 artifact 的 `present` missing_status 误导。

3. **Availability tests。**
   验证 required metric 只有 blocked canonical fact 时不会返回 `present`。

4. **Turtle export tests。**
   验证 Turtle 只传播 dataset 中允许的 present rows，并保留 lifecycle provenance。

## 8. 完成标准

实现完成时应满足：

- P5 dataset 不再把 `auto_analysis_allowed=false` 或缺少治理 metadata 的 canonical
  fact 输出为 present row；
- Turtle export 不绕过 dataset governance；
- availability 不把 blocked fact 标记为 present；
- blocked facts 可在 dataset quality summary 中审计；
- 现有 P5/Turtle/availability 正常路径测试继续通过；
- 不改变 extraction、metric mapping、lifecycle decision write API 或 recompute audit
  contract。

## 9. 后续顺序

完成本 slice 后，才建议进入 Turtle 利润增强最小切片：

- `gross_profit`
- `selling_general_administrative` / SG&A 等价口径
- `fv_value_chg_gain`
- `non_oper_income`
- `non_oper_exp`

这样新增字段会落在已经加固的 P5/Turtle/availability 消费边界之后。
