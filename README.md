# 财报收集工具集合

> 从官方网站下载和管理中国、港股上市公司财报 PDF 文件的工具集

## 项目结构

```
report-collector/
├── report/             # 核心 MCP 服务器 - 财报 PDF 收集 (Python)
├── pdf-reader-mcp/     # PDF 阅读器 MCP 服务器 (Node.js)
├── cninfo/             # 巨潮资讯网数据检索工具
└── cninfo_scraper/     # 巨潮资讯网批量爬虫
```

## 快速开始

```bash
cd report
uv sync
uv run python -m src.main
```

---

## AI 工具集成配置

### Claude Desktop

编辑配置文件：
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

将 `<YOUR_PATH>` 替换为项目实际路径，例如 `/home/user/report-collector/report`

```json
{
  "mcpServers": {
    "financial-reports": {
      "command": "uv",
      "args": ["run", "--directory", "<YOUR_PATH>/report", "python", "-m", "src.main"]
    }
  }
}
```

### Cursor

编辑 `~/.cursor/mcp.json`（全局）或项目根目录 `.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "financial-reports": {
      "command": "uv",
      "args": ["run", "--directory", "<YOUR_PATH>/report", "python", "-m", "src.main"]
    }
  }
}
```

### Claude Code (CLI)

```bash
# 添加到用户全局配置（所有项目可用）
claude mcp add financial-reports -s user -- uv run --directory <YOUR_PATH>/report python -m src.main

# 添加到项目配置（仅当前项目，会创建 .mcp.json）
claude mcp add financial-reports -s project -- uv run --directory <YOUR_PATH>/report python -m src.main

# 查看已配置的服务器
claude mcp list

# 移除服务器
claude mcp remove financial-reports -s user
```

配置文件位置：
- **用户全局**: `~/.claude.json`
- **项目共享**: `<项目根目录>/.mcp.json`（提交到 git）
- **项目私有**: `~/.claude.json` 中的项目特定配置

手动编辑 `~/.claude.json`（用户全局）：

```json
{
  "mcpServers": {
    "financial-reports": {
      "command": "uv",
      "args": ["run", "--directory", "<YOUR_PATH>/report", "python", "-m", "src.main"]
    }
  }
}
```

或项目根目录 `.mcp.json`（项目共享）：

```json
{
  "mcpServers": {
    "financial-reports": {
      "command": "uv",
      "args": ["run", "--directory", "<YOUR_PATH>/report", "python", "-m", "src.main"]
    }
  }
}
```

### VS Code + Continue

编辑 `~/.continue/config.json`：

```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "stdio",
          "command": "uv",
          "args": ["run", "python", "-m", "src.main"],
          "cwd": "<YOUR_PATH>/report"
        }
      }
    ]
  }
}
```

### Windsurf

编辑 `~/.codeium/windsurf/mcp_config.json`：

```json
{
  "mcpServers": {
    "financial-reports": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.main"],
      "cwd": "<YOUR_PATH>/report"
    }
  }
}
```

### Cline (VS Code 扩展)

在 VS Code 设置中配置，或编辑 `settings.json`：

```json
{
  "cline.mcpServers": {
    "financial-reports": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.main"],
      "cwd": "<YOUR_PATH>/report"
    }
  }
}
```

---

## Windows 配置

Windows 系统配置示例：

```json
{
  "mcpServers": {
    "financial-reports": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.main"],
      "cwd": "C:\\Users\\YourName\\projects\\report-collector\\report"
    }
  }
}
```

如果 uv 不在 PATH 中，使用完整路径：

```json
{
  "mcpServers": {
    "financial-reports": {
      "command": "C:\\Users\\YourName\\.local\\bin\\uv.exe",
      "args": ["run", "python", "-m", "src.main"],
      "cwd": "C:\\Users\\YourName\\projects\\report-collector\\report"
    }
  }
}
```

---

## 验证配置

```bash
# 测试服务器启动
cd <YOUR_PATH>/report
uv run python -m src.main

# 运行测试
uv run pytest
```

配置成功后，AI 助手可以使用以下工具：

### A 股工具

| 工具 | 功能 | 主要参数 |
|------|------|----------|
| `search_cn_reports` | 搜索 A 股财报 | `stock_code`, `report_type`, `max_count` |
| `download_cn_report` | 下载单个 A 股财报 | `stock_code`, `report_type`, `url` |
| `download_stock_reports` | 批量下载 A 股财报 | `stock_code`, `report_type`, `max_count` |

### 港股工具

| 工具 | 功能 | 主要参数 |
|------|------|----------|
| `search_hk_reports` | 搜索港股财报 | `stock_code`, `report_type`, `max_count` |
| `download_hk_reports` | 下载港股财报 | `stock_code`, `report_type`, `max_count` |

**港股参数说明：**
- `stock_code`: 港股代码（如 `00700` 腾讯、`01810` 小米、`09988` 阿里巴巴）
- `report_type`: `annual`（年报）、`semi_annual`（中期报告）、`quarterly`（季报）
- `max_count`: 最大返回/下载数量

### 通用工具

| 工具 | 功能 | 主要参数 |
|------|------|----------|
| `list_downloaded_pdfs` | 列出已下载文件 | `stock_code`, `market`, `limit` |
| `get_pdf_info` | 获取 PDF 详情 | `pdf_id` 或 `file_path` |
| `extract_pdf_content` | 提取财务数据 | `pdf_id` 或 `file_path` |
| `get_collection_stats` | 获取统计信息 | - |
| `get_cache_stats` | 获取缓存统计 | - |
| `cleanup_cache` | 清理提取缓存 | `days` |

---

## 使用示例

配置完成后，可以直接与 AI 对话：

### 港股示例

```
用户: 帮我搜索小米最近的年报

AI: [调用 search_hk_reports: stock_code="01810", report_type="annual"]
找到以下小米年报：
1. 2024 年度報告
2. 2023 年度報告
3. 2022 年度報告

用户: 下载最新的

AI: [调用 download_hk_reports: stock_code="01810", report_type="annual", max_count=1]
已下载: downloads/hk_stocks/01810/annual/2024_年度報告.pdf
```

### A 股示例

```
用户: 帮我搜索贵州茅台的年报

AI: [调用 search_cn_reports: stock_code="600519", report_type="annual"]
找到以下茅台年报：
1. 2024年年度报告
2. 2023年年度报告
3. 2022年年度报告

用户: 下载最新的

AI: [调用 download_cn_report: stock_code="600519", report_type="annual"]
已下载: downloads/cn_stocks/600519/annual/2024_年度报告.pdf
```

---

## 故障排除

### 连接失败

1. 确认路径正确（必须是绝对路径）
2. 确认 uv 已安装：`which uv`
3. 确认依赖已安装：`cd report && uv sync`

### 工具不显示

1. 重启 AI 应用
2. 检查日志输出
3. 确认 MCP 服务器正常启动

### Windows 路径问题

- 使用正斜杠 `/` 或双反斜杠 `\\`
- 避免路径中有空格或中文

---

## 许可证

MIT License
