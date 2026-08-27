# GenZ Web — genz.ltd (Stripe review site)

**Branch:** `release/overseas`  
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

## Local dev

```bash
cd frontend
pnpm install
pnpm dev:genz-web
# http://localhost:5180
```

## Build & deploy

```bash
cd frontend && pnpm build:genz-web
bash scripts/deploy-genz-web.sh   # rsync dist/ → /var/www/genz-web
```

Legal entity name: `src/config/site.ts` → `legalEntityName`

See: `docs/OVERSEAS_DEPLOY.md`
