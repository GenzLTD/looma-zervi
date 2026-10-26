/**
 * 职业域试点：叙事走完后把归因带到 SaaS 定价页。
 * 裂变码核销后会清掉 planetx_pending_ref，这里另存一份，避免试用链接丢失 campaign。
 * 不读取游戏等级，也不改付费档位。
 */

const CAMPAIGN_KEY = 'planetx_campaign_ref'
const CAREER_DOMAIN = '职业域'

function normalizeRegion(raw: string): 'CN' | 'US' | '' {
  const region = raw.trim().toUpperCase()
  if (region === 'CN' || region === 'US') return region
  if (region === 'SG') return 'US'
  return ''
}

export function rememberCareerCampaign(code: string): void {
  const trimmed = code.trim()
  if (!trimmed || typeof sessionStorage === 'undefined') return
  try {
    if (!sessionStorage.getItem(CAMPAIGN_KEY)) {
      sessionStorage.setItem(CAMPAIGN_KEY, trimmed)
    }
  } catch {
    /* private mode */
  }
}

export function readCareerCampaign(): string {
  if (typeof window === 'undefined') return ''
  const fromUrl = (new URLSearchParams(window.location.search).get('ref') || '').trim()
  if (fromUrl) {
    rememberCareerCampaign(fromUrl)
    return fromUrl
  }
  try {
    return (sessionStorage.getItem(CAMPAIGN_KEY) || '').trim()
  } catch {
    return ''
  }
}

export function careerTrialPricingUrl(saasBase: string): string {
  const base = (saasBase || 'http://localhost:5174').replace(/\/$/, '')
  const params = new URLSearchParams()
  params.set('src', 'planetx_domain')
  params.set('domain', CAREER_DOMAIN)
  const region = normalizeRegion(new URLSearchParams(window.location.search).get('region') || '')
  if (region) params.set('region', region)
  const campaign = readCareerCampaign()
  if (/^[A-Za-z0-9]{4,32}$/.test(campaign)) params.set('campaign', campaign)
  return `${base}/pricing?${params.toString()}`
}
