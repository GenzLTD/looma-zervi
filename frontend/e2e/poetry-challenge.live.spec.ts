/**
 * P1 — Overseas poetry = Xin-Da-Ya weekly *translation* challenge (not mainland browse UX).
 *
 * Real Vultr API (ChromaDB poem pool feeds the weekly round):
 *   GET  /v1/poetry/challenge/current
 *   POST /v1/poetry/challenge/entries  { translation, license_accepted, round_id? }
 *
 *   E2E_OVERSEAS_API=https://api.genz.ltd pnpm e2e:overseas:poetry
 */
import { test, expect } from "@playwright/test";
import {
  registerOverseasUser,
  getPoetryChallengeCurrent,
  submitPoetryTranslation,
  getPoetryStats,
  apiStatus,
} from "./helpers/overseasApi";

test.describe.configure({ mode: "serial" });

test.describe("poetry translation challenge @overseas @live", () => {
  test("poem library underpins challenge (stats non-empty)", async () => {
    const stats = await getPoetryStats();
    expect(stats.total).toBeGreaterThan(0);
  });

  test("current challenge returns open round + poem", async () => {
    const { status, body } = await getPoetryChallengeCurrent();
    expect(status).toBe(200);
    expect(body.round).toBeTruthy();
    expect(body.poem).toBeTruthy();

    const round = body.round as Record<string, unknown>;
    const poem = body.poem as Record<string, unknown>;
    expect(round.status).toBe("open");
    expect(round.id).toBeTruthy();
    expect(round.week_key).toBeTruthy();
    expect(String(poem.title || "").length).toBeGreaterThan(0);
    expect(String(poem.content || "").length).toBeGreaterThan(0);
    // Overseas challenge title convention
    expect(String(round.title || "")).toMatch(/Xin-Da-Ya/i);
  });

  test("submit without auth returns 401", async () => {
    const current = await getPoetryChallengeCurrent();
    const round = current.body.round as { id: number };
    const denied = await apiStatus("/v1/poetry/challenge/entries", {
      method: "POST",
      body: JSON.stringify({
        round_id: round.id,
        translation: "Bright moths of spring, twin brows of autumn frost.",
        license_accepted: true,
      }),
    });
    expect(denied.status).toBe(401);
  });

  test("reject non-English / missing license / too short", async () => {
    const { token } = await registerOverseasUser("E2E Poetry Guard");
    const current = await getPoetryChallengeCurrent(token);
    const roundId = (current.body.round as { id: number }).id;

    const noLicense = await submitPoetryTranslation(token, {
      round_id: roundId,
      translation: "A graceful English stanza for the challenge.",
      license_accepted: false,
    });
    expect(noLicense.status).toBe(400);
    expect(noLicense.body.error).toBe("license_required");

    const tooShort = await submitPoetryTranslation(token, {
      round_id: roundId,
      translation: "Hi",
      license_accepted: true,
    });
    expect(tooShort.status).toBe(400);
    expect(tooShort.body.error).toBe("translation_too_short");

    const chineseOnly = await submitPoetryTranslation(token, {
      round_id: roundId,
      translation: "春蚕到死丝方尽，蜡炬成灰泪始干。",
      license_accepted: true,
    });
    expect(chineseOnly.status).toBe(400);
    expect(chineseOnly.body.error).toBe("translation_not_english");
  });

  test("submit English translation then update", async () => {
    const { token } = await registerOverseasUser("E2E Poetry Submit");
    const current = await getPoetryChallengeCurrent(token);
    expect(current.status).toBe(200);
    const roundId = (current.body.round as { id: number }).id;
    const poemTitle = String((current.body.poem as { title?: string }).title || "poem");

    const translation = [
      `E2E Xin-Da-Ya rendering for 「${poemTitle}」.`,
      "Spring moths are tender; autumn brows cut deep.",
      "Joy arrives too late — yet the heart stays young in wine.",
    ].join(" ");

    const created = await submitPoetryTranslation(token, {
      round_id: roundId,
      translation,
      note: "faithfulness over flourish",
      license_accepted: true,
    });
    expect(created.status).toBe(200);
    const entry = created.body.entry as Record<string, unknown>;
    expect(entry.translation).toBe(translation);
    expect(entry.license_accepted).toBe(true);

    const updatedText = `${translation} (revised for elegance)`;
    const updated = await submitPoetryTranslation(token, {
      round_id: roundId,
      translation: updatedText,
      license_accepted: true,
    });
    expect(updated.status).toBe(200);
    expect((updated.body.entry as Record<string, unknown>).translation).toBe(updatedText);

    const mine = await getPoetryChallengeCurrent(token);
    expect((mine.body.my_entry as Record<string, unknown>)?.translation).toBe(updatedText);
  });
});
