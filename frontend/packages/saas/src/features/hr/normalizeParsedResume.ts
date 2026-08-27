/**
 * Normalize LLM resume extraction into ParsedResume shape used by UI + match bridge.
 * Backend prompt historically returns experience/role/duration; frontend expects experiences/title/dates.
 */
import type { ParsedResume, ResumeEducation, ResumeExperience } from "@looma/shared-core";

type Loose = Record<string, unknown>;

function asString(v: unknown): string {
  return typeof v === "string" ? v.trim() : v == null ? "" : String(v).trim();
}

function asStringList(v: unknown): string[] {
  if (!Array.isArray(v)) {
    if (typeof v === "string" && v.trim()) {
      return v.split(/[,，、;；]/).map((s) => s.trim()).filter(Boolean);
    }
    return [];
  }
  return v.map(asString).filter(Boolean);
}

function normalizeExperience(item: unknown): ResumeExperience | null {
  if (!item || typeof item !== "object") return null;
  const e = item as Loose;
  const company = asString(e.company);
  const title = asString(e.title) || asString(e.role) || asString(e.position);
  const description = asString(e.description);
  const start_date = asString(e.start_date) || asString(e.start);
  const end_date = asString(e.end_date) || asString(e.end);
  const duration = asString(e.duration);

  if (!company && !title && !description) return null;

  return {
    company,
    title,
    start_date: start_date || (duration ? duration : undefined),
    end_date: end_date || undefined,
    description: description || undefined,
  };
}

function normalizeEducation(item: unknown): ResumeEducation | null {
  if (!item || typeof item !== "object") return null;
  const e = item as Loose;
  const school = asString(e.school);
  const degree = asString(e.degree);
  const field = asString(e.field) || asString(e.major);
  const year = asString(e.year);
  if (!school && !degree && !field) return null;
  return {
    school,
    degree,
    field: field || undefined,
    end_date: asString(e.end_date) || year || undefined,
    start_date: asString(e.start_date) || undefined,
  };
}

export function normalizeParsedResume(raw: unknown): ParsedResume | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Loose;

  const expRaw = r.experiences ?? r.experience;
  const experiences = Array.isArray(expRaw)
    ? (expRaw.map(normalizeExperience).filter(Boolean) as ResumeExperience[])
    : undefined;

  const eduRaw = r.education;
  const education = Array.isArray(eduRaw)
    ? (eduRaw.map(normalizeEducation).filter(Boolean) as ResumeEducation[])
    : undefined;

  return {
    name: asString(r.name) || undefined,
    email: asString(r.email) || undefined,
    phone: asString(r.phone) || undefined,
    summary: asString(r.summary) || undefined,
    skills: asStringList(r.skills),
    experiences,
    education,
    projects: Array.isArray(r.projects) ? (r.projects as ParsedResume["projects"]) : undefined,
    languages: asStringList(r.languages),
    certifications: asStringList(r.certifications),
    raw: r,
  };
}
