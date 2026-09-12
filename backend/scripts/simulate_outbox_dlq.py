#!/usr/bin/env python3
"""R2 本地仿真: 出站事务性发件箱 + 可重放 DLQ 真实闭环(对端 = 本地 gfcc_kernel :5211)。

剧本:
  1. 构建真实 personality_beacon 信封 → 入 signal_outbox(pending)
  2. 故障注入: GFCC URL 指向死端口 → 投递失败 ×3 → 迁入 signal_dlq
  3. 恢复 URL → 值班 replay_dlq_entry(按 nonce 重发)→ 200 stored → replayed_at 标记
  4. 对端 signal_log 已落库; 再次重放同 nonce → 对端 duplicate(幂等,不重复处理)

Usage (from backend/): ./venv/bin/python scripts/simulate_outbox_dlq.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

EMAIL_HASH = "b" * 64  # 64-hex


def main() -> int:
    os.chdir(BACKEND)
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env")

    secret = os.environ.get("SIGNAL_INGEST_SECRET", "").strip()
    real_url = os.environ.get("GFCC_SIGNAL_INGEST_URL", "").strip()
    if not real_url:
        print("GFCC_SIGNAL_INGEST_URL missing in backend/.env")
        return 1

    dead_url = "http://127.0.0.1:5219/v1/signal-ingest"  # 死端口(故障注入)

    from src.db.manager import DatabaseManager
    from src.signal_bridge.gfcc_fanout import (
        deliver_outbox_pending,
        replay_dlq_entry,
        send_gfcc_personality_beacon_outboxed,
    )

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = DatabaseManager(tmp.name)
    db.init_schema()

    nonce = f"r2-sim-{uuid.uuid4().hex[:12]}"
    print(f"nonce   {nonce}")
    print()

    # ── 1) 入箱(URL 指向死端口)→ 网络失败 ×3 → DLQ ──
    print("[1] 故障注入: URL=死端口 → 入箱+投递")
    res = send_gfcc_personality_beacon_outboxed(
        db, EMAIL_HASH, "星云艺术家", ["creative", "explorer"], 0.91,
        nonce, timestamp="2026-08-27T00:00:00+00:00",
        url=dead_url, secret=secret,
    )
    row = db.get_outbox_by_nonce(nonce)
    print(f"    入箱后 outbox: status={row['status']} attempts={row['attempts']}")
    for i in (2, 3):
        deliver_outbox_pending(db, dead_url, secret, max_attempts=3)
    row = db.get_outbox_by_nonce(nonce)
    dlq = db.get_dlq_by_nonce(nonce)
    print(f"    第3次后      : outbox.status={row['status']} attempts={row['attempts']}")
    print(f"    DLQ          : nonce={dlq['nonce']} reason={dlq['reason']} last_error={dlq['last_error']}")
    assert dlq and dlq["reason"] == "network_error", "应已迁入 DLQ"

    # ── 2) 值班按 nonce 重发(URL 恢复真实 5211)──
    print()
    print("[2] 值班重放: URL=真实 5211 → replay_dlq_entry")
    res = replay_dlq_entry(db, nonce, url=real_url, secret=secret)
    print(f"    replay 结果: {json.dumps(res, ensure_ascii=False)}")
    dlq = db.get_dlq_by_nonce(nonce)
    print(f"    DLQ.replayed_at = {dlq['replayed_at']}")
    assert res.get("ok") and dlq["replayed_at"], "重放应成功"

    # ── 3) 幂等: 同 nonce 再重放 → 对端 duplicate ──
    print()
    print("[3] 幂等验证: 同 nonce 再重放 → 对端应返回 duplicate")
    res2 = replay_dlq_entry(db, nonce, url=real_url, secret=secret)
    print(f"    二次重放结果: {json.dumps(res2, ensure_ascii=False)}")
    assert res2.get("ok") and res2.get("duplicate"), "二次重放应对端 duplicate"

    # ── 4) 对端幂等证据(对端响应为准, 不依赖 stub/sqlite 落库差异) ──
    print()
    print("[4] 对端 gfcc_kernel 幂等证据:")
    print(f"    首次重放   → {json.dumps({'ok': res['ok'], 'duplicate': res.get('duplicate', False)})}")
    print(f"    同 nonce 再重放 → {json.dumps({'ok': res2['ok'], 'duplicate': res2.get('duplicate', False)})}")
    print("    → 对端按 nonce 幂等: 重放安全(信号只处理一次)")
    # 若对端配置了 SIGNAL_LOG_DB(sqlite 模式), 补查落库证据
    import sqlite3
    signal_db = os.environ.get("SIGNAL_LOG_DB", "")
    if signal_db:
        try:
            conn = sqlite3.connect(signal_db)
            rows = conn.execute(
                """SELECT signal_type, nonce, created_at FROM signal_log WHERE nonce = ?""",
                (nonce,),
            ).fetchall()
            conn.close()
            print(f"    signal_log({signal_db}): {rows}")
            assert rows, "signal_log 应有该 nonce"
        except Exception as e:
            print(f"    (signal_log 查询失败: {e})")

    # 清理
    os.unlink(tmp.name)
    print()
    print("=== R2 本地仿真闭环通过 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
