"""
QCC (企查查) MCP Client — Official enterprise credit data source.

Integrates 9 QCC MCP services via SSE-based JSON-RPC 2.0:
  - qcc-company      : 企业工商信息
  - qcc-risk         : 企业风险信息
  - qcc-ipr          : 知识产权
  - qcc-operation    : 经营状况
  - qcc-executive    : 高管/法人信息
  - qcc-history      : 历史变更
  - qcc-legal-regulation : 法律法规
  - qcc-legal-case   : 司法案件
  - qcc-document     : 企业文书

Protocol: MCP Streamable HTTP — POST JSON-RPC to each service ``/stream`` URL.
Responses are SSE ``event: message`` or application/json. Optional ``Mcp-Session-Id``.
Overseas SG should set ``QCC_MCP_BASE_URL`` to a China reverse proxy that can
reach ``agent.qcc.com`` (see ``deploy/nginx/qcc-gateway.conf``).
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

logger = logging.getLogger("looma.qcc_client")

# ── Configuration ──────────────────────────────────────────────────────────

# Official QCC MCP root. Overseas SG may set QCC_MCP_BASE_URL to a China
# reverse-proxy (e.g. http://1.14.202.161:8998/mcp) that can reach agent.qcc.com.
_DEFAULT_QCC_MCP_BASE = "https://agent.qcc.com/mcp"

_QCC_SERVICE_PATHS: dict[str, str] = {
    "company": "company/stream",
    "risk": "risk/stream",
    "ipr": "ipr/stream",
    "operation": "operation/stream",
    "executive": "executive/stream",
    "history": "history/stream",
    "legal_regulation": "regulation/stream",
    "legal_case": "case/stream",
    "document": "document/stream",
}


def _mcp_base_url() -> str:
    return (os.getenv("QCC_MCP_BASE_URL") or _DEFAULT_QCC_MCP_BASE).strip().rstrip("/")


def get_qcc_base_urls() -> dict[str, str]:
    """Resolve per-service SSE stream URLs (honours QCC_MCP_BASE_URL)."""
    base = _mcp_base_url()
    return {name: f"{base}/{path}" for name, path in _QCC_SERVICE_PATHS.items()}


# Back-compat: default official URLs (import-time). Prefer get_qcc_base_urls().
QCC_BASE_URLS: dict[str, str] = get_qcc_base_urls()

QCC_TIMEOUT = 30.0  # seconds per call
QCC_MAX_RETRIES = 2


def _resolve_auth_token() -> str:
    """Read QCC token at call time (not import time) and normalize Bearer prefix.

    Docker injects env_file only on container create/recreate; import-time
    os.getenv() would freeze an empty token across workers.
    """
    raw = (os.getenv("QCC_AUTH_TOKEN") or "").strip().strip('"').strip("'")
    if not raw:
        try:
            from src.config import Config
            raw = (getattr(Config, "QCC_AUTH_TOKEN", "") or "").strip()
        except Exception:
            raw = ""
    if not raw:
        return ""
    if raw.lower().startswith("bearer "):
        return raw
    return f"Bearer {raw}"


# Back-compat alias (may be empty at import; prefer _resolve_auth_token())
QCC_AUTH_TOKEN = os.getenv("QCC_AUTH_TOKEN", "")

# ── Data types ─────────────────────────────────────────────────────────────

@dataclass
class QccCompanyInfo:
    """Parsed company basic info from QCC company service."""
    company_name: str = ""
    legal_person: str = ""
    registered_capital: str = ""
    established_date: str = ""
    credit_code: str = ""
    status: str = ""
    industry: str = ""
    address: str = ""
    business_scope: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class QccRiskInfo:
    """Parsed risk info from QCC risk service."""
    risk_level: str = ""          # e.g. "低风险" / "中风险" / "高风险"
    risk_items: list[dict[str, str]] = field(default_factory=list)
    summary: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class QccOperationInfo:
    """Parsed operation / business data from QCC operation service."""
    annual_reports: list[dict[str, str]] = field(default_factory=list)
    key_financials: dict[str, str] = field(default_factory=dict)
    summary: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class QccCreditReport:
    """Aggregated enterprise credit report."""
    company: QccCompanyInfo = field(default_factory=QccCompanyInfo)
    risk: QccRiskInfo = field(default_factory=QccRiskInfo)
    operation: QccOperationInfo = field(default_factory=QccOperationInfo)
    executives: list[dict[str, str]] = field(default_factory=list)
    ipr: list[dict[str, str]] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)
    legal_cases: list[dict[str, str]] = field(default_factory=list)
    documents: list[dict[str, str]] = field(default_factory=list)
    source: str = "qcc"  # official data source marker


# ── MCP SSE Client ─────────────────────────────────────────────────────────

class QccMcpError(Exception):
    """QCC MCP service error."""
    pass


def _extract_session_id_from_endpoint(endpoint_url: str) -> str | None:
    """Parse session id from MCP SSE endpoint event data (URL or path)."""
    from urllib.parse import parse_qs, urlparse

    query = parse_qs(urlparse(endpoint_url).query)
    for key in ("session_id", "sessionId"):
        vals = query.get(key)
        if vals and vals[0]:
            return vals[0]
    return None


def _parse_sse_event_block(block: str) -> tuple[str | None, str | None]:
    """Return (event_name, data) from one SSE event block."""
    event_name: str | None = None
    data_lines: list[str] = []
    for line in block.split("\n"):
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if not data_lines:
        return event_name, None
    return event_name, "\n".join(data_lines)


class QccMcpSession:
    """MCP Streamable HTTP client for one QCC service endpoint.

    Current agent.qcc.com transport:
      POST /mcp/<svc>/stream  with JSON-RPC (initialize / tools/list / tools/call)
      Response is SSE ``event: message`` or plain JSON; optional ``Mcp-Session-Id``.

    Legacy GET SSE handshake (event: endpoint → /messages/) returns HTTP 405
    「请求方式异常」and is no longer used.
    """

    def __init__(self, service_name: str, url: str, auth_token: str, timeout: float = QCC_TIMEOUT):
        self.service_name = service_name
        self.url = url
        self.auth_token = auth_token
        self.timeout = timeout
        self._session_id: Optional[str] = None
        self._tools: list[dict] = []
        self._initialized = False
        self._lock = threading.Lock()
        self._rpc_id = 0

    def connect(self) -> str:
        """Back-compat alias: ensure streamable-HTTP session is initialized."""
        self.ensure_ready()
        return self._session_id or "streamable-http"

    def ensure_ready(self) -> None:
        """Initialize MCP session once (thread-safe)."""
        with self._lock:
            if self._initialized:
                return
            self._post_rpc(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "looma-zervi", "version": "1.0.0"},
                },
                is_notification=False,
            )
            try:
                self._post_rpc("notifications/initialized", {}, is_notification=True)
            except QccMcpError as e:
                logger.debug("[%s] notifications/initialized ignored: %s", self.service_name, e)
            self._initialized = True
            logger.info(
                "[%s] MCP streamable-HTTP ready session=%s",
                self.service_name,
                (self._session_id or "-")[:16],
            )

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    def _parse_rpc_response(self, resp: requests.Response) -> dict:
        """Parse JSON or SSE JSON-RPC body into the result object."""
        sid = (
            resp.headers.get("Mcp-Session-Id")
            or resp.headers.get("mcp-session-id")
            or resp.headers.get("X-Session-Id")
        )
        if sid:
            self._session_id = sid

        content_type = (resp.headers.get("Content-Type") or "").lower()
        text = resp.text or ""

        def _from_obj(data: dict) -> dict:
            if "error" in data:
                err = data["error"]
                msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                raise QccMcpError(f"[{self.service_name}] RPC error: {msg}")
            if "result" in data:
                result = data["result"]
                return result if isinstance(result, dict) else {"value": result}
            return data

        if "application/json" in content_type and not text.lstrip().startswith(("event:", "data:")):
            return _from_obj(resp.json())

        if "text/event-stream" in content_type or text.lstrip().startswith(("event:", "data:")):
            for block in re.split(r"\n\n+", text):
                _event_name, data_str = _parse_sse_event_block(block)
                if not data_str:
                    continue
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict) and ("result" in data or "error" in data or "jsonrpc" in data):
                    return _from_obj(data)

        try:
            return _from_obj(resp.json())
        except (json.JSONDecodeError, ValueError, QccMcpError):
            if text.strip():
                return {"_raw": text}
            raise QccMcpError(f"[{self.service_name}] Empty RPC response")

    def _post_rpc(
        self,
        method: str,
        params: dict | None = None,
        *,
        is_notification: bool = False,
    ) -> dict:
        """POST JSON-RPC to the stream URL (streamable HTTP)."""
        if is_notification:
            payload: dict[str, Any] = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
            }
        else:
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": method,
                "params": params or {},
            }

        headers = {
            "Authorization": self.auth_token,
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        last_err: Exception | None = None
        for attempt in range(QCC_MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    self.url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                # Capture session id even on some error responses
                sid = (
                    resp.headers.get("Mcp-Session-Id")
                    or resp.headers.get("mcp-session-id")
                )
                if sid:
                    self._session_id = sid
                    headers["Mcp-Session-Id"] = sid

                if is_notification:
                    if resp.status_code in (200, 202, 204):
                        return {}
                    # Some servers ack notifications with empty body / 200 SSE
                    if resp.status_code < 400:
                        return {}
                    resp.raise_for_status()
                    return {}

                resp.raise_for_status()
                return self._parse_rpc_response(resp)

            except QccMcpError:
                raise
            except requests.RequestException as e:
                last_err = e
                if attempt < QCC_MAX_RETRIES:
                    logger.warning(
                        "[%s] RPC retry %s/%s %s: %s",
                        self.service_name,
                        attempt + 1,
                        QCC_MAX_RETRIES,
                        method,
                        e,
                    )
                    time.sleep(1)
                    # Soft reset session on transport failure
                    self._initialized = False
                    self._session_id = None
                    headers.pop("Mcp-Session-Id", None)
                    continue
                raise QccMcpError(
                    f"[{self.service_name}] RPC call '{method}' failed: {e}"
                ) from e

        raise QccMcpError(
            f"[{self.service_name}] RPC call '{method}' failed: {last_err}"
        )

    def _rpc_call(self, method: str, params: dict | None = None) -> dict:
        """Public RPC helper used by initialize / list_tools / call_tool."""
        if method != "initialize":
            self.ensure_ready()
        return self._post_rpc(method, params, is_notification=False)

    def initialize(self) -> dict:
        """Send MCP initialize request."""
        self.ensure_ready()
        return {"protocolVersion": "2024-11-05", "sessionId": self._session_id}

    def list_tools(self) -> list[dict]:
        """List available tools on this service."""
        if self._tools:
            return self._tools
        result = self._rpc_call("tools/list")
        tools = result.get("tools", []) if isinstance(result, dict) else []
        self._tools = tools
        logger.info(f"[{self.service_name}] Available tools: {[t.get('name') for t in tools]}")
        return tools

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict:
        """Call a specific tool with arguments."""
        return self._rpc_call("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })


# ── Session Manager ────────────────────────────────────────────────────────

class QccSessionManager:
    """Manages lazy-initialized MCP sessions for all QCC services."""

    def __init__(self, auth_token: str | None = None):
        self.auth_token = (auth_token if auth_token is not None else _resolve_auth_token()).strip()
        if not self.auth_token:
            raise QccMcpError(
                "QCC_AUTH_TOKEN 未配置或为空。请写入 backend/.env 后 "
                "docker compose up -d --force-recreate backend"
            )
        self._sessions: dict[str, QccMcpSession] = {}
        self._lock = threading.Lock()

    def _get_session(self, service: str) -> QccMcpSession:
        urls = get_qcc_base_urls()
        if service not in urls:
            raise QccMcpError(f"Unknown QCC service: {service}")
        with self._lock:
            if service not in self._sessions:
                self._sessions[service] = QccMcpSession(
                    service_name=service,
                    url=urls[service],
                    auth_token=self.auth_token,
                )
            return self._sessions[service]

    def call_tool(self, service: str, tool_name: str, arguments: dict[str, Any]) -> dict:
        """Convenience: call a tool on a named service."""
        session = self._get_session(service)
        return session.call_tool(tool_name, arguments)

    def get_tools(self, service: str) -> list[dict]:
        """Get available tools for a service."""
        session = self._get_session(service)
        return session.list_tools()

    def close_all(self):
        """Release all sessions."""
        with self._lock:
            self._sessions.clear()


# ── High-level API ─────────────────────────────────────────────────────────

# Global session manager (lazy init)
_session_manager: Optional[QccSessionManager] = None


def _get_manager() -> QccSessionManager:
    global _session_manager
    token = _resolve_auth_token()
    if _session_manager is None or _session_manager.auth_token != token:
        _session_manager = QccSessionManager(auth_token=token)
    return _session_manager


def _find_search_tool(session: QccMcpSession) -> dict | None:
    """Find the best search/query tool from a service's tool list."""
    tools = session.list_tools()
    if not tools:
        return None

    preferred = (
        "get_company_by_query",
        "get_company_profile",
        "get_company_registration_info",
        "company_search",
        "search_company",
    )
    by_name = {t.get("name", ""): t for t in tools}
    for name in preferred:
        if name in by_name:
            return by_name[name]

    company_keys = ("searchKey", "keyword", "query", "companyName", "company_name", "name")

    def _score(tool: dict) -> int:
        name = (tool.get("name") or "").lower()
        props = ((tool.get("inputSchema") or {}).get("properties") or {})
        score = 0
        if any(k in props for k in company_keys):
            score += 10
        if "personName" in props and not any(k in props for k in company_keys):
            score -= 20  # person-only tools break company credit lookup
        if "search" in name or "query" in name or "company" in name:
            score += 5
        return score

    ranked = sorted(tools, key=_score, reverse=True)
    if _score(ranked[0]) > 0:
        return ranked[0]
    return None


def _fix_mojibake(text: str) -> str:
    """Repair UTF-8 text that was wrongly decoded as latin-1 (QCC SSE quirk)."""
    if not isinstance(text, str) or not text:
        return text
    if any("\u4e00" <= c <= "\u9fff" for c in text):
        return text
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    if any("\u4e00" <= c <= "\u9fff" for c in repaired):
        return repaired
    return text


def _search_company_by_name(company_name: str) -> dict:
    """Search company basic info via qcc-company service.

    Prefer registration info (richer fields); fall back to by_query / profile.
    """
    mgr = _get_manager()
    session = mgr._get_session("company")
    tools = {t.get("name", ""): t for t in session.list_tools()}

    preferred = (
        "get_company_registration_info",
        "get_company_profile",
        "get_company_by_query",
    )
    last_err: Exception | None = None
    for name in preferred:
        tool = tools.get(name)
        if not tool:
            continue
        try:
            return session.call_tool(name, _build_search_args(tool, company_name))
        except Exception as e:
            last_err = e
            logger.warning("[company] tool %s failed: %s", name, e)

    tool = _find_search_tool(session)
    if not tool:
        raise QccMcpError("[company] No search tool available") from last_err
    return session.call_tool(tool["name"], _build_search_args(tool, company_name))


def _parse_company_result(result: dict) -> QccCompanyInfo:
    """Parse raw QCC company result into structured QccCompanyInfo."""
    content = result
    if isinstance(result, dict):
        if "content" in result:
            items = result["content"]
            if isinstance(items, list) and items:
                for item in items:
                    if isinstance(item, dict) and item.get("type") == "text":
                        raw_text = _fix_mojibake(item.get("text", "") or "")
                        try:
                            content = json.loads(raw_text)
                        except json.JSONDecodeError:
                            content = {"raw_text": raw_text}
                        break
                    elif isinstance(item, dict):
                        content = item
                        break

    if not isinstance(content, dict):
        content = {}

    # get_company_by_query nests fields under 企业信息
    nested = content.get("企业信息")
    if isinstance(nested, dict):
        merged = {**content, **nested}
    else:
        merged = content

    def pick(*keys: str) -> str:
        for k in keys:
            v = merged.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
        return ""

    return QccCompanyInfo(
        company_name=pick(
            "companyName", "company_name", "name", "企业名称", "企业名"
        ),
        legal_person=pick(
            "legalPerson", "legal_person", "legalPersonName", "法定代表人", "法人"
        ),
        registered_capital=pick(
            "registeredCapital", "registered_capital", "regCapital", "注册资本"
        ),
        established_date=pick(
            "establishedDate", "established_date", "estiblishTime", "成立日期"
        ),
        credit_code=pick(
            "creditCode",
            "credit_code",
            "unifiedSocialCreditCode",
            "统一社会信用代码",
        ),
        status=pick("status", "companyStatus", "regStatus", "登记状态", "经营状态"),
        industry=pick("industry", "industryName", "企查查行业", "行业"),
        address=pick("address", "regLocation", "注册地址", "企业地址"),
        business_scope=pick("businessScope", "scope", "经营范围", "简介"),
        raw=merged if isinstance(merged, dict) else content,
    )


def _search_risk(company_name: str) -> QccRiskInfo:
    """Search company risk info via qcc-risk service."""
    mgr = _get_manager()
    session = mgr._get_session("risk")
    tool = _find_search_tool(session)
    if not tool:
        raise QccMcpError("[risk] No search tool available")

    tool_name = tool["name"]
    result = session.call_tool(tool_name, _build_search_args(tool, company_name))

    # Parse content
    items = _extract_content(result)
    return QccRiskInfo(
        risk_level=_extract_risk_level(items),
        risk_items=items if isinstance(items, list) else [],
        summary=_generate_risk_summary(items),
        raw=result,
    )


def _search_operation(company_name: str) -> QccOperationInfo:
    """Search company operation/business data via qcc-operation service."""
    mgr = _get_manager()
    session = mgr._get_session("operation")
    tool = _find_search_tool(session)
    if not tool:
        raise QccMcpError("[operation] No search tool available")

    tool_name = tool["name"]
    result = session.call_tool(tool_name, _build_search_args(tool, company_name))

    items = _extract_content(result)
    return QccOperationInfo(
        summary=_generate_operation_summary(items),
        raw=result,
    )


def _search_service(
    service_name: str,
    company_name: str,
    *,
    person_name: str | None = None,
) -> list[dict]:
    """Generic search on any QCC service, returns list of result dicts."""
    mgr = _get_manager()
    session = mgr._get_session(service_name)
    tool = _find_search_tool(session)
    if not tool:
        logger.warning(f"[{service_name}] No suitable search tool available")
        return []

    required = ((tool.get("inputSchema") or {}).get("required") or [])
    if "personName" in required and not (person_name or "").strip():
        logger.info("[%s] skip: tool requires personName", service_name)
        return []

    tool_name = tool["name"]
    result = session.call_tool(
        tool_name,
        _build_search_args(tool, company_name, person_name=person_name),
    )
    items = _extract_content(result)
    return items if isinstance(items, list) else [items] if items else []


# ── Helpers ────────────────────────────────────────────────────────────────

def _build_search_args(
    tool: dict,
    company_name: str,
    *,
    person_name: str | None = None,
) -> dict[str, Any]:
    """Build search arguments matching the tool's inputSchema."""
    input_schema = tool.get("inputSchema", {}) or {}
    props = input_schema.get("properties", {}) or {}
    args: dict[str, Any] = {}

    for key in (
        "searchKey",
        "keyword",
        "query",
        "companyName",
        "company_name",
        "name",
        "enterpriseName",
        "keyWord",
        "search_key",
    ):
        if key in props:
            args[key] = company_name
            break

    if "personName" in props and (person_name or "").strip():
        args["personName"] = person_name.strip()

    if not args:
        required = input_schema.get("required") or []
        if required and isinstance(required[0], str):
            args[required[0]] = company_name
        else:
            args["searchKey"] = company_name
    return args


def _extract_content(result: dict) -> Any:
    """Extract structured content from MCP tool/call result."""
    if not isinstance(result, dict):
        return result

    if "content" in result:
        items = result["content"]
        if isinstance(items, list):
            parsed = []
            for item in items:
                if isinstance(item, dict) and item.get("type") == "text":
                    raw_text = _fix_mojibake(item.get("text", "") or "")
                    try:
                        parsed.append(json.loads(raw_text))
                    except json.JSONDecodeError:
                        parsed.append({"text": raw_text})
                elif isinstance(item, dict):
                    parsed.append(item)
            return parsed if parsed else items
        return items

    return result


def _extract_risk_level(items: Any) -> str:
    """Heuristic to determine risk level from QCC data."""
    if not isinstance(items, list):
        return "暂无风险评级"

    total = len(items)
    if total == 0:
        return "暂无风险信息"

    # Count risk severity indicators
    high_keywords = ["破产", "失信", "被执行", "吊销", "严重违法", "清算"]
    medium_keywords = ["行政处罚", "经营异常", "欠税", "股权冻结", "限制高消费"]
    high_count = 0
    medium_count = 0

    text = json.dumps(items, ensure_ascii=False).lower()
    for kw in high_keywords:
        if kw in text:
            high_count += 1
    for kw in medium_keywords:
        if kw in text:
            medium_count += 1

    if high_count > 0:
        return "高风险"
    if medium_count > 0:
        return "中风险"
    return "低风险"


def _generate_risk_summary(items: Any) -> str:
    """Generate a concise risk summary."""
    if not isinstance(items, list) or not items:
        return "未发现明显风险信息"

    parts = []
    text = json.dumps(items, ensure_ascii=False)

    if "失信" in text:
        parts.append("存在失信记录")
    if "被执行" in text:
        parts.append("存在被执行信息")
    if "行政处罚" in text:
        parts.append("有行政处罚记录")
    if "经营异常" in text:
        parts.append("曾被列入经营异常名录")
    if "破产" in text or "清算" in text:
        parts.append("涉及破产/清算程序")
    if "吊销" in text:
        parts.append("存在吊销记录")

    if not parts:
        return f"共发现 {len(items)} 条记录，整体风险较低"

    return "；".join(parts) + f"。共 {len(items)} 条记录"


def _generate_operation_summary(items: Any) -> str:
    """Generate operation summary from QCC data."""
    if not isinstance(items, list) or not items:
        return "暂无经营数据"

    # Extract key financial indicators if available
    text = json.dumps(items, ensure_ascii=False)

    parts = []
    # Try to find revenue/profit keywords
    for item in items[:3] if isinstance(items, list) else []:
        if isinstance(item, dict):
            for k, v in item.items():
                if "收入" in k or "营收" in k or "利润" in k:
                    parts.append(f"{k}: {v}")

    if parts:
        return "经营数据: " + "; ".join(parts[:3])
    return f"共获取 {len(items)} 条经营数据"


# ── Public API ─────────────────────────────────────────────────────────────

def check_company_credit(
    company_name: str,
    include_risk: bool = True,
    include_operation: bool = True,
    include_executives: bool = True,
    include_ipr: bool = False,
    include_history: bool = False,
    include_legal_cases: bool = False,
    include_documents: bool = False,
) -> QccCreditReport:
    """Check company credit by name using QCC official data sources.

    This is the main entry point replacing the previous LLM-based credit
    evaluation.  Returns a comprehensive QccCreditReport with structured data
    from multiple QCC MCP services.

    Parameters
    ----------
    company_name : str
        Full company name to look up.
    include_* : bool
        Toggle individual data categories.  By default includes company info,
        risk, operation, and executives.

    Returns
    -------
    QccCreditReport
        Structured credit report with all requested data categories.

    Raises
    ------
    QccMcpError
        If the QCC service is unavailable or returns an error.
    """
    report = QccCreditReport()

    # 1. Company basic info (always fetched)
    try:
        company_result = _search_company_by_name(company_name)
        report.company = _parse_company_result(company_result)
        logger.info(f"[QCC] Company info fetched: {report.company.company_name}")
    except QccMcpError as e:
        logger.error(f"[QCC] Company search failed: {e}")
        raise

    # If company name was resolved differently, use the official name
    resolved_name = report.company.company_name or company_name

    # 2. Risk info
    if include_risk:
        try:
            report.risk = _search_risk(resolved_name)
            logger.info(f"[QCC] Risk info fetched: level={report.risk.risk_level}, items={len(report.risk.risk_items)}")
        except QccMcpError as e:
            logger.warning(f"[QCC] Risk search failed (non-fatal): {e}")

    # 3. Operation / business data
    if include_operation:
        try:
            report.operation = _search_operation(resolved_name)
            logger.info(f"[QCC] Operation data fetched: {report.operation.summary}")
        except QccMcpError as e:
            logger.warning(f"[QCC] Operation search failed (non-fatal): {e}")

    # 4. Executives (QCC executive tools require personName + searchKey)
    if include_executives:
        try:
            report.executives = _search_service(
                "executive",
                resolved_name,
                person_name=report.company.legal_person or None,
            )
            logger.info(f"[QCC] Executives fetched: {len(report.executives)} persons")
        except QccMcpError as e:
            logger.warning(f"[QCC] Executive search failed (non-fatal): {e}")

    # 5. IPR (optional)
    if include_ipr:
        try:
            report.ipr = _search_service("ipr", resolved_name)
        except QccMcpError as e:
            logger.warning(f"[QCC] IPR search failed (non-fatal): {e}")

    # 6. History
    if include_history:
        try:
            report.history = _search_service("history", resolved_name)
        except QccMcpError as e:
            logger.warning(f"[QCC] History search failed (non-fatal): {e}")

    # 7. Legal cases
    if include_legal_cases:
        try:
            report.legal_cases = _search_service("legal_case", resolved_name)
        except QccMcpError as e:
            logger.warning(f"[QCC] Legal case search failed (non-fatal): {e}")

    # 8. Documents
    if include_documents:
        try:
            report.documents = _search_service("document", resolved_name)
        except QccMcpError as e:
            logger.warning(f"[QCC] Document search failed (non-fatal): {e}")

    return report


def format_credit_summary(report: QccCreditReport) -> str:
    """Format a QccCreditReport into a human-readable summary string.

    Used to populate the 'summary' field in the frontend CreditAnalysis response.
    """
    parts = []

    c = report.company
    if c.company_name:
        parts.append(f"【{c.company_name}】")

    if c.status:
        status_map = {"存续": "✅ 正常经营", "在业": "✅ 正常经营", "注销": "⚠️ 已注销", "吊销": "🚫 已吊销"}
        parts.append(f"经营状态: {status_map.get(c.status, c.status)}")

    if c.registered_capital:
        parts.append(f"注册资本: {c.registered_capital}")

    if c.established_date:
        parts.append(f"成立日期: {c.established_date}")

    if c.legal_person:
        parts.append(f"法定代表人: {c.legal_person}")

    if c.industry:
        parts.append(f"行业: {c.industry}")

    # Risk summary
    if report.risk.risk_level:
        risk_emoji = {"低风险": "🟢", "中风险": "🟡", "高风险": "🔴"}.get(report.risk.risk_level, "⚪")
        parts.append(f"风险评级: {risk_emoji} {report.risk.risk_level}")

    if report.risk.summary and report.risk.summary != "未发现明显风险信息":
        parts.append(f"风险摘要: {report.risk.summary}")

    # Executives
    if report.executives:
        exec_names = [e.get("name", "") or e.get("姓名", "") for e in report.executives[:5] if isinstance(e, dict)]
        exec_names = [n for n in exec_names if n]
        if exec_names:
            parts.append(f"主要人员: {', '.join(exec_names[:5])}")

    # Source marker
    parts.append("— 数据来源: 企查查(QCC)")

    return "\n".join(parts)
