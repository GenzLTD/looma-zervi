"""Shared pytest fixtures for backend tests."""
import os
import tempfile

import pytest

from src.app import create_app


@pytest.fixture(autouse=True)
def _billing_region_baseline(monkeypatch):
    """Pin the billing region to CN for every test.

    Most payment tests assume CN: the WeChat flows, and the region gate's
    passthrough expectations. They used to get that for free because nothing
    read DEPLOY_REGION. Once billing resolution started honouring it, CI set it
    to SG (deploy-overseas.yml) and 14 of those tests broke — the same suite is
    green locally where DEPLOY_REGION is unset.

    So the environment no longer decides. This fixture does, and tests that
    care about overseas semantics override it explicitly — see
    tests/test_billing_region.py, whose deploy_region fixture depends on this
    one to guarantee ordering.
    """
    monkeypatch.setenv("DEPLOY_REGION", "CN")


@pytest.fixture(autouse=True)
def _offline_supabase_baseline(monkeypatch):
    """默认不连 Supabase：身份链路走本地路径，断网也不该红。

    本机 .env 配了真实 Supabase（URL + SECRET_KEY + JWT_SECRET 三者齐备），
    而 /v1/auth/wechat 只要这三者齐备就走 Supabase upsert（auth_routes.py:140），
    需要外网。域名解析一抖就是 6 项 502，与被测代码无关——
    test_miniprogram_payment_flow.py 整条 stub 流都挂在微信登录上。

    测试不该依赖外网，所以这里把开关关掉（create_app 会 _refresh_config 重读 env）。
    真正要验 Supabase 的 tests/test_supabase_auth.py 用自己的 app fixture 显式打开：
    env 在它的 fixture 里设置、晚于本 fixture，所以不受影响。
    """
    for _k in (
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_JWT_SECRET",
    ):
        monkeypatch.delenv(_k, raising=False)


@pytest.fixture
def app():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_PATH"] = path
    os.environ["JWT_SECRET"] = "test-secret"
    os.environ["WECHAT_DEV_MODE"] = "true"
    os.environ["DEEPSEEK_API_KEY"] = "skip"
    # Payment tests set these via their own fixtures and never restore them.
    # Reset to a clean stub baseline before every app so later tests
    # (e.g. tier gating relying on PAYMENT_STUB_MODE=true) aren't poisoned.
    os.environ["PAYMENT_STUB_MODE"] = "true"
    for _k in (
        "WECHAT_MCHID",
        "WECHAT_APPID",
        "WECHAT_API_V3_KEY",
        "WECHAT_SERIAL_NO",
        "WECHAT_PRIVATE_KEY_PATH",
        "WECHAT_NOTIFY_URL",
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
    ):
        os.environ.pop(_k, None)
    application = create_app("testing")
    yield application
    os.unlink(path)


@pytest.fixture
def client(app):
    return app.test_client()
