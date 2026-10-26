"""Load payment.v1.json and expose region-aware plan payloads for API routes."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "payment.v1.json"
DEFAULT_REGION = "CN"
SUPPORTED_REGIONS = frozenset({"CN", "US"})
# 部署位别名：契约只建模 CN/US 两区，但海外部署位上报 SG（Vultr 新加坡）。
# 显式传入的部署位码映射到对应美元计费区；其余未识别码仍回 DEFAULT_REGION。
DEPLOY_ALIASES: dict[str, str] = {"SG": "US", "US": "US"}


@lru_cache(maxsize=1)
def _load_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def normalize_region(region: str | None) -> str:
    if not region:
        return DEFAULT_REGION
    code = region.strip().upper()
    if code in SUPPORTED_REGIONS:
        return code
    return DEPLOY_ALIASES.get(code, DEFAULT_REGION)


def _deploy_region_default() -> str | None:
    """Billing region implied by the deploy site, or None on CN/on-prem.

    Overseas deploys bill in USD no matter what language the caller speaks.
    Explicit ``region=CN`` is rejected at the HTTP layer on those deploys
    (see payment_routes._reject_explicit_cn_on_overseas); this helper only
    answers "what does the site settle to when the caller omits region".
    """
    code = os.getenv("DEPLOY_REGION", "").strip().upper()
    return DEPLOY_ALIASES.get(code)


def is_overseas_billing_deploy() -> bool:
    """True on the USD/Stripe site (DEPLOY_REGION=SG or US).

    Unset and CN (and any other unmapped code) are the China/on-prem site and
    must keep accepting CN checkout. Do not treat "resolved region == CN" as
    overseas — that would confuse explicit CN with a CN settlement fallback.
    """
    return _deploy_region_default() == "US"


def resolve_region(region: str | None = None, accept_language: str | None = None) -> str:
    """Pick billing region: explicit param > deploy site > Accept-Language."""
    if region:
        return normalize_region(region)
    # The deploy site decides billing currency BEFORE Accept-Language gets a say.
    # Otherwise a zh-CN browser on the SG site falls to the CN plan and gets its
    # ¥9.9 charged as $9.9 — ~5x the price the page advertises ($1.99).
    deploy_default = _deploy_region_default()
    if deploy_default:
        return deploy_default
    if accept_language:
        lowered = accept_language.lower()
        if lowered.startswith("zh"):
            return "CN"
        # en 及其他非中文语言一律按海外美元区兜底（原实现把非 zh/en 语言落回 CN，
        # 会令海外浏览器（de/fr/ja 等）拿到 CNY 微信方案走 Stripe 集成）
        return "US"
    return DEFAULT_REGION


def list_plans_for_region(region: str | None = None) -> dict[str, Any]:
    code = normalize_region(region)
    contract = _load_contract()
    region_meta = contract["regions"][code]
    currency = region_meta["currency"]

    plans: list[dict[str, Any]] = []
    for entry in contract["plans"]:
        tier = entry["tier"]
        price = entry["prices"][code]
        plans.append(
            {
                "tier": tier,
                "name": entry["name"][code],
                "price_monthly": price["amount"],
                "currency": price["currency"],
                "region": code,
                "plan_id": price["plan_id"],
                "features": entry["features"][code],
                "upgradable": entry.get("upgradable", False),
            }
        )

    return {
        "region": code,
        "currency": currency,
        "payment_provider": region_meta["payment_provider"],
        "payment_providers": region_meta.get("payment_providers", [region_meta["payment_provider"]]),
        "plans": plans,
    }


def get_plan_for_tier(tier: str, region: str | None = None) -> dict[str, Any]:
    code = normalize_region(region)
    payload = list_plans_for_region(code)
    for plan in payload["plans"]:
        if plan["tier"] == tier:
            return plan
    raise KeyError(f"Unknown tier {tier!r} for region {code!r}")


def billing_region_for_provider(provider: str) -> str | None:
    """Which billing region settles through ``provider`` — answered by the contract.

    ``contracts/payment.v1.json`` already declares this ownership:

        regions.US.payment_providers = [stripe, paypal, airwallex]   → USD
        regions.CN.payment_providers = [wechat, huawei_iap]          → CNY

    Callers must derive both ``amount`` and ``currency`` from the plan of the
    region returned here. Reading those two from different sources is what
    produced "9.9 USD": a CN plan amount paired with a USD label, while the
    channel quietly charged $1.99. Returns None for providers the contract
    does not model.
    """
    code = (provider or "").strip().lower()
    if not code:
        return None
    contract = _load_contract()
    for region_code, meta in contract["regions"].items():
        providers = meta.get("payment_providers")
        if not providers:
            providers = [meta["payment_provider"]]
        if code in {str(name).strip().lower() for name in providers}:
            return region_code
    return None


def tier_for_product(rail: str, product_id: str) -> str | None:
    """Map an IAP product_id to a tier from this contract.

    ``rail`` is ``huawei_iap`` or ``apple_iap``. The products table in
    ``payment.v1.json`` is the only map. A missing product or a tier outside
    ``tier_enum`` returns None so the caller can fail closed.
    """
    if not product_id or not rail:
        return None
    contract = _load_contract()
    rail_doc = contract.get(rail)
    if not isinstance(rail_doc, dict):
        return None
    products = rail_doc.get("products")
    if not isinstance(products, dict):
        return None
    tier = products.get(product_id)
    allowed = contract.get("tier_enum") or []
    if not isinstance(tier, str) or tier not in allowed:
        return None
    return tier
