"""Open items: live probes + team-maintained static list.

Feeds the internal API landing page (root.html) so the team sees at a glance
what is missing or needs attention — no need to dig through code or docs.

- Dynamic items: probed from app.config at render time (stub modes, missing
  credentials, mock fallbacks active, ...) — no manual upkeep.
- Static items: backend/open_items.json, maintained by the team
  (status: open / done / blocked). Edit the file → refresh the page.

Usage (in app.py, inside a request context):
    open_items = load_open_items(app)
"""
from __future__ import annotations

import json
import os

# Values that mean "not really configured"
_SKIP_KEYS = {
    "",
    "skip",
    "your-deepseek-api-key",
    "your-openai-api-key",
    "your-key",
    "placeholder",
    "xxx",
    "sk-placeholder",
}


def _is_set(v) -> bool:
    return bool(v and str(v).strip() and str(v).strip().lower() not in _SKIP_KEYS)


def _add(items: list, key: str, title: str, priority: str,
         detail: str = "", ok: bool = False) -> None:
    items.append({
        "id": key,
        "area": "运行时探测",
        "title": title,
        "priority": priority,
        "status": "done" if ok else "open",
        "owner": "",
        "ref": "auto",
        "notes": detail,
    })


def _probe_open_items(cfg) -> list[dict]:
    """Live probes of the running environment."""
    items: list[dict] = []
    P0, P1 = "P0", "P1"

    # Payment stub mode — production must disable it.
    stub = bool(cfg.get("PAYMENT_STUB_MODE", True))
    _add(items, "pay-stub-mode",
         "支付处于 Stub 模式（/v1/payment/upgrade 免支付改 tier）", P0,
         "生产须设 PAYMENT_STUB_MODE=false，否则支付接口 400 或走模拟", ok=not stub)

    # WeChat login dev mode.
    dev = bool(cfg.get("WECHAT_DEV_MODE", False))
    _add(items, "wechat-dev-mode",
         "微信登录 Dev 模式（code 直接当 openid，绕过 code2session）", P1,
         "WECHAT_DEV_MODE=true，仅限本地调试", ok=not dev)

    # WeChat Pay merchant credentials — silent stub orders when incomplete.
    cred_names = ("WECHAT_MCHID", "WECHAT_APPID", "WECHAT_API_V3_KEY",
                  "WECHAT_SERIAL_NO", "WECHAT_PRIVATE_KEY_PATH")
    cred_labels = ("mchid", "appid", "api_v3_key", "serial_no", "private_key")
    cred_values = [cfg.get(k) for k in cred_names]
    missing = [n for n, v in zip(cred_labels, cred_values) if not _is_set(v)]
    _add(items, "wechat-pay-creds",
         "微信支付商户凭证不完整，下单将静默返回 stub 假订单", P0,
         f"缺失: {', '.join(missing) or '无'}", ok=not missing)

    # DeepSeek (LLM primary provider).
    _add(items, "deepseek-key",
         "DeepSeek API Key 未配置，LLM 主 provider 不可用", P0,
         "DEEPSEEK_API_KEY 为空或占位", ok=_is_set(cfg.get("DEEPSEEK_API_KEY")))

    # QCC credit data source.
    qcc_enabled = bool(cfg.get("QCC_ENABLED", True))
    _add(items, "qcc-token",
         "QCC 企查查 AUTH_TOKEN 未配置，credit 接口将降级到 LLM", P1,
         "QCC_AUTH_TOKEN 为空", ok=not qcc_enabled or _is_set(cfg.get("QCC_AUTH_TOKEN")))

    # Google OAuth (G3 overseas login).
    _add(items, "google-oauth",
         "Google OAuth Client ID 未配置（G3 海外登录不可用）", P1,
         "GOOGLE_CLIENT_ID 为空", ok=_is_set(cfg.get("GOOGLE_CLIENT_ID")))

    # Stripe (overseas payments).
    stripe_ok = _is_set(cfg.get("STRIPE_SECRET_KEY")) and _is_set(cfg.get("STRIPE_WEBHOOK_SECRET"))
    _add(items, "stripe-creds",
         "Stripe 凭证未配置（海外支付不可用）", P1,
         "STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET 缺失", ok=stripe_ok)

    # Huawei Push (HarmonyOS).
    _add(items, "huawei-push",
         "华为推送凭证未配置（HarmonyOS 推送不可用）", P1,
         "HUAWEI_PUSH_CLIENT_ID 为空", ok=_is_set(cfg.get("HUAWEI_PUSH_CLIENT_ID")))

    # Jobs persisted? Empty DB → GET /v1/jobs/list silently serves MOCK_JOBS.
    try:
        from src.api.routes.jobs_routes import _get_persisted_jobs

        n = len(_get_persisted_jobs())
        _add(items, "jobs-mock-active",
             "无持久化岗位：GET /v1/jobs/list 返回 MOCK_JOBS 假数据", P0,
             f"documents(job,processed) 现有 {n} 条；空库时静默 fallback mock", ok=n > 0)
    except Exception as exc:  # probe failure → surface as open, not silent
        _add(items, "jobs-mock-active",
             "无法探测岗位数据源（/v1/jobs/list 可能返回 MOCK_JOBS）", P0,
             f"probe error: {exc}", ok=False)

    return items


def _load_static_list() -> list[dict]:
    """Team-maintained list from backend/open_items.json."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "open_items.json")
    try:
        with open(path, encoding="utf-8") as fh:
            items = json.load(fh).get("items", [])
    except Exception:
        items = []
    for it in items:
        it.setdefault("area", "登记清单")
        it.setdefault("owner", "")
        it.setdefault("notes", "")
        it.setdefault("ref", "")
        it.setdefault("priority", "P2")
        it.setdefault("status", "open")
    return items


def load_open_items(app) -> dict:
    """Combined: dynamic probes + static list. Returns open items + counts."""
    dynamic = _probe_open_items(app.config)
    static = _load_static_list()
    open_items = (
        [i for i in dynamic if i["status"] == "open"]
        + [i for i in static if i["status"] == "open"]
    )
    done_count = (
        sum(1 for i in dynamic if i["status"] == "done")
        + sum(1 for i in static if i["status"] == "done")
    )
    # NOTE: key is "list" — "items" would collide with dict.items() in Jinja.
    return {"list": open_items, "done": done_count, "dynamic": len(dynamic)}
