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

from pathlib import Path

import pytest

from src.payment.plans import resolve_region

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

    def test_explicit_cn_still_wins_over_deploy_site(self, deploy_region):
        """A client that really wants WeChat/CNY can still ask for it."""
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
