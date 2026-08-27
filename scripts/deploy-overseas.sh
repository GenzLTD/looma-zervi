#!/usr/bin/env bash
# Overseas VPS deployment script for looma-zervi (release/overseas)
# Target: Ubuntu 22.04 LTS, Vultr Singapore
# Domain: genz.ltd (Cloudflare DNS + proxy, SSL mode: Full)
#
# SSL strategy: self-signed cert on origin + Cloudflare Full mode.
# Upgrade to Cloudflare Origin Certificate later for Full (Strict).
#
# Run as root:
#   bash deploy-overseas.sh

set -euo pipefail

DOMAIN="genz.ltd"
API_SUBDOMAIN="api.genz.ltd"
TSPACE_SUBDOMAIN="tspace.genz.ltd"
REPO_URL="https://gitee.com/szbenyx/looma-zervi.git"
BRANCH="release/overseas"
APP_DIR="/opt/looma-zervi"
SSL_DIR="/etc/nginx/ssl"

export DEBIAN_FRONTEND=noninteractive

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

# ============================
# 1. Basic system setup
# ============================
log "Updating system packages..."
apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release software-properties-common ufw git nginx openssl

log "Configuring timezone..."
timedatectl set-timezone Asia/Singapore || true

# ============================
# 2. Docker + Docker Compose
# ============================
log "Installing Docker..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" >/etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

log "Installing docker-compose (standalone)..."
DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep -oP '"tag_name": "\K[^"]+')
curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# ============================
# 3. Self-signed SSL certificate (Cloudflare Full mode)
# ============================
log "Generating self-signed SSL certificate..."
mkdir -p "${SSL_DIR}"
openssl req -x509 -nodes -days 3650 \
    -newkey rsa:2048 \
    -keyout "${SSL_DIR}/privkey.pem" \
    -out "${SSL_DIR}/fullchain.pem" \
    -subj "/C=SG/ST=Singapore/L=Singapore/O=Looma/CN=${DOMAIN}" \
    -addext "subjectAltName=DNS:${DOMAIN},DNS:*.${DOMAIN}" 2>/dev/null
chmod 600 "${SSL_DIR}/privkey.pem"
log "SSL cert generated at ${SSL_DIR}/"

# ============================
# 4. Clone repository
# ============================
log "Cloning repository ${REPO_URL} branch ${BRANCH}..."
if [ -d "${APP_DIR}" ]; then
    log "Directory exists, pulling latest..."
    cd "${APP_DIR}"
    git fetch origin
    git checkout "${BRANCH}" 2>/dev/null || git checkout -b "${BRANCH}" origin/"${BRANCH}"
    git pull origin "${BRANCH}" || true
else
    git clone -b "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
    cd "${APP_DIR}"
fi

# ============================
# 5. Configure environment
# ============================
log "Configuring environment..."
cd "${APP_DIR}"

if [ ! -f "backend/.env" ]; then
    cp backend/.env.example backend/.env
    log "Created backend/.env from example."
fi

# Set Redis storage for rate limiting
sed -i 's|^RATE_LIMIT_STORAGE_URI=.*|RATE_LIMIT_STORAGE_URI=redis://redis:6379/1|' backend/.env

# Set domain-specific configs
sed -i "s|GOOGLE_REDIRECT_URI=.*|GOOGLE_REDIRECT_URI=https://${API_SUBDOMAIN}/v1/auth/google/callback|" backend/.env
sed -i "s|CORS_ORIGINS=.*|CORS_ORIGINS=https://${DOMAIN},https://www.${DOMAIN},https://${TSPACE_SUBDOMAIN},https://${API_SUBDOMAIN},https://app.${DOMAIN}|g" backend/.env
sed -i "s|DEPLOY_REGION=.*|DEPLOY_REGION=SG|" backend/.env
sed -i "s|^LLM_PROVIDER_ORDER=.*|LLM_PROVIDER_ORDER=deepseek,ollama|" backend/.env

# Add payment success/cancel URLs if not present
if ! grep -q "STRIPE_SUCCESS_URL" backend/.env; then
    {
        echo ""
        echo "# Payment redirect URLs (auto-set by deploy script)"
        echo "STRIPE_SUCCESS_URL=https://${DOMAIN}/pricing?status=success"
        echo "STRIPE_CANCEL_URL=https://${DOMAIN}/pricing?status=cancel"
    } >> backend/.env
fi

# Add PayPal / Airwallex webhook URL hints if not present
if ! grep -q "PAYPAL_WEBHOOK_URL" backend/.env; then
    {
        echo "PAYPAL_WEBHOOK_URL=https://${API_SUBDOMAIN}/v1/payment/webhook/paypal"
        echo "AIRWALLEX_WEBHOOK_URL=https://${API_SUBDOMAIN}/v1/payment/webhook/airwallex"
    } >> backend/.env
fi

# Create chroma_models directory (Docker bind mount needs it)
mkdir -p data/chroma_models

# ============================
# 6. Build and start Docker services
# ============================
log "Building and starting Docker services..."
cd "${APP_DIR}/docker"

docker compose down 2>/dev/null || true
docker compose up -d --build

log "Waiting for backend to start..."
sleep 15
for i in $(seq 1 12); do
    if curl -fsS http://localhost:5200/health >/dev/null 2>&1; then
        log "Backend is healthy."
        break
    fi
    log "Backend not ready yet, retrying... ($i/12)"
    sleep 5
done

# ============================
# 7. Deploy genz-web static site (genz.ltd marketing + payment provider selection)
# ============================
log "Building genz-web (React + i18n)..."
cd "${APP_DIR}/frontend"
if command -v pnpm >/dev/null 2>&1; then
    pnpm install --frozen-lockfile
    pnpm build:genz-web
else
    log "pnpm not found; ensure dist/ is pre-built on the server"
fi

log "Deploying genz-web to /var/www/genz-web..."
GENZ_WEB_DIST="${APP_DIR}/frontend/packages/genz-web/dist"
GENZ_WEB_DEST="/var/www/genz-web"
mkdir -p "${GENZ_WEB_DEST}"
rsync -a --delete "${GENZ_WEB_DIST}/" "${GENZ_WEB_DEST}/"
log "genz-web deployed ($(find "${GENZ_WEB_DEST}" -type f | wc -l) files)."

# ============================
# 8. Nginx config (host-level, reverse proxy to Docker)
# ============================
log "Installing Nginx config..."
cp "${APP_DIR}/docker/nginx.conf" /etc/nginx/nginx.conf
nginx -t
systemctl restart nginx
systemctl enable nginx

# ============================
# 9. Firewall
# ============================
log "Configuring UFW..."
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# ============================
# 10. Health check
# ============================
log "Running health checks..."
IP=$(curl -s -4 ifconfig.me || echo "unknown")
log "Server public IP: ${IP}"
log ""
log "========================================"
log "Deployment complete!"
log ""
log "Health check (local):"
log "  curl http://localhost:5200/health"
log ""
log "Public URLs (after Cloudflare DNS propagates):"
log "  https://${DOMAIN}/health"
log "  https://${API_SUBDOMAIN}/health"
log "  https://${TSPACE_SUBDOMAIN}"
log ""
log "Cloudflare SSL/TLS mode: set to 'Full' (not Strict)"
log "  (upgrade to Full Strict later with Cloudflare Origin Certificate)"
log ""
log "Next steps:"
log "1. Edit ${APP_DIR}/backend/.env with real secrets (OpenAI, Google, Stripe)."
log "2. Restart: cd ${APP_DIR}/docker && docker compose restart"
log "3. Configure Google OAuth + payment provider webhooks (Stripe/PayPal/Airwallex)."
log "========================================"
