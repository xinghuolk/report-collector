# 财报分析 Storage-Backed API Runtime Slice 设计

> **状态:** Brainstorming spec
> **日期:** 2026-04-24
> **阶段:** Post-Storage API Runtime Wiring
> **范围类型:** 最小 DB-backed 运行时闭环

## 1. 目标

这阶段的目标不是再定义一份新的产品 API 蓝图，而是补上当前系统最关键的一段运行时断点：

> 让 API app 真正拿到 durable storage dependency，并通过统一入口读取 report coverage、artifact、dataset、dataset audit 与 recompute。

更准确地说，这阶段要证明：

- durable storage 不只是“库里有表、有数据”
- API runtime 也已经能稳定读取这些对象
- 系统已经从“内部 repository 可用”推进到“对外统一入口可用”

## 2. 非目标

本阶段不包含：

- broad product API
- approval workflow
- URL / upload ingestion 编排
- 把 extract 主路径彻底改成 DB-first orchestration
- whole-document LLM API
- service-mode / Postgres-first 重写

## 3. 当前断点

当前系统已经具备：

- durable storage core
- historical ingestion registry
- storage-backed query / audit
- document ledger baseline

但 API runtime 仍然存在明显断点：

- `create_app()` 还没有 storage dependency wiring
- 当前 HTTP 入口主要还是：
  - `GET /health`
  - `POST /api/v1/analysis/extract`
- `extract` 是即时 ingestion + pipeline，不是 storage-backed read path

因此，当前还不能说“系统入口已经 fully DB-backed”。

## 4. 核心设计问题

### 4.1 App 如何拿到 storage dependency

本阶段必须明确：

- DB path / config 从哪里来
- engine 在哪里初始化
- repository 在哪里初始化
- tests 如何 override

推荐方向：

- `create_app(...)` 支持传入 runtime config 或 explicit storage path
- 同时允许 env/config fallback
- repository 挂在 app state 或通过 dependency helper 获取

第一轮实现至少要明确：

- `create_app(storage_db_path: str | Path | None = None)`
- 若未显式传入，则允许读取 env/config fallback
- app factory 负责：
  - engine creation
  - `initialize_database(...)`
  - repository construction
  - 把 repository 暴露到 `app.state`

### 4.2 Route 层如何读取 durable objects

route 层不应直接写 SQL，也不应复制 repository 逻辑。

推荐方向：

- routes 读取 app-level injected repository
- 直接复用现有 storage-backed query/audit contract
- 保持 endpoint 极薄

### 4.3 现有 extract endpoint 的策略

本阶段不应重写当前 `/api/v1/analysis/extract` 的主逻辑。

更稳的做法是：

- 保留现有 extract route
- 新增一组 read-only storage-backed routes
- 先把 runtime 与 DB 真正接起来

### 4.4 Response model 的边界

第一版最适合暴露：

- `report coverage`
- `extracted artifact`
- `dataset`
- `dataset audit`
- `recompute result`

不宜第一轮就暴露：

- raw statement table ledger
- fact ledger internals
- approval state

## 5. 推荐的最小 endpoint 集

- `GET /issuers/{issuer_id}/reports`
- `GET /reports/{issuer_id}/{fiscal_year}/{report_type}`
- `GET /artifacts/{artifact_id}`
- `GET /datasets/{dataset_id}`
- `GET /datasets/{dataset_id}/audit`
- `GET /recompute-runs/{run_id}`

这些 endpoint 的意义不是“功能很多”，而是它们足够验证：

- registry
- artifact
- dataset
- audit
- recompute

这条最小垂直链路已经成立。

## 6. 配置与依赖注入原则

### 6.1 SQLite-first

本阶段默认仍然是：

- SQLAlchemy
- SQLite-first

### 6.2 Test Override Must Be First-Class

API tests 必须能非常容易地：

- 指向临时 SQLite 文件
- 初始化 schema
- seed deterministic sample

否则这条 runtime slice 很难稳定验证。

### 6.3 App Factory Owns Runtime Wiring

推荐由 app factory 负责：

- storage path resolution
- engine creation
- repository wiring

而不是 route import 时就隐式初始化。

## 7. 成功标准

本阶段完成时，应满足：

- API app 能稳定拿到 storage-backed repository
- read-only routes 能从 durable storage 直接返回当前系统关键对象
- API integration tests 不需要直读本地 JSON 或手写 SQL
- extract route 继续可用，不因 runtime wiring 被破坏

## 8. 结论

这阶段真正要完成的不是“多几个 endpoint”，而是：

- app runtime
- storage dependency
- repository-backed read path

一旦这条 slice 成立，后续 richer API / workflow / service-mode 才有稳定运行时基础。
