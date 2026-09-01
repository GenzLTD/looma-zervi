# Looma-Zervi

> Server-Terminal architecture: Looma Python backend + Zervi frontend clients
> Dual brand: PlanetX (C-end job seekers) + T-space (B-end HR enterprises)

## Architecture overview

```
                    ┌─────────────────────────┐
  WeChat MiniApp ──→│  Supabase Auth (统一身份) │── custom JWT ──→
                    │  THOMAS 生态 IdP          │
                    └─────────────────────────┘               ┌──────────────────┐
                                                              │  Looma Backend    │
  Web Browser ────────── HTTPS ─────────────────────────────→ │  Flask + JWT      │
                                                              │  ChromaDB + SQLite│
                                                              │  DeepSeek API     │
                                                              └──────┬───────────┘
                                                              │
                                          ┌───────────────────┼───────────────┐
                                          │                   │               │
                                    ┌─────┴─────┐    ┌────────┴──────┐  ┌────┴─────┐
                                    │ ChromaDB  │    │    SQLite     │  │ DeepSeek │
                                    │ (vectors) │    │ (users/games) │  │   API    │
                                    └───────────┘    └───────────────┘  └──────────┘
```

## Project structure

```
looma-zervi/
├── backend/          # Looma Python backend (Flask + ChromaDB + SQLite)
├── frontend/         # Frontend monorepo (pnpm workspace)
│   └── packages/
│       ├── shared-core/   # Shared types, API client, constants (dual-review)
│       ├── planetx/       # PlanetX C-end brand (Jason owns)
│       ├── saas/          # T-space B-end brand (szbenyx owns)
│       └── miniprogram/   # WeChat miniprogram shell (Jason owns)
├── docker/           # Docker + nginx deployment
└── docs/             # Architecture docs
    ├── DUAL_REPO_WORK_GUIDE.md   # 双仓协作工作指引（与 szbolent-portal 同文同步）
    ├── PROJECTS_DIRECTORY_AUDIT.md   # Projects 目录勘查记录（暂留、未删）
    └── TENCENT_CLOUD_COMMERCE.md   # 腾讯云备案 / 支付 / P0–P2
```

## Auth flow（THOMAS 生态统一认证 — Supabase，RFC docs/rfc/supabase-unified-auth-v1.md）

| Entry point | Flow | Auth endpoint |
|---|---|---|
| Web browser | Supabase email/password → Supabase JWT（后端 JWKS 验证） | supabase-js（`/v1/auth/login` 旧路径保留兼容） |
| Web register | Supabase signUp（邮箱确认）→ Supabase JWT | supabase-js |
| WeChat MiniApp | wx.login → Supabase Admin API upsert → custom JWT | POST /v1/auth/wechat |
| Cross-platform bind | wechat_openid ↔ email ↔ supabase_uid | POST /v1/auth/bind |

> 未配置 `SUPABASE_URL` 的环境自动回退旧 looma JWT 路径（require_auth 双 token 兼容）。

## Quick start

### 一键启动完整MVP联调环境
```bash
# 启动所有服务（后端、前端、小程序环境）
./scripts/start-full-mvp.sh

# 或使用验证脚本检查环境
./scripts/verify-mvp-setup.sh
```

### 分步启动

#### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # edit config
python run.py
```

#### Frontend Web
```bash
cd frontend
pnpm install
pnpm --filter @looma/planetx dev   # PlanetX on :5173
pnpm --filter @looma/saas dev      # T-space on :5174
```

#### Miniprogram Local Debugging
```bash
# 小程序本地联调
./scripts/start-miniprogram-local.sh
```

#### 验证测试
```bash
# API合规测试
./scripts/verify-p0-local.sh

# 完整本地彩排
./scripts/rehearsal-local.sh
```

### 服务访问地址
- **后端API**: http://localhost:5200
- **PlanetX (C端)**: http://localhost:5173
- **T-space (B端)**: http://localhost:5174
- **小程序**: 微信开发者工具导入 `frontend/packages/miniprogram/`
- **详细指南**: [docs/LOCAL_MVP_DEBUGGING.md](docs/LOCAL_MVP_DEBUGGING.md)

## Ownership matrix

| Package / Route group | Owner |
|---|---|
| packages/planetx + /v1/game/* | Jason |
| packages/saas + /v1/enterprise/* | szbenyx |
| packages/shared-core + /v1/auth/* | Joint (dual review) |
| packages/miniprogram | Jason |
| /v1/jobs/*, /v1/ask, /v1/resume/*, /v1/reports/* | szbenyx |
| /v1/referral/* | Jason |

## Tech stack

- **Backend**: Python 3.10+, Flask, SQLite (WAL), ChromaDB, DeepSeek API
- **Frontend**: React 18, TypeScript, Vite, Zustand, Tailwind CSS
- **Miniprogram**: WeChat native（认证走 Supabase Admin API + custom JWT）
- **Deploy**: Docker + nginx on Aliyun ECS
