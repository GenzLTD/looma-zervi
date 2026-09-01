/**
 * Supabase client factory — THOMAS 生态统一认证
 * (RFC docs/rfc/supabase-unified-auth-v1.md)
 *
 * 仅供 Web 端使用（planetx / saas / genz-web）。
 * 注意：不要被 src/index.ts re-export，否则会污染微信小程序构建产物
 * （supabase-js 依赖浏览器 localStorage / fetch）。
 *
 * 配置：VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY
 * 未配置时 isSupabaseEnabled() 返回 false，authStore 走旧 looma API 路径。
 */
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const LOOMA_TOKEN_KEY = "looma_token"; // G2 aligned（shared-core LOOMA_TOKEN_KEY）

function readEnv(): { url?: string; anonKey?: string } {
  const meta = import.meta as unknown as { env?: Record<string, string | undefined> };
  const env = meta.env ?? {};
  return {
    url: env.VITE_SUPABASE_URL,
    anonKey: env.VITE_SUPABASE_ANON_KEY,
  };
}

let client: SupabaseClient | null = null;

/** 返回全局单例 supabase client；未配置 VITE_SUPABASE_* 时返回 null。 */
export function getSupabaseClient(): SupabaseClient | null {
  if (client) return client;
  const { url, anonKey } = readEnv();
  if (!url || !anonKey) return null;
  client = createClient(url, anonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  });
  return client;
}

/** 是否启用了 Supabase 统一认证（VITE_SUPABASE_URL + ANON_KEY 均已配置）。 */
export function isSupabaseEnabled(): boolean {
  const { url, anonKey } = readEnv();
  return Boolean(url && anonKey);
}

/**
 * 将 Supabase session access_token 写入 looma 共享 token 存储，
 * 供 ApiClient（Authorization: Bearer）与跨端 SSO（looma_token）使用。
 * 后端 require_auth 已支持验证 Supabase JWT（JWKS/ES256）。
 */
export function persistSupabaseSession(accessToken: string | null | undefined): void {
  try {
    if (accessToken) {
      window.localStorage.setItem(LOOMA_TOKEN_KEY, accessToken);
    } else {
      window.localStorage.removeItem(LOOMA_TOKEN_KEY);
    }
  } catch {
    /* SSR / privacy mode: ignore */
  }
}
