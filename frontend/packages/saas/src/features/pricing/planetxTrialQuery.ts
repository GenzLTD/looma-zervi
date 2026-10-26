/**
 * 职业域试点带进定价页的查询参数。只认 src=planetx_domain 且 domain=职业域。
 */

export interface PlanetxTrialQuery {
  src: string
  domain: string
  region: "CN" | "US" | ""
  campaign: string
  fromPlanetx: boolean
}

const STORAGE_KEY = "saas_planetx_trial"

function normalizeRegion(raw: string): "CN" | "US" | "" {
  const region = raw.trim().toUpperCase()
  if (region === "CN") return "CN"
  if (region === "US" || region === "SG") return "US"
  return ""
}

function fromParams(params: URLSearchParams): PlanetxTrialQuery {
  const src = (params.get("src") || "").trim()
  const domain = (params.get("domain") || "").trim()
  const campaign = (params.get("campaign") || "").trim()
  const region = normalizeRegion(params.get("region") || "")
  return {
    src,
    domain,
    region,
    campaign: /^[A-Za-z0-9]{4,32}$/.test(campaign) ? campaign : "",
    fromPlanetx: src === "planetx_domain" && domain === "职业域",
  }
}

export function readPlanetxTrial(search: string): PlanetxTrialQuery {
  const fromUrl = fromParams(new URLSearchParams(search))
  if (fromUrl.fromPlanetx) {
    try {
      sessionStorage.setItem(STORAGE_KEY, search)
    } catch {
      /* private mode */
    }
    return fromUrl
  }
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY)
    if (saved) return fromParams(new URLSearchParams(saved.startsWith("?") ? saved.slice(1) : saved))
  } catch {
    /* private mode */
  }
  return fromUrl
}

export function pricingReturnPath(params: URLSearchParams): string | null {
  if (params.get("from") !== "pricing") return null
  const next = new URLSearchParams()
  for (const key of ["src", "domain", "region", "campaign"] as const) {
    const value = params.get(key)
    if (value) next.set(key, value)
  }
  const query = next.toString()
  return query ? `/pricing?${query}` : "/pricing"
}

export function registerFromPricing(trial: PlanetxTrialQuery): string {
  const params = new URLSearchParams()
  params.set("from", "pricing")
  if (trial.fromPlanetx) {
    params.set("src", trial.src)
    params.set("domain", trial.domain)
    if (trial.region) params.set("region", trial.region)
    if (trial.campaign) params.set("campaign", trial.campaign)
  }
  return `/register?${params.toString()}`
}
