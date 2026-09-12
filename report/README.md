# 财报收集服务器

中国A股、港股上市公司财报PDF收集与提取服务。

## 功能

- 搜索财报：从巨潮资讯网和港交所披露易搜索上市公司财报
- 下载财报：批量下载年报、半年报、季报PDF
- 内容提取：自动提取利润表、资产负债表、现金流量表等财务数据
- 缓存管理：提取结果缓存，提升重复查询效率

## 运行模式

### MCP模式（默认）

```bash
# 使用uv运行
uv run python -m src.server --mode mcp

# 或使用入口点
uv run financial-reports-mcp
```

### HTTP API模式

```bash
# 启动HTTP服务器
uv run python -m src.server --mode http --host 0.0.0.0 --port 8000

# 访问API文档
# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

## API端点

### 搜索
- `GET /api/v1/reports/cn/search` - 搜索A股财报
- `GET /api/v1/reports/hk/search` - 搜索港股财报

### 下载
- `POST /api/v1/reports/cn/download` - 下载单个A股财报
- `POST /api/v1/reports/cn/batch-download` - 批量下载A股
- `POST /api/v1/reports/hk/batch-download` - 批量下载港股
- `GET /api/v1/pdfs` - 列出已下载PDF

### 查询
- `GET /api/v1/pdfs/{pdf_id}` - 获取PDF详情
- `GET /api/v1/stats` - 获取收集统计
- `DELETE /api/v1/pdfs/cleanup` - 清理旧PDF

### 提取
- `POST /api/v1/extract/content` - 提取结构化财务数据（默认 V2）
- `POST /api/v1/extract/tables` - 提取表格
- `POST /api/v1/extract/text` - 提取全文本

### 缓存
- `GET /api/v1/cache/stats` - 缓存统计
- `DELETE /api/v1/cache/cleanup` - 清理缓存
- `POST /api/v1/cache/warm` - 预热缓存

## 数据源

- **A股**: 巨潮资讯网 (cninfo.com.cn)
- **港股**: 港交所披露易 (hkexnews.hk)

## 提取接口（V2）

`POST /api/v1/extract/content` 默认返回 V2 结构：

- `document`: 文档层信息（股票、报告类型、primary_period_id、is_audited）
- `periods`: 标准化期间（`full_year` / `year_to_date` / `single_quarter` / `point_in_time`）
- `facts`: 指标事实（`statement`、`metric`、`period_id`、`value`、`confidence`、`evidence_ids`）
- `evidence`: 证据链（页码、表索引、行标签、列头、原始值）
- `quality`: 质量状态与结构化问题（如 `unit_inferred`、`period_ambiguous`、`cross_check_failed`）

### 版本协商

优先级：`query schema` > `X-Schema-Version` > `Accept`

- Query: `schema=v1|v2`
- Header: `X-Schema-Version: v1|v2`
- Header: `Accept: application/vnd.financial-reports.v2+json`

### 提取请求示例

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/extract/content?schema=v2" \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_id": 123,
    "force_refresh": false,
    "min_confidence": 0.8
  }'
```

`min_confidence` 仅对 V2 生效，用于过滤低置信度 `facts`。

## MCP工具返回（最新）

`extract_pdf_content` 工具已更新：

- 新参数：`schema_version`（`v1|v2`，默认 `v2`）
- 新参数：`min_confidence`（0-1，仅 V2 生效）
- 返回格式：成功和失败都返回 JSON 文本（不再混用纯文本错误）

### MCP调用参数示例

```json
{
  "name": "extract_pdf_content",
  "arguments": {
    "pdf_id": 123,
    "schema_version": "v2",
    "min_confidence": 0.85
  }
}
```

### MCP返回片段示例（V2）

```json
{
  "success": true,
  "schema_version": "v2",
  "document": {
    "stock_code": "09987",
    "report_type": "quarterly",
    "primary_period_id": "2025Q3_YTD"
  },
  "periods": [
    {"period_id": "2025Q3_YTD", "scope": "year_to_date"},
    {"period_id": "2025Q3_SINGLE", "scope": "single_quarter"}
  ],
  "facts": [
    {
      "statement": "income_statement",
      "metric": "revenue",
      "period_id": "2025Q3_YTD",
      "value": 12345.67,
      "confidence": 0.96,
      "evidence_ids": ["ev_0001"]
    }
  ],
  "evidence": [
    {"evidence_id": "ev_0001", "page": 12, "table_index": 1}
  ],
  "quality": {"status": "ok", "issues": []}
}
```
## Financial Report Analysis Integration

- Domain package and standalone service live under
  `financial-report-analysis/`
- `POST /api/v1/extract/analysis` in `report/` is an HTTP forwarding layer
  only; it does not host the analysis core
- Phase-1 supported scope:
  - CN Chinese reports
  - HK English reports
- Phase-1 unsupported scope:
  - HK non-English reports are surfaced as
    `unsupported_in_phase1` with `quality_gate=review`
- External callers should rely on the analysis envelope:
  `canonical_fact_set_id`, `derived_fact_set_id`, `validation_report_id`,
  `quality_gate`, `key_facts`, `ttm_facts`, `analysis_snapshot`,
  `blocked_items`
