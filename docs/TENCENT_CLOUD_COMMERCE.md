# 腾讯云商业闭环执行手册（P0–P2）

> **同步副本：** 本文档在以下两仓保持 **同文同版**，联调时对照执行  
> - **后端 / 支付 / 小程序：** `/Users/jason/Projects/looma-zervi/docs/TENCENT_CLOUD_COMMERCE.md`  
> - **门户前端：** `/Users/jason/Projects/szbolent-portal/docs/TENCENT_CLOUD_COMMERCE.md`  
> **更新规则：** 任一侧修改 checklist 或域名表，**必须同步另一仓**（或注明版本号 + 日期）  
> **主体与费用选型：** 见 `COMMERCE_ENTITY_DECISION.md`（**§5 香港持股+大陆运营**、§6 费用、§11 选型表）

---

## 0. 角色分工（两边对照）

| 职责 | **looma-zervi**（后端真源） | **szbolent-portal**（门户壳） |
|------|---------------------------|------------------------------|
| JWT / 用户 / tier | ✅ Looma Flask | 消费 `/v1/auth/*`、`/v1/payment/*` |
| 微信登录 | ✅ `/v1/auth/wechat` | 可选 H5；小程序走 looma 小程序 |
| 微信支付 | ✅ 改造 `payment_routes.py` | Pricing / VIP 页调 looma |
| 诗词数据 | ✅ `db/manager.py` → SQLite `poems` + ChromaDB（诗词语义搜索）；HTTP 路由 `/v1/poetry/*` | `src/api/poetry.ts` 经 `/v1/poetry/browse` 等读取，**不直连数据库** |
| AI / RAG | ✅ `backend/src/rag/`（原 Tatha RAG 已完全融入）：通用 RAG + 诗词语义搜索 + 嵌入生成 | 消费 `/v1/ask`（通用问答）和 `/v1/poetry/search`（诗词搜索）；**无需独立 Tatha 服务** |
| 静态门户 | — | ✅ `npm run build` → CDN/Nginx |
| CloudBase | ❌ **已删除**（2026-09） | 认证统一走 Supabase |
| 备案 / 商户号 | 运维 + 主体资质 | 同主体域名 `szbolent.com.cn` |

**身份真源（纠正常见误解）：**

```text
小程序 wx.login → code
    → HTTPS api.szbolent.com.cn/v1/auth/wechat   ← 生产主路径
    → Looma code2session → openid → JWT

CloudBase wechat-login 云函数 = 已删除（2026-09，Supabase 统一认证取代）
                                  不是身份中心，不承载支付回调
```

**诗词数据（纠正常见误解）：**

```text
Portal src/api/poetry.ts
    → HTTP GET /v1/poetry/browse | /random | /:id | /search | /stats
    → poetry_routes.py → db/manager.py
    → SQLite poems 表 + ChromaDB 向量检索

不是：legacy bolent Sanic :8001；也不是独立第三方诗词 API。
Looma 无 poets 表、无 like/view 计数；门户侧做字段适配与作者聚合。
```

**RAG / AI 能力（纠正常见误解）：**

```text
原 Tatha RAG（planetx-tatha poetry_rag）已完全融入 Looma：
    backend/src/rag/chroma_client.py    ← ChromaDB 客户端（通用 + 诗词专用）
    backend/src/rag/embeddings.py       ← 嵌入生成（Ollama/DeepSeek/OpenAI）
    backend/src/agents/poetry_search.py ← 诗词语义搜索
    /v1/poetry/search                   ← HTTP 端点（门户调用）
    /v1/ask                             ← 通用 RAG 问答端点

不是：独立 Tatha 服务 (:8010)；也不需要 poetry_rag namespace。
门户 src/api/tatha.ts 保留但默认关闭，不应在生产环境启用。
```

---

## 1. 域名规划

### 1.1 推荐 DNS（备案通过后生效）

| 域名 | 用途 | 部署目标 | 负责仓 |
|------|------|----------|--------|
| `szbolent.com.cn` | 根域（301 → www） | 跳转至 `www.szbolent.com.cn` | szbolent-portal |
| `www.szbolent.com.cn` | **门户首页（canonical）** | 静态 `dist/`（COS+CDN 或 Nginx） | szbolent-portal |
| `api.szbolent.com.cn` | **Looma REST API** | 腾讯云 CVM/Lighthouse + Nginx → Flask | looma-zervi |
| `cms.szbolent.com.cn` | WordPress headless（可选 P1+） | 轻量/docker WP | 运维 |
| `m.szbolent.com.cn` | 小程序业务 H5（可选） | 静态或反代 | 按需 |

### 1.2 小程序「request 合法域名」

在微信公众平台 → 开发 → 开发管理 → 服务器域名，配置：

| 类型 | 域名 |
|------|------|
| request 合法域名 | `https://api.szbolent.com.cn` |
| uploadFile（若需） | `https://api.szbolent.com.cn` |
| downloadFile（若需） | `https://api.szbolent.com.cn` 或 CDN 域 |

**当前状态：** 小程序 **直连** `api.szbolent.com.cn`，CloudBase 登录透传已下线（2026-09）。

### 1.3 Nginx 参考（api 节点）

基于 `looma-zervi/nginx-looma-zervi.conf` 扩展：

```nginx
# /etc/nginx/sites-enabled/api.szbolent.com.cn
server {
    listen 443 ssl http2;
    server_name api.szbolent.com.cn;

    # ssl_certificate ...（腾讯云 SSL 或 Let's Encrypt）

    location /v1/ {
        proxy_pass http://127.0.0.1:5200;  # 与 backend PORT 一致
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://127.0.0.1:5200;
    }
}

# 门户静态（可独立 server block 或 CDN）
# server_name szbolent.com.cn www.szbolent.com.cn;
# root /var/www/szbolent-portal/dist;
```

### 1.4 门户生产环境变量（szbolent-portal）

`.env.production` 或构建 CI 注入：

```env
VITE_SITE_URL=https://www.szbolent.com.cn
VITE_LOOMA_API_BASE=https://api.szbolent.com.cn
VITE_BLOG_API_BASE=https://cms.szbolent.com.cn/wp-json/wp/v2
```

**诗词说明：** 门户 `src/api/poetry.ts` 调用 Looma **`/v1/poetry/*`**（后端内部读写 `looma.db`），不是独立第三方诗词 API，也不是 legacy bolent Sanic `:8001`。

---

## 2. 备案清单（ICP）

> 在 **腾讯云备案系统** 提交；主体、域名、小程序、微信支付商户建议 **同一企业主体**。  
> **路径与费用选型（个人 / 个体户 / 有限公司 / 香港）** → `COMMERCE_ENTITY_DECISION.md` §3–§6、**§5 既定架构合规要点**。

### 2.1 备案前准备

- [ ] 腾讯云账号已完成实名（企业）
- [ ] 域名 `szbolent.com.cn` 已在腾讯云注册/转入
- [ ] 云服务器（CVM/Lighthouse）已购，大陆节点
- [ ] 营业执照、法人身份证、网站负责人身份证
- [ ] 网站名称、简介（建议：诗词文化 / 个人品牌门户，与小程序类目一致）
- [ ] 隐私政策、用户协议 URL（可先部署静态页到 `www.szbolent.com.cn/legal/*`）

### 2.2 备案材料对照

| 项 | 内容 |
|----|------|
| 网站名称 | SZBolent 诗词门户（示例，与小程序名称协调） |
| 首页 URL | `https://www.szbolent.com.cn` |
| 前置审批 | 一般无需；涉及出版/新闻需另查 |
| API 域 | `api.szbolent.com.cn` 作为二级域名一并备案 |
| 服务器 IP | 填入腾讯云实例公网 IP |

### 2.3 备案后 24h 内必做

- [ ] DNS A 记录：`api` → 服务器 IP
- [ ] DNS：`www` / `@` → CDN 或服务器
- [ ] 全站 HTTPS（腾讯云 SSL 证书）
- [ ] 更新 `looma-zervi/frontend/packages/shared-core/src/types/brand.ts` 中 `domain` TODO
- [x] ~~`cloudbase/functions/wechat-login/index.js`~~ 已删除（2026-09）
- [ ] 更新 `frontend/packages/miniprogram/utils/config.ts` → `API_BASE = 'https://api.szbolent.com.cn'`
- [ ] 微信公众平台配置合法域名
- [ ] 运行联调脚本（见 §6）

---

## 3. CloudBase 已移除

### 3.1 当前状态（2026-09）

`cloudbase/` 目录已整体删除（`functions/wechat-login/`、`cloudbaserc.json`、`README.md`）。
小程序登录不再经 CloudBase 透传，统一走 **Supabase Auth**（RFC `docs/rfc/supabase-unified-auth-v1.md`）：

| 环境 | 登录路径 |
|------|----------|
| **生产** | 小程序 → `https://api.szbolent.com.cn/v1/auth/wechat`（Supabase Admin API + custom JWT） |
| **开发** | 开发者工具「不校验合法域名」→ `http://127.0.0.1:5200` |
| **身份源** | Supabase Auth（THOMAS 生态统一身份层） |

---

## 4. 支付接口改造点（looma-zervi）

> 当前 **`payment_routes.py` 为 Stub**（`POST /v1/payment/upgrade` 直接改 tier，无真实收款）。

### 4.1 需新增 / 改造的后端模块

| 优先级 | 文件 / 模块 | 改造内容 |
|--------|-------------|----------|
| P1 | `backend/src/api/routes/payment_routes.py` | Stub → 统一下单 + 查询订单 |
| P1 | **新建** `backend/src/payment/wechat_pay.py` | 微信 JSAPI/小程序支付签名、验签 |
| P1 | **新建** `backend/src/api/routes/payment_notify_routes.py` | `POST /v1/payment/notify/wechat` 回调 |
| P1 | `backend/src/db/manager.py` | 表：`orders`、`payments`、`subscriptions` |
| P2 | `backend/src/utils/quota.py` | tier 变更仅允许来自 **已支付订单** |
| P2 | `backend/src/api/routes/poetry_routes.py` | 可选 `@require_tier` 门控 VIP 内容 |

### 4.2 API 契约（目标）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/payment/plans` | 保留；增加 `plan_id`、周期价 |
| GET | `/v1/payment/status` | 返回 tier + `subscription_expires_at` |
| POST | `/v1/payment/orders` | **新建** 创建订单，返回 `prepay_id` / 小程序支付参数 |
| POST | `/v1/payment/notify/wechat` | **微信回调**（无 JWT，验签） |
| POST | `/v1/payment/upgrade` | **废弃或内测-only**；生产返回 410 |

### 4.3 环境变量（backend `.env`）

```env
# 已有
WECHAT_APPID=wx********
WECHAT_APP_SECRET=********
JWT_SECRET=********（≥32 字符）

# P1 新增 — 微信支付商户（腾讯云申请后填入）
WECHAT_PAY_MCH_ID=********
WECHAT_PAY_API_V3_KEY=********
WECHAT_PAY_CERT_SERIAL=********
WECHAT_PAY_PRIVATE_KEY_PATH=/secure/apiclient_key.pem
WECHAT_PAY_NOTIFY_URL=https://api.szbolent.com.cn/v1/payment/notify/wechat
PAYMENT_STUB_MODE=false
```

### 4.4 前端改造点

| 仓 | 文件 | 改造 |
|----|------|------|
| looma-zervi | `frontend/packages/shared-core/src/types/payment.ts` | 增加 `OrderCreateResponse`、小程序 pay 参数 |
| looma-zervi | `frontend/packages/shared-core/src/api/createApi.ts` | `createPaymentApi().createOrder()` |
| looma-zervi | `frontend/packages/saas/src/features/pricing/Pricing.tsx` | Stub 升级 → 调起 `wx.requestPayment` 或 H5 收银台 |
| looma-zervi | `frontend/packages/miniprogram/utils/api.ts` | 支付完成后刷新 JWT |
| szbolent-portal | **新建** `src/api/looma.ts` | auth + payment + poetry 封装 |
| szbolent-portal | **新建** `src/views/Pricing.vue`（或改 Services） | 套餐页 + 登录态 + 升级 |

---

## 5. P0–P2 可执行 Checklist

> **联调约定：** 每完成一项，在 **两仓** 同版本文档打 `[x]`，并在 PR 描述写 `TENCENT_CLOUD_COMMERCE P0-x`。

### P0 — 备案与连通（无真实支付）

**目标：** 备案域名 + HTTPS + 小程序/门户能调通 Looma API。

#### 运维 / 主体

- [ ] **P0-1** 腾讯云企业实名 + 购买大陆服务器
- [ ] **P0-2** 提交 `szbolent.com.cn`、`api.szbolent.com.cn` ICP 备案
- [ ] **P0-3** 备案通过：DNS + SSL 证书部署
- [ ] **P0-4** 申请微信小程序（或与现有 PlanetX 小程序协调类目/主体）
- [ ] **P0-5** 微信公众平台配置 `api.szbolent.com.cn` 合法域名

#### looma-zervi（后端）

- [ ] **P0-6** 服务器部署 Flask（`PORT=5200`，systemd/docker）
- [ ] **P0-7** Nginx 反代 `api.szbolent.com.cn` → `:5200`（见 §1.3）
- [ ] **P0-8** 生产 `.env`：`WECHAT_DEV_MODE=false`，填入真实 `WECHAT_APPID/SECRET`
- [ ] **P0-9** `GET https://api.szbolent.com.cn/health` 返回 200
- [ ] **P0-10** `POST /v1/auth/wechat` 真机小程序登录成功，返回 JWT
- [ ] **P0-11** 小程序 `config.ts` 指向 `https://api.szbolent.com.cn`（弃用 CloudBase 透传）
- [ ] **P0-12** 运行 `scripts/verify-closed-loop.sh`（`API_BASE=https://api.szbolent.com.cn`）

#### szbolent-portal（门户）

- [ ] **P0-13** 生产构建：`VITE_LOOMA_API_BASE=https://api.szbolent.com.cn`
- [ ] **P0-14** 部署 `dist/` 至 `www.szbolent.com.cn`（CDN 或 Nginx）
- [ ] **P0-15** 门户 `src/api/poetry.ts` 对接 Looma 诗词数据层（`/v1/poetry/browse`、`/random` 等；替换 legacy bolent `:8001`）
- [ ] **P0-16** 门户可打开 HTTPS 首页，诗词列表有数据（或 graceful 空态）
- [ ] **P0-17** 隐私政策 / 用户协议页面上线（备案与小程序审核需要）

#### 联调验收（P0 Done 定义）

```bash
# 1. API 健康
curl -sf https://api.szbolent.com.cn/health

# 2. 诗词公开浏览
curl -sf "https://api.szbolent.com.cn/v1/poetry/random?count=1"

# 3. 门户可访问
curl -sfI https://www.szbolent.com.cn | head -1
```

- [ ] **P0-18** 以上三条命令均通过
- [ ] **P0-19** 小程序真机：登录 → 浏览诗词 → 无 CloudBase 依赖

---

### P1 — 微信支付与 tier 闭环

**目标：** 真实收款 → 回调 → tier 升级 → 门户/小程序感知会员状态。

#### 商户与合规

- [ ] **P1-1** 申请 **微信支付商户号**（营业执照、对公账户、经营类目）
- [ ] **P1-2** 商户平台绑定小程序 AppID
- [ ] **P1-3** 配置 API 证书 / APIv3 密钥
- [ ] **P1-4** 回调 URL 白名单：`https://api.szbolent.com.cn/v1/payment/notify/wechat`

#### looma-zervi（后端）

- [ ] **P1-5** DB 迁移：`orders`、`payments` 表
- [ ] **P1-6** 实现 `POST /v1/payment/orders`（统一下单）
- [ ] **P1-7** 实现 `POST /v1/payment/notify/wechat`（验签 + 幂等 + 更新 tier）
- [ ] **P1-8** `PAYMENT_STUB_MODE=false` 时禁用直接 `upgrade` Stub
- [ ] **P1-9** `GET /v1/payment/status` 返回 `expires_at`
- [ ] **P1-10** 单元测试：回调验签、重复通知幂等

#### looma-zervi（前端 / 小程序）

- [ ] **P1-11** Pricing 页：创建订单 → `wx.requestPayment`
- [ ] **P1-12** 支付成功：刷新 JWT / 重新 `GET /v1/payment/status`
- [ ] **P1-13** 分析埋点：`trial_started` → 改为 `payment_success` 等真实事件

#### szbolent-portal

- [ ] **P1-14** 新增 `/pricing` 套餐页（调 looma plans + orders）
- [ ] **P1-15** 登录态：localStorage `looma_token`（与 PlanetX 键名一致）
- [ ] **P1-16** 未登录点击购买 → 引导微信扫码 / 小程序码 / H5 登录

#### 联调验收（P1 Done 定义）

- [ ] **P1-17** 小程序 0.01 元测试单支付成功
- [ ] **P1-18** 回调后 `users.tier` 变为 `supporter` 或 `pro`
- [ ] **P1-19** 门户 Pricing 页展示正确 tier
- [ ] **P1-20** `scripts/verify-closed-loop.sh` 中 Stub 升级步骤改为真实支付或跳过并文档化

---

### P2 — 内容订阅与运营化

**目标：** VIP 内容、订阅周期、门户完整商业体验。

#### looma-zervi

- [ ] **P2-1** 表：`subscriptions`（周期、自动续费标记）
- [ ] **P2-2** `/v1/poetry/*` VIP 内容 `@require_tier('supporter')`
- [ ] **P2-3** 订阅到期 cron：降级 tier + 通知
- [ ] **P2-4** Boost Pack 购买 API（schema 已有，补路由）
- [ ] **P2-5** 发票 / 订单列表 `GET /v1/payment/orders`（用户侧）

#### szbolent-portal

- [ ] **P2-6** 诗词详情页：VIP 遮罩 + 跳转 Pricing
- [ ] **P2-7** 博客 headless（`cms.szbolent.com.cn`）+ 会员文章标记
- [ ] **P2-8** Footer 邮件订阅（Newsletter API 或第三方）
- [ ] **P2-9** SEO：`company.ts` `siteUrl` 生产校验

#### 运维

- [ ] **P2-10** 日志与对账：微信支付账单 ↔ `orders` 日对账
- [ ] **P2-11** 监控：`/health` + 支付回调失败告警
- [ ] **P2-12** CloudBase 云函数正式下线确认

#### 联调验收（P2 Done 定义）

- [ ] **P2-13** 免费用户看不到 VIP 诗词全文；付费后可看
- [ ] **P2-14** 订阅到期后自动降级，门户与小程序一致
- [ ] **P2-15** 端到端文档更新 SurfaceZervi `MANIFEST.yaml` / `poetries-of-bolent`

---

## 6. 双仓联调矩阵

| 场景 | looma 动作 | portal 动作 | 验证 |
|------|------------|-------------|------|
| 本地开发 | `cd backend && python run.py`（:5200） | `npm run dev` + proxy `/v1` → :5200 | 门户诗词有数据 |
| 备案 staging | 部署 api 测试域 | `VITE_LOOMA_API_BASE` 指向 staging | curl + 浏览器 |
| 支付沙箱 | 启用 Stub 或微信 sandbox | Pricing 页调订单 API | tier 变化 |
| 生产 | `PAYMENT_STUB_MODE=false` | 生产 CDN 构建 | 真机 0.01 元 |

### 6.1 本地联调（开发阶段）

**looma-zervi：**

```bash
cd /Users/jason/Projects/looma-zervi/backend
source venv/bin/activate
python run.py   # 确认 PORT=5200
```

**szbolent-portal：** 在 `vite.config.ts` 增加（若尚未配置）：

```ts
proxy: {
  '/v1': { target: 'http://127.0.0.1:5200', changeOrigin: true },
}
```

`.env.local`：

```env
VITE_LOOMA_API_BASE=
# 留空则走同源 /v1 proxy；生产填 https://api.szbolent.com.cn
```

**诗词联调（Looma 字段契约）：**

| 门户方法 | Looma 路由 | 主要参数 / 响应 |
|----------|-----------|----------------|
| `getPoems` | `GET /v1/poetry/browse` | `dynasty`, `author`, `theme`, `keyword`, `page`, `per_page` → `{ items, total, page, per_page }`；item 含 `content_preview` |
| `getPoem` | `GET /v1/poetry/:id` | 全文 `content` |
| `getRandom` | `GET /v1/poetry/random` | `count`（非 `n`）→ `{ results, count }` |
| `search` | `GET /v1/poetry/search` | `q`, `n` |
| `getStats` | `GET /v1/poetry/stats` | `total`, `dynasties`, `themes` |

---

## 7. 风险与边界

| 风险 | 缓解 |
|------|------|
| 主体不一致导致支付审核失败 | 域名、小程序、商户同一企业 |
| CloudBase 与 CVM 双写逻辑 | 业务只在 Looma，CloudBase 不承载支付 |
| JobFirst 与 Bolent 叙事混线 | 共用 looma 账号/支付；**首屏文案分离** |
| nginx PORT 与 run.py 不一致 | 部署 checklist 写死同一 PORT（建议 5200） |
| Stub 误上生产 | `PAYMENT_STUB_MODE` 生产必须为 `false` |

---

## 8. 相关文件索引

### looma-zervi

| 路径 | 说明 |
|------|------|
| `backend/src/api/routes/payment_routes.py` | 支付 Stub（P1 改造） |
| `backend/src/api/routes/auth_routes.py` | `/v1/auth/wechat` |
| `backend/src/api/routes/poetry_routes.py` | 诗词 HTTP 路由（内部 `db/manager.py`） |
| ~~`cloudbase/`~~ | 已删除（2026-09，Supabase 统一认证取代） |
| `frontend/packages/miniprogram/utils/config.ts` | 小程序 API_BASE |
| `nginx-looma-zervi.conf` | Nginx 模板 |
| `scripts/verify-closed-loop.sh` | 闭环烟雾测试 |

### szbolent-portal

| 路径 | 说明 |
|------|------|
| `src/config/company.ts` | 品牌 / SEO |
| `src/api/poetry.ts` | Looma `/v1/poetry/*` 客户端 + 门户字段适配 |
| `src/api/tatha.ts` | **已废弃**（Tatha RAG 已融入 Looma `backend/src/rag/`），默认关闭不可用 |
| `vite.config.ts` | 开发 proxy |
| `.env.example` | 环境变量模板 |
| `docs/INTEGRATION.md` | 集成总览（已更新：双后端架构） |
| `docs/LINEAGE.md` | 溯源边界（已更新：Looma 替代 Tatha + legacy） |

---

## 9. 版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-07-03 | 初版：域名、备案、支付改造、CloudBase 降级、P0–P2 |
| 1.1 | 2026-07-03 | 诗词表述改为数据访问层；browse/random 字段契约；`poetry.ts` 对接 Looma |
| 1.2 | 2026-07-03 | **审阅修订**：Tatha RAG 已完全融入 Looma（`backend/src/rag/`），移除独立 Tatha 服务表述；`src/api/tatha.ts` 标记为已废弃 |

---

*维护者：Jason + szbenyx · 战略索引：`SurfaceZervi/GitHub/szjason72/poetries-of-bolent`*
