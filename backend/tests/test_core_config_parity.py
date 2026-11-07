"""刀 5b 门禁：`CoreConfig` 与宿主 `Config` 在核需要的键上必须逐键同值。

为什么要有这条测试：核原先是 `app.config.from_object(Config)`，改成 `CoreConfig`
是为了把产品侧配置面挡在核外。一旦两边取值语义漂移（默认值、类型转换、rstrip、
CORS 拆分），核会以"看起来正常但行为不同"的方式跑偏 —— 只有逐键比对能抓住。
"""
from __future__ import annotations

import pytest

from src.config import Config, _refresh_config
from src.thomas_core.config import CoreConfig


def _core_keys() -> list[str]:
    return sorted(k for k in vars(CoreConfig) if k.isupper())


def test_core_config_keys_exist_in_host_config():
    missing = [k for k in _core_keys() if not hasattr(Config, k)]
    assert missing == [], f"CoreConfig 有宿主 Config 没有的键（会掩盖拼写错误）: {missing}"


def test_core_config_matches_host_config(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s3cr3t")
    monkeypatch.setenv("JWT_SECRET", "jwt-secret-for-parity")
    monkeypatch.setenv("JWT_EXPIRY_HOURS", "7")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("SUPABASE_URL", "https://demo.supabase.co/")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_x")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "sb-jwt")
    monkeypatch.setenv("DATABASE_PATH", "data/parity.db")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test ,")
    monkeypatch.setenv("FREE_DAILY_LIMIT", "11")
    monkeypatch.setenv("SUPPORTER_DAILY_LIMIT", "222")
    monkeypatch.setenv("PRO_DAILY_LIMIT", "333")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dk")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "ollama,deepseek")
    monkeypatch.setenv("EMBED_MODEL", "nomic-embed-text:latest")
    monkeypatch.setenv("CHROMA_COLLECTION", "looma_knowledge")
    monkeypatch.setenv("WECHAT_DEV_MODE", "TRUE")
    monkeypatch.setenv("ETHOS_AUTH_SECRET", "  ethos  ")

    _refresh_config()
    CoreConfig.refresh()

    diffs = {
        k: (getattr(CoreConfig, k), getattr(Config, k))
        for k in _core_keys()
        if getattr(CoreConfig, k) != getattr(Config, k)
    }
    assert diffs == {}, f"CoreConfig 与 Config 取值漂移: {diffs}"


def test_core_config_excludes_product_secrets():
    """核不该持有产品侧配置面（支付 / 企查查 / 推送 / 快递）。"""
    product_keys = {
        "STRIPE_SECRET_KEY", "PAYPAL_CLIENT_SECRET", "AIRWALLEX_API_KEY",
        "WECHAT_MCHID", "WECHAT_API_V3_KEY", "QCC_AUTH_TOKEN",
        "HUAWEI_IAP_PUBLIC_KEY", "HUAWEI_PUSH_CLIENT_SECRET",
        "SIGNAL_BRIDGE_SECRET", "GFCC_SIGNAL_INGEST_URL",
    }
    leaked = sorted(k for k in product_keys if hasattr(CoreConfig, k))
    assert leaked == [], f"产品侧键漏进核配置: {leaked}"


@pytest.fixture(autouse=True)
def _restore_config_after_test():
    """测试改了 env 后把类属性还原，避免污染同进程内的后续用例。"""
    yield
    _refresh_config()
    CoreConfig.refresh()
