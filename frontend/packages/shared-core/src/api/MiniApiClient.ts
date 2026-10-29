/**
 * 小程序专用的 API 客户端
 * 移除所有 Web 特定 API 依赖
 */

export interface StorageAdapter {
  getItem(key: string): string | null | Promise<string | null>;
  setItem(key: string, value: string): void | Promise<void>;
  removeItem(key: string): void | Promise<void>;
}

export interface ApiClientConfig {
  baseURL: string;
  storage?: StorageAdapter;
  tokenKey?: string;
  onUnauthorized?: () => void;
  timeout?: number;
  getToken?: () => string | null | Promise<string | null>;
}

export interface RequestOptions {
  headers?: Record<string, string>;
  timeout?: number;
  signal?: any; // 小程序不支持 AbortSignal，保留类型兼容
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public code?: string,
    public details?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/** WeChat miniprogram wx.storage adapter. */
export function wxStorageAdapter(): StorageAdapter {
  // 小程序环境中 wx 是全局变量
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
        // ignore
      }
    },
    removeItem: (key: string) => {
      try {
        storage?.removeStorageSync(key);
      } catch {
        // ignore
      }
    },
  };
}

/**
 * 小程序兼容的 ApiClient 实现
 * 使用 wx.request 替代 fetch，保持相同接口
 */
export class MiniApiClient {
  private baseURL: string;
  private storage: StorageAdapter;
  private tokenKey: string;
  private onUnauthorized?: () => void;
  private defaultTimeout: number;
  private externalGetToken?: () => string | null | Promise<string | null>;

  constructor(config: ApiClientConfig) {
    this.baseURL = config.baseURL.replace(/\/$/, '');
    this.storage = config.storage || wxStorageAdapter();
    this.tokenKey = config.tokenKey || 'looma_token';
    this.onUnauthorized = config.onUnauthorized;
    this.defaultTimeout = config.timeout || 30000;
    this.externalGetToken = config.getToken;
  }

  private async getToken(): Promise<string | null> {
    if (this.externalGetToken) {
      const result = this.externalGetToken();
      return Promise.resolve(result);
    }
    return this.storage.getItem(this.tokenKey);
  }

  /** Store a token in the configured storage adapter. */
  async setToken(token: string): Promise<void> {
    await this.storage.setItem(this.tokenKey, token);
  }

  /** Remove the stored token. Called automatically on 401 responses. */
  async clearToken(): Promise<void> {
    await this.storage.removeItem(this.tokenKey);
  }

  private buildQueryString(params?: Record<string, any>): string {
    if (!params) return '';
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
    return parts.length ? `?${parts.join('&')}` : '';
  }

  private async buildHeaders(
    extraHeaders?: Record<string, string>,
    includeAuth = true
  ): Promise<Record<string, string>> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...extraHeaders,
    };

    if (includeAuth) {
      const token = await this.getToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
    }

    return headers;
  }

  private parseWxError(resp: any): Record<string, any> {
    try {
      const data = resp.data;
      return typeof data === 'object' && data !== null ? data : { message: String(data) };
    } catch {
      return { message: resp.statusText || `HTTP ${resp.statusCode}` };
    }
  }

  /**
   * 核心请求方法包装 wx.request
   */
  private async request<T = any>(
    method: string,
    url: string,
    data?: any,
    options: RequestOptions = {}
  ): Promise<T> {
    const fullUrl = `${this.baseURL}${url}`;
    const headers = await this.buildHeaders(options.headers);
    const timeout = options.timeout || this.defaultTimeout;

    return new Promise((resolve, reject) => {
      if (!wx?.request) {
        reject(new ApiError('wx.request not available', 501, 'NOT_SUPPORTED'));
        return;
      }
      wx.request({
        url: fullUrl,
        method: method as any,
        data: data,
        header: headers,
        timeout: timeout,
        success: (resp: any) => {
          const status = resp.statusCode;
          if (status >= 200 && status < 300) {
            resolve(resp.data as T);
          } else if (status === 401) {
            this.clearToken().then(() => {
              this.onUnauthorized?.();
              reject(new ApiError('Unauthorized', 401));
            });
          } else {
            const errorData = this.parseWxError(resp);
            // 附带请求上下文：405 白名单已于阶段3 收口移除，此处仅留作日志/排查诊断
            reject(
              new ApiError(
                errorData.message || `HTTP ${status}`,
                status,
                errorData.code,
                { ...errorData, __method: method, __path: url }
              )
            );
          }
        },
        fail: (err: any) => {
          reject(new ApiError(err.errMsg || 'Network error', 0, 'NETWORK_ERROR'));
        },
      });
    });
  }

  async get<T = any>(url: string, params?: Record<string, any>, options?: RequestOptions): Promise<T> {
    const query = this.buildQueryString(params);
    return this.request<T>('GET', `${url}${query}`, undefined, options);
  }

  async post<T = any>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>('POST', url, data, options);
  }

  async put<T = any>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>('PUT', url, data, options);
  }

  async patch<T = any>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>('PATCH', url, data, options);
  }

  async delete<T = any>(url: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('DELETE', url, undefined, options);
  }

  // 小程序不支持流式请求和文件上传，提供空实现以保持接口兼容
  async stream(_url: string, _data?: any, _callbacks?: any, _options?: RequestOptions): Promise<void> {
    throw new ApiError('Stream not supported in miniprogram', 501, 'NOT_SUPPORTED');
  }

  async upload(_url: string, _file: any, _fieldName?: string, _options?: RequestOptions): Promise<any> {
    throw new ApiError('Upload not supported in miniprogram', 501, 'NOT_SUPPORTED');
  }
}

/** Factory for creating a MiniApiClient instance. */
export function createMiniApiClient(config: ApiClientConfig): MiniApiClient {
  return new MiniApiClient(config);
}