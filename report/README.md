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
- `POST /api/v1/extract/content` - 提取结构化财务数据
- `POST /api/v1/extract/tables` - 提取表格
- `POST /api/v1/extract/text` - 提取全文本

### 缓存
- `GET /api/v1/cache/stats` - 缓存统计
- `DELETE /api/v1/cache/cleanup` - 清理缓存
- `POST /api/v1/cache/warm` - 预热缓存

## 数据源

- **A股**: 巨潮资讯网 (cninfo.com.cn)
- **港股**: 港交所披露易 (hkexnews.hk)
