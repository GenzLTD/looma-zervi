# 标准博主模板 · 克隆手册

> 目标：把「陆游实例」当母版，李白 / 白居易照抄复制，各自起一套独立实例。
> 原则：**代码一份、博主身份参数化、货各配各的**。不共用基础设施，不重构母版。

---

## 0. 三件套定位

| 文件 | 作用 | 自动/手工 |
|------|------|-----------|
| `bloggers/*.env` | 博主参数（单一事实来源） | 手工填 |
| `scripts/clone-blogger.sh` | 从母版生成域名/CORS/JWT 配置 | **自动** |
| `scripts/poetry-split-by-author.py` | 诗词库按作者切分 | **自动** |
| 人格题 / 品牌皮 | 「货」，每博主定制 | 手工（见 §3） |
| `docs/BLOGGER_CLONE_GUIDE.md` | 本手册 | — |

**不碰的东西**：云服务器形态（Vultr/腾讯/天翼/裸机都行，脚本只产配置不绑机器）、
后端业务代码（`config.py` 已 100% 环境变量化，天然可复制）。

---

## 1. 快速开始（30 分钟起一套）

```bash
# ① 复制参数模板，改成李白
cp bloggers/blogger.template.env bloggers/libai.env
vim bloggers/libai.env    # 填 BLOGGER_NAME=李白 / BLOGGER_SLUG=libai / MAIN_DOMAIN=... / JWT_SECRET

# ② 生成域名/CORS/JWT 配置
bash scripts/clone-blogger.sh bloggers/libai.env
# 产物：clones/libai/{nginx.conf, deploy.sh, backend.env, README.md}

# ③ 配货（见 §3）：诗词库切分 + 人格题 + 品牌皮
python scripts/poetry-split-by-author.py \
    --source-dir data/poetry_full \
    --target-dir data/poetry_full_libai \
    --author 李白

# ④ 部署（把 clones/libai 上传到目标机，见 §4）
```

---

## 2. 参数文件字段

见 `bloggers/blogger.template.env`（含逐字段注释）。要点：

- **必填**：`BLOGGER_NAME` / `BLOGGER_SLUG` / `MAIN_DOMAIN` / `JWT_SECRET`
- **可留空自动推导**：`WWW_DOMAIN` / `API_DOMAIN` / `APP_DOMAIN` / `TSPACE_DOMAIN`
  （默认分别 = `www./api./app./tspace.` + 主域）
- `JWT_SECRET` 留占位符时脚本自动生成随机值（`openssl rand -hex 32`）

`clone-blogger.sh` 的原理：**不做模板副本**，直接从母版现有文件
`docker/nginx.conf`、`scripts/deploy-overseas.sh`、`backend/.env.example`
用 sed 做「母版域名 `genz.ltd` → 目标域名」的最长优先替换。母版改了，克隆自动跟随，
不会出现模板漂移。

---

## 3. 各配各的货（三步）

### 货 1 · 诗词库（自动）

陆游全集在 ChromaDB 集合 `poetry_full`（目录 `data/poetry_full`，metadata 有 `author` 字段）。
李白/白居易各自只保留自己的诗：

```bash
python scripts/poetry-split-by-author.py \
    --source-dir data/poetry_full \
    --target-dir data/poetry_full_libai \
    --author 李白            # 精确匹配；加 --contains 走子串匹配（author 含朝代变体时）
```

产出 `data/poetry_full_libai/` 是新的 ChromaDB 目录（集合名仍是 `poetry_full`）。
部署时把它挂载/替换到容器的 `data/poetry_full` 位置即可（见 §4 第 3 步）。
多作者用 `--author 李白,杜甫`；目标目录非空加 `--force`。

### 货 2 · 人格题（手工，前后端各一处真源）

母版人格标签是「星际主题」6 种（星云艺术家/黑洞程序员/…）。李白/白居易要换成自己的主题。
**两处真源必须同步改**：

1. 前端标签 + 文案（单真源）：
   `frontend/packages/shared-core/src/constants/personality.ts`
   → 改 `PERSONALITY_MAP` 里 6 个人格的 `name / emoji / tagline / desc / traits`。
   （key 如 `creative_social` 不要改，是双特质组合的稳定标识）

2. 后端匹配规则：
   `backend/src/api/routes/game_routes.py` L52-78
   → 改 `PERSONALITY_EMOJI` / `COMPLEMENTARY_PERSONALITY` / `MATCH_REASON` 三个字典，
   key 换成新人格名（与前端 `name` 一一对应）。

3. 题库本身（若各博主要自己的题）：
   `frontend/packages/planetx/src/features/quiz/QuizScreen.tsx` + `auth/planetxAuthStore.ts`
   （`QuizQuestion / QuizOption / TraitKey` 定义处）。题目文案逐条替换。

> 只换标签不改题库，可以直接复用母版题库（题不变，只有结果标签变），
> 这是最小改动路径；若要「各配各的题」，再改第 3 步。

### 货 3 · 品牌皮（手工）

1. 主题色：`frontend/packages/planetx/src/brand/tokens.css`（母版是深空星际配色）
2. 品牌文案：全局搜品牌词替换，核心文件在 `frontend/packages/planetx/src/brand/`
   （`components/`、`ui/`）以及各 feature 的文案。

---

## 4. 部署

`clone-blogger.sh` 生成的 `clones/<slug>/` 是完整产物，在目标机（root）上：

```bash
# 1. 上传（或用 git 拉取后取 clones/<slug>/）
scp -r clones/libai root@<目标IP>:/opt/blogger-clone

# 2. 首次部署（装 Docker/nginx/证书 + 拉代码 + 起服务）
cd /opt/blogger-clone && bash deploy.sh

# 3. 诗词库替换为切分后的子库
#    把 data/poetry_full_libai 挂载/复制到 backend 容器的 data/poetry_full

# 4. backend.env 是安全密钥参考，合并进目标机 backend/.env 真实值
```

---

## 5. 验证清单

- [ ] `clones/<slug>/` 里 `grep -rn "genz.ltd"` 无残留（脚本已自动校验，失败会 exit 1）
- [ ] `nginx.conf` 里 server_name 全为目标域名
- [ ] `backend.env` 的 CORS_ORIGINS 含目标四个域
- [ ] 诗词子库条数 = 该作者在全集中的诗数（切分脚本会打印命中数）
- [ ] 前后端人格标签一一对应（`personality.ts` 的 name == `game_routes.py` 的 key）
- [ ] 目标机 `/health` 返回 200、诗词搜索命中该作者的诗

---

## 6. 已知边界（刻意不做）

- **不做多租户**：一套实例 = 一个博主 = 独立 DB / JWT / 域名 / 诗词库 / 人格题。
- **不重构母版**：`nginx.conf` 仍是陆游母版原样，克隆用 sed 派生，不改线上陆游。
- **不绑云形态**：脚本只产配置，不 care 目标是 Vultr/腾讯/天翼/裸机。
- **JWT/SECRET 不入库**：陆游线上真实密钥在 Vultr 的 `backend/.env`，参数文件只放占位。
- **切分不复制向量**：子库查询时现场算 embedding，与母版「sqlite 关键词优先 + chroma 兜底」一致。
