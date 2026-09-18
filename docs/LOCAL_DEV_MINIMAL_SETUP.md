# 本地最小环境适配指南（无 Docker / 无 ServBay）

> 适用对象：没有 Docker Desktop、没有 ServBay 的团队成员。
> 目标：三个终端命令跑通「后端 API + T-space 前端」，即本地等价线上 Vultr 的
> `api.genz.ltd`（Looma backend）+ `tspace.genz.ltd`（SaaS 前端）两个角色。
>
> 本文口径基于 2026-09-18 main（`dd2c3ce`）实测验证，不依赖任何容器与域名层。

## 为什么不需要 Docker 和 ServBay

| 组件 | 线上角色 | 本地是否必需 | 缺失时的行为 |
|------|----------|--------------|--------------|
| Flask 后端 | `:5200` API | 必需（纯 Python venv） | — |
| SQLite | 数据落库 | 必需（零安装，`backend/data/looma.db`） | — |
| Vite dev proxy | nginx 反代 | 不需要（vite 已内置 `/v1`、`/health` → `127.0.0.1:5200`） | — |
| ChromaDB `:8000` | 语义检索 | 不需要 | RAG 走降级，关键词检索仍在 |
| PostgreSQL/pgvector `:5433` | 向量库 | 不需要 | 向量检索降级，不阻塞启动 |
| Redis / Ollama | 缓存/本地嵌入 | 不需要 | LLM 按 `.env` 配置走 deepseek 或降级 |
| ServBay | HTTPS 域名体验层 | 可选 | 直接用 `http://127.0.0.1:5174` |

**关键机制**：T-space 的 `vite.config.ts` 里 `server.proxy` 把 `/v1` 和 `/health`
代理到 `http://localhost:5200`（可用 `VITE_PROXY_TARGET` 覆盖）。浏览器始终同源访问
前端 dev server，**不存在 CORS 问题，不需要任何 nginx/域名**。

## 快速启动（三步）

### 1. 后端（终端 1）

```bash
cd backend
./dev.sh
```

`dev.sh` 自动完成：检测/创建 Python venv（要求 3.10+，markitdown 依赖）→ 安装依赖 →
检查 `.env` → 建 `data/` 目录 → 开发模式启动 Flask（`FLASK_PORT=5200`）。

验收：

```bash
curl http://127.0.0.1:5200/health
# {"service":"looma-backend","status":"ok","version":"v1", ...}
```

### 2. 前端（终端 2）

```bash
cd frontend
pnpm install          # 首次
pnpm dev:saas         # T-space → http://127.0.0.1:5174
```

浏览器直接打开 `http://127.0.0.1:5174`，所有 `/v1/*` 请求由 vite 代理转发到后端。

### 3. （可选）PlanetX（终端 3）

```bash
pnpm dev:planetx      # → http://127.0.0.1:5173
```

## 停止与重启

- 停止：对应终端 `Ctrl+C`。
- 重启 Mac 后三个服务不会自启，重跑上述命令即可。
- **不要用 `./scripts/start-full-mvp.sh`**：它会再抢 5173/5174 端口重复拉起前端，
  与手动启动的 dev server 冲突。分步启动是推荐路径。

## 本地的支付行为（重要预期管理）

本地后端 `PAYMENT_STUB_MODE` 默认 `true`（`/v1/payment/providers` 返回
`stub_mode: true, providers: []`）：

- 定价页顶部会显示「🚀 开发模式 — Stub 支付开启」横幅；
- 点击升级/试用**不经过微信或 Stripe**，直接免单秒过（stub 升级），订单带
  `mode: stub` 元数据落库仅供审计；
- 「7 天试用」目前是纯前端文案：后端 `update_user_tier` 只改 `users.tier`，
  **没有到期时间字段和回退逻辑**，不要在本地验证「试用到期」类需求；
- 种子测试账号 `beta_admin@looma.test / looma123` 在本地库可能已是 `pro` 档，
  再次升级会返回 400 `Cannot downgrade from pro to pro`，前端表现为
  「操作失败，请稍后重试」。遇到时换一个新注册账号验证即可。

## 可选增强

### 有 ServBay 的成员（macOS）

ServBay 的 nginx vhost 可以给本地套上 HTTPS 域名体验层：

- `api.servbay.host` → `127.0.0.1:5200`
- `tspace.servbay.host` → `127.0.0.1:5174`（vite `allowedHosts` 已含该域名）

仅是体验增强，功能上与直接访问 `127.0.0.1` 完全等价。

### 连海外后端联调

```bash
VITE_PROXY_TARGET=https://api.genz.ltd pnpm dev:saas
```

浏览器仍同源，vite 把 `/v1` 代理到海外 API，避免 CORS。注意此举会读生产库，
测试账号行为以生产为准。

## 故障排查

| 症状 | 原因与处理 |
|------|------------|
| `:5200/health` 不通 | `./dev.sh` 是否仍在跑；看终端报错；Python 版本 < 3.10 换 3.10+ |
| 前端页面开了但登录失败 | 后端没起，或 `VITE_API_BASE` 被设置成了错误地址（不设即走代理） |
| 升级套餐「操作失败」 | 大概率是账号已是目标档位（400 downgrade），换新账号 |
| pnpm 不存在 | `npm i -g pnpm`；仓库是 pnpm workspace，勿用 npm 装依赖 |
