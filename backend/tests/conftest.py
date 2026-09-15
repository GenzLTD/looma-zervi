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
