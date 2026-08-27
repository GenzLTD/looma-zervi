# 大陆 vs 海外 · 双线内测验收清单

> **版本：** 1.0 · **日期：** 2026-07-12  
> **分支：** `release/overseas`（海外）/ `main`（大陆主开发）  
> **用途：** 内测放行前逐项勾选；P0 不通则该线不算「可开内测」  
> **关联：** [OVERSEAS_DEPLOY.md](./OVERSEAS_DEPLOY.md) · [COMMERCE_CLOSURE_STATUS.md](./COMMERCE_CLOSURE_STATUS.md) · [SZBOLENT_COM_CN_CUTOVER_CHECKLIST.md](./SZBOLENT_COM_CN_CUTOVER_CHECKLIST.md)

**标记说明：** 将 `[ ]` 改为 `[x]` 表示通过；`[~]` 可手写为部分通过并注明原因。

---

## 0. 双线边界（验收前对齐）

| 维度 | 大陆线（CN） | 海外线（OVERSEAS） |
|------|-------------|-------------------|
| 主域 | `szbolent.cn` / `api.szbolent.com.cn`（规划）或当前内测 `api.genz.ltd` | `genz.ltd` + `api.genz.ltd` |
| 客户端 | 微信小程序、PlanetX Web（:5173）、T-space SaaS | genz-web、PlanetX Web（英文）、`tspace.genz.ltd` |
| 登录 | 微信 `code2session` | Google OAuth |
| 支付 | 微信 JSAPI / 小程序 · CNY | Stripe Checkout · USD |
| 主体 | 大陆企业（备案 / 微信商户） | YEDALL LIMITED（香港） |
| 部署 | `main` + 腾讯云双机 | `release/overseas` + Vultr / Cloudflare / Vercel |

**原则：** tier / JWT / 业务逻辑共用 Looma 真源；支付、登录、域名、法律主体 **分轨验收**。

---

## 1. P0 — 不通则不算「该线内测可开」

### 1.1 大陆线 P0

| ID | 验收项 | 验证方式 | 勾选 |
|----|--------|----------|------|
| CN-P0-1 | API 健康检查 | `curl -f https://api.genz.ltd/health`（备案前）或 `api.szbolent.com.cn/health` | [ ] |
| CN-P0-2 | 微信登录（小程序） | 真机授权 → JWT → `looma_token` 写入 | [ ] |
| CN-P0-3 | JWT 会话保持 | 杀进程重开，`authApi.refresh` / checkSession 仍有效 | [ ] |
| CN-P0-4 | 定价展示 CNY | `GET /v1/payment/plans?region=CN` → Supporter ¥9.9 · Pro ¥29.9 | [ ] |
| CN-P0-5 | 小程序支付页 | profile「升级会员」→ `pages/pricing` 可打开 | [ ] |
| CN-P0-6 | 微信下单 | `POST /v1/payment/wechat/order` → `wx.requestPayment`（Stub 或 0.01 元） | [ ] |
| CN-P0-7 | 支付后 tier 升级 | 付完 / Stub 后 JWT tier → `supporter` / `pro` | [ ] |
| CN-P0-8 | PlanetX 核心漏斗 | 登录 → Hub → Quiz → Result → Match 三分流（Web + 小程序） | [ ] |
| CN-P0-9 | identity 持久化 | `profile-sync` 仅传 identity 仍落库 | [ ] |
| CN-P0-10 | tier 门控 | free 受限；supporter 解锁候选人池等 | [ ] |
| CN-P0-11 | CORS | 小程序 / Web / 门户生产域在 `CORS_ORIGINS` | [ ] |
| CN-P0-12 | 无关键信息泄露 | 公开页 / API 无密钥、内网 IP、`.env` | [ ] |

**真源：** `payment.v1.json` · `backend/.env` · `frontend/packages/miniprogram/`

---

### 1.2 海外线 P0

| ID | 验收项 | 验证方式 | 勾选 |
|----|--------|----------|------|
| OS-P0-1 | 营销站可访问 | `https://genz.ltd/` → 英文首页 | [ ] |
| OS-P0-2 | 法律页齐全 | `/legal/privacy` `/terms` `/refund` `/pricing` 均可访问 | [ ] |
| OS-P0-3 | 法律主体一致 | 页脚 / Terms 显示 **YEDALL LIMITED** | [ ] |
| OS-P0-4 | 联系邮箱 | 全站 **zervi@genz.ltd** | [ ] |
| OS-P0-5 | API 健康 | `curl -f https://api.genz.ltd/health` → 200 | [ ] |
| OS-P0-6 | API 根路径不 500 | `curl -s https://api.genz.ltd/` → JSON 404，非 HTML 500 | [ ] |
| OS-P0-7 | USD 定价 API | `GET /v1/payment/plans?region=US` → $0 / $1.99 / $5.99 | [ ] |
| OS-P0-8 | CORS 跨域定价 | genz.ltd/pricing 浏览器控制台无 CORS 错误 | [ ] |
| OS-P0-9 | Google OAuth E2E | 登录 → callback → JWT | [ ] |
| OS-P0-10 | Stripe 商户材料 | Dashboard URL = `https://genz.ltd`，主体 = YEDALL LIMITED | [ ] |
| OS-P0-11 | 无敏感泄露 | 同 CN-P0-12；`config.js` 无内部注释 / 密钥 | [ ] |
| OS-P0-12 | 部署可追溯 | 线上 genz-web ≈ `release/overseas` 目标 commit | [ ] |

**真源：** `frontend/packages/genz-web/` · `docker/nginx.conf` · `docs/OVERSEAS_DEPLOY.md`

---

### 1.3 共用内核 P0（两线各验一遍）

| ID | 验收项 | 验证方式 | 勾选 |
|----|--------|----------|------|
| CORE-P0-1 | 支付契约 | `payment.v1.json` CN/US 价格与 `test_payment_plans.py` | [ ] |
| CORE-P0-2 | 后端测试集 | `pytest tests/test_payment_plans.py tests/test_payment_guard.py tests/test_game.py` | [ ] |
| CORE-P0-3 | shared-core 一致 | Web / 小程序 `matchConsensus`、payment API 同源 | [ ] |
| CORE-P0-4 | tier 真源唯一 | 客户端不写 tier；只消费 JWT + `/v1/payment/status` | [ ] |
| CORE-P0-5 | 分支同步 | `release/overseas` 定期 rebase `main`，避免漂移 | [ ] |

---

## 2. P1 — 内测可开，扩量 / 正式上线前补齐

### 2.1 大陆线 P1

| ID | 验收项 | 验证方式 | 勾选 |
|----|--------|----------|------|
| CN-P1-1 | 备案域名切换 | `www.szbolent.com.cn` + `api.szbolent.com.cn` DNS / HTTPS | [ ] |
| CN-P1-2 | 微信实单 0.01 元 | `PAYMENT_STUB_MODE=false` + 商户号 + notify 回调 | [ ] |
| CN-P1-3 | 小程序合法域名 | 微信公众平台配置 `api.szbolent.com.cn` | [ ] |
| CN-P1-4 | szbolent-portal 接 Looma | `looma.ts` + Pricing 拉 API | [ ] |
| CN-P1-5 | 合伙人闭环 | 发布机会 → 候选人池 → 匹配 E2E（`/v1/job-posts`） | [ ] |
| CN-P1-6 | 社交同心环（若本迭代） | Hub 静态环 / 图谱 API | [ ] |
| CN-P1-7 | 订阅到期降级 | cron 或手动验 `subscriptions` 表 | [ ] |
| CN-P1-8 | 闭环脚本 | `API_BASE=... ./scripts/verify-closed-loop.sh` 全绿 | [ ] |
| CN-P1-9 | 烟雾测试 | `./scripts/quick_smoke_test.sh` 8/8 | [ ] |
| CN-P1-10 | 全站 HTTPS | api / 门户无裸 HTTP 安全隐患 | [ ] |

---

### 2.2 海外线 P1

| ID | 验收项 | 验证方式 | 勾选 |
|----|--------|----------|------|
| OS-P1-1 | Stripe Checkout 实单 | checkout → 支付 → `/pricing?status=success` | [ ] |
| OS-P1-2 | Stripe Webhook | 测试事件 → tier 升级 + `orders` 表 | [ ] |
| OS-P1-3 | CTA 升级 | Checkout 上线后「Join waitlist」→ Subscribe | [ ] |
| OS-P1-4 | PlanetX Web 海外登录 | 海外部署 + Google 登录全流程 | [ ] |
| OS-P1-4b | PlanetX PWA M0 可安装 | `manifest.webmanifest` + icons + SW；Chrome「安装应用」/ iOS 添加到主屏幕 | [ ] |
| OS-P1-4c | PlanetX Web match 演示闭环 | 双账号舰队≥2 → Match → mission-complete → 成就（`?join=` 邀请） | [ ] |
| OS-P1-5 | `tspace.genz.ltd` | saas build + nginx + 英文 Pricing | [ ] |
| OS-P1-6 | Cloudflare Full Strict | Origin Certificate 替换自签 SSL | [ ] |
| OS-P1-7 | 隐藏 stub_mode | 生产 `plans` 响应不暴露内测标志 | [ ] |
| OS-P1-8 | region 默认 US | `Accept-Language` / `region=US` 解析正确 | [ ] |
| OS-P1-9 | 邮箱运营 | `zervi@genz.ltd` 可收信、有回复 SLA | [ ] |
| OS-P1-10 | Supporter 定价复盘 | $1.99 手续费占比；是否调至 $4.99+ | [ ] |

---

## 3. 建议验收顺序（2 周）

| 阶段 | 内容 |
|------|------|
| **Week 1 D1-2** | CORE-P0 全绿 + OS-P0-1 ~ OS-P0-8 |
| **Week 1 D3-4** | CN-P0-1 ~ CN-P0-6 |
| **Week 1 D5** | OS-P0-9 ~ OS-P0-10 + Stripe 提交 |
| **Week 2 D1-2** | CN-P0-7 ~ CN-P0-10 |
| **Week 2 D3-4** | OS-P1-1 ~ OS-P1-2（Stripe 审核通过后） |
| **Week 2 D5** | CN-P1-8 ~ CN-P1-9 + 双线缺陷复盘 |

---

## 4. 放行标准

| 线 | P0 要求 | 可宣告 |
|----|---------|--------|
| **大陆内测** | CN-P0 全 ✅（CN-P1-3 可部分） | 「大陆种子用户可内测（支付可 Stub）」 |
| **海外内测** | OS-P0 全 ✅ + Stripe 已提交 | 「海外 waitlist + 审核进行中」 |
| **双线商业化** | 各线 P0 + P1 支付实单 ✅ | 「CN 微信收款 + OS Stripe 收款」双闭环 |

---

## 5. 当前快照（2026-07-13）

| 线 | P0 粗估 | 主要缺口 |
|----|---------|----------|
| **海外** | ~78% | Google OAuth E2E（需 Client ID + 线上配置）；Stripe 审核；**PlanetX PWA M0 已落代码待线上验** |
| **大陆** | ~60% | 微信实单 / 合法域名；备案域；portal |

**本迭代已补（`release/overseas`）：**

- PlanetX `manifest` + icons + `sw.js` + 注册（PWA M0/M1 壳）
- Auth：`VITE_GOOGLE_CLIENT_ID` 时显示 Google GIS 按钮；`POST /v1/auth/google` 契约进 shared-core
- Match Web：舰队≥2 可开任务；`?join=` 自动入队；错误文案；信任 `can_complete_mission`
- `/v1/game/match/consensus|acknowledge` v0 占位（空列表 / noop），消前端 404

> 快照随迭代更新本节即可；勾选状态以各团队 Gitee PR / issue 为准。

---

## 6. 修订记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-07-12 | 1.0 | 首版：大陆 / 海外 / 共用内核 P0·P1 双线清单 |
