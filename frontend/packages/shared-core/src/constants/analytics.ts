/**
 * Closed-loop funnel event names (sync with backend VALID_EVENTS).
 */
import type { ClosedLoopEventName } from "../types/analytics";

export const CLOSED_LOOP_EVENTS: Record<string, ClosedLoopEventName> = {
  QUIZ_COMPLETE: "quiz_complete",
  SHARE_CODE_CREATED: "share_code_created",
  SHARE_LINK_COPIED: "share_link_copied",
  PROFILE_VIEW_PUBLIC: "profile_view_public",
  HR_REGISTER_FROM_SHARE: "hr_register_from_share",
  CANDIDATE_IMPORTED: "candidate_imported",
  TRIAL_STARTED: "trial_started",
  TRIAL_CLICKED: "trial_clicked",
  TIER_ACTIVATED: "tier_activated",
} as const;

export const ANALYTICS_SESSION_KEY = "looma_analytics_session";

export const MICRO_FEEDBACK_CONTEXT = {
  PLANETX_RESULT: "planetx_result",
  TSPACE_PROFILE_SHARE: "tspace_profile_share",
  TSPACE_PRICING: "tspace_pricing",
} as const;
