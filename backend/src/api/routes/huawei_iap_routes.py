"""
华为 IAP Kit 支付回调路由

流程：元服务客户端完成支付 → 上报 purchaseData + signature →
      服务端 RSA 验签 → 校验一致性 → 发货升级

参考文档：
  https://developer.huawei.com/consumer/cn/doc/HMSCore-References/api-purchase-request-0000001050125197

Endpoints:
  POST /v1/payment/huawei/notify - 客户端支付回调（验签 + 发货）
  POST /v1/payment/huawei/verify - 服务端向华为验证订单（可选，安全等级更高）
"""

import json
import logging
import base64
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

from src.api.auth.decorators import require_auth

logger = logging.getLogger(__name__)

huawei_iap_bp = Blueprint("huawei_iap", __name__)


# ============================================================
# 配置
# ============================================================

def _get_hw_config():
    """从 app config 提取华为 IAP 配置。"""
    return {
        "public_key": current_app.config.get("HUAWEI_IAP_PUBLIC_KEY", ""),
        "default_algorithm": current_app.config.get(
            "HUAWEI_IAP_SIGN_ALGORITHM", "SHA256WithRSA"
        ),
    }


def _load_public_key(pem_key: str):
    """加载 PEM 格式的 RSA 公钥。

    华为 IAP 公钥可能是裸 Base64，自动补齐 PEM 头尾。
    """
    if not pem_key:
        raise ValueError("HUAWEI_IAP_PUBLIC_KEY not configured")

    if "-----BEGIN PUBLIC KEY-----" not in pem_key:
        pem_key = (
            "-----BEGIN PUBLIC KEY-----\n"
            + pem_key
            + "\n-----END PUBLIC KEY-----"
        )

    return serialization.load_pem_public_key(
        pem_key.encode("utf-8"),
        backend=default_backend(),
    )


# ============================================================
# RSA 验签
# ============================================================

def verify_signature(
    content: str,
    signature: str,
    signature_algorithm: str = "SHA256WithRSA",
) -> bool:
    """验证华为 IAP 购买数据的 RSA 签名。

    Args:
        content: 原始 purchaseData JSON 字符串
        signature: Base64 签名字符串
        signature_algorithm: SHA256WithRSA | SHA256WithRSA/PSS
    """
    if not content or not signature:
        return False

    cfg = _get_hw_config()
    if not cfg["public_key"]:
        logger.warning("[huawei_iap] No IAP public key configured — skipping verify")
        return True  # dev 模式放行

    try:
        public_key = _load_public_key(cfg["public_key"])
        signature_bytes = base64.b64decode(signature)

        if "PSS" in signature_algorithm.upper():
            pad = padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        else:
            pad = padding.PKCS1v15()

        public_key.verify(
            signature_bytes,
            content.encode("utf-8"),
            pad,
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


# ============================================================
# 订单处理
# ============================================================

def _parse_purchase_data(purchase_data_str: str) -> dict:
    """解析 purchaseData JSON 字符串。"""
    return json.loads(purchase_data_str)


def _validate_consistency(
    purchase_data: dict,
    expected_product_id: str = "",
    expected_amount: str = "",
) -> bool:
    """校验 productId / price 一致性，防止篡改。"""
    if expected_product_id and purchase_data.get("productId") != expected_product_id:
        return False
    if expected_amount and str(purchase_data.get("price")) != expected_amount:
        return False
    return True


def _process_delivery(purchase_data: dict, user_id: str) -> tuple[bool, str]:
    """发货逻辑：记录订单 → 升级 tier → 创建订阅。

    使用 purchaseToken + productId 做幂等判断。
    """
    purchase_token = purchase_data.get("purchaseToken", "")
    product_id = purchase_data.get("productId", "")
    order_id = purchase_data.get("orderId", "")
    purchase_state = purchase_data.get("purchaseState", -1)

    # purchaseState == 0 表示已购买
    if purchase_state != 0:
        return False, f"Invalid purchaseState: {purchase_state}"

    db = current_app._db

    # --- 防重复发货 ---
    with db.get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM orders WHERE metadata_json LIKE ? AND status = 'paid' LIMIT 1",
            (f"%{purchase_token}%",),
        ).fetchone()
    if existing:
        return True, "Already delivered"

    # --- 映射 productId → tier ---
    TIER_MAP = current_app.config.get(
        "HUAWEI_IAP_TIER_MAP",
        {
            "premium_monthly": "supporter",
            "pro_monthly": "pro",
            "supporter": "supporter",
            "pro": "pro",
        },
    )
    tier = TIER_MAP.get(product_id, "supporter")

    # --- 写入订单 ---
    out_trade_no = f"LOOMA_HW_{order_id or purchase_token[:16]}"
    amount_value = float(purchase_data.get("price", 0))
    currency = purchase_data.get("currency", "CNY")

    order = db.create_order(
        user_id=user_id,
        plan_id=f"huawei_{product_id}",
        tier=tier,
        amount=amount_value,
        currency=currency,
        out_trade_no=out_trade_no,
        metadata_json={
            "provider": "huawei_iap",
            "purchase_token": purchase_token,
            "product_id": product_id,
            "order_id": order_id,
        },
    )

    # --- 标记支付 + 升级 tier + 创建订阅 ---
    db.mark_order_paid(out_trade_no, purchase_token)
    db.update_user_tier(user_id, tier)

    expires = (datetime.now() + timedelta(days=30)).isoformat()
    db.upsert_subscription(user_id, tier, f"huawei_{product_id}", expires, auto_renew=False)

    logger.info(
        f"[huawei_iap] Delivery complete: user={user_id} tier={tier} "
        f"product={product_id} order={out_trade_no}"
    )
    return True, order_id


# ============================================================
# 路由
# ============================================================

@huawei_iap_bp.route("/notify", methods=["POST"])
@require_auth
def iap_notify():
    """
    POST /v1/payment/huawei/notify

    元服务客户端完成华为支付后，将 purchaseData + signature 上报服务端验签发货。

    请求体:
    {
        "purchaseData": "{\"orderId\":\"...\",\"productId\":\"...\",\"purchaseToken\":\"...\",...}",
        "purchaseSignature": "Base64签名...",
        "signatureAlgorithm": "SHA256WithRSA",   # 可选
        "expectedProductId": "premium_monthly",  # 可选，一致性校验
        "expectedAmount": "9.99"                 # 可选
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="bad_request", message="Invalid JSON body"), 400

    purchase_data_str = data.get("purchaseData") or ""
    purchase_signature = data.get("purchaseSignature") or ""
    signature_algorithm = data.get("signatureAlgorithm", "")
    expected_product_id = data.get("expectedProductId", "")
    expected_amount = data.get("expectedAmount", "")

    # --- Step 1: 基础校验 ---
    if not purchase_data_str or not purchase_signature:
        return jsonify(
            error="bad_request", message="purchaseData and purchaseSignature are required"
        ), 400

    # --- Step 2: RSA 验签 ---
    if not verify_signature(purchase_data_str, purchase_signature, signature_algorithm):
        logger.warning("[huawei_iap] Signature verification FAILED")
        return jsonify(error="invalid_signature", message="Signature verification failed"), 403

    # --- Step 3: 解析购买数据 ---
    try:
        purchase_data = _parse_purchase_data(purchase_data_str)
    except json.JSONDecodeError:
        return jsonify(error="bad_request", message="Invalid purchaseData JSON"), 400

    # --- Step 4: 校验一致性 ---
    if not _validate_consistency(purchase_data, expected_product_id, expected_amount):
        return jsonify(
            error="consistency_check_failed",
            message="Order consistency check failed (productId/price mismatch)",
        ), 409

    # --- Step 5: 发货 ---
    from flask import g as request_g
    user_id = request_g.user_id
    success, detail = _process_delivery(purchase_data, user_id)

    if success:
        return jsonify(
            result="OK",
            message="Order processed successfully",
            order_id=detail,
        ), 200
    else:
        return jsonify(
            result="FAIL",
            message=detail,
        ), 500


@huawei_iap_bp.route("/verify", methods=["POST"])
@require_auth
def iap_server_verify():
    """
    POST /v1/payment/huawei/verify

    服务端主动向华为 IAP 验证订单（可选，安全等级更高）。
    需要 OAuth 2.0 Client Credentials → 调用 Order 服务验证。

    MVP: 返回计划中状态。
    """
    data = request.get_json(silent=True) or {}
    purchase_token = data.get("purchaseToken", "")
    product_id = data.get("productId", "")

    if not purchase_token or not product_id:
        return jsonify(
            error="bad_request", message="purchaseToken and productId are required"
        ), 400

    return jsonify(
        verified=False,
        message="Server-side Huawei IAP verification not yet implemented (MVP: client-side verify only)",
        hint="Use POST /v1/payment/huawei/notify with verified purchaseData instead.",
    ), 501
