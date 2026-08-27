"""
Airwallex payment provider — implements BaseProvider interface.

Uses Airwallex REST API v1 (Payment Intents).
Auth: API Key + Client Key → Bearer token.

Required env vars:
  - AIRWALLEX_API_KEY       API access key
  - AIRWALLEX_CLIENT_KEY    Client secret key
  - AIRWALLEX_MODE           "demo" (default) or "production"
  - AIRWALLEX_WEBHOOK_SECRET HMAC secret for webhook verification

Reference: https://www.airwallex.com/docs/api/
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import requests

from src.payment.providers.base import BaseProvider, CheckoutResult, WebhookResult

_AIRWALLEX_DEMO = "https://api-demo.airwallex.com"
_AIRWALLEX_PROD = "https://api.airwallex.com"

# Token cache
_awx_token: dict[str, Any] = {"token": "", "expires_at": 0}


class AirwallexProvider(BaseProvider):
    provider_name = "airwallex"

    # ── Configuration ──────────────────────────────────────

    def is_configured(self, config: dict[str, Any]) -> bool:
        return bool(
            config.get("AIRWALLEX_API_KEY", "")
            and config.get("AIRWALLEX_CLIENT_KEY", "")
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
        token = self._get_token(config)
        amount_cents = int(round(amount * 100))

        body = {
            "amount": amount_cents,
            "currency": currency.upper(),
            "merchant_order_id": out_trade_no,
            "request_id": out_trade_no,
            "return_url": success_url or cancel_url,
            "order": {
                "products": [{
                    "name": plan_name,
                    "quantity": 1,
                    "unit_price": amount_cents,
                    "currency": currency.upper(),
                }],
            },
            "descriptor": plan_name,
            "metadata": {
                "out_trade_no": out_trade_no,
                "tier": tier,
                "mode": mode,
                **(metadata or {}),
            },
        }

        if customer_email:
            body["payer"] = {"email": customer_email}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        resp = requests.post(
            f"{base_url}/api/v1/pa/payment_intents/create",
            json=body, headers=headers, timeout=15,
        )

        if resp.status_code >= 400:
            raise ValueError(f"Airwallex API error {resp.status_code}: {resp.text}")

        data = resp.json()

        # Airwallex returns a client_secret for frontend Elements SDK
        # and a payment_intent id. For redirect-based flow, use the hosted page.
        intent_id = data.get("id", "")
        client_secret = data.get("client_secret", "")

        # Build checkout URL — Airwallex hosted payment page
        checkout_url = data.get("url", "")
        if not checkout_url:
            # Fallback: construct hosted page URL
            env = "demo" if self._is_demo(config) else "prod"
            checkout_url = f"https://checkout.airwallex.com/{intent_id}?env={env}"

        return CheckoutResult(
            provider="airwallex",
            checkout_url=checkout_url,
            out_trade_no=out_trade_no,
            provider_checkout_id=intent_id,
            amount=amount,
            currency=currency.upper(),
            raw={
                "airwallex_intent_id": intent_id,
                "client_secret": client_secret,
            },
        )

    # ── Webhook ────────────────────────────────────────────

    def verify_webhook(
        self,
        config: dict[str, Any],
        payload: bytes,
        headers: dict[str, str],
    ) -> bool:
        webhook_secret = config.get("AIRWALLEX_WEBHOOK_SECRET", "")
        if not webhook_secret:
            return True  # dev mode: skip verification

        sig_header = headers.get("X-Airwallex-Signature", "")
        if not sig_header:
            raise ValueError("Missing Airwallex signature header")

        # Airwallex uses HMAC-SHA256 with timestamp
        timestamp = headers.get("X-Airwallex-Timestamp", "")
        expected = hmac.new(
            webhook_secret.encode("utf-8"),
            f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, sig_header):
            raise ValueError("Airwallex webhook signature verification failed")

        # Check timestamp tolerance (5 minutes)
        try:
            if abs(time.time() - int(timestamp)) > 300:
                raise ValueError("Airwallex webhook timestamp outside tolerance")
        except (ValueError, TypeError):
            raise ValueError("Invalid Airwallex timestamp")

        return True

    def parse_webhook(self, payload: bytes) -> WebhookResult:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return WebhookResult(success=False, provider="airwallex", error="Invalid JSON")

        event_type = event.get("name", "") or event.get("type", "")
        data = event.get("data", {}) or {}
        obj = data.get("object", {}) or {}

        if event_type in ("payment_intent.succeeded", "payment_intent.captured"):
            metadata = obj.get("metadata", {}) or {}
            amount_main = obj.get("amount", 0)
            return WebhookResult(
                success=True,
                provider="airwallex",
                event_type="checkout.completed",
                out_trade_no=metadata.get("out_trade_no", "") or obj.get("merchant_order_id", ""),
                transaction_id=obj.get("id", ""),
                customer_id=obj.get("customer_id", ""),
                amount_total=amount_main,
                currency=(obj.get("currency", "USD") or "USD").upper(),
                tier=metadata.get("tier", ""),
                raw=event,
            )

        elif event_type in ("payment_intent.processing", "payment_intent.requires_capture"):
            return WebhookResult(
                success=True,
                provider="airwallex",
                event_type=event_type,
                raw=event,
            )

        elif event_type == "payment_intent.cancelled":
            return WebhookResult(
                success=True,
                provider="airwallex",
                event_type="payment_intent.cancelled",
                out_trade_no=obj.get("merchant_order_id", ""),
                raw=event,
            )

        elif event_type == "payment_intent.failed":
            return WebhookResult(
                success=False,
                provider="airwallex",
                event_type="payment_intent.failed",
                error=obj.get("failure_reason", "payment_failed"),
                raw=event,
            )

        return WebhookResult(
            success=True,
            provider="airwallex",
            event_type=event_type,
            raw=event,
        )

    # ── Auth ───────────────────────────────────────────────

    def _get_token(self, config: dict[str, Any]) -> str:
        global _awx_token
        now = time.time()
        if _awx_token["token"] and _awx_token["expires_at"] > now + 60:
            return _awx_token["token"]

        api_key = config.get("AIRWALLEX_API_KEY", "")
        client_key = config.get("AIRWALLEX_CLIENT_KEY", "")
        base_url = self._base_url(config)

        headers = {
            "x-api-key": api_key,
            "x-client-key": client_key,
            "Content-Type": "application/json",
        }

        resp = requests.post(
            f"{base_url}/api/v1/authentication/login",
            headers=headers,
            timeout=10,
        )

        if resp.status_code >= 400:
            raise ValueError(f"Airwallex auth error {resp.status_code}: {resp.text}")

        data = resp.json()
        _awx_token = {
            "token": data.get("token", ""),
            "expires_at": now + data.get("expires_in", 1800),
        }
        return _awx_token["token"]

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _is_demo(config: dict[str, Any]) -> bool:
        return config.get("AIRWALLEX_MODE", "demo") != "production"

    @staticmethod
    def _base_url(config: dict[str, Any]) -> str:
        return _AIRWALLEX_PROD if config.get("AIRWALLEX_MODE") == "production" else _AIRWALLEX_DEMO
