# GenZ Web — genz.ltd (Stripe review site)

> ## ⛔ ARCHIVED — 2026-09-18 起为只读归档副本，**不是真源**
>
> **裸域 `genz.ltd` 的真正真源 = 独立仓 [`GenzLTD/genz-web`](https://github.com/GenzLTD/genz-web)，
> 由 Vercel 自动部署（push `main` 即发）。**
>
> 本目录是 looma-zervi 内的历史副本，保留供 grep / 归档 / 回滚参考。**改这里不会影响线上。**
> 相关的投递链已全部切断：
>
> - `scripts/deploy-genz-web.sh` → `.disabled`（默认拒绝执行）
> - `scripts/deploy-overseas.sh` 第 7 步 → 已移除
> - `docker/nginx.conf` / `nginx-vultr.conf` 的 `genz.ltd` / `www.genz.ltd` server 块 → 已摘
>
> 契约对齐（唯一需要保持一致的）：`appRegisterUrl = https://tspace.genz.ltd/register`、
> `apiBase = https://api.genz.ltd`。
>
> 详见 [`docs/MULTI_REPO_PUBLISH_FEDERATION.md`](../../../docs/MULTI_REPO_PUBLISH_FEDERATION.md)

**Branch:** `release/overseas`（历史）  
**Stack:** Vite + React + `react-i18next` (English / 中文)  
**Brand:** GenZ · **Product:** PlanetX

Marketing SPA for Stripe merchant review and USD subscription positioning.

## i18n

- Locales: `src/i18n/locales/en.json`, `zh.json`
- Language switcher in header (persists to `localStorage` key `genz_lang`)
- Default: browser language (`zh*` → 中文, else English)

## Routes

| URL | Page |
|-----|------|
| `/` | Home |
| `/pricing` | Pricing |
| `/legal/privacy` | Privacy |
| `/legal/terms` | Terms |
| `/legal/refund` | Refund |

Legacy `.html` paths redirect to SPA routes.

## Local dev（归档副本，仅供本地查看历史形态）

```bash
cd frontend
pnpm install
pnpm dev:genz-web
# http://localhost:5180
```

## Build

```bash
cd frontend && pnpm build:genz-web
```

> `build:all` 已不再串联本包。产物仅供本地比对，**不要 rsync 到任何服务器**。

Legal entity name: `src/config/site.ts` → `legalEntityName`

See: `docs/MULTI_REPO_PUBLISH_FEDERATION.md`
