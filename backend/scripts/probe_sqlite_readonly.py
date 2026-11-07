# -*- coding: utf-8 -*-
"""诊断：并发写同一 SQLite 库时偶发 `attempt to write a readonly database`。

背景（验证链路 §14.5 坑 33）：NFR 并发压测在写端点（consent grant → audit_logs INSERT）
上观测到 1–4% 的 `sqlite3.OperationalError: attempt to write a readonly database`，
且**只出现在并发首轮**、之后稳定。本脚本用纯 sqlite3 复刻 `DatabaseManager._connect()`
的 PRAGMA 顺序，把「是不是我们自己的 PRAGMA / 业务 SQL 写错」这件事排除掉。

四组对照（每组独立临时库，互不干扰）
  A 同一库文件 + 每操作新建连接            ← 服务端真实形态
  B 同一库文件 + 新建连接 + 失败重试 N 次   ← 候选缓解
  C 多个不同库文件 + 每操作新建连接         ← 若为 0 → 说明是"同一文件"的文件层竞态
  D 单线程 + 每操作新建连接                ← 若为 0 → 说明与并发有关

用法（backend/ 下）：
    ./.venv/Scripts/python.exe scripts/probe_sqlite_readonly.py
    ./.venv/Scripts/python.exe scripts/probe_sqlite_readonly.py --threads 8 --rounds 40 --retry 3

判据：A/C/D 的失败数与 B 的重试次数一起看。A 有失败、C/D 为 0、B 为 0 ⇒
根因在「同一库文件的并发句柄」，缓解手段 = 有限重试；与 PRAGMA 写法无关
（改 PRAGMA 顺序 / 只设一次 / synchronous=NORMAL 的对照组失败数一致）。
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import tempfile
import threading


def _connect(db: str) -> sqlite3.Connection:
    """复刻 DatabaseManager._connect() 的 PRAGMA 顺序。"""
    conn = sqlite3.connect(db, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _one_write(db: str) -> None:
    conn = _connect(db)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS t(x INTEGER)")
        conn.execute("INSERT INTO t(x) VALUES (1)")
        conn.commit()
    finally:
        conn.close()


def _run(name: str, threads: int, rounds: int, *, shared: bool, retry: int = 1) -> int:
    tmp = tempfile.mkdtemp(prefix="probe-ro-")
    shared_db = os.path.join(tmp, "shared.db")
    errors: list = []
    retried = [0]
    lock = threading.Lock()
    barrier = threading.Barrier(threads)

    def worker(idx: int) -> None:
        db = shared_db if shared else os.path.join(tmp, "db%d.db" % idx)
        barrier.wait()
        for _ in range(rounds):
            last = None
            for attempt in range(retry):
                try:
                    _one_write(db)
                    if attempt:
                        with lock:
                            retried[0] += 1
                    last = None
                    break
                except sqlite3.OperationalError as e:
                    last = e
            if last is not None:
                with lock:
                    errors.append(str(last))

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    total = threads * rounds
    extra = "（重试后成功 %d）" % retried[0] if retry > 1 else ""
    print("%-30s 请求=%-4d 失败=%-3d %s" % (name, total, len(errors), extra), flush=True)
    if errors:
        uniq: dict = {}
        for m in errors:
            uniq[m] = uniq.get(m, 0) + 1
        for msg, cnt in sorted(uniq.items(), key=lambda x: -x[1])[:3]:
            print("      %dx  %s" % (cnt, msg[:110]), flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return len(errors)


def main() -> None:
    ap = argparse.ArgumentParser(description="SQLite 并发写 SQLITE_READONLY 诊断")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--rounds", type=int, default=40, help="每线程写次数")
    ap.add_argument("--retry", type=int, default=3, help="B 组单次写的最多尝试次数")
    args = ap.parse_args()

    print("python=%s sqlite=%s" % (__import__("sys").version.split()[0], sqlite3.sqlite_version), flush=True)
    a = _run("A 同库/新连接/不重试", args.threads, args.rounds, shared=True)
    b = _run("B 同库/新连接/重试%d次" % args.retry, args.threads, args.rounds, shared=True, retry=args.retry)
    c = _run("C 不同库/新连接", args.threads, args.rounds, shared=False)
    d = _run("D 单线程/新连接", 1, args.threads * args.rounds, shared=True)
    print("\n汇总：A=%d B=%d C=%d D=%d" % (a, b, c, d), flush=True)
    print("判读：A>0 且 C=D=0 且 B=0 ⇒ 同一库文件的并发句柄竞态，重试可解。", flush=True)


if __name__ == "__main__":
    main()
