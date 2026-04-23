# Durable Storage 与历年入库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改写现有 review / lineage / recompute 业务 contract 的前提下，为 `financial-report-analysis` 引入 durable storage foundation，并补齐 issuer / report / fiscal year / artifact 的历年入库能力。

**Architecture:** 先冻结 post-P5 contract，再引入 database-backed repository。短期保持 JSON repository 可对照共存；新数据库层负责承接 issuer registry、report registry、artifact persistence、review/lineage/recompute persistence 和基础 query capability。当前阶段不做 whole-document LLM assessment，不做广义 HTTP API，不做新的字段扩张。

**Tech Stack:** Python 3.12, SQLModel or SQLAlchemy + SQLite first, Alembic-style migration discipline or equivalent lightweight migration runner, existing P5 contracts, pytest, Ruff.

---

## Scope Check

本计划要做：

- durable issuer / report / artifact model
- historical annual report ingestion registry
- database-backed repository for extracted / dataset / export artifacts
- durable review / lineage / recompute records
- focused query helpers for lookup by issuer / year / artifact id

本计划不做：

- 新字段 coverage phase
- broad HTTP API
- whole-document LLM assessment
- LLM-driven review / recompute
- 把现有 extraction pipeline 改成数据库直写主路径

## File Structure

### New files

- `financial-report-analysis/src/financial_report_analysis/storage/models.py`
- `financial-report-analysis/src/financial_report_analysis/storage/database.py`
- `financial-report-analysis/src/financial_report_analysis/storage/historical_ingestion.py`
- `financial-report-analysis/tests/unit/test_storage_models.py`
- `financial-report-analysis/tests/unit/test_storage_repository.py`
- `financial-report-analysis/tests/unit/test_historical_ingestion.py`
- `financial-report-analysis/tests/integration/test_storage_p5_parity.py`

### Existing files to modify

- `financial-report-analysis/src/financial_report_analysis/storage/artifacts.py`
  - 与现有 artifact-level record helpers 对齐 durable storage core models，避免重复造概念。
- `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
  - 在现有 in-memory repository pattern 基础上扩展 repository protocol / JSON / DB implementations，而不是旁路再造一套平行 storage 包。
- `financial-report-analysis/src/financial_report_analysis/p5/models.py`
  - 只在需要时补稳定 identity / serialization helpers；不要重写业务 shape。
- `financial-report-analysis/src/financial_report_analysis/p5/artifact_repository.py`
  - 如有需要，抽象 repository protocol，允许 JSON / DB 双实现共存。
- `financial-report-analysis/src/financial_report_analysis/p5/recompute.py`
  - 在 durable storage 存在时可记录 recompute run / diff summary。
- `financial-report-analysis/src/financial_report_analysis/p5/review.py`
  - 在 durable storage 存在时可读取或持久化 review surfaces。
- `financial-report-analysis/tests/unit/test_public_exports.py`
  - 如 storage public entry points 需要暴露，锁住公开 surface。

## Task 0: Sample And Contract Inventory

**Files:**
- Create: `docs/architecture-analysis/2026-04-23-durable-storage-and-historical-ingestion-sample-inventory.md`

- [ ] 盘点 durable storage 阶段的最小 sample set：
  - 3 个 issuer
  - 每个 issuer 2 个 fiscal year
  - 至少 1 个 extracted artifact / dataset / turtle export 样本
- [ ] 明确当前 post-P5 contract 中必须持久化的一等对象：
  - issuer
  - report
  - manifest entry
  - extracted artifact
  - dataset artifact
  - turtle export artifact
  - review surfaces
  - lineage links
  - recompute plan/result/diff
- [ ] 记录哪些对象仍是可派生 surface，不要提前物化过多

## Task 1: Freeze Storage-Bound Contracts

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/models.py`
- Test: `financial-report-analysis/tests/unit/test_storage_models.py`

- [ ] 为 extracted / dataset / export / review / lineage / recompute objects 定义 stable storage-facing identity contract
- [ ] 增加 failing tests，锁住：
  - artifact id uniqueness
  - issuer / fiscal year / report_type identity
  - recompute result / diff summary shape
  - lineage record minimum fields
- [ ] 只做最小必要补充，不重命名现有 post-P5 models

## Task 2: Durable Storage Core Models

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/storage/models.py`
- Create: `financial-report-analysis/src/financial_report_analysis/storage/database.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/artifacts.py`
- Test: `financial-report-analysis/tests/unit/test_storage_models.py`

- [ ] 先写 failing tests，锁住以下 durable entities：
  - issuer
  - report
  - report_file
  - extracted_artifact_record
  - dataset_artifact_record
  - turtle_export_record
  - recompute_run_record
- [ ] 落 SQLite-first schema，不提前做 Postgres-only 复杂特性
- [ ] 保留 manifest/report/artifact 的唯一约束
- [ ] 保留后续 review / lineage 承接需要的 foreign-key 关系

## Task 3: Repository Abstraction And JSON/DB Parity

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/artifact_repository.py`
- Test: `financial-report-analysis/tests/unit/test_storage_repository.py`

- [ ] 定义 repository protocol，明确：
  - save/load extracted artifact
  - save/load dataset artifact
  - save/load turtle export
  - list/query by issuer / fiscal year / artifact id
- [ ] 先让 JSON repository 实现 protocol
- [ ] 再实现 DB repository，同一组 contract tests 同时跑 JSON / DB
- [ ] 不允许 DB repository 改变上层 artifact payload shape

## Task 4: Historical Ingestion Registry

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/storage/historical_ingestion.py`
- Test: `financial-report-analysis/tests/unit/test_historical_ingestion.py`

- [ ] 先写 failing tests，锁住：
  - issuer + fiscal year + report_type 的 report identity
  - local pdf_path 与 report_file record 绑定
  - 同一 report 重复入库去重
  - report 已入库但 artifact 未生成的状态
- [ ] 实现最小 historical ingestion service
- [ ] 允许从现有 manifest 或 local pdf inventory 建立 report registry

## Task 5: Persist Review / Lineage / Recompute Records

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/review.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/recompute.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repository.py`
- Test: `financial-report-analysis/tests/unit/test_storage_repository.py`

- [ ] 先写 failing tests，锁住：
  - review surfaces 可持久化并按 artifact id 查询
  - lineage records 可持久化并按 dataset id / artifact id 查询
  - recompute result / diff summary 可持久化并按 run id 查询
- [ ] 只承接已经稳定的 surface，不在这里再发明新的业务 contract

## Task 6: Focused Parity Integration

**Files:**
- Create: `financial-report-analysis/tests/integration/test_storage_p5_parity.py`

- [ ] 先写 focused integration，验证：
  - 同一组 seed artifacts 进入 JSON repository 与 DB repository 后，load 出来的 artifact contract 一致
  - review / lineage / recompute 的关键 fields 一致
  - historical ingestion 能把 3 issuers x 2 years seed manifest 组织进 durable registry
- [ ] 不跑 broad matrix；只跑当前 seed dataset

## Task 7: Closeout

- [ ] 跑 focused unit suite
- [ ] 跑 focused integration parity suite
- [ ] 跑 Ruff
- [ ] 做 spec compliance review
- [ ] 做 code-quality review
- [ ] 再决定是否进入下一阶段：
  - storage-backed query / audit
  - whole-document LLM assessment extension

## Exit Criteria

本计划收口时应满足：

- issuer / report / artifact 有 durable model
- historical annual report ingestion 可入库
- JSON / DB repository 有最小 parity
- review / lineage / recompute records 有 durable persistence
- 当前系统不再只能依赖本地 JSON artifact 才能跑通 end-to-end
