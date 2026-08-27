/** Consent scopes — keep in sync with backend ALL_SCOPES */
export type ConsentScope =
  | "jobseeker_core"
  | "credit_query"
  | "report_share"
  | "resume_upload"
  | "resume_parse"
  | "job_match"
  | "report_generate"
  | "credit_analyze"
  | "profile_share"
  | "ask_rag"
  | "mbti_analyze"
  | "navigator_memory";

/** Three product tiers for the jobseeker main path */
export type PrimaryConsentScope =
  | "jobseeker_core"
  | "credit_query"
  | "report_share";

export interface ConsentRecord {
  id: string;
  scope: ConsentScope;
  purpose?: string;
  status: "granted" | "revoked" | "expired";
  granted_at?: string;
  revoked_at?: string | null;
}

export interface ConsentStatusResponse {
  user_id: string;
  consents: ConsentRecord[];
  status: Record<ConsentScope, boolean>;
  primary_tiers?: PrimaryConsentScope[];
  packages?: Partial<Record<ConsentScope, ConsentScope[]>>;
}

export interface ConsentGrantResponse {
  consent_id?: string;
  already_granted?: boolean;
  granted?: number;
  results?: Array<{ scope: string; consent_id?: string; error?: string }>;
  expanded?: Array<{ scope: string; consent_id?: string; already_granted?: boolean }>;
}

export interface ConsentRequiredResponse {
  available_scopes: ConsentScope[];
  details: Record<ConsentScope, string>;
  primary_tiers?: PrimaryConsentScope[];
  packages?: Partial<Record<ConsentScope, ConsentScope[]>>;
}

export interface ConsentRequiredError {
  error: "consent_required";
  message: string;
  required_scope: ConsentScope;
  action?: "grant_consent";
}
