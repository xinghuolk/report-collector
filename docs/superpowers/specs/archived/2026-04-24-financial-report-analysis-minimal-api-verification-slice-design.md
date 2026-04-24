# 财报分析 Minimal API Verification Slice 设计

> **状态:** Brainstorming spec
> **日期:** 2026-04-24
> **阶段:** Post-Storage Minimal API Slice
> **范围类型:** 最小端到端验证链路

## 1. 目标

本阶段不是要把 `financial-report-analysis` 一次性做成完整产品 API。

本阶段只做一件事：

> 用一条最小、可调用、可验证的 API 链路，证明当前已经完成的 extraction、storage、review、lineage、recompute、document ledger 能够通过统一入口被真实消费。

这条最小链路要验证：

- report 是否已注册
- extracted artifact 是否可读
- dataset 是否可读
- dataset audit / review / lineage / validation / quality gate 是否可读
- recompute 结果是否可读

## 2. 非目标

本阶段不包含：

- broad product API
- dashboard / BI 查询层
- approval workflow
- whole-document LLM API
- 自定义 metric workflow 全套写操作
- Postgres / service-mode 架构重写

## 3. 设计原则

### 3.1 Read-First

第一版 API 以读取与验证为主，不追求写操作做满。

### 3.2 Storage-Backed

API 应直接建立在当前 durable storage / query / audit baseline 之上，而不是绕回本地 JSON 路径或测试夹具。

### 3.3 Audit-Aware

最小 API 不是只返回 artifact payload，还应能暴露：

- review surface
- lineage
- validation
- quality gate
- recompute result

### 3.4 Source Contract Must Be Extensible

如果后续引入写入口，即使第一版只实现本地 PDF 路径，也不应把 API contract 设计成只能吃 `pdf_path` 的死结构。

## 4. 可选写入口的统一输入抽象

### 4.1 `report_source`

如果后续启用最小写入口，报告输入应抽象为统一的 `report_source`：

```json
{
  "issuer_id": "CN_601919",
  "fiscal_year": 2025,
  "report_type": "annual",
  "source": {
    "kind": "local_path",
    "path": "/absolute/path/to/report.pdf"
  }
}
```

### 4.2 支持的 `source.kind`

写入口 contract 应预留：

- `local_path`
- `url`
- `upload`
- `manifest_entry_ref`

但第一版实现只要求：

- `local_path`

其余类型：

- contract defined
- implementation deferred

### 4.3 为什么这样设计

这样可以同时满足：

- 当前最稳定主路径仍然是本地 PDF / manifest entry
- 未来支持 URL、上传、manifest ref 时不需要重做 request shape
- 同时又不会把一个当前未启用的写请求模型硬塞进 read-only API 第一版

## 5. 内部资源模型

第一版最小 API 只围绕以下资源：

- `report`
- `extracted_artifact`
- `dataset`
- `dataset_audit`
- `recompute_run`

这些资源已经和当前 durable storage 主路径对齐。

## 6. 推荐的最小 endpoint 集

### 6.1 Coverage / Registry

- `GET /issuers/{issuer_id}/reports`
  - 列出 available fiscal years / registered reports
- `GET /reports/{issuer_id}/{fiscal_year}/{report_type}`
  - 返回 report coverage 与 extracted availability

### 6.2 Artifact / Dataset

- `GET /artifacts/{artifact_id}`
  - 返回 extracted artifact
- `GET /datasets/{dataset_id}`
  - 返回 dataset artifact

### 6.3 Audit / Recompute

- `GET /datasets/{dataset_id}/audit`
  - 返回 dataset audit read model
- `GET /recompute-runs/{run_id}`
  - 返回 recompute result

## 7. 第一版写接口策略

### 7.1 可选最小写入口

如果需要写入口，最多建议：

- `POST /manifests/register`

它只负责：

- register reports into historical registry

### 7.2 可以暂时不做写接口

如果目标只是验证最小闭环，那么第一版甚至可以先只做 `GET`。

写路径仍可以通过：

- runner
- manifest
- repository
- storage integration

来完成。

因此，第一版如果保持 read-only：

- `report_source` 只保留为 spec-level future contract
- 不要求进入第一轮实现与测试

## 8. Response Shape 原则

### 8.1 Artifact / Dataset

偏原始 durable object：

- extracted artifact
- dataset artifact
- recompute result

### 8.2 Coverage / Audit

偏 read model：

- report coverage
- dataset audit

也就是说：

- 不直接泄露底层 SQL schema
- 也不把 API contract 等同于 repository 表结构

## 9. 第一版成功标准

第一版 API slice 完成时，应满足：

- 可以从 API 查到某个 report 是否已注册、是否已有 extracted artifact
- 可以读取一个 extracted artifact
- 可以读取一个 dataset artifact
- 可以读取一个 dataset audit view
- 可以读取一次 recompute result
- 不需要调用方直接读数据库或本地 JSON 文件

## 10. 推荐阶段顺序

1. 先写 minimal API spec / plan
2. 先做 read-only verification slice
3. 如果需要，再补一个最小 `POST /manifests/register`
4. 之后再评估是否扩：
   - richer review API
   - broader query API
   - workflow / approval API

## 11. 结论

最小 API slice 的职责不是“把所有后端能力都 HTTP 化”，而是：

- 验证当前系统已经形成统一入口
- 把 storage-backed query / audit / dataset capability 暴露成真实可调用链路
- 为后续 API、service mode 和 UI integration 提供稳定起点
