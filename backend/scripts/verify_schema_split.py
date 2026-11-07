# -*- coding: utf-8 -*-
"""Phase 1 自测：schema split（core 只建 core / 宿主只建 product / 缺 core 时 fail-fast）。"""
import os
import sqlite3
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
os.chdir(str(__import__("pathlib").Path(__file__).resolve().parents[1]))

TMP = os.path.abspath(os.path.join(str(__import__("pathlib").Path(__file__).resolve().parents[1]), ".tmp-split-probe"))
os.makedirs(TMP, exist_ok=True)


def tables(db):
    conn = sqlite3.connect(db)
    try:
        t = sorted(r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        v = sorted(r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='view'"))
        return t, v
    finally:
        conn.close()


def run(label, path, builder):
    os.environ["DATABASE_PATH"] = path
    os.environ["THOMAS_SCHEMA_SPLIT"] = "1"
    try:
        app = builder()
        client = app.test_client()
        resp = client.get("/health")
        body = resp.get_json() or {}
        t, v = tables(path)
        print("%-22s health=%s service=%s tables=%d views=%d" % (
            label, resp.status_code, body.get("service"), len(t), len(v)))
        print("    tables: %s" % ", ".join(t))
        return body
    except Exception as exc:
        print("%-22s RAISED %s: %s" % (label, type(exc).__name__, str(exc).splitlines()[0][:90]))
        return None
    finally:
        os.environ.pop("THOMAS_SCHEMA_SPLIT", None)
        os.environ.pop("DATABASE_PATH", None)


# A) core 先起：只应有 core 7 表 + schema_meta
core_db = os.path.join(TMP, "core_only.db")
if os.path.exists(core_db):
    os.remove(core_db)
from src.thomas_core.app import create_core_app  # noqa: E402

run("A core-only", core_db, create_core_app)

# B) 宿主接着起：补 product 50 表 + 3 视图
from src.app import create_app  # noqa: E402

run("B host-after-core", core_db, create_app)

# C) 宿主先起（库中无 core）：必须 fail-fast
host_first = os.path.join(TMP, "host_first.db")
if os.path.exists(host_first):
    os.remove(host_first)
run("C host-without-core", host_first, create_app)

# D) 版本记录
for scope in ("core", "product"):
    conn = sqlite3.connect(core_db)
    try:
        row = conn.execute("SELECT scope, version, applied_at FROM schema_meta WHERE scope=?", (scope,)).fetchone()
        print("D schema_meta %-8s %s" % (scope, row))
    finally:
        conn.close()
