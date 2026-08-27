"""
Credit / Company evaluation routes.
Resume → Job Match → Company Credit: the third leg of the HR evaluation tripod.

Endpoints:
  POST /v1/credit/analyze       — parse raw credit report text via LLM
  POST /v1/credit/check-company  — evaluate a company by name (post-match flow)
                                   ⭐ Now powered by QCC (企查查) official data source
"""
from __future__ import annotations

import json
import logging
import re
import time
from collections import OrderedDict

from flask import Blueprint, request, jsonify, g

from src.api.auth.decorators import require_auth
from src.agents.central_brain import _call_llm
from src.compliance.consent import require_consent
from src.credit.qcc_client import (
    check_company_credit,
    format_credit_summary,
    QccMcpError,
    QccCreditReport,
)

logger = logging.getLogger("looma.credit_routes")

credit_bp = Blueprint("credit", __name__)

# Process-local cache: avoid repeat QCC calls for the same company within TTL.
_CREDIT_CACHE: OrderedDict[str, tuple[float, dict]] = OrderedDict()
_CREDIT_CACHE_TTL = 24 * 3600  # 24h
_CREDIT_CACHE_MAX = 128


def _credit_cache_get(company_name: str) -> dict | None:
    key = company_name.strip().lower()
    if not key or key not in _CREDIT_CACHE:
        return None
    ts, val = _CREDIT_CACHE[key]
    if time.time() - ts >= _CREDIT_CACHE_TTL:
        del _CREDIT_CACHE[key]
        return None
    _CREDIT_CACHE.move_to_end(key)
    return val


def _credit_cache_set(company_name: str, result: dict) -> None:
    key = company_name.strip().lower()
    if not key:
        return
    if key in _CREDIT_CACHE:
        _CREDIT_CACHE.move_to_end(key)
    _CREDIT_CACHE[key] = (time.time(), result)
    while len(_CREDIT_CACHE) > _CREDIT_CACHE_MAX:
        _CREDIT_CACHE.popitem(last=False)


# ---- Helpers ----

def _qcc_is_configured() -> bool:
    """True when QCC is enabled and auth token is non-empty (no secret leaked)."""
    import os
    from flask import current_app

    enabled = str(
        current_app.config.get("QCC_ENABLED", os.getenv("QCC_ENABLED", "true"))
    ).lower() in ("1", "true", "yes", "on")
    if not enabled:
        return False
    try:
        from src.credit.qcc_client import _resolve_auth_token
        return bool(_resolve_auth_token())
    except Exception:
        return bool((os.getenv("QCC_AUTH_TOKEN") or "").strip())


def _sanitize_qcc_error(exc: Exception) -> str:
    """Human-readable QCC failure class without leaking tokens."""
    msg = str(exc)
    low = msg.lower()
    if "QCC_AUTH_TOKEN" in msg or "未配置" in msg or "为空" in msg:
        return "token_missing"
    if "401" in msg or "unauthorized" in low:
        return "unauthorized"
    if "405" in msg or "请求方式异常" in msg:
        return "protocol_error"
    if "timeout" in low:
        return "timeout"
    # Protocol / handshake issues (often misread as network)
    if (
        "endpoint handshake" in low
        or "failed to obtain sse session id" in low
        or "origin mismatch" in low
        or "no search tool" in low
    ):
        return "protocol_error"
    # True transport failures
    if (
        "sse connect failed" in low
        or "connection refused" in low
        or "name or service not known" in low
        or "nodename nor servname" in low
        or "max retries exceeded" in low
        or "network is unreachable" in low
    ):
        return "unreachable"
    return "upstream_error"


def _extract_json_object(text: str) -> dict | None:
    """Parse a JSON object from raw LLM output (fences / prose wrapper OK)."""
    if not text:
        return None
    resp = text.strip()
    if "```" in resp:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", resp)
        if m:
            resp = m.group(1).strip()
    try:
        data = json.loads(resp)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    # Fall back: first balanced {...} block
    start = resp.find("{")
    end = resp.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(resp[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _parse_credit_text(text: str) -> dict | None:
    """LLM-powered credit text extraction: entity_name, report_type, summary.

    Uses a strict JSON-only extractor prompt (not PlanetX navigator persona)
    and low temperature so conversational wrappers are less likely.
    """
    prompt = (
        "你是结构化数据提取器，不是聊天助手，禁止自我介绍或扮演导航员。\n"
        "根据以下文本评估企业信用，只输出一个 JSON 对象，不要 Markdown，不要解释。\n"
        "字段：\n"
        '- "entity_name": 企业名称字符串\n'
        '- "report_type": 报告类型字符串（如：企业信用报告/经营风险评估/工商信息摘要）\n'
        '- "summary": 信用评估摘要字符串（200字以内，含经营状态、风险提示）\n\n'
        "示例：{\"entity_name\":\"示例科技有限公司\",\"report_type\":\"经营风险评估\","
        "\"summary\":\"存续经营，行业地位稳定，未见重大公开风险。\"}\n\n"
        f"待评估文本：\n{text[:4000]}"
    )

    try:
        response = _call_llm(prompt, temperature=0.1, max_tokens=600)
        if not response:
            return None
        data = _extract_json_object(response)
        if not data:
            logger.error("Credit parse failed: no JSON object in LLM response")
            return None
        # Normalize required keys
        return {
            "entity_name": str(data.get("entity_name") or "").strip(),
            "report_type": str(data.get("report_type") or "企业信用评估").strip(),
            "summary": str(data.get("summary") or "").strip(),
        }
    except Exception as e:
        logger.error(f"Credit parse failed: {e}")
        return None


def _credit_diagnostics(qcc_error: str | None = None) -> dict:
    """Attach safe diagnostics for probe scripts."""
    out = {"qcc_configured": _qcc_is_configured()}
    if qcc_error:
        out["qcc_error"] = qcc_error
    return out


def _build_qcc_credit_response(report: QccCreditReport) -> dict:
    """Build a structured credit response from a QCC report.

    Returns a dict compatible with the frontend CreditAnalysis type,
    plus additional fields for rich display.
    """
    c = report.company

    # Determine report type based on what data we have
    report_type = "企业信用报告"
    if report.risk.risk_items and report.operation.raw:
        report_type = "企业综合信用评估（含经营数据）"
    elif report.risk.risk_items:
        report_type = "企业风险评估报告"

    extracted = {
        "entity_name": c.company_name,
        "report_type": report_type,
        "summary": format_credit_summary(report),
    }

    # Extended fields for rich UI display
    extended = {
        "source": report.source,
        "company": {
            "name": c.company_name,
            "legal_person": c.legal_person,
            "registered_capital": c.registered_capital,
            "established_date": c.established_date,
            "credit_code": c.credit_code,
            "status": c.status,
            "industry": c.industry,
            "address": c.address,
            "business_scope": c.business_scope,
        },
        "risk": {
            "level": report.risk.risk_level,
            "summary": report.risk.summary,
            "count": len(report.risk.risk_items),
            "items": report.risk.risk_items[:10],  # top 10 risk items
        },
        "operation": {
            "summary": report.operation.summary,
        },
        "executives": report.executives[:10],
        "ipr": report.ipr[:10] if report.ipr else [],
        "history": report.history[:10] if report.history else [],
        "legal_cases": report.legal_cases[:10] if report.legal_cases else [],
    }

    return {"extracted": extracted, "extended": extended}



# ---- Routes ----

@credit_bp.route("/analyze", methods=["POST"])
@require_auth
@require_consent("credit_query")
def analyze():
    """Parse raw credit / company info text via LLM.

    Body: { "text": "..." }
    Returns: { "extracted": { entity_name, report_type, summary } }
    """
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify(error="missing_text", message="请提供征信/企业信息文本"), 400

    extracted = _parse_credit_text(text)
    if not extracted or not extracted.get("summary"):
        return jsonify(
            error="parse_failed",
            message="征信解析失败，请检查文本内容或重试",
            **_credit_diagnostics(),
        ), 422

    return jsonify(extracted=extracted, source="llm", **_credit_diagnostics())


@credit_bp.route("/check-company", methods=["POST"])
@require_auth
@require_consent("credit_query")
def check_company():
    """Evaluate a company's credit / business status by name.

    ⭐ Now powered by QCC (企查查) official MCP data source — no longer LLM-only.

    Body: { "company_name": "XX科技", "location"?: "深圳", "industry"?: "互联网" }

    The endpoint first tries the QCC official data source.  If QCC is unavailable,
    it falls back to the previous LLM-based evaluation.

    Returns: { "extracted": { entity_name, report_type, summary },
               "extended": { company, risk, operation, executives, ... },
               "source": "qcc" | "llm",
               "qcc_configured": bool,
               "qcc_error"?: str }
    """
    body = request.get_json(silent=True) or {}
    company_name = (body.get("company_name") or "").strip()
    if not company_name:
        return jsonify(error="missing_company", message="请提供公司名称"), 400

    cached = _credit_cache_get(company_name)
    if cached is not None:
        logger.info(f"[Credit] cache hit for '{company_name}'")
        payload = dict(cached)
        payload["cached"] = True
        payload.update(_credit_diagnostics(payload.get("qcc_error")))
        return jsonify(payload)

    location = (body.get("location") or "").strip()
    industry = (body.get("industry") or "").strip()
    qcc_error: str | None = None

    # ── Primary: QCC official data source ──
    try:
        report = check_company_credit(
            company_name=company_name,
            include_risk=True,
            include_operation=True,
            include_executives=True,
            include_ipr=False,
            include_history=False,
            include_legal_cases=False,
            include_documents=False,
        )

        if report.company.company_name:
            logger.info(
                f"[Credit] QCC data retrieved for '{company_name}' → "
                f"risk={report.risk.risk_level}, items={len(report.risk.risk_items)}"
            )
            response = _build_qcc_credit_response(report)
            response["source"] = "qcc"
            response.update(_credit_diagnostics())
            _credit_cache_set(company_name, response)
            return jsonify(response)
        qcc_error = "not_found"

    except QccMcpError as e:
        qcc_error = _sanitize_qcc_error(e)
        logger.warning(
            f"[Credit] QCC unavailable for '{company_name}' ({qcc_error}), "
            f"falling back to LLM: {e}"
        )

    except Exception as e:
        qcc_error = "unexpected"
        logger.error(f"[Credit] QCC unexpected error for '{company_name}': {e}")

    # ── Fallback: LLM-based evaluation (legacy) ──
    logger.info(f"[Credit] Using LLM fallback for '{company_name}'")

    location_hint = f"，位于{location}" if location else ""
    industry_hint = f"，主营{industry}" if industry else ""

    query = (
        f"请评估以下企业的经营状况与信用风险：\n"
        f"企业名称：{company_name}{location_hint}{industry_hint}\n"
        f"请基于你的知识，给出该企业的信用评估摘要，包括经营状态、行业地位、风险提示等。"
    )

    extracted = _parse_credit_text(query)
    if not extracted or not extracted.get("summary"):
        return jsonify(
            error="parse_failed",
            message=f"无法评估 {company_name}，请稍后重试",
            **_credit_diagnostics(qcc_error),
        ), 422

    # Ensure the entity_name matches the requested company
    if not extracted.get("entity_name"):
        extracted["entity_name"] = company_name

    response = {
        "extracted": extracted,
        "source": "llm",
        "warning": (
            "⚠️ 正式数据源暂不可用，当前为 AI 训练知识评估。"
            "本评估基于大语言模型训练数据，不可作为正式征信/风控依据。"
        ),
        **_credit_diagnostics(qcc_error),
    }
    _credit_cache_set(company_name, response)
    return jsonify(response)


@credit_bp.route("/check-company/detail", methods=["POST"])
@require_auth
@require_consent("credit_query")
def check_company_detail():
    """Full detailed credit check with all QCC data categories.

    Body: { "company_name": "XX科技" }

    Includes: company info, risk, operation, executives, IPR, history,
              legal cases, and documents.

    Returns: { "extracted": {...}, "extended": {...}, "source": "qcc" }
    """
    body = request.get_json(silent=True) or {}
    company_name = (body.get("company_name") or "").strip()
    if not company_name:
        return jsonify(error="missing_company", message="请提供公司名称"), 400

    try:
        report = check_company_credit(
            company_name=company_name,
            include_risk=True,
            include_operation=True,
            include_executives=True,
            include_ipr=True,
            include_history=True,
            include_legal_cases=True,
            include_documents=True,
        )

        if not report.company.company_name:
            return jsonify(
                error="not_found",
                message=f"未找到企业 '{company_name}' 的信息",
                **_credit_diagnostics("not_found"),
            ), 404

        response = _build_qcc_credit_response(report)
        response["source"] = "qcc"
        response.update(_credit_diagnostics())

        # Add full extended data for detail view
        response["extended"]["ipr"] = report.ipr
        response["extended"]["history"] = report.history
        response["extended"]["legal_cases"] = report.legal_cases
        response["extended"]["documents"] = report.documents

        return jsonify(response)

    except QccMcpError as e:
        qcc_error = _sanitize_qcc_error(e)
        logger.error(f"[Credit] QCC detail failed for '{company_name}': {e}")
        return jsonify(
            error="qcc_unavailable",
            message="企查查服务暂不可用",
            **_credit_diagnostics(qcc_error),
        ), 503

    except Exception as e:
        logger.error(f"[Credit] QCC detail unexpected error: {e}")
        return jsonify(
            error="internal_error",
            message="征信查询服务异常，请稍后重试",
            **_credit_diagnostics("unexpected"),
        ), 500
