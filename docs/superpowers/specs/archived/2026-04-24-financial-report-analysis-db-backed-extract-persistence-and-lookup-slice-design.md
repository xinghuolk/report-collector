# 财报分析 DB-Backed Extract Persistence And Lookup Slice 设计

> **状态:** Draft for review
> **日期:** 2026-04-24
> **阶段:** Post-Storage Runtime Write Slice
> **范围类型:** 最小 HTTP 写入闭环

## 1. 目标

本阶段的目标不是直接做完整的 workflow API，也不是现在就把 3-5 年 Turtle orchestration 一次做满。

本阶段只做一件关键事：

> 把现有 `/api/v1/analysis/extract` 从“即时返回的内存分析入口”推进到“真正写入 durable storage，并返回稳定 lookup key 的最小 DB-backed write slice”。

完成后，系统应能支持这条最小垂直链路：

```text
HTTP request
-> extract
-> persist to DB
-> return stable identifiers
-> GET read endpoints load persisted objects back
```

这条 slice 的意义是：

- 证明 API 不只是“能从 DB 读”
- 也已经能把真实 extract 结果写进 DB
- 为后续 dataset/turtle build、3-5 年编排、review workflow 提供稳定主路径

## 2. 非目标

本阶段不包含：

- broad workflow / approval API
- URL / upload acquisition orchestration 做满
- whole-document LLM assessment
- 将 dataset/turtle build 同步塞进当前 extract route
- 完整 3-5 年 Turtle orchestration
- Postgres / service-mode 重写

本阶段也不要求：

- 立即把 `p5/runner.py` 完全重写成 DB-first
- 立即把所有 deeper ledger object 都暴露到 API

## 3. 为什么现在做这一步

当前系统已经完成：

- durable storage baseline
- document ledger baseline
- storage-backed read API runtime

但仍存在一个关键断点：

- `/api/v1/analysis/extract` 还不会写 DB
- read API 已能读 artifact / dataset / audit / recompute
- 但没有一个 API write path 会把 extract 结果放进去

这会导致系统呈现出一种“半打通”状态：

- `read from DB`: yes
- `write to DB`: not yet

如果现在直接跳去做：

- 3-5 年 Turtle orchestration
- richer workflow / approval API

就会在最关键的 write path 还不稳定时，把上层复杂度抬起来，后续返工风险很高。

因此，最合理的下一步就是先补这条最小 DB-backed write slice。

## 4. 当前现状

### 4.1 已有能力

当前已具备：

- `SqlAlchemyP5ArtifactRepository`
- `HistoricalIngestionService`
- `document / document_version / extraction_run` 持久化 baseline
- `GET /issuers/...`
- `GET /reports/...`
- `GET /artifacts/...`
- `GET /datasets/...`
- `GET /datasets/.../audit`
- `GET /recompute-runs/...`

也就是说：

- DB schema 已有
- repository 已有
- runtime wiring 已有
- read API 已有

### 4.2 关键缺口

当前 `/api/v1/analysis/extract`：

- 接收 `pdf_path` / `pdf_url`
- 即时跑 ingestion + pipeline
- 返回 analysis payload

但不会：

- 注册 report identity
- 记录 document / document_version
- 创建 extraction_run
- 持久化 extracted artifact
- 返回 `artifact_id` / `run_id` / `dataset_id`

因此，它还不是 durable-system 的正式写入口。

### 4.3 第一版 identity 约束

当前 durable storage 的 `report` / `document` / `extraction_run` 承接，并不适合建立在“只知道一个 PDF 路径”这种弱 identity 上。

因此，本阶段必须明确：

- durable write path 不能只依赖 `pdf_path` / `pdf_url` 自己推断 report identity
- 第一版写入请求必须显式提供最小 report identity

第一版最小建议为：

- `issuer_id`
- `fiscal_year`
- `report_type`
- `stock_code`
- `market`
- `pdf_path`

其中：

- `report_type` 第一版只允许 `annual`
- `issuer_id` / `stock_code` / `fiscal_year` 作为 durable report key 的外部输入

这意味着本阶段不会尝试：

- 从 PDF 文本里“猜” issuer/year 再注册 report
- 依赖后验解析结果补 report identity

## 5. 设计原则

## 5. 设计原则

### 5.1 先把 extracted write path 打通，不在这一步塞入 dataset orchestration

这一步的主目标是：

- durable extract persistence
- stable lookup ids

dataset/turtle 的更深编排应作为后继阶段推进，而不是塞进同一个 route。

### 5.2 Route 保持薄，真正的写逻辑进入 orchestration/service layer

不要把 `/api/v1/analysis/extract` 继续演化成“巨型全能 route”。

推荐结构：

- route 做 request parsing / response serialization
- 新增一个内部 write orchestration service
- service 负责：
  - runtime lookup
  - report registration
  - extraction
  - persistence
  - stable response payload assembly

### 5.3 优先复用现有 contract，不重写主数据模型

优先复用：

- current extract response semantics
- existing storage repository
- historical ingestion service
- document ledger baseline

不要在这一阶段重新发明：

- 新 artifact shape
- 新 report identity
- 新 review/lineage contract

### 5.4 保持与现有 read API 对齐

write slice 的结果必须能被当前 read API 直接消费和验证。

这意味着：

- persist 后拿到的 `artifact_id`
- 对应的 report coverage 状态
- 后续 audit / dataset path

都应能由现有 GET endpoints 读回。

## 6. 推荐架构

### 6.1 新增内部 orchestration service

推荐新增一个窄 service，例如：

- `analysis_write_service.py`
- 或 `api/write_runtime.py`

职责：

1. 接收 normalized extract request
2. 解析 runtime storage dependency
3. 归一化 source identity
4. 注册 report / document / document_version
5. 创建 extraction run
6. 执行 extract
7. 构建 extracted artifact
8. 写入 DB
9. 返回 extract result + lookup ids

### 6.2 Response contract 升级为“analysis result + durable ids”

当前 `AnalysisExtractResponse` 应扩成包含 durable lookup 信息。

最小建议新增：

- `artifact_id`
- `report_id` 或 `report_key`
- `extraction_run_id`

可选但不要求本阶段一定有：

- `dataset_id`
- `recompute_run_id`

原则：

- 先返回最稳定、一定存在的 id
- 不要为了“看起来完整”而返回尚未稳定生成的衍生 id

### 6.3 Dataset/turtle build 的阶段策略

本阶段默认 **不** 在 `POST /api/v1/analysis/extract` 里同步构建 dataset/turtle。

原因：

- 当前最关键的断点是 write path 还没进入 durable system
- dataset/turtle 组装主路径仍有明显 JSON-first 历史包袱
- 如果本阶段把 extract persistence 和 dataset service consolidation 混在一起，implementation scope 会明显变大

因此本阶段的明确策略是：

- 同步持久化 `extracted artifact`
- 返回稳定 lookup ids
- 用现有 read API 验证 `report coverage` 与 `artifact` 已能读回

后继阶段再做：

- DB-backed dataset/turtle assembly consolidation
- 3-5 年 Turtle orchestration

## 7. 最小请求与响应

### 7.1 第一版请求

第一版 durable write path 建议明确支持：

- `issuer_id`
- `stock_code`
- `fiscal_year`
- `report_type`
- `market`
- `pdf_path`
- `min_confidence`

其中：

- `pdf_path` 是本阶段唯一进入 durable write path 的 source kind
- `pdf_url` 可以继续保留在即时 extract 兼容路径里，但 **不进入 durable persistence**

原因：

- `pdf_url` 一旦进入 durable path，就会引入下载、缓存、不可变文件定位、`report_file` 绑定策略等 acquisition 问题
- 这些问题当前被明确排除在本阶段范围外

因此，本阶段应把规则写清楚：

- `pdf_path` + 显式 report identity -> durable write slice
- `pdf_url` -> 继续维持现有即时 extract 行为，或明确返回 unsupported for persistence

### 7.2 第一版响应

第一版建议保留当前已有分析结果，同时新增：

- `artifact_id`
- `extraction_run_id`
- `report_registered`
- `persisted: true`

本阶段不要求：

- `dataset_id`
- `recompute_run_id`

## 8. 数据流

推荐数据流：

```text
POST /api/v1/analysis/extract
-> validate request
-> resolve runtime
-> validate report identity
-> register report
-> ensure document/document_version
-> create extraction_run(status=running)
-> run ingestion + analyze_report-compatible extraction path
-> persist extracted artifact
-> mark extraction_run(status=completed)
-> return analysis payload + lookup ids
```

失败时：

- extraction input error -> `400`
- storage runtime missing -> `503`
- persistence / integrity failure -> `500`

## 9. 测试策略

本阶段至少需要一条真正的 DB-backed integration path：

1. 启动 `TestClient(create_app(storage_db_path=...))`
2. `POST /api/v1/analysis/extract`
3. 响应返回 stable ids
4. 用这些 ids 再调用：
   - `GET /artifacts/{artifact_id}`
   - `GET /reports/{issuer_id}/{fiscal_year}/{report_type}`

还要保留并验证：

- 现有 `extract` 错误语义不回归
- 现有 `/health` 不回归
- package import guard 不回归

## 10. 与后续阶段的关系

本阶段完成后，后续推荐顺序应为：

1. `DB-backed extract persistence and lookup slice`
2. `DB-backed dataset/turtle assembly consolidation`
3. `3-5 year Turtle workflow orchestration`
4. `richer workflow / review API`

也就是说：

- 这一步是 write path 正式进入 durable system
- 但它不是最终 workflow 终局

## 11. 成功标准

本阶段完成时，应满足：

- `/api/v1/analysis/extract` 能把结果写入 DB
- response 返回稳定 lookup ids
- 当前 read API 能直接读回刚写入的 `artifact` 与 `report coverage`
- extract route 仍保持现有输入与错误语义稳定
- 实现没有绕开 report/document/extraction_run contract

## 12. 结论

下一步最合理的工作不是：

- 再扩 read-only API
- 也不是直接做完整 3-5 年 Turtle workflow

而是：

> 把现有 extract HTTP 入口推进成最小 DB-backed write slice，并让它与现有 read API 形成真正闭环。

这一步会是当前路线图里“最接近用户目标、同时又最不容易返工”的下一阶段。*** End Patch
