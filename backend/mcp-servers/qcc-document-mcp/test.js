#!/usr/bin/env node

/**
 * Smoke test for qcc-document-mcp server.
 *
 * Starts the server as a child process, sends MCP JSON-RPC messages over
 * stdio, and validates responses.
 *
 * Usage: node test.js
 */

import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { writeFileSync, unlinkSync, mkdtempSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

let passed = 0;
let failed = 0;

function assert(condition, msg) {
  if (condition) {
    passed++;
    console.log(`  ✅ ${msg}`);
  } else {
    failed++;
    console.error(`  ❌ ${msg}`);
  }
}

function assertEqual(actual, expected, msg) {
  if (actual === expected) {
    passed++;
    console.log(`  ✅ ${msg}`);
  } else {
    failed++;
    console.error(`  ❌ ${msg} (expected: ${JSON.stringify(expected)}, got: ${JSON.stringify(actual)})`);
  }
}

// Start the server
const proc = spawn("node", [join(__dirname, "server.js")], {
  stdio: ["pipe", "pipe", "pipe"],
  env: { ...process.env, NODE_ENV: "test" },
});

const rl = createInterface({ input: proc.stdout });
let responseBuffer = "";
let responseResolve = null;

rl.on("line", (line) => {
  if (responseResolve) {
    responseResolve(line);
    responseResolve = null;
  }
});

proc.stderr.on("data", (d) => {
  // Server logs to stderr, we don't care for test
});

proc.on("error", (err) => {
  console.error("Server failed to start:", err.message);
  process.exit(1);
});

function sendRequest(request) {
  return new Promise((resolve) => {
    responseResolve = resolve;
    proc.stdin.write(JSON.stringify(request) + "\n");
  });
}

// Wait a bit for server to boot
await new Promise((r) => setTimeout(r, 500));

console.log("\n🔍 qcc-document-mcp Smoke Test\n");

// --- Test 1: List tools ---
console.log("Test 1: list_tools");
const listResp = JSON.parse(
  await sendRequest({
    jsonrpc: "2.0",
    id: 1,
    method: "tools/list",
    params: {},
  })
);
assert(Array.isArray(listResp.result?.tools), "tools/list returns tools array");
assert(listResp.result.tools.length >= 3, "at least 3 tools registered");

// --- Test 2: get_supported_formats ---
console.log("\nTest 2: get_supported_formats");
const fmtResp = JSON.parse(
  await sendRequest({
    jsonrpc: "2.0",
    id: 2,
    method: "tools/call",
    params: { name: "get_supported_formats", arguments: {} },
  })
);
const fmtData = JSON.parse(fmtResp.result.content[0].text);
assert(fmtData.total >= 8, "at least 8 format categories");
assert(fmtData.supportedFormats.some((f) => f.key === "pdf"), "PDF format listed");

// --- Test 3: parse_document (TXT) ---
console.log("\nTest 3: parse_document (TXT)");
const tmpDir = mkdtempSync(join(tmpdir(), "qcc-test-"));
const txtPath = join(tmpDir, "hello.txt");
writeFileSync(txtPath, "Hello, qcc-document-mcp!\nThis is a test.\n");
const txtResp = JSON.parse(
  await sendRequest({
    jsonrpc: "2.0",
    id: 3,
    method: "tools/call",
    params: {
      name: "parse_document",
      arguments: { filePath: txtPath },
    },
  })
);
const txtData = JSON.parse(txtResp.result.content[0].text);
assertEqual(txtData.filename, "hello.txt", "filename is hello.txt");
assert(txtData.text.includes("Hello, qcc-document-mcp!"), "text content matches");
assert(txtData.format.includes("Plain Text"), "format detected as text");

// --- Test 4: parse_document (JSON) ---
console.log("\nTest 4: parse_document (JSON)");
const jsonPath = join(tmpDir, "test.json");
writeFileSync(jsonPath, JSON.stringify({ name: "qcc", version: 1 }));
const jsonResp = JSON.parse(
  await sendRequest({
    jsonrpc: "2.0",
    id: 4,
    method: "tools/call",
    params: {
      name: "parse_document",
      arguments: { filePath: jsonPath },
    },
  })
);
const jsonData = JSON.parse(jsonResp.result.content[0].text);
assertEqual(jsonData.filename, "test.json", "filename is test.json");
assert(jsonData.text.includes('"name": "qcc"'), "JSON content parsed");

// --- Test 5: parse_document_base64 ---
console.log("\nTest 5: parse_document_base64");
const b64 = Buffer.from("# QCC Doc Parser\n\nBase64 test doc.").toString("base64");
const b64Resp = JSON.parse(
  await sendRequest({
    jsonrpc: "2.0",
    id: 5,
    method: "tools/call",
    params: {
      name: "parse_document_base64",
      arguments: { base64Content: b64, filename: "readme.md" },
    },
  })
);
const b64Data = JSON.parse(b64Resp.result.content[0].text);
assertEqual(b64Data.filename, "readme.md", "filename from base64");
assert(b64Data.text.includes("QCC Doc Parser"), "base64 content parsed");

// --- Test 6: file not found error ---
console.log("\nTest 6: file not found error");
const errResp = JSON.parse(
  await sendRequest({
    jsonrpc: "2.0",
    id: 6,
    method: "tools/call",
    params: {
      name: "parse_document",
      arguments: { filePath: "/nonexistent/file.pdf" },
    },
  })
);
assert(errResp.result.isError, "returns isError for missing file");
const errData = JSON.parse(errResp.result.content[0].text);
assert(errData.error, "error flag is true");
assert(errData.message.includes("File not found"), "error message mentions file not found");

// --- Cleanup ---
try {
  rmSync(tmpDir, { recursive: true, force: true });
} catch {}

// --- Results ---
console.log(`\n${"─".repeat(40)}`);
console.log(`Results: ${passed} passed, ${failed} failed`);
console.log(`${"─".repeat(40)}\n`);

proc.kill();

if (failed > 0) {
  process.exit(1);
}
