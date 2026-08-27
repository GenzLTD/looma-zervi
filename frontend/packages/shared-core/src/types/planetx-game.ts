/**
 * PlanetX game types — canonical for planetx Web + miniprogram.
 * Distinct from legacy types/game.ts (MBTI scaffold); dual review required.
 */

export type Identity = "explorer" | "captain" | "wanderer";

export const IDENTITY_LABELS: Record<Identity, string> = {
  explorer: "星际探索者 · 求职模式",
  captain: "舰队舰长 · 组队模式",
  wanderer: "星际漫游者 · 探索模式",
};

export type TraitKey =
  | "social"
  | "introvert"
  | "growth"
  | "wanderer"
  | "planner"
  | "action"
  | "thinker"
  | "creative"
  | "balance"
  | "leader"
  | "perfectionist"
  | "supporter";

export interface PersonalityType {
  name: string;
  emoji: string;
  tagline: string;
  desc: string;
  traits: string[];
}

export interface QuizOption {
  text: string;
  trait: TraitKey;
}

export interface QuizQuestion {
  q: string;
  options: QuizOption[];
}

export type PlanetXRankName =
  | "星际新兵"
  | "星域探索者"
  | "银河领航员"
  | "星际指挥官"
  | "宇宙传奇";

/** Level → rank title (PlanetX miniprogram / Web). */
export function getPlanetXRankName(level: number): PlanetXRankName {
  if (level <= 3) return "星际新兵";
  if (level <= 6) return "星域探索者";
  if (level <= 10) return "银河领航员";
  if (level <= 15) return "星际指挥官";
  return "宇宙传奇";
}

export type PlanetXMissionId = "personality" | "team" | "match" | "share";

export type PlanetXGameScreen =
  | "loading"
  | "auth"
  | "onboarding"
  | "hub"
  | "quiz"
  | "result"
  | "match"
  | "timeline"
  | "trust";

export interface PlanetXFleet {
  id: string;
  name: string;
  invite_code: string;
  captain_id: string;
}
