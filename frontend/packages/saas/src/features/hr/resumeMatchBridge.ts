/**
 * Bridge Resume parsing → Jobs matching without merging the two product stages.
 * Stores a plain-text snapshot the user can review before matching.
 */
import type { ParsedResume } from "@looma/shared-core";
import { normalizeParsedResume } from "./normalizeParsedResume";

export const RESUME_MATCH_TEXT_KEY = "saas-resume-match-text";
export const RESUME_MATCH_ID_KEY = "saas-resume-match-id";

export function buildResumeMatchText(resume: ParsedResume): string {
  const r = normalizeParsedResume(resume) ?? resume;
  const parts: string[] = [];

  if (r.name) parts.push(`姓名：${r.name}`);
  if (r.email) parts.push(`邮箱：${r.email}`);
  if (r.phone) parts.push(`电话：${r.phone}`);
  if (r.summary) parts.push(`\n摘要：\n${r.summary}`);

  if (r.skills?.length) {
    parts.push(`\n技能：\n${r.skills.join("、")}`);
  }

  if (r.experiences?.length) {
    parts.push("\n工作经历：");
    for (const exp of r.experiences) {
      const period = [exp.start_date || "", exp.end_date || "至今"].filter(Boolean).join(" ~ ");
      parts.push(`- ${exp.title || ""} @ ${exp.company || ""} (${period})`);
      if (exp.description) parts.push(`  ${exp.description}`);
    }
  }

  if (r.education?.length) {
    parts.push("\n教育背景：");
    for (const edu of r.education) {
      parts.push(
        `- ${edu.school || ""} ${edu.degree || ""} ${edu.field || ""}`.trim(),
      );
    }
  }

  if (r.projects?.length) {
    parts.push("\n项目：");
    for (const p of r.projects) {
      parts.push(`- ${p.name || ""}${p.description ? `：${p.description}` : ""}`);
    }
  }

  if (r.languages?.length) {
    parts.push(`\n语言：${r.languages.join("、")}`);
  }

  if (r.certifications?.length) {
    parts.push(`\n证书：${r.certifications.join("、")}`);
  }

  return parts.join("\n").trim();
}

export function saveResumeMatchText(text: string, resumeId?: string | null): void {
  try {
    localStorage.setItem(RESUME_MATCH_TEXT_KEY, text);
    if (resumeId) {
      localStorage.setItem(RESUME_MATCH_ID_KEY, resumeId);
    }
  } catch {
    /* ignore quota / private mode */
  }
}

export function loadResumeMatchText(): string | null {
  try {
    return localStorage.getItem(RESUME_MATCH_TEXT_KEY);
  } catch {
    return null;
  }
}

export function loadResumeMatchId(): string | null {
  try {
    return localStorage.getItem(RESUME_MATCH_ID_KEY);
  } catch {
    return null;
  }
}

export function clearResumeMatchText(): void {
  try {
    localStorage.removeItem(RESUME_MATCH_TEXT_KEY);
    localStorage.removeItem(RESUME_MATCH_ID_KEY);
  } catch {
    /* ignore */
  }
}
