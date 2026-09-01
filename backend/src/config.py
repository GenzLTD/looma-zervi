"""
Configuration management.
All secrets come from environment variables, never hardcoded.
Uses class-level __dict__ overrides so Flask's from_object()
always picks up the latest env values (not cached at import time).
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Flask config that reads env vars dynamically.

    Flask's ``app.config.from_object()`` iterates over the class's
    ``__dict__`` and copies UPPER-case keys.  By storing them as
    descriptors (or just relying on ``os.getenv`` at access time),
    we ensure each ``from_object`` call gets fresh values.
    """

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5200"))

    # JWT
    JWT_SECRET = os.getenv("JWT_SECRET", "looma-zervi-default-jwt-secret-change-in-production-2026")
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

    # Supabase — THOMAS 生态统一认证 (RFC docs/rfc/supabase-unified-auth-v1.md)
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    # service_role secret key (sb_secret_*) — Admin API upsert 微信/华为用户
    SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")
    # HS256 custom token 签发（微信/华为无原生 provider，looma 代签）
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
    # Auth 签发 token 验证走 JWKS (ES256) —— 由 SUPABASE_URL 推导
    SUPABASE_JWKS_URL = (
        os.getenv("SUPABASE_URL", "").rstrip("/") + "/auth/v1/.well-known/jwks.json"
    ) if os.getenv("SUPABASE_URL", "") else ""

    # WeChat
    WECHAT_APPID = os.getenv("WECHAT_APPID", "")
    WECHAT_APP_SECRET = os.getenv("WECHAT_APP_SECRET", "")
    WECHAT_DEV_MODE = os.getenv("WECHAT_DEV_MODE", "false").lower() == "true"

    # DeepSeek
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # ChromaDB
    CHROMA_MODE = os.getenv("CHROMA_MODE", "local")
    CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
    CHROMA_PORT = os.getenv("CHROMA_PORT", "8000")
    CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "looma_knowledge")

    # Poetry ChromaDB — always uses embedded PersistentClient (static dataset)
    POETRY_CHROMA_PATH = os.getenv("POETRY_CHROMA_PATH", "data/poetry_full")
    POETRY_SEARCH_MODE = os.getenv("POETRY_SEARCH_MODE", "auto").lower()
    POETRY_CHROMA_SEARCH_TIMEOUT = float(os.getenv("POETRY_CHROMA_SEARCH_TIMEOUT", "10"))

    # SQLite — must be dynamic so tests can override per-fixture
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/looma.db")

    # CORS — portal :3000 local; production add szbolent.cn via CORS_ORIGINS env
    CORS_ORIGINS = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:5174,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:3000",
        ).split(",")
        if o.strip()
    ]

    # Quota
    FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "30"))
    SUPPORTER_DAILY_LIMIT = int(os.getenv("SUPPORTER_DAILY_LIMIT", "999999"))
    PRO_DAILY_LIMIT = int(os.getenv("PRO_DAILY_LIMIT", "999999"))

    # LLM Provider (deepseek primary, ollama local fallback; set env to override)
    LLM_PROVIDER_ORDER = os.getenv("LLM_PROVIDER_ORDER", "deepseek,ollama")
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")

    # Embedding provider (overseas: openai embeddings first)
    EMBED_PROVIDER_ORDER = os.getenv("EMBED_PROVIDER_ORDER", "openai,ollama,deepseek")
    EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text:latest")
    EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))

    # API timeout
    API_REQUEST_TIMEOUT = float(os.getenv("API_REQUEST_TIMEOUT", "90.0"))

    # pgvector (optional — used by RAG engine if configured)
    PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
    PG_PORT = int(os.getenv("PG_PORT", "5432"))
    PG_USER = os.getenv("PG_USER", "postgres")
    PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")
    PG_DATABASE = os.getenv("PG_DATABASE", "looma")

    # Navigator psychology layer
    PSYCHOLOGY_ENABLED = os.getenv("PSYCHOLOGY_ENABLED", "true").lower() == "true"
    PSYCHOLOGY_API_TYPE = os.getenv("PSYCHOLOGY_API_TYPE", "local")
    SENTINO_API_KEY = os.getenv("SENTINO_API_KEY", "")

    # Payment — stub mode disables real payment (dev default on)
    PAYMENT_STUB_MODE = os.getenv("PAYMENT_STUB_MODE", "true").lower() == "true"

    # WeChat Pay API v3 (生产环境）
    WECHAT_MCHID = os.getenv("WECHAT_MCHID", "")
    WECHAT_API_V3_KEY = os.getenv("WECHAT_API_V3_KEY", "")
    WECHAT_SERIAL_NO = os.getenv("WECHAT_SERIAL_NO", "")
    WECHAT_PRIVATE_KEY_PATH = os.getenv("WECHAT_PRIVATE_KEY_PATH", "")
    WECHAT_NOTIFY_URL = os.getenv("WECHAT_NOTIFY_URL", "")

    # Google OAuth (overseas — Sign in with Google)
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")

    # Stripe (overseas payment)
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "USD")

    # PayPal (overseas payment)
    PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
    PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
    PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")  # sandbox | live
    PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")

    # Airwallex (overseas payment)
    AIRWALLEX_API_KEY = os.getenv("AIRWALLEX_API_KEY", "")
    AIRWALLEX_CLIENT_KEY = os.getenv("AIRWALLEX_CLIENT_KEY", "")
    AIRWALLEX_MODE = os.getenv("AIRWALLEX_MODE", "demo")  # demo | production
    AIRWALLEX_WEBHOOK_SECRET = os.getenv("AIRWALLEX_WEBHOOK_SECRET", "")

    # ============================================
    # HarmonyOS / 华为生态
    # ============================================
    # 华为帐号 OAuth (AppGallery Connect → OAuth 2.0 客户端ID)
    HUAWEI_CLIENT_ID = os.getenv("HUAWEI_CLIENT_ID", "")
    HUAWEI_CLIENT_SECRET = os.getenv("HUAWEI_CLIENT_SECRET", "")
    HUAWEI_OAUTH_REGION = os.getenv("HUAWEI_OAUTH_REGION", "cn")  # cn | ru | de | sg

    # 华为 IAP (AppGallery Connect → 支付服务信息 → IAP 公钥)
    HUAWEI_IAP_PUBLIC_KEY = os.getenv("HUAWEI_IAP_PUBLIC_KEY", "")
    HUAWEI_IAP_SIGN_ALGORITHM = os.getenv("HUAWEI_IAP_SIGN_ALGORITHM", "SHA256WithRSA")

    # 华为 Push Kit (AppGallery Connect → 项目设置)
    HUAWEI_PUSH_CLIENT_ID = os.getenv("HUAWEI_PUSH_CLIENT_ID", "")
    HUAWEI_PUSH_CLIENT_SECRET = os.getenv("HUAWEI_PUSH_CLIENT_SECRET", "")
    HUAWEI_PROJECT_ID = os.getenv("HUAWEI_PROJECT_ID", "")

    # Rate limiting
    RATE_LIMIT_GLOBAL = os.getenv("RATE_LIMIT_GLOBAL", "200/hour")
    RATE_LIMIT_AUTH = os.getenv("RATE_LIMIT_AUTH", "10/minute")
    RATE_LIMIT_PAYMENT = os.getenv("RATE_LIMIT_PAYMENT", "20/minute")
    RATE_LIMIT_STORAGE_URI = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")

    # Deployment region (overseas: US | EU | SG)
    DEPLOY_REGION = os.getenv("DEPLOY_REGION", "US")

    # QCC (企查查) MCP — Official enterprise credit data source
    QCC_ENABLED = os.getenv("QCC_ENABLED", "true").lower() == "true"
    QCC_AUTH_TOKEN = os.getenv("QCC_AUTH_TOKEN", "")
    QCC_TIMEOUT = float(os.getenv("QCC_TIMEOUT", "30.0"))
    QCC_COMPANY_URL = os.getenv("QCC_COMPANY_URL", "https://agent.qcc.com/mcp/company/stream")
    QCC_RISK_URL = os.getenv("QCC_RISK_URL", "https://agent.qcc.com/mcp/risk/stream")
    QCC_IPR_URL = os.getenv("QCC_IPR_URL", "https://agent.qcc.com/mcp/ipr/stream")
    QCC_OPERATION_URL = os.getenv("QCC_OPERATION_URL", "https://agent.qcc.com/mcp/operation/stream")
    QCC_EXECUTIVE_URL = os.getenv("QCC_EXECUTIVE_URL", "https://agent.qcc.com/mcp/executive/stream")
    QCC_HISTORY_URL = os.getenv("QCC_HISTORY_URL", "https://agent.qcc.com/mcp/history/stream")
    QCC_LEGAL_REGULATION_URL = os.getenv("QCC_LEGAL_REGULATION_URL", "https://agent.qcc.com/mcp/regulation/stream")
    QCC_LEGAL_CASE_URL = os.getenv("QCC_LEGAL_CASE_URL", "https://agent.qcc.com/mcp/case/stream")
    QCC_DOCUMENT_URL = os.getenv("QCC_DOCUMENT_URL", "https://agent.qcc.com/mcp/document/stream")

    # Signal Bridge — chain A (PlanetX ↔ DemoPPI). Empty URL = skip.
    SIGNAL_BRIDGE_SECRET = os.getenv("SIGNAL_BRIDGE_SECRET", "")
    DEMOPPI_SIGNAL_INGEST_URL = os.getenv("DEMOPPI_SIGNAL_INGEST_URL", "")
    # Chain B fan-out — PlanetX → gfcc_kernel /v1/signal-ingest. Empty = skip.
    GFCC_SIGNAL_INGEST_URL = os.getenv("GFCC_SIGNAL_INGEST_URL", "")
    SIGNAL_INGEST_SECRET = os.getenv("SIGNAL_INGEST_SECRET", "")

    @property
    def is_production(self):
        return self.FLASK_ENV == "production"

    @property
    def PG_DSN(self):
        return (
            f"postgresql://{self.PG_USER}:{self.PG_PASSWORD}"
            f"@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DATABASE}"
        )


def _refresh_config():
    """Re-read all env vars into Config class attributes.

    Call this before ``app.config.from_object(Config)`` so that
    runtime env-var changes (e.g. per-test DATABASE_PATH overrides)
    are picked up instead of stale import-time values.
    """
    Config.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    Config.FLASK_ENV = os.getenv("FLASK_ENV", "development")
    Config.FLASK_PORT = int(os.getenv("FLASK_PORT", "5200"))
    Config.JWT_SECRET = os.getenv("JWT_SECRET", "looma-zervi-default-jwt-secret-change-in-production-2026")
    Config.JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
    Config.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    Config.SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    Config.SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    Config.SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")
    Config.SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
    Config.SUPABASE_JWKS_URL = (
        os.getenv("SUPABASE_URL", "").rstrip("/") + "/auth/v1/.well-known/jwks.json"
    ) if os.getenv("SUPABASE_URL", "") else ""
    Config.WECHAT_APPID = os.getenv("WECHAT_APPID", "")
    Config.WECHAT_APP_SECRET = os.getenv("WECHAT_APP_SECRET", "")
    Config.WECHAT_DEV_MODE = os.getenv("WECHAT_DEV_MODE", "false").lower() == "true"
    Config.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    Config.DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    Config.DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    Config.CHROMA_MODE = os.getenv("CHROMA_MODE", "local")
    Config.CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
    Config.CHROMA_PORT = os.getenv("CHROMA_PORT", "8000")
    Config.CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "looma_knowledge")
    Config.POETRY_CHROMA_PATH = os.getenv("POETRY_CHROMA_PATH", "data/poetry_full")
    POETRY_SEARCH_MODE = os.getenv("POETRY_SEARCH_MODE", "auto").lower()
    POETRY_CHROMA_SEARCH_TIMEOUT = float(os.getenv("POETRY_CHROMA_SEARCH_TIMEOUT", "10"))
    Config.DATABASE_PATH = os.getenv("DATABASE_PATH", "data/looma.db")
    Config.CORS_ORIGINS = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:5174,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:3000",
        ).split(",")
        if o.strip()
    ]
    Config.FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "30"))
    Config.SUPPORTER_DAILY_LIMIT = int(os.getenv("SUPPORTER_DAILY_LIMIT", "999999"))
    Config.PRO_DAILY_LIMIT = int(os.getenv("PRO_DAILY_LIMIT", "999999"))
    Config.LLM_PROVIDER_ORDER = os.getenv("LLM_PROVIDER_ORDER", "deepseek,ollama")
    Config.OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    Config.OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
    Config.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    Config.OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
    Config.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")
    Config.EMBED_PROVIDER_ORDER = os.getenv("EMBED_PROVIDER_ORDER", "openai,ollama,deepseek")
    Config.EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text:latest")
    Config.EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))
    Config.API_REQUEST_TIMEOUT = float(os.getenv("API_REQUEST_TIMEOUT", "90.0"))
    Config.PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
    Config.PG_PORT = int(os.getenv("PG_PORT", "5432"))
    Config.PG_USER = os.getenv("PG_USER", "postgres")
    Config.PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")
    Config.PG_DATABASE = os.getenv("PG_DATABASE", "looma")
    Config.PSYCHOLOGY_ENABLED = os.getenv("PSYCHOLOGY_ENABLED", "true").lower() == "true"
    Config.PSYCHOLOGY_API_TYPE = os.getenv("PSYCHOLOGY_API_TYPE", "local")
    Config.SENTINO_API_KEY = os.getenv("SENTINO_API_KEY", "")
    Config.PAYMENT_STUB_MODE = os.getenv("PAYMENT_STUB_MODE", "true").lower() == "true"
    Config.WECHAT_MCHID = os.getenv("WECHAT_MCHID", "")
    Config.WECHAT_API_V3_KEY = os.getenv("WECHAT_API_V3_KEY", "")
    Config.WECHAT_SERIAL_NO = os.getenv("WECHAT_SERIAL_NO", "")
    Config.WECHAT_PRIVATE_KEY_PATH = os.getenv("WECHAT_PRIVATE_KEY_PATH", "")
    Config.WECHAT_NOTIFY_URL = os.getenv("WECHAT_NOTIFY_URL", "")

    # Google OAuth (overseas)
    Config.GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    Config.GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    Config.GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")

    # Stripe (overseas payment)
    Config.STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    Config.STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    Config.STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "USD")

    # PayPal (overseas payment)
    Config.PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
    Config.PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
    Config.PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")
    Config.PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")

    # Airwallex (overseas payment)
    Config.AIRWALLEX_API_KEY = os.getenv("AIRWALLEX_API_KEY", "")
    Config.AIRWALLEX_CLIENT_KEY = os.getenv("AIRWALLEX_CLIENT_KEY", "")
    Config.AIRWALLEX_MODE = os.getenv("AIRWALLEX_MODE", "demo")
    Config.AIRWALLEX_WEBHOOK_SECRET = os.getenv("AIRWALLEX_WEBHOOK_SECRET", "")

    # HarmonyOS / 华为生态
    Config.HUAWEI_CLIENT_ID = os.getenv("HUAWEI_CLIENT_ID", "")
    Config.HUAWEI_CLIENT_SECRET = os.getenv("HUAWEI_CLIENT_SECRET", "")
    Config.HUAWEI_OAUTH_REGION = os.getenv("HUAWEI_OAUTH_REGION", "cn")
    Config.HUAWEI_IAP_PUBLIC_KEY = os.getenv("HUAWEI_IAP_PUBLIC_KEY", "")
    Config.HUAWEI_IAP_SIGN_ALGORITHM = os.getenv("HUAWEI_IAP_SIGN_ALGORITHM", "SHA256WithRSA")
    Config.HUAWEI_PUSH_CLIENT_ID = os.getenv("HUAWEI_PUSH_CLIENT_ID", "")
    Config.HUAWEI_PUSH_CLIENT_SECRET = os.getenv("HUAWEI_PUSH_CLIENT_SECRET", "")
    Config.HUAWEI_PROJECT_ID = os.getenv("HUAWEI_PROJECT_ID", "")

    # Rate limiting
    Config.RATE_LIMIT_GLOBAL = os.getenv("RATE_LIMIT_GLOBAL", "200/hour")
    Config.RATE_LIMIT_AUTH = os.getenv("RATE_LIMIT_AUTH", "10/minute")
    Config.RATE_LIMIT_PAYMENT = os.getenv("RATE_LIMIT_PAYMENT", "20/minute")
    Config.RATE_LIMIT_STORAGE_URI = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")

    # Deployment region
    Config.DEPLOY_REGION = os.getenv("DEPLOY_REGION", "US")

    # QCC (企查查) MCP
    Config.QCC_ENABLED = os.getenv("QCC_ENABLED", "true").lower() == "true"
    Config.QCC_AUTH_TOKEN = os.getenv("QCC_AUTH_TOKEN", "")
    Config.QCC_TIMEOUT = float(os.getenv("QCC_TIMEOUT", "30.0"))
    Config.QCC_COMPANY_URL = os.getenv("QCC_COMPANY_URL", "https://agent.qcc.com/mcp/company/stream")
    Config.QCC_RISK_URL = os.getenv("QCC_RISK_URL", "https://agent.qcc.com/mcp/risk/stream")
    Config.QCC_IPR_URL = os.getenv("QCC_IPR_URL", "https://agent.qcc.com/mcp/ipr/stream")
    Config.QCC_OPERATION_URL = os.getenv("QCC_OPERATION_URL", "https://agent.qcc.com/mcp/operation/stream")
    Config.QCC_EXECUTIVE_URL = os.getenv("QCC_EXECUTIVE_URL", "https://agent.qcc.com/mcp/executive/stream")
    Config.QCC_HISTORY_URL = os.getenv("QCC_HISTORY_URL", "https://agent.qcc.com/mcp/history/stream")
    Config.QCC_LEGAL_REGULATION_URL = os.getenv("QCC_LEGAL_REGULATION_URL", "https://agent.qcc.com/mcp/regulation/stream")
    Config.QCC_LEGAL_CASE_URL = os.getenv("QCC_LEGAL_CASE_URL", "https://agent.qcc.com/mcp/case/stream")
    Config.QCC_DOCUMENT_URL = os.getenv("QCC_DOCUMENT_URL", "https://agent.qcc.com/mcp/document/stream")
    Config.SIGNAL_BRIDGE_SECRET = os.getenv("SIGNAL_BRIDGE_SECRET", "")
    Config.DEMOPPI_SIGNAL_INGEST_URL = os.getenv("DEMOPPI_SIGNAL_INGEST_URL", "")
    Config.GFCC_SIGNAL_INGEST_URL = os.getenv("GFCC_SIGNAL_INGEST_URL", "")
    Config.SIGNAL_INGEST_SECRET = os.getenv("SIGNAL_INGEST_SECRET", "")
