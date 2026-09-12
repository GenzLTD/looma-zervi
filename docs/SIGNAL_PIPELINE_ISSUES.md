# 信号管道 Issue 清单 — 仓内指针（PlanetX / looma-zervi）

> **归属权（2026-08-27）**：本清单已**归集到本地研制侧真源**：`~/THOMAS/docs/SIGNAL_PIPELINE_ISSUES.md`。
> 本文件自 2026-08-27 起**不再双线维护**，仅作仓内指针；一切更新请改真源。
> 依据：`~/THOMAS/docs/CONSISTENCY_GOVERNANCE.md` 原则 1 ——「本地（ServBay）= 开发 + 验证真源，真源唯一」。

## 本仓交付摘要（T0/T1/T3 — 全部 ✅）

| ID | 任务 | 状态 |
|----|------|------|
| T0 | `users.email_hash` 对齐 + `get_user_by_email_hash` | ✅ 2026-08-14 |
| T1 | `POST /v1/game/signal-ingest`（HMAC + SQLite 幂等） | ✅ 2026-08-14 |
| T3 | `personality_beacon` egress（profile-sync 触发） | ✅ 2026-08-14 |
| T5 | 本地 mock 自测（链 A/B 双信封 200）；2026-09-13 复核三态 stored / duplicate / unauthorized | ✅ 2026-08-27 |
| T6 | 真联调（四态 + matched 写库） | ✅ 2026-08-14 |
| R2 | 出站事务性发件箱 + 可重放 DLQ（`signal_outbox`/`signal_dlq`/`replay_dlq.py`/仿真闭环）；**仅 PlanetX 侧**，DemoPPI 出站仍为 best-effort 重试 | ✅ 2026-08-27 |

## 指针

- 真源（改这里）：`~/THOMAS/docs/SIGNAL_PIPELINE_ISSUES.md`
- 权威分解：`~/THOMAS/docs/ECOSYSTEM_SIGNAL_ADAPTER_GUIDE.md` §5
- 本地研制口径：`~/THOMAS/docs/CONSISTENCY_GOVERNANCE.md`
- DemoPPI 侧仓内指针：`~/THOMAS/demo-ppi-mvp/docs/SIGNAL_PIPELINE_ISSUES.md`
