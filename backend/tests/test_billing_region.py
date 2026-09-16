"""Pin billing-region resolution: the deploy site decides currency, not the browser language.

Why this exists
---------------
`resolve_region()` used to fall through to `Accept-Language` whenever the caller
omitted an explicit `region`. On the overseas (SG) site that produced a real
pricing bug:

    Accept-Language: en-US   → US plan  → $1.99   ✅ matches the page copy
    Accept-Language: zh-CN   → CN plan  → ¥9.9 charged as $9.9   ❌ ~5x

The same tier therefore cost different amounts depending on a request header.
Now `DEPLOY_REGION=SG` forces the US plans unless the caller asks for CN
explicitly, and the frontend always sends `region` so nothing depends on that
fallback in the first place.

Runtime coverage note: these tests exercise `resolve_region()` directly (pure
function) plus static locks on the two call sites. They do **not** hit Stripe.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.api.routes import payment_routes
from src.api.routes.payment_routes import _region_from_request
from src.payment.plans import is_overseas_billing_deploy, resolve_region

REPO_ROOT = Path(__file__).resolve().parents[2]
PRICING_TSX = (
    REPO_ROOT / "frontend" / "packages" / "saas" / "src" / "features" / "pricing" / "Pricing.tsx"
)
CHECKOUT_TYPES = (
    REPO_ROOT / "frontend" / "packages" / "shared-core" / "src" / "types" / "payment.ts"
)


@pytest.fixture
def deploy_region(_billing_region_baseline, monkeypatch):
    """Set DEPLOY_REGION, including unsetting it, with automatic cleanup.

    Depends on conftest's autouse baseline so ours is applied second and the
    value set here wins, instead of relying on fixture instantiation order.
    """

    def _set(code: str | None) -> None:
        if code is None:
            monkeypatch.delenv("DEPLOY_REGION", raising=False)
        else:
            monkeypatch.setenv("DEPLOY_REGION", code)

    return _set


class TestOverseasDeployBillsUsd:
    """SG deploy bills USD no matter what the browser says."""

    def test_zh_browser_still_bills_us(self, deploy_region):
        """The exact regression: a zh-CN browser used to get the CN plan."""
        deploy_region("SG")
        assert resolve_region(None, "zh-CN,zh;q=0.9") == "US"

    def test_no_language_hint_still_bills_us(self, deploy_region):
        """API clients / curl send no Accept-Language; they must not get CN."""
        deploy_region("SG")
        assert resolve_region(None, None) == "US"

    def test_english_browser_unchanged(self, deploy_region):
        deploy_region("SG")
        assert resolve_region(None, "en-US,en;q=0.9") == "US"

    def test_explicit_cn_is_still_visible_to_the_resolver(self, deploy_region):
        """Resolver still reports CN so the HTTP gate can tell explicit from fallback.

        Overseas HTTP handlers then 403 that explicit CN (see
        TestOverseasHttpRejectsExplicitCn). Do not fold CN back to US here —
        that would hide the caller's intent and make the gate untestable.
        """
        deploy_region("SG")
        assert resolve_region("CN", "en-US,en;q=0.9") == "CN"

    def test_deploy_alias_is_case_and_space_tolerant(self, deploy_region):
        deploy_region(" sg ")
        assert resolve_region(None, "zh-CN") == "US"


class TestCnDeployKeepsLanguageBehaviour:
    """Guard the other direction — the fix must not leak into CN/on-prem."""

    def test_zh_language_maps_to_cn(self, deploy_region):
        deploy_region("CN")
        assert resolve_region(None, "zh-CN,zh;q=0.9") == "CN"

    def test_non_zh_language_maps_to_us(self, deploy_region):
        deploy_region("CN")
        assert resolve_region(None, "en-US,en;q=0.9") == "US"

    def test_missing_language_falls_back_to_cn(self, deploy_region):
        deploy_region("CN")
        assert resolve_region(None, None) == "CN"

    def test_unset_deploy_region_behaves_like_cn(self, deploy_region):
        """Local dev / ServBay: no DEPLOY_REGION set must keep the old behaviour."""
        deploy_region(None)
        assert resolve_region(None, "zh-CN,zh;q=0.9") == "CN"
        assert resolve_region(None, None) == "CN"


class TestCheckoutRequestCarriesRegion:
    """Static locks on the two call sites — do not let these regress silently."""

    def test_checkout_request_type_has_region_field(self):
        text = CHECKOUT_TYPES.read_text(encoding="utf-8")
        start = text.find("interface CheckoutRequest")
        assert start != -1, "CheckoutRequest interface missing from payment.ts"
        # Interface body ends at the closing brace before the next declaration.
        body = text[start : text.find("\n}", start)]
        assert "region" in body, (
            "CheckoutRequest lost its `region` field — the frontend can no longer "
            "declare the billing region explicitly"
        )

    def test_pricing_checkout_passes_billing_region(self):
        text = PRICING_TSX.read_text(encoding="utf-8")
        start = text.find("createPaymentApi(client).checkout(")
        assert start != -1, "Pricing.tsx no longer calls checkout()"
        block = text[start : text.find("});", start)]
        assert "region:" in block, (
            "checkout() must pass `region: BILLING_REGION`. Otherwise the backend "
            "infers the region from Accept-Language and a zh browser on the "
            "overseas site gets billed the CN plan price in USD."
        )
        assert "BILLING_REGION" in block, "region should come from BILLING_REGION, not a hardcoded string"


class TestCheckoutHonoursRegionSentInBody:
    """The SDK posts CheckoutRequest as JSON — that region must be honoured.

    Discovered on the live SG deploy: both checkout endpoints read only
    ``?region=``, so a client asking for CN in the body got priced on whatever
    the server defaulted to. Any frontend change alone is decorative while the
    endpoint ignores the body.
    """

    def test_helper_reads_region_from_json_body(self, app):
        with app.test_request_context(
            "/v1/payment/checkout", method="POST", json={"region": "CN"}
        ):
            assert _region_from_request() == "CN"

    def test_query_param_keeps_priority_over_body(self, app):
        with app.test_request_context(
            "/v1/payment/checkout?region=US", method="POST", json={"region": "CN"}
        ):
            assert _region_from_request() == "US"

    def test_no_region_anywhere_is_none(self, app):
        """None lets resolve_region fall through to its own precedence rules."""
        with app.test_request_context("/v1/payment/checkout", method="POST", json={}):
            assert _region_from_request() is None

    @pytest.mark.parametrize("view", ["create_checkout", "create_stripe_checkout"])
    def test_checkout_views_price_from_the_channel_plan(self, view):
        """Wiring lock — amount and currency must be read from one plan row.

        The caller's region is still read (the overseas CN gate needs it), but it
        no longer *selects the price*: the payment channel does. Pairing a CN
        plan amount with a USD label is exactly what produced "9.9 USD" while
        the card was charged $1.99.
        """
        fn = getattr(payment_routes, view, None)
        assert fn is not None, f"{view}() no longer exists in payment_routes"
        source = inspect.getsource(fn)
        assert "billing_region_for_provider" in source, (
            f"{view}() must pick the billing region from the payment channel"
        )
        assert 'currency = plan["currency"]' in source, (
            f"{view}() must read currency from the plan row, not from STRIPE_CURRENCY"
        )
        assert "STRIPE_CURRENCY" not in source, (
            f"{view}() still reads STRIPE_CURRENCY — then amount and currency "
            "come from different sources and can disagree"
        )
        assert "get_plan_for_tier(new_tier, region)" not in source, (
            f"{view}() still prices off the caller's region instead of the channel's"
        )


def _register(client, email):
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "secret123", "name": "RegionGate"},
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return {"Authorization": f"Bearer {resp.get_json()['access_token']}"}


class TestOverseasSiteDetection:
    def test_sg_and_us_are_overseas(self, deploy_region):
        deploy_region("SG")
        assert is_overseas_billing_deploy() is True
        deploy_region("US")
        assert is_overseas_billing_deploy() is True

    def test_cn_and_unset_are_not_overseas(self, deploy_region):
        deploy_region("CN")
        assert is_overseas_billing_deploy() is False
        deploy_region(None)
        assert is_overseas_billing_deploy() is False


class TestOverseasHttpRejectsExplicitCn:
    """HTTP gate: overseas + explicit CN → 403. Must setenv SG (not rely on CI)."""

    def test_plans_cn_query_is_403_on_us_deploy_too(self, client, deploy_region):
        deploy_region("US")
        resp = client.get("/v1/payment/plans?region=CN")
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "region_not_supported"

    def test_plans_cn_query_is_403_on_sg(self, client, deploy_region):
        deploy_region("SG")
        resp = client.get("/v1/payment/plans?region=CN")
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "region_not_supported"

    def test_providers_cn_query_is_403_on_sg(self, client, deploy_region):
        deploy_region("SG")
        resp = client.get("/v1/payment/providers?region=CN")
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "region_not_supported"

    def test_plans_omitted_zh_header_still_us_on_sg(self, client, deploy_region):
        """v3.1.15 must not be eaten: language is not an explicit CN input."""
        deploy_region("SG")
        resp = client.get(
            "/v1/payment/plans",
            headers={"Accept-Language": "zh-CN,zh;q=0.9"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["region"] == "US"
        assert body["currency"] == "USD"

    def test_checkout_body_cn_is_403_on_sg(self, client, deploy_region):
        deploy_region("SG")
        auth = _register(client, "sg_explicit_cn_co@test.com")
        resp = client.post(
            "/v1/payment/checkout",
            json={"provider": "stripe", "tier": "supporter", "region": "CN"},
            headers=auth,
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "region_not_supported"

    def test_stripe_alias_query_cn_is_403_on_sg(self, client, deploy_region):
        deploy_region("SG")
        auth = _register(client, "sg_explicit_cn_alias@test.com")
        resp = client.post(
            "/v1/payment/stripe/checkout?region=CN",
            json={"tier": "supporter"},
            headers=auth,
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "region_not_supported"

    def test_wechat_explicit_cn_is_403_on_sg(self, client, deploy_region):
        deploy_region("SG")
        auth = _register(client, "sg_explicit_cn_wx@test.com")
        resp = client.post(
            "/v1/payment/wechat/order?region=CN",
            json={"tier": "supporter", "trade_type": "NATIVE"},
            headers=auth,
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "region_not_supported"

    @pytest.mark.parametrize(
        "view",
        [
            "list_plans",
            "list_providers",
            "create_checkout",
            "create_stripe_checkout",
            "create_wechat_order",
        ],
    )
    def test_views_call_overseas_cn_gate(self, view):
        fn = getattr(payment_routes, view, None)
        assert fn is not None, f"{view}() missing"
        assert "_reject_explicit_cn_on_overseas()" in inspect.getsource(fn)


class TestCnDeployStillAcceptsExplicitCn:
    """Reverse: the gate must not fire on CN / unset. Plans 200 is the clean proof."""

    def test_plans_cn_query_is_200_on_cn_deploy(self, client, deploy_region):
        deploy_region("CN")
        resp = client.get("/v1/payment/plans?region=CN")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["region"] == "CN"
        assert body["currency"] == "CNY"

    def test_plans_cn_query_is_200_when_deploy_unset(self, client, deploy_region):
        deploy_region(None)
        resp = client.get("/v1/payment/plans?region=CN")
        assert resp.status_code == 200
        assert resp.get_json()["region"] == "CN"

    def test_checkout_body_cn_is_not_region_403_on_cn_deploy(self, client, deploy_region):
        """CN site may stub-400, but must not overseas-403."""
        deploy_region("CN")
        auth = _register(client, "cn_explicit_cn_co@test.com")
        resp = client.post(
            "/v1/payment/checkout",
            json={"provider": "stripe", "tier": "supporter", "region": "CN"},
            headers=auth,
        )
        assert resp.status_code != 403
        assert resp.get_json().get("error") != "region_not_supported"
