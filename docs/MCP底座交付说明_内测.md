# MCP 底座交付说明（MVP 内测）

> **受众**：@szbenyx（后端 / MCP Owner）、内测同学、Jason（前端联调）  
> **分支**：`refactor/framework-v2`  
> **交付基线**：`6bcba5a`（含 `fe58f56` P0 consent enforce + MCP 启动兼容）  
> **日期**：2026-07-02  
> **定位**：Python FastMCP **临时 Sidecar**，内测验证用；正式方案见 `docs/mcp-mvp-strategy.md`（Rust zervi）

---

## 1. 交付结论

| 项 | 状态 |
|----|------|
| MCP Sidecar 多工具（含征信聚合+细分） | ✅ 可交付 |
| JWT 认证 | ✅ |
| Health 探测 | ✅ |
| `parse_resume` Consent | ✅（`resume_upload`） |
| 自动化烟雾脚本 | ✅ `scripts/verify-p0-local.sh` |
| MCP 单元测试 | ❌ 内测阶段不做（Rust 阶段补） |

**结论：MVP 内测前 MCP 底座可正式交付。** 与 REST 主后端（`:5200`）并行运行，不替代 Flask API。

---

## 2. 架构一览

```text
┌─────────────────┐     JWT (looma_token)      ┌──────────────────────────┐
│  Web / 小程序    │ ─────────────────────────► │ Flask REST  :5200        │
│  SaaS / PlanetX │                            │ Compliance + 闭环 API     │
└────────┬────────┘                            └──────────────────────────┘
         │
         │  MCP Client（Cursor / 内测脚本）
         ▼
┌──────────────────────────┐
│ MCP Sidecar  :8999 (SSE) │  ← 一个 Looma MCP + 多工具
│  rag_query / match_jobs  │
│  parse_resume (+consent) │
│  credit_check（聚合）    │
│  credit_company/risk/legal│  ← 少量细分；不 1:1 镜像 QCC 九服
└───────────┬──────────────┘
            │ sys.path import backend/src
            ▼
     ChromaDB / LLM / Pipeline（与 REST 共用逻辑）
```

**关键文件**

| 文件 | 说明 |
|------|------|
| `backend/mcp-servers/server.py` | Sidecar 入口，3 工具 + `health://status` |
| `backend/mcp-servers/mcp_auth.py` | 独立 JWT 校验（无 Flask 依赖） |
| `backend/mcp-servers/pyproject.toml` | Sidecar 依赖声明 |
| `scripts/verify-p0-local.sh` | P0 烟雾（含 MCP 端口检测） |
| `docs/mcp-mvp-strategy.md` | 两阶段路线与 checklist |

---

## 3. 端口与环境

| 服务 | 默认地址 | 环境变量 |
|------|----------|----------|
| Flask 主后端 | `http://localhost:5200` | `PORT`（dev.sh） |
| MCP Sidecar | `http://127.0.0.1:8999` | `MCP_HOST`、`MCP_PORT` |
| MCP SSE 路径 | `/sse` | — |
| MCP Resource | `health://status` | MCP 客户端读取 |

**必须与主后端一致的环境变量**（Sidecar 启动前加载 `backend/.env`）：

| 变量 | 说明 |
|------|------|
| `JWT_SECRET` | 与 Flask 相同，否则 token 校验失败 |
| `JWT_ALGORITHM` | 默认 `HS256` |
| `DATABASE_PATH` | Consent / DB 用户校验（默认 `backend/data/looma.db`） |
| `JWT_EXPIRY_HOURS` | 默认 24h |

> 生产/内测服务器务必设置 **≥32 字符** 的 `JWT_SECRET`，勿用代码默认值。

---

## 4. 本地启动（三终端）

### 前置条件

- macOS / Linux，**Python 3.10+**（backend venv 推荐 3.12）
- 已克隆 `refactor/framework-v2` 并 `git pull`
- **不要用裸命令 `python`**（macOS 常不存在）；用 `python3` 或 venv 路径

**首次安装 Sidecar 依赖**（在 backend venv 内，只需一次）：

```bash
cd ~/Projects/looma-zervi/backend
source venv/bin/activate
pip install 'fastmcp>=2.0,<3.0'
```

若 venv 不存在或曾为 Python 3.9：

```bash
cd ~/Projects/looma-zervi/backend
rm -rf venv && bash dev.sh   # 会自动重建 venv 并装主依赖
source venv/bin/activate
pip install 'fastmcp>=2.0,<3.0'
```

### 终端 1 — Flask 主后端

```bash
cd ~/Projects/looma-zervi/backend
bash dev.sh
# → http://localhost:5200/health 应返回 {"status":"ok",...}
```

### 终端 2 — MCP Sidecar

```bash
cd ~/Projects/looma-zervi/backend/mcp-servers
../venv/bin/python3 server.py
```

成功日志示例：

```text
INFO:looma.mcp:Looma MCP Sidecar on 127.0.0.1:8999 (SSE /sse)
INFO:     Uvicorn running on http://127.0.0.1:8999
```

快速探测：

```bash
nc -z 127.0.0.1 8999 && echo "MCP OK"
```

### 终端 3 — P0 烟雾验收

```bash
cd ~/Projects/looma-zervi
bash scripts/verify-p0-local.sh
```

期望最后一行：

```text
✅ P0 本地烟雾测试通过 (API: http://localhost:5200)
```

步骤 7 应显示：

```text
MCP port 127.0.0.1:8999 reachable (SSE /sse)
```

---

## 5. MCP 工具说明

所有工具均要求传入 **`token`**（Looma JWT 字符串）。可选 **`user_id`** 与 token 的 `sub` 交叉校验。

| 工具 | 主要参数 | JWT | Consent | 说明 |
|------|----------|-----|---------|------|
| `rag_query` | `question`, `n_results=3` | ✅ | — | RAG 问答 |
| `match_jobs` | `resume_text`, `top_k=10` | ✅ | — | 简历 × 职位匹配 |
| `parse_resume` | `resume_text` | ✅ | **`resume_upload`** | 简历结构化；无 consent 返回 `consent_required` |

**获取 token 示例**（内测）：

```bash
curl -s -X POST http://localhost:5200/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"mcp-test@example.com","password":"testpass123","name":"MCP"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
```

**grant consent 后再调 `parse_resume`**：

```bash
curl -s -X POST http://localhost:5200/v1/compliance/consent/grant \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scope":"resume_upload"}'
```

**失败响应格式**（MCP 工具内，非 HTTP 401）：

```json
{"error": "auth_error", "message": "..."}
{"error": "consent_required", "message": "Consent required: resume_upload (...)"}
```

---

## 6. 安全与合规边界

| 能力 | MCP Sidecar | Flask REST |
|------|-------------|------------|
| JWT 验签 + exp | ✅ `mcp_auth.py` | ✅ `@require_auth` |
| DB 用户存在性 | 可选 `require_db_user`（默认未全开） | ✅ `@require_auth` 查 DB |
| Consent | `parse_resume`→jobseeker；`credit_*`→credit_query | credit / resume / ask / jobs 等 |
| Token 吊销 | ❌ 无 blacklist | ❌ 同上 |

内测策略：**一个 SSE 入口 + 多工具**；征信为聚合 `credit_check` + 少量细分（company/risk/legal），不 1:1 镜像企查查九服。敏感能力仍走 JWT + Consent。

---

## 7. 已知限制（交付边界）

1. **临时方案**：Python Sidecar，内测后由 Rust `zervi` 接管（见 `mcp-mvp-strategy.md`）。
2. **工具集**：核心三件套 + 征信四工具；不扩 narrative / poetry / mbti 等。
3. **认证传参**：MVP 用工具参数 `token`；Rust 阶段改为 `Authorization: Bearer` Header。
4. **内部实现**：Sidecar 通过 `sys.path` 直接 import `backend/src`，非 HTTP 调 REST；QCC 经 `qcc_client`。
5. **无 MCP 单测**：依赖 `verify-p0-local.sh` 烟雾。
6. **`fastmcp` 未写入主 `requirements.txt`**：需手动 `pip install` 或后续 CI 补装。
7. **端口占用**：`:8999` 被占用时见下方排障。

---

## 8. 验收命令清单

内测同学 / szbenyx 可按序执行，**全部通过即 MCP 底座验收合格**。

```bash
# 0. 代码基线
cd ~/Projects/looma-zervi
git checkout refactor/framework-v2
git pull github refactor/framework-v2   # 或 origin，两端应同为 6bcba5a+

# 1. 后端 pytest（可选但推荐）
cd backend && source venv/bin/activate
pytest tests/test_compliance.py tests/test_closed_loop.py -q
# 期望：23 passed

# 2. 启动 backend + MCP（两个终端，见第 4 节）

# 3. P0 烟雾（含 MCP 步骤 7）
cd ~/Projects/looma-zervi
bash scripts/verify-p0-local.sh

# 4. MCP 端口独立确认
nc -z 127.0.0.1 8999 && echo "MCP OK"
```

**签字表（内测前）**

| 检查项 | 执行人 | 日期 | 结果 |
|--------|--------|------|------|
| `verify-p0-local.sh` 全绿 | | | ☐ |
| MCP `:8999` 可启动 | | | ☐ |
| `JWT_SECRET` 非默认值（部署环境） | | | ☐ |
| 已读 `mcp-mvp-strategy.md` 限制 | | | ☐ |

---

## 9. 常见问题

### `python: command not found`

使用：

```bash
../venv/bin/python3 server.py
```

### `[errno 48] address already in use`（8999）

```bash
lsof -nP -iTCP:8999 -sTCP:LISTEN
kill <PID>
```

或换端口：

```bash
MCP_PORT=9000 ../venv/bin/python3 server.py
```

### 步骤 7 曾显示 MCP 不可达，但 `nc` 成功

旧脚本用 `curl /sse` 会因 SSE 长连接超时误报；**`6bcba5a` 已改为 `nc -z`**，请 pull 最新代码。

### MCP token 校验失败

- 确认 Sidecar 与 Flask 使用同一 `JWT_SECRET`（`backend/.env`）
- 确认 token 未过期（默认 24h）
- 跨环境 token（线上 vs 本地）不可混用

### `parse_resume` 返回 `consent_required`

先调 `POST /v1/compliance/consent/grant` scope=`resume_upload`，或在前端完成 Consent 弹窗。

---

## 10. 相关文档

| 文档 | 内容 |
|------|------|
| [mcp-mvp-strategy.md](./mcp-mvp-strategy.md) | 两阶段路线、Rust 迁移约定 |
| [JWT认证链路排查与修复说明_szbenyx.md](./JWT认证链路排查与修复说明_szbenyx.md) | REST JWT / ApiClient / tier 同步 |
| [技术架构审议报告_合规与数据平台.md](./技术架构审议报告_合规与数据平台.md) | L1 Compliance Gate 与 P0/P1 规划 |

---

## 11. 后续（非本次交付）

| 项 | Owner | 阶段 |
|----|-------|------|
| Jason 四端 Consent UI 人工点验 | Jason | P0 产品签字 |
| `job_match` / `resume_parse` 前端 ensureConsent | Jason | P0 |
| MCP `rag_query` / `match_jobs` consent（若需要） | Joint | P1 评估 |
| Rust zervi 原生 MCP | szbenyx | 内测后 |
| `fastmcp` 写入 dev.sh / CI | Joint | 运维优化 |

---

**交付确认**：MCP Sidecar MVP 底座已于 `refactor/framework-v2` @ `6bcba5a` 通过本地 P0 烟雾验收，可进入 MVP 内测。  
如有问题请在 Gitee/GitHub Issue 或群内 @Jason / @szbenyx。
