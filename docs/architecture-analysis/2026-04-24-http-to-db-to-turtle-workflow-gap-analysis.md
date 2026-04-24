# HTTP -> DB -> Turtle 3-5Y Workflow Gap Analysis

> **日期:** 2026-04-24
> **目的:** 对照统一路线图与当前代码现状，判断如何尽快打通一条“HTTP 输入 PDF -> 写入数据库 -> 返回结果 -> 通过 API 读取/编排 3-5 年龟龟投资数据”的最小正确路径，同时避免为了短期可跑而引入后续高返工成本。

## 1. Executive Summary

当前系统已经完成了两块非常关键的基础：

- durable storage baseline
- storage-backed read API runtime slice

这意味着系统已经从“只能在本地 JSON / 内部模块里跑”推进到了“数据库可承接核心 artifact，HTTP 已能稳定从数据库读关键对象”。

但距离用户想要的目标状态，仍缺一条真正的 **DB-backed write orchestration**：

```text
HTTP PDF ingress
-> report/document/extraction_run registration
-> extraction
-> DB persistence of extracted artifact + deeper ledger
-> dataset / turtle export assembly
-> DB persistence of dataset/review/lineage/recompute
-> synchronous or handled response
-> follow-up API lookup / 3-5Y orchestration
```

**结论：**

- 下一步不应继续优先扩 read-only API。
- 下一步也不应直接跳到完整 workflow/approval 产品化。
- 最合理的路线是新增一个 **DB-backed ingest-and-build orchestration phase**，把当前分裂的写路径统一起来。

这条路线既能最快让系统“真的跑通”，又不会破坏路线图已经建立的 storage / document-ledger / review-lineage-recompute contract。

## 2. 用户目标与架构约束

用户目标不是单纯“多几个 API endpoint”，而是：

1. 通过 HTTP 给系统一个 PDF
2. 系统写入真实数据库
3. 立即返回最小可用结果或 run handle
4. 后续再通过 API 获取已写入结果
5. 编排 3-5 年龟龟投资流程
6. 返回最终可消费结果

同时用户明确要求：

- 不能为了快速可跑而走明显错误的捷径
- 不能把临时实现变成未来必须推倒重来的主路径

因此，推荐路线必须同时满足：

- **短期可跑**
- **中期可扩到 3-5 年**
- **不绕过 document ledger / storage contract**
- **不把 JSON runner 继续扩大成事实上的主路径**

## 3. 当前已完成能力

### 3.1 Durable storage baseline

当前已完成：

- durable core models
- historical ingestion registry
- JSON / DB repository parity
- review / lineage / recompute persistence
- storage-backed query / audit
- document ledger and extraction-run persistence baseline

这意味着数据库已经不是“空壳”：

- `report`
- `report_file`
- `document`
- `document_version`
- `extraction_run`
- `statement_table`
- `fact_set`
- `validation`
- `dataset_artifact`
- `review surfaces`
- `lineage`
- `recompute`

都已经至少有 baseline schema 或 repository 承接。

### 3.2 Minimal storage-backed API runtime slice

当前已完成：

- app runtime 可以拿到 SQLite-backed repository
- HTTP 已可从数据库读取：
  - issuer reports
  - report coverage
  - extracted artifact
  - dataset
  - dataset audit
  - recompute result

这说明：

- **read path 已通**
- API app 与 durable storage 已不是孤立系统

### 3.3 Turtle dataset baseline

当前已完成：

- P5 multi-year investor dataset minimal persistence
- Turtle export artifact
- dataset/review/lineage/recompute 的最小承接

但要注意：

- 当前 `p5/runner.py` 仍以 **JSON repository** 为主
- 这条 runner 还不是 DB-first orchestration

## 4. 当前未完成的关键断点

### 4.1 HTTP write path 仍不是 DB-backed

当前 `/api/v1/analysis/extract` 的行为是：

- 接收 `pdf_path` / `pdf_url`
- 即时跑 ingestion + pipeline
- 返回分析结果

但它 **不会**：

- 注册 report/document/document_version
- 创建 extraction_run
- 写入 extracted artifact 到 DB
- 触发 dataset/turtle build 并写库
- 产生可复用的 run/result handle

因此，API 侧现在仍是：

- **read from DB: yes**
- **write to DB orchestration: no**

### 4.2 P5 runner 仍是 JSON-first

当前 `p5/runner.py` 的主路径仍使用：

- `P5JsonArtifactRepository`

这意味着：

- dataset/turtle 的正式组装主路径还没有切到 DB repository
- 即使数据库可以存这些对象，也还没有一个正式的 DB-backed runner 把它们串起来

### 4.3 缺少统一的 ingest/build orchestration boundary

当前系统已经有这些零件：

- HTTP extract
- storage repositories
- historical ingestion service
- document ledger persistence
- dataset assembly
- review/lineage/recompute persistence

但缺一个居中的编排层，负责：

- 拿到一个 report source
- 统一注册 report/document/run
- 组织 extract -> persist -> dataset build -> persist
- 给 API 层一个稳定的返回 contract

这就是当前最真实的缺口。

### 4.4 3-5 年龟龟流程还缺 dataset orchestration layer

当前已经有：

- P5 dataset artifact
- Turtle export artifact

但还没有一个“按 issuer / 3-5 fiscal years / required metric coverage”去驱动的服务层，负责：

- 选哪些 report
- 缺哪些年份
- 哪些年份需要重算
- 如何合并成一个 3-5Y Turtle dataset request

这层如果不先定义，就很容易把“P5 artifact persistence”误当成“3-5 年流程已完成”。

## 5. 可选路线

### 路线 A：继续扩 read/write API，直接把 `/api/v1/analysis/extract` 改造成全能入口

做法：

- 在现有 extract endpoint 上继续堆：
  - 持久化
  - dataset build
  - turtle build
  - 3-5 年编排

优点：

- 看起来最快

问题：

- 容易让现有 extract endpoint 变成混合职责巨型入口
- 把 ingestion、storage、orchestration、dataset assembly、workflow 返回值全塞进一个 route
- 后面几乎一定要拆

**结论：不推荐。**

### 路线 B：先做 DB-backed orchestration service，再给它最小写 API

做法：

- 新增一个内部 service / orchestration layer
- API 只负责把请求交给它
- service 负责：
  - report source normalization
  - report/document/run registration
  - extraction
  - extracted artifact persistence
  - dataset/turtle build
  - review/lineage/recompute persistence

优点：

- 边界清晰
- 能复用现有 storage / document ledger / P5 models
- 后面扩 upload/url/async runs 也不需要推翻

问题：

- 比“直接改 route”稍多一点前置设计

**结论：推荐。**

### 路线 C：先把 P5 runner DB 化，再回头补 HTTP 写入口

做法：

- 先把 `p5/runner.py` 切换成 DB repository
- 把 HTTP 写入口留到后面

优点：

- 能尽快收拢 dataset/turtle write path

问题：

- 用户最关心的是 HTTP 到 DB 的闭环
- 如果先只做 runner DB 化，系统还是不能从 HTTP 真正走完全链路
- 仍需后续再补 API/write orchestration

**结论：适合作为路线 B 的子步骤，不适合作为单独优先级第一。**

## 6. 推荐路线

推荐采用：

**路线 B 为主，路线 C 作为其内部子阶段。**

一句话说：

> 先建立一个 DB-backed ingest/build orchestration service，再用最小写 API 暴露它；同时把当前 JSON-first 的 P5 runner 收编到这条 orchestration 里，而不是继续并行存在。

## 7. 推荐的下一阶段拆分

### Phase 1: DB-backed Ingest And Build Orchestration

目标：

- 把单份 PDF 的 write path 打通

最小职责：

- 接受 `report_source`
- 注册 `report -> report_file -> document -> document_version`
- 创建 `extraction_run`
- 执行 extract
- 持久化 extracted artifact
- 构建 dataset / turtle export
- 持久化 review / lineage / recompute surfaces
- 返回一个稳定结果对象：
  - synchronous result summary
  - or run/result handle

这一步完成后，系统就能真正做到：

```text
HTTP -> DB write -> API read back
```

### Phase 2: DB-backed P5 / Turtle Assembly Service

目标：

- 把当前 JSON-first runner 收编到 DB orchestration

最小职责：

- 用 DB repository 替换 JSON-first persistence 主路径
- 保留 artifact contract，不重写 dataset logic
- 让 dataset/turtle build 成为正式 service，不再只是脚本式 runner

### Phase 3: 3-5Y Turtle Workflow Orchestration

目标：

- 面向 issuer + year range 提供真正的多年份编排

最小职责：

- 选择已有 report / artifact / dataset coverage
- 对缺失年份给出清晰状态
- 必要时触发补算
- 返回 3-5 年 Turtle dataset / export / audit summary

### Phase 4: Workflow / Review Enrichment

目标：

- 在全链路可跑后，再补 richer workflow

包括：

- async runs / job handles
- review state transitions
- approval workflow
- richer query / audit API

## 8. 为什么这样最不容易返工

这条路线避免了三种常见返工来源：

### 8.1 避免把 route 变成 orchestration 核心

如果直接把 `/api/v1/analysis/extract` 扩成全能入口，后面几乎一定要再把 orchestration 拆出去。

### 8.2 避免让 JSON runner 继续事实性主导系统

如果继续让 `P5JsonArtifactRepository` 作为组装主路径，后面 DB 化只会更痛苦。

### 8.3 避免过早做 workflow 产品层

如果现在直接冲 approval/workflow API，会在 write orchestration 还没稳定时把系统表面复杂度拉高。

## 9. 对输入形态的建议

用户已确认：

- 对外目标可接受 `upload`
- 内部最小实现可先落在 `local_path`

推荐做法是：

- API contract 预留统一 `report_source`
- Phase 1 实现只正式支持一种最稳的 source kind

建议顺序：

1. 内部 orchestration service 支持 `local_path`
2. HTTP 写入口可以先用：
   - `multipart upload` 落盘后转 `local_path`
   - 或明确仅支持 `local_path`
3. `url` 下载/缓存留到后续 acquisition layer

这样可以避免把“远端下载治理”混进当前最关键的 DB-backed write path。

## 10. 建议立即产出的文档

如果按这份分析继续往下做，最合理的下一份正式 spec 应该是：

`financial-report-analysis-db-backed-ingest-and-build-orchestration-design`

它应明确：

- orchestration service 边界
- HTTP write contract
- DB-backed persistence contract
- 与现有 `/api/v1/analysis/extract` 的关系
- 与现有 P5 runner 的收编策略
- 同步返回 vs run handle 的第一版选择

## 11. Final Recommendation

**下一步应该做：**

- `DB-backed ingest/build orchestration`

**下一步不应该做：**

- 继续只扩 read-only API
- 直接把 `/api/v1/analysis/extract` 变成全能 write/workflow endpoint
- 继续把 JSON runner 扩成长期主路径
- 提前做 approval/workflow 全套

最小正确路线是：

```text
DB-backed orchestration service
-> minimal write API
-> DB-backed P5/Turtle assembly
-> 3-5Y Turtle workflow orchestration
-> richer workflow/review API
```
