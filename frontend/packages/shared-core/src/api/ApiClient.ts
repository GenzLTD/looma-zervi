/**
 * API Client - fetch-based with JWT interceptor and platform-aware storage.
 * Shared by web (planetx, saas) and miniprogram packages.
 *
 * Key features:
 * - StorageAdapter pattern: Web localStorage + 小程序 wx.storage
 * - stream()  SSE 流式问答
 * - upload()  文件上传
 * - 自动 401 处理：收到 401 时清除 looma_token 并回调 onUnauthorized
 */

declare global {
  interface Window {
    wx?: WechatStorage;
  }
  const wx: WechatStorage | undefined;
}

interface WechatRequestTask {
  abort?: () => void;
}

interface WechatRequestOptions {
  url: string;
  method?: string;
  data?: unknown;
  header?: Record<string, string>;
  timeout?: number;
  success?: (resp: { statusCode: number; data: unknown; statusText?: string }) => void;
  fail?: (err: { errMsg?: string }) => void;
}

interface WechatStorage {
  getStorageSync(key: string): unknown;
  setStorageSync(key: string, data: string): void;
  removeStorageSync(key: string): void;
  request?(options: WechatRequestOptions): WechatRequestTask;
}

/** Platform-agnostic storage contract. */
export interface StorageAdapter {
  getItem(key: string): string | null | Promise<string | null>;
  setItem(key: string, value: string): void | Promise<void>;
  removeItem(key: string): void | Promise<void>;
}

/** Web localStorage adapter. */
export function webStorageAdapter(): StorageAdapter {
  return {
    getItem: (key: string) => {
      try {
        return localStorage.getItem(key);
      } catch {
        return null;
      }
    },
    setItem: (key: string, value: string) => {
      try {
        localStorage.setItem(key, value);
      } catch {
        /* ignore */
      }
    },
    removeItem: (key: string) => {
      try {
        localStorage.removeItem(key);
      } catch {
        /* ignore */
      }
    },
  };
}

/** WeChat miniprogram wx.storage adapter. */
export function wxStorageAdapter(): StorageAdapter {
  const storage = typeof wx !== "undefined" ? wx : undefined;
  return {
    getItem: (key: string) => {
      try {
        return (storage?.getStorageSync(key) as string | null) ?? null;
      } catch {
        return null;
      }
    },
    setItem: (key: string, value: string) => {
      try {
        storage?.setStorageSync(key, value);
      } catch {
        /* ignore */
      }
    },
    removeItem: (key: string) => {
      try {
        storage?.removeStorageSync(key);
      } catch {
        /* ignore */
      }
    },
  };
}

export interface ApiClientConfig {
  baseURL: string;
  storage?: StorageAdapter;
  tokenKey?: string;
  /**
   * Optional custom token resolver.
   * When provided, the client calls this function instead of reading from storage.
   * Useful when the token is managed by a Zustand store (e.g. `@looma/shared-core` consumers).
   */
  getToken?: () => string | null | Promise<string | null>;
  onUnauthorized?: () => void;
  timeout?: number;
}

export interface RequestOptions {
  headers?: Record<string, string>;
  params?: Record<string, any>;
  timeout?: number;
}

function buildQueryString(params?: Record<string, any>): string {
  if (!params) return "";
  const parts: string[] = [];
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(item))}`);
      }
    } else {
      parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
    }
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

async function resolveStorageValue<T>(value: T | Promise<T>): Promise<T> {
  return Promise.resolve(value);
}

export class ApiClient {
  private baseURL: string;
  private storage: StorageAdapter;
  private tokenKey: string;
  private onUnauthorized?: () => void;
  private defaultTimeout: number;
  private externalGetToken?: () => string | null | Promise<string | null>;

  constructor(config: ApiClientConfig) {
    this.baseURL = config.baseURL.replace(/\/$/, "");
    this.storage = config.storage || webStorageAdapter();
    this.tokenKey = config.tokenKey || "looma_token";
    this.onUnauthorized = config.onUnauthorized;
    this.defaultTimeout = config.timeout || 30000;
    this.externalGetToken = config.getToken;
  }

  private async getToken(): Promise<string | null> {
    if (this.externalGetToken) {
      const result = this.externalGetToken();
      return resolveStorageValue(result);
    }
    return resolveStorageValue(this.storage.getItem(this.tokenKey));
  }

  /** Store a token in the configured storage adapter. */
  async setToken(token: string): Promise<void> {
    await resolveStorageValue(this.storage.setItem(this.tokenKey, token));
  }

  /** Remove the stored token. Called automatically on 401 responses. */
  async clearToken(): Promise<void> {
    await resolveStorageValue(this.storage.removeItem(this.tokenKey));
  }

  private async buildHeaders(
    extraHeaders?: Record<string, string>,
    includeAuth = true
  ): Promise<Record<string, string>> {
    const headers: Record<string, string> = {
      Accept: "application/json",
      ...extraHeaders,
    };

    if (includeAuth) {
      const token = await this.getToken();
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
    }

    return headers;
  }

  private async request<T = any>(
    method: string,
    url: string,
    data?: any,
    options: RequestOptions = {}
  ): Promise<T> {
    const query = buildQueryString(options.params);
    const fullUrl = `${this.baseURL}${url}${query}`;
    const isFormData = typeof FormData !== "undefined" && data instanceof FormData;
    // Credential endpoints: never send stale Bearer, never treat 401 as session expiry
    const isCredentialAuth =
      url.includes("/v1/auth/login") ||
      url.includes("/v1/auth/register") ||
      url.includes("/v1/auth/google") ||
      url.includes("/v1/auth/wechat");
    const headers = await this.buildHeaders(
      isFormData ? options.headers : { "Content-Type": "application/json", ...options.headers },
      !isCredentialAuth
    );

    const controller = new AbortController();
    const timeoutMs = options.timeout ?? this.defaultTimeout;
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    let response: Response;
    try {
      response = await fetch(fullUrl, {
        method,
        headers,
        body: data ? (isFormData ? data : JSON.stringify(data)) : undefined,
        signal: controller.signal,
      });
    } catch (err) {
      clearTimeout(timer);
      if (err instanceof Error && err.name === "AbortError") {
        throw new Error("request_timeout");
      }
      throw err;
    }
    clearTimeout(timer);

    if (response.status === 401) {
      const error = await this.parseError(response);
      if (!isCredentialAuth) {
        await this.clearToken();
        this.onUnauthorized?.();
      }
      throw new ApiError(
        response.status,
        error,
        (error && (error.message || error.error)) || "Unauthorized"
      );
    }

    if (!response.ok) {
      const error = await this.parseError(response);
      throw new ApiError(
        response.status,
        error,
        (error && (error.message || error.error)) || `HTTP ${response.status}`
      );
    }

    const contentType = response.headers.get("Content-Type") || "";
    if (contentType.includes("application/json")) {
      return (await response.json()) as T;
    }
    return (await response.text()) as unknown as T;
  }

  private async parseError(response: Response): Promise<Record<string, any>> {
    try {
      const data = await response.json();
      return typeof data === "object" && data !== null ? data : { message: String(data) };
    } catch {
      return { message: response.statusText || `HTTP ${response.status}` };
    }
  }

  async get<T = any>(url: string, params?: Record<string, any>, options?: RequestOptions): Promise<T> {
    return this.request<T>("GET", url, undefined, { ...options, params });
  }

  async post<T = any>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>("POST", url, data, options);
  }

  async put<T = any>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>("PUT", url, data, options);
  }

  async delete<T = any>(url: string, params?: Record<string, any>, options?: RequestOptions): Promise<T> {
    return this.request<T>("DELETE", url, undefined, { ...options, params });
  }

  /**
   * Upload a file via multipart/form-data.
   * The field name defaults to "file".
   */
  async upload<T = any>(url: string, file: File, fieldName = "file", options?: RequestOptions): Promise<T> {
    const formData = new FormData();
    formData.append(fieldName, file);

    const query = buildQueryString(options?.params);
    const fullUrl = `${this.baseURL}${url}${query}`;
    const headers = await this.buildHeaders(options?.headers, true);
    delete headers["Content-Type"];

    const controller = new AbortController();
    const timeoutMs = options?.timeout ?? this.defaultTimeout;
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    let response: Response;
    try {
      response = await fetch(fullUrl, {
        method: "POST",
        headers,
        body: formData,
        signal: controller.signal,
      });
    } catch (err) {
      clearTimeout(timer);
      if (err instanceof Error && err.name === "AbortError") {
        throw new Error("request_timeout");
      }
      throw err;
    }
    clearTimeout(timer);

    if (response.status === 401) {
      await this.clearToken();
      this.onUnauthorized?.();
      const error = await this.parseError(response);
      throw new ApiError(response.status, error, "Unauthorized");
    }

    if (!response.ok) {
      const error = await this.parseError(response);
      throw new ApiError(response.status, error, `HTTP ${response.status}`);
    }

    const contentType = response.headers.get("Content-Type") || "";
    if (contentType.includes("application/json")) {
      return (await response.json()) as T;
    }
    return (await response.text()) as unknown as T;
  }

  /**
   * SSE 流式请求。
   * 返回一个 ReadableStream<Uint8Array>，调用方可用 TextDecoder 逐段读取。
   */
  async stream(url: string, data?: any, options?: RequestOptions): Promise<ReadableStream<Uint8Array>> {
    const query = buildQueryString(options?.params);
    const fullUrl = `${this.baseURL}${url}${query}`;
    const headers = await this.buildHeaders(
      { "Content-Type": "application/json", Accept: "text/event-stream", ...options?.headers },
      true
    );

    const controller = new AbortController();
    const timeoutMs = options?.timeout ?? this.defaultTimeout;
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    const response = await fetch(fullUrl, {
      method: "POST",
      headers,
      body: data ? JSON.stringify(data) : undefined,
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (response.status === 401) {
      await this.clearToken();
      this.onUnauthorized?.();
      const error = await this.parseError(response);
      throw new ApiError(response.status, error, "Unauthorized");
    }

    if (!response.ok || !response.body) {
      const error = await this.parseError(response);
      throw new ApiError(response.status, error, `HTTP ${response.status}`);
    }

    return response.body;
  }
}

export class ApiError extends Error {
  status: number;
  body: Record<string, any>;

  constructor(status: number, body: Record<string, any>, message?: string) {
    super(message || `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

/** Factory function to create an ApiClient instance. */
export function createApiClient(config: ApiClientConfig): ApiClient {
  return new ApiClient(config);
}
