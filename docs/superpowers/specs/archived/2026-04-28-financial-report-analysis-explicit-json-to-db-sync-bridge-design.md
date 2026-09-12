# 财报分析 Explicit JSON-to-DB Sync Bridge 设计

> **状态:** Implemented baseline, archived
> **日期:** 2026-04-28
> **范围类型:** DB/recompute 边界增强
> **上游基线:** DB-backed recompute boundary/readiness contract 已完成

## 1. 目的

当前系统已经完成 DB-backed recompute boundary/readiness contract：

- JSON-first recompute executor 仍是唯一 canonical executor。
- DB-backed repository 已能读回 extracted artifacts、P5 dataset、Turtle export、
  review、lineage、recompute run 和 lifecycle recompute audit snapshot。
- `/datasets/{dataset_id}/recompute-boundary` 已明确暴露
  `json_first_required`、`db_assembly_available` 和 `db_native_unsupported`。

剩余缺口不再是“能不能 DB-native recompute”，而是：

```text
JSON-first recompute 成功产生新 artifact payloads
-> DB read surface 是否显式、完整、可审计地同步到这些新结果
```

本 spec 定义一个最小的 explicit JSON-to-DB sync bridge，让 JSON-first recompute
结果稳定进入 DB-backed read surface，同时不改变 canonical executor、field coverage
或 governance policy。

## 2. 非目标

本阶段不做：

- DB-native recompute executor。
- HTTP-triggered recompute execution。
- async job queue、job status table 或 workflow lifecycle。
- automatic acquisition、backfill、retry 或 rebuild。
- Postgres/object-storage 迁移。
- Turtle 字段扩展或 v0.15 gap 新字段。
- LLM whole-document assessment。
- approval workflow UI 或人工 review 状态机。

Sync bridge 只同步已经由现有 deterministic JSON-first recompute 产生并验证过的
payloads，不重新抽取 PDF，不重新做 canonical promotion，不改变 metric lifecycle
decisions。

## 3. 当前边界

### 3.1 已有 JSON-first recompute

`p5/recompute.py` 负责：

- 构建 recompute plan；
- 读取 before payloads；
- 调用 JSON repository 路径执行 P5 dataset build 或 export-only rebuild；
- 比较 volatile-stripped payloads；
- 生成 `P5RecomputeResult`；
- 可选持久化 recompute result 和 lifecycle recompute audit snapshot。

该路径是当前唯一可信的 recompute executor。

### 3.2 已有 DB write/read 能力

`SqlAlchemyP5ArtifactRepository` 已支持：

- `save_api_extract_bundle(...)`；
- `save_p5_assembly_bundle(...)`；
- `save_recompute_result(...)`；
- extracted artifact / dataset / Turtle / review / lineage / audit read surfaces。

但当前缺少一个显式 contract 来声明：

- 某次 JSON-first recompute 的输出是否已完整同步到 DB；
- DB 当前 dataset/Turtle/read surfaces 对应哪个 recompute run；
- 同步时使用了哪些 input hashes 和 before/after artifact references；
- partial failure 时哪些对象已写入、哪些对象未写入；
- retry 是否安全、是否会覆盖不匹配的 DB state。

## 4. 设计原则

### 4.1 JSON-first 仍是 canonical executor

Sync bridge 不判断 recompute 是否正确。正确性由现有 recompute plan、artifact payload
diff、governance audit 和 deterministic tests 保证。

### 4.2 同步必须显式

DB read surface 不应静默“看起来像最新”。每次同步都必须有同步记录或同步摘要，能回答：

- 来源 recompute run 是哪个；
- 输入 artifact hashes 是什么；
- before refs 是什么；
- after refs 是什么；
- 同步是否 complete、failed 或 partial；
- failed/partial 时阻塞原因是什么。

### 4.3 Fail closed

如果 sync metadata 缺失、hash mismatch、source artifact mismatch、after payload
缺失或 partial failure 未恢复，DB read surface 不应声称自己已经完整反映该 recompute。
如果 dataset 的 latest recompute run 与 latest sync record 的 recompute run 不一致，
read surface 必须报告 `out_of_sync` 或等价 blocking reason，不能把旧 run 的 completed
sync 当成当前 dataset 状态。

### 4.4 幂等优先

同一个 recompute run 和同一组 input hashes 的 sync 可以安全 retry。Retry 不应创建重复
dataset/Turtle/read surface 语义，也不应覆盖一个 hash 不匹配的新状态。

### 4.5 不扩大产品面

本阶段只做内部 service/repository/API read surface contract。不会新增正式 workflow
product，也不会让用户通过 API 直接触发 heavy recompute。

## 5. 核心组件

### 5.1 Sync Contract

新增一个小型 contract 对象，建议命名为：

- `JsonToDbSyncRequest`
- `JsonToDbSyncResult`
- `JsonToDbSyncStatus`

请求最小字段：

- `recompute_run_id`
- `dataset_id`
- `source_artifact_ids`
- `input_hashes`
- `before_dataset_ref`
- `before_turtle_ref`
- `after_dataset_payload`
- `after_turtle_payload`
- `after_review_payloads`
- `after_lineage_payload`
- `lifecycle_recompute_audit`
- `requested_by`
- `sync_reason`

结果最小字段：

- `sync_id`
- `recompute_run_id`
- `dataset_id`
- `status`
- `written_refs`
- `skipped_refs`
- `blocking_reasons`
- `input_hashes`
- `before_refs`
- `after_refs`
- `created_at`
- `completed_at`

状态集合：

- `pending`
- `completed`
- `failed`
- `partial`
- `skipped_idempotent`

Read surface 还需要两个派生状态：

- `not_attempted`：当前 latest recompute run 没有对应 sync record；
- `out_of_sync`：存在 sync record，但 sync record 的 `recompute_run_id` 不等于当前
  latest recompute run。

### 5.2 Repository Write Boundary

同步服务应通过 DB repository 的显式方法写入，避免把复杂逻辑散落在 API route 或
recompute executor 中。

建议新增能力：

- `save_json_to_db_sync_result(...)`
- `load_json_to_db_sync_result(sync_id)`
- `load_latest_json_to_db_sync_for_dataset(dataset_id)`
- `load_latest_json_to_db_sync_for_recompute_run(recompute_run_id)`
- `load_effective_json_to_db_sync_for_dataset(dataset_id, latest_recompute_run_id)`

如果第一阶段不新增独立 DB table，可以先将 sync metadata 存入 recompute run payload
的扩展区；但 spec 推荐新增关系型同步记录，因为它需要表达 partial writes、retry 和
dataset 当前状态映射。

### 5.3 Sync Service

新增 service，建议命名：

`p5/json_to_db_sync.py`

职责：

- 校验 recompute result 和 after payloads 完整；
- 校验 source artifact ids 与 DB 当前 dataset audit view 一致；
- 计算或验证 input hashes；
- 拒绝 hash mismatch、source artifact mismatch 和 stale before refs；
- 在写 dataset/Turtle/recompute payload 前先写入 `pending` sync metadata，或在同一
  repository transaction 中写入 payload 与 sync metadata；
- 调用 repository 写入 dataset/Turtle/review/lineage/recompute audit；
- 记录 sync status、written refs、blocking reasons；
- 对同一 recompute run + input hashes 支持幂等 retry。

非职责：

- 触发 recompute；
- 读取 PDF；
- 运行 extraction；
- 改写 lifecycle decisions；
- 重新解释 metric governance。

### 5.4 Read Surface

本阶段至少让以下 read surface 能看见 sync 状态：

- dataset audit view；
- recompute run audit/read view；
- recompute boundary view。

可选 API 增强：

- `GET /datasets/{dataset_id}/sync-status`
- 或在现有 `/datasets/{dataset_id}/audit` 和
  `/datasets/{dataset_id}/recompute-boundary` 中增加只读 sync metadata。

第一阶段推荐优先扩展现有 audit/boundary response，避免过早增加独立产品 API。

## 6. 数据流

成功路径：

```text
JSON-first recompute
-> P5RecomputeResult + after payloads
-> JsonToDbSyncRequest
-> validate source artifacts / input hashes / before refs
-> save pending sync metadata
-> save P5 assembly bundle to DB
-> save recompute result + lifecycle audit if present
-> update sync metadata to completed
-> DB read surfaces expose latest synced recompute run
```

幂等 retry：

```text
same recompute_run_id + same input_hashes + same after refs
-> detect existing completed sync
-> return skipped_idempotent or completed result
-> do not duplicate semantic state
```

partial failure：

```text
write dataset succeeds
-> write Turtle or lineage fails
-> sync status partial
-> written_refs records dataset ref
-> blocking_reasons records failed component
-> read surfaces do not claim full sync complete
-> retry resumes or rewrites safely after validation
```

stale input：

```text
DB latest source artifact/hash no longer matches request
-> reject before writing
-> status failed
-> blocking_reasons includes stale_input_hash
```

out-of-sync read：

```text
latest recompute run = run-2
latest completed sync record = run-1
-> read surface status out_of_sync
-> blocking_reasons includes sync_recompute_run_mismatch
-> DB read surfaces do not claim run-2 is synced
```

## 7. Error Handling

Sync service must fail fast for:

- missing recompute run id；
- missing dataset id；
- empty source artifact ids；
- missing after dataset payload；
- source artifact id mismatch；
- input hash mismatch；
- before ref mismatch；
- malformed lifecycle recompute audit；
- repository write failure。

Failure behavior：

- validation failure writes no dataset/Turtle replacement payload；
- repository failure records `failed` or `partial` sync if metadata write is possible；
- if sync metadata cannot be written, service raises a repository error and caller must
  treat sync state as unknown；
- read surfaces must not infer completion from dataset payload alone。

## 8. API Contract

本阶段的 API 应保持只读为主。

Required read behavior：

- dataset audit response 可以看到 latest sync status；
- recompute run read response 可以看到该 run 是否已同步到 DB read surface；
- recompute boundary response 可以区分：
  - JSON-first required；
  - DB assembly available；
  - DB-native unsupported；
  - JSON-to-DB sync not attempted / completed / failed / partial / out-of-sync。

Out of scope：

- `POST /datasets/{id}/recompute`；
- `POST /datasets/{id}/sync`；
- long-running job API。

如果实现计划需要一个 internal-only service entrypoint，可作为 Python service 函数暴露，
但不作为 public HTTP route。

## 9. Testing Strategy

Unit tests：

- 构建有效 `JsonToDbSyncRequest` 并返回 completed result；
- hash mismatch fail closed；
- source artifact mismatch fail closed；
- same recompute run + same hashes idempotent；
- malformed lifecycle audit fail fast；
- missing after payload fail fast。
- latest recompute run 与 latest sync record 不一致时 fail closed 为 out-of-sync。

Integration tests：

- 使用 SQLite repository 从 persisted dataset 触发 sync service；
- sync 后 dataset audit view 显示 latest synced recompute run；
- recompute run read view 显示 sync metadata；
- partial failure 不让 boundary/audit 声称 complete；
- latest recompute run 与 latest sync run 不一致时，boundary/audit 不声称 complete；
- read path 不触发 recompute、dataset build 或 Turtle build。

Regression tests：

- 现有 JSON recompute tests 继续通过；
- 现有 DB-backed recompute boundary endpoint 行为保持 backward-compatible；
- existing P5/Turtle/availability governance tests 继续通过。

## 10. Acceptance Criteria

本阶段完成时应满足：

- 有明确的 JSON-to-DB sync contract 和 service boundary。
- 成功 sync 后，DB-backed dataset/Turtle/review/lineage read surfaces 与指定
  recompute run 的 after payloads 对齐。
- dataset audit、recompute run read 或 boundary view 能读出 latest sync status。
- 同一 recompute run + input hashes 可以安全 retry。
- stale input hash、source artifact mismatch 和 stale before ref 被拒绝，且不会覆盖
  DB state。
- partial failure 可观测，read surfaces 不会误报 complete。
- latest recompute run 与 latest sync run 不一致时，read surfaces 报告 out-of-sync
  或等价 blocking reason。
- DB-native recompute 仍明确 unsupported。
- 没有新增 field coverage、LLM extraction 或 async workflow 行为。

## 11. 后续方向

本阶段完成后，才适合评估：

- HTTP-triggered recompute + sync 的 job boundary；
- append-only lineage history；
- recompute-run-scoped artifact version table；
- product-level 3-5Y workflow artifact lifecycle；
- DB-native recompute executor feasibility。

这些都不是本阶段的一部分。

## 12. 实现状态

当前分支已实现 explicit JSON-to-DB sync bridge baseline：

- JSON-first recompute 仍是唯一 canonical executor。
- sync service 校验 source artifact hashes、dataset identity、after payloads 和
  recompute run identity。
- sync metadata 持久化到 DB，并通过 dataset audit、recompute run read 和
  recompute boundary views 读回。
- stale input hash fail closed。
- partial failure 可观测，read surfaces 不把 partial sync 误报为 completed。
