/**
 * Game / XP / Fleet / Personality type definitions.
 */

export type Identity = "explorer" | "builder" | "connector" | "strategist";

export type PersonalityType =
  | "INTJ"
  | "INTP"
  | "ENTJ"
  | "ENTP"
  | "INFJ"
  | "INFP"
  | "ENFJ"
  | "ENFP"
  | "ISTJ"
  | "ISFJ"
  | "ESTJ"
  | "ESFJ"
  | "ISTP"
  | "ISFP"
  | "ESTP"
  | "ESFP";

export type TraitKey =
  | "E"
  | "I"
  | "S"
  | "N"
  | "T"
  | "F"
  | "J"
  | "P";

export interface QuizOption {
  label: string;
  value: string;
  trait: TraitKey;
  weight?: number;
}

export interface QuizQuestion {
  id: string;
  text: string;
  options: QuizOption[];
}

export type RankName =
  | "青铜星尘"
  | "白银陨石"
  | "黄金行星"
  | "铂金星云"
  | "钻石星系"
  | "星舰指挥官";

export const RANK_NAMES: Record<number, RankName> = {
  1: "青铜星尘",
  2: "白银陨石",
  3: "黄金行星",
  4: "铂金星云",
  5: "钻石星系",
  6: "星舰指挥官",
};

export function getRankName(level: number): RankName {
  const rank = Math.min(Math.max(level, 1), 6);
  return RANK_NAMES[rank] ?? "青铜星尘";
}

export type MissionId =
  | "first_ask"
  | "complete_resume"
  | "job_match"
  | "share_planetx"
  | "join_fleet"
  | "daily_login"
  | string;

export interface Mission {
  id: MissionId;
  name: string;
  description: string;
  xp_reward: number;
  completed?: boolean;
  completed_at?: string;
}

export interface GameProfile {
  id: string;
  user_id: string;
  identity?: string;
  personality_type: string;
  personality_detail: string;
  xp: number;
  level: number;
  missions_completed: number | string[];
  total_mission_xp: number;
  updated_at: string;
  /** 完成首任务的被邀请人数（Hub 信号传播） */
  spread_count?: number;
  team_size?: number;
  fleet_members?: string[];
}

export interface ProfileSyncRequest {
  personality_type?: string;
  personality_detail?: string;
  identity?: string;
}

export interface MissionCompleteRequest {
  mission_id: MissionId;
  xp_reward?: number;
}

export interface MissionCompleteResponse {
  message: string;
  mission_id: MissionId;
  xp_earned: number;
  total_xp: number;
  level: number;
}

/** PlanetX 共识裂变 — match 响应扩展（阶段二） */
export type ConsensusStatus =
  | "consensus_passed"
  | "consensus_weak"
  | "consensus_failed"
  | "consensus_verified";

export interface MatchSpreadHint {
  show_share_cta: boolean;
  message: string | null;
  spread_count: number;
  spread_target: number;
}

export interface MatchConsensusItem {
  id: string;
  candidate_name: string;
  match_score: number;
  status: ConsensusStatus;
  is_incoming: boolean;
}

export interface MatchConsensusListResponse {
  pending: MatchConsensusItem[];
  verified: MatchConsensusItem[];
}

/** PlanetX 舰队内 1:1 匹配结果（POST /v1/game/match） */
export interface FleetMatchCandidate {
  user_id: string;
  name: string;
  personality_type: string;
  personality_emoji: string;
  match_score: number;
  reason: string;
  /** complementary | random | candidate */
  match_mode?: string;
}

export interface FleetMatchResponse {
  matched: boolean;
  match: FleetMatchCandidate;
  self: {
    user_id: string;
    personality_type: string;
    personality_emoji: string;
  };
  fleet_id: string;
  fleet_name: string;
  candidates_considered: number;
  /** 阶段二：共识阈值（默认 85） */
  consensus_threshold?: number;
  consensus_status?: ConsensusStatus;
  consensus_passed?: boolean;
  can_complete_mission?: boolean;
  pending_consensus_id?: string | null;
  spread_hint?: MatchSpreadHint;
}

export interface Fleet {
  id: string;
  name: string;
  captain_id: string;
  description?: string;
  member_count: number;
  created_at: string;
}

export interface FleetMember {
  user_id: string;
  name: string;
  role: "captain" | "member";
  joined_at: string;
}

export interface CreateFleetRequest {
  name: string;
  description?: string;
}

export interface JoinFleetRequest {
  fleet_id: string;
}

export interface FleetResponse {
  id: string;
  name: string;
  captain_id: string;
  description?: string;
  member_count: number;
  created_at: string;
}

export interface MyFleetResponse {
  fleet?: Fleet;
  members?: FleetMember[];
  member_count: number;
  message?: string;
}

export type GameScreen =
  | "home"
  | "profile"
  | "missions"
  | "fleet"
  | "quiz"
  | "rank"
  | "shop";

export type SharePlatform = "wechat" | "moment" | "copy" | "qq" | "weibo";

// ── HarmonyOS 答题游戏 (Quiz Game) ──

export interface QuizGameOption {
  id: string;
  text: string;
  value: number;
}

export interface QuizGameQuestion {
  id: string;
  text: string;
  type: "single" | "multiple";
  order: number;
  options: QuizGameOption[];
}

export interface QuizStartResponse {
  session_id: string;
  questions: QuizGameQuestion[];
  total: number;
}

export interface QuizAnswerRequest {
  session_id: string;
  question_id: string;
  option_ids: string[];
}

export interface QuizAnswerResponse {
  correct: boolean;
  score: number;
  explanation: string;
  completed: boolean;
  next_question?: QuizGameQuestion;
}

export interface QuizResultResponse {
  session_id: string;
  total_score: number;
  total_questions: number;
  correct_count: number;
  result_type: string;
  insights: string[];
}

export interface QuizHistoryItem {
  id: string;
  total_score: number;
  total_questions: number;
  correct_count: number;
  result_type: string;
  status: string;
  created_at: string;
  completed_at: string | null;
}

export interface QuizHistoryResponse {
  sessions: QuizHistoryItem[];
  total: number;
}
