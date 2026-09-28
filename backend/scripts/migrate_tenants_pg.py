#!/usr/bin/env python3
"""
looma-zervi「加盟联邦 / 多租户」P1 数据骨架迁移 —— PostgreSQL 方言版

对应清单：~/Downloads/looma-zervi多租户改造清单.md §1（PostgreSQL genzltd 库）
对应架构：docs/TENANT_FEDERATION_ARCHITECTURE.md §3（加盟登记 + 引用缓存）

目标库：genzltd（looma 后端真实库，改造清单 §1 明载）
        本地 ServBay 副本名为 looma，用 --db looma 覆盖即可在同结构上验证。

设计不变量（与清单一致）：全部为**增量** —— 加表 + 加字段，不删除、不改写任何现有表结构，
可重复执行（IF NOT EXISTS / ON CONFLICT）。

与 migrate_driver_multitenant.py 的关系（两侧结构必须一致）：
    该脚本 = SQLite 方言版（TEXT 存 JSON / INTEGER 布尔 / pragma 探测列）
    本脚本 = PG   方言版（jsonb / timestamptz / now() / ADD COLUMN IF NOT EXISTS）
    => 改动 DDL 时**两份都要改**，否则 SQLite 与 genzltd 漂移。

依赖：只用标准库 —— 通过 psql(1) 执行，不引入 psycopg。
      与既有迁移脚本「零新增依赖」的约定一致；仓库当前确实没有任何 PG 驱动。

用法：
    python3 migrate_tenants_pg.py --dry-run                 # 演练（末尾 ROLLBACK）
    python3 migrate_tenants_pg.py                           # 落 genzltd
    python3 migrate_tenants_pg.py --db looma --port 5432     # 本地副本验证
    python3 migrate_tenants_pg.py --seed                    # 追加首批加盟登记
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ============================================================
# 常量
# ============================================================

DEFAULT_DB = "genzltd"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5432
TTL_SECONDS = 300  # 引用缓存 TTL，与 bolent-shelf-bridge/1 §7 一致

# 幂等 DDL —— 顺序即依赖顺序（表 → 索引 → 列 → 唯一索引 → 公开读视图）
MIGRATION: list[tuple[str, str]] = [
    (
        "tenants 表（加盟登记）",
        """
CREATE TABLE IF NOT EXISTS tenants (
  id           text PRIMARY KEY,
  handle       text NOT NULL,                       -- URL 稳定键：/shop/<handle>
  tenant_type  text NOT NULL DEFAULT 'personal',    -- personal | enterprise
  legal_name   text,                                -- 备案主体名
  icp_no       text,                                -- 备案号（对外展示用）
  domains      jsonb NOT NULL DEFAULT '[]'::jsonb,   -- ["https://szbolent.cn"]
  join_mode    text NOT NULL DEFAULT 'reference',   -- reference | mirror
  feed_url     text,                                -- 通道 A：bolent-shelf-bridge feed
  driver_id    text,                                -- 本地驾驶员（mirror / 平台自营才有；引用式可空）
  status       text NOT NULL DEFAULT 'pending',     -- pending | active | suspended
  share_bp     integer NOT NULL DEFAULT 0,          -- 分成基点（万分之一；0 = 平台自营不分账）
  secret_ref   text,                                -- 通道 B 密钥引用（K(p) 由 master 推导，不落明文）
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT tenants_handle_key        UNIQUE (handle),
  CONSTRAINT tenants_tenant_type_check CHECK (tenant_type IN ('personal','enterprise')),
  CONSTRAINT tenants_join_mode_check   CHECK (join_mode IN ('reference','mirror')),
  CONSTRAINT tenants_status_check      CHECK (status IN ('pending','active','suspended')),
  CONSTRAINT tenants_share_bp_check    CHECK (share_bp BETWEEN 0 AND 10000),
  CONSTRAINT tenants_driver_fk         FOREIGN KEY (driver_id) REFERENCES users(id) ON DELETE SET NULL
);
""",
    ),
    (
        "idx_tenants_status 索引",
        "CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);",
    ),
    (
        "tenant_shelf_items 表（引用缓存，TTL 300s）",
        """
CREATE TABLE IF NOT EXISTS tenant_shelf_items (
  tenant_id   text NOT NULL,
  slug        text NOT NULL,                        -- 引用稳定键（协议 items[].slug）
  title       text,
  excerpt     text,                                 -- 唯一允许展示的正文片段
  url         text NOT NULL,                        -- ★ 原文链接，唯一正典入口
  cover       text,                                 -- 可能为 null，消费方须处理空态
  published   timestamptz,
  modified    timestamptz,
  categories  jsonb NOT NULL DEFAULT '[]'::jsonb,
  tags        jsonb NOT NULL DEFAULT '[]'::jsonb,
  fetched_at  timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT tenant_shelf_items_pkey      PRIMARY KEY (tenant_id, slug),
  CONSTRAINT tenant_shelf_items_tenant_fk FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);
""",
    ),
    (
        "idx_tsi_fetched 索引（惰性 TTL 用）",
        "CREATE INDEX IF NOT EXISTS idx_tsi_fetched ON tenant_shelf_items(tenant_id, fetched_at DESC);",
    ),
    (
        "driver_profiles.handle 列（/shop/<handle> 的落地键）",
        "ALTER TABLE driver_profiles ADD COLUMN IF NOT EXISTS handle text;",
    ),
    (
        "driver_profiles.status 列",
        "ALTER TABLE driver_profiles ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active';",
    ),
    (
        "uq_driver_profiles_handle 唯一索引",
        """
CREATE UNIQUE INDEX IF NOT EXISTS uq_driver_profiles_handle
    ON driver_profiles(handle) WHERE handle IS NOT NULL;
""",
    ),
    (
        "v_catalog_tenants 公开读视图（只暴露 active）",
        """
CREATE OR REPLACE VIEW v_catalog_tenants AS
SELECT id, handle, tenant_type, legal_name, icp_no, domains,
       join_mode, feed_url, status, updated_at
  FROM tenants
 WHERE status = 'active';
""",
    ),
]

# ------------------------------------------------------------
# 首批加盟登记种子（--seed 才执行；幂等）
# ------------------------------------------------------------
SEED = """
-- 1) 平台官方租户（承接平台自营橱窗 / 存量内容）
INSERT INTO tenants (id, handle, tenant_type, join_mode, status, share_bp)
VALUES ('t-official', 'official', 'enterprise', 'reference', 'active', 0)
ON CONFLICT (id) DO UPDATE SET updated_at = now();

-- 2) 首个加盟租户：szbolent.cn（个人备案主体 · 书店）
--    legal_name / icp_no 由加盟登记时人工补全，此处不臆造备案信息。
INSERT INTO tenants (id, handle, tenant_type, domains, join_mode, feed_url, status, share_bp)
VALUES ('t-szbolent-cn', 'szbolent-cn', 'personal',
        '["https://szbolent.cn"]'::jsonb, 'reference',
        'https://szbolent.cn/wp-json/bolent-shelf/v1/feed', 'active', 0)
ON CONFLICT (id) DO UPDATE
   SET domains    = EXCLUDED.domains,
       feed_url   = EXCLUDED.feed_url,
       join_mode  = EXCLUDED.join_mode,
       updated_at = now();
"""

# ------------------------------------------------------------
# 迁移前存在性探测（用于打印「+ 新建 / = 已存在」）
# ------------------------------------------------------------
CHECKS: list[tuple[str, str]] = [
    ("tenants 表", "SELECT to_regclass('public.tenants') IS NOT NULL"),
    ("tenant_shelf_items 表", "SELECT to_regclass('public.tenant_shelf_items') IS NOT NULL"),
    ("v_catalog_tenants 视图", "SELECT to_regclass('public.v_catalog_tenants') IS NOT NULL"),
    (
        "driver_profiles.handle 列",
        "SELECT count(*) = 1 FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='driver_profiles' AND column_name='handle'",
    ),
    (
        "driver_profiles.status 列",
        "SELECT count(*) = 1 FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='driver_profiles' AND column_name='status'",
    ),
    (
        "uq_driver_profiles_handle 索引",
        "SELECT count(*) = 1 FROM pg_indexes "
        "WHERE schemaname='public' AND indexname='uq_driver_profiles_handle'",
    ),
]

# ------------------------------------------------------------
# 事务内硬断言（失败即 RAISE EXCEPTION → psql 非零退出）
# ------------------------------------------------------------
ASSERTIONS = """
DO $$
DECLARE
  c int;
  d "char";
BEGIN
  SELECT count(*) INTO c FROM information_schema.tables
   WHERE table_schema = 'public' AND table_name IN ('tenants','tenant_shelf_items');
  IF c <> 2 THEN RAISE EXCEPTION '[断言失败] 期望 2 张新表，实为 %', c; END IF;

  SELECT count(*) INTO c FROM pg_constraint
   WHERE conrelid = 'public.tenants'::regclass AND contype = 'c';
  IF c < 4 THEN RAISE EXCEPTION '[断言失败] tenants CHECK 约束期望 >= 4，实为 %', c; END IF;

  SELECT confdeltype INTO d FROM pg_constraint
   WHERE conname = 'tenant_shelf_items_tenant_fk';
  IF d IS NULL THEN RAISE EXCEPTION '[断言失败] 缺引用缓存外键';
  ELSIF d <> 'c' THEN RAISE EXCEPTION '[断言失败] 引用缓存外键删除规则期望 CASCADE(c)，实为 %', d; END IF;

  SELECT count(*) INTO c FROM information_schema.columns
   WHERE table_schema='public' AND table_name='driver_profiles' AND column_name IN ('handle','status');
  IF c <> 2 THEN RAISE EXCEPTION '[断言失败] driver_profiles 期望新增 2 列，实为 %', c; END IF;

  SELECT count(*) INTO c FROM v_catalog_tenants WHERE status <> 'active';
  IF c <> 0 THEN RAISE EXCEPTION '[断言失败] 公开读视图泄漏非 active 租户 % 行', c; END IF;
END $$;
"""

# ------------------------------------------------------------
# 联邦可见性 / 级联样例（SAVEPOINT 内，无论提交与否都回滚）
# ------------------------------------------------------------
DEMO = """
\\echo '── 联邦可见性 / 级联样例（SAVEPOINT 内，执行后回滚）──'
SAVEPOINT fed_demo;
INSERT INTO tenants (id, handle, status, tenant_type)
VALUES ('t-demo-susp', 'demo-susp', 'suspended', 'personal')
ON CONFLICT (id) DO UPDATE SET status = 'suspended';
INSERT INTO tenants (id, handle, status, tenant_type)
VALUES ('t-demo-act', 'demo-act', 'active', 'personal')
ON CONFLICT (id) DO UPDATE SET status = 'active';
INSERT INTO tenant_shelf_items (tenant_id, slug, url)
VALUES ('t-demo-act', 's1', 'https://example.test/s1')
ON CONFLICT (tenant_id, slug) DO NOTHING;

SELECT '  · active 租户可见数（期望 1）'        AS item, count(*)::text AS val
  FROM v_catalog_tenants WHERE handle = 'demo-act'
UNION ALL
SELECT '  · suspended 租户可见数（期望 0）',     count(*)::text
  FROM v_catalog_tenants WHERE handle = 'demo-susp'
UNION ALL
SELECT '  · demo 租户引用条目数（期望 1）',      count(*)::text
  FROM tenant_shelf_items WHERE tenant_id = 't-demo-act';

DELETE FROM tenants WHERE id = 't-demo-act';

SELECT '  · 级联删除后残留条目数（期望 0）',     count(*)::text
  FROM tenant_shelf_items WHERE tenant_id = 't-demo-act';

ROLLBACK TO SAVEPOINT fed_demo;
"""

# 落库后汇报（信息性，不参与断言）
REPORT = """
\\echo '── 落库后 ──'
SELECT '  · tenants 行数'                       AS item, count(*)::text AS val FROM tenants
UNION ALL
SELECT '  · active 租户（进公开目录）',           count(*)::text FROM v_catalog_tenants
UNION ALL
SELECT '  · tenant_shelf_items 引用缓存行数',     count(*)::text FROM tenant_shelf_items
ORDER BY 1;
"""


# ============================================================
# 连接参数
# ============================================================

def load_env_file(path: Path) -> dict[str, str]:
    """极简 .env 解析：只认 KEY=VALUE，忽略注释与引号，避免引入 dotenv 依赖。"""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def resolve_conn(args: argparse.Namespace) -> tuple[dict[str, str], str, str]:
    """返回 (conn, password, psql_bin)。

    密码优先级：--password > 环境变量 PGPASSWORD > .env 的 PG_PASSWORD。
    密码只经子进程环境传递，**不进 argv**（避免 ps 泄露）。
    """
    env_file = load_env_file(Path(args.env))

    def pick(cli_val: str | None, env_key: str, fallback: str) -> str:
        if cli_val:
            return cli_val
        if env_file.get(env_key):
            return env_file[env_key]
        return fallback

    # 注意：--db 不取 .env 的 PG_DATABASE —— 目标库由架构文档钉死为 genzltd
    conn = {
        "db": args.db or DEFAULT_DB,
        "host": pick(args.host, "PG_HOST", DEFAULT_HOST),
        "port": str(args.port or _safe_int(env_file.get("PG_PORT"), DEFAULT_PORT)),
        "user": pick(args.user, "PG_USER", os.getenv("USER", "postgres")),
    }
    password = args.password or os.getenv("PGPASSWORD") or env_file.get("PG_PASSWORD", "")
    psql_bin = args.psql or shutil.which("psql") or "/Applications/ServBay/bin/psql"
    return conn, password, psql_bin


def _safe_int(raw: str | None, fallback: int) -> int:
    try:
        return int(raw) if raw else fallback
    except (TypeError, ValueError):
        return fallback


# ============================================================
# psql 执行
# ============================================================

def base_cmd(psql_bin: str, conn: dict[str, str]) -> list[str]:
    return [
        psql_bin,
        "-X",                        # 不读 ~/.psqlrc
        "-q",
        "-v", "ON_ERROR_STOP=1",     # 出错即停，退出码非零
        "-P", "pager=off",           # 防分页器挂起
        "-h", conn["host"],
        "-p", conn["port"],
        "-U", conn["user"],
        "-d", conn["db"],
    ]


def run_sql(psql_bin: str, conn: dict[str, str], password: str, sql: str) -> subprocess.CompletedProcess:
    """执行一段 SQL 脚本（走 stdin，便于包含 psql 元命令）。"""
    env = dict(os.environ)
    if password:
        env["PGPASSWORD"] = password
    return subprocess.run(
        base_cmd(psql_bin, conn) + ["-A", "-t", "-F", "|"],
        input=sql, text=True, capture_output=True, env=env,
    )


def scalar(psql_bin: str, conn: dict[str, str], password: str, sql: str) -> str:
    """执行单值查询，返回去空白结果。"""
    env = dict(os.environ)
    if password:
        env["PGPASSWORD"] = password
    proc = subprocess.run(
        base_cmd(psql_bin, conn) + ["-A", "-t", "-c", sql],
        text=True, capture_output=True, env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"psql exit {proc.returncode}")
    return proc.stdout.strip()


# ============================================================
# 入口
# ============================================================

def main() -> int:
    ap = argparse.ArgumentParser(description="looma 加盟联邦 / 多租户 P1 迁移（PostgreSQL 方言）")
    ap.add_argument("--db", help=f"目标库（默认 {DEFAULT_DB} = looma 后端真实库）")
    ap.add_argument("--host", help="PG 主机（默认取 .env 的 PG_HOST）")
    ap.add_argument("--port", type=int, help="PG 端口（默认取 .env 的 PG_PORT）")
    ap.add_argument("--user", help="PG 用户（默认取 .env 的 PG_USER）")
    ap.add_argument("--password", help="PG 密码（默认取 PGPASSWORD / .env 的 PG_PASSWORD）")
    ap.add_argument("--psql", help="psql 可执行文件路径")
    ap.add_argument(
        "--env",
        default=str(Path(__file__).resolve().parents[1] / ".env"),
        help="PG_* 来源 .env（默认 backend/.env）",
    )
    ap.add_argument("--dry-run", action="store_true", help="末尾 ROLLBACK，不改动数据库")
    ap.add_argument("--seed", action="store_true", help="追加首批加盟登记（幂等）")
    args = ap.parse_args()

    conn, password, psql_bin = resolve_conn(args)
    if not Path(psql_bin).exists() and not shutil.which(psql_bin):
        print(f"[FATAL] 找不到 psql：{psql_bin}")
        return 2

    print("── 目标 ──")
    print(f"  psql   {psql_bin}")
    print(f"  库     {conn['user']}@{conn['host']}:{conn['port']}/{conn['db']}")
    mode = "DRY-RUN（末尾回滚）" if args.dry_run else "APPLY"
    print(f"  模式   {mode}{' + 首批加盟登记' if args.seed else ''}")
    if conn["db"] != DEFAULT_DB:
        print(f"  [注] 目标库非 {DEFAULT_DB}；仅应指向同结构副本（如本地 looma）")

    # 迁移前存在性探测（失败即连接不通）
    try:
        before = {name: scalar(psql_bin, conn, password, sql) == "t" for name, sql in CHECKS}
    except RuntimeError as exc:
        print(f"\n[FATAL] 连接 / 探测失败：{exc}")
        print("        提示：核对 PG_HOST / PG_PORT / PG_USER / PG_PASSWORD（可 --host/--port/--user 覆盖）。")
        print("        本机两种 PG：ServBay 原生 = 5432；pgvector Docker（backend/dev.sh）= 5433。")
        return 2

    # 组装单次 psql 事务：DDL → 种子 → 样例 → 断言 → 汇报 → 提交/回滚
    script: list[str] = ["BEGIN;"]
    for label, sql in MIGRATION:
        script.append(f"\n-- {label}")
        script.append(sql)
    if args.seed:
        script.append("\n-- 首批加盟登记（--seed）")
        script.append(SEED)
    script += [DEMO, ASSERTIONS, REPORT, "ROLLBACK;" if args.dry_run else "COMMIT;"]

    proc = run_sql(psql_bin, conn, password, "\n".join(script))
    if proc.stdout.strip():
        print("\n" + proc.stdout.rstrip())
    if proc.returncode != 0:
        print(f"\n[FATAL] psql 退出码 {proc.returncode}")
        if proc.stderr.strip():
            print(proc.stderr.rstrip())
        print("        事务已随连接关闭回滚，数据库未改动。")
        return 1

    print("\n── 本次动作 ──")
    for name, _ in CHECKS:
        if before[name]:
            print(f"  = {name}（已存在，跳过）")
        elif args.dry_run:
            print(f"  + {name}（演练：待新建）")
        else:
            print(f"  + {name}（已新建）")

    if args.dry_run:
        print("\n[DRY-RUN] 已回滚，数据库未改动")
    else:
        print("\n[OK] 迁移已提交")
        if conn["db"] != DEFAULT_DB:
            print(f"     [注] 生产需在 {DEFAULT_DB} 库再执行一次："
                  f"python3 migrate_tenants_pg.py --db {DEFAULT_DB}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
