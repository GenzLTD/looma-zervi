"""生成测试用 Supabase 兼容 JWT（开发环境专用）

用法：
    python scripts/gen_test_jwt.py

输出：
    { "token": "...", "user_id": "...", "email": "...", "tier": "...", "expires_in": 3600 }
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jwt


def generate_test_jwt(
    user_id: str = "7d521f7f-a8ba-4bc2-939b-f6cf918dc208",
    email: str = "zervi@genz.ltd",
    tier: str = "pro",
    expires_in: int = 3600,
) -> str:
    """用 SUPABASE_JWT_SECRET 签发一个 HS256 JWT（与 Supabase 兼容）"""
    from src.core.config import get_settings

    settings = get_settings()
    secret = settings.SUPABASE_JWT_SECRET
    if not secret:
        raise ValueError("SUPABASE_JWT_SECRET 未配置，请在 .env 中设置")

    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "app_metadata": {
            "tier": tier,
        },
        "aud": "authenticated",
        "exp": now + expires_in,
        "iat": now,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token


def main():
    token = generate_test_jwt()

    # 解码 payload（不验证签名，仅展示内容）
    import base64

    def _b64decode_part(part: str) -> dict:
        padding = 4 - len(part) % 4
        part += "=" * padding
        return json.loads(base64.urlsafe_b64decode(part))

    payload = _b64decode_part(token.split(".")[1])

    result = {
        "token": token,
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
        "tier": payload.get("app_metadata", {}).get("tier", "free"),
        "expires_in": payload.get("exp", 0) - int(time.time()),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return token


if __name__ == "__main__":
    main()
