# 存储、API、审阅、血缘与重算

## 流程

```text
POST /api/v1/analysis/extract
-> PdfIngestionAdapter
-> analyze_report
-> ReportAdapter
-> persist_analysis_extract_result
-> build_extracted_artifact_from_result
-> build_extracted_review_surface
-> SqlAlchemyP5ArtifactRepository.save_api_extract_bundle
-> DB-backed read surfaces
```

可选 P5/Turtle build：

```text
persisted extracted artifact
-> build_db_p5_outputs_for_artifact
-> assemble_dataset
-> build_dataset_review_surface
-> build_turtle_export
-> build_turtle_export_review_surface
-> build_dataset_lineage
-> save_p5_assembly_bundle
```

JSON P5 build：

```text
run_p5_dataset_build
-> P5JsonArtifactRepository
-> load/build extracted artifacts
-> assemble_dataset
-> save dataset JSON
-> build_turtle_export
-> save turtle JSON
```

Recompute：

```text
build_recompute_plan
-> execute_recompute_plan
-> read before payloads
-> run_p5_dataset_build or export-only rebuild
-> compare volatile-stripped JSON payloads
-> P5RecomputeResult
-> optional save_recompute_result
-> optional lifecycle_recompute_audit snapshot in recompute run payload
```

## 运行时与 API

`api/runtime.py` 从 `FRA_STORAGE_DB_PATH` 或显式 path 初始化 storage runtime。
如果没有 storage，storage-backed routes 会返回 unavailable responses，而不是
静默切换行为。

`api/routes.py` 暴露：

- issuer report coverage；
- extracted artifacts；
- dataset artifacts；
- dataset audit；
- Turtle export surfaces；
- recompute run reads, including optional lifecycle audit snapshots；
- metric governance review 和 lifecycle endpoints；
- analysis extract。

`api/schemas.py` 定义 extraction、P5 artifacts、review surfaces、dataset rows、
recompute results 和 lifecycle audit responses 的 request/response contracts。

## JSON 仓储

`p5/artifact_repository.py::P5JsonArtifactRepository` 将 extracted artifacts、
datasets 和 Turtle exports 存储为 JSON files。它拥有 serialization 和
deserialization helpers，这些 helpers 被 JSON 与 DB-backed storage 共用。

该 repository 支撑本地/offline P5 workflows 和 deterministic recompute tests。

## DB 仓储

`storage/repositories.py::SqlAlchemyP5ArtifactRepository` 将 artifacts 和
surfaces 存入 SQLite-backed tables。很多 artifact 主体仍以 JSON payload 形式
保存，同时 issuer/report/dataset/recompute/review/lineage metadata 被关系表索引。

关键写入职责：

- API extract bundle persistence；
- extracted artifact persistence；
- P5 dataset/Turtle/review/lineage bundle persistence；
- recompute result persistence；
- recompute-run-scoped lifecycle audit snapshot persistence；
- lifecycle registry persistence。

关键读取职责：

- report coverage；
- extracted artifact lookup；
- dataset/Turtle lookup；
- dataset audit；
- lineage records；
- recompute run lookup；
- recompute run audit view；
- metric governance review 和 lifecycle lookup。

## 审阅面

`p5/review.py` 构建 extracted artifact、dataset 和 Turtle review surfaces。
这些 surfaces 汇总 validation issues、review required signals、missing status
和 export review counts。

`services/metric_governance_review.py` 从 persisted extracted artifacts 中的
provisional candidate facts 构建 metric-governance-specific review items。

## 血缘

`p5/lineage.py::build_dataset_lineage` 将 dataset rows 链接到 source artifacts、
source facts、evidence bundles 和 Turtle export rows。

Storage 也记录 fact-level lineage，例如 candidate-to-canonical 和
canonical-to-derived relationships。

## 重算

`p5/recompute.py` 定义 recompute plans 和 execution。Recompute 保持
deterministic：它依赖 manifests、persisted artifacts、assembly rules 和显式
recompute reasons。

Phase 4B 增加了：

- `metric_lifecycle_decision_changed`；
- 该 reason 必须带 lifecycle consumption audit；
- 向 `p5/runner.py` 注入 `artifact_transform_func`；
- in-memory controlled consumption，不持久化 transformed extracted artifacts。

当前 recompute audit persistence 增加了：

- `MetricLifecycleRecomputeAudit` payload serialization；
- `save_recompute_result(..., lifecycle_recompute_audit=...)`；
- `load_recompute_run_audit_view(...)`；
- dataset audit view 的 `latest_lifecycle_recompute_audit`；
- `/recompute-runs/{run_id}` 和 `/datasets/{dataset_id}/audit` 的可选 audit
  snapshot 响应字段；
- malformed lifecycle audit payload fail-fast。

当前 DB-backed recompute boundary/readiness contract 增加了：

- `p5/db_recompute_boundary.py` 的 `DbRecomputeBoundaryView`；
- `RecomputeExecutionMode`，明确 `json_first_required`、`db_assembly_available` 和
  `db_native_unsupported`；
- `GET /datasets/{dataset_id}/recompute-boundary` 只读 endpoint；
- endpoint 不触发 recompute，不创建 recompute run，不执行 DB-native recompute；
- DB assembly path 继续只表示 persisted artifact assembly，不表示 recompute executor。

当前 explicit JSON-to-DB sync bridge 增加了：

- `p5/json_to_db_sync.py` 的 sync contract 和 service；
- JSON-first recompute after payloads 到 DB read surface 的显式同步；
- persisted sync metadata；
- dataset audit、recompute run read 和 recompute boundary views 的 sync status；
- stale input hash fail-closed 和 partial failure observability。

## 当前状态

已实现：

- DB-backed extract persistence 和 lookup；
- storage-backed API runtime；
- P5 dataset/Turtle persistence；
- review 和 lineage persistence；
- recompute result model 和 readback；
- lifecycle recompute audit snapshot persistence 和 readback；
- DB-backed recompute boundary/readiness view 和只读 API；
- explicit JSON-to-DB sync bridge baseline；
- offline/local P5 build 的 JSON repository；
- 3-5Y persisted availability/data provider baseline。

尚未作为完整 product workflow 实现：

- 带 locking/idempotency 的 HTTP-triggered recompute execution；
- async jobs；
- automatic acquisition/backfill；
- append-only lineage history；
- full run lifecycle/state machine。

## 风险与边界

- JSON recompute 与 DB-backed API assembly 是不同执行路径；当前通过
  `/datasets/{dataset_id}/recompute-boundary` 显式暴露该边界。
- 许多 DB objects 仍是 JSON payload；高基数 fact queries 能力有限。
- `save_p5_assembly_bundle` 重写 dataset snapshot 的 lineage，而不是保留完整
  lineage history。
- API extract persistence 当前在持久化场景下假设 `pdf_path`。
- Recompute run persistence 存储 result metadata 和可选 lifecycle audit snapshot；
  recompute boundary endpoint 只读说明 JSON-first/DB assembly/DB-native unsupported
  状态，并暴露 JSON-to-DB sync status，但不执行 DB-native recompute。

## 建议的后续切片

- 在 explicit JSON-to-DB sync bridge baseline 之上，后续才评估
  HTTP-triggered recompute/job boundary。
- 增加稳定 recompute run ids、input hashes 和 before/after artifact version
  references。
- 如未来查询需求明确，再将高价值 audit fields 从 JSON payload 提升为
  relational columns。
- 增加 recompute-run-scoped lineage history。
- 在支持 URL-backed persistence 前，先设计 persisted `pdf_url` identity。
