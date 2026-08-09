/**
 * P0 — Jobs match API (Vultr / overseas)
 *
 * JD parse → resume×JD match → credit (consent) → save match report
 *
 *   E2E_OVERSEAS_API=https://api.genz.ltd pnpm e2e:overseas:jobs
 */
import { test, expect } from "@playwright/test";
import {
  registerOverseasUser,
  grantConsent,
  parseJD,
  matchJob,
  checkCredit,
  saveMatchReport,
  apiStatus,
  SAMPLE_JD,
  SAMPLE_RESUME,
} from "./helpers/overseasApi";

test.describe.configure({ mode: "serial" });

const SCORE_KEYS = [
  "overall",
  "background_match",
  "skills_overlap",
  "experience_relevance",
  "seniority",
  "language_requirement",
  "company_score",
  "salary_match",
  "location_match",
  "culture_workload_match",
] as const;

test.describe("jobs match API @overseas @live", () => {
  test("match returns 403 without jobseeker_core consent", async () => {
    const { token } = await registerOverseasUser("E2E Jobs Consent");

    const denied = await apiStatus("/v1/jobs/match", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        resume_text: SAMPLE_RESUME,
        job_description: SAMPLE_JD,
      }),
    });

    expect(denied.status).toBe(403);
    expect(denied.body.error).toBe("consent_required");
    expect(denied.body.required_scope).toBe("jobseeker_core");
  });

  test("parse JD returns structured fields", async () => {
    test.setTimeout(180_000);
    const { token } = await registerOverseasUser("E2E Jobs Parse");
    await grantConsent(token, "jobseeker_core");

    const { parsed, job_id } = await parseJD(token, SAMPLE_JD);
    expect(parsed).toBeTruthy();
    expect(String(parsed.title || "").trim().length).toBeGreaterThan(0);
    // company / skills / description are best-effort LLM fields
    const nonempty = ["title", "company", "skills", "description", "requirements"].filter(
      (k) => {
        const v = parsed[k];
        if (Array.isArray(v)) return v.length > 0;
        return String(v ?? "").trim().length > 0;
      },
    );
    expect(nonempty.length).toBeGreaterThanOrEqual(2);
    // paste parse usually persists a job_id
    if (job_id) {
      expect(typeof job_id).toBe("string");
    }
  });

  test("match scores dimensions + save report", async () => {
    test.setTimeout(240_000);
    const { token } = await registerOverseasUser("E2E Jobs Match");
    await grantConsent(token, "jobseeker_core");

    const { job_id } = await parseJD(token, SAMPLE_JD);

    const result = await matchJob(token, SAMPLE_RESUME, {
      ...(job_id ? { job_id } : { job_description: SAMPLE_JD }),
    });

    expect(result.total_evaluated).toBeGreaterThan(0);
    expect(Array.isArray(result.matches)).toBe(true);
    expect(result.matches.length).toBeGreaterThan(0);

    const top = result.matches[0];
    const scores = (top.scores || {}) as Record<string, unknown>;
    expect(scores).toBeTruthy();

    const overall = Number(scores.overall ?? top.overall_score ?? 0);
    expect(overall).toBeGreaterThanOrEqual(0);
    expect(overall).toBeLessThanOrEqual(100);

    let dimOk = 0;
    for (const key of SCORE_KEYS) {
      if (scores[key] === undefined || scores[key] === null) continue;
      const n = Number(scores[key]);
      expect(n).toBeGreaterThanOrEqual(0);
      expect(n).toBeLessThanOrEqual(100);
      dimOk += 1;
    }
    expect(dimOk).toBeGreaterThanOrEqual(3);

    // analysis / gap fields are optional but when present should be structured
    if (top.gap_analysis !== undefined) {
      expect(Array.isArray(top.gap_analysis) || typeof top.gap_analysis === "object").toBe(
        true,
      );
    }

    const report = await saveMatchReport(token, {
      resume_text: SAMPLE_RESUME,
      matches: result.matches,
      title: `E2E match ${Date.now()}`,
    });
    expect(report.id).toBeTruthy();
  });

  test("credit check gated by credit_query consent", async () => {
    test.setTimeout(120_000);
    const { token } = await registerOverseasUser("E2E Jobs Credit");

    const denied = await checkCredit(token, "星云科技有限公司");
    expect(denied.status).toBe(403);
    expect(denied.body.error).toBe("consent_required");
    expect(denied.body.required_scope).toBe("credit_query");

    await grantConsent(token, "credit_query");
    const allowed = await checkCredit(token, "星云科技有限公司");
    // Upstream QCC/AI may be unavailable on some envs — accept 200 or soft failure
    if (allowed.status === 200) {
      expect(allowed.body.extracted || allowed.body.company || allowed.body).toBeTruthy();
    } else {
      expect([502, 503, 500, 429]).toContain(allowed.status);
      test.info().annotations.push({
        type: "note",
        description: `credit upstream soft-fail: ${allowed.status} ${JSON.stringify(allowed.body).slice(0, 200)}`,
      });
    }
  });
});
