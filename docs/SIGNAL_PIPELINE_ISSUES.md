# 信号管道缺口 — 可执行 Issue 清单（对齐官方指南）

> **权威分解**：`../../docs/ECOSYSTEM_SIGNAL_ADAPTER_GUIDE.md` §5（THOMAS 根 `docs/`）  
> **审查结论（2026-08-13）**：`mission-complete` / `match` 已有；信号桥管道未接。  
> **开工修订（2026-08-13）**：加 **T0**（email hash 对齐）；T1 幂等用 **SQLite UNIQUE**（**不用 Redis**——主后端无 Redis，指南 §9.1 与 §5.2「DB UNIQUE」矛盾，以 SQLite 为准）。合计 ≈ **5 人天**。  
> **本文件**：PlanetX（looma-zervi）侧 Issue（T0 / T1 / T3）+ Epic。  
> DemoPPI：`../../demo-ppi-mvp/docs/SIGNAL_PIPELINE_ISSUES.md`（T0 本仓部分 / T2 / T4）。

## Epic

**标题**：`[Epic] Game 信号桥：ingest + personality_beacon egress`

**标签**：`epic` · `signal-adapter` · `game` · `P0`

```markdown
## 子任务
| ID | 仓 | 任务 | 估时 |
|----|-----|------|------|
| **T0** | **双边** | **email hash 对齐（硬前置）** | **0.5d** |
| T1 | PlanetX | `/v1/game/signal-ingest`（HMAC + **SQLite 幂等**） | 1.0d |
| T2 | DemoPPI | consensus_match egress | 1.0d |
| T3 | PlanetX | personality_beacon egress | 0.5d |
| T4 | DemoPPI | personality_beacon ingress | 0.5d |
| T5 | 双边 | 本地 mock 自测 | 1.0d |
| T6 | 双边 | 联调 + env | 0.5d |

**合计 ≈ 5 人天**

## 建议顺序
**T0 → T1 → T2 → T3 → T4 → T5 → T6**  
共享 `SIGNAL_BRIDGE_SECRET`；先本地 mock 再联调。

种子期：`consensus_match` 入站若用户有进行中的 `mission_id=match` → 调现有 mission-complete；否则幂等忽略。
不做全量 `match/acknowledge` 阶段二（指南 §六）；契约 B2 属后续升级。
不做 Redis 去重。
```

---

## T0 — PlanetX 侧：email hash 对齐（硬前置）

**仓**：`looma-zervi`（THOMAS）· 与 DemoPPI T0 成对  
**标签**：`planetx` · `signal-adapter` · `P0` · `blocker`  
**估时**：约 0.25d（双边合计 0.5d）  
**阻塞**：T1、T3

```markdown
## 问题
指南 §4.5 假设用 email SHA-256 跨端关联，但真实代码：
- `users.email` 可空（小程序-only）
- 仅有 `get_user_by_email`（明文），无 hash→user

T1 收到 `user_email_hash` 后无法定位用户。

## 要做（本仓）
1. `users` 增加 `email_hash TEXT` + 索引 `idx_users_email_hash`
2. 迁移：对已有非空 `email` 回填 `sha256(email.lower().strip())` hex 小写
3. 注册 / 绑邮箱路径：写入 email 时同步写 `email_hash`
4. `get_user_by_email_hash(hash)`（T1/T3 使用）
5. 与 DemoPPI 对齐算法：`sha256(email.toLowerCase().trim())`；跨语言固定向量单测
6. email 为空：`email_hash` 保持 NULL；signal-ingest 找不到用户 → 200 + 日志（不 5xx）

## 验收
- [x] 有邮箱用户可被 hash 命中
- [x] 回填脚本/迁移可重复执行（幂等）
- [x] Node/Python 互验同一 hex
- [x] 小程序-only（无 email）不破坏现有登录

## 参考
- `backend/src/db/manager.py` SCHEMA `users.email`（nullable）
- `get_user_by_email` ~:798
- 指南 §4.5
```

---

## T1 — PlanetX：`POST /v1/game/signal-ingest`

**仓**：`looma-zervi`（THOMAS）  
**标签**：`planetx` · `signal-adapter` · `P0`  
**估时**：1.0d  
**依赖**：**T0**

```markdown
## 问题
`game_routes.py` / 路由表无外部 webhook 入站端点。

## 要做（指南 §5.2，幂等改为 SQLite）
1. 新增 `POST /v1/game/signal-ingest`（**不**走 `require_auth`；HMAC 替代用户 JWT）
2. Header `X-Signal-Signature`：`HMAC-SHA256(raw_body, SIGNAL_BRIDGE_SECRET)`；失败 401
3. **幂等（SQLite，禁用 Redis）**  
   新建表例如：
   ```sql
   CREATE TABLE IF NOT EXISTS signal_ingest (
       signal_type      TEXT NOT NULL,
       user_email_hash  TEXT NOT NULL,
       nonce            TEXT NOT NULL,
       payload_json     TEXT,
       created_at       TEXT DEFAULT (datetime('now')),
       PRIMARY KEY (signal_type, user_email_hash, nonce)
   );
   ```
   INSERT 冲突 → 200 `{ "status": "duplicate", "ignored": true }`，不重复发 XP  
   （指南 §5.2「用数据库 UNIQUE」为准；忽略 §9.1 Redis 建议——主服务无 Redis）
4. `consensus_match`：`get_user_by_email_hash` → 若有进行中 match mission → mission-complete 发 XP；否则日志 + 200
5. 限流建议：10 req/min per email_hash（可用内存滑动窗；勿为此引入 Redis）
6. 注册 blueprint；补测试（合法签 / 坏签 / 重复 nonce / 无用户）

## 验收
- [x] 路由存在；合法签落处理；坏签 401
- [x] 同 `(signal_type, user_email_hash, nonce)` 不重复发 XP
- [x] 无进行中 match mission / 无匹配用户时仍 200
- [x] 无 Redis 依赖

## 实现说明（2026-08-14 已完成并 curl 实测）
- **幂等**：SQLite `signal_ingest` 复合主键 `(signal_type, user_email_hash, nonce)`，重放返回 `200 { status:"ok", duplicate:true }`
- **match 种子期近似**：PlanetX 无「进行中 mission」状态表，「有进行中 match mission」≈「尚未完成过 `mission_id=match`」，不重复发 XP 由 `mission_completions` 的 `UNIQUE(user_id, mission_id)` 兜底；后续接真实「进行中」状态时替换此捷径
- 实测：合法签 `200 matched=true mission_completed=true xp_earned=50`；重放同 nonce `duplicate=true`；坏签 `401`

## 参考
- 指南 §5.2（UNIQUE 约束；参考代码中的 redis 勿照抄）
- `backend/src/api/routes/game_routes.py`（mission-complete / match）
- `backend/src/db/manager.py`（SQLite DatabaseManager）
```

---

## T3 — PlanetX：`personality_beacon` egress

**仓**：`looma-zervi`（THOMAS）  
**标签**：`planetx` · `signal-adapter` · `P0`  
**估时**：0.5d  
**依赖**：**T0**（发送方须有 `email_hash`）

```markdown
## 问题
人格测评完成后未向 DemoPPI 推送 beacon。

## 要做（指南 §5.4）
1. 在 `personality_type` 写入后触发 egress
2. Payload：`signal_type=personality_beacon`, `user_email_hash`, `data{personality_type, traits, score}`, `timestamp`, `nonce`
3. HMAC 签名 → `POST DEMOPPI_SIGNAL_INGEST_URL`（`/api/signal/ingest`）
4. best-effort：失败不阻塞测评响应；无 `email_hash` 时跳过并打日志

## 验收
- [x] 测评完成后 mock/真端点收到 beacon
- [x] 无明文 email；无 URL / 无 hash 时安全跳过

## 实现说明（2026-08-14 已完成）
- 触发点：`POST /v1/game/profile-sync`（`sync_personality`）在 `upsert_game_profile` 之后调用 `_send_personality_beacon`，best-effort（`urllib.request.urlopen` + try/except，失败只 `logger.warning`）
- `_send_personality_beacon(db, user_id, personality_type, personality_detail)`：no-op 守卫（无 `DEMOPPI_SIGNAL_INGEST_URL` / 无 `SIGNAL_BRIDGE_SECRET` / 用户无 `email_hash` → 跳过并打日志）
- 信封对齐指南 §4.4：`{ signal_type:"personality_beacon", user_email_hash, data{personality_type, traits, score}, timestamp, nonce }` + 头 `X-Signal-Signature`（HMAC-SHA256 over raw body，compact `separators=(",", ":")` 对齐 Node `JSON.stringify`）
- `traits`/`score` 种子期近似：从 `personality_detail` 解析（若其为含 `traits` 列表 / 数值 `score` 的 JSON 则透传，否则 `[]` / `None`）——PlanetX 无独立 traits/score 维度
- 单测：`tests/test_personality_beacon.py` 11/11（含端到端 profile-sync 触发 + mock urlopen 断言签名头 = HMAC(body, secret)、无明文 email）
- env：`DEMOPPI_SIGNAL_INGEST_URL=http://127.0.0.1:3000/api/signal/ingest`（PlanetX → DemoPPI，服务端专用）

## 参考
- 指南 §5.4
- `backend/src/api/routes/game_routes.py`（sync_personality / _send_personality_beacon）
```

---

## T5 / T6（PlanetX checklist）

### T6 联调 — ✅ 已验证（2026-08-14 真联调）

> **全量回归（2026-08-27）**：backend tests **142/142 通过**（信号桥 T0/T1/T3 专项 + 全部业务域），详见 [`FULL_REGRESSION_REPORT_20260827.md`](FULL_REGRESSION_REPORT_20260827.md)。

**验收证据（personality_beacon 四态 + matched 写库）**：
- 合法签名 beacon → DemoPPI `200 {"status":"ok","matched":true}`
- 同 nonce 重放 → `200 {"duplicate":true}`（DB 复合主键幂等生效）
- 坏签名 → `401 {"error":"unauthorized"}`
- matched:true → DemoPPI `profiles.personality_type=星云艺术家` + `traits=["creative"]` 已写入

**端到端链路**：`POST /v1/game/profile-sync`（`beta_admin@looma.test` 拿 access_token）→ `upsert_game_profile` → `_send_personality_beacon`（HMAC-SHA256 over raw body，`ensure_ascii=False`）→ DemoPPI `/api/signal/ingest` 验签通过 → 写库。`signal_ingest` 表落 Looma uuid4 nonce + `user_email_hash=99e60963…`（= sha256(beta_admin@looma.test)）。

**真联调中发现并修复的两处坑**：
1. 远程 Supabase（DemoPPI 侧）此前 T0+T4 迁移未应用 → 手动 SQL Editor 应用（email_hash 列/backfill/触发器 + signal_ingest 表 + personality_type/traits 列）
2. DemoPPI 触发器 `handle_new_user_invite` 是 `security definer` 但缺 `set search_path = public, extensions` → gotrue 环境搜不到 `extensions` schema 的 `digest()` → `auth.users` 插入回滚 → create user 500。修复后 create user 通、触发器自动写 `profiles.email_hash`

### T5 本地 mock（可选后置，真联调已覆盖则不必挡路）
- [ ] egress → `localhost:3998` mock 验证
- [ ] curl 打本地 signal-ingest（合法 / 非法 / 重复 nonce → SQLite 幂等）

### env
| 变量 | 配置在 |
|------|--------|
| `SIGNAL_BRIDGE_SECRET` | 两边相同（`824b3402…`） |
| `DEMOPPI_SIGNAL_INGEST_URL` | PlanetX → `http://127.0.0.1:3000/api/signal/ingest` |
| `PLANETX_SIGNAL_INGEST_URL` | DemoPPI |

---

## 与契约阶段二的关系（勿混进本 Epic）

`首次星际匹配_子项目接口契约.md` 的 B2 `match/acknowledge` / 共识门控属**阶段二产品**；种子期信号桥用「有进行中 match mission → mission-complete」捷径。用户量/信号量触发指南 §七 后再升级。

---

## `gh` 命令（鉴权恢复后）

```bash
cd /Users/jason/THOMAS/looma-zervi
gh issue create --title "[Epic] Game 信号桥：ingest + personality_beacon egress" --label "P0,signal-adapter,game" --body-file /tmp/epic-px.md
gh issue create --title "[T0] PlanetX users.email_hash 对齐" --label "P0,signal-adapter,blocker" --body-file /tmp/t0.md
gh issue create --title "[T1] POST /v1/game/signal-ingest（HMAC + SQLite 幂等）" --label "P0,signal-adapter" --body-file /tmp/t1.md
gh issue create --title "[T3] personality_beacon egress 适配器" --label "P0,signal-adapter" --body-file /tmp/t3.md
```
