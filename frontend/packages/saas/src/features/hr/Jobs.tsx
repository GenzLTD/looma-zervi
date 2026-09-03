/**
 * Jobs - Position matching & JD upload page.
 * Owner: szbenyx
 *
 * Features:
 *   - Browse persisted + mock jobs
 *   - Upload JD file (PDF/DOCX) for AI parsing
 *   - Paste JD text for quick parse
 *   - Resume × Job multi-dimension matching (11 dimensions from Tatha)
 *
 * Pure CSS + Tailwind (no tdesign-react).
 * Uses shared-core typed API factories for backend contract alignment.
 */
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import {
  ApiError,
  createJobsApi,
  createCreditApi,
  createMatchReportsApi,
  isPaidTier,
  type Job,
  type JobMatchItem,
  type CreditAnalysis,
  type CreditExtended,
  type GapItem,
} from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";
import { useConsent } from "../../compliance/useConsent";
import { IS_OVERSEAS } from "../../config/region";
import QuotaExhaustedModal from "../../brand/components/QuotaExhaustedModal";
import { loadResumeMatchId, loadResumeMatchText } from "./resumeMatchBridge";
import { useSaasAuthStore } from "../auth/authStore";

function isQuotaExceeded(err: unknown): boolean {
  return (
    err instanceof ApiError &&
    err.status === 429 &&
    err.body?.error === "quota_exceeded"
  );
}

/** Align with backend 9 sub-dimensions + overall (product docs call this 11-dim). */
const SCORE_DIMS: { key: string; max: number }[] = [
  { key: "background_match", max: 10 },
  { key: "skills_overlap", max: 30 },
  { key: "experience_relevance", max: 30 },
  { key: "seniority", max: 10 },
  { key: "language_requirement", max: 10 },
  { key: "company_score", max: 10 },
  { key: "salary_match", max: 10 },
  { key: "location_match", max: 10 },
  { key: "culture_workload_match", max: 10 },
];

function priorityColor(priority: GapItem["priority"]): string {
  if (priority === "high") return "var(--color-danger)";
  if (priority === "low") return "var(--color-text-muted)";
  return "var(--color-warning)";
}

// ── Types ──

interface ParsedJobData {
  title: string;
  company: string;
  location?: string;
  salary_range?: string;
  description?: string;
  requirements?: string[];
  responsibilities?: string[];
  tags?: string[];
}

type TabId = "browse" | "upload";

// ── Helpers ──

function getScoreColor(score: number): string {
  if (score >= 80) return "var(--color-success)";
  if (score >= 60) return "var(--color-warning)";
  return "var(--color-danger)";
}

// ── Component ──

export default function Jobs() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, quota } = useSaasAuthStore();
  const [tab, setTab] = useState<TabId>(IS_OVERSEAS ? "upload" : "browse");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [matches, setMatches] = useState<JobMatchItem[] | null>(null);
  const [resumeText, setResumeText] = useState("");
  const [resumePrefill, setResumePrefill] = useState(false);
  const [matching, setMatching] = useState(false);
  const [savingReport, setSavingReport] = useState(false);
  const [batchCreditBusy, setBatchCreditBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [msgOk, setMsgOk] = useState(false);
  const [msgHint, setMsgHint] = useState<string | null>(null); // "resume_not_jd" etc.
  const [quotaExhausted, setQuotaExhausted] = useState(false);

  const matchRecord = quota?.records?.find((r) => r.resource === "job_match");
  const matchUsagePct =
    matchRecord && matchRecord.daily_limit > 0
      ? Math.round((matchRecord.used / matchRecord.daily_limit) * 100)
      : 0;
  const showQuotaWarn = !isPaidTier(user?.tier ?? quota?.tier) && matchUsagePct >= 80;

  // Credit check state (Tripod leg 3)
  const [creditResults, setCreditResults] = useState<Record<string, CreditAnalysis | null>>({});
  const [creditExtended, setCreditExtended] = useState<Record<string, CreditExtended | null>>({});
  const [creditSources, setCreditSources] = useState<Record<string, string>>({});
  const [creditLoading, setCreditLoading] = useState<Record<string, boolean>>({});

  // Upload state
  const [uploading, setUploading] = useState(false);
  const [parsedJob, setParsedJob] = useState<ParsedJobData | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jdText, setJdText] = useState("");
  const [parsing, setParsing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const api = useMemo(() => createSaasApiClient(), []);
  const jobsApi = createJobsApi(api);
  const creditApi = createCreditApi(api);
  const matchReportsApi = useMemo(() => createMatchReportsApi(api), [api]);
  const { ensureConsent, consentPrompt } = useConsent(() => api);

  // Load job list
  const loadJobs = useCallback(() => {
    jobsApi
      .list()
      .then((res) => setJobs(res.jobs))
      .catch(() => setMsg(t("jobs.loadFailed")));
  }, [jobsApi, t]);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  // Prefill resume text brought from /resume (stage-1 → stage-3 bridge)
  useEffect(() => {
    const saved = loadResumeMatchText();
    if (saved?.trim()) {
      setResumeText(saved);
      setResumePrefill(true);
      setTab("browse");
    }
  }, []);

  // ── Job Upload ──

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    setMsg(null);
    setMsgHint(null);
    try {
      const result = await jobsApi.upload(file) as any;
      if (result.parsed) {
        setParsedJob(result.parsed);
        if (result.job_id) setActiveJobId(result.job_id);
        setMsg(t("jobs.uploadDone"));
        loadJobs(); // Refresh job list
        // Auto-fill JD text for preview
        setJdText(result.markdown || "");
      } else if (result.error) {
        setMsg(result.error);
        if (result.hint === "resume_not_jd") {
          setMsgHint("resume_not_jd");
        }
      } else {
        setMsg(t("jobs.uploadPartial"));
      }
    } catch (err) {
      if (isQuotaExceeded(err)) {
        setQuotaExhausted(true);
        setMsg(null);
      } else {
        setMsg(t("jobs.uploadFailed"));
      }
    } finally {
      setUploading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileUpload(file);
    // Reset so same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFileUpload(file);
  };

  const handleParseText = async () => {
    if (!jdText.trim()) return;
    setParsing(true);
    setMsg(null);
    try {
      const result = await jobsApi.parse(jdText) as any;
      if (result.parsed) {
        setParsedJob(result.parsed);
        if (result.job_id) setActiveJobId(result.job_id);
        setMsg(t("jobs.parseTextDone"));
        loadJobs();
      } else {
        setMsg(t("jobs.parseTextEmpty"));
      }
    } catch (err) {
      if (isQuotaExceeded(err)) {
        setQuotaExhausted(true);
        setMsg(null);
      } else {
        setMsg(t("jobs.parseTextFailed"));
      }
    } finally {
      setParsing(false);
    }
  };

  // ── Job Match ──

  const buildAdhocJobDescription = (): string => {
    if (jdText.trim()) return jdText.trim();
    if (!parsedJob) return "";
    const parts: string[] = [];
    if (parsedJob.title) parts.push(`职位：${parsedJob.title}`);
    if (parsedJob.company) parts.push(`公司：${parsedJob.company}`);
    if (parsedJob.location) parts.push(`地点：${parsedJob.location}`);
    if (parsedJob.salary_range) parts.push(`薪资：${parsedJob.salary_range}`);
    if (parsedJob.description) parts.push(parsedJob.description);
    if (parsedJob.requirements?.length) {
      parts.push(`要求：\n${parsedJob.requirements.map((r) => `- ${r}`).join("\n")}`);
    }
    if (parsedJob.responsibilities?.length) {
      parts.push(`职责：\n${parsedJob.responsibilities.map((r) => `- ${r}`).join("\n")}`);
    }
    return parts.join("\n").trim();
  };

  const handleMatch = async (jobId?: string) => {
    if (!resumeText.trim()) {
      setMsg(t("jobs.emptyResume"));
      return;
    }
    const allowed = await ensureConsent("jobseeker_core");
    if (!allowed) {
      setMsg(t("jobs.consentRequired"));
      return;
    }
    setMatching(true);
    setMsg(null);
    setMsgOk(false);
    try {
      const payload: {
        resume_text: string;
        job_id?: string;
        job_description?: string;
        job_title?: string;
        job_company?: string;
        job_location?: string;
        job_salary_range?: string;
      } = { resume_text: resumeText };

      const targetJobId = jobId || activeJobId || undefined;
      if (targetJobId) {
        payload.job_id = targetJobId;
      } else {
        const adhoc = buildAdhocJobDescription();
        if (adhoc) {
          payload.job_description = adhoc;
          if (parsedJob?.title) payload.job_title = parsedJob.title;
          if (parsedJob?.company) payload.job_company = parsedJob.company;
          if (parsedJob?.location) payload.job_location = parsedJob.location;
          if (parsedJob?.salary_range) payload.job_salary_range = parsedJob.salary_range;
        }
      }

      const res = await jobsApi.match(payload) as any;
      setMatches(res.matches ?? []);
      if (!res.matches?.length) {
        setMsg(t("jobs.matchEmpty"));
      }
    } catch (err) {
      if (isQuotaExceeded(err)) {
        setQuotaExhausted(true);
        setMsg(null);
      } else if (err instanceof ApiError && err.body?.message) {
        setMsg(String(err.body.message));
      } else {
        setMsg(t("jobs.matchFailed"));
      }
    } finally {
      setMatching(false);
    }
  };

  const handleSaveReport = async () => {
    if (!matches?.length) return;
    const allowed = await ensureConsent("jobseeker_core");
    if (!allowed) {
      setMsgOk(false);
      setMsg(t("jobs.reportConsentRequired"));
      return;
    }
    setSavingReport(true);
    setMsg(null);
    try {
      // Attach in-session credit results so report items persist credit_snapshot
      const matchesWithCredit = matches.map((m) => {
        const company = m.company || "";
        const credit = company ? creditResults[company] : null;
        const extended = company ? creditExtended[company] : null;
        if (!credit && !extended) return m;
        return {
          ...m,
          credit_snapshot: {
            extracted: credit ?? null,
            extended: extended ?? null,
            checked_at: new Date().toISOString(),
            source: creditSources[company] || "session",
          },
        };
      });
      const report = await matchReportsApi.create({
        resume_text: resumeText,
        matches: matchesWithCredit,
        resume_id: loadResumeMatchId() || undefined,
      });
      setMsgOk(true);
      setMsg(t("jobs.reportSaved"));
      navigate(`/reports?match=${report.id}`);
    } catch (err) {
      setMsgOk(false);
      if (err instanceof ApiError && err.status === 403) {
        setMsg(t("jobs.reportConsentRequired"));
      } else if (err instanceof ApiError && err.body?.message) {
        setMsg(String(err.body.message));
      } else {
        setMsg(t("jobs.reportSaveFailed"));
      }
    } finally {
      setSavingReport(false);
    }
  };

  // ── Company Credit Check (Tripod leg 3) ──

  const handleCheckCredit = async (companyName: string) => {
    if (!companyName) return;
    const allowed = await ensureConsent("credit_query");
    if (!allowed) {
      setMsg(t("jobs.creditConsentRequired"));
      return;
    }
    setCreditLoading((prev) => ({ ...prev, [companyName]: true }));
    try {
      const result = await creditApi.checkCompany({ company_name: companyName }) as any;
      setCreditResults((prev) => ({ ...prev, [companyName]: result.extracted }));
      if (result.extended) {
        setCreditExtended((prev) => ({ ...prev, [companyName]: result.extended }));
      }
      if (result.source) {
        setCreditSources((prev) => ({ ...prev, [companyName]: String(result.source) }));
      }
    } catch {
      setCreditResults((prev) => ({
        ...prev,
        [companyName]: {
          entity_name: companyName,
          report_type: "企业信用评估",
          summary: t("jobs.creditUnavailable"),
        },
      }));
    } finally {
      setCreditLoading((prev) => ({ ...prev, [companyName]: false }));
    }
  };

  const handleBatchCredit = async () => {
    if (!matches?.length || IS_OVERSEAS) return;
    const companies = Array.from(
      new Set(matches.map((m) => m.company).filter(Boolean) as string[]),
    ).filter((c) => !creditResults[c]);
    if (companies.length === 0) {
      setMsgOk(true);
      setMsg(t("jobs.batchCreditDone"));
      return;
    }
    const allowed = await ensureConsent("credit_query");
    if (!allowed) {
      setMsgOk(false);
      setMsg(t("jobs.creditConsentRequired"));
      return;
    }
    setBatchCreditBusy(true);
    setMsg(null);
    try {
      for (const company of companies) {
        await handleCheckCredit(company);
        await new Promise((r) => setTimeout(r, 300));
      }
      setMsgOk(true);
      setMsg(t("jobs.batchCreditDone"));
    } finally {
      setBatchCreditBusy(false);
    }
  };

  // ── Render Helpers ──

  const renderScoreBar = (label: string, value: number, max: number) => (
    <div key={label} className="flex items-center gap-2 text-xs">
      <span
        className="w-10 shrink-0 text-right"
        style={{ color: "var(--color-text-muted)" }}
      >
        {label}
      </span>
      <div
        className="flex-1 h-1.5 rounded-full"
        style={{ backgroundColor: "var(--color-bg-surface)" }}
      >
        <div
          className="h-1.5 rounded-full transition-all"
          style={{
            width: `${(value / max) * 100}%`,
            backgroundColor: getScoreColor((value / max) * 100),
          }}
        />
      </div>
      <span
        className="w-6 text-left font-mono"
        style={{ color: "var(--color-text-secondary)" }}
      >
        {value}
      </span>
    </div>
  );

  // ── Render ──

  return (
    <>
    {consentPrompt}
    <QuotaExhaustedModal
      isOpen={quotaExhausted}
      onClose={() => setQuotaExhausted(false)}
    />
    <div className="max-w-5xl mx-auto">
      <h1
        className="text-2xl font-bold mb-6"
        style={{ color: "var(--color-text-primary)" }}
      >
        {t("jobs.title")}
      </h1>

      {/* ── Tab Bar ── */}
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: "#e0e0e0" }}>
        {(["browse", "upload"] as TabId[]).map((id) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className="px-4 py-2 text-sm font-medium border-b-2 bg-transparent cursor-pointer transition-colors"
            style={{
              color: tab === id ? "var(--color-primary)" : "var(--color-text-muted)",
              borderColor: tab === id ? "var(--color-primary)" : "transparent",
              marginBottom: -1,
            }}
          >
            {id === "browse" ? t("jobs.tabBrowse") : t("jobs.tabUpload")}
          </button>
        ))}
      </div>

      {/* ── Browse Tab: Job List + Match ── */}
      {tab === "browse" && (
        <>
          {/* Resume input + match bar */}
          <div
            className="rounded-lg p-4 mb-6"
            style={{
              backgroundColor: "var(--color-bg-card)",
              boxShadow: "var(--shadow-sm)",
            }}
          >
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                {resumePrefill ? (
                  <p className="text-xs" style={{ color: "var(--color-primary)" }}>
                    {t("jobs.resumePrefillHint")}
                  </p>
                ) : (
                  <span />
                )}
                <Link
                  to="/resume"
                  className="text-xs no-underline"
                  style={{ color: "var(--color-primary)" }}
                >
                  {t("jobs.goParseResume")}
                </Link>
              </div>
              {showQuotaWarn && (
                <p className="text-xs" style={{ color: "var(--color-warning)" }}>
                  {t("jobs.quotaNearLimit", { pct: matchUsagePct })}
                </p>
              )}
              <textarea
                value={resumeText}
                onChange={(e) => {
                  setResumeText(e.target.value);
                  if (resumePrefill) setResumePrefill(false);
                }}
                placeholder={t("jobs.resumePlaceholder")}
                rows={5}
                className="border rounded-lg px-3 py-2 text-sm outline-none resize-y w-full"
                style={{
                  borderColor: "#e0e0e0",
                  color: "var(--color-text-primary)",
                  backgroundColor: "var(--color-bg-surface)",
                }}
              />
              <div className="flex items-center justify-between">
                <button
                  onClick={() => handleMatch()}
                  disabled={!resumeText.trim() || matching}
                  className="px-4 py-2 text-sm rounded-lg text-white border-none cursor-pointer disabled:opacity-50 transition-colors"
                  style={{ backgroundColor: "var(--color-primary)" }}
                >
                  {matching ? t("jobs.matching") : t("jobs.matchStart")}
                </button>
                <button
                  onClick={() => {
                    setMatches(null);
                    setResumeText("");
                    setResumePrefill(false);
                  }}
                  className="text-sm bg-transparent border-none cursor-pointer"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  {t("jobs.reset")}
                </button>
              </div>
            </div>
          </div>

          {msg && (
            <p
              className="text-sm mb-4 text-center"
              style={{ color: msgOk ? "var(--color-success)" : "var(--color-danger)" }}
            >
              {msg}
            </p>
          )}

          {/* Match Results */}
          {matches ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  {t("jobs.matchCount", { count: matches.length })}
                </p>
                <div className="flex gap-2 flex-wrap">
                  {!IS_OVERSEAS && (
                    <button
                      type="button"
                      onClick={() => void handleBatchCredit()}
                      disabled={batchCreditBusy}
                      className="px-3 py-2 text-sm rounded-lg border cursor-pointer disabled:opacity-50"
                      style={{
                        borderColor: "#e0e0e0",
                        backgroundColor: "var(--color-bg-surface)",
                        color: "var(--color-text-secondary)",
                      }}
                    >
                      {batchCreditBusy ? t("jobs.batchCreditBusy") : t("jobs.batchCredit")}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void handleSaveReport()}
                    disabled={savingReport || matches.length === 0}
                    className="px-4 py-2 text-sm rounded-lg text-white border-none cursor-pointer disabled:opacity-50"
                    style={{ backgroundColor: "var(--color-primary)" }}
                  >
                    {savingReport ? t("jobs.reportSaving") : t("jobs.saveAsReport")}
                  </button>
                </div>
              </div>
              {matches.map((m, i) => (
                <div
                  key={i}
                  className="rounded-lg p-5 transition-shadow hover:shadow-md"
                  style={{
                    backgroundColor: "var(--color-bg-card)",
                    boxShadow: "var(--shadow-sm)",
                  }}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3
                        className="font-bold text-lg"
                        style={{ color: "var(--color-text-primary)" }}
                      >
                        {m.title}
                      </h3>
                      <p
                        className="text-sm mb-2"
                        style={{ color: "var(--color-text-secondary)" }}
                      >
                        {m.company}
                        {m.location && ` · ${m.location}`}
                        {m.salary_range && ` · ${m.salary_range}`}
                      </p>

                      {/* Multi-dimension scores (9 sub-dims) */}
                      <div className="space-y-1.5 mb-3">
                        {SCORE_DIMS.map(({ key, max }) => {
                          const scores = m.scores as unknown as Record<string, number>;
                          const val = Number(scores?.[key] ?? 5);
                          return renderScoreBar(t(`jobs.scores.${key}`), val, max);
                        })}
                      </div>

                      {/* Summary + keywords */}
                      {m.reason && (
                        <p
                          className="text-sm mb-2 px-3 py-2 rounded"
                          style={{
                            color: "var(--color-text-secondary)",
                            backgroundColor: "var(--color-bg-surface)",
                          }}
                        >
                          💡 {m.reason}
                        </p>
                      )}

                      {/* Matched skills */}
                      {m.matched_skills && m.matched_skills.length > 0 && (
                        <div className="mb-2">
                          <p className="text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>
                            {t("jobs.matchedSkills")}
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {m.matched_skills.slice(0, 8).map((s, j) => (
                              <span
                                key={j}
                                className="text-xs px-2 py-0.5 rounded"
                                style={{
                                  backgroundColor: "var(--color-primary-bg, #e8f4fd)",
                                  color: "var(--color-primary)",
                                }}
                              >
                                {s}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Fit bullets */}
                      {m.fit_bullets && m.fit_bullets.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mb-2">
                          {m.fit_bullets.slice(0, 5).map((b, j) => (
                            <span
                              key={j}
                              className="text-xs px-2 py-0.5 rounded-full"
                              style={{
                                backgroundColor: "var(--color-primary-bg, #e8f4fd)",
                                color: "var(--color-primary)",
                              }}
                            >
                              ✓ {b}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Gap analysis */}
                      {((m.gap_analysis && m.gap_analysis.length > 0) ||
                        (m.missing_skills && m.missing_skills.length > 0)) && (
                        <div
                          className="mt-2 mb-2 p-3 rounded"
                          style={{ backgroundColor: "var(--color-bg-surface)" }}
                        >
                          <p
                            className="text-xs font-medium mb-2"
                            style={{ color: "var(--color-text-secondary)" }}
                          >
                            ⚠️ {t("jobs.gapTitle")}
                          </p>
                          {m.gap_analysis && m.gap_analysis.length > 0 ? (
                            <ul className="space-y-2">
                              {m.gap_analysis.slice(0, 5).map((g, j) => (
                                <li key={j} className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                                  <div className="flex items-center gap-2 mb-0.5">
                                    <span className="font-medium" style={{ color: "var(--color-text-primary)" }}>
                                      {g.skill}
                                    </span>
                                    <span
                                      className="px-1.5 py-0.5 rounded"
                                      style={{
                                        color: "#fff",
                                        backgroundColor: priorityColor(g.priority),
                                        fontSize: 10,
                                      }}
                                    >
                                      {t(`jobs.gapPriority.${g.priority}`)}
                                    </span>
                                    {g.estimated_effort && (
                                      <span style={{ color: "var(--color-text-muted)" }}>
                                        {g.estimated_effort}
                                      </span>
                                    )}
                                  </div>
                                  {g.gap && <p className="mb-0.5">{g.gap}</p>}
                                  {g.suggestion && (
                                    <p style={{ color: "var(--color-primary)" }}>💡 {g.suggestion}</p>
                                  )}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <div className="flex flex-wrap gap-1.5">
                              {m.missing_skills!.map((s, j) => (
                                <span
                                  key={j}
                                  className="text-xs px-2 py-0.5 rounded"
                                  style={{
                                    backgroundColor: "#fff3e0",
                                    color: "var(--color-warning)",
                                  }}
                                >
                                  {s}
                                </span>
                              ))}
                            </div>
                          )}
                          {m.improvement_plan && (
                            <div className="mt-2 pt-2 border-t" style={{ borderColor: "var(--color-border, #e0e0e0)" }}>
                              <p className="text-xs font-medium mb-1" style={{ color: "var(--color-text-secondary)" }}>
                                {t("jobs.improvementTitle")}
                              </p>
                              <p
                                className="text-xs whitespace-pre-wrap leading-relaxed"
                                style={{ color: "var(--color-text-secondary)" }}
                              >
                                {m.improvement_plan}
                              </p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Overall score ring */}
                    <div className="ml-6 text-center shrink-0">
                      <svg width="80" height="80" viewBox="0 0 80 80">
                        <circle cx="40" cy="40" r="34" fill="none" stroke="#e0e0e0" strokeWidth="6" />
                        <circle
                          cx="40"
                          cy="40"
                          r="34"
                          fill="none"
                          stroke={getScoreColor(m.scores.overall)}
                          strokeWidth="6"
                          strokeDasharray={`${(m.scores.overall / 100) * 213.6} 213.6`}
                          strokeLinecap="round"
                          transform="rotate(-90 40 40)"
                        />
                        <text
                          x="40"
                          y="40"
                          textAnchor="middle"
                          dy="0.35em"
                          fontSize="16"
                          fontWeight="bold"
                          fill="var(--color-text-primary)"
                        >
                          {Math.round(m.scores.overall)}
                        </text>
                      </svg>
                      <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                        {t("jobs.overallMatch")}
                      </p>

                      {/* Credit check (mainland only) */}
                      {!IS_OVERSEAS && m.company && (
                        <button
                          onClick={() => handleCheckCredit(m.company!)}
                          disabled={creditLoading[m.company]}
                          className="mt-2 px-2 py-1 text-xs rounded border-none cursor-pointer disabled:opacity-50 transition-colors"
                          style={{
                            backgroundColor: creditResults[m.company]
                              ? "var(--color-success)"
                              : "var(--color-bg-surface)",
                            color: creditResults[m.company]
                              ? "#fff"
                              : "var(--color-text-secondary)",
                          }}
                        >
                          {creditLoading[m.company]
                            ? t("jobs.checkingCredit")
                            : creditResults[m.company]
                            ? t("jobs.creditDone")
                            : t("jobs.checkCredit")}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Credit result card (mainland only) */}
                  {!IS_OVERSEAS && m.company && creditResults[m.company] && (
                    <div
                      className="mt-3 rounded border-l-4 overflow-hidden"
                      style={{
                        backgroundColor: "var(--color-bg-surface)",
                        borderColor: creditExtended[m.company]?.risk?.level === "高风险"
                          ? "var(--color-danger)"
                          : creditExtended[m.company]?.risk?.level === "中风险"
                          ? "var(--color-warning)"
                          : "var(--color-success)",
                      }}
                    >
                      {/* Header */}
                      <div className="flex items-center justify-between p-3 pb-2">
                        <div className="flex items-center gap-2">
                          <span
                            className="text-xs font-bold"
                            style={{ color: "var(--color-text-primary)" }}
                          >
                            🛡 {t("jobs.creditReport")}
                          </span>
                          {creditResults[m.company]?.report_type && (
                            <span
                              className="text-xs px-1.5 py-0.5 rounded"
                              style={{
                                backgroundColor: "var(--color-success)",
                                color: "#fff",
                              }}
                            >
                              {creditResults[m.company]?.report_type}
                            </span>
                          )}
                          {creditExtended[m.company] && (
                            <span
                              className="text-xs px-1.5 py-0.5 rounded"
                              style={{
                                backgroundColor: "#f0f9ff",
                                color: "var(--color-primary)",
                                border: "1px solid var(--color-primary)",
                              }}
                            >
                              QCC 官方数据
                            </span>
                          )}
                        </div>
                        {creditExtended[m.company]?.risk?.level && (
                          <span
                            className="text-xs font-bold px-2 py-0.5 rounded"
                            style={{
                              backgroundColor:
                                creditExtended[m.company]!.risk.level === "高风险"
                                  ? "var(--color-danger)"
                                  : creditExtended[m.company]!.risk.level === "中风险"
                                  ? "var(--color-warning)"
                                  : "var(--color-success)",
                              color: "#fff",
                            }}
                          >
                            {creditExtended[m.company]!.risk.level}
                          </span>
                        )}
                      </div>

                      {/* QCC Extended data — multi-dimension grid */}
                      {creditExtended[m.company] ? (
                        <div className="px-3 pb-3 space-y-2">
                          {/* Company info row */}
                          {creditExtended[m.company]!.company && (
                            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                              {creditExtended[m.company]!.company.legal_person && (
                                <div>
                                  <span style={{ color: "var(--color-text-muted)" }}>{t("jobs.creditLegalPerson")}: </span>
                                  <span style={{ color: "var(--color-text-primary)" }}>
                                    {creditExtended[m.company]!.company.legal_person}
                                  </span>
                                </div>
                              )}
                              {creditExtended[m.company]!.company.registered_capital && (
                                <div>
                                  <span style={{ color: "var(--color-text-muted)" }}>{t("jobs.creditRegCapital")}: </span>
                                  <span style={{ color: "var(--color-text-primary)" }}>
                                    {creditExtended[m.company]!.company.registered_capital}
                                  </span>
                                </div>
                              )}
                              {creditExtended[m.company]!.company.established_date && (
                                <div>
                                  <span style={{ color: "var(--color-text-muted)" }}>{t("jobs.creditEstDate")}: </span>
                                  <span style={{ color: "var(--color-text-primary)" }}>
                                    {creditExtended[m.company]!.company.established_date}
                                  </span>
                                </div>
                              )}
                              {creditExtended[m.company]!.company.status && (
                                <div>
                                  <span style={{ color: "var(--color-text-muted)" }}>{t("jobs.creditStatus")}: </span>
                                  <span
                                    style={{
                                      color: ["存续", "在业"].includes(creditExtended[m.company]!.company.status)
                                        ? "var(--color-success)"
                                        : "var(--color-danger)",
                                      fontWeight: 500,
                                    }}
                                  >
                                    {creditExtended[m.company]!.company.status}
                                  </span>
                                </div>
                              )}
                              {creditExtended[m.company]!.company.industry && (
                                <div className="col-span-2">
                                  <span style={{ color: "var(--color-text-muted)" }}>{t("jobs.creditIndustry")}: </span>
                                  <span style={{ color: "var(--color-text-primary)" }}>
                                    {creditExtended[m.company]!.company.industry}
                                  </span>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Risk summary */}
                          {creditExtended[m.company]!.risk && creditExtended[m.company]!.risk.summary && (
                            <div
                              className="text-xs p-2 rounded"
                              style={{
                                backgroundColor: "var(--color-bg-card)",
                                color: "var(--color-text-secondary)",
                              }}
                            >
                              <span style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>
                                {t("jobs.creditRiskSummary")}:
                              </span>{" "}
                              {creditExtended[m.company]!.risk.summary}
                            </div>
                          )}

                          {/* Executives */}
                          {creditExtended[m.company]!.executives && creditExtended[m.company]!.executives.length > 0 && (
                            <div className="text-xs">
                              <span style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>
                                {t("jobs.creditExecutives")}:
                              </span>{" "}
                              <span style={{ color: "var(--color-text-secondary)" }}>
                                {creditExtended[m.company]!.executives
                                  .slice(0, 5)
                                  .map((e: Record<string, string>) => e.name || e["姓名"] || "")
                                  .filter(Boolean)
                                  .join("、")}
                              </span>
                            </div>
                          )}

                          {/* Full summary text */}
                          <p
                            className="text-xs mt-1"
                            style={{
                              color: "var(--color-text-secondary)",
                              lineHeight: 1.6,
                              whiteSpace: "pre-line",
                            }}
                          >
                            {creditResults[m.company]?.summary || t("jobs.creditNoData")}
                          </p>
                        </div>
                      ) : (
                        /* Legacy / LLM fallback card (no extended data) */
                        <div className="px-3 pb-3">
                          <p
                            className="text-xs"
                            style={{ color: "var(--color-text-secondary)" }}
                          >
                            <strong>{t("jobs.creditEntity")}:</strong>{" "}
                            {creditResults[m.company]?.entity_name || m.company}
                          </p>
                          <p
                            className="text-xs mt-1"
                            style={{ color: "var(--color-text-secondary)" }}
                          >
                            {creditResults[m.company]?.summary || t("jobs.creditNoData")}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            /* Job List */
            <div className="space-y-3">
              <h3
                className="text-sm font-medium mb-3"
                style={{ color: "var(--color-text-muted)" }}
              >
                {t("jobs.currentRoles", { count: jobs.length })}
              </h3>
              {jobs.length === 0 ? (
                <div
                  className="rounded-lg p-8 text-center"
                  style={{
                    backgroundColor: "var(--color-bg-card)",
                    boxShadow: "var(--shadow-sm)",
                  }}
                >
                  <p
                    className="font-medium mb-2"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {t("jobs.emptyTitle")}
                  </p>
                  <p
                    className="text-sm mb-4"
                    style={{ color: "var(--color-text-muted)" }}
                  >
                    {t("jobs.emptyDesc")}
                  </p>
                  <button
                    type="button"
                    onClick={() => setTab("upload")}
                    className="px-4 py-2 text-sm rounded-lg text-white border-none cursor-pointer"
                    style={{ backgroundColor: "var(--color-primary)" }}
                  >
                    {t("jobs.uploadFirst")}
                  </button>
                </div>
              ) : (
              jobs.map((job) => (
                <div
                  key={job.id}
                  className="rounded-lg p-4 transition-shadow hover:shadow-sm"
                  style={{
                    backgroundColor: "var(--color-bg-card)",
                    boxShadow: "var(--shadow-sm)",
                  }}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h4
                        className="font-medium"
                        style={{ color: "var(--color-text-primary)" }}
                      >
                        {job.title}
                      </h4>
                      <p
                        className="text-sm"
                        style={{ color: "var(--color-text-secondary)" }}
                      >
                        {job.company}
                        {job.location && ` · ${job.location}`}
                        {job.salary_range && ` · ${job.salary_range}`}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex flex-wrap gap-1 max-w-sm">
                        {(job.requirements ?? []).slice(0, 5).map((req, j) => (
                          <span
                            key={j}
                            className="text-xs px-2 py-0.5 rounded"
                            style={{
                              backgroundColor: "var(--color-bg-surface)",
                              color: "var(--color-text-secondary)",
                            }}
                          >
                            {req}
                          </span>
                        ))}
                      </div>
                      <button
                        onClick={() => handleMatch(job.id)}
                        disabled={!resumeText.trim() || matching}
                        className="ml-3 px-3 py-1 text-xs rounded border-none cursor-pointer disabled:opacity-40 transition-colors shrink-0"
                        style={{
                          backgroundColor: "var(--color-primary)",
                          color: "#fff",
                        }}
                      >
                        {t("jobs.matchRole")}
                      </button>
                    </div>
                  </div>
                </div>
              )))}
            </div>
          )}
        </>
      )}

      {/* ── Upload Tab: JD File + Text ── */}
      {tab === "upload" && (
        <div className="space-y-6">
          {/* Hint: JD only, not resume */}
          <div
            className="rounded-lg px-4 py-3 text-xs"
            style={{
              backgroundColor: "#fff7ed",
              border: "1px solid #fed7aa",
              color: "#9a3412",
            }}
          >
            <strong>提示：</strong>此处上传的是<strong>职位描述 (JD)</strong> 文件，用于招聘匹配。
            如需上传简历，请前往{" "}
            <Link to="/resume" style={{ color: "var(--color-primary)", textDecoration: "underline" }}>
              简历解析页面
            </Link>。
          </div>

          {/* File drop zone */}
          <div
            ref={dropRef}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className="rounded-lg border-2 border-dashed p-8 text-center cursor-pointer transition-colors"
            style={{
              borderColor: dragOver ? "var(--color-primary)" : "#d0d0d0",
              backgroundColor: dragOver ? "var(--color-primary-bg, #e8f4fd)" : "var(--color-bg-card)",
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.doc,.txt,.md"
              onChange={handleFileSelect}
              className="hidden"
            />
            {uploading ? (
              <p className="text-sm" style={{ color: "var(--color-primary)" }}>
                {t("jobs.uploading")}
              </p>
            ) : (
              <>
                <p className="text-sm font-medium mb-1" style={{ color: "var(--color-text-primary)" }}>
                  {t("jobs.dropTitle")}
                </p>
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {t("jobs.dropHint")}
                </p>
              </>
            )}
          </div>

          {/* Divider */}
          <div className="flex items-center gap-3">
            <div className="flex-1 border-t" style={{ borderColor: "#e0e0e0" }} />
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {t("jobs.pasteDivider")}
            </span>
            <div className="flex-1 border-t" style={{ borderColor: "#e0e0e0" }} />
          </div>

          {/* Text paste area */}
          <div
            className="rounded-lg p-4"
            style={{
              backgroundColor: "var(--color-bg-card)",
              boxShadow: "var(--shadow-sm)",
            }}
          >
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder={t("jobs.jdPlaceholder")}
              rows={8}
              className="border rounded-lg px-3 py-2 text-sm outline-none resize-y w-full mb-3"
              style={{
                borderColor: "#e0e0e0",
                color: "var(--color-text-primary)",
                backgroundColor: "var(--color-bg-surface)",
              }}
            />
            <button
              onClick={handleParseText}
              disabled={!jdText.trim() || parsing}
              className="px-4 py-2 text-sm rounded-lg text-white border-none cursor-pointer disabled:opacity-50 transition-colors"
              style={{ backgroundColor: "var(--color-primary)" }}
            >
              {parsing ? t("jobs.parsing") : t("jobs.parseJd")}
            </button>
          </div>

          {msg && (
            <div className="text-sm text-center" style={{ color: "var(--color-danger)" }}>
              <p>{msg}</p>
              {msgHint === "resume_not_jd" && (
                <Link
                  to="/resume"
                  className="inline-block mt-2 px-4 py-1.5 rounded-lg text-white text-sm no-underline hover:opacity-90 transition-opacity"
                  style={{ backgroundColor: "var(--color-primary)" }}
                >
                  前往简历解析页面上传简历 →
                </Link>
              )}
            </div>
          )}

          {/* Parsed result preview */}
          {parsedJob && (
            <div
              className="rounded-lg p-5"
              style={{
                backgroundColor: "var(--color-bg-card)",
                boxShadow: "var(--shadow-sm)",
                borderLeft: "4px solid var(--color-success)",
              }}
            >
              <h3
                className="font-bold text-base mb-3"
                style={{ color: "var(--color-text-primary)" }}
              >
                ✅ {t("jobs.parseResult")}
              </h3>
              <div className="space-y-2 text-sm">
                <div className="flex gap-2">
                  <span style={{ color: "var(--color-text-muted)", minWidth: 60 }}>{t("jobs.fieldTitle")}:</span>
                  <span style={{ color: "var(--color-text-primary)", fontWeight: 500 }}>
                    {parsedJob.title}
                  </span>
                </div>
                {parsedJob.company && (
                  <div className="flex gap-2">
                    <span style={{ color: "var(--color-text-muted)", minWidth: 60 }}>{t("jobs.fieldCompany")}:</span>
                    <span style={{ color: "var(--color-text-primary)" }}>{parsedJob.company}</span>
                  </div>
                )}
                {parsedJob.location && (
                  <div className="flex gap-2">
                    <span style={{ color: "var(--color-text-muted)", minWidth: 60 }}>{t("jobs.fieldLocation")}:</span>
                    <span style={{ color: "var(--color-text-primary)" }}>{parsedJob.location}</span>
                  </div>
                )}
                {parsedJob.salary_range && (
                  <div className="flex gap-2">
                    <span style={{ color: "var(--color-text-muted)", minWidth: 60 }}>{t("jobs.fieldSalary")}:</span>
                    <span style={{ color: "var(--color-text-primary)" }}>{parsedJob.salary_range}</span>
                  </div>
                )}
                {parsedJob.requirements && parsedJob.requirements.length > 0 && (
                  <div className="flex gap-2">
                    <span style={{ color: "var(--color-text-muted)", minWidth: 60 }}>{t("jobs.fieldRequirements")}:</span>
                    <div className="flex flex-wrap gap-1">
                      {parsedJob.requirements.map((r, j) => (
                        <span
                          key={j}
                          className="text-xs px-2 py-0.5 rounded"
                          style={{
                            backgroundColor: "var(--color-bg-surface)",
                            color: "var(--color-text-secondary)",
                          }}
                        >
                          {r}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <div className="mt-3 flex items-center justify-between gap-3 flex-wrap">
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {t("jobs.savedHint")}
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setTab("browse");
                    if (resumeText.trim()) {
                      void handleMatch(activeJobId || undefined);
                    }
                  }}
                  className="px-3 py-1.5 rounded-lg text-sm text-white border-none cursor-pointer"
                  style={{ backgroundColor: "var(--color-primary)" }}
                >
                  {t("jobs.goMatchNext")}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
    </>
  );
}
