#!/usr/bin/env python3
"""looma SQLite  →  PostgreSQL `genzltd`  结构与数据导出（纯标准库）

用途：把生产 SQLite `looma.db` 的**真实结构**（55 表）与数据，转成可直接喂给
`docker exec -i looma-pgvector psql -U looma -d genzltd -f -` 的 SQL。

为什么不用 psycopg / pgloader：仓库至今**零 PG 驱动**，且生产宿主**无 psql**，
所有 PG 侧动作都走 `docker exec … psql`。本脚本只"生产 SQL"，不连任何库。

产出（--out 目录）：
    schema.sql   建表 + 索引 + 唯一约束（PG 方言；FK 一律 DEFERRABLE INITIALLY DEFERRED）
    data.sql     数据（INSERT；NULL 无损；含每表 setval 修正 identity 序列）
    report.md    逐表行数对拍表 + 映射告警（降级类型 / 跳过的对象）

用法：
    python3 export_sqlite_to_pg.py --sqlite backend/data/looma.db --out /tmp/genzltd
    python3 export_sqlite_to_pg.py --sqlite … --out … --schema-only
    python3 export_sqlite_to_pg.py --sqlite … --out … --data-only --tables users,tenants

不变量（评审时按这四条查）：
  1) **只读源库**：连上即 `PRAGMA query_only=ON`（任何写操作立刻报错），绝不写 `looma.db`。
     刻意**不用** `mode=ro` URI —— WAL 模式下它要建 `-shm`，会以
     `sqlite3.OperationalError: unable to open database file` 失败（本机 py3.9 实测）。
     静态快照可用 `--immutable` 走 `immutable=1`（更快，但**活动库上禁用**）。
  2) **类型保真映射**，不做语义升级 —— SQLite 里时间戳存的是 TEXT ISO 串，
     就映射成 `text`（不擅自改 `timestamptz`，避免与 `manager.py` 读写语义分叉）
  3) 不依赖 psql / psycopg（宿主无 psql 也能生成）
  4) 幂等可重放：schema.sql 默认先 `DROP TABLE IF EXISTS … CASCADE`（`--no-drop` 关闭）

对应文档：docs/PROD_PG_REBUILD_PLAN.md §5 阶段 0/4/5、§6
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sqlite3
import sys
from pathlib import Path

# ============================================================
# SQLite → PG 类型映射（保真优先）
# ============================================================
INT_TYPES = ("INT",)
CHAR_TYPES = ("CHAR", "CLOB", "TEXT")
REAL_TYPES = ("REAL", "FLOA", "DOUB")
NUM_TYPES = ("NUMERIC", "DECIMAL")
BLOB_TYPES = ("BLOB", "BINARY", "BYTEA")
BOOL_TYPES = ("BOOL",)
DATE_TYPES = ("DATE", "TIME")

# 默认值里这些 SQLite 写法必须改写，否则 PG 建表即报错
DEFAULT_REWRITE = {
    "datetime('now')": "now()",
    "(datetime('now'))": "now()",
    "current_timestamp": "now()",
    "CURRENT_TIMESTAMP": "now()",
}


def map_type(declared: str, warnings: list[str], ctx: str) -> str:
    """SQLite 声明类型 → PG 类型。映射不确定时**保留最宽类型**并记告警。"""
    t = (declared or "").strip().upper()
    if not t:
        warnings.append(f"{ctx}: 列无声明类型 → 按 text 处理（SQLite 动态类型，需人工复核）")
        return "text"
    if any(k in t for k in INT_TYPES):
        return "bigint"
    if any(k in t for k in BOOL_TYPES):
        return "boolean"
    if any(k in t for k in BLOB_TYPES):
        return "bytea"
    if any(k in t for k in REAL_TYPES):
        return "double precision"
    if any(k in t for k in NUM_TYPES):
        return "numeric"
    if any(k in t for k in CHAR_TYPES):
        if any(k in t for k in DATE_TYPES):
            warnings.append(f"{ctx}: 声明为 {declared} → 映射 text（SQLite 存 ISO 串，保真优先）")
        return "text"
    if any(k in t for k in DATE_TYPES):
        warnings.append(f"{ctx}: 声明为 {declared} → 映射 text（保真优先）")
        return "text"
    warnings.append(f"{ctx}: 未识别类型 {declared!r} → 映射 text")
    return "text"


def map_default(dflt: str | None, pg_type: str, warnings: list[str], ctx: str) -> str | None:
    """SQLite 默认值 → PG 默认值。不能安全改写的直接丢弃并告警（宁缺勿错）。"""
    if dflt is None:
        return None
    raw = dflt.strip()
    if raw in DEFAULT_REWRITE:
        return DEFAULT_REWRITE[raw]
    low = raw.lower().strip("()")
    if low in ("datetime('now')", "current_timestamp"):
        return "now()"
    if "strftime" in low or "datetime(" in low or "date(" in low or "time(" in low:
        warnings.append(f"{ctx}: 默认值 {raw!r} 含 SQLite 时间函数 → **丢弃**默认值（列仍可空）")
        return None
    if raw.upper() in ("NULL",):
        return None
    if pg_type == "bytea":
        warnings.append(f"{ctx}: bytea 列默认值 {raw!r} → 丢弃")
        return None
    return raw


def quote_literal(value: object) -> str:
    """Python 值 → PG 字面量。NULL/bytes 无损。"""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "'\\x" + bytes(value).hex() + "'::bytea"
    s = str(value).replace("'", "''")
    # PG standard_conforming_strings=on：反斜杠无需转义，但显式标 E'' 会更稳；这里保持简单字面量
    return "'" + s + "'"


def q(ident: str) -> str:
    """PG 标识符加双引号（表/列名可能撞保留字）。"""
    return '"' + ident.replace('"', '""') + '"'


# ============================================================
# 结构内省（全部走 PRAGMA，不解析 DDL 文本）
# ============================================================
class Table:
    def __init__(self, name: str, ddl: str) -> None:
        self.name = name
        self.ddl = ddl
        self.cols: list[dict] = []      # pragma table_info
        self.indexes: list[dict] = []   # origin='c' / 'u'（'pk' 跳过）
        self.fks: list[dict] = []       # 按 id 分组的复合外键
        self.autoinc = False
        self.identity_col: str | None = None
        self.rows = 0


def is_virtual(ddl: str) -> bool:
    up = (ddl or "").upper()
    return "VIRTUAL TABLE" in up or "USING FTS" in up


def _dicts(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    """执行查询并返回 dict 列表（用表值 PRAGMA 函数，避免 `dict(tuple)` 误用）。"""
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def introspect(conn: sqlite3.Connection, warnings: list[str]) -> tuple[list[Table], list[dict]]:
    tables: list[Table] = []
    skipped: list[dict] = []
    rows = conn.execute(
        "SELECT name, type, sql FROM sqlite_master "
        "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    for name, kind, ddl in rows:
        if kind != "table" or is_virtual(ddl):
            skipped.append({"name": name, "kind": kind, "why": "视图/FTS 虚拟表，不迁移"})
            continue
        t = Table(name, ddl or "")
        t.autoinc = "AUTOINCREMENT" in (ddl or "").upper()
        t.cols = _dicts(conn,
                        'SELECT cid, name, type, "notnull", dflt_value, pk '
                        'FROM pragma_table_info(?)', (name,))
        if not t.cols:
            skipped.append({"name": name, "kind": kind, "why": "无列定义（异常表），跳过"})
            continue
        # 单列整数主键 → identity（AUTOINCREMENT 与否都要，SQLite 两者都自增）
        pk_cols = [c for c in t.cols if c["pk"]]
        if len(pk_cols) == 1 and "INT" in (pk_cols[0]["type"] or "").upper():
            t.identity_col = pk_cols[0]["name"]
        for info in _dicts(conn,
                           'SELECT seq, name, "unique", origin, partial '
                           'FROM pragma_index_list(?)', (name,)):
            if info["origin"] == "pk":
                continue
            cols = [r["name"] for r in _dicts(conn,
                                             'SELECT seqno, cid, name FROM pragma_index_info(?)',
                                             (info["name"],))]
            info["cols"] = cols
            if info.get("partial"):
                warnings.append(f"{name}.{info['name']}: 部分索引（WHERE 子句）→ **跳过**，需人工补")
                continue
            if not cols:
                warnings.append(f"{name}.{info['name']}: 表达式索引 → **跳过**，需人工补")
                continue
            t.indexes.append(info)
        groups: dict[int, list[dict]] = {}
        for d in _dicts(conn,
                        'SELECT id, seq, "table", "from", "to", on_update, on_delete '
                        'FROM pragma_foreign_key_list(?)', (name,)):
            groups.setdefault(d["id"], []).append(d)
        for gid, items in sorted(groups.items()):
            items.sort(key=lambda d: d["seq"])
            t.fks.append(
                {
                    "cols": [d["from"] for d in items],
                    "ref_table": items[0]["table"],
                    "ref_cols": [d["to"] for d in items],
                    "on_delete": (items[0]["on_delete"] or "NO ACTION").upper(),
                    "on_update": (items[0]["on_update"] or "NO ACTION").upper(),
                }
            )
        tables.append(t)
    return tables, skipped


# ============================================================
# schema.sql
# ============================================================
def gen_schema(tables: list[Table], warnings: list[str], drop: bool) -> str:
    out: list[str] = [
        "-- 由 backend/scripts/export_sqlite_to_pg.py 生成 —— 请勿手改",
        f"-- 生成时间：{_dt.datetime.now().isoformat(timespec='seconds')}",
        "-- 目标库：genzltd（腾讯云 1.14.202.161 · looma-pgvector 容器）",
        "-- 类型映射策略：保真优先（TEXT 时间戳→text，INTEGER 布尔→bigint）",
        "",
        "SET client_encoding TO 'UTF8';",
        "SET standard_conforming_strings TO on;",
        "",
    ]
    if drop:
        out.append("-- 幂等：先清空同名对象（--no-drop 可关闭）")
        for t in tables:
            out.append(f'DROP TABLE IF EXISTS {q(t.name)} CASCADE;')
        out.append("")

    for t in tables:
        lines: list[str] = [f"-- {t.name}（SQLite 行数 {t.rows}）", f"CREATE TABLE IF NOT EXISTS {q(t.name)} ("]
        parts: list[str] = []
        for c in t.cols:
            ctx = f"{t.name}.{c['name']}"
            is_identity = t.identity_col == c["name"]
            pg_type = (
                "bigint GENERATED BY DEFAULT AS IDENTITY" if is_identity
                else map_type(c["type"], warnings, ctx)
            )
            piece = f"    {q(c['name'])} {pg_type}"
            if c["notnull"] and not is_identity:
                piece += " NOT NULL"
            d = map_default(c["dflt_value"], pg_type, warnings, ctx)
            if d is not None:
                piece += f" DEFAULT {d}"
            parts.append(piece)
        pk_cols = [c["name"] for c in t.cols if c["pk"]]
        if pk_cols:
            parts.append("    PRIMARY KEY (" + ", ".join(q(c) for c in pk_cols) + ")")
        lines.append(",\n".join(parts))
        lines.append(");")
        out.extend(lines)
        for ix in t.indexes:
            uniq = "UNIQUE " if ix["unique"] else ""
            cols = ", ".join(q(c) for c in ix["cols"])
            name = ix["name"]
            if name.startswith("sqlite_autoindex_"):     # UNIQUE 内联约束的自动名 → 起个可读名
                name = ("uq_" if ix["unique"] else "ix_") + t.name + "_" + "_".join(ix["cols"])
            out.append(f'CREATE {uniq}INDEX IF NOT EXISTS {q(name)} ON {q(t.name)} ({cols});')
        out.append("")
    # 外键：必须在**所有表建完之后**再加 —— PG 的 REFERENCES 要求目标表已存在，
    # 按字母序建表会撞 `relation "narrative_sessions" does not exist`（narrative_events → narrative_sessions）
    names = {t.name for t in tables}
    fk_lines: list[str] = []
    for t in tables:
        for fk in t.fks:
            if fk["ref_table"] not in names:
                warnings.append(
                    f"{t.name}: 外键指向未导出的表 {fk['ref_table']} → 跳过该 FK（--tables 过滤所致）")
                continue
            cname = "fk_" + t.name + "_" + "_".join(fk["cols"])
            cols = ", ".join(q(c) for c in fk["cols"])
            ref_cols = ", ".join(q(c) for c in fk["ref_cols"])
            fk_lines.append(f"ALTER TABLE {q(t.name)} DROP CONSTRAINT IF EXISTS {q(cname)};")
            fk_lines.append(
                f"ALTER TABLE {q(t.name)} ADD CONSTRAINT {q(cname)} FOREIGN KEY ({cols})"
                f" REFERENCES {q(fk['ref_table'])} ({ref_cols})"
                f" ON DELETE {fk['on_delete']} ON UPDATE {fk['on_update']}"
                " DEFERRABLE INITIALLY DEFERRED;"   # 数据装载顺序无关
            )
    if fk_lines:
        out.append("-- 外键：表全部建好后统一添加（避免引用顺序 / 自引用问题）")
        out.extend(fk_lines)
        out.append("")
    return "\n".join(out) + "\n"


# ============================================================
# data.sql（流式，避免 58k 行 poems 撑爆内存）
# ============================================================
def write_data(conn: sqlite3.Connection, tables: list[Table], path: Path, batch: int,
               warnings: list[str]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("-- 由 backend/scripts/export_sqlite_to_pg.py 生成的数据（INSERT）\n")
        fh.write("-- 依赖 schema.sql 已执行；FK 为 DEFERRABLE INITIALLY DEFERRED，无需排序\n")
        fh.write("BEGIN;\n")
        for t in tables:
            if not t.rows:
                continue
            cols = [c["name"] for c in t.cols]
            collist = ", ".join(q(c) for c in cols)
            cur = conn.execute(f"SELECT {', '.join(q(c) for c in cols)} FROM {q(t.name)}")  # noqa: S608
            pending: list[str] = []
            n = 0
            while True:
                rows = cur.fetchmany(batch)
                if not rows:
                    break
                for row in rows:
                    vals = ", ".join(quote_literal(v) for v in row)
                    pending.append(f"({vals})")
                    n += 1
                fh.write(f"INSERT INTO {q(t.name)} ({collist}) VALUES\n")
                fh.write(",\n".join(pending) + ";\n")
                pending.clear()
            if t.identity_col:
                seq_col = q(t.identity_col)
                fh.write(
                    f"SELECT setval(pg_get_serial_sequence('{t.name}', '{t.identity_col}'), "
                    f"(SELECT max({seq_col}) FROM {q(t.name)}), true);\n"
                )
            fh.write(f"-- {t.name}: {n} 行\n")
        fh.write("COMMIT;\n")


# ============================================================
# constraints.sql：把 SQLite 触发器里守的枚举落成 PG CHECK（数据装载后再加）
# ============================================================
def gen_constraints(conn: sqlite3.Connection, warnings: list[str], skipped: list[dict]) -> str:
    import re

    out: list[str] = [
        "-- 由 export_sqlite_to_pg.py 生成：SQLite 触发器 → PG CHECK 约束",
        "-- 执行时机：**data.sql 之后**（遗留行若违反规则会在此暴露，属预期信息）",
        "",
    ]
    pat = re.compile(
        r"BEFORE\s+(?:INSERT|UPDATE(?:\s+OF\s+[\w, ]+)?)\s+ON\s+(\w+).*?"
        r"NEW\.(\w+)\s+IS\s+NOT\s+NULL\s+AND\s+NEW\.\w+\s+NOT\s+IN\s*\(([^)]*)\)",
        re.IGNORECASE | re.DOTALL,
    )
    for name, sql in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'").fetchall():
        m = pat.search(sql or "")
        if not m:
            skipped.append({"name": name, "kind": "trigger", "why": "非枚举校验类触发器，不迁移"})
            warnings.append(f"触发器 {name} 无法自动翻译 → 请人工确认是否需要 PG 侧等价物")
            continue
        table, col, values = m.group(1), m.group(2), m.group(3)
        vals = ", ".join(v.strip() for v in values.split(",") if v.strip())
        cname = f"{table}_{col}_check"
        out.append(f"-- 源触发器：{name}")
        out.append(f"ALTER TABLE {q(table)} DROP CONSTRAINT IF EXISTS {q(cname)};")
        out.append(f"ALTER TABLE {q(table)} ADD CONSTRAINT {q(cname)} CHECK ({q(col)} IN ({vals}));")
        out.append("")
    if len(out) <= 3:
        out.append("-- 无可迁移的枚举触发器")
    return "\n".join(out) + "\n"


# ============================================================
# report.md / verify.sql
# ============================================================
def gen_report(src: Path, tables: list[Table], skipped: list[dict], warnings: list[str],
               stats: dict, snap_warn: bool) -> str:
    total = sum(t.rows for t in tables)
    lines = [
        "# SQLite → PostgreSQL 导出报告",
        "",
        f"- 源库：`{src}`",
        f"- 生成时间：{_dt.datetime.now().isoformat(timespec='seconds')}",
        f"- 表数：**{len(tables)}** · 合计行数：**{total:,}**",
        f"- schema.sql：{stats['schema']:,} B · data.sql：{stats['data']:,} B",
        "",
    ]
    if snap_warn:
        lines += [
            "> ⚠️ **检测到 `-wal` 文件**：源库处于活动状态。导出连接为 `PRAGMA query_only=ON`（只读），",
            "> 但活动 WAL 中未 checkpoint 的数据可能读不到。生产请先做快照再导出：",
            "> `docker exec looma-backend cp /app/data/looma.db /tmp/looma-snapshot.db`。",
            "",
        ]
    lines += ["## 逐表行数（导入后用 verify.sql 对拍）", "",
              "| 表 | 行数 | identity 列 | 索引 | 外键 |", "|---|---:|---|---:|---:|"]
    for t in tables:
        ident = f"`{t.identity_col}`" if t.identity_col else ("⚠️ autoinc 无整数单列主键" if t.autoinc else "—")
        lines.append(f"| `{t.name}` | {t.rows:,} | {ident} | {len(t.indexes)} | {len(t.fks)} |")
    if skipped:
        lines += ["", "## 跳过对象（需人工判断）", "", "| 对象 | 类型 | 原因 |", "|---|---|---|"]
        for s in skipped:
            lines.append(f"| `{s['name']}` | {s['kind']} | {s['why']} |")
    lines += ["", "## 映射告警", ""]
    lines += [f"- {w}" for w in warnings] if warnings else ["- 无"]
    return "\n".join(lines) + "\n"


def gen_verify(tables: list[Table]) -> str:
    parts = [
        f"SELECT '{t.name}' AS table_name, count(*) AS pg_rows FROM {q(t.name)}"
        for t in tables
    ]
    header = (
        "-- 导入后在生产 PG 执行：\n"
        "-- docker exec -i looma-pgvector psql -U looma -d genzltd -f - < verify.sql\n"
    )
    return header + " UNION ALL\n".join(parts) + "\n ORDER BY table_name;\n"


# ============================================================
# main
# ============================================================
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="looma SQLite → PG genzltd 结构与数据导出")
    ap.add_argument("--sqlite", default="backend/data/looma.db", help="源 SQLite 路径（只读打开）")
    ap.add_argument("--out", default="/tmp/genzltd", help="输出目录")
    ap.add_argument("--tables", default="", help="仅导出这些表（逗号分隔），默认全部")
    ap.add_argument("--batch", type=int, default=200, help="INSERT 每语句行数（默认 200）")
    ap.add_argument("--no-drop", action="store_true", help="schema.sql 不生成 DROP TABLE")
    ap.add_argument("--immutable", action="store_true",
                    help="按 immutable=1 打开（仅用于静态快照；活动库禁用）")
    ap.add_argument("--schema-only", action="store_true")
    ap.add_argument("--data-only", action="store_true")
    args = ap.parse_args(argv)

    src = Path(args.sqlite).resolve()
    if not src.exists():
        print(f"[FATAL] 源库不存在：{src}", file=sys.stderr)
        return 2
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    snap_warn = Path(str(src) + "-wal").exists()
    if args.immutable:
        conn = sqlite3.connect(f"file:{src}?immutable=1", uri=True)
    else:
        conn = sqlite3.connect(str(src))
    conn.execute("PRAGMA query_only = ON")   # 只读硬约束：任何写尝试都会抛错
    # 说明：不主动做 wal_checkpoint —— 读连接无需 checkpoint，且 query_only 下也不允许写。
    #       若源库带 -wal，SQLite 会自动读 WAL 内容；快照策略见 report.md 的提示。
    try:
        tables, skipped = introspect(conn, warnings)
        if args.tables:
            want = {s.strip() for s in args.tables.split(",") if s.strip()}
            tables = [t for t in tables if t.name in want]
        for t in tables:
            t.rows = conn.execute(f"SELECT count(*) FROM {q(t.name)}").fetchone()[0]  # noqa: S608

        stats = {"schema": 0, "data": 0}
        tables.sort(key=lambda t: t.name)
        if not args.data_only:
            text = gen_schema(tables, warnings, drop=not args.no_drop)
            p = out_dir / "schema.sql"
            p.write_text(text, encoding="utf-8")
            stats["schema"] = len(text.encode())
            print(f"[OK] {p}  （{len(tables)} 表）")
        if not args.schema_only:
            p = out_dir / "data.sql"
            write_data(conn, tables, p, args.batch, warnings)
            stats["data"] = p.stat().st_size
            print(f"[OK] {p}  （{p.stat().st_size:,} B）")
        p = out_dir / "constraints.sql"
        p.write_text(gen_constraints(conn, warnings, skipped), encoding="utf-8")
        print(f"[OK] {p}")
        p = out_dir / "verify.sql"
        p.write_text(gen_verify(tables), encoding="utf-8")
        print(f"[OK] {p}")
        p = out_dir / "report.md"
        p.write_text(gen_report(src, tables, skipped, warnings, stats, snap_warn), encoding="utf-8")
        print(f"[OK] {p}  （告警 {len(warnings)} 条）")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



