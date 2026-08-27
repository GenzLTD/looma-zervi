"""
Rate limiting middleware using flask-limiter.

Provides per-endpoint rate limits:
  - Global default: 200 requests/hour per IP
  - Auth endpoints: 10 requests/minute per IP (brute-force protection)
  - Payment endpoints: 20 requests/minute per user

Storage backend: in-memory (dev) / Redis (production, set REDIS_URL env).

Usage in app.py:
    from src.api.middleware.rate_limiter import init_limiter
    limiter = init_limiter(app)

    # Apply to specific blueprints:
    limiter.limit(app.config["RATE_LIMIT_AUTH"])(auth_bp)
"""
from flask import request, g, current_app


def init_limiter(app):
    """Initialize flask-limiter and return the limiter instance.

    Call this after CORS is set up but before blueprints are registered.
    """
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
    except ImportError:
        app.logger.warning("[rate_limiter] flask-limiter not installed, rate limiting disabled")
        return None

    storage_uri = app.config.get("RATE_LIMIT_STORAGE_URI", "memory://")

    limiter = Limiter(
        key_func=_get_key,
        app=app,
        default_limits=[app.config.get("RATE_LIMIT_GLOBAL", "200/hour")],
        storage_uri=storage_uri,
        headers_enabled=True,
        strategy="fixed-window",
    )

    app.extensions = getattr(app, "extensions", {})
    app.extensions["limiter"] = limiter
    return limiter


def _get_key():
    """Rate limit key: use user_id if authenticated, otherwise IP address.

    This gives authenticated users their own bucket (not shared with IP),
    while anonymous requests are limited per IP.
    """
    user_id = g.get("user_id")
    if user_id:
        return f"user:{user_id}"
    return f"ip:{_get_remote_address()}"


def _get_remote_address():
    """Get client IP, respecting X-Forwarded-For from nginx/CDN."""
    if request.headers.get("X-Forwarded-For"):
        return request.headers["X-Forwarded-For"].split(",")[0].strip()
    if request.headers.get("X-Real-IP"):
        return request.headers["X-Real-IP"]
    return request.remote_addr or "127.0.0.1"
