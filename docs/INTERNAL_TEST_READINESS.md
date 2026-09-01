# 内测 Ready Runbook

> **版本：** 1.0 · **日期：** 2026-07-06  
> **受众：** Jason（前端）、@szbenyx（后端/运维）、内测志愿者协调人  
> **关联文档：** [PRESSURE_TEST_ASK_CONTRACT_ADR.md](./PRESSURE_TEST_ASK_CONTRACT_ADR.md) · [LOCAL_MVP_DEBUGGING.md](./LOCAL_MVP_DEBUGGING.md) · [MINIPROGRAM_LOCAL_DEBUGGING.md](./MINIPROGRAM_LOCAL_DEBUGGING.md) · [TENCENT_CLOUD_COMMERCE.md](./TENCENT_CLOUD_COMMERCE.md) · [MCP底座交付说明_内测.md](./MCP底座交付说明_内测.md)

---

## 1. 目的与 Done 定义

本文档回答：**本地 P0 工程完成后，还要做什么才算内测准备「完备」**。

| 阶段 | 含义 | 当前状态 |
|------|------|----------|
| **本地 P0** | 代码契约统一、脚本就绪、本地 gunicorn 可跑 | ✅ 已完成（main `6bc5565`） |
| **内测 Ready** | 公网环境可重复部署、有容量数字、三端可验收、可交接志愿者 | ⬜ 进行中 |

**内测 Ready 验收（8 项全勾 = 可开测）：**

```text
[ ] 1. 内测机 verify-deployment.sh 全绿
[ ] 2. verify-p0-local + verify-closed-loop 对公网 API 通过
[ ] 3. k6 nocache VU=5 基线写入 docs/k6_baseline_main.json（内测机）
[ ] 4. pnpm e2e:live:all 对内测 API 通过
[ ] 5. 小程序真机四条链路通过
[ ] 6. SaaS 5 人并发 Ask 人工冒烟无长连接阻塞
[ ] 7. Runbook + 志愿者测试指南 + 反馈渠道就绪
[ ] 8. ADR / PLATFORM_CAPS 与 main 状态一致
```

**最小开测集（可并行推进）：** 1 + 2 + 3 + 5。

---

## 2. 架构与内测边界

### 2.1 服务拓扑

```text
                    ┌─────────────────────────────────────┐
  志愿者浏览器       │  Nginx (HTTPS)                       │
  小程序真机    ───► │  /        → PlanetX SPA              │
                    │  /tspace/ → SaaS SPA                 │
                    │  /v1/     → gunicorn :5200           │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │  gunicorn (≥4 workers, sync)         │
                    │  Flask app — consent / quota / RAG   │
                    └─────────────────┬───────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │ SQLite + ChromaDB     │ DeepSeek API            │
              │ data/poetry_full      │ (central_brain.py)      │
              └───────────────────────┴───────────────────────┘

  可选并行：MCP Sidecar :8999（Cursor / 内测脚本，非主链路必需）
```

### 2.2 内测测什么 / 不测什么

| 测 | 不测 |
|----|------|
| Ask 非流式 JSON（三端统一） | 浏览器 100 并发压 UI |
| consent / quota / 429 行为 | 真 SSE / askStream |
| 闭环：注册 → 人格 → 分享 → HR 导入 | Rust 重写 shared-core |
| 诗词 RAG、职位列表、简历匹配（配额允许时） | 整分支 merge LLM feature 分支 |
| gunicorn 多 worker 并发 | Flask dev.sh 单进程扛内测流量 |

### 2.3 SLO 目标（k6 跑完后签字确认）

| 指标 | 目标 | 备注 |
|------|------|------|
| Ask p95（DeepSeek，nocache，VU≤5） | < 8s | 本地 gunicorn 基线 ~0.5s（可能命中缓存/短答，以内测机 k6 为准） |
| Ask p95（cache hit，相同 query 120s 内） | < 500ms | `ask_routes.py` 结果缓存 64 条 / 120s |
| 错误率（不含预期 429） | < 5% | |
| 并发 Ask 用户（内测规模） | ≥ 10 | 超出后观察 429 / 超时，非 bug |

---

## 3. 执行顺序（推荐）

按依赖关系依次推进；标 ⭐ 为阻塞开测项。

---

### Phase 1 ⭐ 内测机部署与远端验收

#### 1.1 服务器前置

- [ ] 腾讯云实例就绪（建议 2C4G+，诗词向量库需磁盘空间）
- [ ] **备案前 IP 内测**（当前云 IP `1.14.202.161`）：
  - 安全组 **仅放行 TCP 80** 即可（Nginx 反代 `/v1/`、`/health` → `127.0.0.1:5200`）
  - **不必**对公网放行 **5200**（gunicorn 只监听本机；更安全）
  - SSH（PEM）：`chmod 400 key.pem`，参考 `scripts/ssh-looma-cloud.config.example` 写入 `~/.ssh/config`，或：
    ```bash
    SSH_KEY=~/path/to/key.pem SSH_USER=ubuntu ./scripts/deploy-cloud-internal-test.sh
    ```
  - 验收：`./scripts/test-cloud-connectivity.sh`
  - 本地前端联调：`./scripts/start-local-against-cloud.sh`
- [ ] 域名 + ICP 备案 + SSL（小程序/Web 必需 HTTPS）
- [ ] 微信小程序：合法域名配置 `api.xxx.cn`
- [ ] GitHub Secrets / 服务器 `.env` 已配置（见 §6）

#### 1.2 后端部署（gunicorn，勿用 dev.sh）

```bash
# 服务器上
cd /opt/looma-zervi   # 或 DEPLOY_PATH
git pull origin main

cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt   # 或 poetry install
pip install gunicorn

# 确认 .env（见 §6）
cp .env.example .env   # 首次；编辑生产值

# 启动（前台调试）
./start_gunicorn.sh

# 或 systemd（推荐内测机常驻）
# 参考 LOCAL_MVP_DEBUGGING.md §内测部署配置
```

**验收：**

```bash
curl -sf http://127.0.0.1:5200/health
# {"service":"looma-backend","status":"ok"}
```

#### 1.3 Nginx 反代

使用仓库根目录 `nginx-looma-zervi.conf` 为模板。

> ⚠️ **端口对齐：** 模板已统一为 `proxy_pass http://127.0.0.1:5200`（与 `gunicorn_config.py` / `dev.sh` 一致）。

```nginx
location /v1/ {
    proxy_pass http://127.0.0.1:5200;
    proxy_read_timeout 120s;   # LLM 长请求
    # ... 其余 header 同模板
}
location /health {
    proxy_pass http://127.0.0.1:5200;
}
```

```bash
sudo nginx -t && sudo nginx -s reload
```

#### 1.4 前端构建与发布

**PlanetX / SaaS 构建时必须注入 API 地址**（勿依赖 fallback `1.14.202.161`）：

```bash
cd frontend
export VITE_API_BASE=https://api.xxx.cn
export VITE_API_BASE_URL=https://api.xxx.cn

pnpm install
pnpm --filter @looma/planetx build
pnpm --filter @looma/saas build

# 部署 dist 至 Nginx root / alias（见 nginx-looma-zervi.conf）
# PlanetX → /var/www/planetx/dist
# SaaS    → /var/www/saas/dist  （/tspace/ 路径）
```

**小程序：**

- [ ] `frontend/packages/miniprogram` 中 API 指向 `https://api.xxx.cn`
- [ ] `WECHAT_DEV_MODE=false`，服务器配置真实 `WECHAT_APPID/SECRET`
- [ ] 微信开发者工具 → 上传体验版 → 志愿者扫码

也可使用 CI：`.github/workflows/deploy.yml`（push `main` 自动部署）。

**GitHub Secrets 示例（内测机 `1.14.202.161`）：**

| Secret | 值 |
|--------|-----|
| `SSH_HOST` | `1.14.202.161` |
| `SSH_USER` | `ubuntu` |
| `SSH_PRIVATE_KEY` | `looma_key.pem` 全文 |
| `DEPLOY_PATH` | `/opt/looma-zervi`（可省略，workflow 默认此路径） |
| `ENV_JWT_SECRET` / `ENV_DEEPSEEK_API_KEY` | 生产密钥 |

**Repository Variable（可选）：** `DEPLOY_NGINX_MODE=ip`（备案前默认，使用 `nginx-looma-zervi-ip.conf`）

#### 1.5 远端自动化验收 ⭐

```bash
# 替换为内测域名或 IP
./scripts/verify-deployment.sh api.xxx.cn

API_BASE=https://api.xxx.cn ./scripts/verify-p0-local.sh
API_BASE=https://api.xxx.cn ./scripts/verify-closed-loop.sh
```

**Phase 1 Done：** 三条公网 curl 通过 + verify-deployment 无 FAIL：

```bash
curl -sf https://api.xxx.cn/health
curl -sf "https://api.xxx.cn/v1/poetry/random?count=1"
curl -sfI https://xxx.cn | head -1    # 门户/PlanetX 首页
```

---

### Phase 2 ⭐ 容量基线（k6 + SLO 签字）

本地已用 Python `concurrency_test.py` 跑通 5×20；**内测机须补 k6 正式基线**。

#### 2.1 安装 k6（内测机或 CI）

```bash
# macOS
brew install k6

# Linux
sudo gpg -k && curl -fsSL https://dl.k6.io/key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/k6-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt update && sudo apt install k6
```

#### 2.2 运行 nocache 压测

压测脚本会自动注册测试用户并授予 `ask_rag` consent（无需硬编码 token）。

```bash
# 确保后端在 :5200 运行
export LOOMA_URL=https://api.xxx.cn   # 或 http://127.0.0.1:5200 本机打

k6 run scripts/k6_ask_test_nocache.js \
  --vus 5 \
  --duration 30s \
  -e LOOMA_URL="$LOOMA_URL"

# 轻量 Python 对比（可选）
python3 scripts/concurrency_test.py \
  --url "${LOOMA_URL}/v1/ask" \
  --concurrency 5 \
  --requests 20 \
  --ready-url "${LOOMA_URL}/health"
```

#### 2.3 记录基线

```bash
# 在内测机上
BACKEND_LABEL="gunicorn (production, N workers)" \
  API_BASE=https://api.xxx.cn \
  ./scripts/run_baseline_test.sh
```

将结果 commit 到 `docs/k6_baseline_main.json`，并在 ADR §4 SLO 表格旁注明日期与环境。

**Phase 2 Done：** k6 报告归档 + SLO 四项有实测值或签字豁免说明。

---

### Phase 3 端到端与多端冒烟

#### 3.1 L2 — Playwright live E2E

```bash
cd frontend

# 对内测 API（需后端 + 前端 dev 或 staging 指向内测 API）
export VITE_API_BASE=https://api.xxx.cn
pnpm e2e:live:all
```

覆盖：SaaS 登录/consent、PlanetX 闭环等 live spec。

#### 3.2 L3 — SaaS 人工并发冒烟

**目标：** 5～10 名志愿者同时在使用 SaaS Chat 提问。

| 检查项 | 预期 |
|--------|------|
| 提问后 UI | 加载态 → 一次性显示完整回答（非流式逐字） |
| 并发 5 人 | 无「全员卡死」；慢请求可接受（数秒级） |
| consent 未授权 | 403 + 引导授权，非白屏 |
| quota 耗尽 | 429，文案清晰 |

#### 3.3 L5 — 小程序真机四条链路

按 [MINIPROGRAM_LOCAL_DEBUGGING.md](./MINIPROGRAM_LOCAL_DEBUGGING.md)：

```text
1. splash / 微信登录
2. hub — 加载人格与任务
3. ask — RAG 提问 + ask_rag consent
4. result — 分享 + profile_share consent
```

```bash
./scripts/start-miniprogram-local.sh   # 本地联调指引
./scripts/verify-p0-local.sh           # API 层预检
```

#### 3.4 MCP Sidecar（可选）

若内测包含 Cursor MCP 场景：

```bash
cd backend/mcp-servers
../venv/bin/python3 server.py   # 默认 :8999
```

`verify-p0-local.sh` Step 7 应显示 MCP 端口可达。

**Phase 3 Done：** E2E 绿 + 小程序真机 checklist 签字 + SaaS 并发冒烟记录（截图/日志即可）。

---

### Phase 4 文档、流程与志愿者交接

#### 4.1 运维 Runbook（值班必读）

| 操作 | 命令 |
|------|------|
| 查看 gunicorn | `ps aux \| grep gunicorn` |
| 日志 | `journalctl -u looma-backend -f` 或 `/tmp/looma-gunicorn.log` |
| 重启后端 | `sudo systemctl restart looma-backend` 或 `kill $(lsof -t -i:5200) && cd backend && ./start_gunicorn.sh` |
| 重载 Nginx | `sudo nginx -t && sudo nginx -s reload` |
| 健康检查 | `curl -sf https://api.xxx.cn/health` |

#### 4.2 回滚

```bash
cd /opt/looma-zervi
git log -5 --oneline
git checkout <上一稳定 tag 或 commit>
cd backend && source venv/bin/activate && ./start_gunicorn.sh
# 或 systemctl restart looma-backend
# 前端：重新 deploy 上一版 artifacts 或 git checkout 后 rebuild
```

#### 4.3 志愿者测试指南（建议复制到 Issue / 飞书）

**账号与入口：** 复制 [内测志愿者账号与入口.example.md](./内测志愿者账号与入口.example.md) 为本地 `内测志愿者账号与入口.md` 并填入凭证（已 `.gitignore`，勿提交）

```markdown
## 内测范围
- PlanetX：注册/登录、人格测试、Ask、T 空间入口
- SaaS：HR 注册、候选人导入、Ask 知识库
- 小程序：登录、提问、结果分享

## 不测
- 支付真实扣款（upgrade 为 stub）
- 流式打字效果（当前为非流式 JSON）

## 反馈模板
- 端：PlanetX / SaaS / 小程序
- 步骤：1…2…3…
- 预期 vs 实际
- 截图 / 网络面板（/v1/ask 状态码）
- 时间 + 账号 tier（guest/free/pro）
```

#### 4.4 文档同步 ⭐

- [ ] [PRESSURE_TEST_ASK_CONTRACT_ADR.md](./PRESSURE_TEST_ASK_CONTRACT_ADR.md) — P0 勾选 ✅，§3.4 SaaS 假 SSE 改为已修复
- [ ] [PLATFORM_CAPS.md](../frontend/packages/shared-core/src/PLATFORM_CAPS.md) — SaaS 行改为 `useChatNonStreaming` ✅
- [ ] 本文档 §1 验收清单打勾

**Phase 4 Done：** 志愿者拿到链接 + 指南 + 反馈渠道；值班有 Runbook。

---

### Phase 5 内测并行（P1，不阻塞开测）

| ID | 项 | 说明 |
|----|-----|------|
| P1-1 | LLM fallback + 缓存 | 从 `feature/llm-provider-fallback-k6-baseline` cherry-pick 思路，适配 `central_brain.py` |
| P1-2 | k6 对比报告 | main vs 分支 nocache 5 VU |
| P1-3 | CI k6 smoke | VU=1，需 `DEEPSEEK_API_KEY` secret |
| P1-4 | `docs/api.yaml` 对齐 | `/v1/ask` schema 含 stream 规划 |

---

## 4. 本地预检（开发机，开测前最后一遍）

开发者在推 main / 触发部署前：

```bash
git checkout main && git pull

# 静态 P0
./scripts/verify_ask_contract_fix.sh
./scripts/verify-mvp-setup.sh

# 本地 gunicorn + API
cd backend && ./start_gunicorn.sh &
./scripts/test-planetx-api.sh
./scripts/run_baseline_test.sh

# 合规 + 闭环
./scripts/verify-p0-local.sh

# 可选全栈
./scripts/start-full-mvp.sh
```

---

## 5. 常见问题（FAQ）

| 现象 | 原因 | 处理 |
|------|------|------|
| Ask 403 `consent_required` | 未 grant `ask_rag` | 各端 consent 流程；压测用 `concurrency_test.py` 自动注册 |
| Ask 429 | quota 按 tier 耗尽 | 正常；检查 `GET /v1/quota` |
| SaaS 长时间空白后突然出字 | 旧版假 SSE（已修复） | 确认 main 含 `useChatNonStreaming` |
| PlanetX 打到 1.14.202.161 | 未设 `VITE_API_BASE` | 构建/启动脚本 export 内测 API |
| Nginx 502 | 端口不一致 | Nginx → **5200**，非 5000 |
| k6 全 403 | 无 consent | 使用最新 `concurrency_test.py`（自动 grant） |
| MCP ⚠ 8999 | Sidecar 未启 | 可选；`backend/mcp-servers/server.py` |
| LLM 超时 | DeepSeek 慢或 Key 无效 | 查 `DEEPSEEK_API_KEY`；gunicorn `timeout=120` |

---

## 6. 生产环境变量清单

`backend/.env`（内测机，**勿提交 git**）：

```bash
FLASK_ENV=production
FLASK_PORT=5200

DATABASE_PATH=/opt/looma-zervi/data/looma.db
POETRY_CHROMA_PATH=/opt/looma-zervi/data/poetry_full

JWT_SECRET=<至少32字符随机串>
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24

WECHAT_APPID=<真实 AppID>
WECHAT_SECRET=<真实 Secret>
WECHAT_DEV_MODE=false

DEEPSEEK_API_KEY=<Key>
DEEPSEEK_BASE_URL=https://api.deepseek.com

CORS_ORIGINS=https://xxx.cn,https://api.xxx.cn
```

GitHub Actions Deploy 对应 Secrets：`ENV_JWT_SECRET`、`ENV_DEEPSEEK_API_KEY`、`SSH_*`；`DEPLOY_PATH` 默认 **`/opt/looma-zervi`**。

---

## 7. 脚本索引

| 脚本 | 用途 | 环境 |
|------|------|------|
| `scripts/verify_ask_contract_fix.sh` | P0 契约静态检查 | 本地 |
| `scripts/verify-mvp-setup.sh` | 依赖与目录 | 本地 |
| `scripts/verify-deployment.sh <host>` | 内测机全量验收 | **远端** |
| `scripts/verify-p0-local.sh` | 合规 + consent | 本地/远端 |
| `scripts/verify-closed-loop.sh` | _seeker→HR 闭环_ | 本地/远端 |
| `scripts/run_baseline_test.sh` | Python 基线 + JSON | 本地/远端 |
| `scripts/run_gunicorn_concurrency_test.sh` | Flask→gunicorn 对比 | 本地 |
| `scripts/k6_ask_test_nocache.js` | k6 nocache 压测 | 内测机 |
| `scripts/concurrency_test.py` | 多线程并发 | 本地/远端 |
| `scripts/start-full-mvp.sh` | 全栈本地联调 | 本地 |
| `backend/start_gunicorn.sh` | 内测后端启动 | 服务器 |

---

## 8. 维护

| 事件 | 动作 |
|------|------|
| k6 基线跑完 | 更新 `docs/k6_baseline_main.json` + ADR §4 |
| 内测开测 | §1 八项 checklist 打勾，记录日期与负责人 |
| P1 LLM resilience 合入 | 重跑 Phase 2 k6，更新 SLO |
| 生产域名变更 | 同步 nginx、小程序合法域名、VITE_* 构建参数 |

---

*内测 Ready 签字：Jason ________ 日期 ________ · @szbenyx ________ 日期 ________*

---

## 9. 疏漏审查对照（2026-07-06）

基于 main `6bc5565` 审查，以下项已在本仓库修复或文档化：

| # | 项 | 处理 |
|---|-----|------|
| 1 | 端口 5000/5200 混乱 | ✅ 统一默认 **5200**：`run.py`、`.env.example`、`nginx-looma-zervi.conf`、Docker、PlanetX vite proxy、deploy.yml |
| 2 | PlanetX fallback staging IP | ✅ 改为 `http://127.0.0.1:5200` |
| 3 | 脚本硬编码 Mac 路径 | ✅ 改为通用「请在仓库根目录运行」 |
| 4 | backend/.env 缺失 | ✅ `backend/.env.example` + `start-full-mvp.sh` 从 `.env.example` 复制 |
| 5 | poetry_full 缺失无提示 | ✅ `verify-mvp-setup.sh` / `start-full-mvp.sh` 显式警告 |
| 6 | CloudBase 占位符 | ✅ `cloudbase/` 已删除（2026-09），认证统一走 Supabase（RFC supabase-unified-auth-v1） |
| 7–8 | nginx / Docker 端口 | ✅ 见 #1 |
| 9 | JWT_EXPIRATION_HOURS 等变量名 | ✅ 统一用 `.env.example` 真源 |
| 10 | 小程序 build:npm | ✅ `start-full-mvp.sh` 失败时给出完整命令 |
| 11 | 内测 Checklist | ✅ 本文档 §1 八项清单 |
| 12 | Windows 脚本 | ⬜ 待办：`.ps1` 等价物（非内测阻塞） |
| 13 | E2E 空目录 | ❌ 不准确 — `frontend/e2e/*.live.spec.ts` 已存在 |
| 14 | 微信开发者工具 | 📄 见 [MINIPROGRAM_LOCAL_DEBUGGING.md](./MINIPROGRAM_LOCAL_DEBUGGING.md) |

**端口约定（全仓）：** 开发/内测后端 **`5200`**；gunicorn / dev.sh / 小程序 / vite proxy 一致。

