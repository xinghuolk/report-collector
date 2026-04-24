# Financial Report Analysis 3-5Y Persisted Dataset Availability View Design

> **状态:** Active spec
> **日期:** 2026-04-24
> **范围:** `financial-report-analysis`
> **目标:** 为 3-5 年财报数据消费提供一个只读、可追溯、基于持久化数据的数据可用性视图。

## 1. 背景

当前分支已经具备单报告级竖切：

```text
PDF extract
-> persisted extracted artifact
-> optional dataset / Turtle build
-> persisted review / lineage / audit readback
```

但这不等于已经具备 3-5 年数据消费能力。下游真正需要的是：

```text
issuer + fiscal-year range + metric profile
-> 哪些年份有数据
-> 哪些指标有值
-> 哪些数据缺失或不可用
-> 每个值来自哪个 artifact / fact / evidence
```

本轮不把 `financial_report_analysis` 扩展成投资工作流引擎。它仍然是数据提取与数据供给服务。

## 2. 定位

本轮能力命名为：

```text
3-5Y persisted dataset availability view
```

它是一个只读数据视图，不是 workflow orchestration。

服务职责：

- 从持久化层读取已有 `report` / `extracted artifact` / `canonical facts`。
- 按 issuer、年份范围和指标 profile 组织数据。
- 返回每个年份、每个指标的可用性状态。
- 返回 source artifact / source fact / evidence lineage。
- 明确说明缺失数据，而不是静默忽略。

非职责：

- 不自动读取 PDF。
- 不自动运行 extraction。
- 不自动 recompute。
- 不自动 build Turtle export。
- 不做 async job / retry / approval workflow。
- 不做投资策略判断。

## 3. 数据来源

本轮数据仍然来自真实 PDF，但 PDF 只用于预提取和持久化阶段。

推荐 anchor 数据源：

- HK `01810` 年报：`report/downloads/hk_stocks/01810/annual/`
- HK `09987` 年报：`report/downloads/hk_stocks/09987/annual/`
- CN `601919` 年报：`report/downloads/cn_stocks/601919/annual/`

第一版验证流程应分成两步：

```text
Step A: pre-extract selected real PDFs into durable storage
Step B: query availability view from persisted data only
```

Step B 不允许重新打开 PDF。这样可以同时保留真实财报样本价值，并避免查询接口变成隐式抽取工作流。

## 4. 输入

第一版内部 service 输入：

```text
issuer_id: str
start_year: int
end_year: int
metric_profile: str
report_type: "annual"
```

约束：

- `start_year <= end_year`
- 年份跨度建议为 3-5 年，但 service 不需要硬编码只能 3-5。
- 第一版只支持 `report_type="annual"`。
- `metric_profile` 只用于决定 required metrics，不用于触发 Turtle 策略计算。

建议第一版 profile：

```text
turtle_core
```

## 5. 输出

输出是通用数据视图，而不是 Turtle 业务对象。

建议 shape：

```text
issuer_id
market
stock_code
report_type
start_year
end_year
metric_profile
years[]
  fiscal_year
  report_status
  artifact_status
  metrics[]
    metric_id
    status
    value
    currency
    unit
    quality_status
    source_artifact_id
    source_fact_id
    evidence_bundle_id
coverage_summary
recommended_next_actions[]
```

`recommended_next_actions` 只是提示，不执行动作。

## 6. 状态模型

第一版状态应足够小。

年度级状态：

- `covered`
- `missing_report`
- `missing_extracted_artifact`
- `unknown`

指标级状态：

- `present`
- `missing_metric`
- `out_of_scope`
- `unknown`

预留状态：

- `stale_or_recompute_needed`

`stale_or_recompute_needed` 只有在已有 pipeline / artifact version metadata 足以判断时才输出。第一版不得伪造 stale 判断。

## 7. 服务边界

建议新增内部 service：

```text
MultiYearDatasetAvailabilityService
```

它依赖 storage repository 的只读能力：

- 查询 issuer 已登记年份。
- 查询指定年份 report coverage。
- 查询该年份 extracted artifact。
- 读取 canonical facts / missing status / review metadata。

它不依赖 PDF ingestion adapter，不依赖 semantic fallback，不依赖 P5 runner。

## 8. API 边界

建议新增只读 API：

```text
GET /issuers/{issuer_id}/dataset-availability?start_year=2021&end_year=2025&profile=turtle_core
```

该 API 应保持只读：

- 不接受 `pdf_path`。
- 不接受 upload。
- 不触发 extract。
- 不触发 recompute。
- 不写 dataset / turtle artifact。

如果后续需要补抽或重算，应由独立 ingest / recompute API 承接。

## 9. 与现有 P5 能力的关系

现有 P5 能力仍然有价值：

- `P5ExtractedArtifact` 是 persisted data 的主要输入。
- `P5DatasetRow` 的字段可以复用为 availability metric row 的基础。
- dataset review / audit / lineage 的持久化结构可以作为 readback 来源。

但本轮不要求调用 `run_p5_dataset_build()`，也不要求在查询时创建新的 `P5DatasetArtifact`。

本轮关注的是：

```text
persisted facts -> availability view
```

而不是：

```text
query -> build dataset artifact -> build Turtle export
```

## 10. 验证策略

验证分三层。

### 10.1 Unit tests

使用 fake repository / seeded records 验证：

- 已有 report + artifact + fact 时返回 `present`。
- 有 report 但无 artifact 时返回 `missing_extracted_artifact`。
- 无 report 时返回 `missing_report`。
- required metric 缺失时返回 `missing_metric`。
- out-of-profile metric 不强行返回。
- response 不触发任何 write/build/extract 方法。

### 10.2 Integration tests

使用 SQLite-backed repository seed：

- `01810` 至少两个 fiscal years。
- `09987` 至少两个 fiscal years。
- `601919` 至少两个 fiscal years。
- 每个 issuer 留一个年份作为缺失或缺 artifact 的负例。

断言：

- availability view 按年份返回。
- present facts 带 source lineage。
- missing years 不被静默忽略。
- API response 可序列化且不写入新 dataset/turtle artifact。

### 10.3 Real PDF seed smoke

真实 PDF 只用于 seed 阶段：

```text
01810 annual PDF(s)
09987 annual PDF(s)
601919 annual PDF(s)
-> extract + persist
-> availability query
```

该 smoke 不应成为每次小改动的默认收口测试。默认 closeout 仍以 unit + seeded integration 为主。

## 11. 成功标准

本轮完成后，系统应能回答：

- `01810` 指定 3-5 年范围内哪些年份已有持久化数据。
- `09987` 指定 3-5 年范围内哪些指标 present / missing。
- `601919` 指定 3-5 年范围内每个值来自哪个 persisted artifact。
- 缺失年份和缺失指标以明确状态返回。
- 查询接口不会隐式触发 PDF extraction、recompute 或 Turtle build。

## 12. 非目标

本轮不做：

- PDF 自动发现。
- PDF upload / URL acquisition。
- 自动补抽。
- 自动重算。
- async workflow / job handle。
- approval workflow。
- Turtle 策略侧输入编排。
- whole-document LLM assessment。

## 13. 路线图影响

统一路线图和 gap 文档中原先的 `3-5Y Turtle workflow orchestration` 应收窄为：

```text
3-5Y persisted dataset availability view
```

后续如果需要完整 workflow，应另开新阶段，并建立在本轮只读数据视图之上。
