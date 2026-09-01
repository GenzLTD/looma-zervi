# 全量回归报告 — 2026-08-27

> **结果：142 passed, 26 warnings（3 分 41 秒）**。信号桥（Bridge 2/3 T0/T1/T3）与全部业务域无回归。

## 命令

```bash
cd /Users/jason/thomas/looma-zervi/backend
./venv/bin/python -m pytest tests/ -q --tb=short -p no:cacheprovider
```

环境：`backend/venv`（python3.12）；`tests/conftest.py` 提供临时 SQLite DB + test env（`WECHAT_DEV_MODE=true`、`DEEPSEEK_API_KEY=skip`、`JWT_SECRET=test-secret`）。

## 结果

```
142 passed, 26 warnings in 221.95s (0:03:41)
```

## 覆盖域（13 个测试文件）

| 域 | 文件 |
|----|------|
| 信号桥 T0（email hash 跨端向量） | `test_email_hash.py` |
| 信号桥 T1（signal-ingest：HMAC + SQLite 幂等） | `test_signal_ingest.py` |
| 信号桥 T3（personality_beacon egress：签名头/无明文 email/端到端触发） | `test_personality_beacon.py` |
| 信号桥 fanout（gfcc 联动） | `test_gfcc_fanout.py` |
| 游戏闭环（mission / match / profile-sync） | `test_game.py`、`test_closed_loop.py` |
| 诗词（列表/详情/搜索/随机） | `test_poetry.py` |
| 认证 / 合规（JWT、consent） | `test_auth.py`、`test_compliance.py` |
| 支付与套餐门禁 | `test_payment_guard.py`、`test_payment_plans.py`、`test_tier_gating.py` |
| 分析 | `test_analytics.py` |

## Warnings 说明

26 个 warnings 全部为 `InsecureKeyLengthWarning`（测试 JWT 密钥 `test-secret` 11 字节 < RFC 7518 建议 32 字节），仅测试夹具所致，非缺陷。

## 结论

- 信号桥专项（T0 向量互验 / T1 幂等 / T3 egress 签名）持续通过，与 2026-08-14 真联调结果一致。
- 全部业务域回归无失败，可复述命令：`cd backend && ./venv/bin/python -m pytest tests/ -q`。
