#!/usr/bin/env python3
"""Replace split Auth users with one seed account.

Deletes every Supabase Auth user that carries app_metadata.looma_user_id,
clears users.supabase_uid, then creates one looma row and one Auth user
that both hold the email and the WeChat openid.

SEED_EMAIL, SEED_PASSWORD, SEED_OPENID come from the environment.
The script prints counts only.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import urllib.error
import urllib.request
import uuid

import bcrypt


def _headers(secret: str) -> dict:
    return {
        "apikey": secret,
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
    }


def _request(url: str, secret: str, method: str = "GET", payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(secret), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {}
        return exc.code, body


def list_users(base: str, secret: str) -> list[dict]:
    found: list[dict] = []
    page = 1
    while page <= 20:
        status, body = _request(f"{base}/auth/v1/admin/users?page={page}&per_page=200", secret)
        if status != 200:
            raise SystemExit(f"list failed HTTP {status}")
        batch = body.get("users") or []
        found.extend(batch)
        if len(batch) < 200:
            return found
        page += 1
    raise SystemExit("user list did not terminate")


def main() -> None:
    base = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_SECRET_KEY"]
    email = os.environ["SEED_EMAIL"].strip().lower()
    password = os.environ["SEED_PASSWORD"]
    openid = os.environ["SEED_OPENID"].strip()
    name = os.environ.get("SEED_NAME", "PlanetX Seed")
    db_path = os.environ.get("LOOMA_DB", "backend/data/looma.db")

    deleted = 0
    for user in list_users(base, secret):
        looma_id = ((user.get("app_metadata") or {}).get("looma_user_id") or "").strip()
        if not looma_id:
            continue
        status, _ = _request(f"{base}/auth/v1/admin/users/{user['id']}", secret, "DELETE")
        if status not in (200, 204):
            raise SystemExit(f"delete failed HTTP {status}")
        deleted += 1

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("UPDATE users SET supabase_uid = NULL WHERE supabase_uid IS NOT NULL")
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    email_digest = hashlib.sha256(email.encode()).hexdigest()
    row = con.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        user_id = row["id"]
        con.execute(
            """UPDATE users
               SET password_hash = ?, wechat_openid = ?, name = ?, email_hash = ?,
                   tier = 'supporter', role = 'user', updated_at = datetime('now')
               WHERE id = ?""",
            (password_hash, openid, name, email_digest, user_id),
        )
    else:
        user_id = str(uuid.uuid4())
        con.execute(
            """INSERT INTO users
               (id, email, email_hash, password_hash, wechat_openid, name, tier, role)
               VALUES (?, ?, ?, ?, ?, ?, 'supporter', 'user')""",
            (user_id, email, email_digest, password_hash, openid, name),
        )
    con.execute("DELETE FROM user_identities WHERE user_id = ?", (user_id,))
    for provider, provider_uid in (("email", email), ("wechat", openid)):
        con.execute(
            """INSERT INTO user_identities
               (id, user_id, provider, provider_uid, provider_email, provider_name)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), user_id, provider, provider_uid, email, name),
        )

    status, body = _request(
        f"{base}/auth/v1/admin/users",
        secret,
        "POST",
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "looma_user_id": user_id,
                "full_name": name,
                "wechat_openid": openid,
                "provider": "wechat",
            },
            "app_metadata": {
                "provider": "email",
                "providers": ["email", "wechat"],
                "looma_user_id": user_id,
            },
        },
    )
    if status not in (200, 201):
        raise SystemExit(f"create failed HTTP {status}")
    supabase_id = str(body.get("id") or (body.get("user") or {}).get("id") or "")
    if not supabase_id:
        raise SystemExit("create returned no id")
    con.execute(
        "UPDATE users SET supabase_uid = ?, updated_at = datetime('now') WHERE id = ?",
        (supabase_id, user_id),
    )
    con.commit()
    remaining = list_users(base, secret)
    bound = con.execute(
        "SELECT COUNT(*) FROM users WHERE supabase_uid IS NOT NULL AND trim(supabase_uid) != ''"
    ).fetchone()[0]
    identities = con.execute(
        "SELECT COUNT(*) FROM user_identities WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]
    print(json.dumps({
        "deleted": deleted,
        "auth_users": len(remaining),
        "sqlite_bound": bound,
        "seed_identities": identities,
        "providers": (remaining[0].get("app_metadata") or {}).get("providers") if remaining else [],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
