/**
 * Admin dashboard types — mirrors backend admin_routes.py responses.
 * Used by AdminDashboard to render the management panel.
 */

/** GET /v1/admin/stats */
export interface AdminStatsResponse {
  users: {
    total: number;
    by_tier: Record<string, number>;
    by_role: Record<string, number>;
    early_adopters: number;
    new_today: number;
    new_this_week: number;
    recent: AdminRecentUser[];
  };
  activity: {
    total_queries: number;
    total_resumes: number;
    total_jobs: number;
    total_matches: number;
    total_poems: number;
    dau_trend: AdminDauPoint[];
  };
  system: {
    db_size_bytes: number;
    db_size_mb: number;
  };
}

export interface AdminRecentUser {
  id: string;
  email: string | null;
  name: string;
  tier: string;
  role: string;
  created_at: string;
}

export interface AdminDauPoint {
  day: string;
  count: number;
}

/** GET /v1/admin/funnel */
export interface AdminFunnelResponse {
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

/** GET /v1/admin/narrative */
export interface AdminNarrativeResponse {
  total_sessions: number;
  completed_sessions: number;
  completion_rate: number;       // backend returns 0-100 percentage
  feedback_count: number;
  resonance_rate: number;        // backend returns 0-100 percentage
  share_rate: number;            // backend returns 0-100 percentage
  replay_intent_rate: number;    // backend returns 0-100 percentage
  top_quotes: Array<{ quote: string; count: number }>;
  domains: Array<{ domain: string; count: number }>;
  open_feedback: Array<{ domain: string; text: string; at: string }>;
}

/** GET /v1/admin/health */
export interface AdminHealthResponse {
  status: string;
  service: string;
  environment: string;
  python: {
    version: string;
    executable: string;
  };
  platform: string;
  database: {
    size_mb: number;
    journal_mode: string;
    table_counts: Record<string, number>;
  };
  llm: {
    provider: string;
    embedding_model: string;
  };
  process: {
    pid: number;
    start_time: number | null;
  };
}
