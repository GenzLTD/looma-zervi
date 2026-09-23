"""多租户 API 层最小防线 —— columns/articles 归属过滤测试。

对齐 DB 层 19 项探针的 API 版：
  - 跨驾驶员资源一律 404（不泄露存在性）
  - 挂他人专栏 → 403（API 层先行拦截，复合外键兜底）
  - role=user 无法进入 driver 空间（403）
"""
import uuid

import pytest


def _register_and_login(client, email, password="password123"):
    resp = client.post("/v1/auth/register",
                       json={"email": email, "password": password})
    assert resp.status_code in (200, 201), resp.get_data(as_text=True)
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _promote_to_driver(app, email):
    with app._db.get_conn() as conn:
        conn.execute("UPDATE users SET role='driver' WHERE email=?", (email,))


def _make_driver(client, app, prefix):
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@test.local"
    headers = _register_and_login(client, email)
    _promote_to_driver(app, email)
    return headers


def _make_column(client, headers, slug):
    resp = client.post("/v1/driver/columns", headers=headers,
                       json={"slug": slug, "name": f"col-{slug}"})
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()["column"]


def test_user_role_cannot_access_driver_space(client):
    headers = _register_and_login(client, f"user-{uuid.uuid4().hex[:8]}@test.local")
    resp = client.get("/v1/driver/columns", headers=headers)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "forbidden"


def test_no_token_is_401(client):
    resp = client.get("/v1/driver/columns")
    assert resp.status_code == 401


def test_column_crud_and_duplicate_slug(client, app):
    headers = _make_driver(client, app, "drv-a")
    col = _make_column(client, headers, "shop")
    assert col["driver_id"] and col["slug"] == "shop"

    # 同驾驶员同 slug → 409
    resp = client.post("/v1/driver/columns", headers=headers,
                       json={"slug": "shop", "name": "dup"})
    assert resp.status_code == 409

    # PATCH 本人专栏
    resp = client.patch(f"/v1/driver/columns/{col['id']}", headers=headers,
                        json={"name": "改名书店"})
    assert resp.status_code == 200 and resp.get_json()["column"]["name"] == "改名书店"

    # DELETE 无内容专栏
    resp = client.delete(f"/v1/driver/columns/{col['id']}", headers=headers)
    assert resp.status_code == 200


def test_article_scoping_cross_driver_is_404(client, app):
    ha = _make_driver(client, app, "drv-a")
    hb = _make_driver(client, app, "drv-b")
    col_a = _make_column(client, ha, "shop")

    resp = client.post("/v1/driver/articles", headers=ha,
                       json={"title": "甲的文章", "slug": "art-1",
                             "content": "甲的内容", "column_id": col_a["id"]})
    assert resp.status_code == 201, resp.get_data(as_text=True)
    art = resp.get_json()["article"]

    # 乙读甲的文章 → 404（归属过滤，非本人视为不存在）
    assert client.get(f"/v1/driver/articles/{art['id']}", headers=hb).status_code == 404
    # 乙改甲的文章 → 404
    resp = client.patch(f"/v1/driver/articles/{art['id']}", headers=hb,
                        json={"title": "篡改"})
    assert resp.status_code == 404
    # 乙删甲的文章 → 404
    assert client.delete(f"/v1/driver/articles/{art['id']}", headers=hb).status_code == 404
    # 甲仍能读到原文（未被篡改/删除）
    resp = client.get(f"/v1/driver/articles/{art['id']}", headers=ha)
    assert resp.status_code == 200 and resp.get_json()["article"]["title"] == "甲的文章"


def test_article_cannot_attach_to_others_column(client, app):
    ha = _make_driver(client, app, "drv-a")
    hb = _make_driver(client, app, "drv-b")
    col_a = _make_column(client, ha, "shop")

    # 乙把文章挂进甲的专栏 → API 层 403（复合外键兜底）
    resp = client.post("/v1/driver/articles", headers=hb,
                       json={"title": "乙的文章", "slug": "b-1",
                             "content": "乙的内容", "column_id": col_a["id"]})
    assert resp.status_code == 403
    # 专栏里没有乙的内容
    arts = client.get("/v1/driver/articles", headers=ha).get_json()["articles"]
    assert all(a["driver_id"] != "" for a in arts) and len(arts) == 0


def test_list_scoping_only_own_content(client, app):
    ha = _make_driver(client, app, "drv-a")
    hb = _make_driver(client, app, "drv-b")
    for h, slug in ((ha, "a-1"), (ha, "a-2"), (hb, "b-1")):
        resp = client.post("/v1/driver/articles", headers=h,
                           json={"title": f"t-{slug}", "slug": slug, "content": "x"})
        assert resp.status_code == 201

    a_arts = client.get("/v1/driver/articles", headers=ha).get_json()["articles"]
    b_arts = client.get("/v1/driver/articles", headers=hb).get_json()["articles"]
    assert {a["slug"] for a in a_arts} == {"a-1", "a-2"}
    assert {a["slug"] for a in b_arts} == {"b-1"}


def test_delete_column_with_content_is_409(client, app):
    ha = _make_driver(client, app, "drv-a")
    col = _make_column(client, ha, "shop")
    resp = client.post("/v1/driver/articles", headers=ha,
                       json={"title": "t", "slug": "s", "content": "c",
                             "column_id": col["id"]})
    assert resp.status_code == 201
    resp = client.delete(f"/v1/driver/columns/{col['id']}", headers=ha)
    assert resp.status_code == 409
