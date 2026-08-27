"""
Poetry routes tests — browse, search, random, stats, detail.
Run: pytest tests/test_poetry.py -v
"""
import pytest
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def app():
    """Create a test app with a temporary database file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    os.environ["DATABASE_PATH"] = tmp.name
    os.environ["JWT_SECRET"] = "test-jwt-secret-for-local-testing-only-2026"
    os.environ["SECRET_KEY"] = "test-flask-secret"
    from src.app import create_app
    _app = create_app("testing")
    yield _app

    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app, client):
    """Trigger DB init (before_request) and return the DatabaseManager."""
    # DB is initialized on first request via before_request
    client.get("/health")  # trigger init
    return app._db


# ── Manager CRUD tests ──

class TestPoetryManager:
    def test_insert_poem(self, db):
        id = db.insert_poem(
            title="静夜思", author="李白", dynasty="唐",
            theme="思乡", content="床前明月光，疑是地上霜。举头望明月，低头思故乡。",
        )
        assert id > 0

    def test_insert_duplicate_skipped(self, db):
        id1 = db.insert_poem(title="静夜思", author="李白", dynasty="唐", content="...")
        assert id1 > 0
        # Same title — INSERT OR IGNORE means the row is not inserted,
        # but lastrowid may still return the previous successful insert id.
        # The key check: total count should NOT increase.
        count_before = db.count_poems()
        db.insert_poem(title="静夜思", author="李白", dynasty="唐", content="...")
        count_after = db.count_poems()
        assert count_before == count_after

    def test_bulk_insert_poems(self, db):
        poems = [
            {"title": "春晓", "author": "孟浩然", "dynasty": "唐", "content": "春眠不觉晓"},
            {"title": "登鹳雀楼", "author": "王之涣", "dynasty": "唐", "content": "白日依山尽"},
            {"title": "悯农", "author": "李绅", "dynasty": "唐", "content": "锄禾日当午"},
        ]
        count = db.bulk_insert_poems(poems)
        assert count == 3

    def test_get_poem_by_id(self, db):
        id = db.insert_poem(title="望庐山瀑布", author="李白", dynasty="唐", content="日照香炉生紫烟")
        poem = db.get_poem_by_id(id)
        assert poem is not None
        assert poem["title"] == "望庐山瀑布"
        assert poem["author"] == "李白"

    def test_get_poems_with_filter(self, db):
        db.bulk_insert_poems([
            {"title": "将进酒", "author": "李白", "dynasty": "唐", "content": "君不见黄河之水天上来"},
            {"title": "赤壁赋", "author": "苏轼", "dynasty": "宋", "content": "壬戌之秋"},
            {"title": "望岳", "author": "杜甫", "dynasty": "唐", "content": "岱宗夫如何"},
        ])
        # Filter by dynasty
        result = db.get_poems(dynasty="唐")
        assert result["total"] >= 2
        assert all(p["dynasty"] == "唐" for p in result["items"])

    def test_get_poems_with_keyword(self, db):
        db.insert_poem(title="月夜忆舍弟", author="杜甫", dynasty="唐", content="戍鼓断人行")
        result = db.get_poems(keyword="杜甫")
        assert result["total"] >= 1

    def test_get_poems_pagination(self, db):
        for i in range(25):
            db.insert_poem(title=f"测试诗{i}", author="测试", dynasty="汉", content=f"内容{i}")
        result = db.get_poems(dynasty="汉", page=1, per_page=10)
        assert len(result["items"]) == 10
        assert result["total"] >= 25
        result2 = db.get_poems(dynasty="汉", page=2, per_page=10)
        assert len(result2["items"]) == 10

    def test_get_random_poems(self, db):
        for i in range(10):
            db.insert_poem(title=f"随机诗{i}", author="随机", dynasty="随机", content=f"内容{i}")
        poems = db.get_random_poems(3)
        assert len(poems) == 3

    def test_count_poems(self, db):
        db.bulk_insert_poems([
            {"title": "诗A", "author": "A", "content": "a"},
            {"title": "诗B", "author": "B", "content": "b"},
        ])
        count = db.count_poems()
        assert count >= 2

    def test_get_poetry_stats(self, db):
        db.bulk_insert_poems([
            {"title": "唐诗1", "author": "李白", "dynasty": "唐", "theme": "思乡", "content": "..."},
            {"title": "宋诗1", "author": "苏轼", "dynasty": "宋", "theme": "咏物", "content": "..."},
            {"title": "唐诗2", "author": "杜甫", "dynasty": "唐", "theme": "思乡", "content": "..."},
        ])
        stats = db.get_poetry_stats()
        assert stats["total"] >= 3
        assert any(d["name"] == "唐" for d in stats["dynasties"])


# ── Route tests ──

class TestPoetryRoutes:
    def test_browse_endpoint(self, client, db):
        db.insert_poem(title="静夜思", author="李白", dynasty="唐", content="床前明月光")
        resp = client.get("/v1/poetry/browse")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 1

    def test_browse_with_dynasty_filter(self, client, db):
        db.bulk_insert_poems([
            {"title": "李白诗", "author": "李白", "dynasty": "唐", "content": "..."},
            {"title": "苏轼诗", "author": "苏轼", "dynasty": "宋", "content": "..."},
        ])
        resp = client.get("/v1/poetry/browse?dynasty=唐")
        data = resp.get_json()
        assert data["total"] >= 1
        assert all(p["dynasty"] == "唐" for p in data["items"])

    def test_browse_pagination(self, client, db):
        for i in range(5):
            db.insert_poem(title=f"分页诗{i}", author="A", dynasty="汉", content=f"内容{i}")
        resp = client.get("/v1/poetry/browse?page=1&per_page=3")
        data = resp.get_json()
        assert len(data["items"]) == 3
        assert data["page"] == 1

    def test_search_endpoint_missing_query(self, client):
        resp = client.get("/v1/poetry/search")
        assert resp.status_code == 400

    def test_search_endpoint_with_query(self, client, db):
        db.insert_poem(title="望庐山瀑布", author="李白", dynasty="唐", content="日照香炉生紫烟")
        # ChromaDB won't work in test, but SQLite fallback should kick in
        resp = client.get("/v1/poetry/search?q=李白&n=3")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["query"] == "李白"

    def test_get_single_poem(self, client, db):
        id = db.insert_poem(title="春晓", author="孟浩然", dynasty="唐", content="春眠不觉晓")
        resp = client.get(f"/v1/poetry/{id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "春晓"
        assert data["content"] == "春眠不觉晓"

    def test_get_nonexistent_poem(self, client):
        resp = client.get("/v1/poetry/999999")
        assert resp.status_code == 404

    def test_random_endpoint(self, client, db):
        for i in range(5):
            db.insert_poem(title=f"随机诗{i}", author="随机", dynasty="随机", content=f"内容{i}")
        resp = client.get("/v1/poetry/random?count=3")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] <= 3

    def test_stats_endpoint(self, client, db):
        db.insert_poem(title="诗1", author="A", dynasty="唐", content="...")
        resp = client.get("/v1/poetry/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total" in data
        assert "dynasties" in data


def _register(client, email="challenge@test.com"):
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "secret123", "name": "Translator"},
    )
    assert resp.status_code in (200, 201)
    data = resp.get_json()
    return data["access_token"]


class TestPoetryChallenge:
    def test_current_empty_library(self, client, db):
        resp = client.get("/v1/poetry/challenge/current")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["error"] == "library_empty"

    def test_current_seeds_round(self, client, db):
        db.insert_poem(
            title="静夜思",
            author="李白",
            dynasty="唐",
            content="床前明月光，疑是地上霜。举头望明月，低头思故乡。",
        )
        resp = client.get("/v1/poetry/challenge/current")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["round"]["week_key"]
        assert data["poem"]["title"] == "静夜思"
        assert data["my_entry"] is None

    def test_submit_requires_auth(self, client, db):
        db.insert_poem(title="春晓", author="孟浩然", dynasty="唐", content="春眠不觉晓")
        resp = client.post(
            "/v1/poetry/challenge/entries",
            json={
                "translation": "Spring morning — birds everywhere.",
                "license_accepted": True,
            },
        )
        assert resp.status_code == 401

    def test_submit_and_update(self, client, db):
        db.insert_poem(
            title="登鹳雀楼",
            author="王之涣",
            dynasty="唐",
            content="白日依山尽，黄河入海流。欲穷千里目，更上一层楼。",
        )
        token = _register(client, "xdy@test.com")
        headers = {"Authorization": f"Bearer {token}"}

        cur = client.get("/v1/poetry/challenge/current", headers=headers)
        assert cur.status_code == 200
        round_id = cur.get_json()["round"]["id"]

        resp = client.post(
            "/v1/poetry/challenge/entries",
            headers=headers,
            json={
                "round_id": round_id,
                "translation": "The sun sinks behind the hills; the Yellow River runs to the sea.",
                "note": "Tried for cadence.",
                "license_accepted": True,
            },
        )
        assert resp.status_code == 200
        entry = resp.get_json()["entry"]
        assert "Yellow River" in entry["translation"]

        resp2 = client.post(
            "/v1/poetry/challenge/entries",
            headers=headers,
            json={
                "round_id": round_id,
                "translation": "Daylight dies on the hills; the Yellow River joins the sea.",
                "license_accepted": True,
            },
        )
        assert resp2.status_code == 200
        assert "Daylight dies" in resp2.get_json()["entry"]["translation"]

        again = client.get("/v1/poetry/challenge/current", headers=headers)
        assert again.get_json()["my_entry"]["translation"].startswith("Daylight")
