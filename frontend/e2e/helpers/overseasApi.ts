/**
 * Overseas E2E API helpers — real backend (api.genz.ltd / Vultr or local).
 *
 * Covers B2C subscription smoke + B-end jobs/resume/trust API probes.
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
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

/** Fetch that never throws — for asserting 403/400/429. */
export async function apiStatus(
  path: string,
  init: RequestInit = {},
): Promise<{ status: number; body: Record<string, unknown> }> {
  const resp = await fetch(`${OVERSEAS_API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers as Record<string, string>),
    },
  });
  let body: Record<string, unknown> = {};
  try {
    body = (await resp.json()) as Record<string, unknown>;
  } catch {
    body = {};
  }
  return { status: resp.status, body };
}

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

/** Register a new overseas user and return token + email. */
export async function registerOverseasUser(name = "E2E Overseas"): Promise<{
  email: string;
  password: string;
  token: string;
}> {
  const email = uniqueEmail("overseas");
  const password = TEST_PASS;

  const reg = await apiJson<{ access_token: string }>("/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, name }),
  });

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
    headers: authHeaders(token),
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
    headers: authHeaders(token),
  });

  const totalUsed = data.records.reduce((sum, r) => sum + r.used, 0);
  const totalLimit = data.records.reduce((sum, r) => sum + r.daily_limit, 0);

  return {
    tier: data.tier,
    used: totalUsed,
    limit: totalLimit,
  };
}

/** Grant compliance consent for a scope (e.g. "ask_rag", "jobseeker_core"). */
export async function grantConsent(token: string, scope: string): Promise<void> {
  await apiJson("/v1/compliance/consent/grant", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ scope }),
  });
}

export async function revokeConsent(
  token: string,
  scope: string,
): Promise<Record<string, unknown>> {
  return apiJson("/v1/compliance/consent/revoke", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ scope }),
  });
}

export async function getConsentStatus(token: string): Promise<{
  status: Record<string, boolean>;
  primary_tiers: string[];
  packages: Record<string, string[]>;
}> {
  return apiJson("/v1/compliance/consent/status", {
    headers: authHeaders(token),
  });
}

export async function getRequiredConsents(): Promise<{
  available_scopes: string[];
  primary_tiers: string[];
}> {
  return apiJson("/v1/compliance/consent/required");
}

/** Primary product tiers + other overseas capability scopes (excl. legacy children). */
export const OVERSEAS_CONSENT_SCOPES = [
  "jobseeker_core",
  "credit_query",
  "report_share",
  "profile_share",
  "ask_rag",
  "mbti_analyze",
  "navigator_memory",
] as const;

/** Send a test AI question. */
export async function askQuestion(
  token: string,
  question: string,
): Promise<{ answer: string }> {
  return apiJson("/v1/ask", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ query: question, mode: "quick" }),
  });
}

// ── Jobs / Resume / Credit / Match reports ─────────────────────

export async function parseJD(
  token: string,
  jdText: string,
): Promise<{ parsed: Record<string, unknown>; job_id?: string }> {
  return apiJson("/v1/jobs/parse", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ text: jdText }),
  });
}

export async function parseResumeText(
  token: string,
  text: string,
): Promise<{ extracted: Record<string, unknown> }> {
  return apiJson("/v1/resume/parse", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ text }),
  });
}

export async function matchJob(
  token: string,
  resumeText: string,
  opts?: { job_id?: string; job_description?: string },
): Promise<{ matches: Array<Record<string, unknown>>; total_evaluated: number }> {
  return apiJson("/v1/jobs/match", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      resume_text: resumeText,
      ...(opts?.job_id ? { job_id: opts.job_id } : {}),
      ...(opts?.job_description ? { job_description: opts.job_description } : {}),
    }),
  });
}

export async function checkCredit(
  token: string,
  companyName: string,
): Promise<{ status: number; body: Record<string, unknown> }> {
  return apiStatus("/v1/credit/check-company", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ company_name: companyName }),
  });
}

export async function saveMatchReport(
  token: string,
  data: {
    resume_text: string;
    matches: unknown[];
    title?: string;
    summary?: string;
  },
): Promise<Record<string, unknown>> {
  return apiJson("/v1/match-reports", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
}

// ── Trust ──────────────────────────────────────────────────────

export async function listAttestations(
  token: string,
): Promise<{ attestations: Array<Record<string, unknown>>; total: number }> {
  return apiJson("/v1/trust/attestations", {
    headers: authHeaders(token),
  });
}

export async function refreshAttestations(
  token: string,
): Promise<{ attestations: Array<Record<string, unknown>>; total: number }> {
  return apiJson("/v1/trust/refresh", {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function createTrustShareCode(
  token: string,
  payload?: {
    scope?: string[];
    max_access_count?: number;
    expires_in_seconds?: number;
  },
): Promise<{
  share_code: string;
  expires_at: string;
  scope: string[];
  remaining_access_count: number;
}> {
  return apiJson("/v1/trust/share-code", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload ?? {}),
  });
}

export async function listTrustShareCodes(
  token: string,
): Promise<{ share_codes: Array<Record<string, unknown>>; total: number }> {
  return apiJson("/v1/trust/share-codes", {
    headers: authHeaders(token),
  });
}

export async function revokeTrustShareCode(
  token: string,
  codeId: string,
): Promise<{ message: string }> {
  return apiJson(`/v1/trust/share-code/${codeId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

/** Public verify — no JWT. */
export async function verifyTrustShareCode(
  shareCode: string,
): Promise<{ status: number; body: Record<string, unknown> }> {
  return apiStatus("/v1/trust/verify", {
    method: "POST",
    body: JSON.stringify({ share_code: shareCode }),
  });
}

// ── Candidates / enterprise / referral share ───────────────────

export interface SeededOverseasSeeker {
  email: string;
  password: string;
  token: string;
  shareCode: string;
  personalityName: string;
  displayName: string;
}

/** Register seeker, sync personality, create profile_share code. */
export async function seedOverseasSeekerWithShareCode(
  suffix = String(Date.now()),
): Promise<SeededOverseasSeeker> {
  const email = `e2e-seeker-${suffix}-${Math.random().toString(36).slice(2, 6)}@test.local`;
  const password = TEST_PASS;
  const personalityName = "Nebula Artist";
  const displayName = "E2ESeeker";
  const detail = JSON.stringify({
    name: personalityName,
    emoji: "🎨",
    tagline: "E2E overseas profile",
    desc: "Playwright seeded overseas seeker",
    traits: ["Creativity"],
  });

  const reg = await apiJson<{ access_token: string }>("/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, name: displayName }),
  });

  await apiJson("/v1/game/profile-sync", {
    method: "POST",
    headers: authHeaders(reg.access_token),
    body: JSON.stringify({
      personality_type: personalityName,
      personality_detail: detail,
    }),
  });

  const share = await apiJson<{ code: string }>("/v1/referral/create", {
    method: "POST",
    headers: authHeaders(reg.access_token),
    body: JSON.stringify({ purpose: "profile_share" }),
  });

  return {
    email,
    password,
    token: reg.access_token,
    shareCode: share.code,
    personalityName,
    displayName,
  };
}

export async function getPublicProfileView(
  shareCode: string,
): Promise<Record<string, unknown>> {
  return apiJson(`/v1/referral/profile-view/${encodeURIComponent(shareCode)}`);
}

/**
 * Stub upgrade (local / PAYMENT_STUB_MODE only).
 * On Vultr production this typically returns 402 payment_required.
 */
export async function tryUpgradeToken(
  token: string,
  tier: "supporter" | "pro" = "supporter",
): Promise<{ ok: true; token: string } | { ok: false; status: number; body: Record<string, unknown> }> {
  const result = await apiStatus("/v1/payment/upgrade", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ tier }),
  });
  if (result.status >= 200 && result.status < 300 && result.body.access_token) {
    return { ok: true, token: String(result.body.access_token) };
  }
  return { ok: false, status: result.status, body: result.body };
}

export async function createEnterprise(
  token: string,
  name = `E2E Co ${Date.now()}`,
): Promise<{ id: string; name: string }> {
  return apiJson("/v1/enterprise/create", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ name, domain: "e2e.test" }),
  });
}

export async function importCandidateFromShare(
  token: string,
  shareCode: string,
): Promise<{ status: number; body: Record<string, unknown> }> {
  return apiStatus("/v1/enterprise/candidates/import-share", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ share_code: shareCode }),
  });
}

export async function listEnterpriseCandidates(
  token: string,
): Promise<{ status: number; body: Record<string, unknown> }> {
  return apiStatus("/v1/enterprise/candidates", {
    headers: authHeaders(token),
  });
}

export async function getEnterpriseCandidate(
  token: string,
  candidateId: string,
): Promise<{ status: number; body: Record<string, unknown> }> {
  return apiStatus(`/v1/enterprise/candidate/${candidateId}`, {
    headers: authHeaders(token),
  });
}

// ── Poetry: overseas = Xin-Da-Ya translation challenge ─────────

export async function getPoetryChallengeCurrent(
  token?: string,
): Promise<{ status: number; body: Record<string, unknown> }> {
  return apiStatus("/v1/poetry/challenge/current", {
    headers: token ? authHeaders(token) : {},
  });
}

export async function submitPoetryTranslation(
  token: string,
  payload: {
    translation: string;
    license_accepted: boolean;
    round_id?: number;
    note?: string;
  },
): Promise<{ status: number; body: Record<string, unknown> }> {
  return apiStatus("/v1/poetry/challenge/entries", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

/** Optional: library still powers the challenge poem pool (not mainland browse UX). */
export async function getPoetryStats(): Promise<{
  total: number;
  dynasties?: Array<{ name: string; count: number }>;
}> {
  return apiJson("/v1/poetry/stats");
}

/** Sample fixtures for LLM parse/match (Chinese — matches mainland/Vultr corpora). */
export const SAMPLE_JD = `
职位：高级前端工程师
公司：星云科技有限公司
地点：上海
薪资：30-50K·14薪
职责：
1. 负责 B 端 SaaS 产品前端架构与核心模块开发
2. 使用 React / TypeScript / Tailwind 落地高保真交互
3. 与设计、后端协作完成候选人管理与职位匹配流程
要求：
- 5 年以上前端经验，精通 React、TypeScript
- 熟悉 Vite、状态管理、组件设计系统
- 有招聘/HR SaaS 或数据可视化经验优先
`.trim();

export const SAMPLE_RESUME = `
姓名：张明
邮箱：zhang.ming.e2e@example.com
电话：13800138000
摘要：资深前端工程师，6 年 React/TypeScript 经验，主导过企业级招聘 SaaS 工作台。
技能：React, TypeScript, Vite, Tailwind CSS, Node.js, GraphQL
工作经历：
- 星云科技 · 高级前端 · 2021-至今：负责候选人列表、职位匹配与报表模块
- 云启网络 · 前端工程师 · 2018-2021：搭建组件库与设计 Token 体系
教育：上海交通大学 · 计算机科学 · 本科
`.trim();

export { TEST_PASS, uniqueEmail };
