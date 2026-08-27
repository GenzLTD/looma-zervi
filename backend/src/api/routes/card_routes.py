"""
元服务卡片数据接口

为 HarmonyOS FormExtensionAbility 的 onUpdateForm 提供动态数据刷新。
设计原则：
  - 极低延迟 (<200ms)，最小化 JSON payload
  - 独立端点与限流，避免影响主业务
  - 内置 ttl 机制，客户端据此判断刷新间隔

Endpoints:
  GET  /v1/card/<card_id>     - 单个卡片数据
  POST /v1/card/batch         - 批量获取多个卡片数据
"""

import time
import hashlib
import json
import logging

from flask import Blueprint, request, jsonify, g, current_app

from src.api.auth.decorators import require_auth

logger = logging.getLogger(__name__)

card_bp = Blueprint("card", __name__)


# ============================================================
# 卡片数据源
# ============================================================

def _get_weather_card(user_id: str) -> dict:
    """天气卡片。MVP 返回静态示例。"""
    return {
        "type": "weather",
        "data": {
            "city": "Shenzhen",
            "temperature": "30°C",
            "weather": "Partly Cloudy",
            "humidity": "68%",
            "updateTime": int(time.time()),
        },
    }


def _get_profile_card(user_id: str) -> dict:
    """个人资料卡片。"""
    db = current_app._db
    user = db.get_user_by_id(user_id)
    return {
        "type": "profile",
        "data": {
            "displayName": user.get("name", "User") if user else "User",
            "tier": user.get("tier", "free") if user else "free",
            "level": _tier_display(user.get("tier", "free")) if user else "Free",
            "updateTime": int(time.time()),
        },
    }


def _get_status_card(user_id: str) -> dict:
    """状态卡片。"""
    return {
        "type": "status",
        "data": {
            "status": "active",
            "message": "All systems nominal",
            "updateTime": int(time.time()),
        },
    }


def _get_activity_card(user_id: str) -> dict:
    """动态/活动卡片 — 从 timeline_events 取最近活跃条数。"""
    recent_count = 0
    message = "No recent activity"
    try:
        db = current_app._db
        recent_count = int(db.count_timeline_events(user_id) or 0)
        if recent_count > 0:
            message = f"{recent_count} timeline events"
    except Exception as e:
        logger.warning("card activity: timeline count failed for %s: %s", user_id, e)
    return {
        "type": "activity",
        "data": {
            "recentCount": recent_count,
            "message": message,
            "updateTime": int(time.time()),
        },
    }


_CARD_DISPATCH = {
    "weather": _get_weather_card,
    "profile": _get_profile_card,
    "status": _get_status_card,
    "activity": _get_activity_card,
}


def _tier_display(tier: str) -> str:
    """tier 值 → 展示名。"""
    return {
        "free": "Free",
        "supporter": "Silver",
        "pro": "Gold",
        "enterprise": "Enterprise",
    }.get(tier, tier.title())


# ============================================================
# 路由
# ============================================================

def _etag_response(card_id: str, result: dict, ttl: int = 300):
    """构建响应，支持 ETag / 304 条件请求。

    客户端可发送 If-None-Match 头，内容未变化时返回 304 节省带宽。
    """
    data_str = json.dumps(result.get("data", {}), sort_keys=True, ensure_ascii=False)
    etag = f'W/"{hashlib.md5(data_str.encode()).hexdigest()}"'

    if request.headers.get("If-None-Match") == etag:
        return "", 304

    resp = jsonify(
        cardId=card_id,
        type=result["type"],
        data=result["data"],
        ttl=ttl,
        timestamp=int(time.time()),
    )
    resp.status_code = 200
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = f"max-age={ttl}"
    return resp


@card_bp.route("/card/<card_id>", methods=["GET"])
@require_auth
def get_card(card_id: str):
    """
    GET /v1/card/{card_id}?type=profile

    查询参数:
        type: 卡片类型（weather | profile | status | activity），默认 profile

    返回最小化 JSON:
    {
        "cardId": "card_abc",
        "type": "profile",
        "data": { ... },
        "ttl": 300,
        "timestamp": 1690000000
    }
    """
    card_type = request.args.get("type", "profile").strip().lower()

    if card_type not in _CARD_DISPATCH:
        return jsonify(
            error="unknown_card_type",
            message=f"Supported card types: {', '.join(_CARD_DISPATCH)}",
        ), 404

    handler = _CARD_DISPATCH[card_type]
    result = handler(g.get("user_id", "anonymous"))

    return _etag_response(card_id, result, ttl=300)


@card_bp.route("/card/batch", methods=["POST"])
@require_auth
def get_cards_batch():
    """
    POST /v1/card/batch

    请求体:
    {
        "cards": [
            {"cardId": "card_1", "type": "weather"},
            {"cardId": "card_2", "type": "profile"}
        ]
    }

    批量获取多个卡片数据，减少请求次数。
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="bad_request", message="Invalid JSON"), 400

    cards = data.get("cards", [])
    if not isinstance(cards, list):
        return jsonify(error="bad_request", message="'cards' must be an array"), 400

    user_id = g.get("user_id", "anonymous")
    now = int(time.time())

    results = []
    for card in cards:
        card_id = card.get("cardId", "")
        card_type = card.get("type", "profile").strip().lower()

        if card_type in _CARD_DISPATCH:
            handler = _CARD_DISPATCH[card_type]
            result = handler(user_id)
            result["cardId"] = card_id
        else:
            result = {
                "cardId": card_id,
                "type": card_type,
                "data": {"error": "unknown card type"},
            }

        result["ttl"] = 300
        result["timestamp"] = now
        results.append(result)

    return jsonify(cards=results), 200
