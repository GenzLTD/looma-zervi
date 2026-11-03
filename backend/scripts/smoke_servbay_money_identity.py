# -*- coding: utf-8 -*-
"""Smoke money-identity join against ServBay looma.db (not pytest tempfile).

Why not pytest: this hits the real ServBay sqlite ledger under data/looma.db;
pytest fixtures use a tempfile DB and cannot validate ServBay wiring / schema drift.

Exit codes: 0 PASS, 1 assertion FAIL, 2 environment / purge hygiene failure.
"""
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

DOMAIN = "@servbay-smoke.local"
OPENID_B = "servbay_wx_b"
EMAIL_A = f"join-a{DOMAIN}"
EMAIL_B = f"join-b{DOMAIN}"
EMAIL_STUB = f"stub-smoke{DOMAIN}"

db_path = ROOT / "data" / "looma.db"
if not db_path.exists():
    print("库文件不存在：先起一次 ServBay 后端或跑 migrate 再重试")
    print(f"  expected: {db_path}")
    sys.exit(2)

# Env before create_app (no post-create_app DATABASE_PATH placebo)
os.environ["DATABASE_PATH"] = str(db_path)
os.environ.setdefault("JWT_SECRET", secrets.token_hex(32))
os.environ["WECHAT_DEV_MODE"] = "true"
os.environ["PAYMENT_STUB_MODE"] = "true"
os.environ["DEPLOY_REGION"] = "CN"
os.environ["DEEPSEEK_API_KEY"] = "skip"
for k in (
    "WECHAT_MCHID", "WECHAT_APPID", "WECHAT_API_V3_KEY", "WECHAT_SERIAL_NO",
    "WECHAT_PRIVATE_KEY_PATH", "WECHAT_NOTIFY_URL", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
):
    os.environ.pop(k, None)

from src.app import create_app
from src.identity.ledger_subject import AmbiguousLedgerSubject, resolve_settlement_user_id


def count_smoke_users(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM users WHERE email LIKE ?",
        (f"%{DOMAIN}",),
    ).fetchone()[0]


def purge(db):
    """Delete DOMAIN smoke users and all FK-dependent rows.

    Returns (cleaned_rows, users_left, errors). Row-level failures are counted in
    `errors` instead of being swallowed, so the caller can fail loud (exit 2)
    rather than report PASS on a DB that was never actually cleaned.
    """
    cleaned = 0
    errors = 0
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM users WHERE email LIKE ?",
            (f"%{DOMAIN}",),
        ).fetchall()
        uids = [r[0] for r in rows]
        if not uids:
            return 0, 0, 0
        placeholders = ",".join("?" * len(uids))

        # Dynamic: every table whose FK points at users (avoids hardcode / fake names).
        try:
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' AND name != 'users'"
                ).fetchall()
            ]
        except Exception as e:
            print(f"WARN purge sqlite_master: {e}")
            errors += 1
            tables = []

        for table in tables:
            try:
                fks = conn.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()
            except Exception as e:
                print(f"WARN purge pragma foreign_key_list({table}): {e}")
                errors += 1
                continue
            # PRAGMA cols: id, seq, table, from, to, on_update, on_delete, match
            cols = sorted({fk[3] for fk in fks if fk[2] == "users" and fk[3]})
            for col in cols:
                try:
                    cur = conn.execute(
                        f'DELETE FROM "{table}" WHERE "{col}" IN ({placeholders})',
                        uids,
                    )
                    n = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
                    cleaned += n
                except Exception as e:
                    print(f"WARN purge delete {table}.{col}: {e}")
                    errors += 1

        try:
            conn.execute(
                f"UPDATE users SET wechat_openid=NULL WHERE id IN ({placeholders})",
                uids,
            )
        except Exception as e:
            print(f"WARN purge null wechat_openid: {e}")
            errors += 1
        try:
            cur = conn.execute(
                f"DELETE FROM users WHERE id IN ({placeholders})",
                uids,
            )
            cleaned += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        except Exception as e:
            print(f"WARN purge delete users: {e}")
            errors += 1

        left = count_smoke_users(conn)
    return cleaned, left, errors


def check(cond, label, passed, failed):
    if cond:
        print(f"OK  {label}")
        return passed + 1, failed
    print(f"FAIL {label}")
    return passed, failed + 1


app = create_app("testing")
app.config["PAYMENT_STUB_MODE"] = True

client = app.test_client()
r = client.get("/health")
print("health", r.status_code, r.get_json())

cfg_db = app.config.get("DATABASE_PATH")
cfg_norm = os.path.normcase(os.path.abspath(str(cfg_db)))
expect_norm = os.path.normcase(os.path.abspath(str(db_path)))
if cfg_norm != expect_norm:
    print(f"FATAL DATABASE_PATH mismatch: app.config={cfg_db!r} expected={str(db_path)!r}")
    sys.exit(2)

db = app._db

with db.get_conn() as conn:
    existing = count_smoke_users(conn)
print(f"TARGET DB: {db_path} existing_smoke_users={existing}")

n0, left0, err0 = purge(db)
print(f"purge(start) cleaned_rows={n0} users_left={left0} errors={err0}")
if left0 or err0:
    # Dirty DB would poison every later assertion (UNIQUE email/openid); fail now.
    print(f"FATAL purge(start) incomplete: users_left={left0} purge_errors={err0}")
    sys.exit(2)

passed = 0
failed = 0
n1, left1, err1 = 0, 0, 0
purge_crashed = False

try:
    # --- unit-ish on live db ---
    a = db.create_user(email=EMAIL_A, password_hash="x")
    b = db.create_user(email=EMAIL_B, password_hash="x")
    db.bind_wechat_to_user(b, OPENID_B)
    ambiguous_ok = False
    try:
        resolve_settlement_user_id(
            db, session_user_id=a, issuer="wechat", subject=OPENID_B
        )
    except AmbiguousLedgerSubject as e:
        ambiguous_ok = True
        print("OK conflict rejected:", e)
    passed, failed = check(ambiguous_ok, "AmbiguousLedgerSubject on foreign openid", passed, failed)

    # --- stub payment smoke ---
    resp = client.post("/v1/auth/register", json={"email": EMAIL_STUB, "password": "password123"})
    print("register", resp.status_code)
    body = resp.get_json() or {}
    token = body.get("access_token")
    user = body.get("user") or {}
    user_id = user.get("id")
    passed, failed = check(
        resp.status_code in (200, 201) and token and user_id,
        "register stub user",
        passed,
        failed,
    )
    auth = {"Authorization": f"Bearer {token}"} if token else {}

    resp = client.post(
        "/v1/payment/wechat/order?region=CN",
        json={"tier": "supporter"},
        headers=auth,
    )
    print("order", resp.status_code, resp.get_json())
    order_body = resp.get_json() or {}
    out_trade_no = order_body.get("out_trade_no")
    passed, failed = check(
        resp.status_code == 201 and out_trade_no,
        "wechat stub order 201",
        passed,
        failed,
    )

    resp = client.post(
        "/v1/payment/wechat/notify-simulate",
        json={"out_trade_no": out_trade_no},
    )
    print("notify-simulate", resp.status_code, resp.get_json())
    passed, failed = check(resp.status_code == 200, "notify-simulate 200", passed, failed)

    resp = client.get("/v1/payment/status", headers=auth)
    status = resp.get_json() or {}
    print("status", status)
    passed, failed = check(status.get("tier") == "supporter", "status tier=supporter", passed, failed)
    passed, failed = check(status.get("principal_sub") == user_id, "status principal_sub", passed, failed)
    passed, failed = check(status.get("user_id") == user_id, "status user_id", passed, failed)

    # foreign openid 409
    resp = client.post(
        "/v1/payment/wechat/order?region=CN",
        json={"tier": "pro", "trade_type": "JSAPI", "openid": OPENID_B},
        headers=auth,
    )
    print("foreign openid", resp.status_code, resp.get_json())
    passed, failed = check(resp.status_code == 409, "foreign openid 409", passed, failed)
finally:
    try:
        n1, left1, err1 = purge(db)
        print(f"purge(end) cleaned_rows={n1} users_left={left1} errors={err1}")
    except Exception as e:
        print(f"FATAL purge(end) crashed: {e}")
        purge_crashed = True

total = passed + failed
if total == 0:
    print("FAIL 0/0 (no checks ran)")
    sys.exit(1)
verdict = "PASS" if failed == 0 else "FAIL"
print(f"{verdict} {passed}/{total}")

# Hygiene outranks assertions: a leaky purge makes the next run red for the
# wrong reason, so report it separately with exit 2.
if purge_crashed or left1 or err1:
    print(f"FATAL purge(end) incomplete: users_left={left1} purge_errors={err1} crashed={purge_crashed}")
    sys.exit(2)
sys.exit(0 if failed == 0 else 1)
