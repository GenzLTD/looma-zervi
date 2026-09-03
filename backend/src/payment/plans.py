"""Load payment.v1.json and expose region-aware plan payloads for API routes."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "payment.v1.json"
DEFAULT_REGION = "CN"
SUPPORTED_REGIONS = frozenset({"CN", "US"})
# 部署位别名：契约只建模 CN/US 两区，但海外部署位上报 SG（Vultr 新加坡）。
# 显式传入的部署位码映射到对应美元计费区；其余未识别码仍回 DEFAULT_REGION。
DEPLOY_ALIASES: dict[str, str] = {"SG": "US"}


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


def resolve_region(region: str | None = None, accept_language: str | None = None) -> str:
    """Pick billing region from explicit query param or Accept-Language hint."""
    if region:
        return normalize_region(region)
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
