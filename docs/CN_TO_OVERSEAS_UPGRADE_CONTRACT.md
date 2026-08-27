# 国内 → 海外升级契约（一页）

> **状态：** Draft v0.1 · 2026-08-06  
> **目标：** 国内 PlanetX（腾讯生态 / 游戏化裂变）获客；**付费升级后统一进入海外 SaaS**。  
> **国内职责：** 传播与轻体验。**海外职责：** 订阅收银、Ask/RAG、长期工作台。  
> **关联：** [PAYMENT_TIER_CONTRACT.md](./PAYMENT_TIER_CONTRACT.md) · [TIMELINE_EVENT_MODEL.md](./TIMELINE_EVENT_MODEL.md) · analytics `VALID_EVENTS`

---

## 1. 账号契约

| 项 | 约定 |
|----|------|
| 国内身份 | 微信 openid / 小程序 JWT（`DEPLOY_REGION=CN` 主机） |
| 海外身份 | 邮箱或 Google OAuth JWT（`api.genz.ltd`，`DEPLOY_REGION=SG`） |
| 关联键 | `cn_user_id`（国内 UUID）↔ `overseas_user_id`（海外 UUID），经一次性 **upgrade_token** 绑定 |
| 升级令牌 | 国内签发 `upgrade_token`（JWT/JWE，TTL **15 min**，单次消费，aud=`overseas-saas`） |
| 绑定策略 | 首次兑换：创建或绑定海外账号；同邮箱已存在则要求登录后合并 |
| 国内付费 | **不做主收银**；升级意向在国内产生，**收款与 tier 真源仅在海外** |
| 国内 JWT | 升级成功后可保留只读/裂变权限；**Ask 配额、付费能力以海外 JWT tier 为准** |
| 禁止 | 直接复用国内 JWT 调海外 API；跨区硬编码共享 `JWT_SECRET` 明文长期互通 |

**兑换 API（待实现，契约名）：**

```http
POST https://api.genz.ltd/v1/auth/upgrade/exchange
Body: { "upgrade_token": "<from CN>", "email?": "...", "google_id_token?": "..." }
→ { "access_token", "user_id", "tier", "linked_cn_user_id", "imported": {...} }
```

国内签发侧（契约名）：`POST /v1/auth/upgrade/issue`（需国内登录 + 用户确认升级）。

---

## 2. 跳转 URL

| 步骤 | URL | 说明 |
|------|-----|------|
| 国内升级 CTA | 小程序/PlanetX 内按钮 → 调 `upgrade/issue` | 不直接裸链到定价页丢上下文 |
| 落地（首选） | `https://tspace.genz.ltd/upgrade?token={upgrade_token}` | SaaS 兑换页：登录/注册 → exchange |
| 已登录快捷 | `https://tspace.genz.ltd/upgrade/consume?token=...` | 已有海外会话时静默兑换 |
| 成功后默认 | `https://tspace.genz.ltd/dashboard` | 或 `/?upgraded=1` |
| 定价（未绑定） | `https://tspace.genz.ltd/pricing?src=cn_upgrade` | token 失效时的降级入口 |
| 营销站 | `https://genz.ltd` | **不**承担升级兑换；CTA 可指向 `/upgrade` |
| 旧站 | `https://app.genz.ltd` | **不**作为升级落点 |

Query 约定：`token`（必填）、`src=planetx_cn|miniprogram|harmony`、`campaign`（可选裂变码）。

---

## 3. 带走的数据字段

升级兑换成功后，海外侧 **幂等导入**（可重放）。分档：

### L0 — 必须带走（账号桥）

| 字段 | 说明 |
|------|------|
| `cn_user_id` | 国内用户 UUID |
| `display_name` | 昵称（无 PII 手机号） |
| `avatar_url` | 若有且可公网访问 |
| `locale` | `zh-CN` |
| `referral_code` / `inviter_share_code` | 裂变归因 |
| `upgrade_source` | `planetx` / `miniprogram` / `harmony` |
| `issued_at` | 令牌签发时间 |

### L1 — 默认带走（产品连续性，非简历全文）

| 字段 | 说明 |
|------|------|
| `mbti_type` / `persona_summary` | 人格测评结果摘要 |
| `active_domain` | 六域当前域 |
| `onboarding_stage` | PlanetX 叙事进度枚举 |
| `fleet_id` / `fleet_role` | 舰队关系（若有） |
| `achievement_ids[]` | 成就 ID 列表（非素材包） |
| `quiz_summary` | 最近一次测评摘要（type + score + completed_at） |

### L2 — 二次授权后带走（compliance scope）

| 字段 | scope 建议 | 说明 |
|------|------------|------|
| Timeline L1 事件摘要 | `timeline_export_l1` | 见 Timeline 模型；不含对话全文 |
| 简历结构化标签 | `jobseeker_core` | skills/tags，**不含**简历原文 |
| 匹配报告摘要 | `report_share` | report_id + score，不含对方 PII |

### 明确不带走

密码/微信 session、国内支付凭证、Ask 全文对话、征信原始报文、未授权简历 PDF/原文、他方用户资料。

导入后海外可调：`POST /v1/timeline/bridge/backfill`（对本用户幂等），把 L1 可映射事件灌入 Timeline。

---

## 4. 埋点事件

沿用 `POST /v1/analytics/events`；**新增**下列事件名（需写入 `VALID_EVENTS` + shared-core）。  
`properties` 禁 PII（邮箱/手机/token 全文）；token 只报 `token_prefix`（前 8 位）。

| 事件 | 侧 | 何时 | 关键 properties |
|------|----|------|-------------------|
| `cn_upgrade_cta_shown` | 国内 | 展示升级入口 | `surface`, `tier_hint` |
| `cn_upgrade_cta_clicked` | 国内 | 点击升级 | `surface`, `campaign` |
| `cn_upgrade_token_issued` | 国内 | `upgrade/issue` 成功 | `cn_user_id`, `ttl_sec`, `token_prefix` |
| `cn_upgrade_token_issue_failed` | 国内 | 签发失败 | `reason` |
| `overseas_upgrade_landed` | 海外 | 打开 `/upgrade` | `src`, `token_prefix`, `has_session` |
| `overseas_upgrade_exchange_ok` | 海外 | exchange 成功 | `linked_cn_user_id`, `imported_keys[]`, `is_new_user` |
| `overseas_upgrade_exchange_failed` | 海外 | 兑换失败 | `reason`=`expired\|used\|invalid\|merge_required` |
| `overseas_upgrade_pricing_view` | 海外 | 进入定价（升级漏斗） | `src=cn_upgrade` |
| `overseas_upgrade_checkout_started` | 海外 | 开始 Stripe checkout | `plan`, `region=US` |
| `overseas_upgrade_tier_activated` | 海外 | tier≥supporter | `tier`, `from_cn=true` |

**漏斗（北星）：**

```text
cn_upgrade_cta_clicked
  → cn_upgrade_token_issued
  → overseas_upgrade_landed
  → overseas_upgrade_exchange_ok
  → overseas_upgrade_checkout_started
  → overseas_upgrade_tier_activated
```

复用已有：`trial_clicked` / `trial_started`（海外试用）、`share_code_created`（国内裂变，properties 带 `upgrade_eligible`）。

---

## 5. 验收清单（最小）

- [ ] 国内签发 token → 15 min 内海外兑换成功，得到海外 JWT  
- [ ] 同 token 第二次兑换 → `409/410 used`  
- [ ] L0+L1 字段出现在海外 profile / dashboard  
- [ ] 漏斗 6 步事件均可在两边 analytics（或统一汇聚表）查到  
- [ ] 未付费用户不可因跳转自动获得 overseas paid tier  

---

## 6. 非目标（本页不做）

- 国内微信支付主收银  
- 实时双向同步游戏状态  
- `app.genz.ltd` 作为升级落点  
- Supabase `/v1/auth/bridge`（仍为 501；本契约用 **upgrade exchange**，不复用该路由语义）
