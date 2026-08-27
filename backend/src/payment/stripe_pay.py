"""
Backward-compatible re-exports from the new StripeProvider.

This module is kept for existing code that imports from
``src.payment.stripe_pay`` directly.  New code should use::

    from src.payment.providers.stripe import StripeProvider

or the registry::

    from src.payment.providers import get_provider
    provider = get_provider("stripe")
"""
from __future__ import annotations

from src.payment.providers.stripe import StripeProvider as _StripeProvider

# Legacy function re-exports — these forward to the Provider instance methods.
# They exist so that existing direct imports in tests / scripts continue to work.

_provider = _StripeProvider()

# Re-export the dataclasses for backward compat
from src.payment.providers.base import CheckoutResult
# Alias for old name
StripeCheckoutResult = CheckoutResult

from src.payment.providers.base import WebhookResult
StripeWebhookResult = WebhookResult


def create_checkout_session(
    secret_key: str,
    out_trade_no: str,
    tier: str,
    amount_cents: int,
    currency: str = "USD",
    plan_name: str = "Looma Supporter",
    success_url: str = "",
    cancel_url: str = "",
    customer_email: str = "",
    mode: str = "payment",
    price_id: str = "",
) -> CheckoutResult:
    """Legacy wrapper — delegates to StripeProvider.create_checkout()."""
    metadata = {}
    if price_id:
        metadata["stripe_price_id"] = price_id

    return _provider.create_checkout(
        config={"STRIPE_SECRET_KEY": secret_key},
        out_trade_no=out_trade_no,
        tier=tier,
        amount=amount_cents / 100.0,
        currency=currency,
        plan_name=plan_name,
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=customer_email,
        mode=mode,
        metadata=metadata,
    )


def verify_webhook_signature(
    payload: bytes,
    sig_header: str,
    webhook_secret: str,
    tolerance: int = 300,
) -> bool:
    """Legacy wrapper — delegates to StripeProvider.verify_webhook()."""
    return _provider.verify_webhook(
        config={"STRIPE_WEBHOOK_SECRET": webhook_secret},
        payload=payload,
        headers={"Stripe-Signature": sig_header},
    )


def parse_webhook_event(payload: bytes) -> WebhookResult:
    """Legacy wrapper — delegates to StripeProvider.parse_webhook()."""
    return _provider.parse_webhook(payload)


def generate_out_trade_no() -> str:
    """Generate unique internal order number (same format as WeChat Pay)."""
    import uuid
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = uuid.uuid4().hex[:8].upper()
    return f"LOOMA{ts}{rand}"


__all__ = [
    "StripeCheckoutResult",
    "StripeWebhookResult",
    "create_checkout_session",
    "verify_webhook_signature",
    "parse_webhook_event",
    "generate_out_trade_no",
]
