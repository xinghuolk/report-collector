# HTTP -> DB -> Turtle 3-5Y Workflow Gap Analysis

> **日期:** 2026-04-24
> **目的:** 对照统一路线图与当前代码现状，判断如何尽快打通一条“HTTP 输入 PDF -> 写入数据库 -> 返回结果 -> 通过 API 读取/编排 3-5 年龟龟投资数据”的最小正确路径，同时避免为了短期可跑而引入后续高返工成本。

## 0. 2026-04-24 状态更新

本文最初写于 DB-backed write/build slice 完成之前。以下 gap 已经关闭：

- `/api/v1/analysis/extract` 可以 opt-in 写入 durable storage。
- extract write path 会注册 report/document/document_version/extraction_run baseline。
- 已经有 `extract_write_service.py` 承接 DB-backed extract persistence。
- 已经有 `p5/db_assembly_service.py` 承接 DB-backed dataset / Turtle build。
- extract route 已支持 `build_dataset` / `build_turtle` opt-in flags。
- persisted dataset / turtle / review / lineage 可以通过 storage-backed API/read surface 查回。

因此，本文中的 “HTTP write path 仍不是 DB-backed” 和 “缺少统一 ingest/build orchestration boundary” 已不再准确。Task 5 又补齐了只读 `3-5Y persisted dataset availability view`。按当前“单纯数据提供”业务范围，DB-backed data provider baseline 已经完成：

1. 单年年报 PDF 可以抽取并持久化。
2. dataset / turtle / review / lineage 可以通过 storage-backed surface 读回。
3. `p5/runner.py` 仍保留 JSON-first runner，但不应作为 availability view 的运行时主路径。
4. availability view 已回答 persisted facts / missing states / lineage。
5. upload/url acquisition、async job handle、retry/rebuild policy、approval workflow、workflow product 生命周期属于 future/out of current scope，不是当前 gap。
6. 已完成的只读 availability view 不等于完整 Turtle workflow orchestration；但完整 workflow orchestration 暂不需要。

## 1. Executive Summary

当前系统已经完成了两块非常关键的基础：

- durable storage baseline
- storage-backed read API runtime slice

这意味着系统已经从“只能在本地 JSON / 内部模块里跑”推进到了“数据库可承接核心 artifact，HTTP 已能稳定从数据库读关键对象”。

当前系统又进一步补齐了 opt-in **DB-backed write/build slice** 和只读 **3-5Y persisted dataset availability view**。按当前用户目标，完整数据提供闭环已经是：

```text
HTTP PDF ingress
-> report/document/extraction_run registration
-> extraction
-> DB persistence of extracted artifact + deeper ledger
-> dataset / turtle export assembly
-> DB persistence of dataset/review/lineage/recompute
-> synchronous or handled response
-> follow-up API lookup
-> issuer/year-range 3-5Y availability query
```

**结论：**

- DB-backed ingest/build 的最小 slice 已经完成。
- 只读 **3-5Y persisted dataset availability view** 已完成。
- workflow orchestration / workflow products 暂时不需要，应作为 future bucket 保留，不作为当前阻塞项。

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

## 4. 当前未完成的关键断点（更新后）

### 4.1 HTTP write/build path 已有最小 DB-backed slice

当前 `/api/v1/analysis/extract` 已经可以：

- opt-in persist extract result to storage
- 注册 report/document/document_version/extraction_run baseline
- persist extracted artifact
- opt-in build dataset / turtle export
- persist dataset / turtle / review / lineage surfaces
- 返回 stable lookup IDs

仍不应该继续在这个 route 上堆：

- 多 issuer / 多年度 workflow
- upload/url acquisition governance
- async job scheduling
- approval workflow

因此，API 侧现在是：

- **read from DB: yes**
- **single-report write/build slice: yes**
- **3-5Y persisted dataset availability view: implemented**
- **broader 3-5Y Turtle workflow orchestration / workflow products: future / out of current scope**

### 4.2 P5 runner 仍是 JSON-first

当前 `p5/runner.py` 的主路径仍使用：

- `P5JsonArtifactRepository`

这意味着：

- dataset/turtle 的正式组装主路径还没有切到 DB repository
- 即使数据库可以存这些对象，也还没有一个正式的 DB-backed runner 把它们串起来

### 4.3 3-5Y persisted availability view boundary 已补齐

当前系统已经有单次 extract/write/build 的零件：

- HTTP extract
- storage repositories
- historical ingestion service
- document ledger persistence
- dataset assembly
- review/lineage/recompute persistence
- 面向多年份数据消费的只读 availability view 层

该只读视图现在负责：

- 接收 issuer / year range / report type
- 查询已有 report/artifact/dataset coverage
- 返回缺口状态、可用 facts 和 lineage
- 不调用现有 extract/build path
- 不输出 Turtle 策略对象，只输出通用数据视图

如果未来业务需要，后续可基于该视图继续产品化 workflow orchestration：acquisition、retry/rebuild、approval、job handle、以及 Turtle 策略侧输入编排。它们不属于当前数据提供闭环的未完成项。

### 4.4 3-5 年 workflow products 属于 future scope

当前已经有：

- P5 dataset artifact
- Turtle export artifact
- 3-5Y persisted dataset availability view

当前暂不需要把“按 issuer / 3-5 fiscal years / required metric coverage”查询结果升级成 workflow products。若未来需要，这一层才负责：

- 对缺失 report 发起 acquisition
- 对缺失 artifact 或 stale 状态发起 rebuild/retry
- 把 present / missing / out_of_scope 变成用户可执行的 workflow plan
- 管理 async job handle、approval、review transitions
- 编排 Turtle 策略侧输入

当前应避免两个误读：不要把“3-5 年数据视图已完成”误读为“3-5Y Turtle workflow orchestration 已完成”；也不要把暂不需要的 workflow orchestration 继续当成当前 gap。

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

状态：

- 已完成最小 slice。后续不应把它继续扩成多年份 workflow 核心。

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

状态：

- 已完成 API-triggered DB-backed assembly service。
- 仍可后续决定是否把 CLI runner 也收编为 DB-first。

最小职责：

- 用 DB repository 替换 JSON-first persistence 主路径
- 保留 artifact contract，不重写 dataset logic
- 让 dataset/turtle build 成为正式 service，不再只是脚本式 runner

### Phase 3: 3-5Y Persisted Dataset Availability View

目标：

- 面向 issuer + year range 提供只读、多年份、可追溯的数据可用性视图

最小职责：

- 查询已有 report / extracted artifact / canonical facts coverage
- 对缺失年份和缺失指标给出清晰状态
- 返回 3-5 年 facts / missing states / lineage summary
- 不触发 extract / recompute / Turtle build

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

## 10. 建议立即产出的文档（更新后）

历史上，按当时代码状态继续往下做，最合理的下一份正式 spec 是：

`financial-report-analysis-3-5y-persisted-dataset-availability-view-design`

它应明确：

- issuer/year-range availability view service 边界
- 如何复用现有 storage-backed read/write/build path
- coverage / missing / stale / recompute-needed 状态
- persisted facts 与 lineage 的多年份 response contract
- 查询接口只读，不触发 extract/recompute/build
- 与 upload/url acquisition、approval workflow、Turtle 策略编排的边界

该只读 availability view 已实现；后续只有在业务需要 workflow/job/product lifecycle 时，才应聚焦更广义的 3-5Y Turtle workflow orchestration / workflow products。

## 11. Final Recommendation

**已完成：**

- `3-5Y persisted dataset availability view`

**未来如果需要才做：**

- 基于 availability view 的 3-5Y Turtle workflow orchestration / workflow products

**下一步不应该做：**

- 继续只扩 read-only API
- 直接把 `/api/v1/analysis/extract` 变成全能 write/workflow endpoint
- 继续把 JSON runner 扩成长期主路径
- 提前做 approval/workflow 全套

当前已完成的最小正确路线是：

```text
existing DB-backed single-report write/build slice
-> 3-5Y persisted dataset availability view
```

## 12. 最小全流程验证当前状态

当前单报告竖切已经可以证明：

```text
HTTP extract
-> DB-backed extracted artifact persistence
-> optional dataset / Turtle build
-> persisted dataset / turtle / review / lineage readback
```

Task 5 已经补齐了第一条面向数据消费的多年份只读闭环：

```text
issuer + fiscal-year range
-> availability planning
-> reuse existing persisted extracted artifacts
-> identify missing / stale / recompute-needed years
-> assemble available 3-5Y data view
-> return coverage explanation, audit, lineage
-> read back through stable API
```

因此，本文早期提出的 availability view spec 已经不是下一步“待定义能力”。按当前“单纯数据提供”范围，最小全流程已经完成；更广义 workflow orchestration / workflow products 是 future scope。

如果未来要把当前数据提供层升级成 workflow/product 层，再考虑 6 类能力：

1. **Workflow orchestration boundary**
   - 需要一个独立的 3-5Y workflow entrypoint，消费 availability view 的覆盖计划。
   - 不应继续把多年份 workflow 塞进 `/api/v1/analysis/extract`。

2. **Report discovery / ingest decision**
   - 对 `missing_report` / `missing_extracted_artifact` 年份，需要定义发现报告、排队抽取、或只返回缺口的策略。
   - 第一版可以不自动 rebuild，但 response 必须明确哪些年份需要人工或后续 workflow 补齐。

3. **DB-first multi-year product assembly**
   - 需要从 persisted extracted artifacts / canonical facts 组装 3-5Y workflow product。
   - JSON runner 可以继续作为兼容或离线工具，但不应作为长期 runtime 主路径。

4. **Reuse / recompute policy**
   - 需要定义什么时候复用已有 artifact，什么时候触发 recompute，什么时候只返回缺口。
   - availability view 给出覆盖状态，workflow layer 负责把这些状态转成可执行策略。

5. **Stable workflow product and readback**
   - workflow product 返回值至少应包含：`issuer_id`、`year_range`、`metric_profile`、`coverage_summary`、`source_artifact_ids`、`product_artifact_id`。
   - dataset / turtle / review / lineage 信息必须能通过 storage-backed API/read surface 查回。

6. **Focused workflow verification matrix**
   - 默认验证应复用 seed DB / mocked extracted artifact / availability view fixture，而不是每次跑完整 real-PDF matrix。
   - 最小测试应覆盖：
     - 一个 issuer 的 3 个年份中 2 年已覆盖、1 年缺失。
     - workflow 能复用 availability view 给出的已有 extracted artifacts。
     - 缺失年份进入 workflow product explanation，而不是被忽略。
     - product / audit / lineage 可读回。
     - `/api/v1/analysis/extract` 默认行为不被多年份 workflow 污染。

这意味着如果未来需要下一份正式 spec，不应再定义“单报告写入 DB”或“只读 availability view”能力，而应定义更上层的：

`financial-report-analysis-3-5y-turtle-workflow-products-design`

它的验收目标应该基于已完成的 availability view：

```text
seeded DB artifacts
-> 3-5Y availability request
-> explicit availability plan
-> workflow orchestration decision
-> facts / missing states / lineage from persisted data
-> stable product readback
```

真实 PDF 验证可以继续作为 workflow seed smoke test，但不应作为第一层 correctness 测试的默认前提。
