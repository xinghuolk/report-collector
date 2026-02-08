# HK 报告周期统一数据结构改造计划（v1.1）

## 1. 背景与目标

当前系统对港股报告主要使用 `report_type` + `report_quarter` 表达报告周期，无法完整表达以下场景：

- `Q3 Results`: 同时包含 `Q3 单季` 与 `Q1-Q3 累计`。
- `Q4 and Full Year Results`: 同时包含 `Q4 单季` 与 `全年`，并常带上年同比列。
- `Interim Report`: 可能只有 `H1 累计`，也可能能推导 `Q2 单季`。

同时，提取逻辑存在“取错位置/错列”的风险，影响字段正确率。

目标：

1. 建立统一、可扩展、可追溯的返回结构。
2. 明确“单季值”“累计值”“同比值”并存时的建模方式。
3. 降低错位提取概率，并对每个值提供证据、置信度与质量标记。

---

## 2. 核心设计结论

### 2.1 模型分层

采用三层模型：

1. `document`：文档元信息（公告类型、年份、发布日期、是否审计）。
2. `periods`：文档内包含的一个或多个期间（如 `2025Q3_YTD`、`2025FY`、`2024FY`）。
3. `facts`：具体指标值，每个值明确关联一个 `period_id`。

### 2.2 周期定义规则（强约束）

- Q1 报告：必有 `Q1_YTD`，可选 `Q1_SINGLE`（常相同）。
- 半年报：必有 `H1_YTD`，可选 `Q2_SINGLE`。
- Q3 报告：必有 `Q3_YTD`，可选 `Q3_SINGLE`。
- Q4+全年公告：必有 `FY`，可选 `Q4_SINGLE`。
- 年报：通常只保留 `FY`。

结论：不要假设每类报告都“必须同时有累计+单期”，用“必有 + 可选”建模。

### 2.3 字段语义约束（v1.1 修订）

1. `fiscal_quarter` 仅对 `scope = single_quarter` 有意义；其他 `scope` 设为 `null`。
2. `ytd_through_quarter` 仅对累计类周期有意义：
   - `Q1_YTD=1`, `H1_YTD=2`, `Q3_YTD=3`, `FY=4`。
3. 对同比列，`periods` 内显式建模比较期（如 `2024FY`）并标注 `is_comparison: true`。
4. 资产负债表使用时点语义：`scope = point_in_time`，使用 `as_of_date`，`start_date = null`。

---

## 3. 统一返回结构（V2）

```json
{
  "document": {
    "stock_code": "09987",
    "market": "HK",
    "doc_type": "results_announcement|interim_report|annual_report",
    "announcement_date": "2026-02-04",
    "fiscal_year": 2025,
    "primary_period_id": "2025FY",
    "is_audited": false,
    "source_url": "https://..."
  },
  "periods": [
    {
      "period_id": "2025Q4_SINGLE",
      "scope": "single_quarter",
      "fiscal_quarter": 4,
      "ytd_through_quarter": null,
      "start_date": "2025-10-01",
      "end_date": "2025-12-31",
      "as_of_date": null,
      "is_primary": false,
      "is_comparison": false
    },
    {
      "period_id": "2025FY",
      "scope": "full_year",
      "fiscal_quarter": null,
      "ytd_through_quarter": 4,
      "start_date": "2025-01-01",
      "end_date": "2025-12-31",
      "as_of_date": null,
      "is_primary": true,
      "is_comparison": false
    },
    {
      "period_id": "2024FY",
      "scope": "full_year",
      "fiscal_quarter": null,
      "ytd_through_quarter": 4,
      "start_date": "2024-01-01",
      "end_date": "2024-12-31",
      "as_of_date": null,
      "is_primary": false,
      "is_comparison": true
    },
    {
      "period_id": "BS_2025-12-31",
      "scope": "point_in_time",
      "fiscal_quarter": null,
      "ytd_through_quarter": null,
      "start_date": null,
      "end_date": null,
      "as_of_date": "2025-12-31",
      "is_primary": true,
      "is_comparison": false
    }
  ],
  "facts": [
    {
      "statement": "income_statement",
      "metric": "revenue",
      "period_id": "2025FY",
      "value": 11300,
      "currency": "USD",
      "unit": "million",
      "source_method": "table",
      "confidence": 0.96,
      "evidence_ids": ["ev_001"],
      "is_derived": false,
      "derivation_formula": null
    },
    {
      "statement": "income_statement",
      "metric": "revenue",
      "period_id": "2024FY",
      "value": 10820,
      "currency": "USD",
      "unit": "million",
      "source_method": "table",
      "confidence": 0.95,
      "evidence_ids": ["ev_002"],
      "is_derived": false,
      "derivation_formula": null
    },
    {
      "statement": "income_statement",
      "metric": "gross_margin",
      "period_id": "2025FY",
      "value": 15.3,
      "currency": null,
      "unit": "percent",
      "source_method": "derived",
      "confidence": 1.0,
      "evidence_ids": ["ev_001", "ev_003"],
      "is_derived": true,
      "derivation_formula": "gross_margin = gross_profit / revenue * 100"
    }
  ],
  "evidence": [
    {
      "evidence_id": "ev_001",
      "page": 2,
      "table_index": 5,
      "row_label": "Total revenues",
      "column_header": "Year ended Dec 31, 2025",
      "raw_value": "11.3 billion",
      "snippet": "Total revenues increased ..."
    }
  ],
  "quality": {
    "status": "ok|partial|review",
    "issues": [
      {
        "type": "unit_inferred|period_ambiguous|cross_check_failed|segment_table_skipped",
        "severity": "warning|error",
        "message": "...",
        "affected_facts": ["income_statement.revenue@2025FY"]
      }
    ]
  }
}
```

---

## 4. 代码改造范围

### 4.1 元数据与周期识别

主要文件：

- `report/src/pdf_parser/content_extractor.py`
- `report/src/pdf_sources/hkex_downloader.py`

改造点：

1. 新增 `period_classifier`（可先写在 `content_extractor.py` 内部，再独立到模块）：
   - 输入：标题 + 首页文本 + 报告日期。
   - 输出：`doc_type`、`periods[]`、`primary_period_id`。
2. 修正报告类型判定优先级：
   - 对 “Q4 and Full Year Results Announcement” 优先识别为 `results_announcement`，并产出 `FY + Q4_SINGLE + comparison periods`。
3. 在 downloader 侧保存更多原始字段到 `metadata_json`：
   - `title`
   - `release_time`
   - `web_path`
   - 初步 `period_hint`（仅 hint，不作为最终口径）

### 4.2 提取结果结构升级

主要文件：

- `report/src/pdf_parser/content_extractor.py`
- `report/src/handlers/pdf_handler.py`
- `report/src/api/schemas/extract.py`

改造点：

1. 在 `extract()` 输出中新增：
   - `document`
   - `periods`
   - `facts`
   - `evidence`
   - `quality`
2. `facts` 改为 `evidence_ids: List[str]`，支持多证据链。
3. `facts` 增加：
   - `is_derived`
   - `derivation_formula`
4. `document` 增加：
   - `is_audited`
5. 保留现有 `income_statement/balance_sheet/...` 作为兼容层（V1），并在响应中标记：
   - `schema_version: "v2"`
   - `compat_mode: true`

### 4.3 DB 与缓存

主要文件：

- `report/src/pdf_manager.py`

改造点：

1. 推荐新增独立表 `extracted_financial_data_v2`（默认方案）：
   - `file_hash`
   - `schema_version`
   - `document_json`
   - `periods_json`
   - `facts_json`
   - `evidence_json`
   - `quality_json`
2. 若不新增独立表，则必须改为 `(file_hash, schema_version)` 联合唯一索引。
3. 缓存读写同时支持 V1/V2，并严格按版本隔离。
4. 增加迁移脚本（Alembic 或项目内轻量 SQL 迁移）。

---

## 5. 防错策略（避免提取到错误位置）

### 5.1 表级约束

只在“目标报表表格”提取，不再全局扫表：

- 利润表仅来自包含 `income statement / statements of income / 损益表` 的表。
- 资产负债表仅来自包含 `balance sheet / financial position / 资产负债表` 的表。
- 现金流仅来自包含 `cash flow / 现金流量表` 的表。

### 5.2 列级约束（关键）

对每张目标表先解析列头并建立 `column_role`：

- `single_q`（当季）
- `ytd`（累计）
- `full_year`
- `prior_year_comparison`
- `point_in_time`

仅允许从匹配目标 `period_id` 的列中取值。

### 5.3 行级约束

引入行标签标准化（label normalization）：

- 先标准化空格/换行/大小写。
- 行标签需“完整词匹配 + 黑名单过滤”：
  - 示例：`net profit` 与 `profit attributable to noncontrolling interests` 不可混淆。

### 5.4 证据与置信度

每个提取值至少记录：

- `page`
- `table_index`
- `row_label`
- `column_header`
- `raw_value`
- `source_method`

置信度建议：

- `0.9+`：表格定位 + 行列双命中。
- `0.7-0.9`：文本正则 + 单位可解释。
- `<0.7`：仅 fallback 命中，进入 `quality.status = review`。

### 5.5 交叉校验

- 支持 `EPS * shares ≈ net_profit` 等交叉校验规则。
- 校验失败写入 `quality.issues[]` 的结构化条目（`type = cross_check_failed`）。

---

## 6. 分阶段实施计划

### Phase 1: 周期识别与结构打底（1-2 天）

交付：

1. `periods` 与 `document` 输出。
2. 对样本可识别：
   - `09987/2025_quarterly_en.pdf` => `Q3_YTD (+ Q3_SINGLE 可选)`
   - `09987/2026_quarterly_en.pdf` => `FY + Q4_SINGLE (+ 2024FY comparison)`
   - `09987/2025_semi_annual_en.pdf` => `H1_YTD`
   - 港股常规 `Annual Report` => `FY`
3. 增加一个中文 A 股年报样本回归，确保中文路径不回归。
4. 保持 V1 兼容输出。

验收：

- 单元测试覆盖上述样本标题和首页文本。

### Phase 2: 事实模型与证据链（2-3 天）

交付：

1. `facts[]` 与 `evidence[]`。
2. 每个核心指标都能追溯到证据对象（支持多证据）。
3. 对同比列产出 comparison `period_id` 对应的 facts。
4. 缓存层支持 `schema_version=v2` 且版本隔离。

验收：

- 对 09987 Q3/Q4 样本，`revenue/net_profit/operating_cash_flow` 均有 `evidence_ids`。

### Phase 3: 防错与质量门控（2-3 天）

交付：

1. 表级+列级+行级约束生效。
2. `quality.status` 与结构化 `issues[]` 输出。
3. 低置信度数据可被 API 消费侧过滤（可新增 `min_confidence` 参数）。

验收：

- 错位样本回归测试通过。
- 不再出现“Q4+全年公告被识别为 annual 单周期”的回归问题。

---

## 7. 测试计划

### 7.1 新增测试文件建议

- `report/tests/unit/test_period_classifier.py`
- `report/tests/unit/test_fact_evidence_mapping.py`
- `report/tests/integration/test_hk_09987_period_extraction.py`
- `report/tests/integration/test_cn_annual_period_regression.py`

### 7.2 关键用例

1. 标题含 `Q3 Results` + `third quarter ended` -> `Q3_YTD`。
2. 标题含 `Q4 and Full Year Results` -> `FY + Q4_SINGLE + prior year comparison`。
3. `Interim Report` + `six months ended` -> `H1_YTD`。
4. `Annual Report` -> `FY` 且 `is_audited=true`（若文档明确审计状态）。
5. 存在歧义列头时，低置信度并进入 `quality.review`。

---

## 8. 兼容与迁移策略

1. API 版本协商采用 Header 为主：
   - `Accept: application/vnd.financial-reports.v2+json`
   - 或 `X-Schema-Version: v2`
2. 同时保留 query 参数 `schema=v1|v2` 作为调试/回放兼容入口（后续可 deprecate）。
3. V2 产出后继续填充 V1 字段，避免前端/调用方一次性改动。
4. 迁移期监控两套结果差异（字段级 diff）。
5. 缓存严格按 `file_hash + schema_version` 隔离，避免脏读。

---

## 9. 风险与应对

1. PDF 表格切分不稳定：
   - 预案：增加文本块抽取 fallback，但置信度降低。
2. 中英文混合标题导致分类波动：
   - 预案：标题 + 首页 + release_time 联合投票判定。
3. 历史缓存无证据链：
   - 预案：仅对新提取写入 V2，旧缓存按需重建。

---

## 10. 本计划对应当前问题清单

1. 回答“是否 Q1 只有 Q1，semi 有 Q1+Q2 与 Q2，Q3 有 Q1-Q3 与 Q3，Q4 有全年与 Q4”：
   - 设计上支持这些组合；
   - 但不是每份报告都必须同时提供“累计+单期”，以“必有 + 可选”约束实现。
2. 回答“是否加证据”：
   - 必须加证据；
   - 同时必须加列定位和置信度，否则仍会错位。
3. 回答“当前提取太容易错误”：
   - 根因在全局正则 + 松散表格取值；
   - 本方案通过表/列/行三级约束收紧提取范围。

