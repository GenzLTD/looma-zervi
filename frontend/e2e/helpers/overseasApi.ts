/**
 * Overseas E2E API helpers — real backend (api.genz.ltd or local).
 *
 * Tests the B2C subscription flow:
 *   genz-web → register → login → dashboard → pricing → subscription
 */
export const OVERSEAS_API_BASE =
  process.env.E2E_OVERSEAS_API ?? "https://api.genz.ltd";
export const OVERSEAS_WEB_BASE =
  process.env.E2E_OVERSEAS_WEB ?? "http://localhost:5180";
export const OVERSEAS_SAAS_BASE =
  process.env.E2E_OVERSEAS_SAAS ?? "http://localhost:5174";

const TEST_PASS = "e2e-overseas-456";

function uniqueEmail(label = "user"): string {
  const ts = Date.now();
  const rand = Math.random().toString(36).slice(2, 6);
  return `e2e-${label}-${ts}-${rand}@test.local`;
}

async function apiJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const resp = await fetch(`${OVERSEAS_API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers as Record<string, string>),
    },
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(
      `API ${init.method ?? "GET"} ${path} failed (${resp.status}): ${body}`,
    );
  }
  return resp.json() as Promise<T>;
}

/** Register a new overseas user and return token + email. */
export async function registerOverseasUser(name = "E2E Overseas"): Promise<{
  email: string;
  password: string;
  token: string;
}> {
  const email = uniqueEmail("overseas");
  const password = TEST_PASS;

  const reg = await apiJson<{ access_token: string }>(
    "/v1/auth/register",
    {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    },
  );

  return { email, password, token: reg.access_token };
}

/** Get user profile / quota info. */
export async function getUserProfile(token: string): Promise<{
  email: string;
  name?: string;
  tier?: string;
  quota_used?: number;
  quota_limit?: number;
}> {
  return apiJson("/v1/auth/profile", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

/** Get quota status. */
export async function getQuota(token: string): Promise<{
  tier: string;
  used: number;
  limit: number;
}> {
  const data = await apiJson<{
    tier: string;
    records: Array<{ resource: string; used: number; daily_limit: number }>;
  }>("/v1/quota", {
    headers: { Authorization: `Bearer ${token}` },
  });

  // Aggregate total used/limit across all resources
  const totalUsed = data.records.reduce((sum, r) => sum + r.used, 0);
  const totalLimit = data.records.reduce((sum, r) => sum + r.daily_limit, 0);

  return {
    tier: data.tier,
    used: totalUsed,
    limit: totalLimit,
  };
}

/** Grant compliance consent for a scope (e.g. "ask_rag"). */
export async function grantConsent(token: string, scope: string): Promise<void> {
  await apiJson("/v1/compliance/consent/grant", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ scope }),
  });
}

/** Send a test AI question. */
export async function askQuestion(
  token: string,
  question: string,
): Promise<{ answer: string }> {
  return apiJson("/v1/ask", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ query: question, mode: "quick" }),
  });
}

export { TEST_PASS, uniqueEmail };
