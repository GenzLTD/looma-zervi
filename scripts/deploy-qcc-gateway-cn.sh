#!/usr/bin/env bash
# deploy-qcc-gateway-cn.sh — 在国内云机部署企查查 MCP 反向代理（:8998）
#
# 用法:
#   SSH_KEY=~/.ssh/looma-key.pem ./scripts/deploy-qcc-gateway-cn.sh
#   SSH_ALIAS=looma-cloud ./scripts/deploy-qcc-gateway-cn.sh
#
# 海外后端需设置:
#   QCC_MCP_BASE_URL=http://1.14.202.161:8998/mcp
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=scripts/lib/cloud-ssh-env.sh
source "$ROOT/scripts/lib/cloud-ssh-env.sh"

CONF_SRC="$ROOT/deploy/nginx/qcc-gateway.conf"
[[ -f "$CONF_SRC" ]] || { echo "missing $CONF_SRC" >&2; exit 1; }

cloud_ssh_preflight || exit 1

echo "[qcc-gw] upload nginx config"
scp_cloud "$CONF_SRC" "${SSH_TARGET}:/tmp/qcc-gateway.conf"

ssh_cloud "bash -s" <<'REMOTE'
set -euo pipefail
sudo mv /tmp/qcc-gateway.conf /etc/nginx/sites-available/qcc-gateway
sudo ln -sfn /etc/nginx/sites-available/qcc-gateway /etc/nginx/sites-enabled/qcc-gateway
sudo nginx -t
sudo systemctl reload nginx

# Local firewall: only Vultr SG + loopback (cloud security group should match)
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow from 139.180.184.25 to any port 8998 proto tcp comment 'qcc-gateway-vultr' || true
  sudo ufw allow from 127.0.0.1 to any port 8998 proto tcp comment 'qcc-gateway-local' || true
  # Drop the previous wide-open rule if present
  sudo ufw delete allow 8998/tcp 2>/dev/null || true
  sudo ufw status | head -30 || true
fi

echo "=== local health ==="
curl -sf http://127.0.0.1:8998/health && echo
echo "=== local proxy → QCC (expect 401 without token) ==="
code=$(curl -sS -o /tmp/qcc_gw_head.txt -w '%{http_code}' --connect-timeout 10 --max-time 15 \
  -H 'Accept: text/event-stream' http://127.0.0.1:8998/mcp/company/stream || echo FAIL)
echo "http_code=$code"
head -c 200 /tmp/qcc_gw_head.txt; echo
REMOTE

echo "[qcc-gw] done. Overseas set QCC_MCP_BASE_URL=http://${CLOUD_HOST}:8998/mcp"
echo "[qcc-gw] Ensure cloud security group allows TCP 8998 from Vultr (139.180.184.25)."
