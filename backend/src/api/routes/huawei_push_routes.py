"""
华为 Push Kit 服务端

Token 管理：SQLite 表存储 push_token ↔ user_id 映射
消息推送：华为 Push API V3

参考文档：
  https://developer.huawei.com/consumer/cn/doc/HMSCore-References/push-send-message-0000001050125220

Endpoints:
  POST /v1/push/huawei/register   - 绑定 pushToken 到用户
  POST /v1/push/huawei/unregister - 解绑 pushToken
  POST /v1/push/huawei/send       - 向指定用户发送推送
"""

import time
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests
from flask import Blueprint, request, jsonify, current_app, g

from src.api.auth.decorators import require_auth
from src.db.manager import DatabaseManager

logger = logging.getLogger(__name__)

huawei_push_bp = Blueprint("huawei_push", __name__)


# ============================================================
# 配置
# ============================================================

def _push_config() -> dict:
    return {
        "push_api_url": "https://push-api.cloud.huawei.com",
        "auth_url": "https://oauth-login.cloud.huawei.com/oauth2/v3/token",
        "client_id": current_app.config.get("HUAWEI_PUSH_CLIENT_ID", ""),
        "client_secret": current_app.config.get("HUAWEI_PUSH_CLIENT_SECRET", ""),
        "project_id": current_app.config.get("HUAWEI_PROJECT_ID", ""),
    }


PUSH_API_BASE = "https://push-api.cloud.huawei.com"


# ============================================================
# Access Token 缓存 (内存，避免频繁请求，限流 1000次/5分钟)
# ============================================================

_token_cache: dict = {
    "access_token": None,
    "expires_at": 0,
}


def _get_push_access_token() -> str:
    """获取华为 Push API OAuth 2.0 Access Token（Client Credentials 模式）。"""
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    cfg = _push_config()
    resp = requests.post(
        cfg["auth_url"],
        data={
            "grant_type": "client_credentials",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"Failed to get Push access token: HTTP {resp.status_code} — {resp.text[:200]}"
        )

    data = resp.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)

    return _token_cache["access_token"]


# ============================================================
# Token 管理 (SQLite)
# ============================================================

def _get_db() -> DatabaseManager:
    return current_app._db


def bind_push_token(user_id: str, push_token: str):
    """绑定 pushToken 到用户（幂等：同用户新 Token 替换旧 Token）。

    Push Token 在以下场景会静默变化，元服务端应监听 tokenUpdate 事件主动上报：
      - 用户卸载重装应用
      - 设备恢复出厂设置
      - 用户跨地区（AAID 变化）

    元服务端 ArkTS 示例:
        import { pushService } from '@kit.PushKit';
        pushService.on('tokenUpdate', (newToken: string) => {
            http.createHttp().request('https://api.example.com/v1/push/huawei/register', {
                method: http.RequestMethod.POST,
                extraData: JSON.stringify({ pushToken: newToken, userId: currentUserId }),
            });
        });
    """
    db = _get_db()
    with db.get_conn() as conn:
        # 先删除旧映射（同 token 跨用户 / 同用户旧 token）→ 保证幂等
        conn.execute(
            "DELETE FROM huawei_push_tokens WHERE push_token = ? OR user_id = ?",
            (push_token, user_id),
        )
        conn.execute(
            "INSERT INTO huawei_push_tokens (user_id, push_token, created_at) VALUES (?, ?, ?)",
            (user_id, push_token, int(time.time())),
        )


def unbind_push_token(push_token: str):
    """解绑 pushToken（用户登出时调用）。"""
    db = _get_db()
    with db.get_conn() as conn:
        conn.execute(
            "DELETE FROM huawei_push_tokens WHERE push_token = ?",
            (push_token,),
        )


def get_user_tokens(user_id: str) -> list[str]:
    """获取用户所有绑定的 pushToken。"""
    db = _get_db()
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT push_token FROM huawei_push_tokens WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return [r["push_token"] for r in rows]


def _get_all_tokens() -> list[str]:
    """获取所有已注册的 pushToken（慎用，全量推送时使用）。"""
    db = _get_db()
    with db.get_conn() as conn:
        rows = conn.execute("SELECT push_token FROM huawei_push_tokens").fetchall()
    return [r["push_token"] for r in rows]


# ============================================================
# 推送发送
# ============================================================

def send_push(
    user_id: str,
    title: str,
    body: str,
    category: str = "MARKETING",
    click_data: Optional[dict] = None,
    test_mode: bool = False,
) -> dict:
    """向指定用户发送华为推送通知。

    Args:
        user_id: 目标用户 ID
        title: 通知标题
        body: 通知内容
        category: 消息分类 (MARKETING / SOCIAL / SERVICE)
        click_data: 点击消息后传递的数据
        test_mode: 是否为测试消息
    """
    tokens = get_user_tokens(user_id)
    if not tokens:
        return {"success": False, "reason": "No push tokens registered for user"}

    cfg = _push_config()
    try:
        access_token = _get_push_access_token()
    except RuntimeError as e:
        logger.error(f"[huawei_push] Failed to get access token: {e}")
        return {"success": False, "reason": str(e)}

    url = f"{cfg['push_api_url']}/v3/{cfg['project_id']}/messages:send"

    payload = {
        "payload": {
            "notification": {
                "category": category,
                "title": title,
                "body": body,
                "clickAction": {
                    "actionType": 0,
                    "data": click_data or {},
                },
            }
        },
        "target": {"token": tokens},
        "pushOptions": {"testMessage": test_mode},
    }

    resp = requests.post(
        url,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "push-type": "0",
        },
        timeout=15,
    )

    result = resp.json() if resp.text else {}
    success = resp.status_code == 200 and result.get("code") == "80000000"

    return {
        "success": success,
        "http_code": resp.status_code,
        "data": result,
    }


# ============================================================
# 批量异步推送 (ThreadPoolExecutor)
# ============================================================

def _send_push_to_tokens(
    tokens: list[str],
    title: str,
    body: str,
    category: str,
    click_data: Optional[dict],
    test_mode: bool,
) -> dict:
    """向指定 token 列表发送推送（被 send_push_batch 线程池调用）。"""
    try:
        access_token = _get_push_access_token()
    except RuntimeError as e:
        return {"success": False, "reason": str(e), "token_count": len(tokens)}

    cfg = _push_config()
    url = f"{cfg['push_api_url']}/v3/{cfg['project_id']}/messages:send"

    payload = {
        "payload": {
            "notification": {
                "category": category,
                "title": title,
                "body": body,
                "clickAction": {"actionType": 0, "data": click_data or {}},
            }
        },
        "target": {"token": tokens},
        "pushOptions": {"testMessage": test_mode},
    }

    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "push-type": "0",
            },
            timeout=30,
        )
        result = resp.json() if resp.text else {}
        success = resp.status_code == 200 and result.get("code") == "80000000"
        return {
            "success": success,
            "http_code": resp.status_code,
            "token_count": len(tokens),
            "data": result,
        }
    except requests.RequestException as e:
        return {"success": False, "reason": str(e), "token_count": len(tokens)}


def send_push_batch(
    user_ids: list[str],
    title: str,
    body: str,
    category: str = "MARKETING",
    click_data: Optional[dict] = None,
    test_mode: bool = False,
) -> list[dict]:
    """批量异步推送：将多个用户的推送拆分为最多 1000 token/批，并发发送。

    适用场景：运营消息、全量通知。
    """
    all_tokens: list[str] = []
    seen: set[str] = set()
    for uid in user_ids:
        for t in get_user_tokens(uid):
            if t not in seen:
                all_tokens.append(t)
                seen.add(t)

    if not all_tokens:
        return [{"success": False, "reason": "No registered tokens"}]

    # 华为单次上限 1000 token
    batches = [all_tokens[i : i + 1000] for i in range(0, len(all_tokens), 1000)]

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(5, len(batches))) as executor:
        future_to_batch = {
            executor.submit(
                _send_push_to_tokens,
                batch,
                title,
                body,
                category,
                click_data,
                test_mode,
            ): batch
            for batch in batches
        }
        for future in as_completed(future_to_batch):
            try:
                results.append(future.result(timeout=30))
            except Exception as e:
                results.append({"success": False, "reason": str(e)})

    return results


# ============================================================
# 路由
# ============================================================

@huawei_push_bp.route("/register", methods=["POST"])
@require_auth
def register_token():
    """
    POST /v1/push/huawei/register

    请求体:
    {
        "pushToken": "IQAAAA**********4Tw"
    }

    用户 ID 从 JWT 自动获取。
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="bad_request", message="Invalid JSON body"), 400

    push_token = (data.get("pushToken") or "").strip()
    if not push_token:
        return jsonify(error="bad_request", message="pushToken is required"), 400

    user_id = g.user_id
    bind_push_token(user_id, push_token)

    logger.info(f"[huawei_push] Token registered: user={user_id}")
    return jsonify(status="registered", user_id=user_id), 200


@huawei_push_bp.route("/unregister", methods=["POST"])
@require_auth
def unregister_token():
    """
    POST /v1/push/huawei/unregister

    请求体:
    {
        "pushToken": "IQAAAA**********4Tw"
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="bad_request", message="Invalid JSON body"), 400

    push_token = (data.get("pushToken") or "").strip()
    if not push_token:
        return jsonify(error="bad_request", message="pushToken is required"), 400

    unbind_push_token(push_token)
    return jsonify(status="unregistered"), 200


@huawei_push_bp.route("/send", methods=["POST"])
@require_auth
def send_notification():
    """
    POST /v1/push/huawei/send

    请求体:
    {
        "title": "New message",
        "body": "You have a new friend request",
        "category": "SOCIAL",       // MARKETING | SOCIAL | SERVICE
        "clickData": { ... },        // 可选
        "testMode": false            // 可选
    }
    """
    from flask import g

    data = request.get_json(silent=True) or {}
    title = data.get("title", "Notification")
    body = data.get("body", "")
    category = data.get("category", "MARKETING")
    click_data = data.get("clickData")
    test_mode = data.get("testMode", False)

    if not body:
        return jsonify(error="bad_request", message="body is required"), 400

    user_id = g.user_id

    # 检查推送凭证是否配置
    cfg = _push_config()
    if not cfg["client_id"] or not cfg["client_secret"] or not cfg["project_id"]:
        return jsonify(
            error="push_not_configured",
            message="Huawei Push not configured. Set HUAWEI_PUSH_CLIENT_ID, HUAWEI_PUSH_CLIENT_SECRET, HUAWEI_PROJECT_ID env vars.",
        ), 503

    result = send_push(user_id, title, body, category, click_data, test_mode)

    if result["success"]:
        return jsonify(status="sent", user_id=user_id), 200
    else:
        logger.warning(f"[huawei_push] Send failed: {result.get('reason', 'unknown')}")
        return jsonify(error="push_failed", detail=result), 502


@huawei_push_bp.route("/batch", methods=["POST"])
@require_auth
def send_batch():
    """
    POST /v1/push/huawei/batch

    批量推送给多个用户（ThreadPoolExecutor 并发，每批最多 1000 token）。

    请求体:
    {
        "userIds": ["user_1", "user_2", ...],
        "title": "System Notification",
        "body": "Maintenance scheduled at midnight",
        "category": "SERVICE",       // MARKETING | SOCIAL | SERVICE
        "clickData": { ... },         // 可选
        "testMode": false             // 可选
    }
    """
    data = request.get_json(silent=True) or {}
    user_ids = data.get("userIds", [])
    title = data.get("title", "Notification")
    body = data.get("body", "")
    category = data.get("category", "MARKETING")
    click_data = data.get("clickData")
    test_mode = data.get("testMode", False)

    if not user_ids or not isinstance(user_ids, list):
        return jsonify(error="bad_request", message="userIds (list) is required"), 400
    if not body:
        return jsonify(error="bad_request", message="body is required"), 400

    cfg = _push_config()
    if not cfg["client_id"] or not cfg["client_secret"] or not cfg["project_id"]:
        return jsonify(
            error="push_not_configured",
            message="Huawei Push not configured.",
        ), 503

    results = send_push_batch(user_ids, title, body, category, click_data, test_mode)

    succeeded = sum(1 for r in results if r.get("success"))
    logger.info(
        f"[huawei_push] Batch sent: {succeeded}/{len(results)} batches "
        f"to {len(user_ids)} users"
    )

    return jsonify(
        status="completed",
        total_batches=len(results),
        succeeded_batches=succeeded,
        details=results,
    ), 200
