/**
 * Product analytics types — closed-loop funnel (内测).
 * @see docs/内测埋点与闭环漏斗方案.md
 */

export type AnalyticsPlatform =
  | "planetx_web"
  | "planetx_mp"
  | "tspace_web"
  | "unknown";

export type ClosedLoopEventName =
  | "quiz_complete"
  | "share_code_created"
  | "share_link_copied"
  | "profile_view_public"
  | "profile_view_failed"
  | "hr_register_from_share"
  | "candidate_imported"
  | "candidate_import_duplicate"
  | "trial_started"
  | "trial_failed"
  | "trial_clicked"
  | "tier_activated"
  | "funnel_drop";

export interface ProductEventPayload {
  event_name: ClosedLoopEventName;
  session_id?: string;
  platform?: AnalyticsPlatform;
  share_code?: string;
  success?: boolean;
  properties?: Record<string, unknown>;
}

export interface AnalyticsEventsRequest {
  events: ProductEventPayload[];
}

export type MicroFeedbackContext =
  | "planetx_result"
  | "tspace_profile_share"
  | "tspace_pricing";

export interface MicroFeedbackRequest {
  context: MicroFeedbackContext;
  /** 0 = negative, 1 = positive, or 1–5 scale */
  score: number;
  optional_text?: string;
  session_id?: string;
  platform?: AnalyticsPlatform;
  share_code?: string;
}

export interface FunnelStatsResponse {
  days: number;
  steps: Record<string, number>;
  conversion: Record<string, number | null>;
  micro_feedback: Array<{
    context: string;
    count: number;
    avg_score: number | null;
  }>;
  other_events: Record<string, number>;
}
