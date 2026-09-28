# 生产 PG 重建与 `genzltd` 落地方案（腾讯云 1.14.202.161）

> **版本：** v1.2 · **日期：** 2026-09-28 · **状态：** ✅ **已执行完成**（阶段 1–6 全部落地，证据见 §5.2/§5.3）
> **已改动：** `docker/docker-compose.yml`(D1 + 优雅停机/日志轮转) · `.github/workflows/deploy.yml`(D1b/D1b+/D4) ·
> 生产 `docker/.env`(D2) · 生产容器与卷（孤儿已删 → 新 `looma-pgvector` + `looma-zervi_pgdata`）·
> PG 库 `genzltd`（55 表 / 58,392 行 + P1 骨架）。
> **未改动：** backend 的 `DATABASE_PATH` / `manager.py` / 任何 PG 驱动 → PG 仍是**旁挂数据面**，回滚零成本（§7）。
> **D1b 已验证：** 同命令复演实测「`down` 删掉 PG → `up` 列表把它拉回，数据零丢失」（§5.3②）。
> **剩余待办：** ① D3 安全组收窄（控制台手动，见 §4-D3；容器侧只绑 `127.0.0.1`，公网 5433 已 **REFUSED** ⇒ 清冗余规则）；
> ② CI 平台阻断（当日 5 连 `steps=0` 秒败，既存于 09-23，需人工处理 Actions 面；§5.3①）。
> **关联：** [TENANT_FEDERATION_ARCHITECTURE.md](./TENANT_FEDERATION_ARCHITECTURE.md) §1/§3/§9-1 · `backend/scripts/migrate_tenants_pg.py`

---

## 0. 结论摘要

| 问题 | 实测结论（命令级证据见 §1） |
|---|---|
| 「生产 `genzltd`」在哪台机器 | **腾讯云 `1.14.202.161`**（`ubuntu@1.14.202.161`，SSH 密钥可直登）——**是云服务器**，理由是它是唯一持有 PostgreSQL 的机器 |
| 那台机的 PG 现状 | 容器 `looma-pgvector`（`pgvector/pgvector:pg17`）**孤儿 + 半死**：`started=2026-07-02T16:43:32Z`、手工 `docker run`（`Config.Labels=map[]`）、bind 源 `/home/ubuntu/looma-zervi/data/pgdata` **已被部署删除** |
| 库里现有数据 | **无任何数据**：容器内 `/var/lib/postgresql/data` = `total 0`，`global/pg_filenode.map` 不存在；任意连接 `FATAL: could not open file "global/pg_filenode.map": Permission denied` |
| 生产业务真源 | **SQLite**：`looma-backend` env `DATABASE_PATH=/app/data/looma.db`（卷 `looma-zervi_backend-data`，33.6 MB，2026-09-25） |
| `genzltd` 这个名字的出处 | `~/PycharmProjects/genzltd-docs/docs/genzltd_schema_v0.2.sql`（**PG 方言 50 表蓝图**，对齐 `backend/src/db/manager.py`）——不是一台已存在的服务器 |
| 对外暴露面 | **`1.14.202.161:5433` 对公网 OPEN**（外机 `nc` 成功）；宿主 `ufw inactive`、`iptables` 仅 `YJ-FIREWALL-INPUT` 管 22 端口 → **5433 由腾讯云安全组放行** |
| 本方案风险 | **低**：backend 当前不读 PG，PG 属新增数据面；回滚 = 删容器，现有业务零感知（§7） |

---

## 1. 现场取证（全部只读）

```bash
# 1) 生产容器清单 —— PG 只能在这台机
ssh ubuntu@1.14.202.161 'docker ps --format "{{.Names}} | {{.Image}} | {{.Ports}}"'
# looma-pgvector | pgvector/pgvector:pg17 | 0.0.0.0:5433->5432/tcp    ← 绑公网
# looma-backend  | looma-zervi-backend    | 0.0.0.0:5200->5200/tcp
# looma-chromadb / looma-redis / bolent_wp / bolent_wp_mysql

# 2) PG 容器身世：手工创建、7-02 起未重启、bind 到仓库树内
ssh ubuntu@1.14.202.161 'docker inspect looma-pgvector \
  --format "started={{.State.StartedAt}} labels={{.Config.Labels}} binds={{.HostConfig.Binds}}"'
# started=2026-07-02T16:43:32Z  labels=map[]  binds=[/home/ubuntu/looma-zervi/data/pgdata:/var/lib/postgresql/data]

# 3) PGDATA 已被删（宿主不存在，容器持旧 inode → 空目录）
ssh ubuntu@1.14.202.161 'ls -la /home/ubuntu/looma-zervi/data/pgdata'      # No such file or directory
ssh ubuntu@1.14.202.161 'docker exec looma-pgvector ls -la /var/lib/postgresql/data'   # total 0

# 4) 服务端日志：pid 写不进 + 目录读不了
ssh ubuntu@1.14.202.161 'docker logs --tail 20 looma-pgvector'
# LOG:  could not open file "postmaster.pid": Permission denied; continuing anyway   ← 每分钟一条
# FATAL: could not open file "global/pg_filenode.map": Permission denied             ← 每次连接

# 5) 业务真源仍是 SQLite（PG 从未被 backend 使用）
ssh ubuntu@1.14.202.161 'docker exec looma-backend env | grep -E "DATABASE_PATH|PG_"'
# DATABASE_PATH=/app/data/looma.db        （无任何 PG_* 键）
ssh ubuntu@1.14.202.161 'cut -d= -f1 /home/ubuntu/looma-zervi/backend/.env'   # 12 行，无 PG_*

# 6) 部署管线与 rsync 排除表（根因 R1 的证据）
grep -n -A14 'rsync -avz' .github/workflows/deploy.yml
# 228: rsync -avz --delete  ... 229-239: --exclude .git / node_modules / __pycache__ /
#      backend/venv / backend/data / data/poetry_full / .env / backend/.env / frontend/
#     ← data/pgdata 不在排除表 ⇒ 每次 push main 部署都会删它

# 7) 生产工具面（决定执行方式）
ssh ubuntu@1.14.202.161 'which psql pg_dump'          # 宿主：全无
ssh ubuntu@1.14.202.161 'docker images | grep pgvector'  # pgvector/pgvector:pg17  be400b50812a  627MB  本地已有
ssh ubuntu@1.14.202.161 'docker exec looma-backend python3 -V'   # Python 3.12.14（容器内）
ssh ubuntu@1.14.202.161 'python3 -V; df -h /home | tail -1'      # Python 3.10.12；45G 可用
```

---

## 2. 根因（为什么它死了，而且不修就必然复发）

| # | 根因 | 证据 |
|---|---|---|
| **R1** | **PGDATA 被放在仓库树内**，而部署是 `rsync --delete` | `deploy.yml:228-241` 排除表里没有 `data/pgdata`；`data/` 本身受管（`data/poetry_full` 需显式排除）→ **每次部署删 PGDATA** |
| **R2** | **手工 `docker run` 创建，不在 compose 定义内** | 容器 `Labels=map[]`（无 compose 标签）；仓库与本机生产 compose 内 `grep pgvector` 均无命中 → 无声明式重建路径，坏了只能靠人记 |
| **R3** | bind 源消失后 docker 以 root 建空目录，容器内 `postgres`(999) 写不进 | `postmaster.pid: Permission denied` 循环 + `pg_filenode.map` 不存在 |
| **R4** | 对外绑 `0.0.0.0:5433` + 凭据明文在容器 env | `POSTGRES_USER=looma / POSTGRES_PASSWORD=…`（已暴露，**必须轮换**） |
| **R5** | PG 与业务无耦合，坏了 3 个月无人察觉 | backend 无 PG 驱动、`.env` 无 `PG_*`；`config.py` 的 `PG_DSN` 定义未使用 |

> **设计结论**：重建必须同时消除 R1（PGDATA 出仓库树）、R2（进 compose）、R4（只绑 127.0.0.1 + 轮换凭据），否则是"再死一次"。

---

## 3. 目标态

| 项 | 目标 | 为什么 |
|---|---|---|
| 容器 | `looma-pgvector` = **compose 声明式服务**（`docker/docker-compose.yml`） | 消除 R2：坏了一行命令重建，不再靠人记 |
| PGDATA | **named volume `looma-zervi_pgdata`**（`/var/lib/docker/volumes/`） | 消除 R1+R3：脱离仓库树 → `rsync --delete` 永不触碰；属主由 docker 管理 |
| 端口 | **`127.0.0.1:5433:5432`**（仅宿主本地） | 消除 R4 的公网面；即使安全组误放行也连不上 |
| 凭据 | 新密码入 `docker/.env`（**不入 git**，`.env` 已被 rsync 按 basename 排除） | 旧密码（`Looma***2026!`，字面量已从文档脱敏）曾随公网暴露，**必须轮换且禁止复用** |
| 库 | `POSTGRES_DB=genzltd`（initdb 直接建目标库）· `POSTGRES_USER=looma` | 「生产 `genzltd`」到此刻才**真实存在** |
| 业务库 | **不动**：backend 继续 `DATABASE_PATH=/app/data/looma.db` | 新增数据面，与现有业务零耦合 → 回滚零成本 |
| 版本 | `pgvector/pgvector:pg17`（镜像本地已有 `be400b50812a`） | 离线可重建，不依赖拉网 |

---

## 4. 变更清单（4 项，含精确 diff）

### D1 【仓库】`docker/docker-compose.yml` — 加 pgvector 服务（唯一必改的仓库文件）

```diff
--- a/docker/docker-compose.yml
+++ b/docker/docker-compose.yml
@@ volumes
 volumes:
   backend-data:
   chroma-data:
   redis-data:
+  pgdata:
```

```yaml
  # ============================================
  # PostgreSQL 17 + pgvector（联邦登记 / 目录真源）
  # 2026-09-28 重建，取代 2026-07-02 手工 docker run 的孤儿容器。
  # 三条硬约束（对应 §2 根因，改之前先读 PROD_PG_REBUILD_PLAN.md）：
  #   1) PGDATA 用 named volume —— 绝不能落仓库树内（deploy.yml 的 rsync --delete
  #      会删掉 data/pgdata，这正是上次死亡原因 R1）
  #   2) ports 只绑 127.0.0.1 —— 消除 0.0.0.0:5433 公网暴露（R4）
  #   3) 密码只从 docker/.env 取（env_file），不入 git；.env 已被 rsync 排除
  # ============================================
  pgvector:
    image: pgvector/pgvector:pg17
    container_name: looma-pgvector
    restart: unless-stopped
    ports:
      - "127.0.0.1:5433:5432"
    environment:
      - POSTGRES_USER=looma
      - POSTGRES_DB=genzltd
    env_file:
      - ./.env          # docker/.env：提供 POSTGRES_PASSWORD（缺文件 → compose 报错，快速失败）
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U looma -d genzltd"]
      interval: 10s
      timeout: 5s
      retries: 6
    networks:
      - looma-net
```

> **备选（不加文件）**：若不想在 `docker/` 放 `.env`，把 `env_file` 改成 `../backend/.env` 并在生产
> `backend/.env` 追加 `POSTGRES_PASSWORD=…`。代价：该密钥会同时注入 backend 容器 env。

### D1b 【仓库·执行中发现的必需项】`deploy.yml` 把 pgvector 加进 `up` 列表

```diff
--- a/.github/workflows/deploy.yml
+++ b/.github/workflows/deploy.yml
@@ -370,7 +370,9 @@
           ${COMPOSE} up -d --remove-orphans --force-recreate --no-build backend
-          ${COMPOSE} up -d --no-build chromadb
+          # pgvector 必须在此列出：上面 `compose down -p looma-zervi` 已删除该项目
+          # 全部容器（含 pgvector），不 up 就会被永久停掉。数据在 named volume 中，安全。
+          ${COMPOSE} up -d --no-build chromadb pgvector
```

> **为什么漏了这条会翻车**：`deploy.yml:323-325` 是 `docker compose -p looma-zervi down --remove-orphans` ——
> 它删除**该项目全部容器**。D1 之前 `looma-pgvector` 无 compose 标签（孤儿），所以能"活着"躲过两个月；
> D1 之后它成了项目成员 ⇒ **每次部署都会把它删掉**，而第 370/371 行只 `up backend/chromadb`
> ⇒ PG 会"部署一次、死一次"。这是 D1 的**隐藏耦合**，只在真正接进 compose 后才暴露（数据安全：容器被删但卷 `pgdata` 保留）。

> **同一 `down` 还删了 `redis`，为什么它没死？** 因为 `docker-compose.yml` 里 `backend: depends_on: [redis]` ——
> `up -d backend` 会把依赖链上的 `redis` 一起拉起。**pgvector 不在任何 `depends_on` 里**，所以它必须被显式写进 `up` 列表。
> （若将来给 backend 加 `depends_on: pgvector`，本行可简化，但**不要把 up 列表里的 pgvector 删掉**。）

> **配套守卫（同日追加，D1b+）**：`deploy.yml` 在 `up` 之后新增断言 —— `looma-pgvector` 必须在跑、
> `pg_isready -U looma -d genzltd` 必须就绪（≤20s）、`genzltd` 表数必须 **≥ 55**，任一不满足即 `exit 1` 让部署变红。
> 作用：把"有人再把 pgvector 移出 up 列表"或"卷丢失"这类事故**从静默停摆变成部署期硬失败**。

### D2 【生产机，手工一次】`/home/ubuntu/looma-zervi/docker/.env`

```bash
# 在生产机执行（新密码自定，勿复用 2026-07 旧值）
ssh ubuntu@1.14.202.161 'umask 077; cat > /home/ubuntu/looma-zervi/docker/.env <<EOF
POSTGRES_PASSWORD=<新强密码>
EOF'
```
> 该文件不被 git 跟踪；`--exclude='.env'`（无斜杠 → 匹配任意层 basename）保证它不会被部署删除。

### D3 【生产机 / 控制台】安全组收口

腾讯云控制台 → 该实例安全组 → **删除/收窄 `5433` 的 `0.0.0.0/0` 入站规则**（建议只留 `127.0.0.1` 或管理网段）。
宿主侧无 ufw、`YJ-FIREWALL-INPUT` 只管 22，**5433 完全由安全组放行**，必须控制台改。

### D4 【仓库，防御性】`deploy.yml` 排除表补一行

```diff
--- a/.github/workflows/deploy.yml
+++ b/.github/workflows/deploy.yml
@@ -234,6 +234,7 @@
             --exclude='backend/venv' \
             --exclude='backend/data' \
             --exclude='data/poetry_full' \
+            --exclude='data/pgdata' \
             --exclude='.env' \
```
> 用了 named volume 后此项非必需；留着是防"将来有人改回 bind mount 到 `data/pgdata` 又被删"。

---

## 5. 执行步骤（含顺序依赖与验收）

| 阶段 | 动作 | 命令 / 位置 | 验收 |
|---|---|---|---|
| **0** 本机预演 | 跑导出脚本（只读 SQLite，不连 PG）：生成 PG DDL + 数据 + 行数报告 | `python3 backend/scripts/export_sqlite_to_pg.py --sqlite backend/data/looma.db --out /tmp/genzltd/` | 55 表 DDL 生成、每表行数报告、0 报错 |
| **1** 清理孤儿 | 删旧容器（**已取证无数据**） | `ssh ubuntu@1.14.202.161 'docker rm -f looma-pgvector'` | `docker ps -a` 无该容器；卷未被触碰 |
| **2** 落凭据 | 先做 **D2**（顺序不可颠倒） | 见 §4-D2 | 文件存在、权限 `600` |
| **3** 落定义 | 提交 **D1**（+**D4**）→ push `main` → CI 部署；或该机手工 `up -d pgvector` 立即生效 | `ssh … 'cd /home/ubuntu/looma-zervi && docker compose -p looma-zervi -f docker/docker-compose.yml up -d pgvector'` | `docker ps` 见 `127.0.0.1:5433->5432`；`docker exec looma-pgvector psql -U looma -l` 列出 **`genzltd`** |
| **4** 建表 | 把阶段 0 产物导入 | `docker cp /tmp/genzltd/schema.sql looma-pgvector:/tmp/ && docker exec looma-pgvector psql -U looma -d genzltd -f /tmp/schema.sql` | 表数 = SQLite 侧（55）；索引/唯一约束齐 |
| **5** 灌数据 | 导数据（脚本产出 `INSERT`/`COPY` 内联 SQL） | `docker cp /tmp/genzltd/data.sql looma-pgvector:/tmp/ && docker exec looma-pgvector psql -U looma -d genzltd -f /tmp/data.sql` | 逐表行数与 SQLite 一致（脚本 `--verify` 对拍） |
| **6** 补联邦骨架 | 跑既有 P1 脚本（幂等） | `python3 backend/scripts/migrate_tenants_pg.py --db genzltd --host 127.0.0.1 --port 5433 --user looma`（**在能连 127.0.0.1:5433 的机器上**） | `tenants`/`tenant_shelf_items`/`v_catalog_tenants` 存在且幂等（重跑全跳过） |
| **7** 安全收口 | **D3** 安全组 | 控制台 | 外机 `nc -z -w4 1.14.202.161 5433` → **失败** |
| **8** 记录 | 更新本文 §8 验收表 + 架构文档 §9-1 | — | `git status` 仅文档改动 |

> **阶段 6 的落点提醒**：`migrate_tenants_pg.py` 走 `psql(1)` 子进程，**生产宿主无 psql、无 PG 驱动** →
> 统一用 `docker exec -i looma-pgvector psql … -f -` 从 stdin 喂 SQL；脚本只负责"生成 SQL"。
> 需要连库时用 `docker exec looma-pgvector psql -U looma -d genzltd -c '…'`（**不要**走公网 5433）。

## 5.1 阶段 0 已完成（本机实跑，零生产影响）

已按本方案实现并验证搬运脚本 `backend/scripts/export_sqlite_to_pg.py`（纯标准库）：

```bash
python3 backend/scripts/export_sqlite_to_pg.py --sqlite backend/data/looma.db --out /tmp/genzltd
# [OK] /tmp/genzltd/schema.sql  （55 表）
# [OK] /tmp/genzltd/data.sql  （21,543,719 B）
# [OK] /tmp/genzltd/constraints.sql / verify.sql / report.md  （告警 3 条）
```

产物在本机 PG **17.9**（与生产 `pgvector/pgvector:pg17` 同大版本）的临时库 `genzltd_dryrun` 全量装载：

| 验收项 | 结果 |
|---|---|
| `schema.sql` | rc=0 → **55 表 · 174 索引 · 55 外键**（FK 全部 `DEFERRABLE INITIALLY DEFERRED`） |
| `data.sql` | rc=0 → **58,609 行**，事务提交时 FK 校验通过（无孤儿行） |
| `constraints.sql` | rc=0 → `users_role_check CHECK (role IN ('user','enterprise','admin','driver'))` 生效，坏值被拒 |
| identity 自增 | `insert into query_logs default values returning id` 正常（`setval` 已对齐 max） |
| 逐表行数对拍 | `diff` SQLite vs PG → **✅ 55 表完全一致** |
| 源库安全 | 连接强制 `PRAGMA query_only=ON`；源文件 mtime 未变 |

> 3 条告警（已在 `report.md` 列明，均为"需人工判断"而非静默丢失）：
> `applications.idx_applications_active_unique` 与 `consents.idx_consents_active` 是**部分索引**（跳过）、
> `huawei_push_tokens.created_at` 默认值 `strftime('%s','now')`（丢弃默认值，列仍可空）。

> 注：§5.1 的行数（58,609）来自**本机工作树副本** `backend/data/looma.db`；§5.2 生产快照为 **58,392 行**
> （生产库比该副本更新，users 10 vs 43），两者表结构完全同形。

## 5.2 生产执行记录（2026-09-28 实跑，命令级证据）

| 阶段 | 动作 | 结果 |
|---|---|---|
| **1** 清理孤儿 | `docker rm -f looma-pgvector`（删前二次复核：单 bind 挂载 `/home/ubuntu/looma-zervi/data/pgdata`、容器内 PGDATA `total 0`） | 已删；**无数据损失**（取证见 §1） |
| **2** 落凭据 | 写 `/home/ubuntu/looma-zervi/docker/.env`（`umask 077`） | `-rw------- 51 B`；`POSTGRES_PASSWORD=[a-f0-9]{32}` 校验通过；**密码只在文件里，日志不留** |
| **3** 落定义 + 起服务 | 装 D1 → `docker compose -p looma-zervi -f docker/docker-compose.yml up -d pgvector` | 卷 `looma-zervi_pgdata` **新建**；容器 `127.0.0.1:5433->5432`、`healthy`、标签 `com.docker.compose.project=looma-zervi`（**R2 消除**）；入网 `looma-zervi_looma-net`（别名 `pgvector`，与 backend 同网 → P2 可用 `pgvector:5432`） |
| **4** 服务与库 | `psql -l` / `pg_available_extensions` | **PostgreSQL 17.10**；库列表含 **`genzltd`**；`vector` 扩展**可用**（未 `CREATE EXTENSION`，需要时一行） |
| **5** 快照 | 容器内 `sqlite3.backup()` API（WAL 安全，非 `cp`） | 33,607,680 B 落地宿主 `/tmp`；**源生产库 mtime 未变**（`Sep 25 00:14`） |
| **6** 导出 | `export_sqlite_to_pg.py`（脚本随代码部署在 `/home/ubuntu/looma-zervi/backend/scripts/`） | rc=0：55 表 / **58,392 行** / `data.sql` 21,632,791 B / 告警 3 条（同形于 §5.1） |
| **7** 灌入 | `schema.sql` → `data.sql` → `constraints.sql`（皆 `docker exec -i … -f -` 走 stdin） | schema **rc=0**（1s，55 表）· data **rc=0**（4s，FK 在 COMMIT 校验通过）· constraints **rc=0** |
| **8** 对拍 | `verify.sql` + `sqlite3` 逐表计数自动化对拍 | **55/55 行数一致**；结构 `表 55 · 索引 172 · 外键 55`；**identity 17 个序列 last_value ≥ max(id)**；`users_role_check` 已生效 |
| **9** 联邦骨架（阶段 6） | `migrate_tenants_pg.py`（**不带 `--seed`**） | dry-run **rc=0** → APPLY **rc=0** → **复跑 rc=0 全「已存在，跳过」（幂等 ✅）**；产出 `tenants` / `tenant_shelf_items` / `v_catalog_tenants` + `driver_profiles.handle,status` + `uq_driver_profiles_handle`；总 **57 表 + 1 视图**；原数据抽查 `poems=58,059 · users=10 · driver_profiles=1` 未变 |
| **10** 对外面 | 本机公网 `nc -z -w4 1.14.202.161 5433` | **REFUSED**（容器绑定收口已生效）⇒ 即使安全组仍放行 `0.0.0.0/0`，也**连不进来** |
| **11** 收口 | 三处仓库 diff + 两个脚本 + 两份文档 | 已提交到 `main`（6 files / +1608）—— D1 · D1b · D4 · `export_sqlite_to_pg.py` · `migrate_tenants_pg.py` · 本文档 + 架构文档 |
| **12** 推送上云 | `git push origin main`（先 rebase 到远端 `a51ff19`） | rc=0：`a51ff19..d522301`；后续追加 `2193b24`（D1b+ 守卫）、`3bb0c35`（优雅停机 + 日志轮转）。**CI 当日 5 连秒败**（§5.3①）⇒ 部署未跑，生产容器 id 与「部署前留证」**逐字一致**（未被误改） |
| **13** D1b 复演 | 在 prod 逐字执行 `deploy.yml` 的 down/up 序列（含新守卫） | **PG 被删 → 被拉回，数据零丢失**：容器 `436db82e…`→`d76ed630…`、卷 `CreatedAt` 未变、`57 表/1 视图/58,392 行` 逐项一致（§5.3②） |
| **14** 对外面复测 | 本机 9 端口扫描 + prod 宿主 `ss -lntp` | 公网仅 `22/80/443` 通；`5200/5433/5432/6379/8000/3306` 全 REFUSED；Redis 无认证（§5.3④） |

> **宿主无 `psql(1)` 的解法**：阶段 9 用一次性垫片 `/tmp/psql-shim.py`（剥掉 `-h/-p/-U/-d` 后透传
> `docker exec -i looma-pgvector psql`），使 `migrate_tenants_pg.py --psql <shim>` **原样工作、脚本零改动**；
> 垫片只在执行期存在于 `/tmp`，**不入仓库**。
> **`pg_sequences.last_value = NULL` ≠ 没对齐**：该视图在 **`is_called = false`**（序列 RESTART/setval 后尚未被取用）时返回 NULL。
> 实测三例自证：`poems`（`max(id)=78644`）→ 序列 `last_value=78644, is_called=true` ⇒ **下个 id = 78645** ✅；
> 空表 `boost_consumptions` / `challenge_entries` → 初始态 `last_value=1, is_called=false` ⇒ 下个 id = 1 ✅。
> 脚本体为 `setval(pg_get_serial_sequence(<t>,<c>), max(id))`（`export_sqlite_to_pg.py:323`），语义正确。
> **`driver_profiles` 既有 1 行的回填行为**（实测）：`status` 因 `NOT NULL DEFAULT 'active'` 取到 `active` ；
> `handle` 保持 **NULL**（可空 + 局部唯一索引 `WHERE handle IS NOT NULL`，故不冲突）——**该行要进橱窗须先补 handle**（属 P1 CLI 的活）。
> **未执行 `--seed`**（首批 `t-official` / `t-szbolent-cn` 登记）：需要时同命令去掉 `--dry-run` 并加 `--seed`（幂等 upsert）。

---

### 5.3 D1b 实测与 CI 阻断（2026-09-28 推流执行）

#### ① `git push` 成功，但当日 CI 无法完成部署

| 观察 | 值 |
|---|---|
| 推送 | rebase 后 `a51ff19..d522301`；再追加 `2193b24`（D1b+ 守卫）、`3bb0c35`（优雅停机 + 日志轮转）。`HEAD == origin/main`，工作树干净 |
| 触发的 run | `36394130298` / `36394648004` / `36394649230` / `36394785769` → **全部 `steps=0` 秒级失败**（"Build Frontend"/"Backend Tests" 3 秒内起止、**零步骤**、`runner_name` 为空；两个 Deploy 作业被 `needs` 跳过） |
| 是否我们引起 | **否**：同签名（`steps=0`）在 **09-23 的 3 次运行**（`35812461464`/`35860156322`/`35874564562`）已出现；09-24 唯一的成功 run `36066075150` 是 **attempt=3**（attempt 1/2 同为 `steps=0` 失败）⇒ 该 workflow 长期靠「重试到成功」 |
| 重试通道 | `gh run rerun` 与 `workflow_dispatch` 对 Actions **写**端点均 **HTTP 404**（读端点正常）；空提交 push **不触发**（`paths-ignore` 下零文件变更不算命中） ⇒ 只能等人工修复后重跑 |
| 影响面 | 生产 backend 仍是 `git_commit a51ff19`（容器未重建）；**PG 侧变更已实际生效**（新版 compose 已同步 prod 并 recreate 过） |
| 待办 | 属账号/Actions 面问题（配额/权限），**需人工处理**；修好后重跑，D1b+ 守卫会在真实部署路径上再验一次 |

#### ② D1b 同命令复演（部署序列**逐字**执行，替代被阻断的 CI 部署）

前置：`scp docker/docker-compose.yml → prod`（等价于 `rsync` 的效果；旧文件备份 `/tmp/docker-compose.yml.pre-d1b`）。
脚本 `/tmp/rehearse_d1b.sh` 与 `deploy.yml`：「`compose down -p looma-zervi --remove-orphans`」→「`up -d --remove-orphans --force-recreate --no-build backend`」→「`up -d --no-build chromadb pgvector`」**逐字一致**。

| 观察点 | PRE | POST | 结论 |
|---|---|---|---|
| `down` 输出 | — | `Container looma-pgvector Stopping/Stopped/Removing/**Removed**` + `Network looma-zervi_looma-net Removed` | **耦合确凿**：`down` 真会删掉 PG |
| 全状态容器数（`--filter name=looma-pgvector`） | 1 | **0** | 删净后，才能证明是 `up` 列表把它救回来的 |
| `up` 输出 | — | `up -d --no-build chromadb **pgvector**` → `Container looma-pgvector Created/Started` | **D1b 有效** |
| 容器 id | `436db82ee29d…` | `d76ed630eaec…` | **确实重建**（非复用旧容器） |
| `State.StartedAt` | `06:51:32Z` | `08:01:57Z` | 同上 |
| 卷 `looma-zervi_pgdata.CreatedAt` | `2026-09-28T14:51:32+08:00` | **同值（未变）** | 数据面**不在容器里**，重建无损 |
| `tables / views / rows` | `57 / 1 / 58392` | **`57 / 1 / 58392`** | 逐项一致 |
| 业务数据抽查 | `poems=58059`、`poems_id_seq=78644/true` | 同值 | 未丢未变 |
| 新守卫（D1b+） | — | `pgvector ready after 2s` → `tables=57 (expect >=55)` → **`GUARD_PASSED`** | 断言可跑通 |
| 依赖链旁证 | — | `looma-redis` 同被 `down` 删除，但 `up -d … backend` 时由 `depends_on: [redis]` **自动拉起** | 印证 D1b 注中「为何 redis 没死」 |
| backend | `healthy` | `healthy`（1s 内恢复；`/health` 仍 `a51ff19` —— 复演不写 marker，符合预期） | 业务零感知 |

#### ③ 运维配置实测（engine `29.1.3` 的坑）

- `logging`：容器 `LogConfig=json-file map[max-size:10m max-file:3]` **已生效** ✅
- `stop_grace_period: 60s`：**`docker inspect` 里查不到 `StopTimeout` 字段**。这**不是没生效**，而是 **engine 29.1.3 不输出该字段**：
  - 对照 A：`docker run --stop-timeout 60` 的临时容器 → inspect **同样无该键**（`key_present=False`）
  - 对照 B（行为学，决定性）：忽略 `SIGTERM` 的容器 + `--stop-timeout 25` → `docker stop` 实测 **25s**；compose 版 `stop_grace_period: 20s` → `docker compose stop` 实测 **20s** ✅
  - ⇒ **以行为为准，不以 inspect 字段为准**；prod 的 60s 确已写入容器配置。
  - 附带：为验证 compose 传参，对**真实** `looma-pgvector` 做过一次 `up -d --no-build --force-recreate pgvector`（仅重建容器、不删卷）
    → 新 id `452a09ca…`，数据同样无损（§5.3② 表内 POST id `d76ed630…` 是复演当场值；截至本文档定稿，线上为 `452a09ca…`，`healthy`）。

#### ④ 端口面审计（公网实测 + 宿主监听面对照）

| 端口 | 公网（本机 `nc -z`） | 宿主绑定（`ss -lntp`） | 判定 |
|---|---|---|---|
| 22 / 80 / 443 | **OPEN** | `0.0.0.0` | 预期开放 |
| 5200 backend | REFUSED | `0.0.0.0:5200` | **仅靠安全组挡** |
| 6379 redis | REFUSED | `0.0.0.0:6379` | **仅靠安全组挡**，且实测 **`requirepass` 为空 + `protected-mode no`** ⇒ 安全组一旦被放开即裸奔 |
| 8000 chromadb | REFUSED | `0.0.0.0:8000` | **仅靠安全组挡** |
| 5433 pg | REFUSED | **`127.0.0.1:5433`** | 双保险：宿主只在回环监听，**安全组即使误放行也连不上** ⇒ D3 属「清冗余规则」，非止血 |
| 5432 / 3306 | REFUSED | 未监听 | 正常 |

> **建议（未执行，待你定）**：① 把 `docker-compose.yml` 里 `5200/6379/8000` 的映射一并收窄为 `127.0.0.1:…`
> （compose 内部互通走 `looma-net`，宿主回环足够；**改前先确认 nginx upstream 指向的是 `127.0.0.1:5200` 而非公网 IP**）；
> ② 给 Redis 加 `requirepass`（需同步 backend 的 Redis 配置）。两者都是「安全组之外的第二道锁」。

---

## 6. 数据搬运设计（SQLite → PG，零新依赖）

| 决策 | 取值 | 理由 |
|---|---|---|
| 工具形态 | `backend/scripts/export_sqlite_to_pg.py`（**纯 stdlib**） | 仓库零 PG 驱动；宿主无 psql；只"生成 SQL"，不连库 |
| 结构来源 | SQLite `PRAGMA`（表/列/索引/外键/触发器） | 现网真实结构即真源，**不解析 DDL 文本**，不依赖过期的 `genzltd_schema_v0.2.sql` |
| 类型映射 | `INTEGER→bigint`、`TEXT→text`、`REAL→double precision`、`BLOB→bytea` | **保真优先**：SQLite 时间戳是 TEXT ISO 串就保持 `text`，不擅自升级 `timestamptz`（避免与 `manager.py` 读写语义分叉） |
| 自增 | 单列整数主键 → `bigint GENERATED BY DEFAULT AS IDENTITY` + 末尾 `setval(max)` | 兼容显式 id 与自动 id（SQLite 17 表用了 `AUTOINCREMENT`） |
| 装载顺序 | 表 → 索引 → **FK 统一后置**（`ALTER TABLE … ADD CONSTRAINT`） | PG 的 `REFERENCES` 要求目标表已存在，否则按字母序会撞 `narrative_sessions does not exist` |
| 数据格式 | `INSERT`（按 200 行/语句分批，NULL 无损，`bytes→bytea` hex） | 不依赖服务端文件与 `COPY` 权限；`data.sql` 可 `-f -` 从 stdin 喂 |
| 触发器 | 枚举类自动翻译成 `CHECK`（输出 `constraints.sql`，**数据装载后**执行） | 保留业务规则；遗留坏值会在这一步暴露，属预期信息 |
| 幂等 | `schema.sql` 默认先 `DROP TABLE IF EXISTS … CASCADE`（`--no-drop` 关闭） | 可反复重放 |

### 生产执行序列（阶段 4/5 展开）

```bash
# ① 快照（脚本会检测 -wal；活动库必须先快照）
docker exec looma-backend cp /app/data/looma.db /tmp/looma-snapshot.db
docker cp looma-backend:/tmp/looma-snapshot.db /tmp/looma-snapshot.db

# ② 生成（脚本随代码部署，已在 /home/ubuntu/looma-zervi/backend/scripts/）
cd /home/ubuntu/looma-zervi
python3 backend/scripts/export_sqlite_to_pg.py \
    --sqlite /tmp/looma-snapshot.db --out /tmp/genzltd --immutable

# ③ 灌入（宿主无 psql → 全部走 docker exec；-f - 用 stdin 免落地）
docker exec -i looma-pgvector psql -U looma -d genzltd -v ON_ERROR_STOP=1 -q -f - < /tmp/genzltd/schema.sql
docker exec -i looma-pgvector psql -U looma -d genzltd -v ON_ERROR_STOP=1 -q -f - < /tmp/genzltd/data.sql
docker exec -i looma-pgvector psql -U looma -d genzltd -v ON_ERROR_STOP=1 -q -f - < /tmp/genzltd/constraints.sql

# ④ 对拍
docker exec -i looma-pgvector psql -U looma -d genzltd -At -F'|' -f - < /tmp/genzltd/verify.sql | sort > /tmp/pg_counts.tsv
python3 - <<'PY' | sort > /tmp/sqlite_counts.tsv      # 或直接看 report.md 的行数列
import sqlite3; c=sqlite3.connect('/tmp/looma-snapshot.db')
for (n,) in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
    print(f"{n}|{c.execute('select count(*) from \\"%s\\"' % n).fetchone()[0]}")
PY
diff /tmp/sqlite_counts.tsv /tmp/pg_counts.tsv && echo '✅ 行数一致'
```

---

## 7. 回滚（本方案的核心风险论据）

| 情形 | 回滚动作 | 业务影响 |
|---|---|---|
| 阶段 1 后想撤回 | 无需动作（旧容器已无数据） | 无 |
| 阶段 3 起错版本 | `docker compose -p looma-zervi -f docker/docker-compose.yml rm -sf pgvector` + 回滚 D1 提交 | **无**：backend 仍走 SQLite，PG 无人读 |
| 数据灌错 | `dropdb`/重建容器（`docker volume rm looma-zervi_pgdata`）；源 SQLite 未动 | 无 |
| 需彻底放弃 | 撤销 D1/D4、删 `docker/.env`、删卷 | 无 |

> **前提保持**：本方案**不改** `DATABASE_PATH`、不改 `manager.py`、不引入 PG 驱动 —— PG 是**旁挂数据面**。

---

## 8. 风险与限制

| # | 风险 / 限制 | 处置 |
|---|---|---|
| 1 | 生产 `backend/.env` **无 PG 键**（实测 12 行，无 `PG_*`） | 本方案不让 backend 读 PG；`PG_*` 待 P2 决策后再加（§9） |
| 2 | `docker/.env` 缺 `POSTGRES_PASSWORD` 会让 compose **起不来** | 这是**有意的快速失败**；故 D2 必须先于 D1 合入 |
| 3 | 3 条映射告警（2 部分索引 + 1 默认值） | 已在 `report.md` 列明；部分索引按需人工补 `WHERE` |
| 4 | `poems` 单表 58,059 行占绝大多数数据 | 已验证 21MB `data.sql` 装载 rc=0；`--batch` 可调 |
| 5 | 安全组在**控制台**，机内改不动 | D3 列为独立待办，未完成前 `ports` 已只绑 127.0.0.1（双保险） |
| 6 | 时间戳仍是 text（ISO 串） | **有意**；将来若要 `timestamptz` 需另出迁移（会动语义，须单独评审） |
| 7 | SQLite 的 `TEXT PRIMARY KEY` 允许 NULL，PG 主键隐含 `NOT NULL` | **有意收紧**（实测：缺 id 的插入会被 PG 拒）。**生产快照 `users` 10 行全部有 id**（本机预演副本为 43 行），故装载无损；将来若要"容忍空 id"须显式去掉 PK |
| 8 | SQLite 声明 FK 但默认**不强制**（`PRAGMA foreign_keys` 默认 off） | PG 侧 FK 是**真约束**；本次实测 58,609 行提交时全部通过 → 现网数据自洽，不存在孤儿行 |

---

## 9. P2 前置决策（本方案不擅自决定）

backend 容器**既无 psycopg 也无 psql**（实测 `docker exec looma-backend sh -c 'which psql'` 为空），
所以 `/v1/catalog/*` 读 PG 有三条路，**必须在 P2 开工前定**：

| 方案 | 做法 | 代价 |
|---|---|---|
| **i** 加驱动 | `requirements.txt` 加 `psycopg[binary]`，catalog 路由直连 `pgvector:5432`（同 `looma-net`） | 破坏"零新增依赖"约定；需 rebuild 镜像 |
| **ii** 读 SQLite 镜像（**推荐**） | `tenants`/`tenant_shelf_items` 同时落 SQLite（`migrate_driver_multitenant.py`），catalog 读 SQLite；PG 作离线真源/对账 | PG 与 SQLite 需双写（由 CLI/脚本保证），存在最终一致窗口 |
| **iii** 容器内调 docker exec | 把 docker socket 挂进 backend | ❌ 安全上不可接受，**禁止** |

> **现状（2026-09-28 实测，影响选项 i 的代价）**：重建后的 `looma-pgvector` 已是 `looma-zervi_looma-net`
> 的成员（IP `172.18.0.5`，DNS 别名 **`pgvector`** 与 backend **同网**）⇒ 若选 **i**，DSN 直接用
> `postgresql://looma:<新密码>@pgvector:5432/genzltd`，**无需改 compose、无需暴露宿主端口**，
> 代价只剩"加依赖 + rebuild 镜像"这一项。backend 容器内仍**无 psycopg 也无 psql**（实测），此结论未变。
>
> **通路已实测（2026-09-28 终验）**：在 `looma-backend` 容器内执行
> `socket.create_connection(('pgvector', 5432), 3)` → **`DNS+TCP OK -> ('172.18.0.5', 5432)`**
> ⇒ **网络/DNS 面已通**（不依赖任何新依赖即可验证）。选 **i** 后只剩两件事：① `requirements.txt` 加驱动并 rebuild；
> ② 把凭据注入 backend（`PG_*` 或 DSN），**勿复用 PG 容器 env 里那份明文**。

---

## 10. 验收清单（执行完逐项打勾）

- [x] `docker ps` 显示 `looma-pgvector` 且端口为 **`127.0.0.1:5433->5432/tcp`**（不再是 `0.0.0.0`）· `healthy`
- [x] `docker exec looma-pgvector psql -U looma -l` 列出 **`genzltd`**
- [x] `\dt` 表数 = **57**（SQLite 55 + 联邦骨架 2）· 视图 1（`v_catalog_tenants`）
- [x] 外机 `nc -z -w4 1.14.202.161 5433` → **REFUSED**（容器绑定已收口；安全组 D3 仍待控制台收窄）
- [x] `verify.sql` 对拍 `diff` 为空（**55/55 逐表一致**，58,392 行）
- [x] `migrate_tenants_pg.py` 重跑幂等（第二次全「已存在，跳过」）
- [x] 源生产库未被动过：快照用 `sqlite3.backup()`，`looma.db` mtime 保持 `Sep 25 00:14`
- [x] `docker volume inspect looma-zervi_pgdata` 存在（容器 PGDATA 落于此，不再在仓库树内）
- [x] **仓库树内已无 `data/pgdata`**（实测 `ls -ld /home/ubuntu/looma-zervi/data/pgdata` → `No such file or directory`）⇒ R1/R3 彻底消除
- [x] backend 业务回归：`curl -s http://127.0.0.1:5200/health` → `status: ok`（`git_commit a51ff19`），业务零感知
- [x] 部署后 PG 容器**仍在**且数据未丢 —— **已用同命令复演实测**（§5.3②：容器 `436db82e…`→`d76ed630…` 重建、卷 `CreatedAt` 未变、`57 表/1 视图/58,392 行` 逐项一致）；CI 真实部署路径因平台阻断未执行（§5.3①），修复后重跑即可自动复验
- [x] 新增 **D1b+ 守卫**实测可跑通（输出 `GUARD_PASSED`）——真实部署时会在 `up` 之后自动断言「PG 在跑 + `pg_isready` 就绪 + `genzltd` 表数 ≥ 55」，任一不满足即部署失败
- [ ] D3：腾讯云控制台把 `5433` 入站规则从 `0.0.0.0/0` 收窄到管理网段/删除（**唯一剩余人工项**；实测公网 5433 已 REFUSED，该规则当前**无实际暴露**，删除属清冗余）
- [ ] 建议（非本方案范围，见 §5.3④）：`5200/6379/8000` 宿主映射收窄至 `127.0.0.1` + 给 Redis 加 `requirepass`
- [ ] 待人工：修复 CI（Actions 写端点 404 / 作业 `steps=0` 秒败），重跑 Deploy 以在真实路径上复验 D1b+（§5.3①）
- [ ] 可选：`docker exec looma-pgvector psql -U looma -d genzltd -c 'CREATE EXTENSION IF NOT EXISTS vector'`（镜像已带，本次未启用）

---

## 11. 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-09-28 | 1.2 | **D1b 实测 + 推流**：`push main` 完成（`d522301`/`2193b24`/`3bb0c35`），因当日 CI 被平台阻断（5 连 `steps=0` 秒败，同签名既存于 09-23）改用**同命令复演**实测 D1b：`compose down -p looma-zervi` 真删 `looma-pgvector`（全状态计数 1→0），`up` 列表把它拉回 ⇒ 容器 id 变更而卷 `CreatedAt` 未变、`57 表/1 视图/58,392 行` 逐项一致。新增 **D1b+ 守卫**（`deploy.yml` 部署后断言 PG 存活 + `pg_isready` + 表数 ≥ 55）与 **pgvector 优雅停机 60s / 日志轮转**；实测 engine 29.1.3 的 `docker inspect` **不输出** `StopTimeout`，改用行为学验证 compose 配置真实生效（`--stop-timeout 25` → `stop` 实测 25s；compose `20s` → 实测 20s）。补记端口面审计：公网仅 `22/80/443`，`5200/6379/8000` 仅靠安全组挡且 Redis 无认证（§5.3） |
| 2026-09-28 | 1.1 | **执行完成**：D1/D1b/D2/D4 落地并生产实跑（§5.2）。新增 **D1b**（执行中发现：`deploy.yml` 的 `compose down -p looma-zervi` 会删掉项目内全部容器，`up` 列表不含 `pgvector` 就会"部署一次死一次"）。`genzltd` 迁入 **55 表 / 58,392 行**（55/55 对拍一致 · 172 索引 · 55 外键 · 17 identity 对齐），P1 联邦骨架 APPLY 且幂等复跑通过；公网 5433 已 REFUSED。仅余 D3 安全组（控制台） |
| 2026-09-28 | 1.0 | 首版：现场取证（§1）、根因 R1–R5（§2）、目标态（§3）、D1–D4 diff（§4）、执行步骤（§5）、搬运设计（§6）、回滚（§7）、风险（§8）、P2 前置决策（§9）、验收（§10）；**阶段 0 已实测通过**（§5.1） |



