# Overseas CI/CD Setup Guide

## Architecture

```
GitHub push tag overseas-* → GitHub Actions → Vultr Singapore
                                                 ↓
genz.ltd → Vercel (frontend, auto-deploy)
api.genz.ltd → Cloudflare → Vultr 139.180.184.25 (backend Docker)
```

## Files Created

| File | Purpose |
|------|---------|
| `.github/workflows/deploy-overseas.yml` | Tag-triggered deploy workflow |
| `nginx-looma-zervi-overseas.conf` | Nginx config for api.genz.ltd |

## Step 1: GitHub Secrets

Go to GitHub repo → Settings → Secrets and variables → Actions → New repository secret.

### Required Secrets

| Secret Name | Value | Example |
|-------------|-------|---------|
| `VULTR_SSH_HOST` | Vultr server IP | `139.180.184.25` |
| `VULTR_SSH_USER` | SSH username | `root` |
| `VULTR_SSH_PRIVATE_KEY` | SSH private key (full text including `-----BEGIN/END...-----`) | |
| `VULTR_JWT_SECRET` | JWT signing secret (32+ chars) | generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `VULTR_DEEPSEEK_API_KEY` | DeepSeek API key | `sk-xxxxxxxx` |

### Optional Secrets (have defaults)

| Secret Name | Default | Notes |
|-------------|---------|-------|
| `VULTR_DEPLOY_PATH` | `/opt/looma-zervi` | Server deploy directory |
| `VULTR_DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | DeepSeek API endpoint |

### GitHub Environment (recommended)

Create an `overseas` environment in repo Settings → Environments for:
- Deployment approval (optional)
- Environment-specific secrets (alternative to repo secrets)
- Deployment history tracking

## Step 2: SSH Key Setup

### Option A: Find existing key

If you deployed the first version manually, the key should be on the machine you used:
```bash
# Check common locations
ls ~/.ssh/
ls ~/Downloads/*.pem
# Vultr console → Server → SSH Keys
```

### Option B: Generate new key (recommended)

```bash
# Generate a dedicated deploy key
ssh-keygen -t ed25519 -C "github-actions-overseas" -f ~/.ssh/vultr_deploy_key -N ""

# Public key (add to Vultr server):
cat ~/.ssh/vultr_deploy_key.pub

# Private key (add to GitHub Secrets as VULTR_SSH_PRIVATE_KEY):
cat ~/.ssh/vultr_deploy_key
```

Add public key to Vultr server:
1. Vultr Console → Server → Settings → SSH Keys → Add
2. Or manually: `ssh root@139.180.184.25 "echo '<public_key>' >> ~/.ssh/authorized_keys"`

## Step 3: Vultr Server Preparation

The deploy workflow auto-installs Docker and nginx if missing. But verify:

```bash
# SSH into Vultr
ssh root@139.180.184.25

# Check Docker
docker --version
docker compose version

# Check nginx
nginx -v

# Check existing looma deployment
ls /opt/looma-zervi/
docker ps
```

## Vultr Nginx 架构（monolithic）

Vultr 海外机上的 Nginx **不是** Debian 常见的 `sites-enabled` 多文件模式，而是 **单体配置**：生效内容在 `/etc/nginx/nginx.conf`，由 `scripts/deploy-overseas.sh` 第 8 步 `cp "${APP_DIR}/docker/nginx.conf" /etc/nginx/nginx.conf` 整文件覆盖。
**落地件是 `docker/nginx.conf`**（2026-09-18 实测真机 md5 逐字节等于改动前的该文件）。仓内另有 `nginx-vultr.conf`，名字像真机件但**不被任何管线引用**，且已与真机漂移（行数 300 vs 237，api `/health` 与 api `/` 两处差异）——**不要**用它覆盖真机，待单独对账或删除。
改 `sites-available` / `sites-enabled` 可能 `nginx -t` 通过但 **线上行为不变**——以前海外 CI 对 `sites-enabled` 的操作容易成为「假成功」。
海外部署 **只** 通过 workflow 覆盖 monolithic 配置；**禁止**再指望 `sites-enabled` 生效（大陆 Tencent 机仍可用 sites-enabled，两套勿混）。
排查时以运行时配置为准，不要只 `cat sites-enabled/`。

**验证（SSH 到 Vultr 后执行）：**

```bash
nginx -T 2>/dev/null | grep server_name
# 应看到 api.genz.ltd；若只有 default_server 或缺少 api.genz.ltd，说明 monolithic 主配置未包含海外 server 块
```

## Step 4: Cloudflare DNS

Ensure these DNS records exist (they should already be configured):

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `api` | `139.180.184.25` | Proxied (orange cloud) |
| CNAME | `www` | `cname.vercel-dns.com` | Proxied |
| A/CNAME | `@` | Vercel | Proxied or DNS only |

Cloudflare SSL/TLS mode: **Flexible** (CF terminates SSL, talks HTTP to Vultr :80)
or **Full** (needs cert on Vultr, not needed with this setup).

## Step 5: Trigger Deployment

### Method 1: Tag push (recommended)

```bash
# Tag and push
git tag overseas-v1.1
git push origin overseas-v1.1

# Or with date
git tag overseas-$(date +%Y%m%d)
git push origin overseas-$(date +%Y%m%d)
```

### Method 2: Manual dispatch

GitHub repo → Actions → Deploy Overseas → Run workflow

Options:
- `skip_tests: true` — skip backend tests for faster deploy (use for hotfixes)
- `skip_tests: false` — run full test suite before deploy (recommended)

## Step 6: Verify

```bash
# Health check
curl https://api.genz.ltd/health
# Expected: {"service":"looma-backend","status":"ok"}

# Poetry stats
curl https://api.genz.ltd/v1/poetry/stats

# Frontend
curl -I https://genz.ltd/
```

## Comparison: Domestic vs Overseas

| Aspect | Domestic (deploy.yml) | Overseas (deploy-overseas.yml) |
|--------|----------------------|-------------------------------|
| Trigger | push to `main` | tag `overseas-*` or manual |
| Target | Tencent 1.14.202.161 | Vultr 139.180.184.25 |
| Domain | none (IP mode) | api.genz.ltd |
| SSL | none | Cloudflare proxy |
| Frontend | nginx serves PlanetX + T-space | Vercel (separate auto-deploy) |
| Backend | Docker Flask + ChromaDB | Same |
| Secrets prefix | `SSH_*`, `ENV_*` | `VULTR_*` |
| Environment | none | `overseas` |

## Troubleshooting

### SSH Permission denied
- Verify the private key matches the public key on the server
- Check `VULTR_SSH_USER` is correct (root vs ubuntu)
- Test locally: `ssh -i ~/.ssh/your_key root@139.180.184.25`

### Health check fails
- SSH in and check: `docker ps`, `docker logs looma-backend`
- Verify backend/.env has correct `DEEPSEEK_API_KEY`
- Check Cloudflare DNS/proxy settings

### Nginx 404 on api.genz.ltd
- 先确认 monolithic 配置（见上文 **Vultr Nginx 架构**）：`nginx -T 2>/dev/null | grep server_name`
- 若 `server_name` 无 `api.genz.ltd`，修复 `/etc/nginx/nginx.conf`（或打一个 `overseas-*` tag 走 `deploy-overseas.sh` 用 `docker/nginx.conf` 覆盖），**不要**只改 `sites-enabled`
- Test locally: `curl -H "Host: api.genz.ltd" http://127.0.0.1/health`
- Check Cloudflare SSL mode (should be Flexible or Full)

### DeepSeek API from Singapore
- Test from Vultr: `curl https://api.deepseek.com/v1`
- If blocked, set `VULTR_DEEPSEEK_BASE_URL` to a proxy endpoint
