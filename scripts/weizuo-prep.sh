#!/usr/bin/env bash
#
# weizuo-prep.sh — 围坐前准备：Projects(源) → thomas(本地 ServBay) 对齐 + 重启后端
#                    → rsync 天翼云(内测) → 双端 /health git_commit 一致性对比
#
# 用法:
#   ./scripts/weizuo-prep.sh              # 全流程（对齐 + 重启 + 部署 + 对比）
#   ./scripts/weizuo-prep.sh --local      # 只做 thomas 对齐 + 重启（不动云端）
#   ./scripts/weizuo-prep.sh --cloud      # 只做 rsync 天翼 + health 对比
#
# 环境变量:
#   PROJECTS_DIR=~/Projects/looma-zervi   源仓库（唯一改码点）
#   THOMAS_DIR=~/thomas/looma-zervi       ServBay 本地部署副本
#   BRANCH=feat/tianyi-central-chainb     要对齐的分支
#   SKIP_POETRY=1                         跳过诗词库 rsync（透传给 deploy 脚本）
#   SSH_ALIAS=looma-cloud / SSH_KEY=...   云端 SSH（透传给 deploy 脚本）
#
# 前置条件:
#   - Projects 的该分支已 push 到远端（thomas 从远端 fetch 对齐）
#   - 运行前请先停掉 Projects 里占用 :5200 的 dev server（与本脚本冲突）
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/lib/cloud-ssh-env.sh" 2>/dev/null || true

PROJECTS_DIR="${PROJECTS_DIR:-$HOME/Projects/looma-zervi}"
THOMAS_DIR="${THOMAS_DIR:-$HOME/thomas/looma-zervi}"
BRANCH="${BRANCH:-feat/tianyi-central-chainb}"
# 云端入口走域名（nginx 按 server_name 匹配；:5200 与裸 IP:80 均不通；
# 注意 CLOUD_HOST 是部署 IP，不能直接当 API 入口用）
CLOUD_API="${CLOUD_API:-http://api.genz.ltd}"
LOCAL_API="${LOCAL_API:-http://127.0.0.1:5200}"

MODE="${1:-all}"
case "$MODE" in
  --local)  MODE=local ;;
  --cloud)  MODE=cloud ;;
  all)      MODE=all ;;
  *) echo "用法: $0 [--local|--cloud]" >&2; exit 1 ;;
esac

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
section() { echo ""; echo "━━ $1 ━━"; }
pass() { echo -e "${GREEN}✅${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
fail() { echo -e "${RED}❌${NC} $1"; exit 1; }

[ -d "$PROJECTS_DIR/.git" ] || fail "源仓库不存在: $PROJECTS_DIR"
[ -d "$THOMAS_DIR/.git" ]   || fail "thomas 副本不存在: $THOMAS_DIR"

SRC_COMMIT="$(cd "$PROJECTS_DIR" && git rev-parse --short HEAD)"
echo "源(Projects) HEAD = ${SRC_COMMIT} ($BRANCH)"
if [ -n "$(cd "$PROJECTS_DIR" && git status --porcelain)" ]; then
  warn "Projects 有未提交改动 — 云端不会包含它们。确认无遗漏后再开始围坐。"
fi

align_thomas() {
  section "1. thomas 对齐 (${BRANCH})"
  cd "$THOMAS_DIR"
  if [ -n "$(git status --porcelain | grep -v 'backend/.env' || true)" ]; then
    warn "thomas 存在未提交改动（backend/.env 除外）— 继续对齐，将丢弃这些改动"
  fi
  git fetch origin 2>/dev/null || git fetch "$PROJECTS_DIR" "$BRANCH"
  git checkout -B "$BRANCH" "origin/$BRANCH" 2>/dev/null \
    || git checkout -B "$BRANCH" "FETCH_HEAD"
  local thomas_commit
  thomas_commit="$(git rev-parse --short HEAD)"
  if [ "$thomas_commit" != "$SRC_COMMIT" ]; then
    fail "thomas HEAD=${thomas_commit} ≠ 源 ${SRC_COMMIT} — 对齐失败"
  fi
  pass "thomas HEAD = ${thomas_commit}"
}

restart_thomas() {
  section "2. 重启 thomas 后端 (:5200)"
  local pids pid cwd cwd_norm dir_norm
  dir_norm="$(echo "$THOMAS_DIR" | tr '[:upper:]' '[:lower:]')"
  pids="$(lsof -t -i :5200 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    for pid in $pids; do
      cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' || true)"
      # macOS 卷大小写不敏感：归一化后比较，避免 ~/thomas vs ~/THOMAS 误判
      cwd_norm="$(echo "$cwd" | tr '[:upper:]' '[:lower:]')"
      if [ -n "$cwd" ] && [[ "$cwd_norm" != "$dir_norm"* ]]; then
        fail ":5200 被非 thomas 进程占用 (cwd=$cwd) — 请先停止 Projects 的 dev server"
      fi
    done
    echo "→ 停止旧进程 ($pids)"
    kill $pids 2>/dev/null || true
    sleep 1
  fi
  cd "$THOMAS_DIR/backend"
  [ -f ./start_gunicorn.sh ] || fail "thomas 缺少 backend/start_gunicorn.sh"
  nohup ./start_gunicorn.sh >> /tmp/weizuo-thomas-gunicorn.log 2>&1 &
  local ok=1
  for i in $(seq 1 30); do
    if curl -sf "$LOCAL_API/health" >/dev/null 2>&1; then ok=0; break; fi
    sleep 1
  done
  [ "$ok" = "0" ] || fail "thomas 后端启动超时，见 /tmp/weizuo-thomas-gunicorn.log"
  pass "thomas 后端已起: $LOCAL_API/health"
}

deploy_cloud() {
  section "3. rsync 天翼云 (${CLOUD_HOST})"
  [ -f "$THOMAS_DIR/scripts/deploy-cloud-internal-test.sh" ] \
    || fail "thomas 缺少 deploy-cloud-internal-test.sh"
  (cd "$THOMAS_DIR" && ./scripts/deploy-cloud-internal-test.sh)
}

compare_health() {
  section "4. 双端 /health git_commit 对比"
  local local_commit cloud_commit
  local_commit="$(curl -sf --connect-timeout 10 "$LOCAL_API/health" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('git_commit'))")" \
    || fail "本地 health 不可达"
  cloud_commit="$(curl -sf --connect-timeout 15 "$CLOUD_API/health" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('git_commit'))")" \
    || fail "云端 health 不可达: $CLOUD_API （检查安全组 80 / nginx / gunicorn）"
  echo "  源(Projects):  $SRC_COMMIT"
  echo "  本地(thomas):  $local_commit"
  echo "  云端(天翼):    $cloud_commit"
  [ "$local_commit" = "$SRC_COMMIT" ] || fail "本地 commit 与源不一致"
  [ "$cloud_commit" = "$SRC_COMMIT" ] || fail "云端 commit 与源不一致"
  pass "三端 commit 一致 — 可以开始围坐"
}

if [ "$MODE" = "all" ] || [ "$MODE" = "local" ]; then
  align_thomas
  restart_thomas
fi
if [ "$MODE" = "all" ] || [ "$MODE" = "cloud" ]; then
  deploy_cloud
  compare_health
fi

echo ""
pass "围坐准备完成"
