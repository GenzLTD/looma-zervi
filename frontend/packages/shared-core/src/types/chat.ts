/**
 * Chat / Ask / RAG type definitions.
 */

export interface DocSource {
  chunk_text: string;
  score?: number;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  sources?: DocSource[];
  timestamp?: string;
}

/** SaaS 智能问答 RAG 模式：对话=多轮 / 深度=更多检索+长推理 / 快速=少检索+低温度 */
export type AskMode = "chat" | "deepseek" | "fast";

export interface AskRequest {
  query: string;
  /** RAG mode — chat | deepseek | fast (default chat) */
  mode?: AskMode;
  navigator_mode?: boolean;
  navigator_system_prompt?: string;
  session_history?: ChatMessage[];
  current_stage?: string;
  active_domain?: string;
  /** Optional saved match report for summary-level Ask context */
  report_id?: string;
  /** When true and report_id omitted, backend may attach the latest report */
  use_latest_report?: boolean;
}

export interface AskResponse {
  answer: string;
  intent?: string;
  sources?: DocSource[];
  tokens_used?: number;
  extracted?: Record<string, any>;
  /** Echo of resolved AskMode from backend */
  mode?: AskMode;
}

export interface StreamCallbacks {
  onMessage?: (chunk: any) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

export interface RateRequest {
  query_id: number;
  rating: number;
}

export interface LastQueryResponse {
  has_query: boolean;
  query_id?: number;
}
