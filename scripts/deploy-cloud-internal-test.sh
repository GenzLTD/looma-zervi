#!/usr/bin/env bash
# deploy-cloud-internal-test.sh — 备案前：本地 → 云服务器 IP 内测部署
#
# 内测云 IP: 1.14.202.161（勿用 47.115.168.107）
#
# SSH（PEM）:
#   SSH_KEY=~/path/to/key.pem SSH_USER=ubuntu ./scripts/deploy-cloud-internal-test.sh
#   或在 ~/.ssh/config 配置 Host looma-cloud 后:
#   SSH_ALIAS=looma-cloud ./scripts/deploy-cloud-internal-test.sh
#   参考: scripts/ssh-looma-cloud.config.example
#
# 安全组: 仅放行 TCP 80 即可（Nginx → 127.0.0.1:5200，不必公网开放 5200）
#
# 可选环境变量:
#   DEPLOY_PATH=/opt/looma-zervi
#   SKIP_POETRY=1          跳过诗词库 rsync（约 160MB）
#   SKIP_ENV=1             不覆盖服务器 backend/.env
#   SKIP_NGINX=1           跳过 Nginx 注入（服务器已配好反代时用）
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=scripts/lib/cloud-ssh-env.sh
source "$ROOT/scripts/lib/cloud-ssh-env.sh"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log()  { echo -e "${GREEN}[deploy]${NC} $1"; }
warn() { echo -e "${YELLOW}[deploy]${NC} $1"; }
err()  { echo -e "${RED}[deploy]${NC} $1"; exit 1; }

if [ ! -f "$ROOT/pyproject.toml" ]; then
  err "请在仓库根目录运行"
fi

cloud_ssh_preflight || err "SSH 连接失败。请设置 SSH_KEY=/path/to/key.pem 或 SSH_ALIAS=looma-cloud"

log "目标: ${SSH_TARGET}:${DEPLOY_PATH}"

ssh_cloud "sudo mkdir -p ${DEPLOY_PATH} /var/www/planetx/dist /var/www/saas/dist && sudo chown -R \$(whoami):\$(whoami) ${DEPLOY_PATH} 2>/dev/null || mkdir -p ${DEPLOY_PATH}"

# 云端 rsync --exclude='.git'，无 git 历史 — 写入 git_commit.txt 随代码同步，
# 供 /health 的 git_commit 字段读取（backend/src/app.py _git_commit 三级回退）。
GIT_COMMIT_SHORT="$(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo unknown)"
printf '%s\n' "$GIT_COMMIT_SHORT" > "$ROOT/backend/git_commit.txt"
log "记录 commit: ${GIT_COMMIT_SHORT} → backend/git_commit.txt"

log "同步代码..."
rsync -avz -e "$RSYNC_SSH" --delete \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='frontend/node_modules' \
  --exclude='**/__pycache__' \
  --exclude='**/*.pyc' \
  --exclude='backend/venv' \
  --exclude='backend/data' \
  --exclude='.env' \
  --exclude='backend/.env' \
  --exclude='data/poetry_full' \
  --exclude='.pnpm-store' \
  "$ROOT/" "${SSH_TARGET}:${DEPLOY_PATH}/"

if [ "${SKIP_POETRY:-0}" != "1" ] && [ -d "$ROOT/data/poetry_full" ]; then
  log "同步诗词向量库 data/poetry_full ..."
  rsync -avz -e "$RSYNC_SSH" \
    "$ROOT/data/poetry_full/" \
    "${SSH_TARGET}:${DEPLOY_PATH}/data/poetry_full/"
else
  warn "跳过诗词库同步（无本地 data/poetry_full 或 SKIP_POETRY=1）"
fi

if [ "${SKIP_ENV:-0}" != "1" ]; then
  if [ -f "$ROOT/backend/.env" ]; then
    log "上传 backend/.env ..."
    scp_cloud "$ROOT/backend/.env" "${SSH_TARGET}:${DEPLOY_PATH}/backend/.env"
  elif [ -f "$ROOT/.env.example" ]; then
    warn "本机无 backend/.env，服务器将从 .env.example 生成"
  fi
fi

log "校正云路径（POETRY / DATABASE 绝对路径）..."
ssh_cloud "bash -s" << REMOTE_PATHS
set -euo pipefail
ENV_FILE="${DEPLOY_PATH}/backend/.env"
DEPLOY_PATH="${DEPLOY_PATH}"
touch "\$ENV_FILE"
set_kv() {
  local key="\$1" val="\$2"
  if grep -q "^\${key}=" "\$ENV_FILE"; then
    sed -i "s|^\${key}=.*|\${key}=\${val}|" "\$ENV_FILE"
  else
    echo "\${key}=\${val}" >> "\$ENV_FILE"
  fi
}
set_kv POETRY_CHROMA_PATH "\${DEPLOY_PATH}/data/poetry_full"
set_kv DATABASE_PATH "\${DEPLOY_PATH}/backend/data/looma.db"
REMOTE_PATHS

log "远程安装依赖并启动 gunicorn..."
ssh_cloud "bash -s" << REMOTE
set -euo pipefail
DEPLOY_PATH="${DEPLOY_PATH}"
cd "\${DEPLOY_PATH}/backend"

if [ ! -f .env ]; then
  cp ../.env.example .env 2>/dev/null || cp .env.example .env
  cat >> .env << EOF

# cloud internal test overrides
FLASK_ENV=production
FLASK_PORT=5200
WECHAT_DEV_MODE=true
POETRY_CHROMA_PATH=\${DEPLOY_PATH}/data/poetry_full
DATABASE_PATH=\${DEPLOY_PATH}/backend/data/looma.db
CORS_ORIGINS=http://localhost:5173,http://localhost:5174,http://${CLOUD_HOST}
EOF
  echo "已生成 backend/.env — 请确保 DEEPSEEK_API_KEY 有效"
fi

mkdir -p data "\${DEPLOY_PATH}/data" "\${DEPLOY_PATH}/logs"

PY=\$(command -v python3.11 || command -v python3.10 || command -v python3)
echo "Python: \$(\$PY --version)"
if ! \$PY -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  echo "需要 Python 3.10+，当前: \$(\$PY --version 2>&1)"
  exit 1
fi

if [ ! -d venv ]; then
  \$PY -m venv venv
fi
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt gunicorn

# 停止占用 5200 的旧 Docker 后端（端口映射错误时会导致 502）
if command -v docker >/dev/null 2>&1; then
  sudo docker stop looma-backend 2>/dev/null || true
  sleep 2
fi

if command -v lsof >/dev/null 2>&1; then
  pids=\$(lsof -t -i :5200 2>/dev/null || true)
  [ -n "\$pids" ] && kill \$pids 2>/dev/null || true
  sleep 1
fi

export FLASK_ENV=production
export PYTHONPATH="\${DEPLOY_PATH}/backend:\${PYTHONPATH:-}"
nohup ./start_gunicorn.sh >> "\${DEPLOY_PATH}/logs/gunicorn.log" 2>&1 &
sleep 4
curl -sf http://127.0.0.1:5200/health || { tail -40 "\${DEPLOY_PATH}/logs/gunicorn.log"; exit 1; }
echo "gunicorn :5200 OK"
curl -sf http://127.0.0.1:5200/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('  git_commit:', d.get('git_commit'))" 2>/dev/null || true

if [ ! -s "\${DEPLOY_PATH}/backend/data/looma.db" ] || ! sqlite3 "\${DEPLOY_PATH}/backend/data/looma.db" "SELECT 1 FROM poems LIMIT 1;" 2>/dev/null; then
  echo "导入诗词 SQLite（browse/stats/random）..."
  python scripts/import_poetry.py \\
    --source-dir "\${DEPLOY_PATH}/data/poetry_full" \\
    --db-path "\${DEPLOY_PATH}/backend/data/looma.db" \\
    --batch-size 1000
fi
REMOTE

if [ "${SKIP_NGINX:-0}" != "1" ]; then
  log "配置 Nginx（/v1/ 与 /health → Looma :5200）..."
  ssh_cloud "bash -s" << 'NGINX'
set -euo pipefail

inject_looma_locations() {
  local f="$1"
  grep -q 'looma-api internal test' "$f" 2>/dev/null && return 0
  grep -q 'proxy_pass http://127.0.0.1:5200' "$f" 2>/dev/null && return 0
  sudo sed -i '/location \/ {/i\
    # looma-api internal test\
    location /v1/ {\
        proxy_pass http://127.0.0.1:5200;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_set_header X-Forwarded-Proto $scheme;\
        proxy_read_timeout 120s;\
    }\
    location = /health {\
        proxy_pass http://127.0.0.1:5200/health;\
        proxy_set_header Host $host;\
    }\
' "$f"
  echo "injected into $f"
}

for f in /etc/nginx/sites-enabled/default /etc/nginx/conf.d/*.conf; do
  [ -f "$f" ] || continue
  inject_looma_locations "$f" || true
done

sudo nginx -t
sudo nginx -s reload
echo "nginx reloaded"
NGINX
else
  warn "SKIP_NGINX=1 — 假定 Nginx 已反代 /v1/ 与 /health → :5200"
fi

log "完成。本机验证:"
echo "  ./scripts/test-cloud-connectivity.sh"
