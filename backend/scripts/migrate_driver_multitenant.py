#!/usr/bin/env python3
"""
looma-zervi「驾驶员 / 多租户」P0 数据骨架迁移 —— SQLite 方言版

对应清单：~/Downloads/looma-zervi多租户改造清单.md §1.1 ~ §1.5
目标库：backend/data/looma.db（本机运行时真源）

设计不变量（与清单一致）：全部为增量 —— 加表 + 加字段 + 扩枚举，
不删除、不改写任何现有表结构，可重复执行。

与原清单（PostgreSQL genzltd）的方言映射：
  jsonb                          → TEXT（存 JSON 文本，可用 json_extract 查询）
  timestamptz DEFAULT now()      → TEXT DEFAULT (datetime('now'))（与全库既有约定一致）
  ADD COLUMN IF NOT EXISTS       → pragma table_info() 检查后再 ALTER（SQLite 无此语法）
  CHECK (role IN (...))          → BEFORE INSERT/UPDATE 触发器 RAISE(ABORT)
                                   （SQLite 无法给已有表加 CHECK，重建表会违反"只增量"）
  content_embedding ARRAY        → TEXT（存 JSON 数组；实际 58k 向量在 Chroma
                                   data/poetry_full/chroma.sqlite3，SQLite 侧只留占位）

用法：
    python3 migrate_driver_multitenant.py --db ../data/looma.db [--dry-run]
    python3 migrate_driver_multitenant.py --db ../data/looma.db --backup
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# ============================================================
# 常量
# ============================================================

OFFICIAL_DRIVER_ID = "driver-official"
OFFICIAL_DRIVER_EMAIL = "official@szbolent.com.cn"
POETRY_COLUMN_ID = "col-poetry"

ALLOWED_ROLES = ("user", "enterprise", "admin", "driver")

NEW_TABLES = {
    "driver_profiles": """
CREATE TABLE IF NOT EXISTS driver_profiles (
    id            TEXT PRIMARY KEY,
    display_name  TEXT,
    tagline       TEXT,
    avatar_url    TEXT,
    bio           TEXT,
    show_resume   INTEGER NOT NULL DEFAULT 1,
    show_mbti     INTEGER NOT NULL DEFAULT 1,
    show_social   INTEGER NOT NULL DEFAULT 1,
    show_columns  INTEGER NOT NULL DEFAULT 1,
    theme         TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (id) REFERENCES users(id) ON DELETE CASCADE
);
""",
    "columns": """
CREATE TABLE IF NOT EXISTS columns (
    id            TEXT PRIMARY KEY,
    driver_id     TEXT NOT NULL,
    slug          TEXT NOT NULL,
    name          TEXT NOT NULL,
    description   TEXT,
    content_type  TEXT NOT NULL DEFAULT 'article',
    icon          TEXT,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (driver_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (driver_id, slug)
);
""",
    "articles": """
CREATE TABLE IF NOT EXISTS articles (
    id                TEXT PRIMARY KEY,
    driver_id         TEXT NOT NULL,
    column_id         TEXT,
    title             TEXT NOT NULL,
    slug              TEXT NOT NULL,
    excerpt           TEXT,
    content           TEXT NOT NULL,
    tags              TEXT DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'published',
    view_count        INTEGER NOT NULL DEFAULT 0,
    comment_count     INTEGER NOT NULL DEFAULT 0,
    content_embedding TEXT DEFAULT NULL,
    published_at      TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (driver_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (column_id) REFERENCES columns(id),
    UNIQUE (driver_id, slug)
);
""",
}

# poems 新增归属字段（保留原 author 语义 = 诗词作者，如「李白」）
POEMS_NEW_COLUMNS = (
    ("publisher_id", "TEXT REFERENCES users(id)"),
    ("column_id", "TEXT REFERENCES columns(id)"),
)

NEW_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_columns_driver   ON columns(driver_id)",
    "CREATE INDEX IF NOT EXISTS idx_articles_driver  ON articles(driver_id)",
    "CREATE INDEX IF NOT EXISTS idx_articles_column  ON articles(column_id)",
    "CREATE INDEX IF NOT EXISTS idx_poems_publisher  ON poems(publisher_id)",
    "CREATE INDEX IF NOT EXISTS idx_poems_column     ON poems(column_id)",
)

# 角色枚举收口：SQLite 不能给已有表加 CHECK，用触发器等价实现
ROLE_TRIGGERS = (
    f"""
CREATE TRIGGER IF NOT EXISTS trg_users_role_check_insert
BEFORE INSERT ON users
FOR EACH ROW WHEN NEW.role IS NOT NULL AND NEW.role NOT IN {ALLOWED_ROLES}
BEGIN
    SELECT RAISE(ABORT, 'users.role must be one of: {" ".join(ALLOWED_ROLES)}');
END;
""",
    f"""
CREATE TRIGGER IF NOT EXISTS trg_users_role_check_update
BEFORE UPDATE OF role ON users
FOR EACH ROW WHEN NEW.role IS NOT NULL AND NEW.role NOT IN {ALLOWED_ROLES}
BEGIN
    SELECT RAISE(ABORT, 'users.role must be one of: {" ".join(ALLOWED_ROLES)}');
END;
""",
)


# ============================================================
# 工具
# ============================================================

class Report:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.skipped: list[str] = []
        self.backfilled = 0
        self.seeded: list[str] = []

    def create(self, what: str) -> None:
        self.created.append(what)

    def skip(self, what: str) -> None:
        self.skipped.append(what)


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(r[1] == column for r in conn.execute(f"PRAGMA table_info({table})"))


def email_hash(email: str) -> str:
    """与 manager.email_hash 完全一致：sha256(lower(trim(email))) 小写 hex。"""
    return hashlib.sha256(email.lower().strip().encode("utf-8")).hexdigest()


# ============================================================
# 迁移主体
# ============================================================

def migrate(conn: sqlite3.Connection, rep: Report) -> None:
    # ---------- 前置：目标表必须已存在 ----------
    for required in ("users", "poems"):
        if not table_exists(conn, required):
            raise SystemExit(f"[FATAL] 目标库缺少 {required} 表，不像 looma 库，已中止")

    # ---------- §1.2 / §1.3 / §2.1 建三张新表 ----------
    for name, ddl in NEW_TABLES.items():
        if table_exists(conn, name):
            rep.skip(f"表 {name} 已存在")
        else:
            conn.execute(ddl)
            rep.create(f"表 {name}")

    # ---------- §1.4 poems 补归属字段 ----------
    for col, decl in POEMS_NEW_COLUMNS:
        if column_exists(conn, "poems", col):
            rep.skip(f"poems.{col} 已存在")
        else:
            conn.execute(f"ALTER TABLE poems ADD COLUMN {col} {decl}")
            rep.create(f"字段 poems.{col}")

    # ---------- 索引 ----------
    made = []
    for ddl in NEW_INDEXES:
        name = ddl.split("IF NOT EXISTS")[1].split("ON")[0].strip()
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (name,)
        ).fetchone()
        conn.execute(ddl)
        made.append(name if not exists else None)
    if any(made):
        rep.create(f"索引 {len([m for m in made if m])} 个（{' | '.join(m for m in made if m)}）")
    else:
        rep.skip(f"索引 {len(made)} 个均已存在")

    # ---------- §1.1 role 枚举收口（触发器等价 CHECK） ----------
    made_trg = []
    for ddl in ROLE_TRIGGERS:
        name = ddl.split("IF NOT EXISTS")[1].split("BEFORE")[0].strip()
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name=?", (name,)
        ).fetchone()
        conn.execute(ddl)
        made_trg.append(name if not exists else None)
    if any(made_trg):
        rep.create(f"触发器 role 约束（{' | '.join(ALLOWED_ROLES)}）")
    else:
        rep.skip("触发器 role 约束已存在")

    # ---------- §1.5 种子数据 ----------
    # 1) 平台官方驾驶员（承接存量 58059 首诗词）
    row = conn.execute("SELECT id, role FROM users WHERE id=?", (OFFICIAL_DRIVER_ID,)).fetchone()
    if row:
        if row[1] != "driver":
            conn.execute("UPDATE users SET role='driver' WHERE id=?", (OFFICIAL_DRIVER_ID,))
            rep.create(f"种子 users.{OFFICIAL_DRIVER_ID} 角色修正为 driver")
        else:
            rep.skip(f"种子 users.{OFFICIAL_DRIVER_ID} 已存在")
    else:
        dup = conn.execute(
            "SELECT id FROM users WHERE email=?", (OFFICIAL_DRIVER_EMAIL,)
        ).fetchone()
        if dup:
            rep.skip(f"邮箱 {OFFICIAL_DRIVER_EMAIL} 已被 {dup[0]} 占用，跳过种子用户")
        else:
            conn.execute(
                """INSERT INTO users (id, email, email_hash, name, tier, role)
                   VALUES (?, ?, ?, ?, 'pro', 'driver')""",
                (
                    OFFICIAL_DRIVER_ID,
                    OFFICIAL_DRIVER_EMAIL,
                    email_hash(OFFICIAL_DRIVER_EMAIL),
                    "深伯乐官方",
                ),
            )
            rep.create(f"种子 users.{OFFICIAL_DRIVER_ID}（role=driver）")

    # 2) 官方橱窗
    if conn.execute("SELECT 1 FROM driver_profiles WHERE id=?", (OFFICIAL_DRIVER_ID,)).fetchone():
        rep.skip("种子 driver_profiles 已存在")
    else:
        conn.execute(
            """INSERT INTO driver_profiles (id, display_name, tagline, bio)
               VALUES (?, ?, ?, ?)""",
            (
                OFFICIAL_DRIVER_ID,
                "深伯乐",
                "AI 驱动的智能个人品牌平台",
                "诗词 / 人力 / 法务 / 电梯 / 物联网多专栏作者",
            ),
        )
        rep.create("种子 driver_profiles.driver-official")

    # 3) 首个专栏（诗词）
    if conn.execute("SELECT 1 FROM columns WHERE id=?", (POETRY_COLUMN_ID,)).fetchone():
        rep.skip("种子 columns.col-poetry 已存在")
    else:
        conn.execute(
            """INSERT INTO columns (id, driver_id, slug, name, content_type, sort_order)
               VALUES (?, ?, 'poetry', '诗词', 'poem', 1)""",
            (POETRY_COLUMN_ID, OFFICIAL_DRIVER_ID),
        )
        rep.create("种子 columns.col-poetry")

    # ---------- §1.4 存量回填（幂等：只补 publisher_id IS NULL） ----------
    cur = conn.execute(
        """UPDATE poems
              SET publisher_id = ?, column_id = ?
            WHERE publisher_id IS NULL""",
        (OFFICIAL_DRIVER_ID, POETRY_COLUMN_ID),
    )
    rep.backfilled = cur.rowcount


# ============================================================
# 校验
# ============================================================

def verify(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []

    def q(sql: str, *args):
        return conn.execute(sql, args).fetchone()[0]

    for t in ("driver_profiles", "columns", "articles"):
        out.append(("新表存在", t, "OK" if table_exists(conn, t) else "MISSING"))

    for c in ("publisher_id", "column_id"):
        out.append(("poems 字段", c, "OK" if column_exists(conn, "poems", c) else "MISSING"))

    total = q("SELECT COUNT(*) FROM poems")
    owned = q("SELECT COUNT(*) FROM poems WHERE publisher_id IS NOT NULL AND column_id IS NOT NULL")
    out.append(("诗词归属回填", f"{owned}/{total}", "OK" if owned == total else f"未回填 {total-owned}"))
    out.append(("users 总数", str(q("SELECT COUNT(*) FROM users")), "（迁移前基线 42，+1 官方驾驶员）"))
    out.append(("driver 角色数", str(q("SELECT COUNT(*) FROM users WHERE role='driver'")), ""))

    trig = q("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name LIKE 'trg_users_role_check%'")
    out.append(("role 约束触发器", str(trig), "OK" if trig == 2 else "MISSING"))

    return out


def encroachment_demo(conn: sqlite3.Connection) -> list[str]:
    """越权防护样例：驾驶员只应看到自己的专栏/文章。

    注意：本函数自建 SAVEPOINT 并在返回前回滚，插入的测试数据不会落库，
    与调用方最终是否 COMMIT 无关。
    """
    lines: list[str] = []
    conn.execute("SAVEPOINT encroachment")
    try:
        conn.execute(
            """INSERT OR IGNORE INTO users (id, email, email_hash, name, role)
               VALUES ('driver-intruder', 'intruder@example.test', ?, '越权测试驾驶员', 'driver')""",
            (email_hash("intruder@example.test"),),
        )
        conn.execute(
            """INSERT OR IGNORE INTO columns (id, driver_id, slug, name, content_type)
               VALUES ('col-intruder', 'driver-intruder', 'law', '法务', 'article')"""
        )
        conn.execute(
            """INSERT OR IGNORE INTO articles (id, driver_id, column_id, title, slug, content)
               VALUES ('art-intruder-1', 'driver-intruder', 'col-intruder',
                       '越权测试文章', 'encroachment-test', 'x')"""
        )

        a_cols = conn.execute(
            "SELECT id FROM columns WHERE driver_id=?", (OFFICIAL_DRIVER_ID,)
        ).fetchall()
        b_cols = conn.execute(
            "SELECT id FROM columns WHERE driver_id='driver-intruder'"
        ).fetchall()
        lines.append(f"A(官方) 可见专栏 {[r[0] for r in a_cols]}；B(入侵者) 可见专栏 {[r[0] for r in b_cols]}")
        cross = conn.execute(
            """SELECT COUNT(*) FROM articles a JOIN columns c ON a.column_id = c.id
                WHERE c.driver_id = ? AND a.driver_id <> c.driver_id""",
            (OFFICIAL_DRIVER_ID,),
        ).fetchone()[0]
        lines.append(f"A 名下出现他人文章数 = {cross}（期望 0）")

        # 越权写：以 A 的身份改 B 的文章 → 归属过滤后不应命中
        cur = conn.execute(
            """UPDATE articles SET title='hacked'
                WHERE id='art-intruder-1' AND driver_id=?""",
            (OFFICIAL_DRIVER_ID,),
        )
        lines.append(f"以 A 身份改 B 的文章：影响行数 = {cur.rowcount}（期望 0）")

        # 越权读：A 视角的「我的文章」不会带上 B 的
        leaked = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE driver_id='driver-intruder' AND driver_id=?",
            (OFFICIAL_DRIVER_ID,),
        ).fetchone()[0]
        lines.append(f"A 视角「我的文章」含 B 文章数 = {leaked}（期望 0）")
    finally:
        conn.execute("ROLLBACK TO SAVEPOINT encroachment")
        conn.execute("RELEASE SAVEPOINT encroachment")
    return lines


# ============================================================
# 入口
# ============================================================

def main() -> int:
    ap = argparse.ArgumentParser(description="looma 驾驶员/多租户 P0 迁移（SQLite）")
    ap.add_argument("--db", required=True, help="looma.db 路径")
    ap.add_argument("--dry-run", action="store_true", help="执行后回滚，不改动数据库")
    ap.add_argument("--backup", action="store_true", help="迁移前用 sqlite3 backup API 做一致性快照")
    ap.add_argument("--skip-encroachment", action="store_true", help="跳过越权样例")
    args = ap.parse_args()

    db = Path(args.db).resolve()
    if not db.exists():
        print(f"[FATAL] 数据库不存在：{db}")
        return 2

    if args.backup and not args.dry_run:
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        dst = db.with_name(f"{db.name}.bak-pre-driver-multitenant-{stamp}")
        # 先尽量把 WAL 落盘（失败不阻断：只读/受限环境会拒绝）
        try:
            c = sqlite3.connect(str(db))
            c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            c.close()
        except sqlite3.Error as e:
            print(f"[备份] WAL checkpoint 跳过（{e}）")
        # 文件级复制：不用 sqlite3 backup API —— 某些受限环境（只读 URI / 沙箱）
        # 会以 "disk I/O error" 失败；WAL 已 checkpoint 时文件副本即一致快照
        shutil.copy2(db, dst)
        for suffix in ("-wal", "-shm"):
            side = db.with_name(db.name + suffix)
            if side.exists() and side.stat().st_size > 0:
                shutil.copy2(side, dst.with_name(dst.name + suffix))
        print(f"[备份] {dst}  ({dst.stat().st_size / 1048576:.1f} MB)")

    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys=ON")
    rep = Report()
    try:
        conn.execute("BEGIN")
        migrate(conn, rep)
        print("\n── 本次动作 ──")
        for x in rep.created:
            print(f"  + {x}")
        for x in rep.skipped:
            print(f"  = {x}（已存在，跳过）")
        print(f"  ~ 存量 poems 回填 {rep.backfilled} 行")

        if not args.skip_encroachment:
            print("\n── 越权防护样例（事务内）──")
            for line in encroachment_demo(conn):
                print(f"  · {line}")

        print("\n── 校验 ──")
        for name, val, note in verify(conn):
            print(f"  {name:<16} {val:<18} {note}")

        if args.dry_run:
            conn.rollback()
            print("\n[DRY-RUN] 已回滚，数据库未改动")
        else:
            conn.commit()
            print("\n[OK] 迁移已提交")
    except Exception as e:
        conn.rollback()
        print(f"\n[FATAL] 已回滚：{type(e).__name__}: {e}")
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
