# Minimal API Verification Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在当前 extraction + durable storage + query/audit + document ledger baseline 之上，提供一个最小、可调用、可验证的 API vertical slice，证明系统已经具备统一入口，而不是只存在于内部模块与 repository 测试中。

**Architecture:** API 第一版保持 read-first，建立在现有 storage-backed query/audit 和 artifact persistence contract 之上。对外只暴露最小资源模型：`report`、`artifact`、`dataset`、`dataset_audit`、`recompute_run`。`report_source` 作为 future write-contract 预留，只有在启用最小写入口时才进入第一轮实现。

**Tech Stack:** Python 3.12, existing `financial-report-analysis` API layer, existing storage package, existing P5 artifacts/review/lineage/recompute/document-ledger baseline, pytest, Ruff.

---

## Scope Check

本计划要做：

- 最小 read-only API contract
- `report_source` extensible request model
- report coverage / artifact / dataset / dataset audit / recompute read endpoints
- focused integration，验证 API 可以直接消费 storage-backed objects

本计划不做：

- full CRUD / workflow API
- dashboard / BI 查询层
- approval workflow
- whole-document LLM API
- broad search API
- Postgres migration

## File Structure

### New files

- `financial-report-analysis/tests/unit/test_api_minimal_slice.py`
- `financial-report-analysis/tests/integration/test_api_minimal_slice.py`

### Existing files to modify

- `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
  - 增加 minimal API response shapes；若启用写入口，再补 request shapes。
- `financial-report-analysis/src/financial_report_analysis/api/routes.py`
  - 增加最小 endpoint 接线。
- `financial-report-analysis/src/financial_report_analysis/api/app.py`
  - 如需要，补 app-level wiring 或依赖注入入口。
- `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
  - 只在 API slice 真需要时补极少量 read helpers；优先复用现有 query/audit contract。

## Task 0: API Boundary Inventory

**Files:**
- Create: `docs/architecture-analysis/2026-04-24-minimal-api-verification-slice-boundary-inventory.md`

- [ ] 明确当前 storage-backed baseline 已经能直接支撑哪些 API resources：
  - report coverage
  - extracted artifact
  - dataset
  - dataset audit
  - recompute result
- [ ] 记录哪些对象仍然不应进入第一版 API：
  - raw statement table ledger
  - fact ledger internals
  - approval workflow state

## Task 1: Freeze Input / Output Contract

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Test: `financial-report-analysis/tests/unit/test_api_minimal_slice.py`

- [ ] 先写 failing tests，锁住：
  - 最小 response models：
  - report coverage response
  - artifact response
  - dataset response
  - dataset audit response
  - recompute result response
- [ ] 如果后续启用 `POST /manifests/register`，再补 extensible `report_source` request contract：
  - `source.kind`
    - `local_path`
    - `url`
    - `upload`
    - `manifest_entry_ref`
  - 第一版 only-supported kind:
    - `local_path`

## Task 2: Storage-Backed Read Service Wiring

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/api/app.py` (only if needed)
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py` (only if strictly needed)
- Test: `financial-report-analysis/tests/unit/test_api_minimal_slice.py`

- [ ] 先写 failing tests，锁住 service layer 如何调用：
  - report coverage query
  - artifact lookup
  - dataset lookup
  - dataset audit lookup
  - recompute lookup
- [ ] 不在 API 层重新拼 SQL；优先复用现有 repository query contract

## Task 3: Minimal Endpoint Wiring

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/api/app.py` (only if needed)
- Test: `financial-report-analysis/tests/integration/test_api_minimal_slice.py`

- [ ] 先写 failing tests，锁住：
  - `GET /issuers/{issuer_id}/reports`
  - `GET /reports/{issuer_id}/{fiscal_year}/{report_type}`
  - `GET /artifacts/{artifact_id}`
  - `GET /datasets/{dataset_id}`
  - `GET /datasets/{dataset_id}/audit`
  - `GET /recompute-runs/{run_id}`
- [ ] 保持 endpoint 极薄，不把 repository 表结构直接暴露出去

## Task 4: Optional Minimal Write Entry

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Test: `financial-report-analysis/tests/integration/test_api_minimal_slice.py`

- [ ] 仅在确有必要时实现：
  - `POST /manifests/register`
- [ ] 如果实现，会使用现有 historical-ingestion registry
- [ ] 如果当前验证闭环无需写接口，本 task 可标记 `not needed`

## Task 5: Focused End-to-End Verification

**Files:**
- Modify: `financial-report-analysis/tests/integration/test_api_minimal_slice.py`

- [ ] 先写 focused integration，验证：
  - 已注册 report 可通过 API 查到 coverage
  - persisted extracted artifact 可通过 API 读取
  - persisted dataset 可通过 API 读取
  - dataset audit / review / lineage / validation / quality gate 可通过 API 读取
  - recompute result 可通过 API 读取
- [ ] 不跑 broad matrix；只用小 deterministic sample

## Task 6: Closeout

- [ ] 跑 focused unit suite
- [ ] 跑 focused integration suite
- [ ] 跑 Ruff
- [ ] 做 spec compliance review
- [ ] 做 code-quality review
- [ ] 再决定是否进入下一阶段：
  - richer workflow / approval API
  - broader query API
  - service-mode / Postgres follow-up

## Exit Criteria

本计划收口时应满足：

- 系统已经有最小统一 API 入口
- report / artifact / dataset / dataset_audit / recompute 均可通过 API 读取
- API 不依赖直接访问本地 JSON 或手写 SQL
- 后续工作可以在此基础上扩 richer workflow，而不必重新定义第一层资源模型
