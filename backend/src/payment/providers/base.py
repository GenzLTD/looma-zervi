"""
Payment Provider Abstract Base Class.

All payment providers (Stripe, PayPal, Airwallex, WeChat Pay)
MUST implement this interface to plug into the unified checkout/webhook pipeline.

Design principle: Provider layer is pure integration — no DB access, no HTTP routing.
                     DB writes happen in payment_routes.py after provider returns result.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckoutResult:
    """Unified checkout creation result across all providers."""

    provider: str                    # "stripe" | "paypal" | "airwallex"
    checkout_url: str = ""           # URL to redirect user for payment
    out_trade_no: str = ""           # Internal order number
    provider_checkout_id: str = ""   # Provider's session/order ID (e.g., Stripe session_id)
    amount: float = 0.0
    currency: str = "USD"
    raw: dict[str, Any] = field(default_factory=dict)  # Provider-specific extras


@dataclass
class WebhookResult:
    """Unified webhook parse result across all providers."""

    success: bool
    provider: str = ""
    event_type: str = ""             # checkout.completed | subscription.renewed | subscription.cancelled
    out_trade_no: str = ""
    transaction_id: str = ""         # Provider's payment/transaction ID
    customer_id: str = ""
    subscription_id: str = ""
    amount_total: int = 0            # In minor units (cents)
    currency: str = "USD"
    tier: str = ""                   # tier from metadata (if available)
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    """Abstract payment provider interface.

    Each concrete provider (StripeProvider, PayPalProvider, AirwallexProvider)
    must implement these four methods.
    """

    # Override in subclass
    provider_name: str = "base"

    @abstractmethod
    def is_configured(self, config: dict[str, Any]) -> bool:
        """Check whether this provider has valid credentials in config.

        Returns True if all required keys exist and are non-empty.
        """
        ...

    @abstractmethod
    def create_checkout(
        self,
        config: dict[str, Any],
        out_trade_no: str,
        tier: str,
        amount: float,
        currency: str,
        plan_name: str,
        customer_email: str = "",
        success_url: str = "",
        cancel_url: str = "",
        mode: str = "payment",
        metadata: dict[str, Any] | None = None,
    ) -> CheckoutResult:
        """Create a checkout/payment session.

        Args:
            config: Flask app.config (read-only) for credentials.
            out_trade_no: Internal order number.
            tier: "supporter" | "pro"
            amount: Price in major units (e.g., 1.99 for $1.99).
            currency: ISO 4217 currency code.
            plan_name: Human-readable plan name.
            customer_email: Pre-fill customer email.
            success_url: Redirect URL after payment success.
            cancel_url: Redirect URL after payment cancel.
            mode: "payment" (one-time) or "subscription" (recurring).
            metadata: Extra key-value pairs to attach to the order.

        Returns:
            CheckoutResult with redirect_url for the client.
        """
        ...

    @abstractmethod
    def verify_webhook(
        self,
        config: dict[str, Any],
        payload: bytes,
        headers: dict[str, str],
    ) -> bool:
        """Verify webhook signature/authenticity.

        Must raise ValueError on verification failure (caught by route handler).
        Returns True if verified.
        """
        ...

    @abstractmethod
    def parse_webhook(
        self,
        payload: bytes,
    ) -> WebhookResult:
        """Parse webhook payload into a unified WebhookResult.

        Must handle the three standard event types:
        - checkout.completed   → one-time payment confirmed
        - subscription.renewed  → recurring payment
        - subscription.cancelled → subscription ended
        """
        ...
