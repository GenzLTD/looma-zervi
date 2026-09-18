# Overseas Deployment Guide (main)

> Domain: `genz.ltd`
> Infrastructure: Vultr VPS (Singapore) + Cloudflare CDN + self-signed origin SSL (Full mode)

## DNS Records (Cloudflare)

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| — | `@` | **Vercel**（`GenzLTD/genz-web`，不在本机；见 §genz-web） | — |
| — | `www` | **Vercel**（`Genzer-Terminal` 独立站） | — |
| A | `api` | `VPS_IP` | ON |
| A | `tspace` | `VPS_IP` | ON |

Cloudflare SSL/TLS mode: **Full** (upgrade to Full Strict with Origin Certificate later)

## Subdomain Routing

| Host | Purpose | Backend |
|------|---------|---------|
| `genz.ltd` / `www.genz.ltd` | GenZ marketing site (Stripe review) | **Vercel · 独立仓 `GenzLTD/genz-web`（不在本机）** |
| `api.genz.ltd` | API only | `/v1/*` → backend |
| `tspace.genz.ltd` | T-space B2B SaaS SPA | `saas/dist` (when built) |

## genz-web (marketing / Stripe) — 已迁出本机（2026-09-18）

**裸域营销站不在本仓发布，也不在本机 serve。** 真源 = 独立仓 `GenzLTD/genz-web`，
push `main` 即由 Vercel 自动部署。本机对应的投递链已全部切断：
`deploy-genz-web.sh` → `.disabled`、`deploy-overseas.sh` 第 7 步移除、
两份 nginx（`docker/nginx.conf` / `nginx-vultr.conf`）的 `genz.ltd`/`www.genz.ltd`
server 块摘除。

`frontend/packages/genz-web/` 保留为**只读归档副本**，改它不影响线上。

**Stripe 商户审核前（在 `GenzLTD/genz-web` 仓操作，不在本仓）：**

1. Set Hong Kong legal name in `src/config/site.ts` → `legalEntityName`
2. Push 到 `main`，确认 Vercel 部署成功
3. Confirm `https://genz.ltd/` shows the marketing homepage (not API JSON)

详见 `docs/MULTI_REPO_PUBLISH_FEDERATION.md`。

## Third-party Callback URLs

| Service | Setting | URL |
|---------|---------|-----|
| Google OAuth | Authorized JS origins | `https://genz.ltd` |
| Google OAuth | Redirect URI | `https://api.genz.ltd/v1/auth/google/callback` |
| Stripe | Business website | `https://genz.ltd` |
| Stripe | Webhook endpoint | `https://api.genz.ltd/v1/payment/stripe/webhook` |
| Stripe | Success URL | `https://tspace.genz.ltd/pricing?status=success` |
| Stripe | Cancel URL | `https://tspace.genz.ltd/pricing?status=cancel` |

## CORS

`backend/.env` must include:

```env
CORS_ORIGINS=https://genz.ltd,https://www.genz.ltd,https://tspace.genz.ltd,https://api.genz.ltd
```

(`deploy-overseas.sh` sets this automatically.)

## One-click Deploy

```bash
curl -fsSL https://gitee.com/szbenyx/looma-zervi/raw/main/scripts/deploy-overseas.sh | bash
```

Or manually:

```bash
git clone -b main https://gitee.com/szbenyx/looma-zervi.git /opt/looma-zervi
cd /opt/looma-zervi
cp backend/.env.example backend/.env
# Edit backend/.env with real secrets
bash scripts/deploy-overseas.sh
```

## Redeploy marketing site only

**不再在本机操作。** 营销站已迁出（见上文 §genz-web）。发布方式：

```bash
git clone git@github.com:GenzLTD/genz-web.git && cd genz-web
# 改完 push main，Vercel 自动部署
```

## Post-deploy Checklist

- [ ] `legalEntityName` set in `src/config/site.ts` — 在 `GenzLTD/genz-web` 仓（matches HK CR + Stripe）
- [ ] `backend/.env` — `OPENAI_API_KEY`, `GOOGLE_CLIENT_*`, `STRIPE_*`, `CORS_ORIGINS`
- [ ] `https://genz.ltd/` — marketing homepage（**验收点：Vercel**，不是本机）
- [ ] `https://genz.ltd/pricing` — USD plans（**验收点：Vercel + api.genz.ltd**）
- [ ] `https://api.genz.ltd/health` — HTTP 200
- [ ] Google OAuth end-to-end
- [ ] Stripe Checkout session (when keys configured)
- [ ] Stripe webhook signing secret in `.env`
