# RFC: Supabase 统一认证（THOMAS 生态身份层）

> **状态：** In Progress（后端验证层/微信路径/前端双模式已实施，存量迁移待实测） · **作者：** Jason · **Review：** szbenyx  
> **日期：** 2026-09-01  
> **依据：** THOMAS 生态闭环定位 · `CURRENT_SYSTEM_ARCHITECTURE.md` · `auth_routes.py` 现状 · 决策（2026-09-01 对齐）
> **跨仓审阅：** 本文档决策的「共享同一 Supabase = 统一身份层」记录及待审阅问题见 `THOMAS/docs/SUPABASE_UNIFIED_IDENTITY.md`（window 侧优先看该记录）

---

## 1. 背景

- looma 现为**自建认证**：bcrypt 密码 + 自签 JWT（`issuer=looma` / `JWT_SECRET`），Web / 小程序 / 华为多端已统一签发 looma JWT。
- `cloudbase/` 为**休眠腾讯云遗留**：仅一个 pass-through 云函数 `wechat-login`（域名占位 `your-domain.com`），小程序代码不依赖它，README 已声明弃用。
- Supabase **完全未接入**：无 SDK / 配置；`/v1/auth/bridge` 为 501 占位。
- THOMAS 生态（`looma-zervi` / `demo-ppi-mvp` / `gfcc_kernel`，经信号桥 `email_hash` 跨端关联）需要一个**生态级统一身份层**——Supabase Auth 正承担该角色。

## 2. 目标

1. **Supabase Auth 成为唯一身份源（IdP）**：Web、微信小程序、后续 H5 共享同一账号体系。
2. **looma 回归业务后端**：不再签发认证 token，改为**验证 Supabase JWT** 并解析本地用户。
3. 微信小程序通过 **Supabase Admin API + 自定义 JWT** 接入统一身份。
4. **废弃 `cloudbase/`**（腾讯云函数路径整体移除）。

## 3. 架构决策（ADR）

| # | 决策 | 说明 |
|---|------|------|
| D1 | Supabase Auth = 唯一 IdP | looma 停止签发认证 token；email/password 与 OAuth 由 Supabase 托管 |
| D2 | Token = Supabase JWT（JWKS/ES256 验证） | 已验证 `auth/v1/.well-known/jwks.json` 返回 **ES256（P-256）** 密钥 → looma 用 PyJWT `PyJWKClient` 验证（依赖已有：PyJWT+cryptography）；微信 custom token 用 JWT secret（HS256）签发，网关接受性实施时验证 |
| D3 | 本地映射 `users.supabase_uid` | `sub`（Supabase user UUID）→ looma user；UNIQUE 索引 |
| D4 | 业务属性留 looma | `tier` / `role` / 游戏进度等**不迁 Supabase**，仍在 looma SQLite，与 token claims 解耦 |
| D5 | 微信走 Admin API + 自定义 JWT | Supabase 无原生微信 provider，用 service_role upsert 用户后签发自定义 JWT（claims 见 §6） |
| D6 | 过渡期双 token 兼容 | `require_auth` 先验 Supabase JWT，回退 looma JWT；切换完成后移除旧验证路径 |

## 4. 认证流程

### 4.1 Web：邮箱/密码
```
supabase.auth.signInWithPassword({ email, password })
  → session.access_token（Supabase JWT）
  → 请求 looma: Authorization: Bearer <supabase_token>
  → looma 验证 JWT → 按 supabase_uid 解析本地用户 → 响应业务数据
```

### 4.2 Web：Google OAuth（海外）
```
supabase.auth.signInWithOAuth({ provider: 'google' })
  → 回调后取 session.access_token → 同上调 looma
```
（存量 looma `/v1/auth/google` 路径在切换后废弃。）

### 4.3 微信小程序
```
wx.login() → code
  → POST looma /v1/auth/wechat { code }
  → looma code2session(openid)
  → Supabase Admin API upsert 用户（user_metadata.wechat_openid，email_confirm=true）
  → looma 用 SUPABASE_JWT_SECRET 签发自定义 JWT（§6）返回
  → 小程序后续请求带该 JWT
```

### 4.4 华为（HarmonyOS）
与微信同路径：`/v1/auth/huawei` 保留换取授权码 → Admin API upsert → 自定义 JWT。

## 5. 后端改造清单

| 文件 | 改动 |
|------|------|
| `backend/src/config.py` | 新增 `SUPABASE_JWT_SECRET` / `SUPABASE_PROJECT_REF` / `SUPABASE_SERVICE_ROLE_KEY`（`.env`，示例入 `.env.example`） |
| `backend/src/api/auth/jwt_handler.py` | 新增 `verify_supabase_token()`：`PyJWKClient(auth/v1/.well-known/jwks.json)` + ES256，校验 `aud=authenticated` / `exp` / `iss` |
| `backend/src/api/auth/decorators.py` | `require_auth` / `optional_auth` 支持双 token（D6） |
| `backend/src/db/manager.py` | `users.supabase_uid TEXT UNIQUE` 列 + `get_user_by_supabase_uid()` / `upsert_by_supabase()`（首次按 email 自动绑定，覆盖存量用户） |
| `backend/src/api/routes/auth_routes.py` | `/v1/auth/wechat`、`/v1/auth/huawei` 改走 Admin API + 自定义 JWT；`/v1/auth/bridge` 决定落地或废弃 |
| `backend/contracts/` | 更新 `identity.v1.json`（新增 `provider: supabase`）与 auth 契约 |

## 6. 自定义 JWT claims（微信/华为）

```json
{
  "iss": "https://<project-ref>.supabase.co/auth/v1",
  "sub": "<supabase-user-uuid>",
  "aud": "authenticated",
  "exp": 1760000000,
  "iat": 1759913600,
  "email": "<openid>@wechat.thomas.local",
  "role": "authenticated",
  "aal": "aal1",
  "app_metadata": { "provider": "wechat", "providers": ["wechat"] },
  "user_metadata": { "wechat_openid": "<openid>" }
}
```

## 7. 前端改造清单

| 包 | 改动 |
|----|------|
| `packages/shared-core` | auth 类型支持 Supabase session；封装 `createSupabaseClient()`（`VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY`） |
| `packages/saas`（T空间） | `authStore.ts` 改走 supabase-js；`login`/`register` 换成 `signInWithPassword` |
| `packages/planetx`（C端） | `planetxAuthStore.ts` 改走 supabase-js；Google 改 `signInWithOAuth` |
| `packages/miniprogram` | `utils/api.ts` 登录返回改为 Supabase JWT；token 存取不变（`LOOMA_TOKEN_KEY` 兼容） |

## 8. `cloudbase/` 处理

- [x] **已执行（2026-09）**：`cloudbase/` 目录已整体删除；README / MANIFESTO / DUAL_REPO_WORK_GUIDE / TENCENT_CLOUD_COMMERCE / INTERNAL_TEST_READINESS 均已同步更新。

## 9. 存量 looma 用户迁移（待调研后定）

| 方案 | 说明 | 备注 |
|------|------|------|
| A：首次登录自动绑定（推荐） | Supabase 登录后 looma 按 email 匹配写入 `supabase_uid` | 无需停机，bcrypt 密码留在 looma 但不复验 |
| B：Admin API 批量导入 | `createUser` 支持传 bcrypt `password_hash`（`$2a$...`），可无损迁移 | 依赖 Supabase 版本能力，需调研 |
| C：内测期手动 | 用户量小，先跑通新流程 | 与 A 可并行 |

> 决策时机：拿到 Supabase 项目信息后，验证 Admin API 的 `password_hash` 支持情况再定。

## 10. 待办 / 阻塞

- [x] Supabase 项目已提供：Genzers / demoppi · URL `https://ftsnrqwynofsxdvoxnsw.supabase.co` · publishable key（`sb_publishable_***`，已通过 `auth/health`=200 验证；完整值仅存于 `backend/.env`，不入库）
- [x] 调研 D2：JWKS 端点返回 **ES256** → 验证走 JWKS；custom token 用 JWT secret（HS256）
- [x] **secret key 已通过 CLI 获取**（`supabase projects api-keys --reveal`，已验证 Admin API `/auth/v1/admin/users`=200）：`sb_secret_***`（+ legacy service_role JWT，完整值仅存于 `backend/.env`，不入库）
- [x] **JWT secret 已提供**（2026-09-01）
- [x] **实施（后端）**：`config.py` Supabase 配置 · `jwt_handler.py` `verify_supabase_token()`（JWKS/ES256 + custom HS256）与 `sign_supabase_custom_token()` · `decorators.py` `require_auth`/`optional_auth` 双 token · `supabase_auth.py` Admin API upsert · `db/manager.py` `supabase_uid` 列 + `get_or_create_user_by_supabase`（存量 email 自动绑定）· `/v1/auth/wechat` 改造 · 测试 `test_supabase_auth.py`（8 项，全量 247 passed）
- [x] **实施（前端）**：shared-core `supabase.ts`（独立子路径，不污染小程序产物）· saas/planetx `authStore` 双模式登录/注册/登出 · `.env.example` 更新
- [x] **端到端实测（2026-09-01）**：真实 demoppi 项目凭据写入 `backend/.env`，16 项 e2e 全过：
  - A 路径：Admin API 创建用户 → GoTrue password 登录（publishable key）→ ES256 token 被 JWKS 验证 → looma profile 首次创建/二次复用 → 错误密码被拒
  - B 路径：`/v1/auth/wechat`（dev code）→ Admin upsert 微信用户 → custom HS256 token → profile 映射独立用户 → 二次登录复用
  - **修复 bug**：实测该 GoTrue 实例 `?email=`/`?search=`/`?filter=` 查询参数均不可靠（email 参数被忽略返回全部、filter 返回空），曾致微信 upsert 错绑/422；`admin_get_user_by_email` 改为全量分页拉取 + 本地精确匹配
  - **修复 bug**：`SCHEMA_SQL` 的 `idx_users_supabase_uid` 在旧库（无 supabase_uid 列）启动时崩溃，索引改由 init_schema 迁移块创建
- [ ] 调研/实测：`password_hash` bcrypt 存量导入（§9-B）
- [ ] 决策：`/v1/auth/bridge` 语义（保留为 Supabase→looma 交换，或直接废弃）

## 11. 回归与风险

- 现有 `tests/test_auth.py`（looma JWT 路径）在过渡期（D6）必须全绿。
- 信号桥 `email_hash` 依赖 `users.email`，不因认证源迁移受影响（T0 已对齐）。
- `tier` 判定以本地 DB 为准，token claims 不再承载业务权限，避免 Supabase JWT 过期导致降权。
- 小程序自定义 JWT 的 `email` 为占位值，需确保不与真实邮箱冲突（`@wechat.thomas.local` 后缀）。
