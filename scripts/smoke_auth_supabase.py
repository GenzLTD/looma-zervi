"""Supabase JWT 验签冒烟测试

用法：
    python scripts/smoke_auth_supabase.py

测试项目：
    1. 用 SUPABASE_JWT_SECRET 签发的 token 能通过验签
    2. 用错误 secret 签发的 token 被正确拒绝
    3. JWT 格式检查（长度 ≥ 32，三段结构）
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jwt
from jwt import InvalidSignatureError, ExpiredSignatureError, InvalidTokenError


def green(msg: str) -> str:
    return f"\033[92m[PASS]\033[0m {msg}"


def red(msg: str) -> str:
    return f"\033[91m[FAIL]\033[0m {msg}"


def generate_token(secret: str, user_id: str = "test-user", tier: str = "pro") -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": "test@example.com",
        "app_metadata": {"tier": tier},
        "aud": "authenticated",
        "exp": now + 3600,
        "iat": now,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_verify_correct_secret():
    """用正确 secret 签发的 token 应验签通过"""
    from src.core.config import get_settings
    settings = get_settings()
    secret = settings.SUPABASE_JWT_SECRET
    if not secret:
        print(red("SUPABASE_JWT_SECRET 未配置，跳过测试"))
        return False

    token = generate_token(secret)
    try:
        decoded = jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
        print(green("验签通过"))
        print(f"       sub  = {decoded.get('sub')}")
        print(f"       tier = {decoded.get('app_metadata', {}).get('tier')}")
        return True
    except Exception as e:
        print(red(f"验签失败: {e}"))
        return False


def test_verify_wrong_secret():
    """用错误 secret 签发的 token 应被拒绝"""
    from src.core.config import get_settings
    settings = get_settings()
    secret = settings.SUPABASE_JWT_SECRET
    if not secret:
        print(red("SUPABASE_JWT_SECRET 未配置，跳过测试"))
        return False

    wrong_secret = "wrong-secret-" * 4
    token = generate_token(wrong_secret)
    try:
        jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
        print(red("错误 secret 未被拒绝！这是安全漏洞！"))
        return False
    except (InvalidSignatureError, InvalidTokenError):
        print(green("错误 secret 正确拒绝"))
        return True
    except Exception as e:
        print(green(f"错误 secret 被拒绝（{type(e).__name__}）"))
        return True


def test_jwt_format():
    """检查 JWT 基本格式"""
    from src.core.config import get_settings
    settings = get_settings()
    secret = settings.SUPABASE_JWT_SECRET or "dummy"
    token = generate_token(secret)
    parts = token.split(".")
    if len(parts) != 3:
        print(red(f"JWT 格式错误：应为 3 段，实际 {len(parts)} 段"))
        return False
    ok = len(token) >= 32
    if ok:
        print(green(f"长度 {len(token)} >= 32，格式合理"))
    else:
        print(red(f"JWT 长度 {len(token)} < 32"))
    return ok


def main():
    print("=" * 50)
    print("  Looma-Zervi Supabase JWT 冒烟测试")
    print("=" * 50)
    print()

    r1 = test_verify_correct_secret()
    print()
    r2 = test_verify_wrong_secret()
    print()
    r3 = test_jwt_format()
    print()
    print("-" * 50)
    all_pass = r1 and r2 and r3
    print(f"结果：{'全部通过 ✅' if all_pass else '存在失败 ❌'}")


if __name__ == "__main__":
    main()
