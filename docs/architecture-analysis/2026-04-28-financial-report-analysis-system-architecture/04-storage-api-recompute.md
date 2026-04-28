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
- recompute run reads；
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
- lifecycle registry persistence。

关键读取职责：

- report coverage；
- extracted artifact lookup；
- dataset/Turtle lookup；
- dataset audit；
- lineage records；
- recompute run lookup；
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

## 当前状态

已实现：

- DB-backed extract persistence 和 lookup；
- storage-backed API runtime；
- P5 dataset/Turtle persistence；
- review 和 lineage persistence；
- recompute result model 和 readback；
- offline/local P5 build 的 JSON repository；
- 3-5Y persisted availability/data provider baseline。

尚未作为完整 product workflow 实现：

- 带 locking/idempotency 的 HTTP-triggered recompute execution；
- async jobs；
- automatic acquisition/backfill；
- append-only lineage history；
- full run lifecycle/state machine。

## 风险与边界

- JSON recompute 与 DB-backed API assembly 是不同执行路径。
- 许多 DB objects 仍是 JSON payload；高基数 fact queries 能力有限。
- `save_p5_assembly_bundle` 重写 dataset snapshot 的 lineage，而不是保留完整
  lineage history。
- API extract persistence 当前在持久化场景下假设 `pdf_path`。
- Recompute run persistence 存储 result metadata，但不执行 DB-native recompute。

## 建议的后续切片

- 定义单一 DB-backed recompute executor，或明确 JSON-to-DB sync 边界。
- 增加稳定 recompute run ids、input hashes 和 before/after artifact version
  references。
- 将高价值 audit fields 从 JSON payload 提升为 relational columns。
- 增加 recompute-run-scoped lineage history。
- 在支持 URL-backed persistence 前，先设计 persisted `pdf_url` identity。
