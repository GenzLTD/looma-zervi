# Looma-Zervi Mac 复现指南

> 记录日期：2026-06-17
> 目的：在 Mac 上完整复现 Windows Surface 上的 Looma-Zervi 开发环境

---

## 1. 前置条件

| 依赖 | 版本 | 安装方式 |
|------|------|---------|
| Python | 3.13+ | `brew install python` |
| PostgreSQL + pgvector | 17 | Docker（见下方） |
| Ollama | 最新 | `brew install ollama` |
| Git | 最新 | `brew install git` |

---

## 2. 克隆项目

```bash
git clone https://github.com/szpeter2026/looma-zervi.git
cd looma-zervi
git checkout main   # 确认在 main 分支，应包含最新合并
```

验证：
```bash
git log --oneline -5
# 应看到 merge: Supabase auth unification + deployment docs into main
```

---

## 3. 启动 pgvector 容器

```bash
docker compose up -d
```

验证连接：
```bash
python scripts/smoke_pgvector.py
```

---

## 4. 配置 `.env`

从 `.env.example` 复制并修改：

```bash
cp .env.example .env
```

**必须修改的字段：**

```env
# ---- 数据库 ----
PG_HOST=127.0.0.1
PG_PORT=5433          # docker-compose 里映射的端口
PG_USER=postgres
PG_PASSWORD=postgres
PG_DATABASE=looma

# ---- Ollama ----
OLLAMA_HOST=http://127.0.0.1:11434
EMBED_MODEL=nomic-embed-text:latest
LLM_MODEL=olama/qwen2.5-coder:1.5b

# ---- 服务 ----
LOOMA_HOST=127.0.0.1
LOOMA_PORT=8010

# ---- 认证（Supabase 接入）----
AUTH_STUB=true
SUPABASE_URL=https://acozjhpjidrucqonpkey.supabase.co
SUPABASE_JWT_SECRET=<从 Supabase Dashboard 取，勿写入本文件或任何入库文件>

# ---- 诗词库（可选，pgvector 不可用时回退）----
# Mac 上路径不同，如果没有本地 Chroma 可以注释掉
# POETRY_CHROMA_PATH=...
```

> **注意**：`SUPABASE_JWT_SECRET` 是 Supabase 项目的 JWT Secret，
> 路径：Supabase Dashboard → Project Settings → API → JWT Secret
> **本仓库只保留占位符**，真值写进本地 `.env`（已被 `.gitignore` 覆盖），不要贴进文档或脚本。

---

## 5. 安装 Python 依赖

```bash
python -m venv .venv
source .venv/bin/activate   # Mac 用 bin/activate，Windows 用 .venv\Scripts\activate
pip install -r requirements.txt
```

验证：
```bash
python -c "import fastapi, llama_index, litellm; print('✅ 依赖正常')"
```

---

## 6. 初始化数据库

```bash
# SQLite 元数据库会自动创建（data/looma.db）
# pgvector 表会在首次启动时自动初始化（rag_engine.py 的 lifespan）
```

手动验证 pgvector schema：
```bash
python -c "
import psycopg
conn = psycopg.connect('postgresql://postgres:postgres@127.0.0.1:5433/looma')
cur = conn.cursor()
cur.execute(\"\"\"SELECT table_name FROM information_schema.tables
              WHERE table_schema='looma'\"\"\")
print(cur.fetchall())
"
```

---

## 7. 启动 Looma 服务

```bash
source .venv/bin/activate
uvicorn src.api.app:app --reload --port 8010 --host 127.0.0.1
```

**正常启动应看到：**
```
INFO: Uvicorn running on http://127.0.0.1:8010
INFO: Seeds: knowledge base initialized
```

---

## 8. 认证链路测试（Supabase JWT）

### 8.1 生成测试 JWT

```bash
python scripts/gen_test_jwt.py
```

输出示例：
```json
{
  "token": "eyJhbGci...",
  "user_id": "7d521f7f-a8ba-4bc2-939b-f6cf918dc208",
  "email": "zervi@genz.ltd",
  "tier": "pro",
  "expires_in": 3600
}
```

> **注意**：`gen_test_jwt.py` 用 `SUPABASE_JWT_SECRET` 本地签发 JWT，
> 仅用于开发测试。生产环境应从 Supabase Auth 获取真实 JWT。

### 8.2 验证 JWT 验签

```bash
python scripts/smoke_auth_supabase.py
```

预期输出：
```
[PASS] 验签通过
     sub  = 7d521f7f-a8ba-4bc2-939b-f6cf918dc208
     tier = pro
[PASS] 错误 secret 正确拒绝
[OK] 长度 36 >= 32，格式合理
```

### 8.3 用 curl 测试认证接口

```bash
# 将上一步的 token 值替换 <JWT>
TOKEN="<从 gen_test_jwt.py 输出复制>"

# 测试 /v1/health（无需认证）
curl http://127.0.0.1:8010/v1/health | python -m json.tool

# 测试 /v1/ask（需要认证）
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8010/v1/ask \
  -d '{"question": "什么是RAG"}' | python -m json.tool
```

---

## 9. Stub 模式兜底测试

即使没有 Supabase，Stub 模式也应正常工作：

```bash
# 用任意 token-xxx 格式，走 Stub 分支
curl -X POST \
  -H "Authorization: Bearer token-stub-test" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8010/v1/ask \
  -d '{"question": "测试 Stub 模式"}' | python -m json.tool
```

预期：`user_id = stub-token-stub-test`，`tier = free`（或 enterprise，如果从 DB 查到）

---

## 10. 端到端 RAG 全路径验证

完整链路：`Token → Auth → Quota → RAG Engine → LLM → 返回`

```bash
# 1. 用有效 JWT 提问
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8010/v1/ask \
  -d '{"question": "如何提升简历通过率？"}' 

# 2. 检查响应里是否包含：
#    - answer（非空）
#    - sources（引用文档，非空列表）
#    - timing_ms（耗时）
```

---

## 11. 常见问题

### Q: `SUPABASE_JWT_SECRET` 验签失败
**A**: 确认拿的是 **JWT Secret**（一长串 base64 或 UUID 格式），
不是 "anon/public key" 或 "service_role key"。

路径：Supabase Dashboard → Settings → API → JWT Secret

### Q: Mac 上 `PG_PORT` 应该是 5433 还是 5432？
**A**: 看 `docker-compose.yml` 里的端口映射：
```yaml
ports:
  - "5433:5432"   # 宿主机 5433 → 容器 5432
```
所以用 `5433`。

### Q: Ollama 模型未安装
**A**:
```bash
ollama pull nomic-embed-text:latest
ollama pull qwen2.5-coder:1.5b
```

### Q: 想用 DeepSeek 替代本地 LLM
**A**: 在 `.env.local` 里配置（不要提交到 git）：
```env
LLM_PROVIDER_ORDER=deepseek,ollama
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_MODEL=deepseek/deepseek-v4-pro
```

---

## 12. 目录结构速查

```
looma-zervi/
├── .env                  ← 本地配置（不提交）
├── .env.example          ← 模板（提交）
├── .env.local            ← 密钥覆盖（不提交）
├── docker-compose.yml    ← pgvector 容器
├── requirements.txt      ← Python 依赖
├── src/
│   ├── api/auth.py      ← 认证模块（Supabase JWT + Stub）
│   ├── api/quota.py    ← 配额控制
│   ├── api/routes/ask.py← /v1/ask 主入口
│   ├── core/config.py   ← 配置加载
│   └── retrieval/       ← RAG 引擎
├── scripts/
│   ├── gen_test_jwt.py          ← 生成测试 JWT
│   ├── smoke_auth_supabase.py  ← 认证烟测
│   └── smoke_pgvector.py       ← pgvector 连接测试
└── data/looma.db       ← SQLite 元数据（首次自动创建）
```

---

## 13. 关键配置对照表

| 配置项 | Windows 值 | Mac 值 | 说明 |
|--------|-------------|---------|------|
| `PG_PORT` | `5433` | `5433` | docker-compose 映射端口 |
| `PG_PASSWORD` | `postgres` | `postgres` | 容器默认密码 |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | `http://127.0.0.1:11434` | 相同 |
| `POETRY_CHROMA_PATH` | `D:/surface-zervi/...` | `~/surface-zervi/...` | Mac 路径不同，可注释 |
| `SUPABASE_URL` | 相同 | 相同 | 不依赖环境 |
| `SUPABASE_JWT_SECRET` | 相同 | 相同 | 不依赖环境 |

---

*最后更新：2026-06-17 by 嘟嘟*
