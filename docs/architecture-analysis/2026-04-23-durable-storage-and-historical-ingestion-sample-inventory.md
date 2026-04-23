# Durable Storage 与历年入库 Sample / Contract Inventory

> **状态:** Task 0 phase-entry artifact
> **日期:** 2026-04-23
> **关联计划:** [2026-04-23-financial-report-analysis-durable-storage-and-historical-ingestion-implementation-plan.md](/Users/keli/source/report-collector/docs/superpowers/plans/2026-04-23-financial-report-analysis-durable-storage-and-historical-ingestion-implementation-plan.md)

## 1. 目的

这份文档用于 durable storage 阶段的 `Task 0`：

- 明确当前最小 sample set
- 明确哪些对象已经在 P5 / post-P5 contract 中形成 durable candidate
- 区分哪些对象应作为数据库中的一等实体，哪些对象仍然适合保持派生 surface

## 2. 当前最小 Sample Set

当前 durable storage 阶段的最小 sample set 已经由现有 P5 seed manifest 提供：

- manifest: [p5_seed_manifest.json](/Users/keli/source/report-collector/financial-report-analysis/tests/fixtures/p5_seed_manifest.json)
- integration entry point: [test_p5_seed_dataset.py](/Users/keli/source/report-collector/financial-report-analysis/tests/integration/test_p5_seed_dataset.py)
- recompute/review flow: [test_p5_recompute_review_flow.py](/Users/keli/source/report-collector/financial-report-analysis/tests/integration/test_p5_recompute_review_flow.py)

### 2.1 Issuer Set

当前 seed 包含 3 个 issuer，每个 issuer 2 个 fiscal year：

- `CN_600519`
  - `2024 annual`
  - `2025 annual`
- `CN_601919`
  - `2024 annual`
  - `2025 annual`
- `CN_688008`
  - `2024 annual`
  - `2025 annual`

### 2.2 Sample Characteristics

当前 sample set 满足 durable storage phase 的最小要求：

- 3 个 issuer
- 2 个 fiscal years per issuer
- annual reports only
- manifest-driven pdf path resolution
- extracted artifact / dataset artifact / turtle export 已经有实际测试覆盖

因此，后续 durable storage parity tests 可以直接复用这组样本，而不必再新造更大的 seed matrix。

## 3. 当前已存在的核心 Contract 对象

现有 P5 / post-P5 contract 主要定义在：

- [p5/models.py](/Users/keli/source/report-collector/financial-report-analysis/src/financial_report_analysis/p5/models.py)
- [p5/artifact_repository.py](/Users/keli/source/report-collector/financial-report-analysis/src/financial_report_analysis/p5/artifact_repository.py)
- [p5/review.py](/Users/keli/source/report-collector/financial-report-analysis/src/financial_report_analysis/p5/review.py)
- [p5/lineage.py](/Users/keli/source/report-collector/financial-report-analysis/src/financial_report_analysis/p5/lineage.py)
- [p5/recompute.py](/Users/keli/source/report-collector/financial-report-analysis/src/financial_report_analysis/p5/recompute.py)

### 3.1 Manifest / Report Boundary

当前已明确的对象：

- `P5Manifest`
- `P5ManifestEntry`

这些对象已经隐含 durable storage 需要承接的 report identity 维度：

- `issuer_id`
- `market`
- `stock_code`
- `fiscal_year`
- `report_type`
- `pdf_path`
- `source`
- `company_name`
- `report_language`

当前结论：

- `manifest` 适合作为 durable entity
- `manifest entry` 适合作为 durable entity
- `report` 应从 `manifest entry` 中抽象成 durable entity

## 4. 当前必须持久化的一等对象

### 4.1 Issuer / Report Registry Layer

当前 durable storage 阶段建议作为一等对象持久化：

- `issuer`
- `report`
- `report_file`
- `manifest`
- `manifest_entry`

原因：

- 历年 annual report 入库不能长期只靠临时 manifest JSON
- issuer / fiscal year / report_type 是后续 query / recompute 的天然 lookup key

### 4.2 Artifact Layer

当前 durable storage 阶段建议作为一等对象持久化：

- `P5ExtractedArtifact`
- `P5DatasetArtifact`
- `P5TurtleExport`

原因：

- 这三类 artifact 已经是系统真实输出物
- 当前 JSON repository 已经在持久化它们，只是还没有 durable registry / database-backed repository

### 4.3 Review / Lineage / Recompute Layer

当前 durable storage 阶段建议作为一等对象持久化：

- `P5ExtractedReviewSurface`
- `P5DatasetReviewSurface`
- `P5TurtleExportReviewSurface`
- `P5ArtifactLineage`
- `P5RecomputePlan`
- `P5RecomputeResult`
- `P5RecomputeDiffSummary`

原因：

- 这些对象已经不再只是调试输出
- 它们已经进入 post-P5 contract，并且是后续 query / audit / review / recompute 的基础

## 5. 当前仍可保持派生的对象

本阶段不建议过早物化过多细粒度对象。

当前更适合继续保持派生或延后决定的包括：

- dataset row 的更细粒度 query index
- turtle export row 的独立审批状态
- broad audit trail event stream
- provisional / custom metric governance records
- future whole-document LLM assessment artifact

原因：

- 这些对象还没有在当前 contract 中完全稳定
- 现在过早物化，容易让数据库 schema 反过来驱动业务 contract

## 6. 数据库阶段前的最小稳定边界

durable storage implementation 开始前，应假定以下边界已经足够稳定，可直接承接：

### 6.1 Stable Identities

- `issuer_id`
- `manifest_id`
- `artifact_id`
- `dataset_id`
- `source_artifact_id`
- `manifest_entry_key`

### 6.2 Stable Artifact Families

- extracted artifact
- dataset artifact
- turtle export artifact
- review surfaces
- lineage records
- recompute records

### 6.3 Stable Historical Sample

- 3 issuers x 2 fiscal years x annual only
- 现有 seed manifest 已足够支撑 JSON / DB parity

## 7. 对 Task 1-Task 6 的约束

后续 durable storage tasks 应遵守：

- `Task 1`: 只冻结 storage-bound contracts，不重写现有 P5/post-P5 业务 shape
- `Task 2`: durable model 先承接 issuer / report / artifact / recompute run，不提前做大而全 schema
- `Task 3`: JSON / DB repository 必须同 contract parity
- `Task 4`: historical ingestion registry 必须直接服务当前 seed manifest
- `Task 5`: review / lineage / recompute records 只承接已稳定对象
- `Task 6`: parity integration 先围绕当前 seed samples，不扩广 matrix

## 8. 一句话结论

当前 durable storage 阶段已经有足够清晰的 phase-entry baseline：

- **样本上**：3 issuers x 2 years 的 seed manifest 已够用
- **对象上**：issuer / report / manifest / artifacts / review / lineage / recompute 已形成 durable candidate
- **边界上**：可以开始数据库阶段，但应只承接这些已稳定对象，不提前把更多未来 surface 一起物化
