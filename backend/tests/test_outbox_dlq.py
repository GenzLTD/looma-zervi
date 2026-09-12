"""R2: 出站事务性发件箱 + 可重放 DLQ — PlanetX 发送侧单测。

覆盖:
  - 入箱幂等(nonce 唯一)
  - 投递成功 → delivered
  - 4xx 永久失败 → DLQ(permanent_4xx)
  - 网络失败 → 保留 pending,超限进 DLQ(network_error)
  - 重放:成功标 replayed / 失败仍留 DLQ / 不存在的 nonce 返回 not_in_dlq
  - send_gfcc_personality_beacon_outboxed:skip 不落库 / 正常入箱+投递
  - 重试耗尽日志带出 nonce(丢失信号可定位)
"""
from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch

from src.db.manager import DatabaseManager
from src.signal_bridge.gfcc_fanout import (
    deliver_outbox_pending,
    replay_dlq_entry,
    send_gfcc_personality_beacon_outboxed,
)

URL = "http://127.0.0.1:5211/v1/signal-ingest"
SECRET = "test-secret-123"
EMAIL_HASH = "a" * 64


class _Resp:
    """stand-in for urllib response."""

    def __init__(self, status=200, body=b'{"status":"stored"}'):
        self.status = status
        self._body = body

    def read(self):
        return self._body


def _make_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = DatabaseManager(tmp.name)
    db.init_schema()
    return db, tmp.name


class OutboxTest(unittest.TestCase):
    def setUp(self):
        self.db, self.path = _make_db()
        self.body = json.dumps(
            {
                "signal_type": "personality_beacon",
                "user_id_hash": EMAIL_HASH,
                "nonce": "nonce-abc-001",
                "payload": {"personality_type": "ENFP", "source": "planetx"},
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def tearDown(self):
        import os
        os.unlink(self.path)

    # ---- 入箱幂等 ----
    def test_enqueue_idempotent_by_nonce(self):
        self.assertTrue(self.db.enqueue_signal_outbox("personality_beacon", "n1", self.body))
        self.assertFalse(self.db.enqueue_signal_outbox("personality_beacon", "n1", self.body))
        rows = self.db.list_outbox_pending()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["nonce"], "n1")
        self.assertEqual(rows[0]["status"], "pending")

    # ---- 投递成功 ----
    @patch("src.signal_bridge.gfcc_fanout._post_body")
    def test_deliver_success_marks_delivered(self, mock_post):
        mock_post.return_value = {"ok": True, "status": 200, "duplicate": False}
        self.db.enqueue_signal_outbox("personality_beacon", "n1", self.body)
        stats = deliver_outbox_pending(self.db, URL, SECRET)
        self.assertEqual(stats["delivered"], 1)
        self.assertEqual(stats["dlq"], 0)
        row = self.db.get_outbox_by_nonce("n1")
        self.assertEqual(row["status"], "delivered")
        self.assertIsNotNone(row["delivered_at"])
        # 原 body 逐字节传递(签名不变的基石)
        mock_post.assert_called_once_with(
            self.body.encode("utf-8"), URL, SECRET, max_retries=2, nonce="n1"
        )

    # ---- 4xx 永久失败 → DLQ ----
    @patch("src.signal_bridge.gfcc_fanout._post_body")
    def test_deliver_4xx_moves_to_dlq(self, mock_post):
        mock_post.return_value = {"ok": False, "status": 400}
        self.db.enqueue_signal_outbox("personality_beacon", "n1", self.body)
        stats = deliver_outbox_pending(self.db, URL, SECRET)
        self.assertEqual(stats["dlq"], 1)
        entry = self.db.get_dlq_by_nonce("n1")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["reason"], "permanent_4xx")
        self.assertEqual(entry["body"], self.body)  # 原 body 保留

    # ---- 网络失败:先 pending,超限进 DLQ ----
    @patch("src.signal_bridge.gfcc_fanout._post_body")
    def test_deliver_network_error_eventually_dlq(self, mock_post):
        mock_post.return_value = {"ok": False, "status": 0}
        self.db.enqueue_signal_outbox("personality_beacon", "n1", self.body)

        stats1 = deliver_outbox_pending(self.db, URL, SECRET, max_attempts=3)
        self.assertEqual(stats1["dlq"], 0)
        self.assertEqual(stats1["pending_left"], 1)
        row = self.db.get_outbox_by_nonce("n1")
        self.assertEqual(row["attempts"], 1)
        self.assertEqual(row["status"], "pending")

        stats2 = deliver_outbox_pending(self.db, URL, SECRET, max_attempts=3)
        stats3 = deliver_outbox_pending(self.db, URL, SECRET, max_attempts=3)
        self.assertEqual(stats3["dlq"], 1)
        entry = self.db.get_dlq_by_nonce("n1")
        self.assertEqual(entry["reason"], "network_error")

    # ---- 重放 ----
    @patch("src.signal_bridge.gfcc_fanout._post_body")
    def test_replay_success(self, mock_post):
        mock_post.return_value = {"ok": True, "status": 200, "duplicate": False}
        self.db.enqueue_signal_outbox("personality_beacon", "n1", self.body)
        self.db.move_outbox_to_dlq("n1", "network_error", "boom")
        res = replay_dlq_entry(self.db, "n1", URL, SECRET)
        self.assertTrue(res["ok"])
        self.assertFalse(res["duplicate"])
        entry = self.db.get_dlq_by_nonce("n1")
        self.assertIsNotNone(entry["replayed_at"])
        # 重放也用原 body(逐字节 → 对端幂等)
        mock_post.assert_called_once_with(
            self.body.encode("utf-8"), URL, SECRET, max_retries=3, nonce="n1"
        )

    @patch("src.signal_bridge.gfcc_fanout._post_body")
    def test_replay_failure_keeps_in_dlq(self, mock_post):
        mock_post.return_value = {"ok": False, "status": 0}
        self.db.enqueue_signal_outbox("personality_beacon", "n1", self.body)
        self.db.move_outbox_to_dlq("n1", "network_error", "boom")
        res = replay_dlq_entry(self.db, "n1", URL, SECRET)
        self.assertFalse(res["ok"])
        entry = self.db.get_dlq_by_nonce("n1")
        self.assertIsNone(entry["replayed_at"])

    def test_replay_unknown_nonce(self):
        res = replay_dlq_entry(self.db, "no-such-nonce", URL, SECRET)
        self.assertEqual(res["reason"], "not_in_dlq")

    # ---- 守契约入箱+投递 ----
    @patch("src.signal_bridge.gfcc_fanout._post_body")
    def test_send_outboxed_ok(self, mock_post):
        mock_post.return_value = {"ok": True, "status": 200, "duplicate": False}
        res = send_gfcc_personality_beacon_outboxed(
            self.db, EMAIL_HASH, "ENFP", ["creative"], 0.87,
            "nonce-outboxed-1", timestamp="2026-08-27T00:00:00+00:00",
            url=URL, secret=SECRET,
        )
        self.assertTrue(res["ok"])
        self.assertTrue(res["delivered"])
        row = self.db.get_outbox_by_nonce("nonce-outboxed-1")
        self.assertEqual(row["status"], "delivered")

    @patch("src.signal_bridge.gfcc_fanout._post_body")
    def test_send_outboxed_dlq(self, mock_post):
        # 4xx 永久失败 → 立即进 DLQ(网络/5xx 需多次才进,另行单测)
        mock_post.return_value = {"ok": False, "status": 400}
        res = send_gfcc_personality_beacon_outboxed(
            self.db, EMAIL_HASH, "ENFP", ["creative"], 0.87,
            "nonce-outboxed-2", timestamp="2026-08-27T00:00:00+00:00",
            url=URL, secret=SECRET,
        )
        self.assertFalse(res["ok"])
        self.assertTrue(res["dlq"])
        self.assertIsNotNone(self.db.get_dlq_by_nonce("nonce-outboxed-2"))

    def test_send_outboxed_skip_not_enqueued(self):
        # 无法映射的人格 → skip,不落库
        res = send_gfcc_personality_beacon_outboxed(
            self.db, EMAIL_HASH, "不存在的类型", None, None,
            "nonce-skip-1", url=URL, secret=SECRET,
        )
        self.assertTrue(res["skipped"])
        self.assertIsNone(self.db.get_outbox_by_nonce("nonce-skip-1"))

    # ---- 重试耗尽日志必须带出 nonce ----
    @patch("urllib.request.urlopen")
    def test_exhausted_retries_logs_nonce(self, mock_urlopen):
        # 丢失信号的定位线索只有 nonce；日志写 None 会让「按 nonce 重发」无从下手。
        mock_urlopen.side_effect = OSError("connection refused")
        self.db.enqueue_signal_outbox("personality_beacon", "n-lost", self.body)
        with self.assertLogs("looma.gfcc_fanout", level="WARNING") as cm:
            deliver_outbox_pending(self.db, URL, SECRET)
        self.assertIn("nonce=n-lost", "\n".join(cm.output))


if __name__ == "__main__":
    unittest.main()
