# Overseas Deployment Guide (release/overseas)

> Domain: `genz.ltd`
> Infrastructure: Vultr VPS (Singapore) + Cloudflare CDN + self-signed origin SSL (Full mode)

## DNS Records (Cloudflare)

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `@` | `VPS_IP` | ON |
| A | `www` | `VPS_IP` | ON |
| A | `api` | `VPS_IP` | ON |
| A | `tspace` | `VPS_IP` | ON |

Cloudflare SSL/TLS mode: **Full** (upgrade to Full Strict with Origin Certificate later)

## Subdomain Routing

| Host | Purpose | Backend |
|------|---------|---------|
| `genz.ltd` / `www.genz.ltd` | GenZ marketing site (Stripe review) | `nginx` → `/var/www/genz-web` (`frontend/packages/genz-web`) |
| `genz.ltd` / `www` `/v1/*` | API (same host) | `nginx` → Looma `:5200` |
| `api.genz.ltd` | API only | `/v1/*` → backend |
| `tspace.genz.ltd` | T-space B2B SaaS SPA | `saas/dist` (when built) |

## genz-web (marketing / Stripe)

Static files live in `frontend/packages/genz-web/`. Deploy copies them to `/var/www/genz-web`.

**Before Stripe merchant review:**

1. Set Hong Kong legal name in `frontend/packages/genz-web/assets/config.js` → `legalEntityName`
2. Redeploy: `bash scripts/deploy-genz-web.sh`
3. Confirm `https://genz.ltd/` shows the marketing homepage (not API JSON)

## Third-party Callback URLs

| Service | Setting | URL |
|---------|---------|-----|
| Google OAuth | Authorized JS origins | `https://genz.ltd` |
| Google OAuth | Redirect URI | `https://api.genz.ltd/v1/auth/google/callback` |
| Stripe | Business website | `https://genz.ltd` |
| Stripe | Webhook endpoint | `https://api.genz.ltd/v1/payment/stripe/webhook` |
| Stripe | Success URL | `https://genz.ltd/pricing?status=success` |
| Stripe | Cancel URL | `https://genz.ltd/pricing?status=cancel` |

## CORS

`backend/.env` must include:

```env
CORS_ORIGINS=https://genz.ltd,https://www.genz.ltd,https://tspace.genz.ltd,https://api.genz.ltd
```

(`deploy-overseas.sh` sets this automatically.)

## One-click Deploy

```bash
curl -fsSL https://gitee.com/szbenyx/looma-zervi/raw/release/overseas/scripts/deploy-overseas.sh | bash
```

Or manually:

```bash
git clone -b release/overseas https://gitee.com/szbenyx/looma-zervi.git /opt/looma-zervi
cd /opt/looma-zervi
cp backend/.env.example backend/.env
# Edit backend/.env with real secrets
bash scripts/deploy-overseas.sh
```

## Redeploy marketing site only

```bash
cd /opt/looma-zervi && git pull origin release/overseas
bash scripts/deploy-genz-web.sh
```

## Post-deploy Checklist

- [ ] `legalEntityName` set in `assets/config.js` (matches HK CR + Stripe)
- [ ] `backend/.env` — `OPENAI_API_KEY`, `GOOGLE_CLIENT_*`, `STRIPE_*`, `CORS_ORIGINS`
- [ ] `https://genz.ltd/` — marketing homepage (HTML)
- [ ] `https://genz.ltd/pricing` — USD plans (API or fallback)
- [ ] `https://api.genz.ltd/health` — HTTP 200
- [ ] Google OAuth end-to-end
- [ ] Stripe Checkout session (when keys configured)
- [ ] Stripe webhook signing secret in `.env`
