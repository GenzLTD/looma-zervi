"""
PayPal payment provider — implements BaseProvider interface.

Uses PayPal REST API v2 (Orders + Subscriptions).
Auth: OAuth2 client_credentials grant.

Required env vars:
  - PAYPAL_CLIENT_ID       PayPal app client ID
  - PAYPAL_CLIENT_SECRET   PayPal app secret
  - PAYPAL_MODE            "sandbox" (default) or "live"

Reference: https://developer.paypal.com/docs/api/orders/v2/
"""
from __future__ import annotations

import json
import time
from typing import Any

import requests

from src.payment.providers.base import BaseProvider, CheckoutResult, WebhookResult

# PayPal API bases
_PAYPAL_SANDBOX = "https://api-m.sandbox.paypal.com"
_PAYPAL_LIVE = "https://api-m.paypal.com"

# Token cache (in-memory, per-process)
_token_cache: dict[str, Any] = {"access_token": "", "expires_at": 0}


class PayPalProvider(BaseProvider):
    provider_name = "paypal"

    # ── Configuration ──────────────────────────────────────

    def is_configured(self, config: dict[str, Any]) -> bool:
        return bool(
            config.get("PAYPAL_CLIENT_ID", "")
            and config.get("PAYPAL_CLIENT_SECRET", "")
        )

    # ── Checkout ───────────────────────────────────────────

    def create_checkout(
        self,
        config: dict[str, Any],
        out_trade_no: str,
        tier: str,
        amount: float,
        currency: str = "USD",
        plan_name: str = "Looma Plan",
        customer_email: str = "",
        success_url: str = "",
        cancel_url: str = "",
        mode: str = "payment",
        metadata: dict[str, Any] | None = None,
    ) -> CheckoutResult:
        base_url = self._base_url(config)
        access_token = self._get_access_token(config)

        if mode == "subscription":
            return self._create_subscription_checkout(
                base_url, access_token, out_trade_no, tier,
                amount, currency, plan_name, success_url, cancel_url,
            )

        # One-time payment: Orders API v2
        amount_str = f"{amount:.2f}"
        body = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": out_trade_no,
                "description": plan_name,
                "amount": {
                    "currency_code": currency.upper(),
                    "value": amount_str,
                },
                "custom_id": out_trade_no,
            }],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
                        "landing_page": "LOGIN",
                        "user_action": "PAY_NOW",
                        "return_url": success_url,
                        "cancel_url": cancel_url,
                    }
                }
            },
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": out_trade_no,
        }

        resp = requests.post(
            f"{base_url}/v2/checkout/orders",
            json=body,
            headers=headers,
            timeout=15,
        )

        if resp.status_code >= 400:
            raise ValueError(f"PayPal API error {resp.status_code}: {resp.text}")

        data = resp.json()
        order_id = data.get("id", "")

        # Find the approval URL for redirect
        approve_url = ""
        for link in data.get("links", []):
            if link.get("rel") == "payer-action":
                approve_url = link.get("href", "")
                break
        # Fallback: use generic checkout URL
        if not approve_url:
            approve_url = f"https://www.{'sandbox.' if self._is_sandbox(config) else ''}paypal.com/checkoutnow?token={order_id}"

        return CheckoutResult(
            provider="paypal",
            checkout_url=approve_url,
            out_trade_no=out_trade_no,
            provider_checkout_id=order_id,
            amount=amount,
            currency=currency.upper(),
            raw={"paypal_order_id": order_id},
        )

    def _create_subscription_checkout(
        self, base_url, access_token, out_trade_no, tier,
        amount, currency, plan_name, success_url, cancel_url,
    ) -> CheckoutResult:
        """Create a PayPal Subscription plan + subscription for recurring payments."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": f"plan-{out_trade_no}",
        }

        amount_str = f"{amount:.2f}"

        # Step 1: Create product
        product_body = {
            "name": f"Looma {tier.title()}",
            "description": plan_name,
            "type": "SERVICE",
            "category": "SOFTWARE",
        }
        product_resp = requests.post(
            f"{base_url}/v1/catalogs/products",
            json=product_body, headers=headers, timeout=15,
        )
        if product_resp.status_code >= 400:
            raise ValueError(f"PayPal product creation error {product_resp.status_code}: {product_resp.text}")
        product_id = product_resp.json().get("id", "")

        # Step 2: Create billing plan
        headers["PayPal-Request-Id"] = f"sub-{out_trade_no}"
        plan_body = {
            "product_id": product_id,
            "name": f"Looma {tier.title()} Monthly",
            "status": "ACTIVE",
            "billing_cycles": [{
                "frequency": {"interval_unit": "MONTH", "interval_count": 1},
                "tenure_type": "REGULAR",
                "sequence": 1,
                "total_cycles": 0,  # infinite
                "pricing_scheme": {
                    "fixed_price": {
                        "value": amount_str,
                        "currency_code": currency.upper(),
                    }
                },
            }],
            "payment_preferences": {
                "auto_bill_outstanding": True,
                "payment_failure_threshold": 3,
            },
        }
        plan_resp = requests.post(
            f"{base_url}/v1/billing/plans",
            json=plan_body, headers=headers, timeout=15,
        )
        if plan_resp.status_code >= 400:
            raise ValueError(f"PayPal plan creation error {plan_resp.status_code}: {plan_resp.text}")
        plan_id = plan_resp.json().get("id", "")

        # Step 3: Create subscription
        headers["PayPal-Request-Id"] = out_trade_no
        sub_body = {
            "plan_id": plan_id,
            "custom_id": out_trade_no,
            "application_context": {
                "return_url": success_url,
                "cancel_url": cancel_url,
                "user_action": "SUBSCRIBE_NOW",
            },
        }
        sub_resp = requests.post(
            f"{base_url}/v1/billing/subscriptions",
            json=sub_body, headers=headers, timeout=15,
        )
        if sub_resp.status_code >= 400:
            raise ValueError(f"PayPal subscription creation error {sub_resp.status_code}: {sub_resp.text}")

        sub_data = sub_resp.json()
        sub_id = sub_data.get("id", "")
        approve_url = ""
        for link in sub_data.get("links", []):
            if link.get("rel") == "approve":
                approve_url = link.get("href", "")
                break

        return CheckoutResult(
            provider="paypal",
            checkout_url=approve_url,
            out_trade_no=out_trade_no,
            provider_checkout_id=sub_id,
            amount=amount,
            currency=currency.upper(),
            raw={
                "paypal_subscription_id": sub_id,
                "paypal_plan_id": plan_id,
                "mode": "subscription",
            },
        )

    # ── Webhook ────────────────────────────────────────────

    def verify_webhook(
        self,
        config: dict[str, Any],
        payload: bytes,
        headers: dict[str, str],
    ) -> bool:
        webhook_id = config.get("PAYPAL_WEBHOOK_ID", "")
        if not webhook_id:
            return True  # dev mode: skip verification

        base_url = self._base_url(config)
        access_token = self._get_access_token(config)

        # Verify webhook signature via PayPal API
        verify_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        verify_body = {
            "auth_algo": headers.get("PAYPAL-AUTH-ALGO", ""),
            "cert_url": headers.get("PAYPAL-CERT-URL", ""),
            "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID", ""),
            "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG", ""),
            "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME", ""),
            "webhook_id": webhook_id,
            "webhook_event": json.loads(payload),
        }

        resp = requests.post(
            f"{base_url}/v1/notifications/verify-webhook-signature",
            json=verify_body, headers=verify_headers, timeout=10,
        )

        if resp.status_code >= 400:
            raise ValueError(f"PayPal webhook verification error: {resp.text}")

        result = resp.json()
        if result.get("verification_status") != "SUCCESS":
            raise ValueError("PayPal webhook signature verification failed")

        return True

    def parse_webhook(self, payload: bytes) -> WebhookResult:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return WebhookResult(success=False, provider="paypal", error="Invalid JSON")

        event_type = event.get("event_type", "")
        resource = event.get("resource", {})

        if event_type == "CHECKOUT.ORDER.APPROVED":
            return WebhookResult(
                success=True,
                provider="paypal",
                event_type="checkout.completed",
                out_trade_no=self._extract_reference(resource),
                transaction_id=resource.get("id", ""),
                amount_total=self._extract_amount_cents(resource),
                currency=self._extract_currency(resource),
                raw=event,
            )

        elif event_type == "PAYMENT.CAPTURE.COMPLETED":
            return WebhookResult(
                success=True,
                provider="paypal",
                event_type="checkout.completed",
                out_trade_no=self._extract_reference(resource),
                transaction_id=resource.get("id", ""),
                amount_total=self._extract_amount_cents(resource),
                currency=self._extract_currency(resource),
                raw=event,
            )

        elif event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
            return WebhookResult(
                success=True,
                provider="paypal",
                event_type="checkout.completed",
                out_trade_no=resource.get("custom_id", ""),
                subscription_id=resource.get("id", ""),
                amount_total=int(round(
                    float(resource.get("billing_info", {}).get("last_payment", {}).get("amount", {}).get("value", 0)) * 100
                )),
                raw=event,
            )

        elif event_type == "BILLING.SUBSCRIPTION.PAYMENT.COMPLETED":
            return WebhookResult(
                success=True,
                provider="paypal",
                event_type="subscription.renewed",
                out_trade_no=resource.get("custom_id", ""),
                subscription_id=resource.get("id", ""),
                raw=event,
            )

        elif event_type == "BILLING.SUBSCRIPTION.CANCELLED":
            return WebhookResult(
                success=True,
                provider="paypal",
                event_type="subscription.cancelled",
                out_trade_no=resource.get("custom_id", ""),
                subscription_id=resource.get("id", ""),
                raw=event,
            )

        return WebhookResult(
            success=True,
            provider="paypal",
            event_type=event_type,
            raw=event,
        )

    # ── Auth ───────────────────────────────────────────────

    def _get_access_token(self, config: dict[str, Any]) -> str:
        global _token_cache
        now = time.time()
        if _token_cache["access_token"] and _token_cache["expires_at"] > now + 60:
            return _token_cache["access_token"]

        client_id = config.get("PAYPAL_CLIENT_ID", "")
        client_secret = config.get("PAYPAL_CLIENT_SECRET", "")
        base_url = self._base_url(config)

        resp = requests.post(
            f"{base_url}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            headers={"Accept": "application/json"},
            timeout=10,
        )

        if resp.status_code >= 400:
            raise ValueError(f"PayPal auth error {resp.status_code}: {resp.text}")

        data = resp.json()
        _token_cache = {
            "access_token": data.get("access_token", ""),
            "expires_at": now + data.get("expires_in", 3600),
        }
        return _token_cache["access_token"]

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _is_sandbox(config: dict[str, Any]) -> bool:
        return config.get("PAYPAL_MODE", "sandbox") != "live"

    @staticmethod
    def _base_url(config: dict[str, Any]) -> str:
        return _PAYPAL_LIVE if config.get("PAYPAL_MODE") == "live" else _PAYPAL_SANDBOX

    @staticmethod
    def _extract_reference(resource: dict) -> str:
        # Orders v2: purchase_units[0].custom_id or reference_id
        units = resource.get("purchase_units", [])
        if units:
            return units[0].get("custom_id", "") or units[0].get("reference_id", "")
        return resource.get("custom_id", "")

    @staticmethod
    def _extract_amount_cents(resource: dict) -> int:
        try:
            amount_obj = resource.get("amount", {})
            value = float(amount_obj.get("value", 0))
            return int(round(value * 100))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _extract_currency(resource: dict) -> str:
        return (resource.get("amount", {}).get("currency_code", "USD") or "USD").upper()
