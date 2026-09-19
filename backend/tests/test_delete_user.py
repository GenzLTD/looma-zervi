"""
delete_user 回归测试 —— 账号清理路径。

Run: pytest tests/test_delete_user.py -v

背景（2026-09-16）：生产 users 表累积了 210 个测试账号，需要批量清理。
库内 34 张表以**裸外键**引用 users(id)，没有任何 ON DELETE CASCADE，而连接
固定开启 PRAGMA foreign_keys=ON（见 DatabaseManager._connect）—— 因此
`DELETE FROM users` 会被外键约束直接拒绝，必须先把子行按反向拓扑序删干净。

本文件锁死三处最容易改坏的地方：

1. 裸 DELETE 不可行；delete_user 必须真的把依赖行清干净（含孙表）。
2. NON_FK_USER_TABLES（query_logs / product_events / audit_logs）不持有外键，
   沿外键遍历**永远覆盖不到** —— 漏删会留下孤儿行，永久污染用量统计。
3. 孙表（match_report_items 经 match_reports 关联）单趟删除覆盖不到，
   必须迭代到不动点。

另外锁死管理端接口的安全边界：只认测试域名后缀、永不触碰 seed 账号。
"""
import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db.manager import (  # noqa: E402
    BETA_USERS,
    NON_FK_USER_TABLES,
    TEST_EMAIL_SUFFIXES,
    DatabaseManager,
)


# ── fixtures / helpers ──

@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    manager = DatabaseManager(path)
    manager.init_schema()
    yield manager
    os.unlink(path)


def _seed_children(db, uid, tag="a"):
    """写入一条覆盖各类依赖的足迹，返回期望各表被删的行数。

    含三类关键样本：
      * 普通子表          consents / quota_records / trust_memories / game_profiles
      * 孙表（非直接引用） match_report_items 仅是 match_reports 的子表
      * 无外键表          query_logs / product_events（遍历覆盖不到）
    """
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO consents (id, user_id, scope) VALUES (?, ?, ?)",
            ("consent-%s" % tag, uid, "ask_rag"),
        )
        conn.execute(
            "INSERT INTO quota_records (user_id, resource, date, used, daily_limit)"
            " VALUES (?, ?, ?, ?, ?)",
            (uid, "ask", "2026-09-16", 1, 20),
        )
        conn.execute(
            "INSERT INTO trust_memories (id, user_id, session_type, session_id, memory_content)"
            " VALUES (?, ?, ?, ?, ?)",
            ("tm-%s" % tag, uid, "ask", "s-%s" % tag, "{}"),
        )
        conn.execute(
            "INSERT INTO game_profiles (id, user_id, personality_type) VALUES (?, ?, ?)",
            ("gp-%s" % tag, uid, "星云艺术家"),
        )
        conn.execute(
            "INSERT INTO match_reports (id, user_id) VALUES (?, ?)",
            ("mr-%s" % tag, uid),
        )
        # 孙表：只经由 match_reports 关联，没有指向 users 的外键
        conn.execute(
            "INSERT INTO match_report_items (id, report_id, job_title, company_name)"
            " VALUES (?, ?, ?, ?)",
            ("mri-%s" % tag, "mr-%s" % tag, "后端工程师", "某公司"),
        )
        conn.execute(
            "INSERT INTO fleets (id, name, captain_id) VALUES (?, ?, ?)",
            ("fleet-%s" % tag, "测试舰队", uid),
        )
        conn.execute(
            "INSERT INTO fleet_members (id, fleet_id, user_id) VALUES (?, ?, ?)",
            ("fm-%s" % tag, "fleet-%s" % tag, uid),
        )
        # 无外键表 —— 沿外键遍历永远找不到
        conn.execute(
            "INSERT INTO query_logs (query_text, provider, user_id, created_at)"
            " VALUES (?, ?, ?, ?)",
            ("测试查询", "deepseek", uid, "2026-09-16 00:00:00"),
        )
        conn.execute(
            "INSERT INTO product_events (event_name, user_id, success) VALUES (?, ?, ?)",
            ("e2e_register", uid, 1),
        )
        # 审计轨迹：默认保留
        conn.execute(
            "INSERT INTO audit_logs (id, actor, action, resource_type) VALUES (?, ?, ?, ?)",
            ("al-%s" % tag, uid, "register", "user"),
        )


def _footprint(db, uid):
    """uid 在库内任意表任意列中出现的次数 -> {(table, col): n}。"""
    hits = {}
    with db.get_conn() as conn:
        tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
                " AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table in tables:
            for col in [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]:
                try:
                    n = conn.execute(
                        "SELECT COUNT(*) FROM %s WHERE %s = ?" % (table, col), (uid,)
                    ).fetchone()[0]
                except sqlite3.Error:
                    continue
                if n:
                    hits[(table, col)] = n
    return hits


def _rows(db, sql, params=()):
    with db.get_conn() as conn:
        return conn.execute(sql, params).fetchone()[0]


# ── delete_user ──

def test_naive_delete_is_rejected_by_foreign_keys(db):
    """证明 delete_user 存在的理由：裸 DELETE 会被外键拒绝且事务回滚。"""
    uid = db.create_user(email="naive@test.local")
    _seed_children(db, uid)

    with pytest.raises(sqlite3.IntegrityError):
        with db.get_conn() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (uid,))

    # get_conn 在异常时 rollback —— 用户必须仍在库里
    assert db.get_user_by_id(uid) is not None


def test_delete_user_removes_user_and_all_dependents(db):
    uid = db.create_user(email="wipe@test.local")
    _seed_children(db, uid)
    assert _footprint(db, uid), "前置条件：应当已写入足迹"

    result = db.delete_user(uid)

    assert result["user_id"] == uid
    assert result["deleted"]["users"] == 1
    assert db.get_user_by_id(uid) is None

    leftover = {k: v for k, v in _footprint(db, uid).items() if k[0] != "audit_logs"}
    assert leftover == {}, "存在孤儿行: %s" % leftover


def test_delete_user_sweeps_tables_without_foreign_keys(db):
    """query_logs / product_events 无外键 —— 必须靠 NON_FK_USER_TABLES 显式补扫。"""
    uid = db.create_user(email="nonfk@test.local")
    _seed_children(db, uid)

    result = db.delete_user(uid)

    assert result["deleted"]["query_logs"] == 1
    assert result["deleted"]["product_events"] == 1
    assert _rows(db, "SELECT COUNT(*) FROM query_logs WHERE user_id = ?", (uid,)) == 0
    assert _rows(db, "SELECT COUNT(*) FROM product_events WHERE user_id = ?", (uid,)) == 0


def test_delete_user_reaches_grandchildren(db):
    """match_report_items 只经 match_reports 关联，单趟遍历覆盖不到。"""
    uid = db.create_user(email="grandchild@test.local")
    _seed_children(db, uid)

    result = db.delete_user(uid)

    assert "match_reports" in result["deleted"]
    assert "match_report_items" in result["deleted"], (
        "孙表未被删除 —— 反向拓扑遍历没有迭代到不动点"
    )
    assert _rows(db, "SELECT COUNT(*) FROM match_report_items") == 0


def test_delete_user_handles_user_without_children(db):
    """无依赖行的用户也要能正常删除（边界：空 footprints）。"""
    uid = db.create_user(email="bare@test.local")

    result = db.delete_user(uid)

    assert result["deleted"] == {"users": 1}
    assert db.get_user_by_id(uid) is None


def test_audit_logs_retained_by_default_purged_on_demand(db):
    """审计轨迹默认保留；显式 include_audit=True 才清除。"""
    uid = db.create_user(email="audit@test.local")
    _seed_children(db, uid)

    db.delete_user(uid)
    assert _rows(db, "SELECT COUNT(*) FROM audit_logs WHERE actor = ?", (uid,)) == 1, (
        "默认应保留审计轨迹"
    )

    uid2 = db.create_user(email="audit2@test.local")
    _seed_children(db, uid2, tag="b")
    result = db.delete_user(uid2, include_audit=True)

    assert result["deleted"].get("audit_logs") == 1
    assert _rows(db, "SELECT COUNT(*) FROM audit_logs WHERE actor = ?", (uid2,)) == 0


def test_delete_user_leaves_other_users_untouched(db):
    """清理一个账号不得影响其他账号。"""
    keep = db.create_user(email="keep@test.local")
    _seed_children(db, keep, tag="keep")
    keep_before = _footprint(db, keep)

    victim = db.create_user(email="victim@test.local")
    _seed_children(db, victim, tag="victim")

    db.delete_user(victim)

    assert db.get_user_by_id(keep) is not None
    assert _footprint(db, keep) == keep_before


def test_database_stays_consistent_after_delete(db):
    uid = db.create_user(email="consistency@test.local")
    _seed_children(db, uid)

    db.delete_user(uid)

    with db.get_conn() as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_non_fk_table_list_covers_expected_tables():
    """NON_FK_USER_TABLES 是硬编码清单 —— 表被改名/新增时应在此暴露。"""
    names = {t[0] for t in NON_FK_USER_TABLES}
    assert {"query_logs", "product_events", "audit_logs"} <= names


# ── 管理端接口 ──

def _auth_headers(token):
    return {"Authorization": "Bearer %s" % token}


def _register(client, email):
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "secret123", "name": "Test"},
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["access_token"]


@pytest.fixture
def app_db(app, client):
    """返回 app 所用的 DatabaseManager。

    app._db 由 before_request 懒初始化（src/app.py:434）—— 必须先打一次请求，
    否则该属性还不存在。同 tests/test_poetry.py 的 db fixture 用法。
    """
    client.get("/health")
    return app._db


def _register_admin(client, db, email="ops-admin@looma.test"):
    """注册后把 role 提升为 admin。

    require_auth 每次请求都从库里读 role（decorators.py:69），
    因此提升后沿用原 token 即可，无需重新登录。
    """
    token = _register(client, email)
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET role = 'admin' WHERE email = ?", (email,))
    return token


def test_purge_requires_admin(app, client):
    token = _register(client, "plain-user@looma.test")

    resp = client.post(
        "/v1/admin/test-accounts/purge", headers=_auth_headers(token), json={"dry_run": True}
    )

    assert resp.status_code == 403


def test_purge_rejects_non_test_suffix(app_db, client):
    """白名单之外的后缀必须被拒 —— 这是「不可能误删真人账号」的第一道保证。"""
    token = _register_admin(client, app_db)

    resp = client.post(
        "/v1/admin/test-accounts/purge",
        headers=_auth_headers(token),
        json={"suffixes": ["@gmail.com"]},
    )

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["disallowed"] == ["@gmail.com"]
    assert "@test.local" in body["allowed"]


def test_purge_dry_run_does_not_mutate(app_db, client):
    db = app_db
    uid = db.create_user(email="e2e-dryrun@test.local")
    _seed_children(db, uid, tag="dry")
    token = _register_admin(client, db)

    resp = client.post(
        "/v1/admin/test-accounts/purge", headers=_auth_headers(token), json={"dry_run": True}
    )

    assert resp.status_code == 200
    assert resp.get_json()["matched"] == 1
    assert db.get_user_by_id(uid) is not None, "dry_run 不得改动数据"


def test_purge_removes_test_accounts_and_spares_real_ones(app_db, client):
    db = app_db
    victim = db.create_user(email="e2e-apply@test.local")
    _seed_children(db, victim, tag="apply")
    # 非测试域名：purge 绝不该碰
    real = db.create_user(email="someone@qq.com")
    _seed_children(db, real, tag="real")
    token = _register_admin(client, db)

    resp = client.post(
        "/v1/admin/test-accounts/purge", headers=_auth_headers(token), json={}
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["purged"] == 1
    assert body["failed"] == 0
    assert db.get_user_by_id(victim) is None
    assert db.get_user_by_id(real) is not None, "真人域名账号被误删"
    assert _rows(db, "SELECT COUNT(*) FROM query_logs WHERE user_id = ?", (real,)) == 1


def test_purge_never_touches_seeded_beta_users(app_db, client):
    """seed 账号删了会被重新 seed，属白删 —— 接口必须显式跳过。"""
    db = app_db
    db.seed_beta_users()
    seeded = [db.get_user_by_email(u["email"]) for u in BETA_USERS]
    assert all(seeded), "前置条件：seed 账号应已创建"
    token = _register_admin(client, db)

    resp = client.post(
        "/v1/admin/test-accounts/purge", headers=_auth_headers(token), json={}
    )

    assert resp.status_code == 200
    for u in BETA_USERS:
        assert db.get_user_by_email(u["email"]) is not None, (
            "seed 账号 %s 被误删" % u["email"]
        )


def test_suffix_whitelist_matches_manager_constant():
    """接口权限来自这个常量 —— 它被改动时测试必须跟着醒。"""
    assert "@test.local" in TEST_EMAIL_SUFFIXES
    assert "@gmail.com" not in TEST_EMAIL_SUFFIXES
    assert all(s.startswith("@") for s in TEST_EMAIL_SUFFIXES)


# ── paid 订单护栏（2026-09-19：orders 落在删除拓扑内，不设护栏会连
#    真金白银订单一起级联清掉；对齐 Stripe 不允许删除有支付历史的客户）──


def _seed_order(db, uid, out_trade_no, status="pending", amount=0.0, currency="CNY"):
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO orders (id, user_id, plan_id, tier, amount, currency,"
            " out_trade_no, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("order-" + out_trade_no, uid, "pro_monthly", "pro", amount,
             currency, out_trade_no, status),
        )


def test_delete_user_blocked_by_paid_order(db):
    """存在 paid 订单 → 一票否决，用户与依赖行全不动。"""
    from src.db.manager import PaidOrderBlockedError

    uid = db.create_user(email="paid-user@test.local")
    _seed_children(db, uid, tag="paid")
    _seed_order(db, uid, "LOOMA-PAID-001", status="paid", amount=9.9)

    with pytest.raises(PaidOrderBlockedError) as excinfo:
        db.delete_user(uid)

    assert excinfo.value.orders[0]["out_trade_no"] == "LOOMA-PAID-001"
    assert db.get_user_by_id(uid) is not None, "护栏触发时用户必须原地不动"
    assert _rows(db, "SELECT COUNT(*) FROM orders WHERE user_id = ?", (uid,)) == 1


def test_refunded_order_also_blocks(db):
    """refunded 同样存在真实支付历史（transaction_id / paid_at），必须一并拦。"""
    from src.db.manager import PaidOrderBlockedError

    uid = db.create_user(email="refunded@test.local")
    _seed_order(db, uid, "LOOMA-REFUND-001", status="refunded", amount=9.9)

    with pytest.raises(PaidOrderBlockedError):
        db.delete_user(uid)
    assert db.get_user_by_id(uid) is not None


def test_pending_orders_do_not_block(db):
    """pending / expired 属无资金流水，不拦——随用户级联删除。"""
    uid = db.create_user(email="pending-only@test.local")
    _seed_children(db, uid, tag="po")
    _seed_order(db, uid, "LOOMA-PENDING-001", status="pending", amount=9.9)
    _seed_order(db, uid, "LOOMA-EXPIRED-001", status="expired", amount=9.9)

    result = db.delete_user(uid)

    assert db.get_user_by_id(uid) is None
    assert result["deleted"]["orders"] == 2


def test_list_paid_orders_returns_full_detail(db):
    """护栏明细要够运维定位：单号 / 金额 / 币种 / 状态 / 支付时间。"""
    uid = db.create_user(email="detail@test.local")
    _seed_order(db, uid, "LOOMA-PAID-002", status="paid", amount=1.99, currency="USD")
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE orders SET paid_at = '2026-09-19T00:00:00'"
            " WHERE out_trade_no = 'LOOMA-PAID-002'"
        )

    orders = db.list_paid_orders(uid)

    assert len(orders) == 1
    o = orders[0]
    assert o["out_trade_no"] == "LOOMA-PAID-002"
    assert o["amount"] == 1.99
    assert o["currency"] == "USD"
    assert o["status"] == "paid"
    assert o["paid_at"] == "2026-09-19T00:00:00"


def test_purge_dry_run_reports_paid_breakdown(app_db, client):
    """dry_run 必须把 paid 挡板算清楚：matched / eligible / blocked_by_paid。"""
    db = app_db
    blocked = db.create_user(email="paid-target@test.local")
    _seed_order(db, blocked, "LOOMA-DRY-PAID-1", status="paid", amount=9.9)
    free = db.create_user(email="free-target@test.local")
    token = _register_admin(client, db)

    resp = client.post(
        "/v1/admin/test-accounts/purge", headers=_auth_headers(token), json={"dry_run": True}
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["matched"] == 2
    assert body["eligible"] == 1
    assert body["blocked_by_paid"] == 1
    assert body["blocked_details"][0]["email"] == "paid-target@test.local"
    assert body["blocked_details"][0]["paid_orders"][0]["out_trade_no"] == "LOOMA-DRY-PAID-1"
    assert db.get_user_by_id(blocked) is not None, "dry_run 不得改动数据"


def test_purge_blocks_users_with_paid_orders(app_db, client):
    """实跑：paid 用户被单独跳过不连坐，其余测试账号正常清理。"""
    db = app_db
    blocked = db.create_user(email="paid-run@test.local")
    _seed_children(db, blocked, tag="pr")
    _seed_order(db, blocked, "LOOMA-RUN-PAID-1", status="paid", amount=9.9)
    victim = db.create_user(email="clean-run@test.local")
    _seed_children(db, victim, tag="cr")
    token = _register_admin(client, db)

    resp = client.post(
        "/v1/admin/test-accounts/purge", headers=_auth_headers(token), json={}
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["purged"] == 1
    assert body["blocked_by_paid"] == 1
    assert db.get_user_by_id(blocked) is not None, "paid 用户被误删"
    assert _rows(db, "SELECT COUNT(*) FROM orders WHERE user_id = ?", (blocked,)) == 1
    assert db.get_user_by_id(victim) is None


# ── 按订单清理（不动用户；与 paid 护栏配套）──


def test_purge_test_orders_requires_prefix(app_db, client):
    token = _register_admin(client, app_db)

    resp = client.post(
        "/v1/admin/test-orders/purge", headers=_auth_headers(token), json={}
    )

    assert resp.status_code == 400
    assert "prefixes" in resp.get_json()["message"]


def test_purge_test_orders_rejects_paid_status(app_db, client):
    """paid/refunded 传入状态白名单直接 400——结构上不可能清掉真金订单。"""
    token = _register_admin(client, app_db)

    resp = client.post(
        "/v1/admin/test-orders/purge",
        headers=_auth_headers(token),
        json={"prefixes": ["LOOMA-WIN-"], "statuses": ["paid"]},
    )

    assert resp.status_code == 400
    assert "paid" in resp.get_json()["message"]


def test_purge_test_orders_by_prefix(app_db, client):
    """按前缀清测试订单：命中删除、paid 同前缀跳过、users 分毫不动。"""
    db = app_db
    uid = db.create_user(email="order-owner@test.local")
    _seed_order(db, uid, "LOOMA-WIN-NOORDER-1", status="pending", amount=0)
    _seed_order(db, uid, "LOOMA-WIN-PAID-1", status="paid", amount=9.9)
    _seed_order(db, uid, "OTHER-PREFIX-1", status="pending", amount=0)
    token = _register_admin(client, db)

    # dry_run：只报不删
    resp = client.post(
        "/v1/admin/test-orders/purge",
        headers=_auth_headers(token),
        json={"prefixes": ["LOOMA-WIN-"], "dry_run": True},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["matched"] == 1
    assert body["deleted"] == 0
    assert body["skipped_non_purgeable"] == 1  # 同前缀的 paid 单
    assert _rows(db, "SELECT COUNT(*) FROM orders") == 3, "dry_run 不得改动数据"

    # 实跑：只删命中的 pending 单
    resp = client.post(
        "/v1/admin/test-orders/purge",
        headers=_auth_headers(token),
        json={"prefixes": ["LOOMA-WIN-"]},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["matched"] == 1
    assert body["deleted"] == 1

    remaining = {r[0] for r in _rows_list(db, "SELECT out_trade_no FROM orders")}
    assert remaining == {"LOOMA-WIN-PAID-1", "OTHER-PREFIX-1"}
    assert db.get_user_by_id(uid) is not None, "按订单清理不得动用户"


def test_purge_test_orders_zero_amount_only(app_db, client):
    """zero_amount_only：同前缀 pending 里只清零元单，非零单留下。"""
    db = app_db
    uid = db.create_user(email="zero@test.local")
    _seed_order(db, uid, "LOOMA-Z-1", status="pending", amount=0)
    _seed_order(db, uid, "LOOMA-Z-2", status="pending", amount=9.9)
    token = _register_admin(client, db)

    resp = client.post(
        "/v1/admin/test-orders/purge",
        headers=_auth_headers(token),
        json={"prefixes": ["LOOMA-Z-"], "zero_amount_only": True},
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["matched"] == 1
    assert body["deleted"] == 1
    remaining = {r[0] for r in _rows_list(db, "SELECT out_trade_no FROM orders")}
    assert remaining == {"LOOMA-Z-2"}


def _rows_list(db, sql):
    with db.get_conn() as conn:
        return conn.execute(sql).fetchall()
