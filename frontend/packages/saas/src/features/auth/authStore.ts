/**
 * SaaS Auth Store - Zustand store for authentication state.
 * Owner: szbenyx
 *
 * THOMAS 生态统一认证 (RFC supabase-unified-auth-v1.md)：
 * 配置 VITE_SUPABASE_URL/VITE_SUPABASE_ANON_KEY 后走 Supabase 登录；
 * 未配置时回退旧 looma JWT 路径（后端 require_auth 双 token 兼容）。
 * Token is stored in localStorage via persist middleware.
 * API paths are aligned with Flask backend.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { createAuthApi, createQuotaApi, type UserProfile, type QuotaResponse } from "@looma/shared-core";
import {
  getSupabaseClient,
  isSupabaseEnabled,
  persistSupabaseSession,
} from "@looma/shared-core/supabase";
import { createSaasApiClient } from "../../api/saasApiClient";

export type QuotaInfo = QuotaResponse;

function getClient() {
  return createSaasApiClient();
}

function getAuthApi() {
  return createAuthApi(getClient());
}

interface AuthState {
  token: string | null;
  user: UserProfile | null;
  quota: QuotaInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => void;
  fetchProfile: () => Promise<void>;
  fetchQuota: () => Promise<void>;
  /** 写入新 JWT 并刷新 profile/quota（tier 升级等场景） */
  applySessionToken: (accessToken: string) => Promise<void>;
  /** 从 PlanetX 共享的 looma_token 自动登录 */
  tryAutoLogin: () => Promise<void>;
}

export const useSaasAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      quota: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (email, password) => {
        set({ isLoading: true });
        try {
          if (isSupabaseEnabled()) {
            // Supabase 统一认证：登录后 access_token 直接作 looma Bearer（后端 JWKS 验证）
            const sb = getSupabaseClient()!;
            const { data, error } = await sb.auth.signInWithPassword({ email, password });
            if (error) throw new Error(error.message);
            const accessToken = data.session?.access_token;
            if (!accessToken) throw new Error("no session");
            persistSupabaseSession(accessToken);
            getClient().setToken(accessToken);
            set({ token: accessToken, isAuthenticated: true, isLoading: false });
          } else {
            const api = getAuthApi();
            const resp = await api.login({ email, password });
            set({ token: resp.access_token, user: resp.user as UserProfile, isAuthenticated: true, isLoading: false });
            // 写入共享 localStorage，PlanetX 侧也可识别（为未来双向 SSO 做准备）
            getClient().setToken(resp.access_token);
          }
          // 登录后拉取完整 profile（含 is_early_adopter / created_at）
          await get().fetchProfile();
          await get().fetchQuota();
        } catch (e) {
          set({ isLoading: false });
          throw e;
        }
      },

      register: async (email, password, name) => {
        set({ isLoading: true });
        try {
          if (isSupabaseEnabled()) {
            const sb = getSupabaseClient()!;
            const { data, error } = await sb.auth.signUp({
              email,
              password,
              options: name ? { data: { full_name: name } } : undefined,
            });
            if (error) throw new Error(error.message);
            const accessToken = data.session?.access_token;
            if (!accessToken) {
              // 邮箱确认开启，未自动登录 → 提示查收邮件
              throw new Error("注册成功，请查收邮箱完成确认后再登录");
            }
            persistSupabaseSession(accessToken);
            getClient().setToken(accessToken);
            set({ token: accessToken, isAuthenticated: true, isLoading: false });
          } else {
            const api = getAuthApi();
            const resp = await api.register({ email, password, name });
            set({ token: resp.access_token, user: resp.user as UserProfile, isAuthenticated: true, isLoading: false });
            getClient().setToken(resp.access_token);
          }
          await get().fetchProfile();
          await get().fetchQuota();
        } catch (e) {
          set({ isLoading: false });
          throw e;
        }
      },

      logout: () => {
        // Supabase 端退出（best-effort）
        if (isSupabaseEnabled()) {
          getSupabaseClient()?.auth.signOut().catch(() => {});
        }
        // 清除共享 localStorage token
        getClient().clearToken();
        set({ token: null, user: null, quota: null, isAuthenticated: false, isLoading: false });
      },

      fetchProfile: async () => {
        const token = get().token;
        if (!token) return;
        try {
          const api = getAuthApi();
          const profile = await api.profile();
          set({ user: profile, isAuthenticated: true });
        } catch {
          get().logout();
        }
      },

      fetchQuota: async () => {
        if (!get().token) return;
        try {
          const api = createQuotaApi(getClient());
          const data = await api.get();
          set({ quota: data });
        } catch {
          /* ignore */
        }
      },

      applySessionToken: async (accessToken: string) => {
        getClient().setToken(accessToken);
        set({ token: accessToken, isAuthenticated: true });
        await get().fetchProfile();
        await get().fetchQuota();
      },

      /** 从 PlanetX 共享的 looma_token 自动登录（C→B 互通核心） */
      tryAutoLogin: async () => {
        const state = get();
        if (state.token && state.isAuthenticated) return;

        const sharedToken = localStorage.getItem("looma_token") || state.token;
        if (!sharedToken) return;

        set({ token: sharedToken, isLoading: true });
        try {
          await get().fetchProfile();
          await get().fetchQuota();
        } catch {
          get().logout();
        } finally {
          set({ isLoading: false });
        }
      },
    }),
    {
      name: "saas-auth",
      partialize: (state) => ({ token: state.token }),
    }
  )
);
