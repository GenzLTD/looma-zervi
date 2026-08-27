/** Career timeline types — aligned with backend/contracts/timeline.v1.json */
export type TimelineEventKind =
  | "initial_hypothesis"
  | "quiz_completed"
  | "project_record"
  | "check_in"
  | "interaction_log"
  | "share_authorized"
  | "match_scan"
  | "resume_ingest"
  | "mission_completed"
  | "learning_activity"
  | "career_decision"
  | "interview_session"
  | "fleet_co_presence"
  | "external_signal"
  | "emotion_signal";

export type TimelineSignalQuality =
  | "self_report"
  | "observed"
  | "external"
  | "hypothesis";

export type TimelineWeightRole = "hypothesis" | "evidence" | "calibration";

export type TimelineVisibility = "private" | "l1" | "l2" | "l3";

export interface TimelineEvent {
  id: string;
  user_id: string;
  event_kind: TimelineEventKind | string;
  occurred_at: string;
  recorded_at: string;
  source_system: string;
  source_ref: string;
  title: string;
  summary: string;
  payload: Record<string, unknown>;
  signal_quality: TimelineSignalQuality | string;
  confidence: number;
  weight_role: TimelineWeightRole | string;
  visibility: TimelineVisibility | string;
  consent_scope: string[];
  status: string;
  superseded_by?: string | null;
}

export interface TimelineListResponse {
  items: TimelineEvent[];
  next_cursor: string | null;
  count: number;
}

export interface CreateTimelineEventRequest {
  event_kind: "project_record" | "check_in" | "career_decision";
  title?: string;
  summary?: string;
  payload?: Record<string, unknown>;
  occurred_at?: string;
  visibility?: TimelineVisibility;
  source_ref?: string;
}

export interface TimelineGrowthDimension {
  id: string;
  label: string;
  level: number;
  max?: number;
  hint?: string;
}

export interface TimelineGrowthResponse {
  confidence: "low" | "medium" | "building" | string;
  message: string;
  event_count: number;
  hypothesis_present: boolean;
  hypothesis_weight_cap: number;
  dimensions: TimelineGrowthDimension[];
  version: string;
}

export interface TimelineBackfillResponse {
  ok: boolean;
  written_kinds: string[];
  event_count: number;
  note?: string;
}

export interface TimelineExportResponse {
  exported_at: string;
  user_id: string;
  event_count: number;
  l1_summary: Record<string, unknown>;
  items: TimelineEvent[];
  note: string;
}

export interface TimelineDeleteAllResponse {
  ok: boolean;
  user_id: string;
  deleted: number;
  errors: number;
  total_was: number;
  note: string;
}
