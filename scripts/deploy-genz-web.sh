#!/usr/bin/env bash
# Build and deploy genz-web (Vite React SPA) to /var/www/genz-web
#
#   cd /opt/looma-zervi/frontend && pnpm install && pnpm build:genz-web
#   bash scripts/deploy-genz-web.sh

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/looma-zervi}"
GENZ_WEB_DIST="${APP_DIR}/frontend/packages/genz-web/dist"
GENZ_WEB_DEST="/var/www/genz-web"

if [ ! -d "${GENZ_WEB_DIST}" ]; then
    echo "Missing ${GENZ_WEB_DIST}. Run: cd ${APP_DIR}/frontend && pnpm install && pnpm build:genz-web" >&2
    exit 1
fi

mkdir -p "${GENZ_WEB_DEST}"
rsync -a --delete "${GENZ_WEB_DIST}/" "${GENZ_WEB_DEST}/"

nginx -t && systemctl reload nginx

echo "genz-web deployed to ${GENZ_WEB_DEST}"
echo "Verify: curl -sI https://genz.ltd/ | head -1"
