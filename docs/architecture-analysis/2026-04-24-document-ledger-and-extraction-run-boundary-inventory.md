# Document Ledger And Extraction-Run Boundary Inventory

> **状态:** Task 0 completed baseline
> **日期:** 2026-04-24
> **阶段:** Document Ledger And Extraction-Run Persistence

## 2026-04-24 Closeout Update

本文件原本是 phase-entry boundary inventory。当前 `Document Ledger And Extraction-Run Persistence` 已完成最小 durable 接线并收口：

- `report_file / document / document_version / extraction_run` 已有 repository 接线
- statement table identity / rows / columns / payload baseline 已有 repository 接线
- fact set / candidate / canonical / derived / fact lineage baseline 已有 repository 接线
- validation report / validation issue / quality gate baseline 已有 repository 接线
- integration tests 覆盖 artifact snapshot 与 deeper ledger objects 共存

因此，下文中“尚未真正接线”的表述是阶段入口状态，不再代表当前代码状态。

当前仍开放的是：

- 让主 pipeline 默认把真实 extraction table/fact ledger 全量写入这些 deeper objects
- 对 document/extraction-run/statement/fact ledger 暴露更高层 read API
- extraction-run 多版本比较
- workflow-level lineage / recompute orchestration

## 当前 schema 已存在、但尚未真正接线的 deeper objects

当前 durable schema 已经包含以下 deeper-ledger 对象：

- `report_files`
- `documents`
- `document_versions`
- `extraction_runs`
- `statement_tables`
- `statement_table_rows`
- `statement_table_columns`
- `statement_table_payloads`
- `fact_sets`
- `candidate_facts`
- `canonical_facts`
- `derived_facts`
- `fact_lineage_records`
- `validation_reports`
- `validation_issues`
- `quality_gate_results`

这些表已经存在于 [models.py](/Users/keli/source/report-collector/financial-report-analysis/src/financial_report_analysis/storage/models.py)，但大部分仍然只是 schema baseline，而不是当前主 pipeline 的 durable source of truth。

## 当前真正已经接线的只有哪些

当前真实代码路径仍然主要围绕以下对象运行：

- `issuers`
- `reports`
- `manifests`
- `manifest_entries`
- `extracted_artifacts`
- `dataset_artifacts`
- `turtle_export_artifacts`
- review surfaces
- lineage
- recompute

对应 repository 接线集中在 [repositories.py](/Users/keli/source/report-collector/financial-report-analysis/src/financial_report_analysis/storage/repositories.py)，尚未覆盖 deeper-ledger 表族。

## 哪些对象当前只需要 durable identity

当前阶段优先只需要 durable identity / minimal relation，不需要完整 payload relation 化的对象：

- `report_file`
- `document`
- `document_version`
- `extraction_run`
- `statement_table`
- `fact_set`
- `validation_report`

原因是当前目标是先让这些对象可以被稳定引用和追踪，而不是立刻把所有原始 parser / fact payload 全量拆到关系表。

## 哪些 payload 继续留在 artifact snapshot

当前阶段仍应继续保留在 artifact snapshot 或 payload-json 中的内容：

- 完整 document payload
- 完整 extracted payload
- statement table 的完整原始表结构
- candidate / canonical / derived fact 的完整业务 payload
- validation issue 的完整上下文

本阶段只为它们补 durable identity 和最小 source pointers，不改现有 artifact-first 主路径。

## 推荐的最小接线顺序

### Task 1

先钉住：

- `report -> report_file -> document -> document_version`
- `document_version -> extraction_run`

这一步只需要 identity helper、最小唯一性约束和模型级合同，不必先写 statement/fact 的 repository。

### Task 2+

在 document / extraction-run identity 稳定后，再逐层补：

- `statement_table`
- `fact_set`
- `validation_report`

这样可以避免在 document identity 还不稳定时，把更深层对象提前绑定到可能会变化的 key 上。

## 阶段边界结论

第三阶段当前最稳的起点不是“直接把 fact ledger 全接完”，而是先把：

- document identity
- document version identity
- extraction run identity

这三层钉成 durable first-class anchors。只要这一步收稳，后面的 statement/fact/validation 接线就可以围绕稳定根节点继续展开。
