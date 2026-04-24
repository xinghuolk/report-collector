# Storage-Backed API Runtime Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前 API app 从“只有即时 extract route”推进到“真正拿到 durable storage dependency 并能稳定返回最小 read-only storage-backed resources”的状态。

**Architecture:** 保留现有 `/api/v1/analysis/extract` 主路径不变；新增一组 read-only routes，直接建立在 storage-backed query/audit baseline 之上。app factory 负责 DB path / engine / repository 的 runtime wiring，routes 只做极薄的 read-through。

**Tech Stack:** Python 3.12, FastAPI, current `financial-report-analysis` API app/routes/schemas, SQLAlchemy + SQLite-first, storage repositories, pytest, Ruff.

---

## Scope Check

本计划要做：

- app-level storage dependency wiring
- minimal read-only response contract
- storage-backed read-only endpoints
- focused API integration on temp SQLite

本计划不做：

- rewrite existing extract route
- workflow / approval write APIs
- URL/upload ingestion orchestration
- broad search/query API
- Postgres/service-mode refactor

## File Structure

### New files

- `financial-report-analysis/tests/unit/test_api_storage_runtime.py`
- `financial-report-analysis/tests/integration/test_api_storage_runtime.py`

### Existing files to modify

- `financial-report-analysis/src/financial_report_analysis/api/app.py`
  - app-level DB path / repository wiring
- `financial-report-analysis/src/financial_report_analysis/api/routes.py`
  - add read-only storage-backed endpoints
- `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
  - add minimal response models
- `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
  - only if strictly needed for one small missing read helper

## Task 0: Runtime Boundary Inventory

**Files:**
- Create: `docs/architecture-analysis/2026-04-24-storage-backed-api-runtime-boundary-inventory.md`

- [ ] 明确当前 API runtime 已有：
  - app factory
  - health route
  - extract route
- [ ] 明确当前 storage-backed baseline 已有：
  - report coverage
  - extracted artifact
  - dataset
  - dataset audit
  - recompute result
- [ ] 记录第一版不暴露的 deeper objects：
  - raw statement table ledger
  - fact ledger internals
  - approval state

## Task 1: Freeze Runtime Dependency Contract

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/app.py`
- Test: `financial-report-analysis/tests/unit/test_api_storage_runtime.py`

- [ ] 先写 failing tests，锁住：
  - `create_app(...)` 如何接收 storage path / runtime config
  - tests 如何 override temp SQLite
  - app state / dependency 如何暴露 repository
- [ ] 不在 route import 时隐式初始化 DB

## Task 2: Freeze Minimal Response Models

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Test: `financial-report-analysis/tests/unit/test_api_storage_runtime.py`

- [ ] 先写 failing tests，锁住：
  - report coverage response
  - artifact response
  - dataset response
  - dataset audit response
  - recompute result response
- [ ] 不把 repository 的 SQL row shape 直接泄露成 API contract

## Task 3: Add Read-Only Storage-Backed Routes

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py` (only if strictly needed)
- Test: `financial-report-analysis/tests/integration/test_api_storage_runtime.py`

- [ ] 先写 failing tests，锁住：
  - `GET /issuers/{issuer_id}/reports`
  - `GET /reports/{issuer_id}/{fiscal_year}/{report_type}`
  - `GET /artifacts/{artifact_id}`
  - `GET /datasets/{dataset_id}`
  - `GET /datasets/{dataset_id}/audit`
  - `GET /recompute-runs/{run_id}`
- [ ] 路由只做 read-through，不重写 repository 逻辑

## Task 4: Focused End-to-End API Verification

**Files:**
- Modify: `financial-report-analysis/tests/integration/test_api_storage_runtime.py`

- [ ] 用 temp SQLite + seeded storage records 验证：
  - report coverage endpoint
  - artifact endpoint
  - dataset endpoint
  - dataset audit endpoint
  - recompute endpoint
- [ ] 每个 endpoint 至少一条 happy path + 一条 not found
- [ ] 验证现有 `/health` 继续可用
- [ ] 验证现有 `/api/v1/analysis/extract` 没被 runtime wiring 打坏

## Task 5: Evaluate Optional Write Entry

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Test: `financial-report-analysis/tests/integration/test_api_storage_runtime.py`

- [ ] 仅在确有必要时考虑：
  - `POST /manifests/register`
- [ ] 如果当前目标已经通过 read-only slice 达成，本 task 标记 `not needed`

## Task 6: Closeout

- [ ] 跑 focused unit suite
- [ ] 跑 focused integration suite
- [ ] 跑 Ruff
- [ ] 做 spec compliance review
- [ ] 做 code-quality review
- [ ] 再决定是否进入：
  - richer workflow/review API
  - broader query API
  - Postgres/service-mode follow-up

## Exit Criteria

本计划收口时应满足：

- API app 已经有明确 storage runtime wiring
- read-only storage-backed endpoints 可稳定返回当前关键对象
- extract route 保持不回归
- 系统已经形成最小 DB-backed runtime slice，而不只是内部 repository 可用
