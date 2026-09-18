# 多仓发布联邦：一源一管线（genz.ltd / www.genz.ltd / api·tspace）

> **版本：** 1.0 · **日期：** 2026-09-18
> **受众：** 产品 / 工程 / 运维
> **关联：** [PIPELINE_MAIN_OVERSEAS_CI.md](./PIPELINE_MAIN_OVERSEAS_CI.md) · [OVERSEAS_DEPLOY.md](./OVERSEAS_DEPLOY.md) · [DUAL_TRACK_ACCEPTANCE_CHECKLIST.md](./DUAL_TRACK_ACCEPTANCE_CHECKLIST.md)
> **装置：** `scripts/cutover-test/`（摘块安全门禁）

---

## 0. 一句话口径

**三个站 = 三套自动化。每个站只有一个真源、一条发布管线；真源之间不互相投递。**

不把裸域（genz.ltd）与 Vultr-Genzltd 合成一条流水线，也不让任何一个仓「既打到 Vercel 又打到新加坡机」。
可行形态是 **联邦式归集**（一源一管线、拆错链），不是大包大揽。

---

## 1. 三站三线（钉死）

| 站 | 真源 | 自动发 | 不该碰 |
|----|------|--------|--------|
| `genz.ltd` | **GenzLTD/genz-web**（公开仓） | **Vercel**（push `main` 即发，已通） | Vultr、looma 内的副本 |
| `www.genz.ltd` | **Genzer-Terminal** | **Vercel** | 裸域仓 |
| `api.genz.ltd` / `tspace.genz.ltd` | **looma-zervi** 产品 + 日后 Vultr-Genzltd 投递 | **GH Actions**（Deploy / Deploy Overseas） | genz-web |

### 边界说明

- `genz.ltd` 与 `www.genz.ltd` 是**两个独立站**，不是别名关系：apex 是 Vite 营销站（`GenzLTD/genz-web`），`www` 是 Next.js 终端站（`Genzer-Terminal`）。
- `api` / `tspace` 是 **looma-zervi 产品面**，由 GH Actions 发布；Vultr-Genzltd 只负责把它们跑起来（见 §2）。
- 三站各自的"发"互不触发：推 genz-web 不会更新 api，合 looma-zervi main 不会更新 genz.ltd。

---

## 2. Vultr-Genzltd 的职责边界：只该管钱和脑

**管：**

| 项 | 落点 |
|----|------|
| backend | `docker/` compose，容器 :5200 → 宿主 127.0.0.1:5200 |
| compose 编排 | `docker/docker-compose.yml` |
| nginx 反代 | `api.genz.ltd`、`tspace.genz.ltd` 两个 Host 的 `/v1/*`、`/health` |
| 支付 | Stripe / PayPal / Airwallex webhook（`/v1/payment/webhook/*`，**无 rate limit**） |

**不管：**

| 项 | 现在归谁 |
|----|----------|
| `genz.ltd` / `www.genz.ltd` 静态站 | Vercel（各自的独立仓） |
| 营销站构建产物 | 各仓自己的管线 |
| 裸域证书 | Vercel 终结；本机保留的 `ssl_certificate` 仅供 api / tspace |

**已摘除的 serve 端（2026-09-18）：**

- `docker/nginx.conf` — `genz.ltd` / `www.genz.ltd` 的 HTTP :80 与 HTTPS :443 server 块 → 替换为「已迁出」注释
  → **这份就是 Vultr 真机在跑的文件**（2026-09-18 实测：真机 `/etc/nginx/nginx.conf` md5 `0f505e33f8fb047f4185689b89e4c256`
  逐字节等于 `a52638e:docker/nginx.conf`），故真机落地就是 scp 这份、`nginx -t`、`reload`。
- `nginx-vultr.conf` — 同上摘块，但**它并不等于真机文件**：真机版比对下来只有 api `/health`（`location = /health` + `Host` 头）
  与 api `/`（真机走 Flask 端点列表，此件走 404 JSON）两处历史差异，行数 300 vs 237。
  即仓内存在一份**失同步兄弟副本**，摘块已同步、其余差异未对账 → 属独立待办（要么与真机对齐，要么标注为参考件），
  **不要**拿它当真机落地件 scp。
- `scripts/deploy-overseas.sh` — 原第 7 步（`pnpm build:genz-web` + rsync → `/var/www/genz-web`）→ 替换为「已迁出」注释
- `scripts/deploy-genz-web.sh` → `scripts/deploy-genz-web.sh.disabled`（归档，默认拒绝执行）
- `.github/workflows/deploy-overseas.yml` — Bootstrap 的 `mkdir -p ... /var/www/genz-web` 已删；`Public health check` 里对 `https://genz.ltd/` 的断言已删（本管线不得断言别人管线的可用性，否则 Vercel 抖动会拖红 looma 发布）；旧仓名 `szpeter2026/genz-web` → `GenzLTD/genz-web`
- `frontend/package.json` — `build:genz-web` 已移出 `build:all` 串联（脚本本身保留供本地比对，产物**不得**投递）
- `frontend/packages/genz-web/README.md` — 头部加 ARCHIVED 只读声明

**摘块前的越界影响核查（证明不会断营销站）：** 被摘掉的 apex server 块里除静态 serve 外还挂着 `/v1/*` 与 `/health` 反代，
所以必须确认营销站不靠**裸域同源**调 API。实测 `frontend/packages/genz-web/src/`：

```text
src/config/site.ts:9   apiBase: import.meta.env.VITE_API_BASE || "https://api.genz.ltd"
src/pages/PricingPage.tsx   fetch(`${apiBase}/v1/payment/providers|plans|checkout`)
```

营销站**全部**经 `apiBase` 出站，仓内无 `https://genz.ltd/v1/...` 之类同源调用 →
摘掉 apex `/v1` 反代不会影响定价页与结账。今后若要改 `apiBase`，必须先回到本条复核。

`nginx-looma-zervi-overseas.conf` 本就已是干净版（头部：「Frontend is on Vercel (genz.ltd) — this config is API-only by default」），未改动，可作正确口径样板。

**关于 Live E2E 的 «genz-web landing» 阶段（实测口径，勿想当然）：**

`frontend/e2e/overseas-closed-loop.live.spec.ts` 里有一段访问营销站的断言。它**确实在 CI 里跑**——
`ci.yml` 的 `frontend-e2e-live` job → `pnpm e2e:live` → `playwright.overseas.live.config.ts`。
但**不构成对 Vercel 的依赖**，因为：

- CI 未设 `E2E_OVERSEAS_WEB/SAAS/API`，故 `IS_PRODUCTION=false` → 走 **local 模式**，
  由 webServer 起 `pnpm dev:genz-web`（`:5180`），测的是**仓内归档副本**，**从不碰 genz.ltd**；
- 只有在本地显式 `E2E_ALLOW_REMOTE_API=1` + `E2E_OVERSEAS_WEB=https://genz.ltd` 时才会打线上，
  那是人工验收，不是门禁。

所以：**Vercel 抖动不会拖红 looma CI**（这点是对的），但这段断言现在测的是**已归档的过期副本**——
按 §6 的反模式口径，它是「本地替身」而非「线上真源」的代表。因此：

- 不得把 `https://genz.ltd` 写进任何 workflow 的默认路径或断言；
- 该阶段的绿灯**不能**当成「线上营销站正常」的证据（线上真源看 GenzLTD/genz-web 的 Vercel 部署记录）；
- 若日后要真正校验线上营销站，应放在 genz-web 仓自己的管线里，不放在 looma。

---

## 3. 拆掉的两条错链

同一类错误，一次发生在 Git 层，一次发生在机器层。

### 错链 A（Git 层）— 已修 2026-09-18

Vercel 项目 `genz-web` 的 git link **错挂 `szpeter2026/DemoPPI`**，导致：

- 推 `genz-web` 不触发部署；
- 推 `DemoPPI` 在此项目按 **Next.js 预设**构建一个 **Vite** 项目 → production ERROR。

修法：源仓转到 `GenzLTD/genz-web`（`szpeter2026/genz-web` 301 到新地址），rootDirectory 空、framework `vite`、outputDirectory `dist`。

### 错链 B（机器层）— 本次修

looma 仓把 `frontend/packages/genz-web` 当作**可部署组件**：

```text
deploy-overseas.sh 第 7 步
  → pnpm build:genz-web
  → rsync --delete dist/ → /var/www/genz-web
  → nginx server_name genz.ltd www.genz.ltd  (注释原文: "VPS fallback if not on Vercel")
```

把营销站和 backend 捆在**同一次海外发布**里，等价于"把一个 Vite 静态站投到新加坡机"。危害是滞留的：

- 公网 apex 已经在 Vercel 上，Vultr 那份是**死副本**；
- **DNS 一旦被指回本机，ICP 已删的旧营销壳会复活**；
- 这份副本会把"栈自包含"当成理由，持续吸引后续改动回投。

修法（本次 PR）：见 §2 的「已摘除的 serve 端」。

---

## 4. 唯一该对齐的是契约，不是代码

两仓之间需要保持一致的**只有契约**，不共享源码、不共享构建产物：

| 契约项 | 值 | 消费方 |
|--------|-----|--------|
| `appRegisterUrl` | `https://tspace.genz.ltd/register` | genz-web 营销 CTA |
| `apiBase` | `https://api.genz.ltd` | genz-web 定价页 / 法律页 / 支付入口 |

（同源口径见 `PIPELINE_MAIN_OVERSEAS_CI.md` §4.1「CI 契约约定营销 CTA」。）

营销站上的 USD 定价走 `GET {apiBase}/v1/payment/plans?region=US`；金额与币种由后端同一份 plan 派生，前端不硬编码。

---

## 5. 摘块安全门禁：`scripts/cutover-test/`

摘掉 nginx server 块是**高风险改动**（误伤 api/tspace 就等于切断收银）。因此配一套本地预演装置，证明三件事：

| 探测 | Host | 期望 |
|------|------|------|
| `GET /health` | `api.genz.ltd` | 200（stub ok） |
| `GET /` | `api.genz.ltd` | 404 `Use /v1`（不出现营销壳） |
| `POST /v1/payment/webhook/stripe` | `api.genz.ltd` | **200（路径还在）** |
| `GET /` | `tspace.genz.ltd` | 200（tspace stub） |
| `GET /` | `genz.ltd` / `www.genz.ltd` | **404 Unknown host（裸域块已摘）** |

装置以 HTTP-only 形态加载「摘块后」的配置（对应 Cloudflare Flexible 回源 :80），用 stub 顶 `:5200` 与 webhook，**不依赖真 Flask、不依赖 SaaS 构建、不依赖 443**。

**它证明：** 摘裸域 nginx 块不会切掉 api webhook，也不会误伤 tspace。
**它不代替：** 真 Flask 后端、真 SaaS 构建产物、HTTPS :443 行为、DNS 真实切换。

---

## 6. 为什么不做「一个仓打到两处」

| 形态 | 问题 |
|------|------|
| 一个仓 → Vercel + Vultr | 两处构建产物必然漂移；发布耦合导致任一侧故障拖死另一侧；`rsync --delete` 会安静地清掉另一侧刚发的东西 |
| looma 内嵌 genz-web + sync | 副本会悄悄落后（本仓子树 HEAD 与公开仓 HEAD 已不同），且"待例行 sync"这类注释会长期挂账作废 |
| 只保留 Vercel 单线 | ✅ 一源一管线：push 即发，构建产物只有一份，回滚点唯一 |

**反模式清单（出现即视为重新引入错链）：**

- 在 `deploy-overseas.sh` / `deploy-overseas.yml` 里恢复 `pnpm build:genz-web` 或 rsync 到 `/var/www/genz-web`
- 在 `docker/nginx.conf` / `nginx-vultr.conf` 里恢复 `server_name genz.ltd www.genz.ltd`
- 把 `/var/www/genz-web` 写进任何部署清单
- 在 Vultr 上手工 `pnpm build` 营销站
- 在 looma 仓内直接改 `frontend/packages/genz-web` 并期望线上生效（改的是归档副本，不是真源）

---

## 7. 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-09-18 | 1.0 | 首版：三站三线钉死；Vultr-Genzltd 收敛为「钱和脑」；摘除 genz.ltd/www serve 端与投递链；新增 `scripts/cutover-test/` 门禁 |
