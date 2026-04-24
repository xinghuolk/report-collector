# Storage Query And Audit Boundary Inventory

> **状态:** Task 0 completed baseline
> **日期:** 2026-04-24
> **阶段:** Storage-Backed Query And Audit

## 2026-04-24 Closeout Update

本文件原本是 phase-entry boundary inventory。当前 `Storage-Backed Query And Audit` 已完成并收口：

- repository 已提供 issuer/year/report coverage query
- repository 已提供 extracted / dataset / turtle review surface lookup
- repository 已提供 lineage / recompute lookup
- repository 已提供 dataset audit view
- API runtime 已通过 storage-backed endpoints 暴露 report coverage、artifact、dataset、dataset audit、recompute read path

因此，下文的“本阶段应该统一暴露的问题”应按已完成 baseline 理解，不再是未完成 gap。

当前仍开放的是：

- document-ledger deeper lookup 的更高层 API
- extraction-run 多版本比较
- workflow-level coverage summary
- approval/review decision API

## 当前 durable records 已经存在什么

当前 durable storage baseline 已经持久化了：

- `issuers`
- `reports`
- `manifests` / `manifest_entries`
- `extracted_artifacts`
- `dataset_artifacts`
- `turtle_export_artifacts`
- persisted review surfaces
- persisted lineage records
- persisted recompute runs/results

这意味着，当前数据库实际上已经能回答一批查询问题，只是还没有通过统一 query surface 暴露出来。

## 本阶段应该统一暴露的问题

### Report coverage

本阶段应通过稳定 repository query contract 暴露：

- 某个 `issuer_id` 覆盖了哪些 `fiscal_year`
- 某个 `issuer_id + fiscal_year + report_type` 是否已经注册为 report
- 该 report 当前是否已有 extracted artifact

这里明确只锁 report-level / extracted-level 状态。

### Persisted surfaces

本阶段应统一读取：

- `artifact_id -> extracted review surface`
- `dataset_id -> dataset review surface`
- `dataset_id -> turtle export review surface`
- `dataset_id / source_artifact_id -> lineage records`
- `run_id -> recompute result`

这些记录在 durable baseline 里已经存在，当前阶段只做统一 lookup 入口，不改业务 contract。

### Audit read model

本阶段最小 audit read model 应能回答：

- 某个 dataset 由哪些 source artifacts 构成
- 每个 source artifact 对应哪份 PDF
- 每个 source artifact 当前是否已有 extracted review surface
- 某个 dataset 是否已有 dataset / turtle export review surface
- 某个 dataset 最近一次 recompute 的 `run_id` 和 `reason`

## 明确后置到下一阶段的问题

以下问题不在本阶段解决，应后置到 `Document Ledger And Extraction-Run Persistence`：

- `report_file / document / document_version / extraction_run` 的深层 durable lookup
- statement table 粒度的 query
- fact set / validation / quality gate 的 ledger-style audit trail
- extraction-run 之间的多版本比较
- 基于 document ledger 的覆盖统计

## 阶段边界结论

`Storage-Backed Query And Audit` 的目标不是扩张 schema，而是在现有 durable records 之上补齐：

- report coverage query
- persisted surface query
- minimal dataset-centric audit view

只要这三层稳定，后续 API / audit / review flow 就不需要再直接拼底层 SQL 或重新猜测表关系。
