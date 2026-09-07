"""Tests for payment contract and region-aware plans."""
import pytest


def test_payment_plans_default_cn(client):
    resp = client.get("/v1/payment/plans")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["region"] == "CN"
    assert data["currency"] == "CNY"
    assert data["payment_provider"] == "wechat"

    tiers = {plan["tier"]: plan for plan in data["plans"]}
    assert tiers["supporter"]["price_monthly"] == 9.9
    assert tiers["supporter"]["currency"] == "CNY"
    assert tiers["supporter"]["plan_id"] == "supporter_monthly_cn"
    assert tiers["pro"]["price_monthly"] == 29.9


def test_payment_plans_us_region(client):
    resp = client.get("/v1/payment/plans?region=US")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["region"] == "US"
    assert data["currency"] == "USD"
    assert data["payment_provider"] == "stripe"

    tiers = {plan["tier"]: plan for plan in data["plans"]}
    assert tiers["supporter"]["price_monthly"] == 1.99
    assert tiers["supporter"]["currency"] == "USD"
    assert tiers["supporter"]["plan_id"] == "supporter_monthly_us"
    assert tiers["pro"]["price_monthly"] == 5.99


def test_payment_plans_invalid_region_falls_back_to_cn(client):
    resp = client.get("/v1/payment/plans?region=XX")
    assert resp.status_code == 200
    assert resp.get_json()["region"] == "CN"


def test_payment_plans_deploy_alias_sg_maps_to_us(client):
    """Vultr 海外部署位上报 SG（DEPLOY_REGION=SG）时按美元区计费，不得落 CNY/微信。"""
    resp = client.get("/v1/payment/plans?region=SG")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["region"] == "US"
    assert data["currency"] == "USD"
    assert data["payment_provider"] == "stripe"


def test_payment_plans_non_chinese_language_falls_back_us(client):
    """非 zh/en 的 Accept-Language（如 de/fr/ja 浏览器）按海外美元区兜底，不落 CNY。"""
    resp = client.get("/v1/payment/plans", headers={"Accept-Language": "de-DE,de;q=0.9"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["region"] == "US"
    assert data["currency"] == "USD"


@pytest.mark.parametrize("tier,expected_price", [("supporter", 9.9), ("pro", 29.9)])
def test_payment_upgrade_includes_regional_plan(client, tier, expected_price):
    resp = client.post("/v1/auth/register", json={
        "email": f"{tier}-plan@test.com",
        "password": "password123",
    })
    token = resp.get_json()["access_token"]

    resp = client.post(
        f"/v1/payment/upgrade?region=CN",
        json={"tier": tier},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["tier"] == tier
    assert data["plan"]["price_monthly"] == expected_price
    assert data["plan"]["currency"] == "CNY"
