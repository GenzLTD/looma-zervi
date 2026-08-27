"""
Payment Provider Registry.

All providers register themselves here. The payment_routes module
uses get_provider() to resolve provider by name at runtime.

Usage:
    from src.payment.providers import get_provider, list_configured_providers

    provider = get_provider("stripe")
    if provider.is_configured(app.config):
        result = provider.create_checkout(app.config, ...)
"""
from __future__ import annotations

from typing import Any

from src.payment.providers.base import BaseProvider
from src.payment.providers.stripe import StripeProvider
from src.payment.providers.paypal import PayPalProvider
from src.payment.providers.airwallex import AirwallexProvider

# ── Registry ──────────────────────────────────────────

_PROVIDERS: dict[str, BaseProvider] = {
    "stripe": StripeProvider(),
    "paypal": PayPalProvider(),
    "airwallex": AirwallexProvider(),
}


def get_provider(name: str) -> BaseProvider:
    """Resolve a payment provider by name.

    Raises ValueError if the provider name is not registered.
    """
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ValueError(
            f"Unknown payment provider: {name!r}. "
            f"Available: {', '.join(sorted(_PROVIDERS.keys()))}"
        )
    return provider


def list_configured_providers(config: dict[str, Any]) -> list[str]:
    """Return a list of provider names that are configured and ready to use."""
    return [
        name
        for name, provider in _PROVIDERS.items()
        if provider.is_configured(config)
    ]


def list_registered_providers() -> list[str]:
    """Return all registered provider names (regardless of config status)."""
    return sorted(_PROVIDERS.keys())


__all__ = [
    "get_provider",
    "list_configured_providers",
    "list_registered_providers",
    "BaseProvider",
]
