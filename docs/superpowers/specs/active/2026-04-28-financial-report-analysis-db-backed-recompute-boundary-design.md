# 财报分析 DB-backed Recompute Boundary 设计

> **状态:** Implemented boundary/readiness contract
> **日期:** 2026-04-28
> **范围:** 明确 JSON-first recompute executor 与 DB repository/read surface 的长期边界

## 1. 目的

当前系统已经完成 P5 dataset/Turtle persistence、storage-backed API、review/lineage
persistence、recompute result persistence、downstream governance hardening 和 lifecycle
recompute audit snapshot persistence。

剩余架构风险不是“缺少一个 recompute audit 字段”，而是 recompute 的执行边界仍容易被误读：

```text
JSON recompute executor
vs
DB-backed assembly/readback/persistence
```

如果不先钉住边界，后续实现者可能把 `db_assembly_service` 当成 DB-native recompute，也可能在
API 层增加一个看似 DB-backed 的 recompute endpoint，但底层仍绕回 JSON artifact root。这样会
长期保留两条语义含糊的路径，影响审计、lineage、run id、input hash、staleness 和 failure
recovery 的后续设计。

本 spec 选择 **方案 A：JSON-first executor + DB 边界契约**。本轮只明确边界并增加最小可验证的
readiness/read surface，不实现 DB-native recompute executor，也不引入 async job 或 product
workflow state。

## 2. 当前状态

已有能力：

- `p5/recompute.py::execute_recompute_plan(...)` 是当前 canonical recompute executor。
  它基于 `P5JsonArtifactRepository`、manifest、artifact root 和显式 recompute reason
  重建 dataset/Turtle output。
- `p5/recompute.py::build_recompute_plan(...)` 已把 reason 映射为 dataset/Turtle rebuild flags。
- `metric_lifecycle_decision_changed` recompute 必须传入
  `MetricLifecycleRecomputeAudit`，并通过 controlled consumption transform 改写下游输出。
- `storage/repositories.py::save_recompute_result(...)` 能持久化 recompute plan/result 和可选
  lifecycle audit snapshot。
- `load_recompute_run_audit_view(...)` 和 `load_dataset_audit_view(...)` 能读回 recompute result、
  latest run metadata 和 lifecycle audit snapshot。
- `p5/db_assembly_service.py::build_db_p5_outputs_for_artifact(...)` 能从一个已持久化 extracted
  artifact 组装 dataset/Turtle/review/lineage，并写入 DB。

当前缺口：

- `db_assembly_service` 是 DB-backed assembly，不是 recompute executor；它没有接受
  `P5RecomputePlan`，也不产生 `P5RecomputeResult` diff summary。
- DB read surface 能展示 recompute result，但不能说明某个 dataset 当前是否支持 DB-native
  recompute、是否必须走 JSON-first、或为什么被阻断。
- 路线图只说“明确 JSON-first + DB sync 还是 DB-native”，但没有给后续方向的阶段顺序。

## 3. 设计决策

### 3.1 当前 canonical executor

当前阶段继续把 `execute_recompute_plan(...)` 视为唯一 canonical recompute executor。

原因：

- 它已经覆盖 manifest/source/pdf/pipeline/dataset contract/export/lifecycle reason；
- lifecycle-controlled consumption 已在该路径上实现并测试；
- 它能生成 `P5RecomputeResult.diff_summary`，并与现有 run persistence 对齐；
- 直接切到 DB-native 会牵涉 artifact selection、input versioning、lineage history、
  locking/idempotency 和 run lifecycle，超出当前最小切片。

### 3.2 DB 当前职责

DB 在本阶段承担以下职责：

- 保存 extracted artifacts、dataset/Turtle snapshots、review surfaces 和 lineage records；
- 保存 recompute run plan/result/audit payload；
- 提供 API/runtime readback、dataset audit view 和 availability/data provider；
- 提供一个明确的 recompute boundary/readiness view，说明当前 dataset 可以走哪类路径。

DB 在本阶段不承担以下职责：

- 执行 `P5RecomputePlan`；
- 执行 lifecycle-controlled recompute；
- 对 manifest/PDF/source artifact 变化做自动发现；
- 管理 async job、locking、retry 或 product workflow state。

### 3.3 Boundary modes

新增一个轻量边界模型，用于 read surface 和测试，不直接触发 recompute：

```python
class RecomputeExecutionMode(StrEnum):
    JSON_FIRST_REQUIRED = "json_first_required"
    DB_ASSEMBLY_AVAILABLE = "db_assembly_available"
    DB_NATIVE_UNSUPPORTED = "db_native_unsupported"
```

含义：

- `json_first_required`：当前 reason 或输入依赖只能由 JSON-first executor 正确执行。
- `db_assembly_available`：DB audit view 已验证当前 dataset 引用的 persisted extracted
  artifact 存在，且只适合执行 persisted artifact assembly；这仍不是 recompute executor。
- `db_native_unsupported`：调用者要求 DB-native recompute，但当前系统明确不支持。

配套 view model：

```python
@dataclass(frozen=True, slots=True)
class DbRecomputeBoundaryView:
    dataset_id: str
    latest_recompute_run_id: str | None
    latest_recompute_reason: str | None
    latest_lifecycle_audit_present: bool
    source_artifact_ids: tuple[str, ...]
    supported_modes: tuple[RecomputeExecutionMode, ...]
    required_mode: RecomputeExecutionMode
    blocking_reasons: tuple[str, ...]
```

该 view 的目标是回答：

```text
这个 dataset 当前能不能由 DB 路径 recompute？
如果不能，必须走 JSON-first 的原因是什么？
```

## 4. 目标行为

### 4.1 Repository/service boundary view

新增一个小型 service，例如 `p5/db_recompute_boundary.py`：

```python
build_db_recompute_boundary_view(
    *,
    repository: SqlAlchemyP5ArtifactRepository,
    dataset_id: str,
    requested_reason: str | None = None,
) -> DbRecomputeBoundaryView
```

行为：

- 从 dataset audit view 或 repository read methods 获取 latest recompute run metadata；
- 从 persisted dataset snapshot 获取 source artifact ids；
- 如果 latest recompute run 带 lifecycle audit snapshot，设置
  `latest_lifecycle_audit_present=True`；
- 如果调用者传入 lifecycle/pipeline/source/pdf/manifest/dataset-contract 类 reason，返回
  `required_mode=json_first_required`；
- 如果 DB audit view 已验证 source artifacts 存在，且只是单 artifact assembly 场景，可把
  `db_assembly_available` 放入 `supported_modes`，但 blocking reasons 必须说明它不是
  DB-native recompute；
- 不存在 dataset 或缺少 source artifact 时 fail fast，沿用现有 repository 错误风格；
- dataset 存在但 `source_artifact_ids` 为空时应返回 caller error，不应静默 fallback。

### 4.2 API read surface

新增只读 endpoint：

```text
GET /datasets/{dataset_id}/recompute-boundary
```

返回 `DbRecomputeBoundaryView` 的 JSON 形态。该 endpoint 不触发 recompute，不写 DB。

### 4.3 文档和命名约束

后续文档、API schema 和 plan 必须避免以下表述：

- “DB recompute 已实现”；
- “db_assembly_service 是 recompute executor”；
- “DB-backed recompute endpoint 会执行 recompute”。

推荐表述：

- “DB-backed recompute boundary/readiness”；
- “JSON-first recompute executor”；
- “DB-backed assembly path”；
- “DB-native recompute unsupported in this phase”。

## 5. 非目标

本切片不做：

- DB-native recompute executor；
- JSON-to-DB sync bridge 的实现；
- HTTP-triggered recompute execution；
- async jobs、locking、idempotency、retry；
- recompute run state machine；
- automatic acquisition/backfill；
- append-only lineage history；
- new lifecycle audit table；
- object storage/Postgres 产品化；
- UI。

## 6. 测试策略

需要覆盖：

1. **Boundary mode unit tests。**
   不同 recompute reason 能映射到明确 required mode 和 blocking reasons。

2. **DB-backed boundary service tests。**
   seeded dataset/recompute run/lifecycle audit snapshot 能生成稳定
   `DbRecomputeBoundaryView`。

3. **Negative tests。**
   缺失 dataset、缺失 source artifacts、请求 DB-native reason 时明确 fail fast 或返回
   `db_native_unsupported`，不能静默 fallback。

4. **API integration tests。**
   新 endpoint 应验证它只读、不触发 recompute、不改变 recompute run count。

5. **Regression tests。**
   现有 recompute、storage query/audit、API runtime、metric governance lifecycle audit
   persistence 测试继续通过。

## 7. 完成标准

实现完成时应满足：

- 代码和 API/read surface 能明确说明当前 dataset 的 recompute boundary；
- DB assembly path 不再被文档或命名误认为 DB-native recompute；
- lifecycle recompute 仍明确要求 JSON-first executor；
- 调用者能看到 unsupported/blocking reasons，而不是误以为 DB 会自动 recompute；
- 路线图包含后续方向：boundary/readiness -> JSON-to-DB sync bridge -> DB-native executor。

实现收口后，`GET /datasets/{dataset_id}/recompute-boundary` 是只读 readiness surface。
它返回 `json_first_required`、`db_assembly_available` 或 `db_native_unsupported`
相关状态说明，但不触发 recompute，不写入 recompute run，也不执行 DB-native recompute。

## 8. 后续方向

本 spec 完成后，后续方向按以下顺序推进：

1. **Boundary/readiness contract。**
   当前切片。只回答“能不能 DB-backed recompute、为什么不能、应该走哪条路径”。

2. **Explicit JSON-to-DB sync bridge。**
   如果产品需要让 JSON-first recompute 结果稳定进入 DB read surface，再设计显式 sync：
   input hashes、before/after artifact version references、run id 稳定性、partial failure
   recovery 和 overwrite semantics。

3. **DB-native recompute executor。**
   只有当 DB sync bridge 仍不能满足产品需求时，才设计 DB-native executor。该阶段必须单独处理
   artifact selection、locking/idempotency、lineage history、run lifecycle/state machine 和
   lifecycle-controlled consumption 的 DB 等价实现。

4. **Workflow/product layer。**
   async jobs、automatic backfill、approval workflow 和 product artifact lifecycle 应在 executor
   边界稳定后再启动。
