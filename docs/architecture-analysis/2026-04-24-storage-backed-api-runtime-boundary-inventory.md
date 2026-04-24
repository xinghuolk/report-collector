# Storage-Backed API Runtime Boundary Inventory

> **日期:** 2026-04-24
> **阶段:** Storage-Backed API Runtime Slice
> **用途:** Task 0 boundary inventory

## 2026-04-24 Closeout Update

本文件原本是 phase-entry boundary inventory。当前 `Storage-Backed API Runtime Slice` 已完成并收口：

- `create_app(storage_db_path=...)` / runtime override 已落地
- app state 已提供 `ApiRuntime`
- read-only storage-backed endpoints 已落地
- `/api/v1/analysis/extract` 后续也已支持 opt-in DB persistence 与 opt-in dataset/Turtle build

因此，“Phase-Entry Runtime 断点”保留为历史入口状态，不再代表当前 gap。

当前仍开放的是：

- upload/url acquisition API
- workflow / approval write API
- document-ledger deeper objects 的 HTTP read surface
- 3-5 年 Turtle workflow API

## 当前 API runtime 已有对象

- `create_app()` app factory
- module-global `app = create_app()` uvicorn 入口
- `ApiRuntime` bundle on `app.state.runtime`
- `get_runtime(request)` request-scoped runtime accessor
- `GET /health`
- `POST /api/v1/analysis/extract`

## 当前 storage-backed baseline 已有对象

- issuer/year report coverage
- extracted artifact
- dataset artifact
- dataset audit view
- recompute result

## Phase-Entry Runtime 断点

- API app 还没有 app-level storage dependency wiring
- route 还不能通过统一 runtime 读取 durable storage
- 当前 extract route 仍是即时 ingestion + pipeline，不是 DB-backed read path

## 第一轮 runtime slice 不暴露的 deeper objects

- raw statement table ledger
- fact ledger internals
- approval state
- document-ledger deeper persistence objects

## 第一轮 runtime contract

- app factory 负责 runtime wiring
- runtime 以单一 bundle 形式挂在 `app.state.runtime`
- runtime bundle currently carries `storage_db_path`, `storage_engine`, `storage_repository`, and `historical_ingestion_service`
- tests 可以通过显式传入 runtime 或 temp SQLite path override
- 若未提供 storage path，API app 仍可正常启动并保持现有 routes 可用

## 当前已落地 baseline

- `create_app(...)` 已支持显式 `storage_db_path` 或 runtime override
- app state 已稳定提供 `runtime` bundle
- read-only storage-backed endpoints 已覆盖：
  - issuer reports
  - report coverage
  - extracted artifact
  - dataset artifact
  - dataset audit
  - recompute result
