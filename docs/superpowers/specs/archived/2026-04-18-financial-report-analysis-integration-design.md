# 财报分析接入设计文档

## 1. 目的

本文档定义财报分析能力如何被其他项目接入，重点面向 `/home/like/mycode/finanice/TradingAgents-CN` 这类带大模型与 agent 的 Python 项目。

目标不是让外部项目直接消费底层 extractor 输出，而是建立一层受控 adapter，使外部系统只访问：

- 已裁决的标准事实
- 已派生的 TTM 与单季度数据
- 可追溯的证据
- 可判断是否可用的质量闸门

## 2. 接入原则

接入层必须遵守以下原则：

1. 外部项目通过独立 HTTP API 接入，不直接依赖底层解析细节或跨仓库 import 核心实现
2. 大模型不直接消费 `candidate_facts` 或原始 block payload
3. 大模型不自行计算 TTM、不自行做单位换算、不自行解释未校验数字
4. 财报分析包负责产出可信结构化结果，大模型负责解释和推理
5. 接入层要显式暴露质量状态，防止上层把可疑数据当成确定事实
6. `report/` 作为转发调用方时，应尽量透传 analysis service contract，而不是重新发明一套 analysis schema

第一阶段港股输入策略：

- 调用方若请求港股财报分析，接入层默认只使用英文版港股披露
- 繁体中文版不作为第一阶段的核心数字来源
- 后续阶段可以在不改变主账本来源的前提下，把繁体中文版加入辅助证据链

## 3. 推荐接入层次

推荐三层结构：

### 3.1 底层：财报分析包

负责：

- 文档解析
- 事实账本
- 单位统一
- TTM 派生
- 校验
- 分析快照

### 3.2 中间层：独立 analysis service API

主服务暴露稳定 HTTP contract，例如：

- `POST /api/v1/analysis/extract`
- `GET /health`

这层统一屏蔽底层复杂对象和重算细节，是 `report/` 与 `TradingAgents-CN` 的共同上游。

### 3.3 顶层：调用方 client / agent

调用方项目内可以再包一层本地 client，例如：

- `get_report_facts`
- `get_report_analysis_snapshot`
- `get_ttm_metrics`
- `get_validation_report`

大模型只负责：

- 调用 adapter 获取结构化结果
- 基于 `canonical_facts / derived_facts / analysis_snapshot / validation_report` 生成解释和结论

大模型不负责：

- 解析 PDF
- 计算 TTM
- 决定单位换算
- 直接使用未经校验的候选数字

## 4. 主接入方式

### 4.1 主路径：独立 HTTP API

对于 `TradingAgents-CN` 和 `report/`，推荐主路径都是直接调用 `financial-report-analysis` 的独立 HTTP API。

推荐入口：

- `POST /api/v1/analysis/extract`
- `GET /health`

### 4.2 兼容路径：嵌入式 app factory

当部署环境要求同进程承载时，可嵌入启动 analysis app，但这不改变主集成契约仍为 HTTP。

## 5. 推荐适配接口

### 5.1 主入口

```http
POST /api/v1/analysis/extract
```

请求体第一阶段支持：

- `pdf_path`
- `pdf_url`
- 文件上传
- `market`
- 可选分析参数，如 `min_confidence`

用途：

- 给上层 agent 的主入口
- 返回可以直接进入模型推理的结果集

### 5.2 健康检查

```http
GET /health
```

用途：

- 给调用方做服务发现和存活检测

## 6. 建议输入对象

```json
{
  "pdf_path": "/abs/path/to/report.pdf",
  "pdf_url": null,
  "market": "CN",
  "min_confidence": null
}
```

设计原则：

- 同时支持 `pdf_path`、`pdf_url`、上传文件，但第一阶段以 `pdf_path` 为 happy path
- `report/` 转发时尽量透传请求体，而不是重组为另一套 analysis query
- 后续可以扩展更多选项，但不能破坏主返回契约

## 7. 建议主返回对象

```python
@dataclass
class AnalysisResult:
    document: dict
    canonical_fact_set_id: str
    derived_fact_set_id: str
    validation_report_id: str
    quality_gate: str
    key_facts: list[dict]
    ttm_facts: list[dict]
    analysis_snapshot: dict
    blocked_items: list[dict]
```

字段含义：

- `document`：当前文档摘要信息
- `canonical_fact_set_id`：事实账本主事实集合
- `derived_fact_set_id`：TTM、单季度差分等派生事实集合
- `validation_report_id`：对应校验报告
- `quality_gate`：质量闸门结果
- `key_facts`：供大模型高频消费的核心事实子集
- `ttm_facts`：供估值与趋势分析的 TTM 子集
- `analysis_snapshot`：已生成的结构化分析结果
- `blocked_items`：因为质量或依赖问题被阻断的项目

## 8. 大模型允许消费的数据范围

大模型允许直接消费：

- `canonical_facts`
- `derived_facts`
- `analysis_snapshot`
- `validation_report`
- `evidence_bundle`

大模型不应直接消费：

- `candidate_facts`
- 原始 block payload
- 原始 prompt / completion
- `provisional` custom metric
- 未通过校验的核心数字

## 9. 质量闸门

analysis service 应统一输出：

- `quality_gate = pass | review | fail`

建议判定规则：

### 9.1 `pass`

可以进入自动分析链路。

典型条件：

- 无 error 级 validation issue
- 核心指标单位已确认
- TTM 依赖完整
- 不依赖 provisional custom metric

### 9.2 `review`

允许展示，但必须提示“需要人工复核”。

典型条件：

- 存在 warning 级关键 issue
- 单位有继承推断但尚未强确认
- 单季度差分与披露值存在小幅不一致

### 9.3 `fail`

禁止进入核心分析链路。

典型条件：

- 存在 error 级 validation issue
- 核心数值缺失或冲突无法裁决
- TTM 依赖缺失
- 核心分析必须依赖 provisional custom metric

## 10. 给 TradingAgents-CN 的约束

`TradingAgents-CN` 的 agent 使用本项目时，应遵守：

1. 不直接读取本项目源码后自定义解释财报
2. 不绕过 HTTP contract 直接操作底层 fact pipeline
3. 不在上层重新计算 TTM 或单位转换
4. 不把 `quality_gate=review/fail` 的结果当成生产级确定结论
5. 必要时引用 `evidence_bundle` 支撑输出结论

## 11. Skill 与包的关系

本项目的主交付物是：

- 独立 analysis service
- 包内领域实现与 app factory

不是：

- 仅靠 skill 作为生产能力载体

skill 只应作为大模型或 agent 的“使用规范层”，例如告诉模型：

- 什么时候调用哪个接口
- 哪些字段允许进入推理
- 哪些字段必须带 validation
- 什么情况下应停止自动分析并转人工复核

一句话总结：

**跨项目复用靠独立 HTTP API，服务内部复用靠包，模型使用规范靠 skill。**

## 12. 当前代码状态的风险提示

在当前仓库现状下，不能把旧 extractor 直接当成生产级权威数据源开放给 `TradingAgents-CN`。

原因：

- 当前主链路仍然偏 extractor 思路
- `normalized_facts / canonical_facts / resolver / validation / TTM` 尚未完整落地
- A 股与港股在术语、单位、期间上的差异仍会放大错误

因此在新包完成前：

- 不建议让 `TradingAgents-CN` 的大模型直接消费当前 extractor 输出
- 应先完成新包和 adapter，再逐步对上层 agent 开放

## 13. 结论

推荐接入方式是：

- 财报分析项目产出独立 analysis service
- `report/` 保留 `/extract/analysis`，但作为 HTTP forwarding client
- `TradingAgents-CN` 推荐直连 analysis service
- 上层大模型只消费经过质量闸门保护的结构化结果

通过这种方式：

- 财报解析与分析能力保持统一
- 上层 agent 不会直接放大底层抽取误差
- 后续版本升级、重算、审计和证据回链都更可控
## 14. Task 7 Phase-1 Validation Matrix

Task 7 should be driven by a small set of real sample reports rather than only
synthetic payloads. The goal of this phase is not to prove a complete
extractor. The goal is to lock down the Phase-1 service boundary, forwarding
behavior, and quality-gate semantics with representative CN and HK inputs.

### 14.1 Required Sample Anchors

- CN annual happy path:
  `report/downloads/cn_stocks/688008/annual/2024_年度报告.pdf`
- HK English supported path:
  `report/downloads/hk_stocks/09987/` quarterly and semi-annual English PDFs
- HK non-English unsupported path:
  `report/downloads/hk_stocks/01810/annual/2020_annual_zh.pdf`

### 14.2 Expected Phase-1 Outcomes

- CN annual sample:
  the independent analysis service should accept the input and return a valid
  analysis envelope. The outcome may be `pass` or `review`, but it must not be
  treated as an input error.
- HK English samples:
  the supported path should continue to preserve period extraction, fact /
  evidence mapping, and forwarding compatibility.
- HK non-English sample:
  Phase-1 must classify this as `unsupported_in_phase1` and expose it through
  `quality_gate=review`, not `fail`.

### 14.3 Task 7 Scope

Task 7 is allowed to make small behavior fixes that are required to satisfy the
real-sample matrix above, including:

- language-policy branching in the analysis pipeline
- quality-gate mapping fixes between `review` and `fail`
- forwarding-layer regression fixes so that upstream gate semantics are not
  rewritten
- README and integration-spec synchronization

Task 7 should not expand into a broad "complete extractor" effort.

### 14.4 Acceptance Criteria

- `financial-report-analysis/tests/integration/test_analysis_api.py` covers:
  - CN annual real-sample happy path
  - HK non-English unsupported path
- `report/tests/integration/test_hk_09987_period_extraction.py` remains green
  for the HK English supported path
- `report/tests/integration/test_cn_annual_period_regression.py` remains green
  for the CN annual sample path
- forwarding-related tests in `report/` confirm that `quality_gate` and
  unsupported semantics from the analysis service are preserved
- `financial-report-analysis/README.md`, `report/README.md`, and this spec all
  describe the same Phase-1 support boundary
