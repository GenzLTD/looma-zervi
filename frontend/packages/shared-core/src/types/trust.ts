/**
 * Trust protocol types — aligned with backend/contracts/trust.v1.json
 */

export type TrustClaimType =
  | "identity"
  | "collaboration"
  | "communication"
  | "influence";

export type TrustEvidenceType =
  | "quiz"
  | "fleet_consensus"
  | "dialogue_analysis"
  | "share_signal"
  | "credential"
  | "match_scan"
  | "resume"
  | "fleet"
  | string;

export type TrustVerificationStatus =
  | "verified"
  | "verified_by_authority"
  | "weak"
  | "unverified"
  | string;

export interface TrustAttestation {
  attestation_id: string;
  candidate_id: string;
  claim_type: TrustClaimType | string;
  claim_statement: string;
  evidence_type: TrustEvidenceType;
  verification_status: TrustVerificationStatus;
  evidence_refs: string[];
  confidence_score: number;
  issued_at: string;
  expires_at?: string | null;
  signature?: string;
}

export interface TrustAttestationsResponse {
  attestations: TrustAttestation[];
  total: number;
}

export interface CreateShareCodeRequest {
  scope?: TrustClaimType[];
  max_access_count?: number;
  expires_in_seconds?: number;
}

export interface CreateShareCodeResponse {
  share_code: string;
  expires_at: string;
  scope: TrustClaimType[] | string[];
  remaining_access_count: number;
}

export interface TrustShareCode {
  id: string;
  code: string;
  owner_id: string;
  scope: string;
  max_access_count: number;
  access_count: number;
  expires_at: string;
  status: string;
  created_at: string;
}

export interface TrustShareCodesResponse {
  share_codes: TrustShareCode[];
  total: number;
}

export interface TrustVerifyRequest {
  share_code: string;
}

export interface TrustVerifyResponse {
  attestations: TrustAttestation[];
  total?: number;
  owner_id?: string;
  scope?: string[];
  remaining_access_count?: number;
  candidate_alias?: string;
  verified_at?: string;
  share_code_scope?: string[];
}

export interface TrustAuditLogEntry {
  id: string;
  share_code: string;
  owner_id: string;
  verifier_info: string;
  attestation_ids: string;
  result: string;
  created_at: string;
}

export interface TrustAuditLogResponse {
  audit_logs: TrustAuditLogEntry[];
  total: number;
}

export interface TrustPublicKeyResponse {
  algorithm: string;
  public_key_pem: string;
  usage: string;
}
