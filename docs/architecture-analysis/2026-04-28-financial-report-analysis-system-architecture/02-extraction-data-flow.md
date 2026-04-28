# 抽取与数据流

## 高层流程

```text
PDF path / URL
-> PdfIngestionAdapter.extract_candidate_facts()
-> pypdf text pages + pdfplumber table blocks
-> ParsedTable recovery
-> header / period / unit / currency parsing
-> normalize_table_semantics()
-> MetricMappingRegistry.match()
-> build_table_candidate_facts()
-> note disclosure candidates and bounded fallback
-> analyze_report()
-> FactNormalizer.normalize_candidates()
-> ConflictResolver.resolve_with_review()
-> canonical facts + review packets
-> DerivationService.derive_ttm()
-> ValidationService.validate()
-> ReportAdapter / P5ExtractedArtifact
-> assemble_dataset()
-> build_turtle_export()
```

## 摄取与表格恢复

`ingestion/pdf_ingestion.py::PdfIngestionAdapter.extract_candidate_facts` 是
PDF ingestion 主入口。它读取 PDF 文本页和 table blocks，再使用 table
structure 与 semantic adapters 产出 candidate facts。

重要文件：

- `ingestion/table_source.py`：从 PDF 抽取 `RawTableBlock`。
- `ingestion/table_structure.py`：将 raw table blocks 转换为 `ParsedTable`。
- `ingestion/table_header_parser.py`：解析 periods、units、currencies 和
  column shapes。
- `ingestion/table_stitcher.py`：拼接跨页拆分的 tables。
- `ingestion/table_semantics.py`：归一化 table kind、rows、cells 和 semantic
  metadata。
- `services/table_fact_builder.py`：将 normalized table semantics 转成
  candidate fact dictionaries。

抽取路径是 table-first。Text fallback 和 note-disclosure extraction 是补充
路径，不是主事实来源。

## 候选事实到规范事实

`pipeline.py::analyze_report` 编排核心转换：

```text
candidate facts
-> FactNormalizer
-> ConflictResolver
-> canonical facts
-> DerivationService
-> ValidationService
```

`models/facts.py` 定义 `CandidateFact`、`CanonicalFact` 和 `DerivedFact`。

`services/fact_normalizer.py::FactNormalizer.normalize_candidates` 标准化
candidate 的 unit/currency，并附加 `extensions.metric_governance`。

`services/conflict_resolver.py::ConflictResolver.resolve_with_review` 将符合条件
的 candidate facts 提升为 canonical facts，同时为 source conflicts、scope
conflicts 或 provisional custom metrics 生成 review packets。

`services/derivation_service.py::DerivationService.derive_ttm` 在存在足够连续
季度 facts 时派生 TTM facts。

`services/validation_service.py::ValidationService.validate` 生成 validation
issues 和 quality gate status。

## API 适配

`adapters/report_adapter.py::ReportAdapter.build_analysis_result` 将 pipeline
result 转成 API-facing output。它会防御性排除 governance metadata 中
`auto_analysis_allowed=false` 的 facts。

这是阻止 provisional/custom facts 静默进入 `key_facts` 的最后防线之一。

## P5 与 Turtle

`p5/extraction.py::build_extracted_artifact` 基于 manifest entry 和 PDF 构建
`P5ExtractedArtifact`。

`p5/dataset.py::assemble_dataset` 基于 `artifact.canonical_facts` 生成
`P5DatasetArtifact` rows，也会为 required metrics 生成 missing rows。Phase 4B
之后，如果 controlled consumption 合成了 governed canonical fact，dataset row
可以携带 `lifecycle_consumption` provenance。

`p5/turtle_export.py::build_turtle_export` 通过当前 alias mapping 导出 dataset
rows。它使用 dataclass serialization，因此 `lifecycle_consumption` 等 dataset
row 字段会流入 Turtle review/export rows。

## 当前状态

已实现：

- PDF text/table ingestion；
- parsed table recovery；
- normalized table semantics；
- deterministic metric mapping；
- candidate/canonical/derived/validation 路径；
- note disclosure supplement paths；
- P5 extracted artifact、dataset、Turtle export；
- extracted artifact 和可选 P5/Turtle outputs 的 DB-backed persistence。

## 主要风险与边界

- `PdfIngestionAdapter` 在 table parsing 失败时可能 fallback；这需要 metadata
  可见性，让调用方区分“事实确实缺失”和“parser failure”。
- `MetricMappingRegistry` 的 external source loading 仍未实现；多数 mapping
  仍定义在代码中。
- `assemble_dataset()` 只消费 canonical facts，derived facts 不会自动进入 P5
  dataset/Turtle outputs。
- Turtle export 由 alias-map 驱动，自身不强制执行字段完整性策略。
- 复杂 scope/source precedence 仍依赖 review packets 和测试，而不是完整 policy
  engine。

## 建议的后续切片

- 将 parse-failure metadata 加入 quality/audit outputs。
- 明确 derived facts 是否应进入 P5 datasets；如需要，作为独立合同实现。
- 在大规模扩字段前，先给 external metric mappings 增加版本化机制。
- 减少 JSON P5 build 与 DB-backed P5 assembly 两条路径的职责分叉。
