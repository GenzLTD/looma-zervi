"""
Auth routes blueprint.
Ownership: JOINT (dual review required)

Endpoints:
  POST /v1/auth/register     - Web email/password registration
  POST /v1/auth/login        - Web email/password login
  POST /v1/auth/wechat       - WeChat miniprogram login (openid -> JWT)
  POST /v1/auth/google       - Google OAuth login (ID Token -> JWT) [overseas]
  POST /v1/auth/huawei       - HarmonyOS Account Kit login (authorizationCode -> JWT)
  POST /v1/auth/bind         - Bind wechat openid to existing account
  GET  /v1/auth/profile      - Get current user profile (requires auth)
  GET  /v1/auth/identities   - List linked identities (requires auth)
  POST /v1/auth/refresh      - Refresh JWT token (requires auth)
  POST /v1/auth/bridge       - [OPTIONAL] Supabase JWT -> looma JWT (MVP: 501)
"""
import bcrypt
import logging
from flask import Blueprint, request, jsonify, current_app, g

from src.api.auth.jwt_handler import sign_token, verify_token, get_current_user_id, sign_token_for_user
from src.api.auth.decorators import require_auth
from src.api.auth.wechat_auth import code2session
from src.api.auth.google_auth import verify_id_token, exchange_auth_code, GoogleUserInfo
from src.api.auth.huawei_auth import exchange_authorization_code, fetch_user_info

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


def _get_db():
    return current_app._db


# ============================================
# Web registration
# ============================================
@auth_bp.route("/register", methods=["POST"])
def register():
    """Web email/password registration -> looma JWT."""
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    name = data.get("name", "")

    if not email or not password:
        return jsonify(error="bad_request", message="email and password required"), 400

    if len(password) < 8:
        return jsonify(error="bad_request", message="password must be at least 8 characters"), 400

    db = _get_db()
    if db.get_user_by_email(email):
        return jsonify(error="conflict", message="email already registered"), 409

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_id = db.create_user(email=email, password_hash=password_hash, name=name)

    token = sign_token(user_id, extra_claims={"tier": "free", "email": email})
    return jsonify(
        access_token=token,
        token_type="bearer",
        expires_in=current_app.config["JWT_EXPIRY_HOURS"] * 3600,
        user={"id": user_id, "email": email, "name": name, "tier": "free", "role": "user"}
    ), 201


# ============================================
# Web login
# ============================================
@auth_bp.route("/login", methods=["POST"])
def login():
    """Web email/password login -> looma JWT."""
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify(error="bad_request", message="email and password required"), 400

    db = _get_db()
    user = db.get_user_by_email(email)
    if not user or not user.get("password_hash"):
        return jsonify(error="unauthorized", message="invalid credentials"), 401

    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return jsonify(error="unauthorized", message="invalid credentials"), 401

    token = sign_token(user["id"], extra_claims={
        "tier": user.get("tier", "free"),
        "email": user.get("email", ""),
    })
    return jsonify(
        access_token=token,
        token_type="bearer",
        expires_in=current_app.config["JWT_EXPIRY_HOURS"] * 3600,
        user={
            "id": user["id"],
            "email": user.get("email"),
            "name": user.get("name", ""),
            "tier": user.get("tier", "free"),
            "role": user.get("role", "user"),
        }
    )


# ============================================
# WeChat miniprogram login
# ============================================
@auth_bp.route("/wechat", methods=["POST"])
def wechat_login():
    """
    WeChat miniprogram login flow:
    1. Client calls wx.login() -> gets code
    2. Client sends code to this endpoint
    3. Backend calls WeChat API to exchange code for openid
    4. Backend finds or creates user by wechat_openid
    5. Backend signs looma JWT
    """
    data = request.get_json() or {}
    code = data.get("code", "")

    if not code:
        return jsonify(error="bad_request", message="wx.login code required"), 400

    # Dev mode: skip WeChat API, use code as mock openid
    if current_app.config.get("WECHAT_DEV_MODE"):
        openid = f"dev_{code[:20]}"
        print(f"[DEV MODE] Wechat login - mock openid: {openid}")
    else:
        try:
            wechat_data = code2session(code)
        except ValueError as e:
            return jsonify(error="wechat_error", message=str(e)), 400
        openid = wechat_data["openid"]
    db = _get_db()

    user = db.get_user_by_openid(openid)
    if not user:
        user_id = db.create_user(wechat_openid=openid)
        user = db.get_user_by_id(user_id)

    token = sign_token(user["id"], extra_claims={
        "tier": user.get("tier", "free"),
    })
    return jsonify(
        access_token=token,
        token_type="bearer",
        expires_in=current_app.config["JWT_EXPIRY_HOURS"] * 3600,
        user={
            "id": user["id"],
            "email": user.get("email"),
            "name": user.get("name", ""),
            "tier": user.get("tier", "free"),
            "role": user.get("role", "user"),
        }
    )


# ============================================
# Google OAuth login (overseas)
# ============================================
@auth_bp.route("/google", methods=["POST"])
def google_login():
    """Google OAuth login flow.

    Two modes:
    1. ID Token mode (recommended): client sends Google ID Token
       Body: { "id_token": "eyJhbG..." }
    2. Auth code mode (server-side OAuth): client sends authorization code
       Body: { "code": "4/0AXX...", "redirect_uri": "https://..." }

    Backend verifies → extracts sub (Google user ID) + email + name
    → finds or creates user via user_identities table → signs looma JWT
    """
    data = request.get_json() or {}
    id_token_str = data.get("id_token", "")
    code = data.get("code", "")

    if not id_token_str and not code:
        return jsonify(error="bad_request", message="id_token or code required"), 400

    try:
        if id_token_str:
            google_user = verify_id_token(id_token_str)
        else:
            google_user = exchange_auth_code(code)
    except ValueError as e:
        return jsonify(error="google_error", message=str(e)), 400

    db = _get_db()
    user, created = db.get_or_create_user_by_identity(
        provider="google",
        provider_uid=google_user.sub,
        email=google_user.email,
        name=google_user.name,
        metadata_json=google_user.to_metadata(),
    )

    if not user:
        return jsonify(error="server_error", message="Failed to create/find user"), 500

    current_app.logger.info(
        f"[google_auth] Login {'(new)' if created else '(existing)'}: "
        f"user={user['id']} google_sub={google_user.sub} email={google_user.email}"
    )

    token = sign_token(user["id"], extra_claims={
        "tier": user.get("tier", "free"),
        "email": user.get("email", ""),
    })
    return jsonify(
        access_token=token,
        token_type="bearer",
        expires_in=current_app.config["JWT_EXPIRY_HOURS"] * 3600,
        user={
            "id": user["id"],
            "email": user.get("email"),
            "name": user.get("name", ""),
            "tier": user.get("tier", "free"),
            "role": user.get("role", "user"),
            "is_new_user": created,
        }
    )


# ============================================
# HarmonyOS Account Kit login
# ============================================
@auth_bp.route("/huawei", methods=["POST"])
def huawei_login():
    """
    POST /v1/auth/huawei

    请求体:
    {
        "authorizationCode": "CgB6e3...",  # 元服务端 Account Kit 获取的授权码
        "state": "uuid-string"             # (可选) 防跨站攻击 state
    }

    响应:
    {
        "access_token": "eyJhbG...",
        "token_type": "bearer",
        "expires_in": 86400,
        "user": {
            "id": "user_xxx",
            "name": "...",
            "tier": "free",
            "is_new_user": false
        }
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="bad_request", message="Invalid JSON body"), 400

    authorization_code = (data.get("authorizationCode", "") or "").strip()
    if not authorization_code:
        return jsonify(error="bad_request", message="authorizationCode is required"), 400

    # --- Step 1: 换取 access_token ---
    try:
        token_data = exchange_authorization_code(authorization_code)
    except ValueError as e:
        logger.warning(f"[huawei_auth] Token exchange failed: {e}")
        return jsonify(error="oauth_error", message=str(e)), 401
    except Exception as e:
        logger.error(f"[huawei_auth] Token exchange network error: {e}")
        return jsonify(error="upstream_error", message="Huawei OAuth server unreachable"), 502

    access_token = token_data.get("access_token", "")
    if not access_token:
        return jsonify(error="oauth_error", message="No access_token in Huawei response"), 502

    # --- Step 2: 获取用户信息 ---
    try:
        hw_user = fetch_user_info(access_token)
    except ValueError as e:
        logger.warning(f"[huawei_auth] Userinfo fetch failed: {e}")
        return jsonify(error="oauth_error", message=str(e)), 502
    except Exception as e:
        logger.error(f"[huawei_auth] Userinfo network error: {e}")
        return jsonify(error="upstream_error", message="Huawei account server unreachable"), 502

    if not hw_user.open_id:
        return jsonify(error="oauth_error", message="Failed to retrieve Huawei openID"), 502

    # --- Step 3: 查找或创建用户 ---
    # metadata 保留 union_id / avatar；勿写入 wechat_openid（微信专用列）
    import json as _json
    meta = {
        "union_id": hw_user.union_id or "",
        "avatar_url": hw_user.avatar_url or "",
        "display_name": hw_user.display_name or "",
        "raw": hw_user.raw or {},
    }
    db = _get_db()
    user, created = db.get_or_create_user_by_identity(
        provider="huawei",
        provider_uid=hw_user.open_id,
        name=hw_user.display_name or "",
        metadata_json=_json.dumps(meta, ensure_ascii=False),
    )

    if not user:
        return jsonify(error="server_error", message="Failed to create/find user"), 500

    logger.info(
        f"[huawei_auth] Login {'(new)' if created else '(existing)'}: "
        f"user={user['id']} huawei_open_id={hw_user.open_id}"
    )

    # --- Step 4: 签发 JWT ---
    token = sign_token(user["id"], extra_claims={
        "tier": user.get("tier", "free"),
        "provider": "huawei",
    })
    return jsonify(
        access_token=token,
        token_type="bearer",
        expires_in=current_app.config["JWT_EXPIRY_HOURS"] * 3600,
        user={
            "id": user["id"],
            "name": user.get("name", ""),
            "tier": user.get("tier", "free"),
            "role": user.get("role", "user"),
            "is_new_user": created,
        }
    )


# ============================================
# Cross-platform account binding
# ============================================
@auth_bp.route("/bind", methods=["POST"])
@require_auth
def bind_account():
    """
    Bind WeChat openid to an existing email-based account.
    User must be authenticated (has looma JWT).
    After binding, the user can login from both Web and MiniApp.
    """
    data = request.get_json() or {}
    code = data.get("code", "")

    if not code:
        return jsonify(error="bad_request", message="wx.login code required"), 400

    try:
        wechat_data = code2session(code)
    except ValueError as e:
        return jsonify(error="wechat_error", message=str(e)), 400

    openid = wechat_data["openid"]
    db = _get_db()

    existing = db.get_user_by_openid(openid)
    if existing and existing["id"] != g.user_id:
        return jsonify(error="conflict", message="this WeChat account is already bound to another user"), 409

    db.bind_wechat_to_user(g.user_id, openid)
    return jsonify(message="WeChat account bound successfully")


# ============================================
# Get profile
# ============================================
@auth_bp.route("/profile", methods=["GET"])
@require_auth
def get_profile():
    """Get current user's profile."""
    db = _get_db()
    user = db.get_user_by_id(g.user_id)
    if not user:
        return jsonify(error="not_found", message="user not found"), 404

    return jsonify(
        id=user["id"],
        email=user.get("email"),
        name=user.get("name", ""),
        tier=user.get("tier", "free"),
        role=user.get("role", "user"),
        is_early_adopter=bool(user.get("is_early_adopter", 0)),
        created_at=user.get("created_at"),
    )


# ============================================
# List linked identities (overseas)
# ============================================
@auth_bp.route("/identities", methods=["GET"])
@require_auth
def list_identities():
    """List all third-party identities linked to the current user."""
    db = _get_db()
    identities = db.get_user_identities(g.user_id)
    return jsonify(
        user_id=g.user_id,
        identities=identities,
    )


# ============================================
# Refresh token
# ============================================
@auth_bp.route("/refresh", methods=["POST"])
@require_auth
def refresh_token():
    """Issue a new JWT with extended expiry."""
    db = _get_db()
    user = db.get_user_by_id(g.user_id)
    if not user:
        return jsonify(error="not_found", message="user not found"), 404

    token = sign_token_for_user(db, g.user_id)
    return jsonify(
        access_token=token,
        token_type="bearer",
        expires_in=current_app.config["JWT_EXPIRY_HOURS"] * 3600,
    )


# ============================================
# Supabase bridge (OPTIONAL - MVP returns 501)
# ============================================
@auth_bp.route("/bridge", methods=["POST"])
def supabase_bridge():
    """
    [OPTIONAL] Exchange a Supabase JWT for a looma JWT.
    MVP: not implemented. Enable when Web social login is needed.
    """
    return jsonify(error="not_implemented", message="Supabase bridge will be available in a future phase"), 501
