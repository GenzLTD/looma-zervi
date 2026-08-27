/**
 * Referral / growth type definitions.
 */

import type { Candidate } from "./enterprise";

export type ReferralPurpose = "referral" | "profile_share";

export interface CreateReferralRequest {
  purpose?: ReferralPurpose;
  tier_grant?: string;
}

export interface CreateReferralResponse {
  code: string;
  purpose?: ReferralPurpose;
  tier_grant?: string;
}

export interface UseReferralRequest {
  code: string;
}

export interface UseReferralResponse {
  consumed: boolean;
  code: string;
  tier_granted: string;
}

export interface ReferralCodeEntry {
  code: string;
  tier_grant?: string;
  purpose?: ReferralPurpose;
  used_by?: string | null;
  used_at?: string | null;
  created_at?: string;
}

export interface ProfileShareView {
  share_code: string;
  user_id: string;
  user_display: string;
  personality_type?: string;
  personality_detail?: Record<string, unknown> | string | null;
  xp: number;
  level: number;
  /** L1 behaviour thickness — aggregates only (E5) */
  timeline_l1?: TimelineL1Summary;
}

/** Public/HR-safe timeline thickness (no private payloads). */
export interface TimelineL1Summary {
  level: "l1" | string;
  event_count: number;
  evidence_count?: number;
  project_count?: number;
  check_in_count?: number;
  has_thickness: boolean;
  hypothesis_present?: boolean;
  confidence: "empty" | "thin" | "building" | string;
  message: string;
  last_active_at?: string | null;
  recent_labels?: string[];
}

export interface ImportShareRequest {
  share_code: string;
}

export interface ImportShareResponse extends Candidate {
  imported?: boolean;
}
