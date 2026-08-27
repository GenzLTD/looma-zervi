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
