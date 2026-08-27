/**
 * Auth-related type definitions.
 * These mirror the backend response structures exactly.
 * Backend changes must update these types first (dual review).
 */

export type Tier = "free" | "supporter" | "pro" | "enterprise";
export type Role = "user" | "admin";

export interface User {
  id: string;
  email: string | null;
  name: string;
  tier: Tier;
  role: Role;
}

export interface UserProfile extends User {
  is_early_adopter: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

/** Alias for backward compatibility with consumers expecting LoginResponse. */
export interface LoginResponse extends AuthResponse {}

/** Alias for backward compatibility with consumers expecting RegisterResponse. */
export interface RegisterResponse extends AuthResponse {}

/** Alias for backward compatibility with consumers expecting WechatLoginResponse. */
export interface WechatLoginResponse extends AuthResponse {}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name?: string;
}

export interface WechatAuthRequest {
  code: string;
}

export interface WechatAuthResponse extends AuthResponse {}

/** Google OAuth (overseas) — ID token from GIS / One Tap */
export interface GoogleAuthRequest {
  id_token: string;
}

export interface GoogleAuthResponse extends AuthResponse {}

export interface QuotaRecord {
  resource: string;
  daily_limit: number;
  used: number;
}

export interface QuotaResponse {
  tier: Tier;
  records: QuotaRecord[];
}

export interface TokenPayload {
  sub: string; // looma user_id
  iat: number; // issued at (unix timestamp)
  exp: number; // expiry (unix timestamp)
  iss: "looma";
  tier?: Tier;
  email?: string;
}
