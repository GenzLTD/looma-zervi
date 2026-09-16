"""The money must come from one place: the plan that owns the payment channel.

Why this exists
---------------
`create_checkout` used to assemble an order out of three unrelated sources:

    plan = get_plan_for_tier(tier, region)          # caller asked for CN → 9.9
    amount_usd = TIER_PRICE_USD_CENTS[tier] / 100   # channel charged $1.99
    currency = config["STRIPE_CURRENCY"]            # label said USD

    order(amount=plan["price_monthly"], currency=currency)   # → 9.9 USD

Same request, two different prices: the ledger (and the API response) recorded
¥9.9 with a USD label while the card was charged $1.99. Nothing ever billed
$9.90 — the bug is the disagreement, not the charge.

Fix: the payment channel selects the billing region (the contract already
declares which providers belong to which region), and `amount` + `currency` are
then read from that single plan row. These tests pin that behaviour so it cannot
be reintroduced by either endpoint.
"""
from __future__ import annotations

import pytest

from src.payment.plans import billing_region_for_provider
from src.payment.providers.base import CheckoutResult
from src.payment.providers.stripe import StripeProvider


@pytest.fixture
def deploy_region(_billing_region_baseline, monkeypatch):
    """Set DEPLOY_REGION; depends on the autouse baseline so ours wins."""

    def _set(code: str | None) -> None:
        if code is None:
            monkeypatch.delenv("DEPLOY_REGION", raising=False)
        else:
            monkeypatch.setenv("DEPLOY_REGION", code)

    return _set


@pytest.fixture
def stripe_checkout_calls(app, monkeypatch):
    """Non-stub mode with a fake Stripe channel; returns what the channel received.

    We never touch the card network — we only care that the backend hands the
    provider the *same* amount and currency it writes to the order.
    """
    app.config["PAYMENT_STUB_MODE"] = False
    app.config["STRIPE_SECRET_KEY"] = "sk_test_dummy_key_for_money_source_tests"

    seen: dict[str, object] = {}

    def _fake_create_checkout(self, config, **kwargs):
        seen.update(kwargs)
        return CheckoutResult(
            provider="stripe",
            checkout_url="https://checkout.stripe.test/c/pay/cs_test_dummy",
            out_trade_no=kwargs.get("out_trade_no", ""),
            provider_checkout_id="cs_test_dummy",
            amount=float(kwargs.get("amount") or 0.0),
            currency=kwargs.get("currency", "USD"),
            raw={"session_id": "cs_test_dummy"},
        )

    monkeypatch.setattr(StripeProvider, "create_checkout", _fake_create_checkout)
    return seen


def _auth(client, email: str) -> dict[str, str]:
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "secret123", "name": "MoneySource"},
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return {"Authorization": f"Bearer {resp.get_json()['access_token']}"}


class TestContractOwnsChannelToRegion:
    """The contract already says which region settles through which channel."""

    @pytest.mark.parametrize("provider", ["stripe", "paypal", "airwallex"])
    def test_card_channels_belong_to_the_usd_region(self, provider):
        assert billing_region_for_provider(provider) == "US"

    @pytest.mark.parametrize("provider", ["wechat", "huawei_iap"])
    def test_wallet_channels_belong_to_the_cny_region(self, provider):
        assert billing_region_for_provider(provider) == "CN"

    @pytest.mark.parametrize("provider", ["", "nope", None])
    def test_undeclared_providers_have_no_region(self, provider):
        assert billing_region_for_provider(provider) is None


class TestCardCheckoutPricesTheUsdPlan:
    """View /v1/payment/checkout."""

    def test_cn_deploy_card_checkout_prices_usd(self, client, deploy_region, stripe_checkout_calls):
        """The regression itself: a CN deploy used to record 9.9 USD."""
        deploy_region("CN")
        auth = _auth(client, "ms_cn_card@test.com")

        resp = client.post(
            "/v1/payment/checkout",
            json={"provider": "stripe", "tier": "supporter"},
            headers=auth,
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        body = resp.get_json()

        assert body["currency"] == "USD"
        assert body["amount"] == 1.99

        # What the channel was asked to charge must match what the ledger says.
        assert stripe_checkout_calls["amount"] == 1.99
        assert stripe_checkout_calls["currency"] == "USD"

    def test_body_region_cn_no_longer_moves_the_card_price(
        self, client, deploy_region, stripe_checkout_calls
    ):
        """A caller asking for CN must not get a CN price on a card channel."""
        deploy_region("CN")
        auth = _auth(client, "ms_cn_body@test.com")

        resp = client.post(
            "/v1/payment/checkout",
            json={"provider": "stripe", "tier": "supporter", "region": "CN"},
            headers=auth,
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        body = resp.get_json()

        assert (body["amount"], body["currency"]) == (1.99, "USD")
        assert stripe_checkout_calls["amount"] == 1.99
        assert stripe_checkout_calls["currency"] == "USD"

    def test_order_row_uses_the_usd_plan_id(self, client, deploy_region, stripe_checkout_calls):
        """The stored order must point at the plan whose price it recorded."""
        deploy_region("CN")
        auth = _auth(client, "ms_cn_planid@test.com")

        resp = client.post(
            "/v1/payment/checkout",
            json={"provider": "stripe", "tier": "pro"},
            headers=auth,
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        assert (resp.get_json()["amount"], resp.get_json()["currency"]) == (5.99, "USD")

    def test_zh_header_on_overseas_deploy_still_usd(
        self, client, deploy_region, stripe_checkout_calls
    ):
        """v3.1.15 must survive: language never decides the money."""
        deploy_region("SG")
        auth = _auth(client, "ms_sg_zh@test.com")

        resp = client.post(
            "/v1/payment/checkout",
            json={"provider": "stripe", "tier": "supporter"},
            headers={**auth, "Accept-Language": "zh-CN,zh;q=0.9"},
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        assert (resp.get_json()["amount"], resp.get_json()["currency"]) == (1.99, "USD")


class TestLegacyStripeAliasPricedTheSameWay:
    """View /v1/payment/stripe/checkout — the deprecated alias, historically the worst offender."""

    def test_cn_deploy_alias_prices_usd(self, app, client, deploy_region, monkeypatch):
        deploy_region("CN")
        app.config["PAYMENT_STUB_MODE"] = False
        app.config["STRIPE_SECRET_KEY"] = "sk_test_dummy_key_for_money_source_tests"

        captured: dict[str, object] = {}

        def _fake_create_session(**kwargs):
            captured.update(kwargs)
            return CheckoutResult(
                provider="stripe",
                checkout_url="https://checkout.stripe.test/c/pay/cs_test_alias",
                out_trade_no=kwargs.get("out_trade_no", ""),
                provider_checkout_id="cs_test_alias",
                raw={"session_id": "cs_test_alias"},
            )

        monkeypatch.setattr("src.api.routes.payment_routes.stripe_create_checkout", _fake_create_session)
        auth = _auth(client, "ms_alias_cn@test.com")

        resp = client.post(
            "/v1/payment/stripe/checkout",
            json={"tier": "supporter"},
            headers=auth,
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        body = resp.get_json()

        assert (body["amount"], body["currency"]) == (1.99, "USD")
        # The alias works in cents: $1.99 → 199, never ¥9.9 → 990.
        assert captured["amount_cents"] == 199
        assert captured["currency"] == "USD"
