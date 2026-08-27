# 多端客户体验战略：Web + PWA 与分组落地指南

> **版本：** 1.1 · **日期：** 2026-07-12  
> **分支：** 大陆主开发 `main` · 海外 `release/overseas`  
> **用途：** 组队逐项落地；从**客户体验（CX）**而非技术栈拆组  
> **关联：** [DUAL_TRACK_ACCEPTANCE_CHECKLIST.md](./DUAL_TRACK_ACCEPTANCE_CHECKLIST.md) · [OVERSEAS_DEPLOY.md](./OVERSEAS_DEPLOY.md) · [API_PARTNER_ALIGNMENT.md](./API_PARTNER_ALIGNMENT.md) · [HARMONY_FRONTEND_ALIGNMENT.md](./HARMONY_FRONTEND_ALIGNMENT.md) · [ZERVI_GENZER_IMPLEMENTATION.md](./ZERVI_GENZER_IMPLEMENTATION.md)

---

## 0. 产品信念（分组前提）

**我们不相信「企业」作为信用主体，只相信「个人」及其可验证的信用。**

因此产品中**不存在**传统 B 端叙事（HR 替公司招人、企业招聘 SaaS）。  
与之对应的是 **合伙人（Partner）**：以个人身份发布机会、积累候选人池、用 tier 与行为建立信用。

| 不存在 | 存在 |
|--------|------|
| 企业 HR 招聘工作台 | **合伙人**个人工作台 |
| 公司主体招聘信用 | **个人信用** + 行为记录 + tier |
| `/v1/enterprise/jobs` 式企业职位域 | `/v1/job-posts`（归属 `user_id` 的合伙人发布） |

代码里 `saas` 包、`tspace` 域、`enterprise` API 命名是**历史实现壳**；体验分组与对外叙事统一用 **合伙人**，见 [API_PARTNER_ALIGNMENT.md](./API_PARTNER_ALIGNMENT.md)。

## 1. PWA 是什么

**PWA** = **Progressive Web App**（渐进式 Web 应用）。

用 Web 技术提供接近原生 App 的体验，典型能力包括：

| 能力 | 说明 |
|------|------|
| 可安装 | 添加到主屏幕 / 桌面，独立图标启动 |
| 离线壳 | Service Worker 缓存静态资源与部分页面 |
| 推送 | Web Push（iOS / 各浏览器支持度不一） |
| 安全 | 必须 HTTPS（genz.ltd / api 已满足） |

**组成：** `manifest.json` + Service Worker + HTTPS + 现有 SPA（PlanetX Web）。

---

## 2. 核心判断：Web+PWA 能否「根本解决」多端难题？

**不能根本解决，但能战略性地「收口」其中一条主航道。**

```text
正道架构（已在践行）
  Looma API 真源
       +
  shared-core 契约（类型 / API / match / payment）
       +
  各端薄壳（Web · 小程序 · Harmony · SaaS · 营销静态站）

Web + PWA 的正确定位
  = PlanetX Web 的「交付形态升级」
  ≠ 替代微信小程序、鸿蒙、合伙人工作台独立壳
```

| 能显著缓解 | 不能替代 |
|------------|----------|
| 浏览器 + 可安装 Web 一套代码 | 微信小程序（支付 / 登录 / 分享 / `wx.*`） |
| 海外桌面 / Android Chrome 主客户端 | HarmonyOS 元服务 / 系统能力 |
| 内测链接一键分发 | iOS 生态习惯与 PWA 能力上限 |
| 与 shared-core 共用业务逻辑 | WXML vs React 的 UI 层双实现 |

**结论：** 多端适配的真正解法 = **契约统一 + 按体验分组薄壳**；PWA 是 **海外 / 桌面 C 端** 组的利器，不是全局银弹。

---

## 3. 客户体验分组（推荐 5 组）

按「谁在用、要完成什么任务、走哪条商业线」划分，便于组队与验收对齐 [双线清单](./DUAL_TRACK_ACCEPTANCE_CHECKLIST.md)。

```text
  G1 获客与信任          → 还没注册，要建立信任
  G2 大陆职业成长（C）   → 微信生态内求职 / 闯关
  G3 海外职业成长（C）   → genz.ltd / USD / Google / Stripe
  G4 合伙人（个人信用）   → 个人发机会、建候选人池、看匹配
  G5 鸿蒙轻量求职        → 元服务 / 答题 / 岗位浏览

  横切：G0 平台与契约    → 所有组共用，不直接面向终端客户
```

### 分组总览

| 组 | 客户体验一句话 | 主载体 | PWA 角色 | 建议 Owner |
|----|----------------|--------|----------|------------|
| **G0 平台与契约** | 账号与付费在任意端一致、可预期 | Looma API + shared-core | 不直接面向用户 | 后端 + shared-core |
| **G1 获客与信任** | 看懂产品、价格、法律主体，敢付费 | genz-web（Vercel） | 可选轻量 PWA（低优先） | 海外运营 / 前端 |
| **G2 大陆 C 端成长** | 登录 → 闯关 → 匹配 → 微信升级 | **微信小程序**（主）+ PlanetX Web（辅） | Web 辅线可加 PWA，**不替代小程序** | 小程序 + PlanetX |
| **G3 海外 C 端成长** | 英文成长伙伴 → Google 登录 → Stripe | **PlanetX Web + PWA**（主） | **主战场，优先落地 PWA** | PlanetX + 海外部署 |
| **G4 合伙人成长** | 以个人信用发机会、撮合匹配 | T-space 工作台（`saas` 壳） | 桌面 Web 为主，PWA 可选 | 合伙人前端 + API |
| **G5 鸿蒙轻量体验** | 快问快答、浏览岗位、轻量答题 | Harmony 独立仓（ArkTS） | 不适用 | Harmony 前端 |

---

## 4. 各组客户旅程与落地 backlog

### G0 · 平台与契约（横切赋能）

**客户感知：** 换端登录后 tier、进度、匹配结果不丢、不乱。

| 阶段 | 客户期望 | 落地项 | 优先级 |
|------|----------|--------|--------|
| 身份 | 同一用户在多端是「同一个人」 | JWT + `profile-sync` + identity 持久化 | P0 |
| 付费 | CN ¥ / US $ 展示与实收一致 | `payment.v1.json` 真源 + region 分叉 | P0 |
| 匹配 | Web / 小程序 match 三分流一致 | `matchConsensus.ts` 共用 | P0 |
| 合规 | 同意书、配额提示一致 | shared-core consent / quota | P1 |

**验收：** [DUAL_TRACK_ACCEPTANCE_CHECKLIST](./DUAL_TRACK_ACCEPTANCE_CHECKLIST.md) § CORE-P0。

---

### G1 · 获客与信任体验

**画像：** 首次访问 genz.ltd 的海外访客、Stripe 审核员、waitlist 用户。

**旅程：** 落地页 → 定价 → 法律页 → 邮件联系 / waitlist →（未来）注册。

| 阶段 | 体验目标 | 落地项 | 优先级 | 状态 |
|------|----------|--------|--------|------|
| 认知 | 3 秒懂「AI Career Growth Partner」 | genz-web 首页文案 | P0 | ✅ |
| 信任 | 主体 / 邮箱 / 法律齐全 | YEDALL + zervi@ + 五页 | P0 | ✅ |
| 定价 | USD 与 API 一致 | `/pricing` 拉 `region=US` | P0 | ✅ |
| 转化 | 不误导「已可订阅」 | Join waitlist（Stripe 未通前） | P0 | ✅ |
| 审核 | Stripe / Google 材料与站一致 | `STRIPE_HK_COMPANY_GUIDE.md` | P0 | 🟡 |
| 进阶 | 一键安装（可选） | genz-web PWA | P2 | ⬜ |

**说明：** 本组以**静态营销站**为主，不必强行 PWA；PlanetX 产品 PWA 在 G3 落地。

---

### G2 · 大陆 C 端职业成长体验

**画像：** 大陆求职者，主要在微信里完成闯关与匹配。

**旅程：** 微信授权 → Hub → Quiz → Result → Match →（升级）小程序支付。

| 阶段 | 体验目标 | 落地项 | 优先级 | 主载体 |
|------|----------|--------|--------|--------|
| 进入 | 分享卡片点得开、登录顺 | 小程序登录 + `looma_token` | P0 | 小程序 |
| 核心玩法 | 闯关 / 匹配 / 同心环 | Match 三分流 + Hub | P0 | 小程序 + Web |
| 付费 | ¥9.9 / ¥29.9 可理解可支付 | `pages/pricing` + 微信下单 | P0 | 小程序 |
| 留存 | 次日还能接着玩 | session / tier / 进度同步 | P1 | 小程序 |
| 扩入口 | 非微信环境分享链接 | PlanetX Web（可选 PWA） | P2 | Web |

**PWA 在本组：** **辅助渠道**（浏览器分享、内测链接），**不替代**微信小程序主路径。

**验收：** 双线清单 § CN-P0。

---

### G3 · 海外 C 端职业成长体验（Web + PWA 主战场）

**画像：** 海外专业人士，英文界面，Google 登录，USD 订阅。

**旅程：** genz.ltd 营销站 → PlanetX App（Web/PWA）→ Google 登录 → 核心玩法 → Stripe 订阅。

| 阶段 | 体验目标 | 落地项 | 优先级 | 主载体 |
|------|----------|--------|--------|--------|
| 引流 | 从 genz.ltd 无缝进入产品 | 统一品牌 GenZ · PlanetX | P0 | genz-web → Web |
| 安装 | 可「添加到主屏幕」 | **PlanetX PWA manifest + SW** | **P1** | Web+PWA |
| 登录 | Google 一键登录 | `/v1/auth/google` E2E | P0 | Web |
| 核心玩法 | 与大陆同契约的 match / ask | shared-core + PlanetX 功能对齐 | P0 | Web |
| 付费 | $1.99 / $5.99 Stripe 实收 | Checkout + Webhook | P1 | Web |
| 离线 | 弱网可打开壳与缓存页 | SW 缓存策略 | P2 | PWA |

**PWA 最小落地包（建议迭代顺序）：**

1. `frontend/packages/planetx/public/manifest.webmanifest`（名称、图标、theme）
2. Vite PWA 插件或轻量 Service Worker（仅缓存静态资源）
3. `genz.ltd` 与 PlanetX 同域或子路径策略（避免双域登录割裂）
4. 验收：Chrome Lighthouse PWA ≥ 可安装；iOS Safari「添加到主屏幕」冒烟

**验收：** 双线清单 § OS-P0 / OS-P1。

---

### G4 · 合伙人成长体验（个人信用，非企业招聘）

**画像：** 有行业资源与判断力的**个人合伙人**（猎头、资深从业者、社群 KOL 等），以**个人信用**而非公司名义撮合机会。

**信念：** 不信任企业主体；信任可累积的个人行为、tier 与匹配质量。

**旅程：** 注册 → 建立合伙人档案 → 发布机会（`job-posts`）→ 导入/积累候选人 → 查看匹配 → 按 tier 扩展配额。

| 阶段 | 体验目标 | 落地项 | 优先级 | 主载体 |
|------|----------|--------|--------|--------|
| 身份 | 我是「合伙人」而非某公司员工 | 个人档案 + tier 徽章；文案去 HR/企业化 | P0 | T-space 工作台 |
| 发布 | 以个人名义发布机会 | `POST /v1/job-posts`（归属 `user_id`） | P0 | API + [合伙人对照表](./API_PARTNER_ALIGNMENT.md) |
| 撮合 | 看匹配质量，而非「筛简历」 | `GET /v1/job-posts/:id/matches` | P0 | 合伙人 Dashboard |
| 信用 | 配额与 tier 挂钩，激励负责任发布 | `tier_limits` + supporter/pro 档位 | P0 | G0 契约 |
| 种子计划 | **前 30 位种子合伙人：pro 档永久免费**（个人账号，非企业主体） | 运营规则 + tier 人工/Stub 开通 | P1 | G4 文案 |
| 池化 | 从分享码导入候选人（人际信用链） | `import-share` / 候选人池 API | P1 | 合伙人 API |
| 海外 | 英文合伙人工作台（可选） | `tspace.genz.ltd` | P1 | saas 包 |

**与 C 端工具区分（必读）：**

| 路径 | 谁用 | 做什么 |
|------|------|--------|
| `/v1/job-posts` | **合伙人** | 持久化发布机会 + 看匹配 |
| `/v1/jobs/*` | **求职者（C 端）** | 上传 JD → AI 解析 → 自助匹配 |

**PWA 在本组：** 优先级低；合伙人多为桌面深度操作，**响应式 Web 工作台**优先。

**验收：** [API_PARTNER_ALIGNMENT.md](./API_PARTNER_ALIGNMENT.md) §8 勾验；双线清单 § CN-P1-5（合伙人闭环）。

---

### G5 · 鸿蒙轻量求职体验

**画像：** 鸿蒙用户，快问快答、轻量岗位浏览，非 PlanetX 全量闯关。

**旅程：** 元服务启动 → 答题 / 浏览岗位 →（未来）与 Looma 账号打通。

| 阶段 | 体验目标 | 落地项 | 优先级 | 主载体 |
|------|----------|--------|--------|--------|
| 可用 | 核心 API 对齐 | Harmony 网络 / 存储适配器 | P0 | Harmony 仓 |
| 场景 | 与 PlanetX 差异化定位清晰 | 求职 / 答题域，非全量 PlanetX | P1 | 产品 |
| 统一 | 与 Looma tier 长期打通 | 账号联邦（后期） | P2 | G0 + Harmony |

**PWA 在本组：** **不适用**；保持 ArkTS 独立实现 + API 契约对齐。

**验收：** [HARMONY_FRONTEND_ALIGNMENT.md](./HARMONY_FRONTEND_ALIGNMENT.md)。

---

## 5. 组队建议（按体验组认领）

| 小组 | 认领范围 | 第一周建议产出 |
|------|----------|----------------|
| **平台组** | G0 | CORE-P0 全绿；CORS / region 文档更新 |
| **海外增长组** | G1 + G3 营销与转化 | Stripe 审核通过；Google OAuth E2E |
| **PlanetX 组** | G2 + G3 产品 | 小程序支付闭环；PlanetX PWA manifest v0 |
| **合伙人组** | G4 | 合伙人 Dashboard E2E；`/v1/job-posts` 联调；去企业化文案 |
| **Harmony 组** | G5 | 对齐文档内 P0 端点联调 |

**协作规则：**

1. UI 可分叉，**契约不可分叉**（改 API 必须同步 shared-core + 双线清单）。
2. 缺陷 ticket 标签：`[G1]` … `[G5]` + `[CN]` / `[OVERSEAS]`。
3. 每周五对照 [DUAL_TRACK_ACCEPTANCE_CHECKLIST](./DUAL_TRACK_ACCEPTANCE_CHECKLIST.md) 更新勾选。

---

## 6. Web + PWA 落地路线图（仅 G3 主投）

| 迭代 | 目标 | 交付物 | 预计 |
|------|------|--------|------|
| **M0** | 可安装 | manifest + 图标 + HTTPS 同域 | 3d | ✅ 代码已落 `planetx/public/`（待线上 HTTPS 验） |
| **M1** | 离线壳 | SW 缓存静态资源；启动 < 3s（弱网） | 3d | ✅ `sw.js` 静态壳缓存（API 不缓存） |
| **M2** | 登录闭环 | Google OAuth 在 PWA standalone 模式可用 | 5d | 🟡 前端 GIS + `/v1/auth/google` 已接；待 Client ID / E2E |
| **M3** | 支付闭环 | Stripe Checkout 回跳 PWA | 5d | ⬜ |
| **M4** | 推送（可选） | Web Push 海外通知 | P2 | ⬜ |

**不纳入首期 PWA：** G2 小程序、G4 合伙人工作台、G5 Harmony、G1 静态营销站。

---

## 7. 体验组 vs 技术栈对照（防混淆）

| 客户体验组 | 代码包 | 域名示例 |
|------------|--------|----------|
| G1 | `frontend/packages/genz-web` | genz.ltd（Vercel） |
| G2 小程序 | `frontend/packages/miniprogram` | 微信 |
| G2/G3 Web | `frontend/packages/planetx` | genz.ltd / :5173 |
| G4 合伙人 | `frontend/packages/saas`（T-space 工作台壳） | tspace.genz.ltd / :5174 |
| G0 | `shared-core` + `backend/` | api.genz.ltd |
| G5 | 独立 Harmony 仓 | 元服务 |

---

## 8. 决策备忘

| 问题 | 结论 |
|------|------|
| PWA 全称？ | Progressive Web App |
| 能否根本解决多端？ | **否**；契约统一 + 体验分组才是根本 |
| PWA 优先投哪？ | **G3 海外 C 端** |
| 大陆主战场？ | **G2 微信小程序**，Web+PWA 辅助 |
| 合伙人 vs 企业？ | **只有合伙人（个人信用）**；无企业 HR B 端叙事 |
| 与海外分支关系？ | `release/overseas` 先行 G1/G3；合并能力回 `main` 供 G2 |

---

## 9. 修订记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-07-12 | 1.1 | G4 由「企业招聘 B 端」改为「合伙人 / 个人信用」；新增 §0 产品信念 |
| 2026-07-13 | 1.2 | G4 种子计划：前 30 **位合伙人** pro 永久免费（废止「前 30 家企业」表述）；链 ZERVI_GENZER 实施总纲 |
| 2026-07-12 | 1.0 | 首版：PWA 定义、五组 CX 划分、各组 backlog 与 PWA 路线图 |
