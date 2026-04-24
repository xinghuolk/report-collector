# 财报分析 DB-Backed Extract To P5/Turtle Orchestration 设计

> **状态:** Draft for review
> **日期:** 2026-04-24
> **阶段:** Post-DB Extract Persistence Follow-up
> **范围类型:** 最小 HTTP 触发编排与 DB-backed P5/Turtle 组装

## 1. 目标

本阶段的目标是在已经完成的 DB-backed extract persistence slice 之上，补齐一条最小的 HTTP 到 P5/Turtle 持久化链路。

完成后，系统应支持这条 opt-in 垂直链路：

```text
HTTP /api/v1/analysis/extract
-> extract
-> persist extracted artifact to DB
-> optionally build DB-backed P5 dataset
-> optionally build DB-backed Turtle export
-> persist dataset/turtle/review/lineage to DB
-> return stable lookup identifiers
```

这一步不是完整 workflow API，也不是 3-5 年 Turtle orchestration。它只解决一个更窄的问题：

> 当调用方明确要求时，当前 extract 写入结果可以继续进入 DB-backed dataset/turtle build，并返回可查询的持久化结果。

## 2. 非目标

本阶段不包含：

- 自动报告发现、自动下载或批量历史补料
- 多 issuer / 多年度 batch workflow orchestration
- 异步 job queue / background worker / retry scheduler
- approval workflow / 人工 review decision API
- 新 Turtle analytics、估值或投资结论计算
- Postgres migration 或 service-mode 重写
- 把 `/api/v1/analysis/extract` 改成默认 always-build 的重接口

本阶段也不要求：

- 一次性替换所有 JSON artifact runner
- 改变现有 P5 dataset/turtle artifact contract
- 删除现有 JSON-first seed runner

## 3. 当前基线

当前已经具备：

- `/api/v1/analysis/extract` 的 opt-in DB extract persistence
- `SqlAlchemyP5ArtifactRepository.save_api_extract_bundle(...)`
- report / report_file / document / document_version / extraction_run ledger
- extracted artifact readback API
- dataset / turtle / review / lineage / recompute 的 repository baseline
- JSON-first `p5/runner.py`，可从 manifest 组装 P5 dataset 和 Turtle export

当前缺口是：

- P5 dataset/turtle build 主路径仍是 JSON-first runner
- HTTP extract 写入后不会继续触发 dataset/turtle build
- route 层没有稳定返回 dataset/turtle lookup ids
- DB repository 的 dataset/turtle 能力尚未被 HTTP write path 使用

因此系统目前已经完成：

```text
HTTP -> extract -> DB extracted artifact -> GET readback
```

但还没有完成：

```text
HTTP -> extract -> DB extracted artifact -> DB dataset/turtle -> GET readback/audit
```

## 4. 设计原则

### 4.1 Opt-in build，不改变默认 extract 行为

`/api/v1/analysis/extract` 的默认行为必须保持：

- 不持久化时仍是即时分析返回
- `persist_to_storage=true` 时只保证 extracted artifact 入库
- 只有调用方显式请求 dataset/turtle build 时，才进入后续组装

这可以避免刚完成的 extract write slice 被扩大成默认重流程。

### 4.2 Route 保持薄，组装逻辑进入 service

不要把 dataset/turtle 组装逻辑直接写进 API route。

推荐边界：

- route 负责 request parsing / validation / response serialization
- extract write service 负责现有 extract persistence
- 新增 DB-backed P5/Turtle assembly service 负责 dataset/turtle build
- 可选的 orchestration wrapper 负责串联 extract persistence 和 assembly service

route 只能调用 service，不直接处理 repository 细节。

### 4.3 DB-backed service 优先，JSON runner 保留兼容

本阶段应新增 DB-backed build path，但不要求立刻删除 JSON-first runner。

推荐做法：

- 抽出可复用的 assembly 业务逻辑
- DB-backed service 从 `SqlAlchemyP5ArtifactRepository` 读取 extracted artifact
- JSON runner 继续作为 seed/offline helper 存在
- 两条路径共享 artifact/dataset/turtle contract，避免 drift

### 4.4 单报告触发面必须显式承认局限

从单次 extract 请求触发 dataset/turtle build 时，第一版只能覆盖该请求明确提供的 report context。

如果只传入一份年报，dataset/turtle build 的最小成功标准是：

- 能把该 extracted artifact 组装为一个合法 dataset
- 能生成 Turtle-facing export
- 能保存 lineage，说明 dataset 来源于这次 extraction artifact
- 响应中能返回 dataset/turtle lookup ids

它不应伪装成完整 3-5 年 issuer dataset。

后续多年度 workflow 应通过独立 orchestration spec 扩展，而不是让单次 extract route 自动猜测历史范围。

## 5. API Contract

### 5.1 Request

在现有 `/api/v1/analysis/extract` request 上增加显式 opt-in build 参数。

建议字段：

- `persist_to_storage: bool`
- `build_dataset: bool = false`
- `build_turtle: bool = false`
- `dataset_id: str | null = null`
- `dataset_version: str | null = null`

约束：

- `build_dataset=true` 要求 `persist_to_storage=true`
- `build_turtle=true` 要求 `persist_to_storage=true`
- `build_turtle=true` 隐含需要 dataset build；service 应自动把它视为 `build_dataset=true`，调用方不需要重复传两个字段
- 第一版仍只允许 persisted annual report path
- 第一版不接受自动 issuer/year range discovery

`dataset_id` / `dataset_version` 的用途：

- 未提供时由 service 使用稳定默认规则生成
- 提供时用于调用方指定本次单报告 dataset 的业务 id
- 不应允许覆盖已有 dataset 的不可预期写入；重复 id 的行为必须由 repository/service 明确定义

第一版默认 id 规则应偏向可重复验证，而不是全局历史 dataset 语义。例如可以使用单报告上下文生成：

```text
single_report_<issuer_id>_<fiscal_year>_<report_type>_<artifact_id>
```

后续多年度 orchestration 可以定义独立的 dataset id 规则，不能复用单报告默认规则来暗示完整历史覆盖。

### 5.2 Response

现有 response 在 `storage` 或等价持久化字段下继续返回 extract ids，并在 build 被请求时附加 build result。

最小新增响应信息：

- `dataset_id`
- `turtle_export_id`
- `dataset_lookup_path`
- `turtle_export_lookup_path`
- `source_artifact_ids`
- `lineage_record_count`
- `build_warnings`

响应语义：

- 未请求 build 时，不返回虚假的 dataset/turtle ids
- 请求 build 且成功时，返回完整 lookup 信息
- 请求 build 且失败时，必须清楚标记失败，不能只返回 extracted persistence success 并吞掉 build error

## 6. Service Design

### 6.1 新增 DB-backed assembly service

建议新增窄 service，例如：

- `p5/db_assembly_service.py`
- 或 `api/p5_build_service.py`

职责：

1. 接收已持久化 extract identity
2. 从 DB repository 读取 extracted artifact
3. 构建 P5 manifest entry / source context
4. 调用现有 dataset assembly 规则
5. 生成 Turtle export
6. 保存 dataset artifact
7. 保存 turtle export
8. 保存 dataset/turtle review surface
9. 保存 lineage records
10. 返回 stable build result

输入模型建议包含：

- `report_id`
- `document_id`
- `document_version_id`
- `extraction_run_id`
- `artifact_id`
- `issuer_id`
- `market`
- `stock_code`
- `fiscal_year`
- `report_type`
- `dataset_id | None`
- `dataset_version | None`
- `build_turtle`

输出模型建议包含：

- `dataset_id`
- `dataset_version`
- `turtle_export_id | None`
- `source_artifact_ids`
- `review_surface_ids`
- `lineage_record_count`
- `warnings`

### 6.2 Orchestration wrapper

为了避免 route 知道两个 service 的内部细节，可以新增一个极薄 orchestration wrapper：

```text
persist_analysis_extract_result(...)
-> build_p5_outputs_for_persisted_extract(...)
-> assemble response storage/build section
```

这个 wrapper 不应包含业务规则，只做：

- 参数门控
- service 调用顺序
- 错误映射
- response assembly

### 6.3 Repository 复用

优先复用现有 `SqlAlchemyP5ArtifactRepository` 方法：

- `save_dataset_artifact`
- `load_dataset_artifact`
- `save_turtle_export`
- `load_turtle_export`
- `save_dataset_review_surface`
- `save_turtle_export_review_surface`
- `save_lineage_records`

如果现有方法缺少单报告 build 所需的 lookup helper，应补窄方法，而不是在 service 中散落 SQL。

## 7. Failure Behavior

### 7.1 Storage unavailable

如果请求包含：

- `persist_to_storage=true`
- 或 `build_dataset=true`
- 或 `build_turtle=true`

但 runtime storage 不可用，应返回 503。

这沿用当前 DB-backed extract persistence 的行为。

### 7.2 Build requested without persistence

如果：

- `build_dataset=true`
- 或 `build_turtle=true`

但 `persist_to_storage=false`，应返回 400 validation error。

原因是 DB-backed build 的输入是 persisted extracted artifact identity。

### 7.3 Extract succeeded but build failed

第一版建议采用 fail-fast 整体错误语义：

- extract persistence 已经入库
- dataset/turtle build 失败
- HTTP response 返回 500/422 级别错误
- error detail 尽量包含已完成的 extract persistence ids，便于调用方后续查询或人工排查

如果现有 error response 不适合承载 partial ids，则第一版至少要返回明确错误 message，不能把 build failure 降级成普通 warning。

后续如果引入 async job/retry，再把 partial success 语义正式化。

### 7.4 Turtle build requested but dataset invalid

如果 dataset assembly 产生 validation failure，turtle export 不应继续生成。

错误应指向 dataset build failure，而不是 turtle failure。

## 8. Testing Strategy

本阶段采用 tests-first。

### 8.1 Unit tests

新增或扩展：

- DB-backed assembly service 从 repository 读取 persisted artifact 并保存 dataset/turtle
- build request validation：
  - build without persistence -> 400
  - turtle implies/depends on dataset
  - missing storage -> 503
- response assembler 只在 build 被请求时返回 dataset/turtle ids

### 8.2 Integration tests

新增 API integration tests：

1. `persist_to_storage=true, build_dataset=true`
   - extract 成功
   - dataset 入库
   - response 返回 `dataset_id`
   - `GET /datasets/{dataset_id}` 可读回

2. `persist_to_storage=true, build_dataset=true, build_turtle=true`
   - turtle export 入库
   - response 返回 `turtle_export_id`
   - audit/lineage 可读回或 repository 可验证

3. `build_dataset=true` without `persist_to_storage=true`
   - 返回 400

4. storage disabled + build requested
   - 返回 503

### 8.3 Regression tests

必须保留并继续通过：

- 未请求 persistence 的 extract 行为
- 只请求 `persist_to_storage=true` 的 extract write/readback 行为
- 现有 JSON P5 runner tests
- storage repository parity tests

## 9. Completion Criteria

本阶段完成时，应满足：

- `/api/v1/analysis/extract` 支持显式 build dataset/turtle 参数
- 默认 extract 行为不变
- build 参数要求 storage persistence
- DB-backed assembly service 能从 persisted artifact 生成 dataset
- Turtle export 能作为 opt-in build 结果入库
- response 返回 stable dataset/turtle lookup ids
- dataset/turtle 结果能通过现有 read/query surface 验证
- JSON-first runner 仍可运行
- 新增 integration tests 覆盖 HTTP 到 DB dataset/turtle 的最小闭环

## 10. 后续阶段

本阶段完成后，下一阶段才适合进入：

- 多报告 / 多年度 DB-backed build orchestration
- 3-5 年 Turtle workflow API
- async job/retry/status tracking
- report acquisition / discovery orchestration
- review decision workflow

也就是说，本阶段是从“单次 extract 写入”通向“完整多年 Turtle workflow”的中间桥接层，而不是 workflow 终点。
