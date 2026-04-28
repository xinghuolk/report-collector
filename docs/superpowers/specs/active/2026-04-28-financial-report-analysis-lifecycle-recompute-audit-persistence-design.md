# 财报分析 Lifecycle Recompute Audit Persistence 设计

> **状态:** Active design spec
> **日期:** 2026-04-28
> **范围:** metric lifecycle recompute audit snapshot 的持久化与 read surface

## 1. 目的

当前系统已经完成 metric governance Phase 1-4B 和 downstream governance hardening。
Phase 4B 能生成 `MetricLifecycleRecomputeAudit`，并能在 lifecycle recompute 时通过
`lifecycle_consumption` provenance 改写下游输出。

剩余问题是：这份 audit 目前主要存在于 API 响应、测试输入或 recompute 调用参数中。
当 dataset/Turtle output 已经被 recompute run 重新生成后，系统只能看到 latest
recompute run 和 diff summary，不能稳定回答：

```text
这次 dataset/Turtle 输出到底受哪些 lifecycle review item / decision 影响？
```

本 spec 的目标是把 lifecycle recompute audit snapshot 持久化到 recompute run，并在
recompute run read surface 与 dataset audit view 中读回。它不改变 lifecycle decision
写入 API，不引入 async job，不重构 DB-native recompute。

## 2. 当前状态

已有能力：

- `MetricLifecycleRecomputeAudit` / `MetricLifecycleRecomputeAuditItem` /
  `MetricLifecycleRecomputeAuditSummary` 已存在于 `models/governance.py`。
- `/api/v1/metric-governance/lifecycle-recompute-audit` 可以按 review items 生成 audit。
- `execute_recompute_plan(..., lifecycle_consumption_audit=...)` 在
  `metric_lifecycle_decision_changed` reason 下要求传入 audit。
- `apply_metric_lifecycle_consumption(...)` 会把 controlled consumption provenance 写入
  fact governance metadata。
- `SqlAlchemyP5ArtifactRepository.save_recompute_result(...)` 会持久化
  recompute plan/result 到 `recompute_runs.result_json`。
- `/recompute-runs/{run_id}` 和 `/datasets/{dataset_id}/audit` 已有 read surface。

当前缺口：

- `save_recompute_result(...)` 没有保存 lifecycle audit snapshot。
- `load_recompute_result(...)` 只返回 `P5RecomputeResult`，无法读回 audit。
- `DatasetAuditView` 只暴露 latest recompute run id/reason，不暴露 latest lifecycle audit。
- API schemas 没有 lifecycle audit snapshot 字段。

## 3. 设计原则

1. **Audit snapshot 归属 recompute run。**
   它解释的是某次 recompute 为什么、如何受 lifecycle decisions 影响，而不是解释当前
   lifecycle registry 的最新状态。

2. **保存 snapshot，不保存 live lookup。**
   Dataset audit view 应读取 recompute run 当时保存的 audit payload，不能重新调用
   lifecycle service 推断历史。

3. **不新增 schema 表。**
   本切片优先复用 `recompute_runs.result_json` 承载可选
   `lifecycle_recompute_audit` payload。这样避免 DB migration，并保持现有
   `RecomputeRunRecord` 结构稳定。

4. **非 lifecycle recompute 保持空值。**
   普通 pipeline/dataset/export recompute 不应带 lifecycle audit snapshot。

5. **API 向后兼容。**
   新字段为 optional；旧 recompute result payload 没有该字段时，应返回 `None`。

## 4. 目标行为

### 4.1 保存 recompute result

`SqlAlchemyP5ArtifactRepository.save_recompute_result(...)` 增加可选参数：

```python
lifecycle_recompute_audit: MetricLifecycleRecomputeAudit | None = None
```

保存时，`result_json` payload 增加可选字段：

```json
{
  "lifecycle_recompute_audit": {
    "items": [...],
    "summary": {...}
  }
}
```

如果参数为 `None`，不写该字段，或写为 `null` 均可；read surface 统一返回 `None`。

### 4.2 读取 recompute run

新增一个轻量 view model，例如：

```python
@dataclass(frozen=True, slots=True)
class RecomputeRunAuditView:
    run_id: str
    result: P5RecomputeResult
    lifecycle_recompute_audit: MetricLifecycleRecomputeAudit | None
```

Repository 增加：

```python
load_recompute_run_audit_view(run_id: str) -> RecomputeRunAuditView
```

`load_recompute_result(run_id)` 继续保持原行为，避免破坏现有调用者。

### 4.3 Dataset audit view

`DatasetAuditView` 增加：

```python
latest_lifecycle_recompute_audit: MetricLifecycleRecomputeAudit | None
```

`load_dataset_audit_view(dataset_id)` 读取 latest recompute run 的 snapshot。如果 latest
run 不是 lifecycle recompute 或没有 snapshot，则返回 `None`。

### 4.4 API 响应

`RecomputeResultResponse` 增加：

```python
lifecycle_recompute_audit: MetricLifecycleRecomputeAuditResponse | None = None
```

`DatasetAuditResponse` 增加：

```python
latest_lifecycle_recompute_audit: MetricLifecycleRecomputeAuditResponse | None = None
```

API 不新增 endpoint。已有 endpoint 直接带出 snapshot：

- `GET /recompute-runs/{run_id}`
- `GET /datasets/{dataset_id}/audit`

## 5. 非目标

本切片不做：

- 新 lifecycle decision 状态；
- approval workflow；
- async recompute job；
- DB-native recompute 重构；
- 单独的 lifecycle audit table；
- 历史 recompute run backfill；
- UI；
- whole-document LLM assessment。

## 6. 测试策略

需要覆盖：

1. **Payload serializer tests。**
   `MetricLifecycleRecomputeAudit` 可以稳定 round-trip 为 dict payload。

2. **Repository tests。**
   `save_recompute_result(..., lifecycle_recompute_audit=audit)` 后，
   `load_recompute_run_audit_view(run_id)` 能读回 result 和 audit。

3. **Dataset audit view tests。**
   latest recompute run 带 lifecycle audit 时，dataset audit view 返回
   `latest_lifecycle_recompute_audit`；普通 recompute run 返回 `None`。

4. **API integration tests。**
   `/recompute-runs/{run_id}` 和 `/datasets/{dataset_id}/audit` 返回 lifecycle audit
   snapshot，且旧 run 不带该字段时仍返回 `null`。

5. **Regression tests。**
   现有 P5 recompute、storage query/audit、metric governance API 测试继续通过。

## 7. 完成标准

实现完成时应满足：

- lifecycle recompute audit snapshot 能随 recompute run 持久化；
- recompute run read surface 能读回 snapshot；
- dataset audit view 能展示 latest recompute run 的 lifecycle audit snapshot；
- 普通 recompute run 不产生 lifecycle audit；
- 旧 payload 缺少 lifecycle audit 时不会报错；
- 不改变 lifecycle decision write API、downstream governance policy、dataset assembly
  或 Turtle export 行为。

## 8. 后续顺序

完成本 slice 后，DB-backed recompute boundary/readiness 已作为后续切片完成。
如果继续推进，下一步可以在两类工作中选择：

- **Explicit JSON-to-DB sync bridge。** 如果产品需要让 JSON-first recompute
  结果稳定进入 DB read surface，再设计显式同步边界；当前 DB-native recompute
  仍不作为下一步默认目标。
- **One-field post-P5 onboarding。** 从 Turtle v0.15 gap list 中选择一个字段族做
  sample-onboarding diagnosis，再决定是否扩展 deterministic semantics / registry。
