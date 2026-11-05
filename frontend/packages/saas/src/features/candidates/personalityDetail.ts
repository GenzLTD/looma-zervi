/**
 * Parse personality_detail from referral profile view (shared by CandidateShare).
 */
import type { ProfileShareView } from "@looma/shared-core";

export interface PersonalityCard {
  name?: string;
  emoji?: string;
  tagline?: string;
  desc?: string;
  traits?: string[];
  strengths?: string[];
  growth?: string[];
}

export function textList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

export function parsePersonalityDetail(view: ProfileShareView): PersonalityCard {
  const raw = view.personality_detail;
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    return normalizeCard(raw as PersonalityCard);
  }
  if (typeof raw === "string" && raw.trim()) {
    try {
      const parsed = JSON.parse(raw) as PersonalityCard;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return normalizeCard(parsed);
      }
    } catch {
      /* fall through */
    }
  }
  return { name: view.personality_type ?? "未知类型" };
}

function normalizeCard(card: PersonalityCard): PersonalityCard {
  return {
    ...card,
    name: card.name || undefined,
    traits: textList(card.traits),
    strengths: textList(card.strengths),
    growth: textList(card.growth),
  };
}
