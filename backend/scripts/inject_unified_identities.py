#!/usr/bin/env python3
"""Inject one Supabase Auth user per looma user.

Source of truth is the looma ``users`` row. Each row becomes exactly one
Auth user on the project in ``SUPABASE_URL``. The Auth user's id is written
back to ``users.supabase_uid``. Re-running matches ``app_metadata.looma_user_id``
and does not create a second Auth user.

Email accounts keep their bcrypt hash when the Admin API accepts
``password_hash``. WeChat-only accounts use ``<openid>@wechat.thomas.local``,
the same placeholder as ``supabase_auth.placeholder_email``.

Secrets stay in the environment. This script never prints emails, openids,
or password hashes.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import urllib.error
import urllib.request


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
            body = resp.read()
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"msg": raw[:180]}
        return exc.code, parsed


def list_users(base: str, secret: str) -> list[dict]:
    found: list[dict] = []
    page = 1
    while page <= 20:
        status, body = _request(
            f"{base}/auth/v1/admin/users?page={page}&per_page=200",
            secret,
        )
        if status != 200:
            raise SystemExit(f"list users failed: HTTP {status}")
        batch = body.get("users") or []
        found.extend(batch)
        if len(batch) < 200:
            return found
        page += 1
    raise SystemExit("user list did not terminate")


def user_id_of(body: dict) -> str:
    if body.get("id"):
        return str(body["id"])
    nested = body.get("user") or {}
    return str(nested.get("id") or "")


def classify(row: sqlite3.Row) -> tuple[str, str]:
    email = (row["email"] or "").strip().lower()
    openid = (row["wechat_openid"] or "").strip()
    real_email = email if email and not email.endswith(".thomas.local") else ""
    if openid and real_email:
        return real_email, "both"
    if openid:
        return f"{openid}@wechat.thomas.local", "wechat"
    if email:
        return email, "email"
    return "", "skip"


def create_user(base: str, secret: str, email: str, kind: str, row: sqlite3.Row) -> tuple[str, str]:
    providers = ["email", "wechat"] if kind == "both" else [kind]
    metadata = {
        "looma_user_id": row["id"],
        "full_name": row["name"] or "",
    }
    if row["wechat_openid"]:
        metadata["wechat_openid"] = row["wechat_openid"]
        metadata["provider"] = "wechat"
    payload = {
        "email": email,
        "email_confirm": True,
        "user_metadata": metadata,
        "app_metadata": {
            "provider": providers[0],
            "providers": providers,
            "looma_user_id": row["id"],
        },
    }
    password_hash = row["password_hash"] or ""
    if password_hash.startswith("$2"):
        payload["password_hash"] = password_hash
    status, body = _request(f"{base}/auth/v1/admin/users", secret, "POST", payload)
    if status in (200, 201):
        mode = "created_with_hash" if "password_hash" in payload else "created"
        return user_id_of(body), mode
    if "password_hash" in payload and status in (400, 422):
        payload.pop("password_hash")
        status, body = _request(f"{base}/auth/v1/admin/users", secret, "POST", payload)
        if status in (200, 201):
            return user_id_of(body), "created_without_hash"
    raise RuntimeError(f"create failed HTTP {status}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="backend/data/looma.db")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_SECRET_KEY"]
    existing = list_users(base, secret)
    by_looma = {}
    for user in existing:
        looma_id = ((user.get("app_metadata") or {}).get("looma_user_id") or "").strip()
        if looma_id and user.get("id"):
            by_looma[looma_id] = user["id"]

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT id, email, password_hash, wechat_openid, name, supabase_uid
           FROM users ORDER BY created_at"""
    ).fetchall()

    counts = {
        "already": 0,
        "linked_existing": 0,
        "created": 0,
        "created_with_hash": 0,
        "created_without_hash": 0,
        "skipped": 0,
        "failed": 0,
    }
    for row in rows:
        if row["supabase_uid"]:
            counts["already"] += 1
            continue
        email, kind = classify(row)
        if kind == "skip":
            counts["skipped"] += 1
            continue
        supabase_id = by_looma.get(row["id"])
        mode = "linked_existing"
        if not supabase_id:
            if args.dry_run:
                counts["created"] += 1
                continue
            try:
                supabase_id, mode = create_user(base, secret, email, kind, row)
            except Exception:
                counts["failed"] += 1
                continue
        if not supabase_id:
            counts["failed"] += 1
            continue
        if not args.dry_run:
            con.execute(
                "UPDATE users SET supabase_uid = ?, updated_at = datetime('now') WHERE id = ?",
                (supabase_id, row["id"]),
            )
            con.commit()
        counts[mode] = counts.get(mode, 0) + 1
        by_looma[row["id"]] = supabase_id

    bound = con.execute(
        "SELECT COUNT(*) FROM users WHERE supabase_uid IS NOT NULL AND trim(supabase_uid) != ''"
    ).fetchone()[0]
    print(json.dumps({"looma_users": len(rows), "bound": bound, **counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
