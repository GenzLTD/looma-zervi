#!/usr/bin/env bash
# Sync local poetry ChromaDB + seed SQLite poems onto Vultr overseas host.
#
# Usage:
#   SSH_HOST=139.180.184.25 SSH_USER=root SSH_KEY=~/.ssh/your_key \
#     ./scripts/sync-poetry-overseas.sh
#
# Optional:
#   DEPLOY_PATH=/opt/looma-zervi
#   SKIP_VOLUME=1   — only rsync files, do not seed docker volume / restart
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH_HOST="${SSH_HOST:-139.180.184.25}"
SSH_USER="${SSH_USER:-root}"
SSH_KEY="${SSH_KEY:-}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/looma-zervi}"
LOCAL_POETRY="${ROOT}/data/poetry_full"

if [ ! -d "${LOCAL_POETRY}" ]; then
  echo "Missing ${LOCAL_POETRY}. Build or unpack poetry_full first." >&2
  exit 1
fi

SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)
if [ -n "${SSH_KEY}" ]; then
  SSH_OPTS+=(-i "${SSH_KEY}")
fi
SSH_TARGET="${SSH_USER}@${SSH_HOST}"
RSYNC_SSH="ssh ${SSH_OPTS[*]}"

echo "=== rsync poetry_full → ${SSH_TARGET}:${DEPLOY_PATH}/data/poetry_full ==="
ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" "mkdir -p ${DEPLOY_PATH}/data/poetry_full"
rsync -avz --progress -e "${RSYNC_SSH}" \
  "${LOCAL_POETRY}/" \
  "${SSH_TARGET}:${DEPLOY_PATH}/data/poetry_full/"

if [ "${SKIP_VOLUME:-0}" = "1" ]; then
  echo "SKIP_VOLUME=1 — done (files only)."
  exit 0
fi

echo "=== Seed docker volume looma-zervi_poetry-data + restart chromadb/backend ==="
ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" bash -s <<EOF
set -euo pipefail
DEPLOY_PATH="${DEPLOY_PATH}"
VOLUME_NAME="looma-zervi_poetry-data"
COMPOSE="docker compose -f \${DEPLOY_PATH}/docker/docker-compose.yml -p looma-zervi"

docker run --rm \
  -v \${VOLUME_NAME}:/dest \
  -v \${DEPLOY_PATH}/data/poetry_full:/src:ro \
  alpine sh -c 'rm -rf /dest/* /dest/.[!.]* 2>/dev/null || true; cp -a /src/. /dest/'

# If looma.db has zero poems, run import inside backend container when script exists
if docker ps --format '{{.Names}}' | grep -q '^looma-backend\$'; then
  docker exec looma-backend python -c "
from src.db.manager import DatabaseManager
import os
db = DatabaseManager(os.environ.get('DATABASE_PATH', '/app/data/looma.db'))
db.init_schema()
print('poems=', db.count_poems())
" || true
fi

\${COMPOSE} up -d --no-build --force-recreate chromadb backend
echo "=== poetry sync complete ==="
EOF

echo "Verify: curl -s https://api.genz.ltd/v1/poetry/stats"
