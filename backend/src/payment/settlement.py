"""统一支付结算路径 —— 供 payment 与 membership 两套路由共用。

职责：查单 → 幂等校验 → mark_order_paid → update_user_tier →
upsert_subscription(+30天)。抽此函数避免两处结算逻辑漂移：
payment webhook 与 membership webhook 必须走同一核销路径。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from src.identity.ledger_subject import (
    AmbiguousLedgerSubject,
    ensure_principal_sub,
    resolve_settlement_user_id,
)

logger = logging.getLogger(__name__)


def _remember_provider_refs(
    db: Any,
    order_id: str,
    customer_id: str,
    subscription_id: str,
) -> None:
    """在订单上留痕 Stripe 侧的 customer / subscription id。

    生命周期事件（invoice.paid / customer.subscription.deleted）只带这些 id，
    不带我们的 out_trade_no；留痕后即可反查用户，无需依赖邮箱猜测。
    """
    extra: dict[str, str] = {}
    if customer_id:
        extra["stripe_customer_id"] = customer_id
    if subscription_id:
        extra["stripe_subscription_id"] = subscription_id
    if not extra:
        return
    merge = getattr(db, "merge_order_metadata", None)
    if merge is None:
        return
    try:
        merge(order_id, extra)
    except Exception:  # 记账失败绝不能阻断结算主链路
        logger.warning(
            "[settlement] failed to record provider refs for order=%s", order_id,
            exc_info=True,
        )


def settle_payment(
    db: Any,
    out_trade_no: str,
    transaction_id: str,
    provider_name: str,
    customer_id: str = "",
    subscription_id: str = "",
) -> dict | None:
    """Settle a completed payment: mark paid + upgrade tier + create subscription.

    Shared by Stripe / WeChat / PayPal webhooks and the membership webhook.
    Returns the paid order dict, or None on idempotent skip / not-found.
    """
    order = db.get_order_by_out_trade_no(out_trade_no)
    if not order:
        logger.error("[%s] Order not found: %s", provider_name, out_trade_no)
        return None

    if order["status"] == "paid":
        # 幂等：Stripe 会重投同一 session.completed。不重复发货，
        # 但仍补齐 provider 侧 id（老订单在本次改动前没有留痕）。
        _remember_provider_refs(db, order["id"], customer_id, subscription_id)
        return None

    try:
        user_id = resolve_settlement_user_id(
            db, order_user_id=order["user_id"]
        )
    except AmbiguousLedgerSubject as exc:
        logger.error(
            "[%s] Ambiguous ledger subject for %s: %s",
            provider_name, out_trade_no, exc,
        )
        return None

    paid_order = db.mark_order_paid(out_trade_no, transaction_id)
    if not paid_order:
        return None

    _remember_provider_refs(db, paid_order["id"], customer_id, subscription_id)

    tier = paid_order["tier"]
    plan_id = paid_order["plan_id"]

    expires = (datetime.now() + timedelta(days=30)).isoformat()
    # 带 subscription_id 说明是真实 Stripe Subscription（会自动续费）；
    # 一次性付款不是。
    db.upsert_subscription(
        user_id, tier, plan_id, expires, auto_renew=bool(subscription_id),
    )

    # tier 不再由本轨直写 —— 交给 entitlement 仲裁：
    #   tier = max(两条轨上所有未过期订阅的 tier)
    # 旧代码在这里 `db.update_user_tier(user_id, tier)`（last-write-wins），
    # 会把用户在另一条轨（Apple IAP）上**档位更高且仍有效**的订阅反向拉低。
    granted = db.recompute_user_tier(user_id)
    logger.info(
        "[%s] settled user=%s principal_sub=%s tier=%s order=%s",
        provider_name, user_id, ensure_principal_sub(db, user_id), granted, out_trade_no,
    )

    logger.info(
        "[%s] Payment confirmed: user=%s order_tier=%s granted_tier=%s order=%s txn=%s sub=%s",
        provider_name, user_id, tier, granted, out_trade_no, transaction_id,
        subscription_id or "-",
    )
    _record_payment_event(db, user_id, tier, out_trade_no, paid_order)
    return paid_order


def _record_payment_event(
    db: Any,
    user_id: str,
    tier: str,
    out_trade_no: str,
    order: dict,
) -> None:
    """服务端记一笔 payment_succeeded。

    漏斗终点必须由服务端产生 —— 前端上报的「付款成功」不可信（可伪造），
    而这里是唯一「钱确实到账」的地方。
    """
    log_event = getattr(db, "log_product_event", None)
    if log_event is None:
        return
    try:
        log_event(
            event_name="payment_succeeded",
            user_id=user_id,
            platform="tspace_web",
            source="server",
            success=True,
            properties={
                "tier": tier,
                "out_trade_no": out_trade_no,
                "amount": order.get("amount"),
                "currency": order.get("currency"),
            },
        )
    except Exception:  # 埋点失败绝不能影响结算结果
        logger.warning(
            "[settlement] failed to record payment_succeeded: order=%s",
            out_trade_no, exc_info=True,
        )
