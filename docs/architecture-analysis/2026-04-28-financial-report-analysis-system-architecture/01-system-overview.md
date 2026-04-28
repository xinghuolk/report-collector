# 系统总览

## 架构分层

```text
HTTP / CLI input
-> PDF ingestion and table recovery
-> table semantic normalization
-> metric mapping / metric identity governance
-> candidate facts
-> fact normalization
-> conflict resolution and canonical facts
-> derivation and validation
-> review surfaces
-> P5 dataset and Turtle export
-> storage, lineage, recompute, availability, audit APIs
```

系统围绕 facts 组织，而不是围绕单个 endpoint 组织。核心契约是：抽取出的
facts 必须能从 PDF/table evidence 一路追溯到 candidate、canonical、dataset、
Turtle、review、lineage 和 recompute surfaces。

## 主路径

主抽取路径从
`financial-report-analysis/src/financial_report_analysis/pipeline.py::analyze_report`
开始。它接收 ingestion 产生的 candidate facts，执行标准化、冲突消解、TTM
派生、validation，并返回结构化 analysis result。

关键模块：

- `ingestion/pdf_ingestion.py`：PDF 读取、table extraction、note-disclosure
  candidates、text fallback。
- `ingestion/table_source.py`：raw table block extraction。
- `ingestion/table_structure.py`：parsed table recovery。
- `ingestion/table_header_parser.py`：header、period、unit、currency parsing。
- `ingestion/table_semantics.py`：normalized table semantics。
- `services/table_fact_builder.py`：normalized table rows 到 candidate facts。
- `services/fact_normalizer.py`：unit/currency normalization 和 metric
  governance metadata。
- `services/conflict_resolver.py`：canonical promotion 和 review packets。
- `services/derivation_service.py`：derived facts，目前主要是 TTM。
- `services/validation_service.py`：quality gate 和 validation issues。
- `adapters/report_adapter.py`：API-facing analysis result 和 key facts。
- `p5/dataset.py`：从 extracted artifacts 生成 P5 dataset rows。
- `p5/turtle_export.py`：从 dataset rows 生成 Turtle export rows。

## 治理路径

Metric governance 是主事实路径之上的并行控制面：

```text
MetricMappingRegistry / MetricRegistry
-> metric_governance metadata
-> provisional guardrails
-> metric governance review items
-> lifecycle entry/link/decision
-> lifecycle recompute audit
-> controlled consumption during explicit recompute
```

关键模块：

- `registries/metric_mapping.py`：确定性 table semantics 到 supported metric ids。
- `registries/metric_registry.py`：raw label identity resolution 和稳定
  provisional custom ids。
- `registries/metric_governance.py`：governance metadata helpers。
- `services/metric_governance_review.py`：provisional metric review items。
- `services/metric_lifecycle.py`：durable lifecycle service。
- `services/metric_lifecycle_recompute.py`：recompute / dry-run audit。
- `services/metric_lifecycle_consumption.py`：controlled output overlay。

## 存储与读取路径

系统有两种存储模式：

- 面向本地/offline P5 artifact workflow 的 JSON artifact repository：
  `p5/artifact_repository.py::P5JsonArtifactRepository`。
- 面向 API/runtime 的 DB-backed repository：
  `storage/repositories.py::SqlAlchemyP5ArtifactRepository`。

DB runtime 在 `api/runtime.py` 初始化。`api/routes.py` 中的 API routes 负责
读写 extracted artifacts、datasets、Turtle exports、review surfaces、lineage、
recompute runs 和 metric governance state。

## 当前完成状态

已完成能力：

- table-driven extraction baseline；
- P5 dataset 和 Turtle export；
- storage-backed API runtime；
- DB-backed extract persistence 和 lookup；
- review 和 lineage surfaces；
- deterministic recompute contracts；
- 3-5Y persisted availability/data provider baseline；
- metric governance Phase 1 到 Phase 4B。

当前尚未作为 production workflow 实现：

- async job orchestration；
- automatic multi-year report acquisition；
- automatic retry/rebuild lifecycle；
- full approval workflow；
- UI；
- whole-document LLM assessment 作为 canonical decision source。

## 关键边界

当前架构是 deterministic-first。Semantic fallback 可以辅助受限分类任务，
但不能成为事实来源、lifecycle approver 或 recompute arbiter。
