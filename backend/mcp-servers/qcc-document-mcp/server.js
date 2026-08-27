#!/usr/bin/env node

/**
 * qcc-document-mcp — Local Intelligent Document Parsing MCP Server.
 *
 * Parses documents dropped / uploaded to the chat dialog or specified by
 * local file path.  Coexists with the remote QCC (企查查) MCP entry;
 * Agents auto-route by document origin (local file vs. remote API).
 *
 * Tools:
 *   parse_document           — Parse by absolute file path
 *   parse_document_base64    — Parse from base64-encoded content + filename
 *   get_supported_formats    — List supported extensions & MIME types
 *
 * Requires: Node.js ≥ 20
 */

import { createRequire } from "node:module";
import {
  readFileSync,
  statSync,
  existsSync,
  mkdtempSync,
  writeFileSync,
  rmSync,
} from "node:fs";
import { basename, extname, join } from "node:path";
import { tmpdir } from "node:os";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const require = createRequire(import.meta.url);

// ---------------------------------------------------------------------------
// Lazy-load heavy CJS parsers via require
// ---------------------------------------------------------------------------

let _pdfParse = null;
function getPdfParse() {
  if (!_pdfParse) {
    _pdfParse = require("pdf-parse");
  }
  return _pdfParse;
}

// ---------------------------------------------------------------------------
// Supported formats registry
// ---------------------------------------------------------------------------

const SUPPORTED_FORMATS = {
  pdf: {
    extensions: [".pdf"],
    mimeTypes: ["application/pdf"],
    label: "PDF Document",
    parser: "pdf-parse",
  },
  docx: {
    extensions: [".docx"],
    mimeTypes: [
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ],
    label: "Word Document (DOCX)",
    parser: "mammoth",
  },
  xlsx: {
    extensions: [".xlsx", ".xls"],
    mimeTypes: [
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "application/vnd.ms-excel",
    ],
    label: "Excel Spreadsheet",
    parser: "xlsx (SheetJS)",
  },
  csv: {
    extensions: [".csv"],
    mimeTypes: ["text/csv"],
    label: "CSV",
    parser: "xlsx (SheetJS)",
  },
  txt: {
    extensions: [
      ".txt",
      ".log",
      ".cfg",
      ".conf",
      ".ini",
      ".env",
      ".yaml",
      ".yml",
      ".toml",
    ],
    mimeTypes: ["text/plain"],
    label: "Plain Text",
    parser: "built-in (fs)",
  },
  md: {
    extensions: [".md", ".markdown"],
    mimeTypes: ["text/markdown", "text/x-markdown"],
    label: "Markdown",
    parser: "built-in (fs)",
  },
  json: {
    extensions: [".json", ".jsonl", ".ndjson"],
    mimeTypes: ["application/json"],
    label: "JSON",
    parser: "built-in (JSON.parse)",
  },
  html: {
    extensions: [".html", ".htm"],
    mimeTypes: ["text/html"],
    label: "HTML",
    parser: "built-in (strip tags)",
  },
  image: {
    extensions: [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"],
    mimeTypes: [
      "image/png",
      "image/jpeg",
      "image/gif",
      "image/webp",
      "image/bmp",
      "image/svg+xml",
    ],
    label: "Image (metadata + note for OCR)",
    parser: "built-in (metadata only, OCR via multimodal model)",
  },
};

/**
 * Detect format from a filename.
 * @param {string} filename
 * @returns {{ key: string; info: typeof SUPPORTED_FORMATS[string] } | null}
 */
function detectFormat(filename) {
  const ext = extname(filename).toLowerCase();
  if ([".csv"].includes(ext)) return { key: "csv", info: SUPPORTED_FORMATS.csv };
  if ([".xlsx", ".xls"].includes(ext))
    return { key: "xlsx", info: SUPPORTED_FORMATS.xlsx };
  for (const [key, info] of Object.entries(SUPPORTED_FORMATS)) {
    if (info.extensions.includes(ext)) return { key, info };
  }
  return null;
}

// ---------------------------------------------------------------------------
// Path safety
// ---------------------------------------------------------------------------

/**
 * Validate that a path exists and is a regular file.
 * @param {string} filePath
 */
function validateFilePath(filePath) {
  if (!filePath || typeof filePath !== "string") {
    throw new Error("param 'filePath' is required and must be a string");
  }
  if (!existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`);
  }
  const stat = statSync(filePath);
  if (stat.isDirectory()) {
    throw new Error(`Path is a directory, not a file: ${filePath}`);
  }
  return stat;
}

// ---------------------------------------------------------------------------
// Parsers
// ---------------------------------------------------------------------------

/** @param {string} filePath */
async function parsePdf(filePath) {
  const parse = getPdfParse();
  const buf = readFileSync(filePath);
  const data = await parse(buf);
  return {
    pages: data.numpages,
    text: data.text,
    metadata: data.metadata || {},
  };
}

/** @param {string} filePath */
async function parseDocx(filePath) {
  const mammoth = await import("mammoth");
  const buf = readFileSync(filePath);
  const result = await mammoth.extractRawText({ buffer: buf });
  return { text: result.value, warnings: result.messages };
}

/** @param {string} filePath */
async function parseSheet(filePath) {
  const XLSX = await import("xlsx");
  const buf = readFileSync(filePath);
  const wb = XLSX.read(buf, { type: "buffer" });
  const sheets = {};
  for (const [name, sheet] of Object.entries(wb.Sheets)) {
    const json = XLSX.utils.sheet_to_json(sheet, { header: 1 });
    const rows = json.filter((row) =>
      row.some((cell) => cell != null && cell !== "")
    );
    sheets[name] = rows;
  }
  return {
    sheetNames: wb.SheetNames,
    sheets,
    text: Object.entries(sheets)
      .map(([name, rows]) => {
        const header = `\n## Sheet: ${name}\n`;
        const body = rows.map((row) => row.join("\t")).join("\n");
        return header + body;
      })
      .join("\n"),
  };
}

/** @param {string} filePath */
function parseText(filePath) {
  return { text: readFileSync(filePath, "utf-8") };
}

/** @param {string} filePath */
function parseJson(filePath) {
  const raw = readFileSync(filePath, "utf-8");
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    const lines = raw.split("\n").filter((l) => l.trim());
    parsed = lines.map((l) => {
      try {
        return JSON.parse(l);
      } catch {
        return l;
      }
    });
  }
  return { parsed, text: JSON.stringify(parsed, null, 2) };
}

/** @param {string} filePath */
function parseHtml(filePath) {
  const raw = readFileSync(filePath, "utf-8");
  const text = raw
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return { text, rawLength: raw.length };
}

/** @param {string} filePath */
function parseImage(filePath) {
  const stat = statSync(filePath);
  let dimensions = null;
  try {
    const buf = readFileSync(filePath);
    if (buf[0] === 0x89 && buf[1] === 0x50) {
      dimensions = {
        width: buf.readUInt32BE(16),
        height: buf.readUInt32BE(20),
      };
    } else if (buf[0] === 0xff && buf[1] === 0xd8) {
      let i = 2;
      while (i < buf.length - 1) {
        if (buf[i] !== 0xff) break;
        const marker = buf[i + 1];
        if (marker === 0xc0 || marker === 0xc2) {
          dimensions = {
            width: buf.readUInt16BE(i + 7),
            height: buf.readUInt16BE(i + 5),
          };
          break;
        }
        i += 2 + buf.readUInt16BE(i + 2);
      }
    }
  } catch {
    // best-effort
  }
  return {
    filename: basename(filePath),
    size: stat.size,
    dimensions,
    note: "Image returned as metadata. For visual understanding, pass to a multimodal model.",
  };
}

// ---------------------------------------------------------------------------
// Orchestrator
// ---------------------------------------------------------------------------

/**
 * @param {string} filePath
 * @param {{ maxTextLength?: number }} [options]
 */
async function parseDocument(filePath, options = {}) {
  validateFilePath(filePath);

  const filename = basename(filePath);
  const format = detectFormat(filename);

  if (!format) {
    const ext = extname(filename);
    return {
      filename,
      format: "unknown (treated as text)",
      text: readFileSync(filePath, "utf-8"),
      warning: `Unrecognized extension "${ext}". Content returned as plain text.`,
    };
  }

  let result;
  switch (format.key) {
    case "pdf":
      result = await parsePdf(filePath);
      break;
    case "docx":
      result = await parseDocx(filePath);
      break;
    case "xlsx":
    case "csv":
      result = await parseSheet(filePath);
      break;
    case "txt":
    case "md":
      result = parseText(filePath);
      break;
    case "json":
      result = parseJson(filePath);
      break;
    case "html":
      result = parseHtml(filePath);
      break;
    case "image":
      result = parseImage(filePath);
      break;
    default:
      result = parseText(filePath);
  }

  const maxLen = options.maxTextLength || 100_000;
  if (result.text && result.text.length > maxLen) {
    result.text = result.text.slice(0, maxLen);
    result.truncated = true;
    result.truncatedLength = maxLen;
  }

  return {
    filename,
    format: format.info.label,
    parser: format.info.parser,
    ...result,
  };
}

// ---------------------------------------------------------------------------
// MCP Server
// ---------------------------------------------------------------------------

const server = new Server(
  {
    name: "qcc-document-mcp",
    version: "0.1.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// --- List tools ---

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "parse_document",
      description:
        "解析本地文件系统中的文档（PDF / DOCX / XLSX / CSV / TXT / MD / JSON / HTML / 图片）。" +
        "传入文件的绝对路径，返回结构化解析内容。" +
        "适用于：用户拖入文件、粘贴文件路径、或引用本地文档时。",
      inputSchema: {
        type: "object",
        properties: {
          filePath: {
            type: "string",
            description:
              "要解析的文件的绝对路径（例如 /Users/me/report.pdf）",
          },
          maxTextLength: {
            type: "number",
            description: "最大返回文本长度（字符数），默认 100000。超过则截断。",
          },
        },
        required: ["filePath"],
      },
    },
    {
      name: "parse_document_base64",
      description:
        "解析 base64 编码的文档内容。适用于文件通过拖拽/上传到对话框后的 base64 解码解析。" +
        "需要同时提供文件名（含扩展名，用于判断格式）。",
      inputSchema: {
        type: "object",
        properties: {
          base64Content: {
            type: "string",
            description:
              "文件的 Base64 编码内容（不含 data:xxx;base64, 前缀）",
          },
          filename: {
            type: "string",
            description:
              "原始文件名（含扩展名，如 report.pdf），用于判断文档类型",
          },
          maxTextLength: {
            type: "number",
            description: "最大返回文本长度，默认 100000",
          },
        },
        required: ["base64Content", "filename"],
      },
    },
    {
      name: "get_supported_formats",
      description:
        "列出 qcc-document-mcp 支持的所有文档格式、扩展名和 MIME 类型。",
      inputSchema: {
        type: "object",
        properties: {},
      },
    },
  ],
}));

// --- Call tool ---

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "get_supported_formats": {
      const formats = Object.entries(SUPPORTED_FORMATS).map(([key, info]) => ({
        key,
        label: info.label,
        extensions: info.extensions,
        mimeTypes: info.mimeTypes,
      }));
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              { supportedFormats: formats, total: formats.length },
              null,
              2
            ),
          },
        ],
      };
    }

    case "parse_document": {
      const { filePath, maxTextLength } = args;
      try {
        const data = await parseDocument(filePath, { maxTextLength });
        return {
          content: [
            { type: "text", text: JSON.stringify(data, null, 2) },
          ],
        };
      } catch (err) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                { error: true, message: err.message, filePath },
                null,
                2
              ),
            },
          ],
          isError: true,
        };
      }
    }

    case "parse_document_base64": {
      const { base64Content, filename, maxTextLength } = args;
      try {
        const buf = Buffer.from(base64Content, "base64");
        const tmpDir = mkdtempSync(join(tmpdir(), "qcc-doc-"));
        const tmpPath = join(tmpDir, filename);
        writeFileSync(tmpPath, buf);

        try {
          const data = await parseDocument(tmpPath, { maxTextLength });
          return {
            content: [
              { type: "text", text: JSON.stringify(data, null, 2) },
            ],
          };
        } finally {
          try {
            rmSync(tmpDir, { recursive: true, force: true });
          } catch {
            // best-effort cleanup
          }
        }
      } catch (err) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                { error: true, message: err.message, filename },
                null,
                2
              ),
            },
          ],
          isError: true,
        };
      }
    }

    default:
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              error: true,
              message: `Unknown tool: ${name}`,
            }),
          },
        ],
        isError: true,
      };
  }
});

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(
    "qcc-document-mcp running on stdio (Node.js " + process.version + ")"
  );
}

main().catch((err) => {
  console.error("qcc-document-mcp fatal:", err);
  process.exit(1);
});
