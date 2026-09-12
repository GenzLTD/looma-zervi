#!/usr/bin/env python3
"""R2 值班重放 CLI: 从 signal_dlq 按 nonce 重发出站信号(原 body 逐字节 → 签名不变 → 对端 nonce 幂等)。

Usage (from backend/):
  ./venv/bin/python scripts/replay_dlq.py list
  ./venv/bin/python scripts/replay_dlq.py replay --nonce <nonce>
  ./venv/bin/python scripts/replay_dlq.py replay --all

Options:
  --db <path>     覆盖 DATABASE_PATH(默认读 env / backend/data/looma.db)
  --url <url>     覆盖 GFCC_SIGNAL_INGEST_URL
  --secret <s>    覆盖 SIGNAL_INGEST_SECRET
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(BACKEND / ".env")
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="R2 signal_dlq 值班重放")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出 DLQ")
    p_list.add_argument("--limit", type=int, default=100)

    p_replay = sub.add_parser("replay", help="按 nonce 重发(或 --all)")
    p_replay.add_argument("--nonce", default="")
    p_replay.add_argument("--all", action="store_true")

    for p in (p_list, p_replay):
        p.add_argument("--db", default="")
        p.add_argument("--url", default="")
        p.add_argument("--secret", default="")

    args = parser.parse_args()

    os.chdir(BACKEND)
    _load_env()

    db_path = args.db or os.environ.get("DATABASE_PATH", "").strip()
    if not db_path:
        db_path = str(BACKEND / "data" / "looma.db")
    db_path = str(Path(db_path).expanduser().resolve())

    url = args.url or os.environ.get("GFCC_SIGNAL_INGEST_URL", "").strip()
    secret = args.secret or os.environ.get("SIGNAL_INGEST_SECRET", "").strip()

    from src.db.manager import DatabaseManager
    from src.signal_bridge.gfcc_fanout import replay_dlq_entry

    db = DatabaseManager(db_path)

    if args.cmd == "list":
        rows = db.list_dlq(limit=args.limit)
        if not rows:
            print("signal_dlq is empty")
            return 0
        print(f"{'nonce':<40} {'type':<22} {'reason':<16} {'attempts':<8} {'moved_at':<20} {'replayed_at'}")
        for r in rows:
            print(
                f"{r['nonce']:<40} {r['signal_type']:<22} {r['reason']:<16} "
                f"{r['attempts']:<8} {r['moved_at']:<20} {r.get('replayed_at') or ''}"
            )
        return 0

    # replay
    if not url:
        print("GFCC_SIGNAL_INGEST_URL missing (env / --url)")
        return 1
    if not secret:
        print("SIGNAL_INGEST_SECRET missing (env / --secret)")
        return 1

    if args.all:
        entries = db.list_dlq()
        if not entries:
            print("signal_dlq is empty — nothing to replay")
            return 0
    elif args.nonce:
        entry = db.get_dlq_by_nonce(args.nonce)
        if not entry:
            print(f"nonce {args.nonce} not in signal_dlq")
            return 2
        entries = [entry]
    else:
        parser.error("replay 需要 --nonce 或 --all")

    ok_count = 0
    for entry in entries:
        nonce = entry["nonce"]
        result = replay_dlq_entry(db, nonce, url=url, secret=secret)
        if result.get("ok"):
            ok_count += 1
            dup = " (duplicate)" if result.get("duplicate") else ""
            print(f"[OK]   {nonce} replayed{dup}")
        else:
            print(
                f"[FAIL] {nonce} — {result.get('reason') or result.get('status')} "
                f"(仍在 DLQ, 可稍后重试)"
            )
    print(f"\n{ok_count}/{len(entries)} replayed successfully")
    return 0 if ok_count == len(entries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
