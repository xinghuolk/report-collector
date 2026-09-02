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
- `POST /api/v1/reports/hk/download` - 下载单个已选择的港股财报
- `POST /api/v1/reports/hk/batch-download` - 批量下载港股
- `GET /api/v1/pdfs` - 列出已下载PDF

### 下载已选择的港股财报

使用已选报告的 HKEX HTTPS URL 下载单份港股财报：服务会在校验后按请求中提供的
`url` 原样下载，不搜索报告，也不会调用提取或缓存。该接口固定使用 `market=HK` 和
`auto_extract=false`；响应使用现有的 `APIResponse` 结构。

`announcement_at` 和 `announcement_date` 均为独立的可选字段。`announcement_at` 必须是
带 `Z` 或 UTC 偏移量的 ISO/RFC3339 时间；仅提供 `announcement_date` 时不会合成时间戳。
请求会校验五位港股代码、HKEX HTTPS 主机、`annual`/`semi_annual`/`quarterly` 报告类型、
1990--2100 年、`en`/`zh` 语言，以及（提供时）非空白标题。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/reports/hk/download \
  -H 'Content-Type: application/json' \
  -d '{"stock_code":"00700","url":"https://www1.hkexnews.hk/listedco/report.pdf","title":"Tencent 2025 Annual Report","report_type":"annual","report_year":2025,"language":"en","announcement_at":"2026-03-18T16:30:00+08:00","announcement_date":"2026-03-18"}'
```

成功响应：

```json
{
  "success": true,
  "data": {
    "pdf_id": 123,
    "file_path": "/data/reports/00700/annual/2025_annual_en.pdf",
    "file_name": "2025_annual_en.pdf",
    "stock_code": "00700",
    "market": "HK",
    "report_year": 2025,
    "language": "en"
  },
  "error": null,
  "message": "下载成功"
}
```

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
