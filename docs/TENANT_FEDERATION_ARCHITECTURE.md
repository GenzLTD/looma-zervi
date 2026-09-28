# 加盟联邦架构：平台出橱窗 · 租户出书店（引用式）

> **版本：** 1.1 · **日期：** 2026-09-28
> **受众：** 产品 / 工程 / 运维
> **定案 1：** 内容归集形态 = **引用式**（Jason 2026-09-28）
> **定案 2：** 加盟登记与引用缓存的**真源 = PostgreSQL `genzltd` 库**（looma 后端真实库；改造清单 §1 明载）
> **关联：** `~/THOMAS/docs/三方数据归集与多租户对账架构.md` · [SZBOLENT_COM_CN_CUTOVER_CHECKLIST.md](./SZBOLENT_COM_CN_CUTOVER_CHECKLIST.md) · [MULTI_REPO_PUBLISH_FEDERATION.md](./MULTI_REPO_PUBLISH_FEDERATION.md) · `bolent-writer/wordpress/docs/SHELF_BRIDGE_PROTOCOL.md` · `~/Downloads/looma-zervi多租户改造清单.md`

---

## 0. 一句话口径

| 方 | 主体 | 出什么 | 不出什么 |
|----|------|--------|----------|
| **平台** `szbolent.com.cn` | 深伯乐（企业法人） | **橱窗**（展示位）+ **目录** + **收款台** | 不持有租户正文 |
| **租户** `szbolent.cn` | 个人备案主体 | **书店**（内容真源在自己站） | 不收款、不经营 |

跨方只有两条 HTTP 契约，**没有共享库、没有共享 SSO、没有共享部署管线**：

- **通道 A · 读（拉）** = `GET {site}/wp-json/bolent-shelf/v1/feed`（`bolent-shelf-bridge/1`，只给摘要 + 原文链）
- **通道 B · 写（推）** = `POST /v1/signals/content`（HMAC `K(p)`，幂等 `(type,publisher,nonce)`）

---

## 1. 三层角色与真源

| 角色 | 主体 / 备案 | 机器 / 域名 | 持有真源 | 已有 |
|------|-------------|-------------|----------|------|
| 平台方 | 深伯乐 · 企业 ICP | 腾讯云 `1.14.202.161` · `www.szbolent.com.cn` | 登记表 + 引用缓存 + 平台自有内容 | ✅ 站点在跑 |
| 多租户内核 | 同上 | 同机 Looma `:5200` | `driver_profiles` / `columns` / `articles` | ✅ 骨架已建 |
| 加盟租户 | 个人备案 | 阿里云 `47.115.168.107` · `szbolent.cn` | 自己的 WP MySQL（19 表） | ✅ 已上线 |
| 消费者 | — | — | — | — |

> **物理落点（2026-09-28 实测校准 + 当日重建完成）**：加盟登记表与引用缓存均在 PG **`genzltd`**，落点为
> **腾讯云 `1.14.202.161` 的 `looma-pgvector` 容器**（`pgvector/pgvector:pg17`，宿主 `127.0.0.1:5433` → 容器 `5432`）——
> 即上表「多租户内核」那一行持有的同一套数据，见 §3、§9-1。
> ✅ **该容器已于 2026-09-28 重建并可用**：compose 声明式服务 + named volume `looma-zervi_pgdata` +
> 仅绑 `127.0.0.1`（公网 `nc -z 1.14.202.161 5433` 已 **REFUSED**）；库内含**从生产 SQLite 迁入的
> 55 表 / 58,392 行**（逐表对拍一致）与 P1 联邦骨架（`tenants` / `tenant_shelf_items` / `v_catalog_tenants`）。
> 命令级证据见 **[PROD_PG_REBUILD_PLAN.md](./PROD_PG_REBUILD_PLAN.md)** §5.2。
>
> **合规硬要求（这套架构的商业价值所在）**：`szbolent.cn` 是**个人备案**，个人备案站不得从事经营性活动。
> 因此「书店」的收款**绝不能放在 .cn**。正确形态是 —— **内容在 .cn（非经营性 · 备案主体相符）**，
> **交易在 .com.cn（企业法人 · 商户号 · 可开票 · 责任主体）**。三者合一，企业法人才有落点。

---

## 2. 引用式的三条硬后果（先接受，再落地）

| # | 后果 | 工程含义 |
|---|------|----------|
| 1 | **平台零存储租户正文** | `articles` 表**不是**加盟内容的落点（只服务平台自有内容 / 未来归集式租户）。无版权风险、无删文联动、无内容双份 |
| 2 | **官网 SEO 权重归租户** | `/shop/:handle` 的每个详情入口一律 `items[].url` 原链（协议 §3 已强制「禁止拼接、禁止改成书架内页」） |
| 3 | **平台必须有引用缓存层** | 新增 `tenant_shelf_items`（缓存 feed 摘要，TTL 300s，与协议 §7 一致），否则官网每次渲染都打租户站 |

> 与既有契约的关系：`/v1/signals/content`（归集式）**保留但不用于加盟链**——它服务的是"租户自愿归集全文"的未来场景（决策 C）。
> 加盟链上**只有通道 A**。这条边界不写清，两套真源会再次并行，就是本轮要消除的病根。

---

## 3. 数据模型增补（P1）

### 3.1 `tenants` — 加盟登记（**真源：PG `genzltd` 库**）

> 落地脚本：`backend/scripts/migrate_tenants_pg.py`（PG 方言；纯标准库 + `psql(1)`，零新增依赖）
> 本地副本验证：`--db looma --port 5432`（ServBay 原生 PG）；pgvector Docker 栈为 5433（`backend/dev.sh`）

```sql
CREATE TABLE IF NOT EXISTS tenants (
  id           text PRIMARY KEY,
  handle       text NOT NULL,                       -- URL 稳定键：/shop/<handle>
  tenant_type  text NOT NULL DEFAULT 'personal',    -- personal | enterprise
  legal_name   text,                                -- 备案主体名
  icp_no       text,                                -- 备案号（对外展示用）
  domains      jsonb NOT NULL DEFAULT '[]'::jsonb,   -- ["https://szbolent.cn"]
  join_mode    text NOT NULL DEFAULT 'reference',   -- reference | mirror
  feed_url     text,                                -- 通道 A：bolent-shelf-bridge feed
  driver_id    text,                                -- 本地驾驶员（mirror / 平台自营才有；引用式可空）
  status       text NOT NULL DEFAULT 'pending',     -- pending | active | suspended
  share_bp     integer NOT NULL DEFAULT 0,          -- 分成基点（万分之一；0 = 平台自营不分账）
  secret_ref   text,                                -- 通道 B 密钥引用（K(p) 由 master 推导，不落明文）
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT tenants_handle_key        UNIQUE (handle),
  CONSTRAINT tenants_tenant_type_check CHECK (tenant_type IN ('personal','enterprise')),
  CONSTRAINT tenants_join_mode_check   CHECK (join_mode IN ('reference','mirror')),
  CONSTRAINT tenants_status_check      CHECK (status IN ('pending','active','suspended')),
  CONSTRAINT tenants_share_bp_check    CHECK (share_bp BETWEEN 0 AND 10000),
  CONSTRAINT tenants_driver_fk         FOREIGN KEY (driver_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);
```

> `driver_id` **可空是引用式的必然**：加盟租户的内容真源在站外，可能**根本没有本地 Looma 账号**。
> 因此 `/v1/catalog/{handle}` 的橱窗主数据源是 `tenants` 本身，`driver_profiles` 只在 `driver_id` 非空时才叠加。

### 3.2 `tenant_shelf_items` — 引用缓存（TTL 300s）

```sql
CREATE TABLE IF NOT EXISTS tenant_shelf_items (
  tenant_id   text NOT NULL,
  slug        text NOT NULL,                        -- 引用稳定键（协议 items[].slug）
  title       text,
  excerpt     text,                                 -- 唯一允许展示的正文片段
  url         text NOT NULL,                        -- ★ 原文链接，唯一正典入口
  cover       text,                                 -- 可能为 null，消费方须处理空态
  published   timestamptz,
  modified    timestamptz,
  categories  jsonb NOT NULL DEFAULT '[]'::jsonb,
  tags        jsonb NOT NULL DEFAULT '[]'::jsonb,
  fetched_at  timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT tenant_shelf_items_pkey      PRIMARY KEY (tenant_id, slug),
  CONSTRAINT tenant_shelf_items_tenant_fk FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tsi_fetched ON tenant_shelf_items(tenant_id, fetched_at DESC);
```

惰性 TTL 判定：`WHERE fetched_at > now() - interval '300 seconds'`。
租户下线（删 `tenants` 行）→ 引用条目**级联消失**，不残留过期卡片。

### 3.3 `driver_profiles` 补两列

```sql
ALTER TABLE driver_profiles ADD COLUMN IF NOT EXISTS handle text;
ALTER TABLE driver_profiles ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active';
CREATE UNIQUE INDEX IF NOT EXISTS uq_driver_profiles_handle
    ON driver_profiles(handle) WHERE handle IS NOT NULL;
```

> `handle` 是当前最缺的东西：`driver_profiles` 原字段（id / display_name / tagline / avatar_url / bio / show_* / theme）
> **没有任何 URL 稳定键**，无法对外给 `/shop/<handle>`。
> 方言差异（两侧结构必须一致）：PG 侧 `show_*` 是 `boolean`、`theme` 是 `jsonb`；SQLite 侧为 INTEGER / TEXT。

### 3.4 `v_catalog_tenants` — 公开读视图（只暴露 active）

```sql
CREATE OR REPLACE VIEW v_catalog_tenants AS
SELECT id, handle, tenant_type, legal_name, icp_no, domains,
       join_mode, feed_url, status, updated_at
  FROM tenants
 WHERE status = 'active';
```

> 视图是**公开读的单一口径**：`suspended` / `pending` 租户在架构层面就出不了目录，
> 不依赖路由层记得加 `WHERE status='active'`（与「过滤下沉到 DB 层」的既有纪律一致）。

---

## 4. 公开读通道（P2 · 解「官网读不到租户」）

| 端点 | 鉴权 | 数据源 | 说明 |
|------|------|--------|------|
| `GET /v1/catalog` | 无 | `tenants WHERE status='active'` | 目录（官网 `/shops`） |
| `GET /v1/catalog/{handle}` | 无 | `v_catalog_tenants`（`driver_id` 非空时叠加 `driver_profiles`） | 橱窗；主数据源是 `tenants`，按 `show_*` 裁剪 |
| `GET /v1/catalog/{handle}/columns` | 无 | `columns WHERE driver_id` | 书店专栏（仅 published） |
| `GET /v1/catalog/{handle}/feed` | 无 | `tenant_shelf_items` | **平台代理**拉租户 feed，TTL 300s |

**纪律（沿用现有约定，不新造）**：可见性 / 归属过滤**一律在 DB 方法层强制**
（对齐 `backend/src/db/manager.py` 的「Driver content」段），路由层不允许出现"无归属"的查询。
公开读风格对齐 `backend/src/api/routes/poetry_routes.py` 的 `/v1/poetry/*`（现成 public 样板）。

---

## 5. 解耦收口（P0 · 反模式清单）

**必须切掉的既有耦合：**

| 项 | 位置 | 为什么必须切 |
|----|------|--------------|
| `/peer-wp-json/` 反代 | `szbolent-portal-local.conf:88-107`（TCP 中继 `4443` → `192.168.3.44:443`） | 联调期打洞，把**对方站当自家 API** 逐请求代理 —— 这不是联邦，是伪装同源。改为消费 shelf-bridge feed |
| `wp-json/szbolent/v1/shelf` | 双机文档 P4 记的 404 待办 | 第二套 shelf 契约。**直接废止**，全站口径统一到 `bolent-shelf-bridge/1` |
| 两个"博客"语义混用 | `szbolent-portal/src/views/Blog.vue:25` | `/wp-json/` = 官网**自己**的 WP；shelf-bridge = **别人的**站。文案与代码都要分开 |

**反模式（出现即视为重新引入耦合）：**

- 在平台侧建库直连租户 MySQL / 读租户 WP 库
- 让官网前端直接 `fetch()` 租户站 feed（必须经平台 `/v1/catalog/{handle}/feed`，否则 CORS、缓存、下线三方不可控）
- 把租户正文写进 `articles` 并称"顺手归集"
- 重新打开 `/peer-wp-json/` 或新增任何"对方站同源"反代

---

## 6. 官网渲染（P3）

| 路由 | 内容 | 数据源 |
|------|------|--------|
| `/shops` | 加盟书店目录 | `/v1/catalog` |
| `/shop/:handle` | 橱窗 + 书店卡片流 | `/v1/catalog/{handle}` + `/feed` |
| `/shop/:handle/:columnSlug` | 单专栏 | `/v1/catalog/{handle}/columns` + `/feed?category=` |

**卡片契约**：`cover` + `title` + `excerpt` + 跳 `items[].url`（**原链，新窗口，`rel="noopener"`**）。
渲染方**禁止**：请求/存储全文、拼接详情页、改写入口链接。`cover` 可能为 `null`，必须处理空态。

**SEO 取舍（引用式的代价，明账）**：SPA 对多租户 SEO 本就不友好；引用式下详情页在租户域名上，
官网 `/shop/*` 只承担**聚合与导航**权重。若后续要把 SEO 收回平台 → 升级为决策 C（按租户开关 `join_mode='mirror'`），
字段已预留，不改表结构。

---

## 7. 变现与分成（P4）

| 项 | 现状（实测） | 动作 |
|----|--------------|------|
| 官网 Pricing 按钮 | `szbolent-portal/src/views/Pricing.vue:25` `<button>` **无 `@click`**（死按钮） | 接入 `POST /v1/payment/wechat/order` |
| 支付开关 | `backend/src/config.py:112` `PAYMENT_STUB_MODE` 默认 `true` | 生产置 `false` + 5 项 `WECHAT_*` |
| 商户号 | **外部依赖** | 深伯乐企业主体微信商户号 → 建议并行启动 |
| 成交信号 | 协议**无金额字段** → 抽佣跑不通 | 扩 `amount` / `order_ref` |
| 分成台账 | 对账原型已跑通（双台账 + 稳定键 + 四类差异 + 退出码门禁） | 直接复用 |

**收款主体唯一性**：`wechat_pay.py` 文件头的 `Ownership: szbenyx` 是**注释级**产权声明。
对外招加盟前必须升级为**正式加盟协议文本**（明确：looma 供能力、深伯乐收款承责、数据与知识产权边界、
退出时数据删除责任），否则纠纷时责任链会断。

---

## 8. 落地清单（文件级）

| 阶段 | 动作 | 目标文件 | 状态 |
|------|------|----------|------|
| **P0** | 切 `/peer-wp-json/` 反代 | `szbolent-portal-local.conf:88-107` | ⏳ |
| **P0** | 废止 `wp-json/szbolent/v1/shelf`，统一到 `bolent-shelf-bridge/1` | `szbolent-portal` + 双机文档 P4 | ⏳ |
| **P0** | 分离两个"博客"语义（官网 WP vs 加盟 feed） | `szbolent-portal/src/views/Blog.vue` | ⏳ |
| **P1** | `tenants` / `tenant_shelf_items` / `driver_profiles` 补 `handle`+`status` / `v_catalog_tenants` 视图 —— **PG `genzltd` 真源** | `backend/scripts/migrate_tenants_pg.py` | ✅ 已建 · 本机副本 `looma` 已验证 |
| **P1** | 同上 —— **SQLite 侧镜像**（结构与 PG 必须一致，改一份改两份） | `backend/scripts/migrate_driver_multitenant.py` 同系脚本 | ⏳ |
| **P1** | `genzltd` 生产库执行同一脚本 | `migrate_tenants_pg.py --db genzltd` | ✅ **已执行（2026-09-28）**：生产 PG 重建后 dry-run rc=0 → APPLY rc=0 → **复跑幂等（全「已存在，跳过」）**；产出 `tenants` / `tenant_shelf_items` / `v_catalog_tenants` / `driver_profiles.handle,status` / `uq_driver_profiles_handle`。证据 → [PROD_PG_REBUILD_PLAN.md](./PROD_PG_REBUILD_PLAN.md) §5.2 |
| **P1** | 加盟登记 CLI（参数文件单一事实来源，风格对齐 `scripts/clone-blogger.sh`） | `scripts/onboard-tenant.sh` + `tenants/<slug>.env` | ⏳ |
| **P2** | `/v1/catalog/*` 四端点（匿名只读） | 新 `backend/src/api/routes/catalog_routes.py` + `app.py` 注册 | ⏳ |
| **P2** | 引用缓存刷新（惰性 TTL 300s，与协议 §7 对齐） | `backend/src/db/manager.py` + 代理端点 | ⏳ |
| **P3** | `/shops` `/shop/:handle` `/shop/:handle/:col` | `szbolent-portal/src/router/index.ts` + 新 views | ⏳ |
| **P3** | 书架板块从"硬编码 szbolent.cn feed"升级为"读 `/v1/catalog`" | `szbolent-portal/src/views/Blog.vue` | ⏳ |
| **P4** | Pricing 接线 + 支付开关 + 信号扩字段 | `Pricing.vue` · `.env` · `driver_content_routes.py` | ⏳ |
| **P5** | SQLite 侧复合外键迁移 + `PRAGMA foreign_keys=ON` | 迁移脚本 + `manager.py` 连接段 | ⏳ |
| **P5** | 生产 `looma.db` 执行迁移 | 腾讯云 | ⏳ |

---

## 9. 待决

1. ~~**真源分歧**~~ → **已结案（2026-09-28）**：**真源 = PG `genzltd`**（looma 后端真实库，改造清单 §1 明载）。
   结构变更一律先进 `migrate_tenants_pg.py`（PG 方言）；SQLite 侧仅作**镜像**，用于 pytest 与本地降级运行 ——
   两侧结构漂移即视为缺陷（每个 DDL 改动需同时落两份脚本）。
   > 落地记录（2026-09-28 **实测重校**）：本机 ServBay PG（`127.0.0.1:5432`）里**不存在 `genzltd`**
   > （只有 `looma` / `postgres` / `ppi_demo`），已用同结构副本 `looma` 全量验证脚本；
   > 生产侧 `genzltd` **尚不存在任何可用实例** —— 生产机（腾讯云 `1.14.202.161`）唯一 PG 容器
   > `looma-pgvector` 是手工 `docker run` 的孤儿，PGDATA（bind 到仓库树内 `data/pgdata`）已被
   > `deploy.yml:228` 的 `rsync --delete` 删除，库内 `total 0`、`pg_filenode.map` 缺失、任何连接 FATAL。
   > **结论（当时）：`genzltd` 是"目标库名 + DDL 蓝图"**（蓝图 = `~/PycharmProjects/genzltd-docs/docs/genzltd_schema_v0.2.sql`，
   > 对齐真源 `backend/src/db/manager.py`）；生产落地顺序见 **[PROD_PG_REBUILD_PLAN.md](./PROD_PG_REBUILD_PLAN.md)**。
   >
   > ✅ **落地完成（2026-09-28 当日，同一轮）**：按该方案执行 ——
   > 删孤儿容器 → 写 `/home/ubuntu/looma-zervi/docker/.env`（新 32 位随机密码，`600`，不入 git）
   > → **D1** compose 服务 + `pgdata` named volume（只绑 `127.0.0.1:5433`）
   > → **D1b** `deploy.yml` 的 `up` 列表补 `pgvector`（否则每次部署会把它删掉且不重启 —— 执行中发现）
   > → **D4** rsync 排除 `data/pgdata`（防御性）
   > → 从生产 SQLite 快照迁入 **55 表 / 58,392 行**（逐表对拍一致 · 17 个 identity 序列对齐 · 55 外键提交校验通过）
   > → `migrate_tenants_pg.py` APPLY + 幂等复跑。
   > **`genzltd` 自此是真实生产库**：PostgreSQL 17.10，57 表 + 1 视图，容器 `healthy` 且带 compose 标签。
   > 仍未动的：backend 的 `DATABASE_PATH`（依旧 SQLite）—— PG 属**旁挂数据面**，P2 读取方式决策见该方案 §9。
2. **引用缓存刷新方式**：惰性 TTL（首次访问触发，简单）vs 定时任务（新鲜度可控，多一个组件）。
   暂按**惰性 TTL 300s** 实现（协议 §7 允许 300s 内陈旧）；DDL 已同时留 `fetched_at` + `idx_tsi_fetched`，
   两条路线都不需要改表，故**不阻塞 P2**。

---

## 10. 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-09-28 | 1.0 | 首版：定案**引用式**；三层角色；`tenants` / `tenant_shelf_items`；`/v1/catalog/*`；P0 解耦反模式清单；P0~P5 文件级落地清单 |
| 2026-09-28 | 1.2 | **实测校准生产落点**（§1 物理落点、§9-1 落地记录）：`genzltd` 的生产落点 = 腾讯云 `1.14.202.161` 的 `looma-pgvector` 容器；实测该容器为**孤儿+半死**（PGDATA 被 `rsync --delete` 删除，库内无数据），故 P1「生产库执行」改为**阻塞于 PG 重建**，方案另出 [PROD_PG_REBUILD_PLAN.md](./PROD_PG_REBUILD_PLAN.md)。**定案 2（真源 = PG `genzltd`）不变**，仅补齐落点与前置条件 |
| 2026-09-28 | 1.1 | **真源结案 = PG `genzltd`**（§9-1）；§3 DDL 改 PG 方言（`jsonb` / `timestamptz` / `ADD COLUMN IF NOT EXISTS`）；新增 `tenants.driver_id`（可空，引用式的必然）与 `v_catalog_tenants` 公开读视图（§3.4）；`/v1/catalog/{handle}` 数据源修正为 `tenants` 为主（§4）；落地脚本 `backend/scripts/migrate_tenants_pg.py`（本机副本 `looma` 已建 + 幂等验证通过） |
| 2026-09-28 | 1.3 | **生产落地完成**：`genzltd` 已在腾讯云 `1.14.202.161` 重建可用（compose 服务 + `pgdata` named volume + 仅绑 `127.0.0.1`，公网 5433 已 REFUSED），迁入 SQLite **55 表 / 58,392 行**，P1 联邦骨架 APPLY 且幂等复跑通过。§1 物理落点、§8 P1 状态、§9-1 落地记录同步更新；执行证据见 [PROD_PG_REBUILD_PLAN.md](./PROD_PG_REBUILD_PLAN.md) §5.2 |
