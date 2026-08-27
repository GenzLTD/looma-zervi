export const SITE_CONFIG = {
  legalEntityName: "YEDALL LIMITED",
  productName: "PlanetX",
  brandName: "GenZ",
  taglineKey: "site.tagline",
  supportEmail: "zervi@genz.ltd",
  siteUrl: "https://genz.ltd",
  appRegisterUrl: "https://tspace.genz.ltd/register",
  apiBase: import.meta.env.VITE_API_BASE || "https://api.genz.ltd",
} as const;
