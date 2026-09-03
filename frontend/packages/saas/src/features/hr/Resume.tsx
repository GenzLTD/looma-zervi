/**
 * Resume - Upload and AI parsing page.
 * Owner: szbenyx
 *
 * Pure CSS + Tailwind (no tdesign-react).
 * Uses authStore for token, direct fetch for file upload.
 */
import { useState, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError, createResumeApi, type ParsedResume } from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";
import { useConsent } from "../../compliance/useConsent";
import QuotaExhaustedModal from "../../brand/components/QuotaExhaustedModal";
import { buildResumeMatchText, saveResumeMatchText } from "./resumeMatchBridge";
import { normalizeParsedResume } from "./normalizeParsedResume";

export default function Resume() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [resume, setResume] = useState<ParsedResume | null>(null);
  const [resumeId, setResumeId] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [quotaExhausted, setQuotaExhausted] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const api = useMemo(() => createSaasApiClient(), []);
  const resumeApi = createResumeApi(api);
  const { ensureConsent, consentPrompt } = useConsent(() => api);

  const handleBringToMatch = () => {
    if (!resume) return;
    const text = buildResumeMatchText(resume);
    if (!text) return;
    saveResumeMatchText(text, resumeId);
    navigate("/jobs");
  };

  const handleUpload = async (file: File) => {
    const allowed = await ensureConsent("jobseeker_core");
    if (!allowed) {
      setMsg("需要授权后才能上传简历");
      return;
    }
    setParsing(true);
    setMsg(null);
    setResume(null);
    setResumeId(null);
    try {
      const result = await resumeApi.upload(file) as any;
      if (result.resume_id) {
        setResumeId(String(result.resume_id));
      }
      if (result.extracted) {
        const normalized = normalizeParsedResume(result.extracted);
        setResume(normalized ?? result.extracted);
        setMsg("简历解析完成");
      } else if (result.error) {
        setMsg(result.error);
      } else if (result.markdown && !result.extracted) {
        // LLM extraction failed but MarkItDown succeeded - show partial result
        setMsg("简历已提取文本，但结构化解析失败，请稍后重试");
      } else {
        setMsg("简历解析完成，但未能提取结构化信息");
      }
    } catch (err: unknown) {
      const apiErr = err instanceof ApiError ? err : null;
      if (apiErr?.status === 422 || apiErr?.status === 503) {
        setMsg(apiErr.body?.message || "文档解析失败，请检查文件格式或文件是否损坏");
      } else if (apiErr?.status === 400) {
        setMsg(apiErr.body?.message || "不支持的文件格式，请上传 PDF 或 Word 文件");
      } else if (
        apiErr?.status === 429 &&
        apiErr.body?.error === "quota_exceeded"
      ) {
        setQuotaExhausted(true);
        setMsg(null);
      } else if (apiErr?.status === 429) {
        setMsg("今日简历解析配额已用尽，请明天再试或升级套餐");
      } else if (err instanceof Error && err.message === "request_timeout") {
        setMsg("请求超时，请检查网络或稍后重试");
      } else if (apiErr?.body?.message) {
        setMsg(String(apiErr.body.message));
      } else {
        setMsg("解析失败，请检查文件格式");
      }
    } finally {
      setParsing(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  };

  return (
    <>
    {consentPrompt}
    <QuotaExhaustedModal
      isOpen={quotaExhausted}
      onClose={() => setQuotaExhausted(false)}
    />
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6" style={{ color: "var(--color-text-primary)" }}>
        简历解析
      </h1>

      {/* 上传区域 */}
      <div
        className={`rounded-lg p-8 mb-6 text-center border-2 border-dashed transition-colors cursor-pointer ${
          dragOver ? "border-[var(--color-primary)] bg-blue-50" : ""
        }`}
        style={{
          backgroundColor: "var(--color-bg-card)",
          borderColor: dragOver ? "var(--color-primary)" : "#e0e0e0",
          boxShadow: "var(--shadow-sm)",
        }}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc"
          onChange={handleFileChange}
          className="hidden"
        />
        <span className="text-4xl block mb-3">📄</span>
        <p className="font-medium" style={{ color: "var(--color-text-primary)" }}>
          点击或拖拽上传简历
        </p>
        <p className="text-sm mt-1" style={{ color: "var(--color-text-muted)" }}>
          支持 PDF / DOCX；旧版 .doc 请先另存为 .docx 或 PDF
        </p>
      </div>

      {parsing && (
        <div className="text-center text-sm mb-4" style={{ color: "var(--color-text-secondary)" }}>
          AI 正在解析简历，请稍候...
        </div>
      )}

      {msg && (
        <p
          className="text-sm mb-4 text-center"
          style={{
            color: msg.includes("完成") ? "var(--color-success)" : "var(--color-danger)",
          }}
        >
          {msg}
        </p>
      )}

      {/* 解析结果 */}
      {resume && (
        <div
          className="rounded-lg p-6"
          style={{
            backgroundColor: "var(--color-bg-card)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div className="flex items-start justify-between gap-3 mb-4">
            <h2 className="text-lg font-bold" style={{ color: "var(--color-text-primary)" }}>
              解析结果
            </h2>
            <button
              type="button"
              onClick={handleBringToMatch}
              className="shrink-0 px-3 py-1.5 rounded-lg text-sm text-white border-none cursor-pointer"
              style={{ backgroundColor: "var(--color-primary)" }}
              title={t("resume.bringToMatchHint")}
            >
              {t("resume.bringToMatch")}
            </button>
          </div>

          {/* 基本信息 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
            {resume.name && (
              <div className="flex items-center gap-2 text-sm" style={{ color: "var(--color-text-secondary)" }}>
                <span>👤</span>
                <span className="font-medium" style={{ color: "var(--color-text-primary)" }}>
                  {resume.name}
                </span>
              </div>
            )}
            {resume.email && (
              <div className="flex items-center gap-2 text-sm" style={{ color: "var(--color-text-secondary)" }}>
                <span>📧</span>
                <span>{resume.email}</span>
              </div>
            )}
            {resume.phone && (
              <div className="flex items-center gap-2 text-sm" style={{ color: "var(--color-text-secondary)" }}>
                <span>📱</span>
                <span>{resume.phone}</span>
              </div>
            )}
          </div>

          {/* 技能标签 */}
          {resume.skills && resume.skills.length > 0 && (
            <>
              <div className="border-t mb-3" style={{ borderColor: "#e0e0e0" }} />
              <h3 className="text-sm font-medium mb-2" style={{ color: "var(--color-text-secondary)" }}>
                技能
              </h3>
              <div className="flex flex-wrap gap-2 mb-6">
                {resume.skills.map((s, i) => (
                  <span
                    key={i}
                    className="text-xs px-3 py-1 rounded-full"
                    style={{
                      backgroundColor: "#e8f0fe",
                      color: "var(--color-primary)",
                    }}
                  >
                    {s}
                  </span>
                ))}
              </div>
            </>
          )}

          {/* 工作经验 */}
          {resume.experiences && resume.experiences.length > 0 && (
            <>
              <div className="border-t mb-3" style={{ borderColor: "#e0e0e0" }} />
              <h3 className="text-sm font-medium mb-3" style={{ color: "var(--color-text-secondary)" }}>
                工作经历
              </h3>
              <div className="space-y-3 mb-6">
                {resume.experiences.map((exp, i) => (
                  <div
                    key={i}
                    className="rounded-lg p-3"
                    style={{ backgroundColor: "var(--color-bg-surface)" }}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-sm" style={{ color: "var(--color-text-primary)" }}>
                        {exp.title}
                      </span>
                      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                        {exp.start_date || ""} ~ {exp.end_date || "至今"}
                      </span>
                    </div>
                    <p className="text-xs mb-1" style={{ color: "var(--color-text-secondary)" }}>
                      {exp.company}
                    </p>
                    {exp.description && (
                      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                        {exp.description}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          {/* 教育背景 */}
          {resume.education && resume.education.length > 0 && (
            <>
              <div className="border-t mb-3" style={{ borderColor: "#e0e0e0" }} />
              <h3 className="text-sm font-medium mb-3" style={{ color: "var(--color-text-secondary)" }}>
                教育背景
              </h3>
              <div className="space-y-2 mb-6">
                {resume.education.map((edu, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <div>
                      <span className="font-medium" style={{ color: "var(--color-text-primary)" }}>
                        {edu.school}
                      </span>
                      <span className="ml-2" style={{ color: "var(--color-text-muted)" }}>
                        {edu.field}
                      </span>
                    </div>
                    <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                      {edu.degree}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* AI 摘要 */}
          {resume.summary && (
            <>
              <div className="border-t mb-3" style={{ borderColor: "#e0e0e0" }} />
              <h3 className="text-sm font-medium mb-2" style={{ color: "var(--color-text-secondary)" }}>
                AI 摘要
              </h3>
              <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
                {resume.summary}
              </p>
            </>
          )}
        </div>
      )}
    </div>
    </>
  );
}
