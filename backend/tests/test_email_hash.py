"""
Email hash tests — T0 cross-service match (Bridge 2/3, PlanetX side).

Run: pytest tests/test_email_hash.py -v
"""
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db.manager import DatabaseManager, email_hash

# Canonical vector shared with DemoPPI (lib/signal-bridge/hash.ts).
# sha256("user@example.com") as lowercase hex.
VECTOR = "b4c9a289323b21a01c3e940f150eb9b8c542587f1abfd8f0e1cc1ffc5e475514"


def _tmp_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return tmp.name


def test_email_hash_fixed_vector():
    assert email_hash("user@example.com") == VECTOR


def test_email_hash_normalizes_case_and_whitespace():
    assert email_hash("User@Example.com") == VECTOR
    assert email_hash("  User@Example.com  ") == VECTOR


def test_email_hash_empty_returns_none():
    assert email_hash(None) is None
    assert email_hash("") is None
    assert email_hash("   ") is None


def test_create_user_writes_email_hash():
    path = _tmp_db()
    try:
        db = DatabaseManager(path)
        db.init_schema()
        uid = db.create_user(email="A@B.com", password_hash="x")
        u = db.get_user_by_id(uid)
        assert u["email_hash"] == email_hash("A@B.com")
    finally:
        os.unlink(path)


def test_get_user_by_email_hash_matches():
    path = _tmp_db()
    try:
        db = DatabaseManager(path)
        db.init_schema()
        db.create_user(email="match@example.com")
        u = db.get_user_by_email_hash(email_hash("match@example.com"))
        assert u is not None
        assert u["email"] == "match@example.com"
        # Normalized form resolves to the same user
        u2 = db.get_user_by_email_hash(email_hash("Match@Example.com"))
        assert u2 is not None
        assert u2["id"] == u["id"]
    finally:
        os.unlink(path)


def test_email_hash_null_for_miniprogram_user():
    path = _tmp_db()
    try:
        db = DatabaseManager(path)
        db.init_schema()
        uid = db.create_user(wechat_openid="wx_123")
        u = db.get_user_by_id(uid)
        assert u["email_hash"] is None
    finally:
        os.unlink(path)


def test_init_schema_backfill_is_idempotent():
    path = _tmp_db()
    try:
        db = DatabaseManager(path)
        db.init_schema()
        # Simulate a legacy row created before email_hash existed
        with db.get_conn() as conn:
            conn.execute(
                "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
                ("legacy1", "legacy@example.com", "x"),
            )
        # Migration should backfill the missing hash
        db.init_schema()
        u = db.get_user_by_email("legacy@example.com")
        assert u["email_hash"] == email_hash("legacy@example.com")
        # Re-running is idempotent — no error, no duplicate
        db.init_schema()
        u2 = db.get_user_by_email("legacy@example.com")
        assert u2["email_hash"] == email_hash("legacy@example.com")
    finally:
        os.unlink(path)
