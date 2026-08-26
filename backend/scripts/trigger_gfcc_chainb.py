#!/usr/bin/env python3
"""Mac-only: drive PlanetX (this looma-zervi process) to fan-out chain B.

Windows does **not** run THOMAS / PlanetX / DemoPPI. Their only job is
gfcc_kernel :5211 + querying signal_log.

This script:
  1. Boots PlanetX in-process (Flask test client, local sqlite)
  2. Registers a user and POST /v1/game/profile-sync  (real T3 egress path)
  3. Lets chain A try DemoPPI (likely down — expected, best-effort)
  4. Lets chain B POST the frozen envelope to GFCC_SIGNAL_INGEST_URL

Usage (from backend/):
  ./venv/bin/python scripts/trigger_gfcc_chainb.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.request
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

EMAIL = f"gfcc-chainb-{uuid.uuid4().hex[:8]}@thomas.local"


def main() -> int:
    os.chdir(BACKEND)
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.environ["DATABASE_PATH"] = tmp.name
    os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-local-testing-only-2026")
    os.environ.setdefault("SECRET_KEY", "dev-trigger-secret")
    os.environ.setdefault("FLASK_ENV", "testing")
    # Chain A may  fail if DemoPPI is not on :3000; do not block chain B.
    os.environ.setdefault("DEMOPPI_SIGNAL_INGEST_URL", "http://127.0.0.1:3000/api/signal/ingest")

    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env")

    os.environ.setdefault(
        "GFCC_SIGNAL_INGEST_URL",
        "http://127.0.0.1:5211/v1/signal-ingest",
    )

    gfcc_url = os.environ.get("GFCC_SIGNAL_INGEST_URL", "").strip()
    gfcc_secret = os.environ.get("SIGNAL_INGEST_SECRET", "").strip()
    if not gfcc_url or not gfcc_secret:
        print("GFCC_SIGNAL_INGEST_URL / SIGNAL_INGEST_SECRET missing in backend/.env")
        return 1

    captured: dict = {}
    real_urlopen = urllib.request.urlopen

    def wrapping_urlopen(req, timeout=5):
        url = getattr(req, "full_url", "") or ""
        if "5211" in url or "/v1/signal-ingest" in url:
            try:
                body = json.loads(req.data.decode("utf-8"))
            except Exception:
                body = {}
            captured["gfcc"] = {"url": url, "body": body}
        return real_urlopen(req, timeout=timeout)

    urllib.request.urlopen = wrapping_urlopen  # type: ignore[method-assign]

    from src.app import create_app
    from src.db.manager import email_hash

    app = create_app("testing")
    client = app.test_client()

    reg = client.post("/v1/auth/register", json={
        "email": EMAIL,
        "password": "password123",
        "name": "GFCC ChainB",
    })
    if reg.status_code not in (200, 201):
        print("register failed", reg.status_code, reg.get_json())
        return 1
    token = (reg.get_json() or {}).get("access_token")
    user_hash = email_hash(EMAIL)

    sync = client.post(
        "/v1/game/profile-sync",
        json={
            "personality_type": "星云艺术家",
            "personality_detail": '{"traits": ["creative"], "score": 0.87}',
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    print("profile-sync", sync.status_code, json.dumps(sync.get_json(), ensure_ascii=False))

    gfcc = captured.get("gfcc") or {}
    body = gfcc.get("body") or {}
    print()
    print("=== Mac trigger done (PlanetX = this looma-zervi). Windows only queries DB. ===")
    print(f"email            {EMAIL}")
    print(f"user_id_hash     {user_hash}")
    print(f"gfcc_url         {gfcc.get('url')}")
    print(f"signal_type      {body.get('signal_type')}")
    print(f"nonce            {body.get('nonce')}")
    print(f"payload          {json.dumps(body.get('payload'), ensure_ascii=False)}")
    print()
    print("Windows (data/memory.db):")
    print("  sqlite3 data/memory.db \\")
    print("    \"SELECT signal_id, signal_type, substr(user_id_hash,1,12), nonce, created_at")
    print("     FROM signal_log ORDER BY created_at DESC LIMIT 5;\"")
    if user_hash:
        print(f"  sqlite3 data/memory.db \"SELECT signal_id, signal_type, nonce, payload FROM signal_log WHERE user_id_hash='{user_hash}';\"")
    return 0 if body.get("nonce") else 2


if __name__ == "__main__":
    raise SystemExit(main())
