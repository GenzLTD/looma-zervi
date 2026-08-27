# 成就体系 Layer 5 — 与 PlanetX Mission 映射

> **版本：** 0.1 · **日期：** 2026-07-13  
> **状态：** 映射表（36 格全量规格见 declare `成就体系设计文档.md`，待逐步迁入）  
> **前置：** [game.v1.json](../backend/contracts/game.v1.json) 四 mission 契约化完成后再扩 UI  
> **关联：** [ZERVI_GENZER_IMPLEMENTATION.md](./ZERVI_GENZER_IMPLEMENTATION.md) §6

---

## 1. 原则

1. **先 4 mission，后 36 格** — Hub 闯关闭环是成就触发真源。  
2. **interview 域后置** — 面试模拟相关成就依赖未来 `/v1/interview/*`，不阻塞 match 共识 P0。  
3. **影响类 ← share + social** — 传播、裂变、六度关系计入 Layer 5，支撑个人信用叙事。

---

## 2. 四 Mission → 成就（L5-0 映射）

| Mission | XP | 优先成就（declare #） | 触发条件（v1） |
|---------|-----|----------------------|----------------|
| `personality` | 50 | #1 首次测试 · #15 面试达人 | mission-complete(personality) |
| `team` | 80 | #23 舰队指挥官 | mission-complete(team) |
| `match` | 40 | 验证组队成功 · #（待定）星际完美共振 | mission-complete(match) 且 consensus_verified |
| `share` | 30 | 影响类 #29–35 | mission-complete(share) 或 spread_count 阈值 |

---

## 3. 稀有度与 UI

| 稀有度 | 占比 | PlanetX 首版是否实现 |
|--------|------|---------------------|
| N | ~22% | ✅ mission 完成即解锁 |
| R–UR | 其余 | 📋 L5-2 起按 analytics / 计数器 |

首版 Hub 仅保证：**mission 完成 → AchievementPopup**（已有组件），不建独立 36 格墙。

---

## 4. 待迁入（来自 declare 成就体系设计文档）

- 量级类 7 格 → interview 模块上线后  
- 坚持类 7 格 → DAU / 连续登录 analytics  
- 技能类 8 格 → 多领域 interview + 题库  
- 突破类 7 格 → Offer / 排行榜（P2）  
- 影响类 7 格 → share + social spread（**与 Line 2/3 战略线绑定**）

---

## 5. 契约化路径

```text
game.v1.json (4 missions)  →  本映射表  →  achievements.v1.json (36 格)  →  Hub / 公开档案徽章
```

`achievements.v1.json` 在 **ZG-M3** 前不必起草全量；M-1 完成后更新「验证组队成功」文案与成就 ID。
