# PlanetX 工程闭环 P0 校准文档

> **这份文档的唯一目的**：冻结一份「代码现状」的共享事实源，终止「文档说没有 / 代码其实有」导致的反复分歧与重复建设。
>
> - **校准日期**：2026-08-08
> - **校准方式**：直接检索仓库源码（非转述文档），每条断言附文件路径与行号，可复现
> - **适用范围**：`looma-zervi` 仓库，PlanetX / SaaS / miniprogram / backend
> - **配套文档**：`PLANETX_GROWTH_LOOP_REDESIGN.md`（设计意图）、`PLANETX_REFERENCE_GAMES.md`（竞品活检）、`PLANETX_RESEARCH_PROPOSAL.md`（科研立项）

---

## 0. 一句话结论

**工程闭环缺口比文档描述的小得多，但比"只差一个 UI"大。**

真实缺口只有三块：
1. **C 端「被看见」出口缺失** —— PlanetX 没有信任档案页（SaaS 有）
2. **Match 共识门控未实现** —— 前端在调 `acknowledge`，后端无路由
3. **增长后半段未接线** —— 信号传播是硬编码 `0`，不是漏斗断，是 UI 没接数据

其余大量"未构建"的断言，**已被代码追上**。文档债让缺口看起来比代码更大。

---

## 1. 为什么需要这份文档

同一批 P0 问题，出现过三种互相矛盾的表述：

| 表述来源 | 说法 | 问题 |
|---|---|---|
| 早期规划文档 | 「四大能力全部代码未写」 | 与代码不符，会导致重复建设 |
| 校准意见 A | 「Timeline 是半成品」 | 低估了完成度（实际 8 端点全在） |
| 校准意见 B | 「先建 Timeline 地基」 | 地基已建完，该做的是灌数据 |

**风险**：下一个工程师照着过时文档，把已存在的 `timeline_routes.py` / `TimelineScreen.tsx` 重建一遍。这份对照表就是防呆装置。

---

## 2. 文档断言 vs 代码现状（核心对照表）

### 2.1 已被代码追上的断言（不要再重建）

| # | 文档断言 | 代码证据 | 校准后表述 |
|---|---|---|---|
| 1 | `timeline_events` 表未落库（E0.2） | `backend/src/db/manager.py:865` `CREATE TABLE IF NOT EXISTS timeline_events`，含 3 个索引（`:889/:891/:893`） | **已落库**，含 `(user_id, occurred_at)`、`(user_id, event_kind, occurred_at)`、`(source_system, source_ref)` 索引 |
| 2 | `/v1/timeline/*` API 未实现（E2.1） | `backend/src/api/routes/timeline_routes.py`，**8 个端点已实现** | **已实现**，见 2.2 端点清单 |
| 3 | Backfill 幂等灌入（E1.6）未实现 | `timeline_routes.py:136` `POST /bridge/backfill` | **端点已有**，缺口是「白名单映射是否覆盖 quiz/share/login」 |
| 4 | 成长曲线 API（E4.1）未实现 | `timeline_routes.py:128` `GET /growth` | **端点已有**，缺口是「空态是否诚实」 |
| 5 | PlanetX 时间线页面未构建（E3） | `frontend/packages/planetx/src/features/timeline/TimelineScreen.tsx` | **页面已有**（含 check-in / 项目记录） |
| 6 | 信任档案完全缺失 | `frontend/packages/saas/src/features/trust/TrustProfile.tsx`、`TrustVerify.tsx` | **SaaS 侧有**；缺口收敛为 **PlanetX C 端无** |
| 7 | Match 任务无法真正完成 | v0 已可 `mission-complete`（`can_complete_mission: true`） | **玩法闭环可通**；共识门控是阶段二增强，不是「任务点不亮」 |
| 8 | Timeline 事件模型未定义 | `backend/contracts/timeline.v1.json`、`frontend/packages/shared-core/src/types/timeline.ts` | **前后端契约都已存在** |

### 2.2 Timeline 已实现端点清单（`timeline_routes.py`）

| 方法 | 路径 | 行号 | 用途 |
|---|---|---|---|
| GET | `/` | `:34/:35` | 列出时间线 |
| POST | `/events` | `:60` | 创建事件 |
| PATCH | `/events/<event_id>` | `:97` | 修改事件 |
| DELETE | `/events/<event_id>` | `:118` | 删除单事件 |
| GET | `/growth` | `:128` | 成长曲线 |
| POST | `/bridge/backfill` | `:136` | 幂等回灌 |
| GET | `/export` | `:153` | 数据导出（合规能力，科研立项可复用） |
| DELETE | `/me` | `:190` | 清空我的全部事件（数据主体权利） |

> **重要**：`/export` 与 `DELETE /me` 已经是 PIPL/GDPR 意义上的「数据可携权 + 删除权」实现。`PLANETX_RESEARCH_PROPOSAL.md` 第 6 章的合规缺口应据此下调——不是从零建，是补同意分级。

### 2.3 仍然成立的真缺口

| # | 缺口 | 代码证据 | 严重度 |
|---|---|---|---|
| A | **红线未清**：`trust_score(degrees)` 仍在 API 暴露 | `backend/src/social/social_bfs.py:52` `def compute_trust_score(degrees)`；被 `social_routes.py:18/94/128` 引用并 `jsonify(trust_score=...)` 输出（`:112`、`:132`） | 🔴 会与新信任建模打架 |
| B | **`match/acknowledge` 后端缺失** | 前端已在调：`shared-core/src/api/createApi.ts:238`、`createMiniApi.ts:144`、`routes.ts:26` `GAME_MATCH_ACK: "/v1/game/match/acknowledge"`；调用点 `planetx/.../MatchScreen.tsx:140`、`miniprogram/pages/match/index.ts:183`。后端 `src/` 无对应路由实现 | 🔴 前端调空 |
| C | **`match_consensus` 表未创建** | `backend/contracts/game.v1.json` 有契约，`db/manager.py` 无建表 | 🔴 凭证无处落 |
| D | **信号传播硬编码 0** | `planetx/src/features/hub/HubScreen.tsx:237` `{ v: 0, l: '信号传播' }`；小程序同构 `miniprogram/pages/hub/index.wxml:109` | 🔴 分享再成功也永远是 0 |
| E | **PlanetX 无 C 端信任档案页** | `planetx/src/features/` 目录仅有 `auth / feedback / hub / match / onboarding / quiz / result / timeline / tspace`，**无 `trust/`** | 🔴 价值主张断在最后一厘米 |

> 校准要点：B 的准确表述是**「后端未实现」**，不是「返回 501 占位」。没有占位路由，前端调用会打到 404/路由未注册，这是两种不同的排障路径，写错会浪费工程师时间。

---

## 3. 校准后的缺口重新定性

| 原表述 | 校准后表述 |
|---|---|
| 「四大产品能力全部停留在规划文档阶段」 | **Timeline 引擎已建完（表+8端点+页面+契约），缺的是「灌满数据 + 当成主线叙事」** |
| 「数据在库里，但被看见的出口尚未存在」 | **半对**：Trust 数据在库且 SaaS 有页；缺的是 **PlanetX C 端出口** + **凭证持续生成的门控** |
| 「工程闭环缺口集中在变现层」 | **更准确**：缺口集中在 **C 端出口 + 共识门控 + 增长接线**三点，且其中一点（信号传播）是接线 bug 而非功能开发 |

**闭环公式不变**：行为 → 凭证 → 被看见 → 下一动机
**当前断点**：凭证生成（B/C）与被看见（E）之间，以及下一动机（D）。

---

## 4. 校准后的 P0 执行序列

| 序 | 动作 | 类型 | 为什么是这个位置 | 依赖 |
|---|---|---|---|---|
| **P0-0** | 清除 `social_bfs.compute_trust_score(degrees)` 及 `social_routes` 中的 `trust_score` 输出字段 | 清理（红线） | 唯一**会主动和新系统打架**的孤儿：source 无 sink，且违反「不做用户可见信用分」红线。不清它，新档案页上线即自相矛盾 | 无 |
| **P0-1** | **配对切片**：Timeline backfill 灌满（quiz/share/login 白名单）+ PlanetX C 端「我的信任档案」页 | substrate + 出口 | 档案页首版消费已存在的 `trust_attestations`（无需等 Timeline），Timeline 灌满后档案自动变厚。两者同 Sprint 交付 | P0-0 |
| **P0-2** | 拆掉 `HubScreen.tsx:237` 硬编码 `{v:0}`，接真实传播计数（Web + 小程序同构） | 接线修复 | 不是功能阶段，是 bug。工作量小、可见度高 | 无（可并行） |
| **P0-3** | Match 共识门控：建 `match_consensus` 表 + 实现 `POST /v1/game/match/acknowledge` | 凭证生成 | **不阻塞 v0 `mission-complete`**——v0 旁路继续可用，共识作为增强 | P0-1 |
| **P0-4** | 增长后半段：通关强制进时间线/档案/邀请回流；人格标签随行为修订 | 闭环动机 | 依赖前三项产出真实行为后才有东西可增长 | P0-1~3 |
| **P0-5** | 内测 8 项验收 + 部署 `b8c8f30`（optional_auth 修复）+ HTTPS 证书 | 可验证 | 决定能否对真人验证，不决定产品逻辑是否成立 | P0-4 |

### 4.1 为什么 P0-0 排在最前

`social_bfs.compute_trust_score(degrees)` 是按「社交距离度数」算出的 0-100 分数，直接从 API 输出（`social_routes.py:112/:132`）。它与 `TRUST_LAYER.md` 的「不做用户可见信用分」红线冲突。

排在最前的理由不是洁癖，是**语义冲突会污染验收**：新信任档案页一旦上线，同一个用户会同时存在「旧 degrees 分数」与「新 attestation 证据」两套信任语义，测试永远过不了「诚实基线」这一条。

### 4.2 为什么 P0-1 是配对切片而非二选一

两份校准意见的分歧在此，仲裁如下：

| 意见 | 主张 | 成立部分 | 不成立部分 |
|---|---|---|---|
| A：档案页优先 | 最快让用户看见闭环 | ✅ `trust_attestations` 已在库，档案页首版**无需等 Timeline** | ❌ 档案的「成长叙事」厚度确实依赖 Timeline |
| B：Timeline 优先 | Timeline 是所有能力的 substrate | ✅ substrate 论证成立 | ❌ Timeline 地基**已经建完**，不需要「先起」，需要的是灌数据 |

**结论**：两者不是先后关系，是同一垂直切片的两端。档案页消费存量 attestations 立即可跑；Timeline backfill 到位后档案自动变厚。**同 Sprint 交付，互不阻塞。**

---

## 5. 开工前必须锁定的三件事（防返工）

1. **事件 schema 是否 final** —— `contracts/timeline.v1.json` 与 `shared-core/src/types/timeline.ts` 必须一致后再 backfill，否则灌完返工。
2. **backfill 白名单覆盖范围** —— 至少覆盖 quiz 完成、share 动作、login 事件；映射规则需幂等（`source_system + source_ref` 索引已就绪，见 `manager.py:893`）。
3. **档案页展示语义以主文档第 11 章翻译层为准** —— 行为证据 + 验证链进，XP / 舰队皮肤 / 等级不进。**禁止前端按旧 `social_bfs` 语义画分数条**，否则又回到红线。

---

## 6. 需要同步修订的文档债

以下文档含已过时断言，建议在对应位置加「⚠️ 已由 `ENGINEERING_CLOSED_LOOP_P0.md` 校准（2026-08-08）」标注：

| 文档 | 过时断言 | 应改为 |
|---|---|---|
| `TIMELINE_PHASE1_BACKLOG.md` | E0.2 / E2.1 / E1.6 / E4.1 / E3 未实现 | 全部已实现，缺口转为「数据灌满 + 空态诚实 + 主线化」 |
| `MANIFESTO.md` §6.1 | 「信任数据在数据库里，但没有被呈现为面向用户的产品」 | 收敛为「PlanetX C 端无档案页」（SaaS 已有） |
| `TRUST_LAYER.md` §7 | 诚实基线表述 | 同上，并补「红线 `trust_score(degrees)` 待清理」 |
| `ZERVI_GENZER_IMPLEMENTATION.md` §4 | M-3「acknowledge 返回 501」 | 改为「后端未实现路由，前端已接入」 |
| `PLANETX_RESEARCH_PROPOSAL.md` §6 | 合规能力从零建 | 下调：`/export` 与 `DELETE /me` 已实现数据可携权与删除权 |

---

## 7. 待定项（PLACEHOLDER）

| 项 | 状态 | 谁来定 |
|---|---|---|
| `match_consensus` 表结构（是否需 quorum 字段、共识超时） | [PLACEHOLDER] | 后端 + 设计 |
| 信号传播计数口径（注册即计 vs 完成首任务才计） | [PLACEHOLDER] · 设计倾向后者（防刷量） | 增长 + 设计 |
| Timeline backfill 白名单最终清单 | [PLACEHOLDER] | 后端 |
| 档案页首版展示字段（attestation 全量 vs 精选） | [PLACEHOLDER] | 设计 + 前端 |
| 人格标签修订触发规则（每 N 行为 or 每 7 天） | [PLACEHOLDER] · 主文档建议取先到者 | 设计 |

---

## 8. 复现方式（下次有分歧先跑这个）

```bash
# 红线是否还活着
rg "social_bfs|compute_trust_score" backend/src

# Timeline 实现程度
rg "timeline_events" backend/src
rg "@timeline_bp.route" backend/src/api/routes/timeline_routes.py

# acknowledge 后端是否实现
rg "match/acknowledge|match_consensus" backend/src

# 信号传播是否仍硬编码
rg "信号传播" frontend/packages --glob '!*dist*'

# PlanetX 是否有 trust 出口
ls frontend/packages/planetx/src/features/
```

**规则**：任何关于「X 未实现」的断言，进文档前先跑一遍上述检索。**没有文件路径与行号的缺口断言，不进 P0 清单。**

---

---

## 9. 实施状态（2026-08-08 落地）

| 序 | 动作 | 状态 | 落点 |
|---|---|---|---|
| P0-0 | 清除 `trust_score(degrees)` API 输出 | ✅ | `social_bfs.py` 删除函数；`social_routes.py` 不再返回 `trust_score` |
| P0-1a | Timeline backfill 灌满 | ✅ | `events.backfill_user_timeline`：quiz + account_joined + missions + share/invite + match/resume |
| P0-1b | PlanetX C 端信任档案 | ✅ | `planetx/src/features/trust/TrustScreen.tsx` + Hub 入口；消费 `trust_attestations`，无信用分条 |
| P0-2 | 信号传播接真数 | ✅ | `GET /v1/game/profile.spread_count`；Hub Web + 小程序去掉硬编码 `0` |
| P0-3 | Match 共识门控 | ✅ | `match_consensus` 表 + `POST …/acknowledge` + `GET …/consensus`；**不阻塞** v0 `mission-complete` |
| P0-4 | 通关下一动机 | ✅ | 四任务完成后 Hub「通关大奖→信任档案」；匹配确认后若全通关直达档案 |
| P0-5 | 内测 8 项 / HTTPS / 部署 | ⬜ | 仍属运维验收，本切片未做 |

自动化：`pytest tests/test_game.py -k "consensus or spread_count or trust_score"`  

_校准人：游戏设计师视角 + 源码检索 | 日期：2026-08-08_  
_实施：Agent · 2026-08-08_
