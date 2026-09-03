# 部署审计与孤儿差异固化（2026-09-03）

> 范围：P1–P4 部署收口。每端验收口径 = `health.git_commit == 目标 SHA`；
> 孤儿 diff 审计固化（防 CI `rsync --delete` 把端上活文件/本地补丁回退）。
> 关联部署线：GitHub `main`（GenzLTD/looma-zervi）→ 腾讯 + 天翼；
> `release/overseas`（overseas-v* tag）→ Vultr。gitee origin 为镜像，滞后属常态。

## 1. 各端验收表（health git_commit == 目标 SHA）

| 端 | 目标 SHA | health git_commit | 部署方式 | 结论 |
|---|---|---|---|---|
| 腾讯 1.14.202.161 (:5200) | `9eee467` | `9eee467` | deploy job（rsync 全仓 + marker 启动前 + build） | ✅ |
| 天翼 14.29.216.219 (:5203) | `9eee467` | `9eee467` | deploy-tianyi job（rsync backend + marker 启动前 + `--no-build --force-recreate`） | ✅ |
| Vultr 139.180.184.25 (:5200) | `2dbd67a` | `2dbd67a` | deploy-overseas job（overseas-v3.1.11，build-arg `PIP_INDEX_URL=https://pypi.org/simple`） | ✅ |
| gfcc（P2 关联，独立仓） | `bac4e86` | —（gfcc-kernel :5211 health 200） | git checkout + systemctl restart gfcc-kernel | ✅ |

## 2. 孤儿 diff 审计（三孤儿差异判定）

背景：CI `rsync --delete` 以仓库内容为准同步端上目录。若端上 git 树存在
本地未提交补丁（`M`）或仓库未跟踪文件（`??`），rsync 会回退/删除它们——
必须在部署前判定每份孤儿差异「已被 main 吸收 / 冗余 / 端上特定需保留」。
天翼已 `git reset --hard 9eee467` 对齐，结论如下：

| 孤儿文件 | 判定 | 处置 |
|---|---|---|
| `backend/src/payment/plans.py`（R1：`DEPLOY_ALIASES={SG:US}` + 非 zh/en 语言统一 USD 兜底） | **已被 main 吸收**（`bed691c` 固化入 main） | `reset --hard` 覆盖无损；线上 R1 行为保持 |
| `backend/src/db/manager.py`（本地 970 行补丁中冗余部分） | **冗余**（上游已含等价实现/无需保留） | `reset --hard` 覆盖无损 |
| `backend/src/rag/chroma_client.py`（天翼特定适配 + 若干 `.bak-*` 备份） | **天翼特定·覆盖无损**（`.bak-*` 已进 tianyi job rsync excludes，主文件改动与仓库对齐） | 保留 `.bak-*`；主文件随仓库 |

腾讯孤儿残留：历史部署产生的孤儿树/文件已 `sudo mv` 归档为
`/opt/looma-zervi.orphan-archive-20260903`，部署目录恢复干净。

## 3. 天翼 untracked 活文件（保留清单，勿误删）

天翼 `docker/` 下 untracked 文件均**不在 rsync 同步范围**
（deploy-tianyi job 只同步 `backend/`，不碰 `docker/`），属安全活文件：

- `docker/docker-compose.tianyi.full.yml` — **活文件**，deploy-tianyi job 目标
  compose（secret `TIANYI_COMPOSE_FILE` 指向），缺失会导致部署失败
- `docker/RESTART_天翼.md` — 运维笔记
- `docker/docker-compose.tianyi.full.yml.bak.{20260827,20260901_144446,qcc}`、
  `docker/docker-compose.yml.bak.20260827` — 历史备份
- `backend/git_commit.txt` — CI 每次写入的 marker（已在 tianyi job rsync
  excludes），非手工维护

## 4. marker 顺序修复要点（71ae357）

`_git_commit()` 为**进程级缓存**（env → `git_commit.txt` → `git rev-parse`
三级回退，进程存活期间不重读）。腾讯端曾因 marker 写在 restart 之后，
`git_commit=unknown`。修复 = **marker 必须写于容器启动前**：

- 腾讯 deploy job：`Write git_commit marker (main SHA, before container start)`
  步骤位于 `Build & restart Docker backend` 之前
- 天翼 deploy-tianyi job：同一步骤内先写 `git_commit.txt` 再
  `up -d --no-build --force-recreate backend`
- Vultr（overseas）：deploy-overseas.yml 同步前置

## 5. 防护固化（长期生效）

- deploy.yml `paths-ignore` 含 `docs/**`、`**.md` → 本文档推送不触发部署
- 腾讯 job rsync excludes：`.git` / `.env` / `node_modules` / `backend/data` 等
- tianyi job rsync excludes 追加：`backend/poems_all.json.gz`、
  `backend/open_items.json`、`backend/git_commit.txt`、
  `backend/src/rag/chroma_client.py.bak-*`
- 后续部署若见 `git_commit` 与目标 SHA 不符 → 先查 marker 顺序，
  再查端上孤儿 diff（本文档 §2 判定流程）

## 6. 待办/边界

- gitee 镜像滞后（origin main = 旧线），如需对齐另行 push
- Vultr build 走 aliyun pip 镜像卡死的彻底解 = Dockerfile
  `ARG PIP_INDEX_URL` 可配置（`9eee467`），overseas 构建传 pypi.org；
  腾讯/天翼默认 aliyun 镜像不受影响
