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

# C) 空库冷启动（宿主先起、库是空的）：允许，且产出与 legacy 相同 58 表 + 3 视图
#    —— 这条是 CI / 单测路径（tests/conftest.py 每个 app 都是新的空 temp db）
cold_db = os.path.join(TMP, "cold_start.db")
if os.path.exists(cold_db):
    os.remove(cold_db)
run("C cold-start", cold_db, create_app)

# C2) 库非空但缺 core：必须 fail-fast（防指错库）
host_first = os.path.join(TMP, "host_first.db")
if os.path.exists(host_first):
    os.remove(host_first)
_conn = sqlite3.connect(host_first)
_conn.execute("CREATE TABLE stray_product_table (id INTEGER PRIMARY KEY)")
_conn.commit()
_conn.close()
run("C2 host-without-core", host_first, create_app)

# D) 版本记录
for scope in ("core", "product"):
    conn = sqlite3.connect(core_db)
    try:
        row = conn.execute("SELECT scope, version, applied_at FROM schema_meta WHERE scope=?", (scope,)).fetchone()
        print("D schema_meta %-8s %s" % (scope, row))
    finally:
        conn.close()

# E) 行尾归一：同一份 DDL 的 LF 副本与 CRLF 副本必须算出同一个版本号（坑 32）
#    —— 否则 Windows（autocrlf=true）检出后会把 Linux/CI 建的库误判 drift
from pathlib import Path  # noqa: E402

from src.db import schema_loader  # noqa: E402

_orig = dict(schema_loader.SCOPE_FILES)
try:
    _src = _orig["core"]
    _lf = _src.read_bytes().replace(b"\r\n", b"\n")
    _lf_path = Path(TMP) / "core_LF.sql"
    _crlf_path = Path(TMP) / "core_CRLF.sql"
    _lf_path.write_bytes(_lf)
    _crlf_path.write_bytes(_lf.replace(b"\n", b"\r\n"))

    schema_loader.SCOPE_FILES["core"] = _lf_path
    _v_lf = schema_loader.file_version("core")
    schema_loader.SCOPE_FILES["core"] = _crlf_path
    _v_crlf = schema_loader.file_version("core")
    print("E crlf-normalize      lf=%s crlf=%s %s" % (
        _v_lf, _v_crlf, "SAME" if _v_lf == _v_crlf else "DIFF(FAIL)"))
finally:
    schema_loader.SCOPE_FILES.clear()
    schema_loader.SCOPE_FILES.update(_orig)
