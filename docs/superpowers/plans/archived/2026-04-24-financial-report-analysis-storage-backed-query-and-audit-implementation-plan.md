# Storage-Backed Query And Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在已完成的 durable storage core baseline 之上，补齐最小可用的 storage-backed query / audit surface，让 issuer/year/report 覆盖状态以及 persisted review / lineage / recompute records 可以通过统一 query contract 稳定读取。

**Architecture:** 保持当前 durable models、JSON/DB repository parity 和 historical-ingestion minimal registry 不变；本阶段新增的只读 query surface 建立在已稳定的 durable records 之上，不重新设计 review / lineage / recompute 业务 contract，不引入 broad HTTP API。

**Tech Stack:** Python 3.12, SQLAlchemy + SQLite-first, existing storage package, existing durable storage baseline, pytest, Ruff.

---

## Scope Check

本计划要做：

- issuer / year / report coverage query
- persisted review / lineage / recompute lookup
- audit-oriented read model
- focused integration，验证 query contract 能在当前 seed dataset 上稳定回答关键问题

本计划不做：

- broad HTTP API
- dashboard / BI 风格聚合
- Postgres migration
- document-ledger deeper wiring
- whole-document LLM assessment

## File Structure

### New files

- `financial-report-analysis/tests/unit/test_storage_query_audit.py`
- `financial-report-analysis/tests/integration/test_storage_query_audit.py`

### Existing files to modify

- `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
  - 扩充 query-oriented repository methods，统一 lookup 入口。
- `financial-report-analysis/src/financial_report_analysis/storage/historical_ingestion.py`
  - 如需要，补 coverage-state oriented read helpers。
- `financial-report-analysis/src/financial_report_analysis/storage/models.py`
  - 只在必须时补索引或最小状态字段；不引入新业务表族。
- `financial-report-analysis/tests/unit/test_storage_repository.py`
  - 如有必要，补 storage baseline 与 query layer 的 contract 衔接测试。

## Task 0: Query Boundary Inventory

**Files:**
- Create: `docs/architecture-analysis/2026-04-24-storage-query-and-audit-boundary-inventory.md`

- [ ] 明确当前 durable records 已经能回答、但尚未通过统一 query surface 暴露的问题：
  - issuer 覆盖了哪些 fiscal years
  - 某个 report 是否已注册
  - extracted / dataset / turtle export 是否已生成
  - 某个 artifact / dataset / run id 能否定位到 persisted review / lineage / recompute
- [ ] 记录哪些查询仍应后置到 document-ledger 阶段

## Task 1: Freeze Query Contract

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Test: `financial-report-analysis/tests/unit/test_storage_query_audit.py`

- [ ] 先写 failing tests，锁住最小 query contract：
  - `list_available_fiscal_years(issuer_id)`
  - `get_report_coverage(issuer_id, fiscal_year, report_type)`
  - `load_extracted_review_surface(artifact_id)`
  - `load_dataset_review_surface(dataset_id)`
  - `load_turtle_export_review_surface(dataset_id)`
  - `list_lineage_records(dataset_id / source_artifact_id)`
  - `load_recompute_result(run_id)`
- [ ] 只定义只读 contract，不在这里扩写 mutation 流程

## Task 2: Report Coverage Query

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/historical_ingestion.py`
- Test: `financial-report-analysis/tests/unit/test_storage_query_audit.py`

- [ ] 先写 failing tests，锁住：
  - issuer available years
  - `issuer + fiscal_year + report_type` 的 report 注册状态
  - extracted artifact availability
- [ ] 输出应优先服务 audit/read model，不要做 UI 定制结构

这里要显式避免把多 issuer 聚合对象写成 report-level status：

- `dataset artifact`
- `turtle export`

这两者如需参与 coverage 判断，应在后续作为 dataset-side 派生 query 引入，而不是塞进 report registry 基础状态。

## Task 3: Persisted Surface Query

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Test: `financial-report-analysis/tests/unit/test_storage_query_audit.py`

- [ ] 先写 failing tests，锁住：
  - artifact -> extracted review surface
  - dataset -> dataset review surface
  - dataset -> turtle export review surface
  - dataset/source_artifact -> lineage records
  - run id -> recompute result
- [ ] 统一返回 shape，避免调用方继续直接拼 SQL 或摸底层表

## Task 4: Audit Read Model

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Test: `financial-report-analysis/tests/unit/test_storage_query_audit.py`

- [ ] 先写 failing tests，锁住最小 audit read model：
  - dataset 由哪些 source artifacts 构成
  - source artifact 对应哪份 PDF
  - recompute reason 是什么
  - dataset 当前有哪些 persisted review signals
- [ ] 第一阶段只读，不做 decision / approval workflow

## Task 5: Focused Integration

**Files:**
- Create: `financial-report-analysis/tests/integration/test_storage_query_audit.py`

- [ ] 先写 focused integration，验证：
  - historical ingestion + repository persistence 后，query contract 能在 seed dataset 上直接回答 coverage 问题
  - review / lineage / recompute 的 persisted records 能通过统一 query 读取
  - 不需要调用方知道底层是哪张表
- [ ] 不跑 broad matrix；只跑当前 deterministic seed dataset

## Task 6: Closeout

- [ ] 跑 focused unit suite
- [ ] 跑 focused integration suite
- [ ] 跑 Ruff
- [ ] 做 spec compliance review
- [ ] 做 code-quality review
- [ ] 再决定是否进入后继阶段：
  - `Document Ledger And Extraction-Run Persistence`
  - storage-backed HTTP/API layer

## Exit Criteria

本计划收口时应满足：

- issuer/year/report coverage 有稳定 query surface
- persisted review / lineage / recompute 有统一 lookup 入口
- audit read model 能回答当前 seed dataset 的关键追溯问题
- 后续 API / review 工作不需要重新发明查询 contract
