"""Driver content management (橱窗/书店) + 通道 B 内容信号 ingest.

多租户 API 层最小防线（2026-09-23 定案落地）：
  1. columns/articles 读写 —— 全部经 @require_driver，以 g.driver_id 作用域执行；
  2. 归属过滤 —— DB 方法层强制 WHERE driver_id（见 manager.py Driver content 段），
     跨驾驶员资源一律 404（不泄露存在性）；
  3. 签名校验 —— POST /v1/signals/content 走通道 B 信封：
     X-Signal-Signature = HMAC-SHA256(raw_body, K(publisher))，
     K(publisher) = HMAC-SHA256(SIGNAL_BRIDGE_SECRET, "signal:" + publisher_id)。
     验签密钥由"信封声称的 publisher_id"推导 —— 用乙的密钥签甲的
     publisher_id 在数学上不可能通过验签（三方归集对账文档 §5.1 用例 9 的断言）。
     幂等：signal_ingest 表 (signal_type, publisher_id, nonce) 主键。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging

from flask import Blueprint, current_app, g, jsonify, request

from src.api.auth.decorators import require_auth, require_driver

logger = logging.getLogger(__name__)

driver_content_bp = Blueprint("driver_content", __name__)     # /v1/driver/*
signal_content_bp = Blueprint("signal_content", __name__)     # /v1/signals/*

CONTENT_SIGNAL_TYPES = ("content_publish", "content_update", "content_remove")


def _db():
    return current_app._db


def _serialize_column(col: dict | None) -> dict | None:
    if not col:
        return None
    return {
        "id": col["id"],
        "driver_id": col["driver_id"],
        "slug": col["slug"],
        "name": col["name"],
        "description": col.get("description"),
        "content_type": col.get("content_type", "article"),
        "icon": col.get("icon"),
        "sort_order": col.get("sort_order", 0),
        "created_at": col.get("created_at"),
    }


def _serialize_article(art: dict | None) -> dict | None:
    if not art:
        return None
    return {
        "id": art["id"],
        "driver_id": art["driver_id"],
        "column_id": art.get("column_id"),
        "title": art["title"],
        "slug": art["slug"],
        "excerpt": art.get("excerpt"),
        "content": art.get("content"),
        "tags": art.get("tags", ""),
        "status": art.get("status", "published"),
        "published_at": art.get("published_at"),
        "updated_at": art.get("updated_at"),
    }


# ============================================================
# columns（书店专栏容器）
# ============================================================

@driver_content_bp.route("/columns", methods=["GET"])
@require_auth
@require_driver
def list_my_columns():
    return jsonify(columns=[_serialize_column(c) for c in _db().list_columns(g.driver_id)])


@driver_content_bp.route("/columns", methods=["POST"])
@require_auth
@require_driver
def create_column():
    data = request.get_json(silent=True) or {}
    slug = (data.get("slug") or "").strip()
    name = (data.get("name") or "").strip()
    if not slug or not name:
        return jsonify(error="bad_request", message="slug and name are required"), 400
    try:
        col = _db().create_column(
            driver_id=g.driver_id,
            slug=slug,
            name=name,
            description=data.get("description"),
            content_type=data.get("content_type", "article"),
            icon=data.get("icon"),
            sort_order=int(data.get("sort_order", 0)),
        )
    except Exception as e:  # UNIQUE(driver_id, slug) 冲突
        logger.info("[driver-content] create_column rejected: %s", e)
        return jsonify(error="conflict", message="slug already exists for this driver"), 409
    return jsonify(column=_serialize_column(col)), 201


@driver_content_bp.route("/columns/<column_id>", methods=["GET"])
@require_auth
@require_driver
def get_my_column(column_id):
    col = _db().get_column(column_id, g.driver_id)
    if not col:
        return jsonify(error="not_found", message="column not found"), 404
    return jsonify(column=_serialize_column(col))


@driver_content_bp.route("/columns/<column_id>", methods=["PATCH"])
@require_auth
@require_driver
def update_my_column(column_id):
    data = request.get_json(silent=True) or {}
    col = _db().update_column(
        column_id, g.driver_id,
        name=data.get("name"),
        description=data.get("description"),
        icon=data.get("icon"),
        sort_order=data.get("sort_order"),
    )
    if col is None:
        return jsonify(error="not_found", message="column not found"), 404
    return jsonify(column=_serialize_column(col))


@driver_content_bp.route("/columns/<column_id>", methods=["DELETE"])
@require_auth
@require_driver
def delete_my_column(column_id):
    try:
        deleted = _db().delete_column(column_id, g.driver_id)
    except Exception:
        # 仍挂着内容的专栏：FK 拒绝删除（articles.column_id_fkey）
        return jsonify(error="conflict",
                       message="column still has content; empty it first"), 409
    if not deleted:
        return jsonify(error="not_found", message="column not found"), 404
    return jsonify(deleted=True)


# ============================================================
# articles（书店存货）
# ============================================================

@driver_content_bp.route("/articles", methods=["GET"])
@require_auth
@require_driver
def list_my_articles():
    db = _db()
    arts = db.list_articles(
        driver_id=g.driver_id,
        column_id=request.args.get("column_id") or None,
        status=request.args.get("status") or None,
        limit=min(int(request.args.get("limit", 50)), 200),
        offset=int(request.args.get("offset", 0)),
    )
    return jsonify(articles=[_serialize_article(a) for a in arts])


@driver_content_bp.route("/articles", methods=["POST"])
@require_auth
@require_driver
def create_my_article():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    slug = (data.get("slug") or "").strip()
    content = data.get("content") or ""
    if not title or not slug or not content:
        return jsonify(error="bad_request",
                       message="title, slug and content are required"), 400

    # column_id 若提供，必须属于本人（DB 方法层查 + 复合外键兜底）
    column_id = data.get("column_id") or None
    if column_id and not _db().get_column(column_id, g.driver_id):
        return jsonify(error="forbidden",
                       message="column_id does not belong to this driver"), 403

    try:
        art = _db().create_article(
            driver_id=g.driver_id,
            title=title,
            slug=slug,
            content=content,
            column_id=column_id,
            excerpt=data.get("excerpt"),
            tags=data.get("tags", ""),
            status=data.get("status", "published"),
        )
    except Exception as e:
        logger.info("[driver-content] create_article rejected: %s", e)
        return jsonify(error="conflict", message="slug already exists for this driver"), 409
    return jsonify(article=_serialize_article(art)), 201


@driver_content_bp.route("/articles/<article_id>", methods=["GET"])
@require_auth
@require_driver
def get_my_article(article_id):
    art = _db().get_article(article_id, g.driver_id)
    if not art:
        return jsonify(error="not_found", message="article not found"), 404
    return jsonify(article=_serialize_article(art))


@driver_content_bp.route("/articles/<article_id>", methods=["PATCH"])
@require_auth
@require_driver
def update_my_article(article_id):
    data = request.get_json(silent=True) or {}
    column_id = data.get("column_id", ...)
    if column_id is not None and column_id is not ...:
        if column_id and not _db().get_column(column_id, g.driver_id):
            return jsonify(error="forbidden",
                           message="column_id does not belong to this driver"), 403
    art = _db().update_article(
        article_id, g.driver_id,
        title=data.get("title"),
        content=data.get("content"),
        excerpt=data.get("excerpt"),
        tags=data.get("tags"),
        status=data.get("status"),
        column_id=column_id,
    )
    if art is None:
        return jsonify(error="not_found", message="article not found"), 404
    return jsonify(article=_serialize_article(art))


@driver_content_bp.route("/articles/<article_id>", methods=["DELETE"])
@require_auth
@require_driver
def delete_my_article(article_id):
    if not _db().delete_article(article_id, g.driver_id):
        return jsonify(error="not_found", message="article not found"), 404
    return jsonify(deleted=True)


# ============================================================
# 通道 B：内容信号 ingest（webhook + HMAC，无 JWT）
# ============================================================

def _derive_publisher_secret(master_secret: str, publisher_id: str) -> bytes:
    """按 publisher 推导独立密钥：K(p) = HMAC-SHA256(master, "signal:" + p)。"""
    return hmac.new(master_secret.encode(), f"signal:{publisher_id}".encode(),
                    hashlib.sha256).digest()


@signal_content_bp.route("/signals/content", methods=["POST"])
def signal_content_ingest():
    """通道 B 内容信号入口。

    验签规则（对齐 ECOSYSTEM_SIGNAL_ADAPTER_GUIDE §4.4 + 三方归集 §5.1）：
      - X-Signal-Signature = hex(HMAC-SHA256(raw_body, K(publisher_id)))
      - 密钥按信封声称的 publisher_id 推导 → "乙钥签甲" 直接验签失败（401）
      - 失败统一 401，不泄露原因；幂等重复 200；未知名/未启用 403
    """
    master_secret = current_app.config.get("SIGNAL_BRIDGE_SECRET", "")
    if not master_secret:
        # fail-closed：信号层未配置即不开放写入面
        return jsonify(error="signal_layer_disabled",
                       message="SIGNAL_BRIDGE_SECRET is not configured"), 503

    body = request.get_data()
    envelope = request.get_json(silent=True)
    if not isinstance(envelope, dict):
        return jsonify(error="bad_request", message="invalid JSON envelope"), 400

    publisher_id = envelope.get("publisher_id") or ""
    signal_type = envelope.get("signal_type") or ""
    nonce = envelope.get("nonce") or ""
    if not publisher_id or not nonce or signal_type not in CONTENT_SIGNAL_TYPES:
        return jsonify(error="bad_request",
                       message="publisher_id, nonce and valid signal_type are required"), 400

    # ① 身份先行：publisher 必须存在且是驾驶员（含 signal 密钥推导依据）
    db = _db()
    publisher = db.get_user_by_id(publisher_id)
    if not publisher or publisher.get("role") not in ("driver", "admin"):
        return jsonify(error="forbidden", message="unknown publisher"), 403

    # ② 验签：用"声称的 publisher"的推导密钥 → 乙钥签甲在数学上不可行
    signature = request.headers.get("X-Signal-Signature", "")
    expected = hmac.new(_derive_publisher_secret(master_secret, publisher_id),
                        body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        logger.warning("[signal-content] signature rejected: publisher=%s type=%s",
                       publisher_id, signal_type)
        return jsonify(error="unauthorized"), 401

    # ③ 断言：载荷内的 publisher_id（若有）必须与信封一致
    data = envelope.get("data") or {}
    inner_publisher = data.get("publisher_id")
    if inner_publisher and inner_publisher != publisher_id:
        logger.warning("[signal-content] publisher mismatch: envelope=%s data=%s",
                       publisher_id, inner_publisher)
        return jsonify(error="forbidden",
                       message="publisher mismatch between envelope and payload"), 403

    # ④ 幂等：(signal_type, publisher_id, nonce)
    if not db.record_signal_ingest(signal_type, publisher_id, nonce,
                                   json.dumps(envelope, ensure_ascii=False)):
        return jsonify(status="duplicate", ignored=True), 200

    # ⑤ 按信号类型落库（稳定键 (publisher_id, slug)，跨库不共享 id）
    slug = (data.get("slug") or "").strip()
    if not slug:
        return jsonify(error="bad_request", message="data.slug is required"), 400

    if signal_type == "content_publish":
        existing = db.get_article_by_slug(publisher_id, slug)
        if existing:
            # 同 (publisher, slug) 重复发布 → 内容更新语义（upsert）
            art = db.update_article(existing["id"], publisher_id,
                                    title=data.get("title"),
                                    content=data.get("content"),
                                    excerpt=data.get("excerpt"))
        else:
            column_id = data.get("column_id") or None
            if column_id and not db.get_column(column_id, publisher_id):
                return jsonify(error="forbidden",
                               message="data.column_id does not belong to publisher"), 403
            art = db.create_article(
                driver_id=publisher_id,
                title=data.get("title") or slug,
                slug=slug,
                content=data.get("content") or "",
                column_id=column_id,
                excerpt=data.get("excerpt"),
            )
        return jsonify(status="accepted", article=_serialize_article(art)), 201

    if signal_type == "content_update":
        art = db.get_article_by_slug(publisher_id, slug)
        if not art:
            return jsonify(error="not_found",
                           message="no such (publisher, slug) to update"), 404
        art = db.update_article(art["id"], publisher_id,
                                title=data.get("title"),
                                content=data.get("content"),
                                excerpt=data.get("excerpt"),
                                status=data.get("status"))
        return jsonify(status="accepted", article=_serialize_article(art)), 200

    # content_remove
    art = db.get_article_by_slug(publisher_id, slug)
    if not art:
        # 幂等语义：删不存在的也视为成功（对端已删即可）
        return jsonify(status="accepted", removed=False), 200
    db.delete_article(art["id"], publisher_id)
    return jsonify(status="accepted", removed=True), 200
