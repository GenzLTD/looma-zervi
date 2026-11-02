# 双轨账本边界（写死）— looma / 天翼轨

> Lock 2 仓内口径（大陆）。海外 SG 见 `Vultr-Genzltd/docs/dual-track-ledger-boundary.md`。  
> Project Store 汇总：`docs/dual-track-gate-prs.md`。

---

## Lock 2 — 两本物理库

| 项 | 口径 |
| --- | --- |
| 双轨 | **两本物理库**：本仓 → 天翼 CN；`Vultr-Genzltd` → 新加坡 SG |
| 认人 | 同轨：`principal_sub` / `(issuer, subject)` 规则同源（`identity/ledger_subject.py`） |
| 跨区并账 | **不是默认**。禁止假定 CN 余额自动出现在 SG |

「一套契约」= `payment.v1` 同 blob（海外 CI 对 tip 断言）。「一本账」= **同物理库内**多壳同 `users.id`。

---

## Lock 1 — 契约真源

- 真源文件：`backend/contracts/payment.v1.json`
- 钉：`contracts/payment.v1.PIN.json`（blob + tip sha）
- 海外 `Deploy stack` 的 `dual-track-gates` 对 **本仓 tip** 比 blob；漂移阻断 tag/deploy

GFCC `contracts/gfcc/SOURCE.json` 消费者钉仍受 playbook（1.6.0）约束；海外默认 `STRICT_GFCC_SOURCE=0`。

---

## Lock 3 / 4

- 认人模块：`backend/src/identity/`（海外必须同 blob 携带）
- `/health`：暴露 `looma_sha`（=`git_commit` 或 env）、以及若注入则 `vultr_tag`/`stack_sha`（CN 部署通常为 null）
- 验收：同区双登录同账；跨区负例（不并账）

---

## 不做

- 不 live 部署 SG、不推生产 `stack-v*`
- 不在本仓发明第二套 rsync→SG（见 `deploy-sg.yml` 派发 Vultr）
