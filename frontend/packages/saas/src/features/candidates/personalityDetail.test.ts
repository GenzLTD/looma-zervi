import { describe, expect, it } from "vitest";
import { parsePersonalityDetail } from "./personalityDetail";
import type { ProfileShareView } from "@looma/shared-core";

describe("parsePersonalityDetail", () => {
  const base: ProfileShareView = {
    share_code: "ABC",
    user_id: "u1",
    user_display: "Tester",
    xp: 0,
    level: 1,
  };

  it("parses object personality_detail", () => {
    const view: ProfileShareView = {
      ...base,
      personality_type: "星云艺术家",
      personality_detail: {
        name: "星云艺术家",
        emoji: "🎨",
        tagline: "创造无限",
        traits: ["创造力"],
      },
    };
    expect(parsePersonalityDetail(view)).toMatchObject({
      name: "星云艺术家",
      emoji: "🎨",
      traits: ["创造力"],
    });
  });

  it("parses JSON string personality_detail", () => {
    const view: ProfileShareView = {
      ...base,
      personality_type: "星云艺术家",
      personality_detail: JSON.stringify({
        name: "星云艺术家",
        emoji: "🎨",
      }),
    };
    expect(parsePersonalityDetail(view).emoji).toBe("🎨");
  });

  it("falls back to personality_type when detail missing", () => {
    const view: ProfileShareView = {
      ...base,
      personality_type: "星际探索者",
    };
    expect(parsePersonalityDetail(view).name).toBe("星际探索者");
  });

  it("keeps an MBTI name and its strengths beside an archetype name", () => {
    const entj: ProfileShareView = {
      ...base,
      personality_type: "ENTJ",
      personality_detail: {
        name: "ENTJ",
        strengths: ["领导力"],
        growth: ["耐心倾听"],
      },
    };
    expect(parsePersonalityDetail(entj)).toMatchObject({
      name: "ENTJ",
      strengths: ["领导力"],
      growth: ["耐心倾听"],
    });

    const archetype: ProfileShareView = {
      ...base,
      personality_type: "星云艺术家",
      personality_detail: JSON.stringify({
        name: "星云艺术家",
        traits: ["创造力爆表"],
      }),
    };
    expect(parsePersonalityDetail(archetype).name).toBe("星云艺术家");
    expect(parsePersonalityDetail(archetype).traits).toEqual(["创造力爆表"]);
  });
});
