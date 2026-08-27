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
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5174,http://localhost:3000",
    ).split(",")

    # Quota
    FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "30"))
    SUPPORTER_DAILY_LIMIT = int(os.getenv("SUPPORTER_DAILY_LIMIT", "999999"))
    PRO_DAILY_LIMIT = int(os.getenv("PRO_DAILY_LIMIT", "999999"))

    # LLM Provider (multi-provider fallback: deepseek, ollama, openai)
    LLM_PROVIDER_ORDER = os.getenv("LLM_PROVIDER_ORDER", "deepseek,ollama,openai")
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")

    # Embedding provider
    EMBED_PROVIDER_ORDER = os.getenv("EMBED_PROVIDER_ORDER", "ollama,deepseek")
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

    # Signal Bridge — HMAC shared secret for cross-service Bridge 2/3 (PlanetX ↔ DemoPPI)
    SIGNAL_BRIDGE_SECRET = os.getenv("SIGNAL_BRIDGE_SECRET", "")
    # PlanetX → DemoPPI personality_beacon egress target (T3, service-to-service)
    DEMOPPI_SIGNAL_INGEST_URL = os.getenv("DEMOPPI_SIGNAL_INGEST_URL", "")
    # Chain B fan-out — PlanetX → GFCC /v1/signal-ingest (independent of SIGNAL_BRIDGE_SECRET)
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
    Config.CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5174,http://localhost:3000",
    ).split(",")
    Config.FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "30"))
    Config.SUPPORTER_DAILY_LIMIT = int(os.getenv("SUPPORTER_DAILY_LIMIT", "999999"))
    Config.PRO_DAILY_LIMIT = int(os.getenv("PRO_DAILY_LIMIT", "999999"))
    Config.LLM_PROVIDER_ORDER = os.getenv("LLM_PROVIDER_ORDER", "deepseek,ollama,openai")
    Config.OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    Config.OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
    Config.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    Config.OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
    Config.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")
    Config.EMBED_PROVIDER_ORDER = os.getenv("EMBED_PROVIDER_ORDER", "ollama,deepseek")
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
    Config.SIGNAL_BRIDGE_SECRET = os.getenv("SIGNAL_BRIDGE_SECRET", "")
    Config.DEMOPPI_SIGNAL_INGEST_URL = os.getenv("DEMOPPI_SIGNAL_INGEST_URL", "")
    Config.GFCC_SIGNAL_INGEST_URL = os.getenv("GFCC_SIGNAL_INGEST_URL", "")
    Config.SIGNAL_INGEST_SECRET = os.getenv("SIGNAL_INGEST_SECRET", "")
