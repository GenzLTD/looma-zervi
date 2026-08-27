"""
Payment routes blueprint — Stub + WeChat Pay (CN) + Multi-provider overseas.

Endpoints:
  GET  /v1/payment/plans             - List available pricing plans (region-aware)
  GET  /v1/payment/status            - Current user's subscription status
  GET  /v1/payment/providers         - List configured payment providers
  POST /v1/payment/upgrade           - Upgrade tier (stub: blocked unless PAYMENT_STUB_MODE=true)
  POST /v1/payment/wechat/order      - Create WeChat Pay order → prepay_id / qr_code [CN]
  POST /v1/payment/wechat/notify     - WeChat Pay callback (no auth, signature verified) [CN]
  POST /v1/payment/checkout          - Unified checkout → provider redirect URL [overseas]
  POST /v1/payment/webhook/<provider>- Unified webhook receiver (no auth, signature verified) [overseas]
  POST /v1/payment/stripe/checkout   - [DEPRECATED] Alias for unified checkout (backward compat)
  POST /v1/payment/stripe/webhook    - [DEPRECATED] Alias for unified webhook (backward compat)

Pricing contract: backend/contracts/payment.v1.json
  CN supporter: ¥9.9/mo · US supporter: $1.99/mo

For production, set PAYMENT_STUB_MODE=false and configure payment credentials.
"""
from flask import Blueprint, jsonify, g, request, current_app

from src.api.auth.decorators import require_auth
from src.api.auth.jwt_handler import sign_token_for_user
from src.analytics.events import (
    log_product_event,
    platform_from_request,
    EVENT_TRIAL_STARTED,
    EVENT_TRIAL_FAILED,
)
from src.payment.plans import get_plan_for_tier, list_plans_for_region, resolve_region
from src.payment.wechat_pay import (
    create_native_order,
    generate_out_trade_no,
    verify_notify_sign,
    parse_notify_body,
    build_notify_response,
    WECHAT_SIGNATURE_HEADER,
    WECHAT_SERIAL_HEADER,
    WECHAT_TIMESTAMP_HEADER,
    WECHAT_NONCE_HEADER,
)
# Legacy Stripe imports (backward compat)
from src.payment.stripe_pay import (
    create_checkout_session as stripe_create_checkout,
    verify_webhook_signature as stripe_verify_webhook,
    parse_webhook_event as stripe_parse_webhook,
    generate_out_trade_no as stripe_generate_order_no,
)
# Multi-provider system
from src.payment.providers import get_provider, list_configured_providers
from src.payment.providers.base import CheckoutResult, WebhookResult

payment_bp = Blueprint("payment", __name__)

UPGRADABLE_TIERS = frozenset({"supporter", "pro"})
TIER_ORDER = {"free": 0, "supporter": 1, "pro": 2, "enterprise": 3}

# 人民币金额 → 分（WeChat Pay 以分为单位）
TIER_PRICE_FEN = {
    "supporter": 990,   # ¥9.90
    "pro": 2990,         # ¥29.90
}

# USD 金额 → cents（Stripe 以 cents 为单位）
TIER_PRICE_USD_CENTS = {
    "supporter": 199,    # $1.99
    "pro": 599,          # $5.99
}


def _is_stub_mode():
    """检查当前是否为 Stub 模式。"""
    return current_app.config.get("PAYMENT_STUB_MODE", True)


@payment_bp.route("/payment/plans", methods=["GET"])
def list_plans():
    """List pricing plans for a billing region (?region=CN|US)."""
    region = resolve_region(
        request.args.get("region"),
        request.headers.get("Accept-Language"),
    )
    payload = list_plans_for_region(region)
    return jsonify(**payload)


@payment_bp.route("/payment/status", methods=["GET"])
@require_auth
def payment_status():
    """Get current user's subscription status, including real subscription expiry."""
    region = resolve_region(
        request.args.get("region"),
        request.headers.get("Accept-Language"),
    )
    tier = g.get("user_tier", "free")

    # 查询真实订阅信息
    db = current_app._db
    sub = db.get_subscription(g.user_id)
    expires_at = sub["expires_at"] if sub else None
    sub_status = sub["status"] if sub else ("active" if tier != "free" else "inactive")

    if tier == "enterprise":
        plan = {
            "tier": "enterprise",
            "name": "企业版" if region == "CN" else "Enterprise",
            "price_monthly": 0,
            "currency": list_plans_for_region(region)["currency"],
            "region": region,
            "plan_id": f"enterprise_contact_{region.lower()}",
            "features": [],
            "upgradable": False,
        }
    else:
        try:
            plan = get_plan_for_tier(tier, region)
        except KeyError:
            plan = get_plan_for_tier("free", region)

    return jsonify(
        tier=tier,
        plan=plan,
        status=sub_status,
        expires_at=expires_at,
    )


@payment_bp.route("/payment/upgrade", methods=["POST"])
@require_auth
def upgrade_tier():
    """Upgrade user tier.

    - Stub mode (dev): direct tier upgrade, no payment required.
    - Production mode: **blocked** — must go through WeChat Pay / Stripe order flow.
    """
    if not _is_stub_mode():
        return jsonify(
            error="payment_required",
            message="Upgrade requires real payment. Please use POST /v1/payment/wechat/order to create a payment order.",
            hint="Set PAYMENT_STUB_MODE=true in development if you need a quick upgrade.",
        ), 402

    data = request.get_json(silent=True) or {}
    new_tier = data.get("tier")

    if new_tier not in UPGRADABLE_TIERS:
        return jsonify(error="bad_request", message="Invalid tier. Choose: supporter, pro"), 400

    current_tier = g.get("user_tier", "free")

    if TIER_ORDER.get(new_tier, 0) <= TIER_ORDER.get(current_tier, 0):
        log_product_event(
            current_app._db,
            EVENT_TRIAL_FAILED,
            user_id=g.user_id,
            platform=platform_from_request(request),
            source="server",
            success=False,
            properties={"reason": "downgrade", "current_tier": current_tier, "requested": new_tier},
        )
        return jsonify(
            error="bad_request",
            message=f"Cannot downgrade from {current_tier} to {new_tier}",
        ), 400

    db = current_app._db
    db.update_user_tier(g.user_id, new_tier)

    # 创建 Stub 订单记录（审计用）
    region = resolve_region(
        request.args.get("region") or data.get("region"),
        request.headers.get("Accept-Language"),
    )
    plan = get_plan_for_tier(new_tier, region)
    db.create_order(
        user_id=g.user_id,
        plan_id=plan["plan_id"],
        tier=new_tier,
        amount=plan["price_monthly"],
        currency=plan["currency"],
        out_trade_no=generate_out_trade_no(),
        metadata_json={"mode": "stub", "region": region},
    )

    if new_tier == "pro":
        log_product_event(
            db,
            EVENT_TRIAL_STARTED,
            user_id=g.user_id,
            platform=platform_from_request(request),
            source="server",
            properties={"from_tier": current_tier},
        )

    access_token = sign_token_for_user(db, g.user_id)
    return jsonify(
        tier=new_tier,
        plan=plan,
        status="active",
        access_token=access_token,
        token_type="bearer",
        expires_in=current_app.config["JWT_EXPIRY_HOURS"] * 3600,
        message="[STUB] Tier upgraded without real payment. Set PAYMENT_STUB_MODE=false for production.",
    )


# ============================================================
# WeChat Pay 路由
# ============================================================

@payment_bp.route("/payment/wechat/order", methods=["POST"])
@require_auth
def create_wechat_order():
    """创建 WeChat Pay 支付订单。

    根据用户环境选择支付方式：
      - PC Web：Native 支付 → 返回 qr_code_url，前端渲染二维码
      - 微信内：JSAPI 支付 → 返回 prepay_id + 签名，前端 wx.chooseWXPay

    Request body:
        { "tier": "supporter" | "pro", "trade_type": "NATIVE" | "JSAPI", "openid": "..." }

    Response:
        { "out_trade_no": "...", "prepay_id": "...", "qr_code_url": "...",
          "jsapi_params": { "appId": "...", "timeStamp": "...", ... } }
    """
    if _is_stub_mode():
        return jsonify(
            error="stub_mode",
            message="Payment stub mode is enabled. Use POST /v1/payment/upgrade for instant tier change, or set PAYMENT_STUB_MODE=false to enable real payments.",
        ), 400

    data = request.get_json(silent=True) or {}
    new_tier = data.get("tier")
    trade_type = data.get("trade_type", "NATIVE").upper()
    openid = data.get("openid", "")

    # 方案 A：JSAPI 支付时若前端未传 openid，从用户 DB 自动填充
    if trade_type == "JSAPI" and not openid:
        db = current_app._db
        user = db.get_user_by_id(g.user_id)
        if user and user.get("wechat_openid"):
            openid = user["wechat_openid"]

    if new_tier not in UPGRADABLE_TIERS:
        return jsonify(error="bad_request", message="Invalid tier. Choose: supporter, pro"), 400

    current_tier = g.get("user_tier", "free")
    if TIER_ORDER.get(new_tier, 0) <= TIER_ORDER.get(current_tier, 0):
        return jsonify(
            error="bad_request",
            message=f"Cannot downgrade from {current_tier} to {new_tier}",
        ), 400

    if new_tier not in TIER_PRICE_FEN:
        return jsonify(error="bad_request", message=f"No price configured for tier: {new_tier}"), 400

    # JSAPI 必须有关联的 openid（已从 DB 自动填充，若仍为空则报错）
    # 此检查须在凭证检查之前，否则用户会收到不准确的 503 错误
    if trade_type == "JSAPI" and not openid:
        return jsonify(
            error="openid_required",
            message="JSAPI payment requires a WeChat openid. Please ensure the user has logged in via WeChat miniprogram.",
        ), 400

    region = resolve_region(
        request.args.get("region"),
        request.headers.get("Accept-Language"),
    )
    plan = get_plan_for_tier(new_tier, region)

    # 从配置读取 WeChat Pay 凭证
    mchid = current_app.config.get("WECHAT_MCHID", "")
    appid = current_app.config.get("WECHAT_APPID", "")
    api_v3_key = current_app.config.get("WECHAT_API_V3_KEY", "")
    serial_no = current_app.config.get("WECHAT_SERIAL_NO", "")
    private_key_path = current_app.config.get("WECHAT_PRIVATE_KEY_PATH", "")
    notify_url = current_app.config.get("WECHAT_NOTIFY_URL", "")

    if not all([mchid, appid, api_v3_key, serial_no, notify_url]):
        return jsonify(
            error="payment_not_configured",
            message="WeChat Pay credentials not configured. Set WECHAT_MCHID, WECHAT_APPID, WECHAT_API_V3_KEY, WECHAT_SERIAL_NO, WECHAT_PRIVATE_KEY_PATH, WECHAT_NOTIFY_URL env vars.",
        ), 503

    amount_fen = TIER_PRICE_FEN[new_tier]
    out_trade_no = generate_out_trade_no()
    description = f"Looma {plan['name']}"

    if trade_type == "JSAPI" and openid:
        from src.payment.wechat_pay import create_jsapi_order
        result = create_jsapi_order(
            mchid=mchid, appid=appid, openid=openid,
            description=description, out_trade_no=out_trade_no,
            amount_total=amount_fen, notify_url=notify_url,
            api_v3_key=api_v3_key, serial_no=serial_no,
            private_key_path=private_key_path,
        )
        jsapi_params = {
            "appId": appid,
            "timeStamp": result.jsapi_time_stamp,
            "nonceStr": result.jsapi_nonce_str,
            "package": result.jsapi_package,
            "signType": "RSA",
            "paySign": result.jsapi_pay_sign,
        }
    else:
        # 默认 Native 支付
        result = create_native_order(
            mchid=mchid, appid=appid,
            description=description, out_trade_no=out_trade_no,
            amount_total=amount_fen, notify_url=notify_url,
            api_v3_key=api_v3_key, serial_no=serial_no,
            private_key_path=private_key_path,
        )
        jsapi_params = None

    # 写入订单表
    db = current_app._db
    order = db.create_order(
        user_id=g.user_id,
        plan_id=plan["plan_id"],
        tier=new_tier,
        amount=plan["price_monthly"],
        currency="CNY",
        out_trade_no=out_trade_no,
        prepay_id=result.prepay_id,
        qr_code_url=result.qr_code_url,
        metadata_json={
            "trade_type": trade_type,
            "region": region,
        },
    )

    resp = {
        "order_id": order["id"],
        "out_trade_no": out_trade_no,
        "prepay_id": result.prepay_id,
        "qr_code_url": result.qr_code_url,
        "amount": plan["price_monthly"],
        "currency": "CNY",
        "tier": new_tier,
    }
    if jsapi_params:
        resp["jsapi_params"] = jsapi_params

    return jsonify(**resp), 201


@payment_bp.route("/payment/wechat/notify", methods=["POST"])
def wechat_pay_notify():
    """WeChat Pay 支付结果通知回调。

    该端点由微信服务器回调，不走用户认证。
    需验证签名后才能处理业务逻辑。
    """
    body = request.get_data(as_text=True)
    signature = request.headers.get(WECHAT_SIGNATURE_HEADER, "")
    serial = request.headers.get(WECHAT_SERIAL_HEADER, "")
    timestamp = request.headers.get(WECHAT_TIMESTAMP_HEADER, "")
    nonce = request.headers.get(WECHAT_NONCE_HEADER, "")

    api_v3_key = current_app.config.get("WECHAT_API_V3_KEY", "")

    # 签名验证
    if not verify_notify_sign(
        body=body,
        signature=signature,
        serial_no=serial,
        timestamp=timestamp,
        nonce=nonce,
        api_v3_key=api_v3_key,
    ):
        current_app.logger.warning("[wechat_pay] Notify signature verification FAILED")
        resp, code = build_notify_response(False)
        return resp, code, {"Content-Type": "application/json"}

    # 解析通知体
    result = parse_notify_body(body)
    if not result.success:
        current_app.logger.warning(f"[wechat_pay] Notify parse error: {result.error}")
        resp, code = build_notify_response(False)
        return resp, code, {"Content-Type": "application/json"}

    # 处理业务逻辑：标记订单已支付 + 升级用户 tier + 创建订阅
    db = current_app._db
    order = db.get_order_by_out_trade_no(result.out_trade_no)
    if not order:
        current_app.logger.error(f"[wechat_pay] Order not found: {result.out_trade_no}")
        resp, code = build_notify_response(True)  # 返回 SUCCESS 避免微信重复通知
        return resp, code, {"Content-Type": "application/json"}

    if order["status"] == "paid":
        # 幂等：已支付的订单直接返回成功
        resp, code = build_notify_response(True)
        return resp, code, {"Content-Type": "application/json"}

    # 原子操作：标记支付 → 升级 tier → 创建订阅
    paid_order = db.mark_order_paid(result.out_trade_no, result.transaction_id)
    if not paid_order:
        resp, code = build_notify_response(True)
        return resp, code, {"Content-Type": "application/json"}

    user_id = paid_order["user_id"]
    tier = paid_order["tier"]
    plan_id = paid_order["plan_id"]

    # 升级用户 tier
    db.update_user_tier(user_id, tier)

    # 创建/更新订阅（1 个月有效期）
    from datetime import datetime, timedelta
    expires = (datetime.now() + timedelta(days=30)).isoformat()
    db.upsert_subscription(user_id, tier, plan_id, expires, auto_renew=False)

    current_app.logger.info(
        f"[wechat_pay] Payment confirmed: user={user_id} tier={tier} "
        f"txn={result.transaction_id} order={result.out_trade_no}"
    )

    resp, code = build_notify_response(True)
    return resp, code, {"Content-Type": "application/json"}


# ============================================================
# Multi-provider unified routes (overseas)
# ============================================================

def _process_payment_completed(db, out_trade_no: str, transaction_id: str,
                                provider_name: str) -> dict | None:
    """Shared webhook handler: mark order paid + upgrade tier + create subscription.

    Used by Stripe, PayPal, Airwallex, and future providers.
    Returns the paid order dict or None (idempotent skip).
    """
    order = db.get_order_by_out_trade_no(out_trade_no)
    if not order:
        current_app.logger.error(
            f"[{provider_name}] Order not found: {out_trade_no}"
        )
        return None

    if order["status"] == "paid":
        return None  # idempotent

    paid_order = db.mark_order_paid(out_trade_no, transaction_id)
    if not paid_order:
        return None

    user_id = paid_order["user_id"]
    tier = paid_order["tier"]
    plan_id = paid_order["plan_id"]

    db.update_user_tier(user_id, tier)

    from datetime import datetime, timedelta
    expires = (datetime.now() + timedelta(days=30)).isoformat()
    db.upsert_subscription(user_id, tier, plan_id, expires, auto_renew=False)

    current_app.logger.info(
        f"[{provider_name}] Payment confirmed: user={user_id} tier={tier} "
        f"order={out_trade_no} txn={transaction_id}"
    )
    return paid_order


@payment_bp.route("/payment/providers", methods=["GET"])
def list_providers():
    """List configured payment providers for the current region.

    Returns a list of providers that have valid credentials, allowing
    the frontend to show only available payment options.
    """
    region = resolve_region(
        request.args.get("region"),
        request.headers.get("Accept-Language"),
    )
    providers = list_configured_providers(current_app.config)

    return jsonify(
        region=region,
        providers=providers,
        stub_mode=_is_stub_mode(),
    )


@payment_bp.route("/payment/checkout", methods=["POST"])
@require_auth
def create_checkout():
    """Unified checkout endpoint for all overseas payment providers.

    Client specifies the desired provider and tier. Backend validates,
    creates the provider-specific checkout session, and returns a redirect URL.

    Request body:
        {
            "provider": "stripe" | "paypal" | "airwallex",
            "tier": "supporter" | "pro",
            "mode": "payment" | "subscription",    // default: "payment"
            "success_url": "https://...",            // optional override
            "cancel_url": "https://...",             // optional override
        }

    Response 201:
        {
            "order_id": "...",
            "out_trade_no": "LOOMA...",
            "provider": "stripe",
            "checkout_url": "https://...",
            "amount": 1.99,
            "currency": "USD",
            "tier": "supporter"
        }
    """
    if _is_stub_mode():
        return jsonify(
            error="stub_mode",
            message="Payment stub mode is enabled. Use POST /v1/payment/upgrade for instant tier change, or set PAYMENT_STUB_MODE=false to enable real payments.",
        ), 400

    data = request.get_json(silent=True) or {}
    provider_name = data.get("provider", "stripe").lower()
    new_tier = data.get("tier")
    mode = data.get("mode", "payment")

    if new_tier not in UPGRADABLE_TIERS:
        return jsonify(error="bad_request", message="Invalid tier. Choose: supporter, pro"), 400

    current_tier = g.get("user_tier", "free")
    if TIER_ORDER.get(new_tier, 0) <= TIER_ORDER.get(current_tier, 0):
        return jsonify(
            error="bad_request",
            message=f"Cannot downgrade from {current_tier} to {new_tier}",
        ), 400

    if new_tier not in TIER_PRICE_USD_CENTS:
        return jsonify(error="bad_request", message=f"No USD price configured for tier: {new_tier}"), 400

    # Resolve provider
    try:
        provider = get_provider(provider_name)
    except ValueError:
        return jsonify(
            error="unknown_provider",
            message=f"Unknown payment provider: {provider_name!r}. "
                    f"Available: {', '.join(list_configured_providers(current_app.config))}",
        ), 400

    if not provider.is_configured(current_app.config):
        return jsonify(
            error="payment_not_configured",
            message=f"{provider_name.title()} not configured. Set the required environment variables.",
        ), 503

    region = resolve_region(
        request.args.get("region"),
        request.headers.get("Accept-Language"),
    )
    plan = get_plan_for_tier(new_tier, region)
    amount_usd = TIER_PRICE_USD_CENTS[new_tier] / 100
    out_trade_no = stripe_generate_order_no()

    # Get user email for checkout pre-fill
    db = current_app._db
    user = db.get_user_by_id(g.user_id)
    customer_email = user.get("email", "") if user else ""

    # Build success/cancel URLs
    origin = request.headers.get("Origin", "") or request.host_url.rstrip("/")
    success_url = data.get("success_url", f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}")
    cancel_url = data.get("cancel_url", f"{origin}/payment/cancel")

    currency = current_app.config.get("STRIPE_CURRENCY", "USD")

    try:
        result: CheckoutResult = provider.create_checkout(
            config=current_app.config,
            out_trade_no=out_trade_no,
            tier=new_tier,
            amount=amount_usd,
            currency=currency,
            plan_name=f"Looma {plan['name']}",
            customer_email=customer_email,
            success_url=success_url,
            cancel_url=cancel_url,
            mode=mode,
        )
    except ValueError as e:
        current_app.logger.error(f"[{provider_name}] Checkout creation failed: {e}")
        return jsonify(error=f"{provider_name}_error", message=str(e)), 502

    # Write order to DB
    order_metadata = {
        "provider": provider_name,
        "mode": mode,
        "region": region,
    }
    if result.raw:
        order_metadata.update({f"{provider_name}_{k}": str(v) for k, v in result.raw.items()})

    order = db.create_order(
        user_id=g.user_id,
        plan_id=plan["plan_id"],
        tier=new_tier,
        amount=plan["price_monthly"],
        currency=currency,
        out_trade_no=out_trade_no,
        metadata_json=order_metadata,
    )

    return jsonify(
        order_id=order["id"],
        out_trade_no=out_trade_no,
        provider=provider_name,
        checkout_url=result.checkout_url,
        amount=plan["price_monthly"],
        currency=currency,
        tier=new_tier,
    ), 201


@payment_bp.route("/payment/webhook/<provider_name>", methods=["POST"])
def unified_webhook(provider_name: str):
    """Unified webhook endpoint for all overseas payment providers.

    Stripe:     POST /v1/payment/webhook/stripe
    PayPal:     POST /v1/payment/webhook/paypal
    Airwallex:  POST /v1/payment/webhook/airwallex

    Verifies provider-specific signature, parses event, and processes payment.
    Does NOT require auth — these endpoints are called by payment provider servers.
    """
    provider_name = provider_name.lower()

    try:
        provider = get_provider(provider_name)
    except ValueError:
        current_app.logger.warning(f"[webhook] Unknown provider: {provider_name!r}")
        return jsonify(error="unknown_provider", message=f"Unknown provider: {provider_name!r}"), 404

    if not provider.is_configured(current_app.config):
        return jsonify(error="not_configured", message=f"{provider_name} not configured"), 503

    payload = request.get_data()
    headers = dict(request.headers)

    # Verify webhook signature
    try:
        provider.verify_webhook(current_app.config, payload, headers)
    except ValueError as e:
        current_app.logger.warning(f"[{provider_name}] Webhook signature FAILED: {e}")
        return jsonify(error="invalid_signature", message=str(e)), 400

    # Parse event
    result: WebhookResult = provider.parse_webhook(payload)
    if not result.success:
        current_app.logger.warning(f"[{provider_name}] Webhook parse error: {result.error}")
        return jsonify(error="parse_error", message=result.error), 400

    db = current_app._db

    # Handle checkout.completed (one-time payment)
    if result.event_type == "checkout.completed":
        if not result.out_trade_no:
            current_app.logger.warning(f"[{provider_name}] Webhook: no out_trade_no in event")
            return jsonify(status="ok"), 200

        _process_payment_completed(db, result.out_trade_no, result.transaction_id, provider_name)

    # Handle subscription.renewed
    elif result.event_type == "subscription.renewed":
        current_app.logger.info(
            f"[{provider_name}] Subscription renewed: customer={result.customer_id} "
            f"sub={result.subscription_id}"
        )
        # TODO: extend subscription expiry by 1 month, update transaction

    # Handle subscription.cancelled
    elif result.event_type == "subscription.cancelled":
        current_app.logger.info(
            f"[{provider_name}] Subscription cancelled: customer={result.customer_id}"
        )
        # TODO: find user by customer_id, downgrade to free

    return jsonify(status="ok"), 200


# ============================================================
# Stripe routes (overseas) — backward-compatible aliases
# ============================================================

@payment_bp.route("/payment/stripe/checkout", methods=["POST"])
@require_auth
def create_stripe_checkout():
    """Create a Stripe Checkout Session for overseas payment.

    Client redirects user to the returned session_url for Stripe-hosted checkout.
    Supports card, Apple Pay, Google Pay.

    Request body:
        { "tier": "supporter" | "pro", "mode": "payment" | "subscription" }

    Response:
        { "session_id": "cs_test_xxx", "session_url": "https://checkout.stripe.com/...",
          "out_trade_no": "LOOMA..." }
    """
    if _is_stub_mode():
        return jsonify(
            error="stub_mode",
            message="Payment stub mode is enabled. Use POST /v1/payment/upgrade for instant tier change, or set PAYMENT_STUB_MODE=false to enable real payments.",
        ), 400

    data = request.get_json(silent=True) or {}
    new_tier = data.get("tier")
    mode = data.get("mode", "payment")  # payment | subscription

    if new_tier not in UPGRADABLE_TIERS:
        return jsonify(error="bad_request", message="Invalid tier. Choose: supporter, pro"), 400

    current_tier = g.get("user_tier", "free")
    if TIER_ORDER.get(new_tier, 0) <= TIER_ORDER.get(current_tier, 0):
        return jsonify(
            error="bad_request",
            message=f"Cannot downgrade from {current_tier} to {new_tier}",
        ), 400

    if new_tier not in TIER_PRICE_USD_CENTS:
        return jsonify(error="bad_request", message=f"No USD price configured for tier: {new_tier}"), 400

    stripe_key = current_app.config.get("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        return jsonify(
            error="payment_not_configured",
            message="Stripe not configured. Set STRIPE_SECRET_KEY env var.",
        ), 503

    region = resolve_region(
        request.args.get("region"),
        request.headers.get("Accept-Language"),
    )
    plan = get_plan_for_tier(new_tier, region)
    amount_cents = TIER_PRICE_USD_CENTS[new_tier]
    out_trade_no = stripe_generate_order_no()

    # Get user email for Stripe Checkout pre-fill
    db = current_app._db
    user = db.get_user_by_id(g.user_id)
    customer_email = user.get("email", "") if user else ""

    # Build success/cancel URLs from request origin or config
    origin = request.headers.get("Origin", "") or request.host_url.rstrip("/")
    success_url = data.get("success_url", f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}")
    cancel_url = data.get("cancel_url", f"{origin}/payment/cancel")

    try:
        result = stripe_create_checkout(
            secret_key=stripe_key,
            out_trade_no=out_trade_no,
            tier=new_tier,
            amount_cents=amount_cents,
            currency=current_app.config.get("STRIPE_CURRENCY", "USD"),
            plan_name=f"Looma {plan['name']}",
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=customer_email,
            mode=mode,
        )
    except ValueError as e:
        current_app.logger.error(f"[stripe] Checkout creation failed: {e}")
        return jsonify(error="stripe_error", message=str(e)), 502

    # Write order to DB
    order = db.create_order(
        user_id=g.user_id,
        plan_id=plan["plan_id"],
        tier=new_tier,
        amount=plan["price_monthly"],
        currency="USD",
        out_trade_no=out_trade_no,
        metadata_json={
            "provider": "stripe",
            "stripe_session_id": result.session_id,
            "mode": mode,
            "region": region,
        },
    )

    return jsonify(
        order_id=order["id"],
        session_id=result.session_id,
        session_url=result.session_url,
        out_trade_no=out_trade_no,
        amount=plan["price_monthly"],
        currency="USD",
        tier=new_tier,
    ), 201


@payment_bp.route("/payment/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """Stripe webhook endpoint.

    Receives events from Stripe (checkout.session.completed, invoice.paid, etc.)
    Verifies signature, processes payment, upgrades user tier.

    This endpoint does NOT require auth — it's called by Stripe servers.
    """
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET", "")

    # Verify webhook signature
    try:
        stripe_verify_webhook(payload, sig_header, webhook_secret)
    except ValueError as e:
        current_app.logger.warning(f"[stripe] Webhook signature verification FAILED: {e}")
        return jsonify(error="invalid_signature"), 400

    # Parse event
    result = stripe_parse_webhook(payload)
    if not result.success:
        current_app.logger.warning(f"[stripe] Webhook parse error: {result.error}")
        return jsonify(error="parse_error"), 400

    db = current_app._db

    # Handle different event types
    if result.event_type == "checkout.session.completed":
        # One-time payment completed
        if not result.out_trade_no:
            current_app.logger.warning("[stripe] Webhook: no out_trade_no in event")
            return jsonify(status="ok"), 200

        order = db.get_order_by_out_trade_no(result.out_trade_no)
        if not order:
            current_app.logger.error(f"[stripe] Order not found: {result.out_trade_no}")
            return jsonify(status="ok"), 200

        # Idempotency: skip if already paid
        if order["status"] == "paid":
            return jsonify(status="ok"), 200

        # Mark paid + upgrade tier + create subscription
        paid_order = db.mark_order_paid(result.out_trade_no, result.customer_id)
        if not paid_order:
            return jsonify(status="ok"), 200

        user_id = paid_order["user_id"]
        tier = paid_order["tier"]
        plan_id = paid_order["plan_id"]

        db.update_user_tier(user_id, tier)

        from datetime import datetime, timedelta
        expires = (datetime.now() + timedelta(days=30)).isoformat()
        db.upsert_subscription(user_id, tier, plan_id, expires, auto_renew=False)

        current_app.logger.info(
            f"[stripe] Payment confirmed: user={user_id} tier={tier} "
            f"order={result.out_trade_no} session={result.customer_id}"
        )

    elif result.event_type == "invoice.paid":
        # Subscription recurring payment
        current_app.logger.info(
            f"[stripe] Subscription renewed: customer={result.customer_id} "
            f"sub={result.subscription_id}"
        )
        # TODO: extend subscription expiry by 1 month

    elif result.event_type == "customer.subscription.deleted":
        # Subscription cancelled — downgrade to free
        current_app.logger.info(
            f"[stripe] Subscription cancelled: customer={result.customer_id}"
        )
        # TODO: find user by stripe customer_id, downgrade to free

    return jsonify(status="ok"), 200

