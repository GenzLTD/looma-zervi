# -*- coding: utf-8 -*-
"""刀3 验证门禁：
① core_schema 空库独立建库；② core+product 同库依次建库；
③ FK 方向门禁：product 表 FK 目标 ∈ {users} ∪ product；core 表 FK 目标 ∈ core；
④ PRAGMA foreign_key_check 零违规；⑤ 实库（looma.db）FK 方向同扫描（防 DDL 与运行库漂移）。
退出码 0 = 全绿。"""
import sqlite3, os, sys, io

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[1])
CORE_SQL = os.path.join(ROOT, "src", "db", "core_schema.sql")
PROD_SQL = os.path.join(ROOT, "src", "db", "product_schema.sql")
LIVE_DB = os.path.join(ROOT, "data", "looma.db")
CORE = {"users", "user_identities", "consents", "audit_logs",
        "signal_ingest", "signal_outbox", "signal_dlq"}

fails = []

def check(label, ok, detail=""):
    print("%-38s %-4s %s" % (label, "PASS" if ok else "FAIL", detail))
    if not ok:
        fails.append(label)

def load(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()

# ① core 独立建库
db1 = sqlite3.connect(":memory:")
db1.execute("PRAGMA foreign_keys=ON")
try:
    db1.executescript(load(CORE_SQL))
    n = db1.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
    check("① core_schema 空库独立建库", n == len(CORE), "tables=%d 期望=%d" % (n, len(CORE)))
except Exception as e:
    check("① core_schema 空库独立建库", False, str(e)[:120])

# ② core+product 同库依次建库
db2 = sqlite3.connect(":memory:")
db2.execute("PRAGMA foreign_keys=ON")
try:
    db2.executescript(load(CORE_SQL) + load(PROD_SQL))
    t = db2.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
    v = db2.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view'").fetchone()[0]
    check("② 同库依次建库", t == 57 and v == 3, "tables=%d(期望57) views=%d(期望3)" % (t, v))
except Exception as e:
    check("② 同库依次建库", False, str(e)[:120])

# ③/④ FK 方向门禁 + foreign_key_check（在 ② 的同库上）
def fk_map(conn):
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    m = {}
    for t in tables:
        m[t] = [(r[2] if r[2] else "rowid") for r in conn.execute(
            "PRAGMA foreign_key_list(%s)" % t)]
    return m

m = fk_map(db2)
prod_bad = [(t, tgt) for t, tgts in m.items() if t not in CORE
            for tgt in tgts if tgt in CORE and tgt != "users"]
check("③a product FK 只许→users(id)", not prod_bad, str(prod_bad[:5]))
core_bad = [(t, tgt) for t, tgts in m.items() if t in CORE
            for tgt in tgts if tgt not in CORE]
check("③b core FK 不指向 product", not core_bad, str(core_bad[:5]))
viol = db2.execute("PRAGMA foreign_key_check").fetchall()
check("④ foreign_key_check 零违规", not viol, "%d rows" % len(viol))

# ⑤ 实库同扫描（防漂移）
try:
    live = sqlite3.connect("file:%s?mode=ro" % LIVE_DB.replace("\\", "/"), uri=True)
    ml = fk_map(live)
    lb = [(t, tgt) for t, tgts in ml.items() if t not in CORE
          for tgt in tgts if tgt in CORE and tgt != "users"]
    cb = [(t, tgt) for t, tgts in ml.items() if t in CORE
          for tgt in tgts if tgt not in CORE]
    check("⑤ 实库 FK 方向同门禁", not lb and not cb, "prod:%s core:%s" % (lb[:3], cb[:3]))
except Exception as e:
    check("⑤ 实库 FK 方向同门禁", False, str(e)[:120])

print()
if fails:
    print("verdict: FAIL:%s" % ",".join(fails)); sys.exit(1)
print("verdict: PASS（两份 DDL 可独立建库 + FK 方向门禁绿）")
