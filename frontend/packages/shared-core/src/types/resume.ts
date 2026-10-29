/**
 * Resume / Job / Hiring type definitions.
 */

export interface ResumeExperience {
  company: string;
  title: string;
  start_date?: string;
  end_date?: string;
  description?: string;
}

export interface ResumeEducation {
  school: string;
  degree: string;
  field?: string;
  start_date?: string;
  end_date?: string;
}

export interface ResumeProject {
  name: string;
  description?: string;
  url?: string;
}

export interface ParsedResume {
  name?: string;
  email?: string;
  phone?: string;
  summary?: string;
  skills?: string[];
  experiences?: ResumeExperience[];
  education?: ResumeEducation[];
  projects?: ResumeProject[];
  languages?: string[];
  certifications?: string[];
  raw?: Record<string, any>;
}

export interface Job {
  id: string;
  title: string;
  company: string;
  location?: string;
  salary_range?: string;
  description?: string;
  requirements?: string[];
  tags?: string[];
  posted_at?: string;
  url?: string;
}

/**
 * Actual API match item returned by POST /v1/jobs/match.
 * The pipeline returns flat fields + a nested scores object (11 dimensions).
 */
export interface GapItem {
  skill: string;
  current_level: string;
  required_level: string;
  gap: string;
  suggestion: string;
  estimated_effort: string;
  priority: "high" | "medium" | "low";
}

export interface JobMatchItem {
  job_id: string;
  title: string;
  company: string;
  location: string;
  salary_range: string;
  /** JD text used for scoring (persisted as jd_snapshot on save) */
  description?: string;
  jd_snapshot?: string;
  /** Multi-dimension scores (来自 Tatha 评分引擎 11 维度) */
  scores: JobMatchScore;
  /** 一句话匹配摘要 */
  reason: string;
  matched_skills?: string[];
  missing_skills?: string[];
  fit_bullets?: string[];
  gap_analysis?: GapItem[];
  improvement_plan?: string;
  /** Attached at report-save time from in-session credit check */
  credit_snapshot?: Record<string, unknown>;
}

export interface JobMatchRequest {
  resume_text: string;
}

export interface JobMatchResponse {
  matches: JobMatchItem[];
  total_evaluated: number;
}

// Legacy alias – kept for backward compatibility with any code that imported JobMatchResult
/** @deprecated use JobMatchItem instead */
export type JobMatchResult = JobMatchItem;

// ============================================================
// Enhanced job types (migrated from Tatha scoring engine)
// ============================================================

/** Multi-dimension match score (11 dimensions from Tatha) */
export interface JobMatchScore {
  overall: number;
  background_match: number;
  skills_overlap: number;
  experience_relevance: number;
  seniority: number;
  language_requirement: number;
  company_score: number;
  salary_match: number;
  location_match: number;
  culture_workload_match: number;
  summary: string;
  keywords: string[];
  fit_bullets: string[];
  missing_skills?: string[];
  gap_analysis?: GapItem[];
  improvement_plan?: string;
}

/** Parsed job info from LLM extraction */
export interface ParsedJob {
  id?: string;
  title: string;
  company: string;
  location?: string;
  salary_range?: string;
  description?: string;
  requirements?: string[];
  responsibilities?: string[];
  tags?: string[];
  seniority_level?: string;
  employment_type?: string;
  remote_policy?: string;
  source?: string;
  posted_at?: string;
  url?: string;
}

/** Return type for POST /v1/jobs/upload (file → parsed + metadata) */
export interface JobUploadResult {
  parsed: ParsedJob | null;
  markdown: string;
  filename: string;
  job_id: string | null;
  error?: string;
}

// ============================================================
// Company Credit types (Tripod leg 3: Resume → Job → Company)
// ============================================================

/** Parsed credit analysis (supports both LLM and QCC data sources) */
export interface CreditAnalysis {
  entity_name?: string;
  report_type?: string;
  summary?: string;
}

/** Request body for POST /v1/credit/check-company */
export interface CheckCompanyRequest {
  company_name: string;
  location?: string;
  industry?: string;
}

/** QCC company basic info */
export interface QccCompanyInfo {
  name: string;
  legal_person: string;
  registered_capital: string;
  established_date: string;
  credit_code: string;
  status: string;
  industry: string;
  address: string;
  business_scope: string;
}

/** QCC risk data */
export interface QccRiskData {
  level: string;           // 低风险 / 中风险 / 高风险
  summary: string;
  count: number;
  items: Array<Record<string, string>>;
}

/** QCC operation data */
export interface QccOperationData {
  summary: string;
}

/** Extended QCC credit data (rich fields from official source) */
export interface CreditExtended {
  source: "qcc" | "llm";
  company: QccCompanyInfo;
  risk: QccRiskData;
  operation: QccOperationData;
  executives: Array<Record<string, string>>;
  ipr: Array<Record<string, string>>;
  history: Array<Record<string, string>>;
  legal_cases: Array<Record<string, string>>;
}

/** Response from POST /v1/credit/check-company */
export interface CheckCompanyResponse {
  extracted: CreditAnalysis;
  extended?: CreditExtended;
  source?: "qcc" | "llm";
  warning?: string;
}

/** Return type for POST /v1/resume/upload (file → parsed + metadata) */
export interface ResumeUploadResult {
  extracted: ParsedResume | null;
  markdown: string;
  filename: string;
  resume_id: string | null;
  /** "complete" when extraction succeeded, "partial" when only markdown was stored */
  status?: "complete" | "partial";
  error?: string;
  hint?: string;
}

/** Request body for POST /v1/resume/ingest (DemoPeter thin-ingest) */
export interface ResumeIngestRequest {
  markdown: string;
  filename?: string;
  extracted?: ParsedResume | null;
}

/** Response from POST /v1/resume/ingest */
export interface ResumeIngestResponse {
  resume_id: string;
  status: "processed" | "stored";
}

// ── HarmonyOS 简历管理 ──

export interface ResumeListItem {
  id: string;
  title: string;
  filename: string;
  file_size: number;
  uploaded_at: string;
  extracted: ParsedResume;
}

export interface ResumeListResponse {
  resumes: ResumeListItem[];
  total: number;
}

export interface ResumeAnalysisResult {
  overall_score: number;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  matched_roles: string[];
  summary: string;
}

export interface ResumeAnalysisResponse {
  resume_id: string;
  title: string;
  extracted: ParsedResume;
  /** Stored markdown snippet (powers analysis when extracted is empty) */
  markdown?: string;
  analysis: ResumeAnalysisResult | null;
}

// ============================================================
// resume.v1.json v0.1.0 — 契约缺口类型
// 契约真源: looma-zervi/backend/contracts/resume.v1.json
// 裁决 2026-10-29: visibility 单一写入口归 PUT /:resume_id/permission，
// ResumeUpdateRequest 不含 visibility（双写路径已拆）。
// ============================================================

export type ResumeVisibility = "everyone" | "trusted" | "private";

export type ResumeDocStatus = "uploaded" | "processed" | "partial";

/** GET /v1/resume/:resume_id 成功体 */
export interface ResumeDetail {
  id: string;
  title: string;
  filename: string;
  file_size?: number;
  uploaded_at: string;
  extracted: ParsedResume;
  /** 原文/转换后 markdown；private 默认仅 owner 可得 */
  markdown?: string;
  visibility: ResumeVisibility;
  status?: ResumeDocStatus;
}

/** PUT /v1/resume/:resume_id 请求体 — 只写正文相关字段，未传字段服务端 merge */
export interface ResumeUpdateRequest {
  title?: string;
  extracted?: ParsedResume;
  markdown?: string;
}

export type PermissionScope = "read" | "download";

export interface ResumePermissionGrant {
  subject_type: "user" | "enterprise" | "share_code_ref";
  subject_id: string;
  scope: PermissionScope;
  expires_at?: string | null;
}

/** GET/PUT /v1/resume/:resume_id/permission — 简历维授权面 */
export interface ResumePermission {
  resume_id: string;
  visibility: ResumeVisibility;
  /** 全量替换语义；PUT 时省略即视为 []（清空）——必须先 GET 再 PUT */
  grants: ResumePermissionGrant[];
  /** 服务端生成；客户端传入忽略（last-write-wins 检测用） */
  updated_at?: string;
}

export type BlacklistMatch = "exact_name" | "credit_code" | "enterprise_id";

export interface ResumeBlacklistItem {
  id: string;
  company_name: string;
  credit_code?: string;
  enterprise_id?: string;
  match: BlacklistMatch;
  created_at?: string;
  note?: string;
}

/** POST /v1/resume/blacklist — match 枚举分情况必填 */
export interface ResumeBlacklistAddRequest {
  match: BlacklistMatch;
  /** match=exact_name 时必填 */
  company_name?: string;
  /** match=credit_code 时必填 */
  credit_code?: string;
  /** match=enterprise_id 时必填 */
  enterprise_id?: string;
  note?: string;
}

export interface ResumeBlacklistResponse {
  items: ResumeBlacklistItem[];
  total: number;
}

export interface ResumeTemplate {
  id: string;
  name: string;
  /** zh-CN | en-US */
  locale: string;
  summary?: string;
  tags?: string[];
  /** 建议填充的 ParsedResume 字段名 */
  preview_fields?: string[];
}

/** GET /v1/resume/templates — 全局目录，0.1 只读（写操作需另开 /custom 端点升 minor） */
export interface ResumeTemplatesResponse {
  templates: ResumeTemplate[];
  total: number;
}
