/**
 * Enterprise / T空间 B-end type definitions.
 */

export interface CreateEnterpriseRequest {
  name: string;
  domain?: string;
}

export interface JoinEnterpriseRequest {
  enterprise_id: string;
}

export interface EnterpriseProfile {
  id: string;
  name: string;
  domain?: string;
  role: "admin" | "member";
  created_at?: string;
}

export interface Candidate {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  status?: string;
  user_id?: string;
  profile_data?: Record<string, unknown>;
  created_at?: string;
  imported?: boolean;
  trust_profile?: { attestations?: unknown[]; total?: number };
  timeline_l1?: import("./referral").TimelineL1Summary;
}

export interface AddCandidateRequest {
  name: string;
  email?: string;
  phone?: string;
  profile_data?: Record<string, any>;
}

export interface AddCandidateResponse {
  name: string;
  email?: string;
  status: string;
}

export interface ContactSalesRequest {
  company_name: string;
  contact_name: string;
  contact_email: string;
  contact_phone?: string;
  scale?: string;
  message?: string;
}

export interface ContactSalesResponse {
  ok: boolean;
  id: string;
  message: string;
}

export interface JobPost {
  id: string;
  user_id: string;
  title: string;
  company?: string;
  description?: string;
  requirements?: string | string[];
  status: "active" | "closed" | "draft";
  created_at?: string;
  updated_at?: string;
}

export interface JobPostListResponse {
  job_posts: JobPost[];
  limit: number | null;
  count: number;
}

export interface JobPostMatch {
  candidate: Candidate;
  match_score: number;
}

export interface JobPostMatchesResponse {
  job_post: JobPost;
  matches: JobPostMatch[];
  total: number;
}

export interface CandidateListResponse {
  candidates: Candidate[];
  limit: number | null;
  total: number;
}
