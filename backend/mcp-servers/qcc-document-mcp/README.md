# qcc-document-mcp

本地智能文档解析 MCP Server — 与远端企查查入口互不冲突，Agent 按来源自动选用。

## 快速开始

```bash
cd backend/mcp-servers/qcc-document-mcp
npm install
node server.js    # stdio 模式，由 MCP 客户端拉起
```

要求 Node.js ≥ 20（当前 v26.0.0 ✅）。

## MCP 客户端配置

在 Cursor / CodeBuddy / Claude Desktop 的 MCP 配置中加入（与远端 QCC 入口并列，互不冲突）：

```json
{
  "mcpServers": {
    "looma-zervi": {
      "url": "http://127.0.0.1:8999/sse"
    },
    "qcc-document-mcp": {
      "command": "node",
      "args": ["backend/mcp-servers/qcc-document-mcp/server.js"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

远端 `looma-zervi` 管企业数据（credit_check 等），本地 `qcc-document-mcp` 管文件解析——两条工具线互不干扰。

## 工具列表

| 工具 | 用途 | 输入 |
|------|------|------|
| `parse_document` | 按绝对路径解析本地文件 | `filePath` (必填), `maxTextLength` (可选) |
| `parse_document_base64` | 解析 base64 文档（拖入/上传） | `base64Content` (必填), `filename` (必填) |
| `get_supported_formats` | 列出所有支持格式 | 无参数 |

## 支持的格式

| 类型 | 扩展名 | 解析引擎 |
|------|--------|----------|
| PDF | `.pdf` | pdf-parse |
| Word | `.docx` | mammoth |
| Excel | `.xlsx`, `.xls` | SheetJS |
| CSV | `.csv` | SheetJS |
| 纯文本 | `.txt`, `.log`, `.yaml`, `.yml`, `.toml`, `.env` 等 | 内置 fs |
| Markdown | `.md`, `.markdown` | 内置 fs |
| JSON | `.json`, `.jsonl`, `.ndjson` | 内置 JSON.parse |
| HTML | `.html`, `.htm` | 内置（去标签） |
| 图片 | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.svg` | 元数据（OCR 委托多模态模型） |

## 运行测试

```bash
node test.js
```

输出 `Results: 14 passed, 0 failed` 即通过。
