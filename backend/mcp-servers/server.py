#!/usr/bin/env python3
"""
Looma-Zervi MCP Sidecar — MVP Temporary Adapter Layer.

Product shape: **one Looma MCP (SSE :8999) + multiple tools**.
QCC's nine upstream MCP streams stay behind `qcc_client` — not 1:1 mirrored.

Tools:
  - rag_query         RAG knowledge-base query with AI answer
  - match_jobs        Resume-to-job-posting matching
  - parse_resume      Resume text → structured JSON
  - credit_check      Aggregated enterprise credit (QCC multi-source)
  - credit_company    Company profile only (light)
  - credit_risk       Risk readout only
  - credit_legal      Legal / case readout only

⚠  Temporary Python FastMCP adapter. Permanent path: Rust zervi.

Security: tools that touch user data require a valid looma JWT (+ consent where noted).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BACKEND_SRC = HERE.parent / "src"
sys.path.insert(0, str(BACKEND_SRC))

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse

from mcp_auth import MCPAuthError, verify_bearer_token_inline

logger = logging.getLogger("looma.mcp")
logging.basicConfig(level=logging.INFO)

_MCP_PORT = int(os.getenv("MCP_PORT", "8999"))
_MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")

TOOL_NAMES = [
    "rag_query",
    "match_jobs",
    "parse_resume",
    "credit_check",
    "credit_company",
    "credit_risk",
    "credit_legal",
]

mcp = FastMCP(
    "looma-zervi",
    instructions=(
        "Looma-Zervi MCP Sidecar: one SSE entry, multiple tools. "
        "Credit tools wrap QCC upstream via Looma qcc_client (not 1:1 QCC servers)."
    ),
    host=_MCP_HOST,
    port=_MCP_PORT,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_guard(token: str, user_id: str) -> dict:
    """Verify JWT and return decoded payload.  Raises MCPAuthError on failure."""
    if not token:
        raise MCPAuthError("Missing authentication token (param 'token')")
    return verify_bearer_token_inline(token, user_id=user_id or None)


def _error_dict(msg: str, kind: str = "auth_error") -> dict:
    return {"error": kind, "message": msg}


def _require_credit_consent(uid: str) -> dict | None:
    """Return error dict if credit_query consent missing; None if ok / skipped."""
    try:
        from src.compliance.consent import get_consent_manager
        cm = get_consent_manager()
        if not cm.check(uid, "credit_query"):
            return _error_dict(
                "Consent required: credit_query (请先授权企业风险查询)",
                "consent_required",
            )
    except Exception as e:
        logger.warning(f"Consent check skipped (DB unavailable): {e}")
    return None


def _company_dict(c: Any) -> dict:
    return {
        "name": c.company_name,
        "legal_person": c.legal_person,
        "registered_capital": c.registered_capital,
        "established_date": c.established_date,
        "credit_code": c.credit_code,
        "status": c.status,
        "industry": c.industry,
        "address": c.address,
        "business_scope": c.business_scope,
    }


def _run_credit(
    company_name: str,
    token: str,
    user_id: str,
    *,
    include_risk: bool = False,
    include_operation: bool = False,
    include_executives: bool = False,
    include_ipr: bool = False,
    include_history: bool = False,
    include_legal_cases: bool = False,
    include_documents: bool = False,
    mode: str = "custom",
) -> dict:
    """Shared credit path: auth → consent → qcc_client → shaped response."""
    try:
        payload = _auth_guard(token, user_id)
    except MCPAuthError as e:
        return _error_dict(str(e))

    denied = _require_credit_consent(payload["sub"])
    if denied:
        return denied

    name = (company_name or "").strip()
    if not name:
        return _error_dict("company_name required", "bad_request")

    try:
        from src.credit.qcc_client import (
            check_company_credit,
            format_credit_summary,
            QccMcpError,
        )

        report = check_company_credit(
            company_name=name,
            include_risk=include_risk,
            include_operation=include_operation,
            include_executives=include_executives,
            include_ipr=include_ipr,
            include_history=include_history,
            include_legal_cases=include_legal_cases,
            include_documents=include_documents,
        )

        if not report.company.company_name:
            return _error_dict(f"Company not found: {name}", "not_found")

        out: dict[str, Any] = {
            "source": "qcc",
            "mode": mode,
            "company": _company_dict(report.company),
        }

        if include_risk:
            out["risk"] = {
                "level": report.risk.risk_level,
                "summary": report.risk.summary,
                "count": len(report.risk.risk_items),
                "items": report.risk.risk_items[:20],
            }
        if include_operation:
            out["operation"] = {
                "summary": report.operation.summary,
                "key_financials": report.operation.key_financials,
                "annual_reports": report.operation.annual_reports[:5],
            }
        if include_executives:
            out["executives"] = report.executives[:15]
        if include_ipr:
            out["ipr"] = report.ipr[:15]
        if include_history:
            out["history"] = report.history[:15]
        if include_legal_cases:
            out["legal_cases"] = report.legal_cases[:15]
        if include_documents:
            out["documents"] = report.documents[:10]

        # Human summary when enough signals exist
        if include_risk or include_operation or include_executives:
            out["summary"] = format_credit_summary(report)

        return out

    except QccMcpError as e:
        return _error_dict(f"QCC service error: {e}", "qcc_unavailable")
    except ImportError as e:
        return _error_dict(f"Credit module unavailable: {e}", "module_error")


# ---------------------------------------------------------------------------
# Browser / ops surface (not MCP protocol — /sse remains SSE-only)
# ---------------------------------------------------------------------------

def _public_status() -> dict:
    return {
        "status": "ok",
        "service": "looma-mcp-sidecar",
        "shape": "one_mcp_many_tools",
        "sse_url": f"http://{_MCP_HOST}:{_MCP_PORT}/sse",
        "health_url": f"http://{_MCP_HOST}:{_MCP_PORT}/health",
        "tools": TOOL_NAMES,
        "credit_tools": ["credit_check", "credit_company", "credit_risk", "credit_legal"],
        "note": "/sse is an MCP protocol stream for clients (Cursor/scripts), not a web page.",
    }


def _landing_html() -> str:
    status = _public_status()
    tools_li = "\n".join(f"<li><code>{t}</code></li>" for t in TOOL_NAMES)
    cursor_snippet = json.dumps(
        {
            "mcpServers": {
                "looma-zervi": {
                    "url": status["sse_url"],
                }
            }
        },
        indent=2,
        ensure_ascii=False,
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Looma MCP Sidecar</title>
  <style>
    :root {{
      --bg: #f6f3ee;
      --ink: #1c1917;
      --muted: #57534e;
      --line: #e7e5e4;
      --card: #fffdf9;
      --accent: #0f766e;
      --code: #292524;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Source Han Sans SC", "Noto Sans SC", system-ui, sans-serif;
      background:
        radial-gradient(1200px 600px at 10% -10%, #d9f0ec 0%, transparent 55%),
        radial-gradient(900px 500px at 100% 0%, #f5e6d3 0%, transparent 50%),
        var(--bg);
      color: var(--ink);
      line-height: 1.55;
    }}
    main {{
      max-width: 720px;
      margin: 0 auto;
      padding: 48px 20px 64px;
    }}
    h1 {{
      font-family: "IBM Plex Serif", "Source Han Serif SC", Georgia, serif;
      font-size: clamp(1.8rem, 4vw, 2.4rem);
      margin: 0 0 8px;
      letter-spacing: -0.02em;
    }}
    .sub {{ color: var(--muted); margin-bottom: 28px; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 18px 20px;
      margin-bottom: 16px;
    }}
    .card h2 {{
      font-size: 0.95rem;
      margin: 0 0 10px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--accent);
    }}
    code, pre {{
      font-family: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.85rem;
    }}
    pre {{
      background: var(--code);
      color: #fafaf9;
      padding: 14px 16px;
      border-radius: 8px;
      overflow-x: auto;
      margin: 0;
    }}
    ul {{ margin: 0; padding-left: 1.2rem; }}
    li {{ margin: 4px 0; }}
    a {{ color: var(--accent); }}
    .pill {{
      display: inline-block;
      padding: 2px 10px;
      border-radius: 999px;
      background: #ccfbf1;
      color: #115e59;
      font-size: 0.8rem;
      font-weight: 600;
    }}
    .warn {{
      border-left: 3px solid #d97706;
      padding-left: 12px;
      color: var(--muted);
      font-size: 0.92rem;
    }}
  </style>
</head>
<body>
  <main>
    <p class="pill">one MCP · many tools</p>
    <h1>Looma MCP Sidecar</h1>
    <p class="sub">浏览器适配层 / 运维入口。协议连接请用 MCP 客户端，不要把 <code>/sse</code> 当网页。</p>

    <section class="card">
      <h2>状态</h2>
      <p>服务：<strong>{status["service"]}</strong> · <span class="pill">ok</span></p>
      <p>SSE：<a href="{status["sse_url"]}"><code>{status["sse_url"]}</code></a>（EventStream，浏览器会空白/挂起）</p>
      <p>JSON：<a href="/health"><code>/health</code></a></p>
    </section>

    <section class="card">
      <h2>已注册工具</h2>
      <ul>
        {tools_li}
      </ul>
      <p class="warn" style="margin-top:12px">征信为聚合 <code>credit_check</code> + 少量细分（company/risk/legal），不 1:1 镜像企查查九服。</p>
    </section>

    <section class="card">
      <h2>Cursor / MCP 客户端配置示例</h2>
      <pre>{cursor_snippet}</pre>
      <p class="sub" style="margin:10px 0 0">工具调用需传 Looma JWT（参数 <code>token</code>）；征信类另需 <code>credit_query</code> 授权。</p>
    </section>

    <section class="card">
      <h2>说明</h2>
      <p class="warn">本页是 HTTP 适配层，方便人眼查看与联调；真正的 Agent 通道是 SSE 协议流。</p>
    </section>
  </main>
</body>
</html>
"""


@mcp.custom_route("/", methods=["GET"])
async def browser_landing(_request: Request) -> HTMLResponse:
    """Human-readable entry so opening :8999 is not a blank page."""
    return HTMLResponse(_landing_html())


@mcp.custom_route("/health", methods=["GET"])
async def http_health(_request: Request) -> JSONResponse:
    """HTTP health for ops / verify scripts (complements health://status)."""
    return JSONResponse(_public_status())


@mcp.custom_route("/sse-info", methods=["GET"])
async def sse_info(_request: Request) -> PlainTextResponse:
    """Plain tip if someone expects HTML on the protocol path."""
    return PlainTextResponse(
        "Looma MCP SSE endpoint is at /sse (text/event-stream).\n"
        "Open http://127.0.0.1:8999/ in a browser for the landing page.\n"
        "Health JSON: /health\n",
        media_type="text/plain; charset=utf-8",
    )


# ---------------------------------------------------------------------------
# MCP resource
# ---------------------------------------------------------------------------

@mcp.resource("health://status")
def health_status() -> dict:
    """Health check resource for MCP clients / CI."""
    return _public_status()


# ---------------------------------------------------------------------------
# Core tools
# ---------------------------------------------------------------------------

@mcp.tool(
    name="rag_query",
    description="RAG knowledge base query with AI answer (requires JWT token)",
)
def rag_query(question: str, token: str = "", user_id: str = "", n_results: int = 3) -> dict:
    """Query the RAG knowledge base and return an AI-generated answer."""
    try:
        _auth_guard(token, user_id)
    except MCPAuthError as e:
        return _error_dict(str(e))

    try:
        from src.rag.chroma_client import search_chroma
        from src.agents.central_brain import _call_llm

        results = search_chroma(question, n_results=n_results)
        ctx = "\n\n".join(r.get("content", "") for r in results) if results else ""
        prompt = f"Answer based on context:\n{ctx}\n\nQuestion: {question}\nAnswer:"
        answer = _call_llm(prompt) or "RAG query failed"
        sources = [
            {"chunk": r.get("content", "")[:200], "score": r.get("score")}
            for r in results
        ]
        return {"answer": answer, "sources": sources, "n_results": len(results)}
    except ImportError as e:
        return {"answer": f"RAG unavailable: {e}", "sources": [], "n_results": 0}


@mcp.tool(
    name="match_jobs",
    description="Match resume text against job postings (requires JWT token)",
)
def match_jobs(resume_text: str, token: str = "", user_id: str = "", top_k: int = 10) -> dict:
    """Match a resume against available job postings."""
    try:
        _auth_guard(token, user_id)
    except MCPAuthError as e:
        return _error_dict(str(e))

    try:
        from src.pipeline.job_match_pipeline import run_job_match_pipeline

        results_list, total = run_job_match_pipeline(resume_text=resume_text)
        return {"matches": results_list[:top_k], "total_evaluated": total}
    except ImportError as e:
        return {"matches": [], "total_evaluated": 0, "error": str(e)}


@mcp.tool(
    name="parse_resume",
    description="Parse resume text into structured JSON (requires JWT token + consent)",
)
def parse_resume(resume_text: str, token: str = "", user_id: str = "") -> dict:
    """Parse unstructured resume text into structured JSON fields."""
    try:
        payload = _auth_guard(token, user_id)
    except MCPAuthError as e:
        return _error_dict(str(e))

    uid = payload["sub"]
    try:
        from src.compliance.consent import get_consent_manager
        cm = get_consent_manager()
        if not cm.check(uid, "resume_upload") and not cm.check(uid, "jobseeker_core"):
            return _error_dict(
                "Consent required: jobseeker_core / resume_upload",
                "consent_required",
            )
    except Exception as e:
        logger.warning(f"Consent check skipped (DB unavailable): {e}")

    try:
        from src.agents.document_agents import DocumentAnalysisError, run_document_analysis

        extracted = run_document_analysis("resume", resume_text)
        return {"extracted": extracted}
    except DocumentAnalysisError as e:
        return {"extracted": {}, "error": e.message, "hint": e.code}
    except ImportError as e:
        return {"extracted": {}, "error": str(e)}
    except Exception as e:
        return {"extracted": {}, "error": str(e)}


# ---------------------------------------------------------------------------
# Credit tools — one aggregate + a few focused (not 1:1 QCC MCP mirror)
# ---------------------------------------------------------------------------

@mcp.tool(
    name="credit_check",
    description=(
        "Aggregated enterprise credit via Looma→QCC: company + risk + operation + executives; "
        "set detail=true for IPR/history/legal/documents (JWT + credit_query consent)"
    ),
)
def credit_check(company_name: str, token: str = "", user_id: str = "", detail: bool = False) -> dict:
    """Aggregated credit report. Prefer this for HR screening; use focused tools for light reads."""
    return _run_credit(
        company_name,
        token,
        user_id,
        include_risk=True,
        include_operation=True,
        include_executives=True,
        include_ipr=detail,
        include_history=detail,
        include_legal_cases=detail,
        include_documents=detail,
        mode="full" if detail else "basic",
    )


@mcp.tool(
    name="credit_company",
    description="Company profile only (工商基本信息) via Looma→QCC (JWT + credit_query consent)",
)
def credit_company(company_name: str, token: str = "", user_id: str = "") -> dict:
    """Light lookup: company registration profile without risk/legal pulls."""
    return _run_credit(
        company_name,
        token,
        user_id,
        mode="company",
    )


@mcp.tool(
    name="credit_risk",
    description="Enterprise risk readout only via Looma→QCC (JWT + credit_query consent)",
)
def credit_risk(company_name: str, token: str = "", user_id: str = "") -> dict:
    """Focused risk check — cheaper/faster than full credit_check when only risk is needed."""
    return _run_credit(
        company_name,
        token,
        user_id,
        include_risk=True,
        mode="risk",
    )


@mcp.tool(
    name="credit_legal",
    description="Enterprise legal/case readout only via Looma→QCC (JWT + credit_query consent)",
)
def credit_legal(company_name: str, token: str = "", user_id: str = "") -> dict:
    """Focused legal/case check for diligence without pulling full credit bundle."""
    return _run_credit(
        company_name,
        token,
        user_id,
        include_legal_cases=True,
        mode="legal",
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    env_file = BACKEND_SRC.parent / ".env"
    if env_file.exists():
        from dotenv import load_dotenv

        load_dotenv(env_file)
    logger.info(
        "Looma MCP Sidecar on %s:%s (SSE /sse) tools=%s",
        _MCP_HOST,
        _MCP_PORT,
        ",".join(TOOL_NAMES),
    )
    mcp.run(transport="sse")
