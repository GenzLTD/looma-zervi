/**
 * P0 — Resume AI parse API (Vultr / overseas)
 *
 *   E2E_OVERSEAS_API=https://api.genz.ltd pnpm e2e:overseas:resume
 */
import { test, expect } from "@playwright/test";
import {
  registerOverseasUser,
  grantConsent,
  parseResumeText,
  apiStatus,
  SAMPLE_RESUME,
} from "./helpers/overseasApi";

test.describe.configure({ mode: "serial" });

test.describe("resume parse API @overseas @live", () => {
  test("parse returns 403 without jobseeker_core consent", async () => {
    const { token } = await registerOverseasUser("E2E Resume Consent");

    const denied = await apiStatus("/v1/resume/parse", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ text: SAMPLE_RESUME }),
    });

    expect(denied.status).toBe(403);
    expect(denied.body.error).toBe("consent_required");
    expect(denied.body.required_scope).toBe("jobseeker_core");
  });

  test("empty text returns 400", async () => {
    const { token } = await registerOverseasUser("E2E Resume Empty");
    await grantConsent(token, "jobseeker_core");

    const bad = await apiStatus("/v1/resume/parse", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ text: "   " }),
    });

    expect(bad.status).toBe(400);
    expect(bad.body.error).toBe("bad_request");
  });

  test("parse extracts core resume fields", async () => {
    test.setTimeout(180_000);
    const { token } = await registerOverseasUser("E2E Resume Parse");
    await grantConsent(token, "jobseeker_core");

    const { extracted } = await parseResumeText(token, SAMPLE_RESUME);
    expect(extracted).toBeTruthy();

    const name = String(extracted.name ?? extracted.full_name ?? "").trim();
    const email = String(extracted.email ?? "").trim();
    const phone = String(extracted.phone ?? extracted.mobile ?? "").trim();
    const summary = String(extracted.summary ?? "").trim();
    const skills = extracted.skills;
    const experience = extracted.experiences ?? extracted.experience ?? extracted.work_experience;
    const education = extracted.education ?? extracted.educations;

    const coreHits = [
      name.length > 0,
      email.length > 0,
      Array.isArray(skills) ? skills.length > 0 : String(skills ?? "").trim().length > 0,
      Array.isArray(experience) ? experience.length > 0 : Boolean(experience),
      Array.isArray(education) ? education.length > 0 : Boolean(education),
      summary.length > 0,
    ].filter(Boolean).length;

    // At least 4 of 6 core fields populated (LLM variance)
    expect(coreHits).toBeGreaterThanOrEqual(4);

    if (email) {
      expect(email).toMatch(/^[^\s@]+@[^\s@]+\.[^\s@]+$/);
    }

    if (Array.isArray(skills)) {
      expect(skills.length).toBeGreaterThan(0);
    }

    // phone is optional but should look sane when present
    if (phone) {
      expect(phone.replace(/\D/g, "").length).toBeGreaterThanOrEqual(7);
    }
  });
});
