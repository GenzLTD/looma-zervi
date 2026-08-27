# zervi-genzer 三条战略线落地实施

> **版本：** 1.0 · **日期：** 2026-07-13  
> **状态：** 执行基线（与 Jason 叙事裁定对齐）  
> **实现主仓：** `looma-zervi`（API + PlanetX + 小程序 + 契约）  
> **决策/研讨仓：** `zervi-genzer`（match 阶段文档 + Genzer 终端路线）  
> **关联：** [MULTI_CLIENT_CX_STRATEGY.md](./MULTI_CLIENT_CX_STRATEGY.md) · [identity.v1.json](../backend/contracts/identity.v1.json) · [game.v1.json](../backend/contracts/game.v1.json) · [首次星际匹配_子项目接口契约.md](../首次星际匹配_子项目接口契约.md)

---

## 0. 项目定义

**zervi-genzer** 不是第四个代码仓库，而是 **三条长期战略线在 Looma 底座上的落地项目名称**：

| 名称 | 含义 |
|------|------|
| **Zervi** | Looma 前端品牌代号 + 海外 `genz.ltd` 产品面 |
| **Genzer** | 共识网络 + 软件/硬件终端（DemoPPI → 穿戴），与 PlanetX **域内闭环**分层 |
| **Genzer 终端机** | 阶段二：链下快路径（`consensus_match` 信号），**不嵌入** PlanetX 主 App |

```text
                    ┌─────────────────────────────────────┐
                    │  Line 1  契约化身份（Layer 0–1, 4）   │
                    │  user_id · linked_accounts · tier    │
                    └──────────────────┬──────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
  Line 2 共识裂变              Line 3 关系信任              Layer 5 成就
  match + share 增长           social 1–6 度 + 同心环        4 mission → 36 格
         │                             │
         └──────────────┬──────────────┘
                        ▼
              Genzer 终端（阶段二+，信号层，可选链上）
```

---

## 1. 叙事勘误（已裁定）

### 1.1 禁止再用的表述

| ❌ 旧表述 | 问题 |
|----------|------|
| 前 30 家企业永久免费 | 暗示 B 端 HR SaaS、企业主体信用 |
| T空间面向中小企业 HR | 与「只信个人」信念冲突 |
| 种子企业 30 家 | KPI 口径错误 |

### 1.2 标准替换（对外申报 / Stripe / 深创赛 / PPT 统一）

| 场景 | ✅ 标准表述 |
|------|------------|
| T空间定位 | **T空间 = 合伙人个人工作台**；`/v1/job-posts` 归属 `user_id`，不是企业招聘 SaaS |
| 早期激励 | **前 30 位种子合伙人：pro 档订阅永久免费**（个人账号，需完成合伙人档案认证） |
| 对比竞品 | 对比 Moka/北森时改为：**个人合伙人轻量发布 + PlanetX C 端流量池**，而非「替企业省 HR 系统年费」 |
| Q3–Q4 KPI | **种子合伙人 30 位**（非「种子企业 30 家」） |
| 代码/文档壳名 | `saas` 包、`enterprise` API 路径 = **历史实现壳**；对外与体验组统一称 **合伙人** |

### 1.3 待人工同步的文件（不在本仓）

`~/Desktop/declare/` 下深创赛文案、鸿蒙报名表、商业计划书 fusion 版 — 按上表批量替换后归档。

---

## 2. 个人信用栈（Layer 0–5）

| Layer | 契约文件 | 状态 | 负责组 |
|-------|----------|------|--------|
| 0 账号 | `identity.v1.json` → `linked_accounts` | ✅ 骨架 | G0 |
| 1 画像 | `identity.v1.json` → `planetx_identity` + personality | ✅ 骨架 + API 已跑 | G2/G3 |
| 2 关系 | `social.v1.json`（待建）← `/v1/social/*` | 后端 ✅ / 前端 ❌ | G2 + 合伙人 |
| 3 验证 | `game.v1.json` → match consensus | 部分（threshold 有，ack 未完整） | PlanetX 组 |
| 4 商业 | `payment.v1.json` | ✅ | G0 |
| 5 成就 | `achievements.v1.json`（待建）← 先映射 4 mission | 📋 | PlanetX 组 |

**原则：** 先契约化 **4 mission**（`game.v1.json`），再扩 **36 格成就** + 未来 **interview** 模块。

---

## 3. 战略线一：契约化身份

**目标：** 同一 `user_id` 跨小程序 / Web / PWA / 合伙人工作台可互认；JWT 仅为会话。

### 3.1 工作包

| ID | 工作包 | 交付物 | 优先级 | 验收 |
|----|--------|--------|--------|------|
| I-1 | identity 契约 v1 | `identity.v1.json` | P0 | ✅ 已起草 |
| I-2 | identity 说明文档 | `IDENTITY_CONTRACT.md` | P0 | 待写 |
| I-3 | shared-core 类型镜像 | `IdentityProfile` 等 | P0 | 待写 |
| I-4 | 聚合 API | `GET /v1/identity/profile` | P1 | 按 visibility 过滤 |
| I-5 | 可见性 API | `PATCH /v1/identity/visibility` | P1 | 对照 ORCID 三级 |
| I-6 | 公开页 | `GET /v1/identity/public/{handle}` | P2 | 空 record 不 404 |
| I-7 | ORCID 绑定 | `POST /v1/auth/orcid` | P2 | 海外线 optional |
| I-8 | 合伙人 role | `users.role=partner` + 档案 UI | P0 | G4 E2E |

### 3.2 里程碑

```text
M1（2w） identity.v1 + game.v1 + shared-core 导出 + G4 文案去企业化
M2（4w） GET /v1/identity/profile + 合伙人公开摘要
M3（8w） visibility + 公开页 + ORCID（可选）
```

---

## 4. 战略线二：共识裂变（PlanetX match）

**目标：** 匹配 = 验证 + 增长；未达标 → share 出口；verified 后才完成 match mission。

**规格真源：** `首次星际匹配_子项目接口契约.md` §5–8 · `zervi-genzer/TECH_DOC_*`

### 4.1 阶段划分（与 Genzer 终端分层）

| 阶段 | 范围 | 仓库 | 状态 |
|------|------|------|------|
| **1a v0** | 舰队内算分 + 双端匹配页 | looma-zervi | ✅ |
| **1b 共识门控** | consensus 表 + acknowledge + mission 403 | looma-zervi | ✅ 已校准（mission 403 降级 v0 不阻塞，见 M-4） |
| **1c 裂变 UI** | 三分流 + spread_hint + share CTA | looma-zervi | 📋 |
| **2 软件终端** | DemoPPI `consensus_match` 信号 | DemoPPI + genzer-contracts | 📋 不阻塞 1b |
| **3 穿戴硬件** | Ctrl4U 参照 | 硬件 | 📋 3–6 月 |

### 4.2 工作包（Line 2 · looma-zervi）

| ID | 工作包 | 交付物 | 优先级 |
|----|--------|--------|--------|
| M-1 | match 响应扩展 | `consensus_*` + `spread_hint` 字段 | P0 · 部分 ✅ |
| M-2 | `match_consensus` 表 | DB migration | P0 |
| M-3 | `POST /v1/game/match/acknowledge` | 真实现（非 501） | P0 |
| M-4 | mission-complete 门控 | ~~match 无 verified → 403~~ **已校准降级**：v0 不阻塞，阶段二增强。`game_routes.py:448` 硬编码 `can_complete_mission: True`，注释「舰队内算出配对 + 用户确认即可完成任务（阶段二共识为增强，不阻塞）」 | 已校准 |
| M-5 | Web MatchScreen 三分流 | verified / weak / failed | P0 |
| M-6 | 小程序 match 页同构 | 同上 | P0 |
| M-7 | share 任务联动 | 未达标主 CTA | P1 |
| M-8 | `GET /v1/game/match/consensus` UI | 待认可列表 | P1 |
| M-9 | game.v1.json | 四 mission 契约 | P0 · ✅ |

### 4.3 Genzer 终端（zervi-genzer 阶段二，独立排期）

| ID | 工作包 | 说明 |
|----|--------|------|
| G-1 | DemoPPI 本地 `consensus_match` 闭环 | 不共享 PlanetX DB |
| G-2 | genzer-contracts ActionType 扩展 | MatchIntent / PersonalityBeacon |
| G-3 | 信号 ingress/egress 适配器 | PlanetX 域外；**晚于 M-4 有真实载荷** |

**纪律：** 本周/本月优先 **M-2～M-6**；不提前做 G-3。

---

## 5. 战略线三：关系信任（社交图谱）

**目标：** 量化个人信任链（1–6 度）；支撑合伙人「人际信用」与 identity `visibility: trusted`。

**规格真源：** [SOCIAL_GRAPH_GUIDE.md](./SOCIAL_GRAPH_GUIDE.md) · [SOCIAL_RINGS_INTEGRATION_RUNBOOK.md](./SOCIAL_RINGS_INTEGRATION_RUNBOOK.md)

### 5.1 边规则勘误（对齐合伙人信念）

| 边来源 | v0（现网） | v1（目标） |
|--------|-----------|-----------|
| 推荐链 | `invite_codes` | ✅ 保留 |
| 舰队 | `fleet_members` | ✅ 保留 |
| 企业共属 | `enterprise_users` | ⚠️ **deprecated**；新 UI 不展示 |
| 合伙人互动 | — | 📋 `job_post_views` / import-share / match 互认 |

### 5.2 工作包

| ID | 工作包 | 交付物 | 优先级 |
|----|--------|--------|--------|
| S-1 | social.v1.json 骨架 | 契约 | P1 |
| S-2 | shared-core `createSocialApi` | 类型 + 客户端 | P0 |
| S-3 | PlanetX 六度同心环 UI | Hub 舰队 Tab | P0 |
| S-4 | 路径链动画 | connection 演示 | P1 |
| S-5 | 种子图谱脚本 | 7+ 用户联调 | P0 |
| S-6 | `verify-social-rings.sh` | 自动化 | P0 |
| S-7 | trust_score → 合伙人档案 | identity claim | P2 |

### 5.3 P0 Done（Runbook §1.2）

最小可演示：**S-2 + S-3 + S-5 + S-6**（深创赛应急集）。

---

## 6. Layer 5：成就体系（映射 4 mission）

**真源（declare）：** `成就体系设计文档.md` → 迁入 `docs/ACHIEVEMENTS_LAYER5.md`（下一步）

| 阶段 | 内容 |
|------|------|
| **L5-0** | `game.v1.json` 四 mission ↔ 成就 ID 映射表 | ✅ 见 game 契约 |
| **L5-1** | Hub 成就弹窗对齐 mission 完成事件 | P1 |
| **L5-2** | 影响类 7 格 ← share + spread_count | P1 |
| **L5-3** | interview 模块成就（量级/技能/突破） | P2 · 依赖 interview API |
| **L5-4** | `achievements.v1.json` 全 36 格 | P2 |

**不做：** 在 L5-0 完成前实现 36 格全量 UI。

---

## 7. 仓库与组队分工

| 仓库 | 职责 | 三条线中的位置 |
|------|------|----------------|
| **looma-zervi** | API、契约、PlanetX、小程序、genz-web | Line 1–3 主实现 |
| **zervi-genzer** | 决策文档、match 阶段说明、终端路线 | Line 2 规格 + Genzer 阶段 2–3 |
| **genzer-contracts** | 链上 ActionType / Badge | Line 2 阶段 2+ |
| **DemoPPI** | Genzer 软件终端 | Line 2 阶段 2 |
| **szbolent-portal** | 诗词门户（消费 Looma API） | 非 zervi-genzer 主路径 |

### 体验组认领（复用 MULTI_CLIENT_CX）

| 组 | 战略线 | 第一周 |
|----|--------|--------|
| **G0 平台** | Line 1 契约 + payment 拉通 | identity/game shared-core 导出 |
| **PlanetX 组** | Line 2 M-2～M-6 | consensus 表 + 双端三分流 |
| **PlanetX 组** | Line 3 S-2～S-3 | createSocialApi + 同心环 |
| **合伙人组 G4** | Line 1 I-8 + 叙事 | 种子合伙人 30 位计划 + 去企业文案 |
| **海外组** | G1/G3 + I-7 | Stripe + Google OAuth |

---

## 8. 里程碑总表（2026 Q3–Q4）

| 里程碑 | 时间 | 包含 | 对外可讲 |
|--------|------|------|----------|
| **ZG-M0** | 即期 | identity + game 契约；叙事勘误同步 declare | 个人信用栈地基 |
| **ZG-M1** | +2w | match 共识 P0 闭环；合伙人 pro 种子计划上线文案 | 共识验证非自动分配 |
| **ZG-M2** | +4w | 六度同心环可演示；`GET /v1/identity/profile` v0 | 信任可视化 |
| **ZG-M3** | +8w | 成就 L5-1；social.v1；match 裂变 P1 | 增长闭环数据 |
| **ZG-M4** | Q4 | DemoPPI 信号 POC；interview 成就预埋 | Genzer 终端叙事 |

### 内测 KPI（修正后）

| 指标 | 目标 |
|------|------|
| 注册用户 | 300+ |
| DAU | 50+ |
| **种子合伙人** | **30 位**（个人 pro 永久免费，非企业） |
| match verified 完成率 | 待 M-1 后基线 |

---

## 9. 验收与文档索引

| 文档 | 用途 |
|------|------|
| [DUAL_TRACK_ACCEPTANCE_CHECKLIST.md](./DUAL_TRACK_ACCEPTANCE_CHECKLIST.md) | CN / 海外 P0 |
| [PLANETX_MATCH_INTERNAL_TEST.md](./PLANETX_MATCH_INTERNAL_TEST.md) | match 内测 |
| [API_PARTNER_ALIGNMENT.md](./API_PARTNER_ALIGNMENT.md) | 合伙人 API |
| `zervi-genzer/TECH_DOC_PLANETX_MATCH_PHASE1_2026-07-12.md` | match 阶段一 |
| `zervi-genzer/TEAM_DISCUSSION_GENZER_TERMINAL_2026-07-12.md` | Genzer 终端研讨 |

---

## 10. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-07-13 | 初版：三战略线 + 叙事勘误 + zervi-genzer 落地分工 + Layer 5 映射 |
| 1.1 | 2026-08-08 | 校准 M-4：mission-complete 门控降级为 v0 不阻塞（game_routes.py:448），阶段二增强 |
