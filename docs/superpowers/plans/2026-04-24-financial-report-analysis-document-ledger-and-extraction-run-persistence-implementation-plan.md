# Document Ledger 与 Extraction-Run Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不打乱当前 artifact-first 主路径的前提下，把 `document / document_version / extraction_run / statement_table / fact_ledger` 这些更深层对象，从“schema 已存在”推进到“有最小 durable 接线与可验证 contract”。

**Architecture:** 继续保留现有 extracted/dataset/turtle-export artifact snapshot 作为可回放快照；本阶段新增的 durable 接线只承接高价值、高稳定引用对象。优先让 document identity、extraction-run identity、statement table identity 和 fact-set identity 可持久化追踪，再决定哪些 payload 仍保留在 artifact JSON 中。

**Tech Stack:** Python 3.12, SQLAlchemy + SQLite-first, existing storage package, existing artifact/review/lineage/recompute contracts, pytest, Ruff.

---

## Scope Check

本计划要做：

- `report_file / document / document_version / extraction_run` 最小 durable 接线
- statement table identity 的最小 durable 接线
- fact set / candidate / canonical / derived 的最小 durable 映射
- validation / quality gate 的最小 durable 接线
- focused integration，验证 artifact snapshot 与 deeper ledger objects 能共存

本计划不做：

- broad query dashboard
- whole-document LLM assessment
- 重新设计 canonical fact contract
- 完整 cell-matrix 关系化
- broad HTTP API
- Postgres migration

## File Structure

### New files

- `financial-report-analysis/tests/unit/test_document_ledger_models.py`
- `financial-report-analysis/tests/unit/test_document_ledger_repository.py`
- `financial-report-analysis/tests/integration/test_document_ledger_persistence.py`

### Existing files to modify

- `financial-report-analysis/src/financial_report_analysis/storage/models.py`
  - 为已存在但尚未 fully-wired 的 deeper objects 收紧 foreign keys / minimal statuses。
- `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
  - 增加 document-ledger / extraction-run / fact-set 的最小 repository methods。
- `financial-report-analysis/src/financial_report_analysis/storage/artifacts.py`
  - 如需要，补充更深层对象的 stable id builder helpers。
- `financial-report-analysis/src/financial_report_analysis/p5/models.py`
  - 仅在必须时暴露与 document ledger 接线相关的稳定 identity helper，不改变业务 shape。
- `financial-report-analysis/src/financial_report_analysis/p5/runner.py`
  - 如需要，允许在 artifact snapshot 生成后同步写入 deeper ledger baseline。

## Task 0: Boundary Inventory

**Files:**
- Create: `docs/architecture-analysis/2026-04-24-document-ledger-and-extraction-run-boundary-inventory.md`

- [ ] 明确当前 schema 中已经存在但仍未实际接线的 deeper objects：
  - `report_files`
  - `documents`
  - `document_versions`
  - `extraction_runs`
  - `statement_tables`
  - `statement_table_rows`
  - `statement_table_columns`
  - `fact_sets`
  - `candidate_facts`
  - `canonical_facts`
  - `derived_facts`
  - `fact_lineage`
  - `validation_reports`
  - `validation_issues`
- [ ] 记录哪些对象当前只需要 durable identity，不需要完整 payload relation 化
- [ ] 记录哪些 payload 继续留在 artifact snapshot 中

## Task 1: Freeze Document / Run Identity Contract

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/models.py`
- Test: `financial-report-analysis/tests/unit/test_document_ledger_models.py`

- [ ] 先写 failing tests，锁住：
  - `report -> report_file -> document -> document_version` identity chain
  - `document_version -> extraction_run` 的最小 foreign-key 完整性
  - 同一 report 的多次下载 / 多次解析 / 多次抽取如何稳定分层
- [ ] 只补最小必要字段，不扩成完整下载器编排模型

## Task 2: Statement Table Identity Wiring

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/models.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Test: `financial-report-analysis/tests/unit/test_document_ledger_repository.py`

- [ ] 先写 failing tests，锁住：
  - `extraction_run -> statement_table`
  - `statement_table -> rows / columns`
  - row / column identity 在一次 extraction run 内稳定可引用
- [ ] 暂不要求完整 cell matrix 关系化
- [ ] 允许完整表 payload 继续保留在 artifact snapshot

## Task 3: Fact Set Minimal Durable Mapping

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/models.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Test: `financial-report-analysis/tests/unit/test_document_ledger_repository.py`

- [ ] 先写 failing tests，锁住：
  - `fact_set`
  - `candidate_facts`
  - `canonical_facts`
  - `derived_facts`
  - `fact_lineage`
- [ ] 只要求最小 durable representation：
  - fact identity
  - fact set identity
  - source pointers
  - evidence / lineage pointers
- [ ] 不重写当前 candidate/canonical/derived 的业务 contract

## Task 4: Validation / Quality Gate Persistence

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/models.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Test: `financial-report-analysis/tests/unit/test_document_ledger_repository.py`

- [ ] 先写 failing tests，锁住：
  - validation report identity
  - validation issues
  - quality gate result
- [ ] 让 validation / quality gate 能引用 canonical/derived fact set，而不是只留在 artifact payload

## Task 5: Focused Integration

**Files:**
- Create: `financial-report-analysis/tests/integration/test_document_ledger_persistence.py`

- [ ] 先写 focused integration，验证：
  - 一份 PDF 的 report / report_file / document / document_version / extraction_run 能串起来
  - statement table identity 能稳定附着在 extraction run 下
  - fact set / validation / quality gate 有最小 durable representation
  - artifact snapshot 与 deeper ledger objects 不冲突
- [ ] 不跑 broad real-PDF matrix；只跑一个小的 deterministic sample

## Task 6: Closeout

- [ ] 跑 focused unit suite
- [ ] 跑 focused integration suite
- [ ] 跑 Ruff
- [ ] 做 spec compliance review
- [ ] 做 code-quality review
- [ ] 再判断是否进入后继阶段：
  - storage-backed query / audit 扩展实现
  - richer fact ledger / custom metric governance
  - Postgres/service-mode follow-up

## Exit Criteria

本计划收口时应满足：

- document / document_version / extraction_run 有最小 durable identity chain
- statement table 不再只存在于 artifact payload
- fact set / validation / quality gate 有最小 durable representation
- deeper ledger objects 能和现有 artifact snapshot 共存
- 后续 query / audit / recompute 可以逐步引用更深层对象，而不是只依赖 artifact snapshot
