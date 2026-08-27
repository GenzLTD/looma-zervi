/**
 * Xin-Da-Ya poetry translation challenge (overseas MVP).
 */

export interface ChallengePoem {
  id: number;
  title: string;
  author: string;
  dynasty: string;
  theme: string;
  content: string;
}

export interface ChallengeRound {
  id: number;
  week_key: string;
  title: string;
  status: "open" | "closed" | string;
  starts_at: string;
  ends_at: string;
  poem_id: number;
}

export interface ChallengeEntry {
  id: number;
  round_id: number;
  translation: string;
  note: string;
  license_accepted: boolean;
  vote_count: number;
  created_at?: string;
  updated_at?: string;
}

export interface ChallengeCurrentResponse {
  round: ChallengeRound | null;
  poem: ChallengePoem | null;
  my_entry: ChallengeEntry | null;
  error?: string;
  message?: string;
}
