/**
 * Reports — match reports (user-owned) + ops daily/weekly/monthly.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  createMatchReportsApi,
  createReportsApi,
  formatDate,
  type MatchReport,
  type MatchReportItem,
  type MatchReportSummary,
  type Report,
  type ReportType,
  type ShareDimension,
} from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";
import { useSaasAuthStore } from "../auth/authStore";
import { useConsent } from "../../compliance/useConsent";

const typeMap: Record<string, { label: string; emoji: string }> = {
  daily: { label: "日报", emoji: "📊" },
  weekly: { label: "周报", emoji: "📈" },
  monthly: { label: "月报", emoji: "📋" },
};

const SCORE_KEYS: { key: keyof MatchReportItem; label: string; max: number }[] = [
  { key: "background_match", label: "背景", max: 10 },
  { key: "skills_overlap", label: "技能", max: 30 },
  { key: "experience_relevance", label: "经历", max: 30 },
  { key: "seniority", label: "职级", max: 10 },
  { key: "language_requirement", label: "语言", max: 10 },
  { key: "company_score", label: "公司", max: 10 },
  { key: "salary_match", label: "薪资", max: 10 },
  { key: "location_match", label: "地点", max: 10 },
  { key: "culture_workload_match", label: "强度", max: 10 },
];

const SHARE_DIMS: { id: ShareDimension; label: string }[] = [
  { id: "skills", label: "技能标签" },
  { id: "scores", label: "评分数据" },
  { id: "gap_analysis", label: "改进建议" },
  { id: "experience", label: "经历相关" },
  { id: "personal_info", label: "基本信息" },
  { id: "credit", label: "企业征信" },
];

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function Reports() {
  const [searchParams, setSearchParams] = useSearchParams();
  const token = useSaasAuthStore((s) => s.token);
  const api = useMemo(() => createSaasApiClient(), []);
  const reportsApi = useMemo(() => createReportsApi(api), [api]);
  const matchReportsApi = useMemo(() => createMatchReportsApi(api), [api]);
  const { ensureConsent, consentPrompt } = useConsent(() => api);

  const [opsReports, setOpsReports] = useState<Report[]>([]);
  const [type, setType] = useState<ReportType>("daily");
  const [generating, setGenerating] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [matchReports, setMatchReports] = useState<MatchReportSummary[]>([]);
  const [matchTotal, setMatchTotal] = useState(0);
  const [activeMatch, setActiveMatch] = useState<MatchReport | null>(null);
  const [loadingMatch, setLoadingMatch] = useState(false);
  const [shareDims, setShareDims] = useState<ShareDimension[]>(["skills", "scores", "gap_analysis"]);
  const [sharingBusy, setSharingBusy] = useState(false);
  const [showCompare, setShowCompare] = useState(false);

  const fetchOpsReports = useCallback(async () => {
    try {
      const res = await reportsApi.list();
      setOpsReports(res.reports);
    } catch {
      /* ignore */
    }
  }, [reportsApi]);

  const fetchMatchReports = useCallback(async () => {
    try {
      const res = await matchReportsApi.list({ page_size: 20 });
      setMatchReports(res.reports);
      setMatchTotal(res.total);
    } catch {
      /* ignore */
    }
  }, [matchReportsApi]);

  const openMatchReport = useCallback(
    async (id: string) => {
      setLoadingMatch(true);
      try {
        const detail = await matchReportsApi.get(id);
        setActiveMatch(detail);
        setSearchParams({ match: id }, { replace: true });
        const active = detail.sharings?.find((s) => s.status === "active");
        if (active?.shared_dimensions?.length) {
          setShareDims(active.shared_dimensions as ShareDimension[]);
        }
      } catch {
        setMsg("加载匹配报告失败");
      } finally {
        setLoadingMatch(false);
      }
    },
    [matchReportsApi, setSearchParams],
  );

  useEffect(() => {
    if (!token) return;
    void fetchOpsReports();
    void fetchMatchReports();
  }, [token, fetchOpsReports, fetchMatchReports]);

  const focusMatchId = searchParams.get("match");
  useEffect(() => {
    if (focusMatchId && token) void openMatchReport(focusMatchId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusMatchId, token]);

  const handleGenerate = async () => {
    setGenerating(true);
    setMsg(null);
    try {
      await reportsApi.generate({ type });
      setMsg("报告生成成功");
      void fetchOpsReports();
    } catch {
      setMsg("生成失败，请检查后端服务");
    } finally {
      setGenerating(false);
    }
  };

  const handleDeleteMatch = async (id: string) => {
    try {
      await matchReportsApi.remove(id);
      if (activeMatch?.id === id) {
        setActiveMatch(null);
        setSearchParams({}, { replace: true });
      }
      void fetchMatchReports();
    } catch {
      setMsg("删除匹配报告失败");
    }
  };

  const handleExport = async (id: string) => {
    try {
      const data = await matchReportsApi.export(id);
      downloadJson(`match-report-${id.slice(0, 8)}.json`, data);
      setMsg("报告已导出为 JSON");
    } catch {
      setMsg("导出失败");
    }
  };

  const handleShare = async () => {
    if (!activeMatch) return;
    const allowed = await ensureConsent("report_share");
    if (!allowed) {
      setMsg("需要授权「报告分享」后才能授权给合伙人");
      return;
    }
    setSharingBusy(true);
    try {
      await matchReportsApi.share(activeMatch.id, {
        shared_dimensions: shareDims,
        purpose: "用于职业成长合伙人持续推荐",
      });
      setMsg("已授权给职业成长合伙人");
      await openMatchReport(activeMatch.id);
      void fetchMatchReports();
    } catch {
      setMsg("授权失败，请重试");
    } finally {
      setSharingBusy(false);
    }
  };

  const handleRevoke = async () => {
    if (!activeMatch) return;
    const active = activeMatch.sharings?.find((s) => s.status === "active");
    if (!active) return;
    setSharingBusy(true);
    try {
      await matchReportsApi.revokeShare(activeMatch.id, active.id);
      setMsg("已撤回授权");
      await openMatchReport(activeMatch.id);
    } catch {
      setMsg("撤回失败");
    } finally {
      setSharingBusy(false);
    }
  };

  const comparePair = matchReports.slice(0, 2);

  return (
    <>
    {consentPrompt}
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6" style={{ color: "var(--color-text-primary)" }}>
        报告中心
      </h1>

      <section className="mb-10">
        <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
          <h2 className="text-lg font-medium" style={{ color: "var(--color-text-primary)" }}>
            我的匹配报告
          </h2>
          <div className="flex items-center gap-3">
            {matchReports.length >= 2 && (
              <button
                type="button"
                onClick={() => setShowCompare((v) => !v)}
                className="text-xs bg-transparent border-none cursor-pointer"
                style={{ color: "var(--color-primary)" }}
              >
                {showCompare ? "收起对比" : "对比最近 2 份"}
              </button>
            )}
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              共 {matchTotal} 份
            </span>
          </div>
        </div>

        {showCompare && comparePair.length === 2 && (
          <div
            className="rounded-lg p-4 mb-4 grid grid-cols-2 gap-3"
            style={{ backgroundColor: "var(--color-bg-card)", boxShadow: "var(--shadow-sm)" }}
          >
            {comparePair.map((r) => (
              <div key={r.id}>
                <p className="text-sm font-medium" style={{ color: "var(--color-text-primary)" }}>
                  {r.title}
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                  {r.created_at ? formatDate(r.created_at) : ""}
                </p>
                <p className="text-xs mt-2" style={{ color: "var(--color-text-secondary)" }}>
                  职位 {r.metadata?.total_jobs ?? 0}
                  {" · "}最高 {r.metadata?.max_score ?? "—"}
                  {" · "}平均 {r.metadata?.avg_score ?? "—"}
                </p>
              </div>
            ))}
          </div>
        )}

        {matchReports.length === 0 ? (
          <div
            className="rounded-lg p-8 text-center"
            style={{ backgroundColor: "var(--color-bg-card)", boxShadow: "var(--shadow-sm)" }}
          >
            <p className="text-sm mb-3" style={{ color: "var(--color-text-muted)" }}>
              暂无匹配报告。完成职位匹配后点击「保存为报告」。
            </p>
            <Link
              to="/jobs"
              className="inline-block px-4 py-2 rounded-lg text-sm text-white no-underline"
              style={{ backgroundColor: "var(--color-primary)" }}
            >
              去职位匹配 →
            </Link>
          </div>
        ) : (
          <div className="space-y-3 mb-4">
            {matchReports.map((r) => (
              <div
                key={r.id}
                className="rounded-lg p-4 flex items-start justify-between gap-3"
                style={{ backgroundColor: "var(--color-bg-card)", boxShadow: "var(--shadow-sm)" }}
              >
                <button
                  type="button"
                  onClick={() => void openMatchReport(r.id)}
                  className="text-left flex-1 bg-transparent border-none cursor-pointer p-0"
                >
                  <p className="font-medium text-sm" style={{ color: "var(--color-text-primary)" }}>
                    {r.title}
                  </p>
                  <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                    {r.metadata?.total_jobs ?? 0} 个职位
                    {r.metadata?.max_score != null ? ` · 最高 ${r.metadata.max_score}` : ""}
                    {r.metadata?.avg_score != null ? ` · 平均 ${r.metadata.avg_score}` : ""}
                    {" · "}
                    {r.created_at ? formatDate(r.created_at) : ""}
                  </p>
                </button>
                <div className="flex flex-col gap-1 shrink-0 items-end">
                  <button
                    type="button"
                    onClick={() => void handleExport(r.id)}
                    className="text-xs bg-transparent border-none cursor-pointer"
                    style={{ color: "var(--color-primary)" }}
                  >
                    导出
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDeleteMatch(r.id)}
                    className="text-xs bg-transparent border-none cursor-pointer"
                    style={{ color: "var(--color-text-muted)" }}
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {(loadingMatch || activeMatch) && (
          <div
            className="rounded-lg p-5 mt-2"
            style={{ backgroundColor: "var(--color-bg-card)", boxShadow: "var(--shadow-sm)" }}
          >
            {loadingMatch && !activeMatch ? (
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>加载详情…</p>
            ) : activeMatch ? (
              <>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <h3 className="font-medium" style={{ color: "var(--color-text-primary)" }}>
                      {activeMatch.title}
                    </h3>
                    <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                      {activeMatch.summary}
                    </p>
                  </div>
                  <div className="flex gap-2 items-center">
                    <Link
                      to={`/query?report=${encodeURIComponent(activeMatch.id)}`}
                      className="text-xs no-underline"
                      style={{ color: "var(--color-primary)" }}
                    >
                      基于报告提问
                    </Link>
                    <button
                      type="button"
                      onClick={() => void handleExport(activeMatch.id)}
                      className="text-xs bg-transparent border-none cursor-pointer"
                      style={{ color: "var(--color-primary)" }}
                    >
                      导出 JSON
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setActiveMatch(null);
                        setSearchParams({}, { replace: true });
                      }}
                      className="text-xs bg-transparent border-none cursor-pointer"
                      style={{ color: "var(--color-text-muted)" }}
                    >
                      收起
                    </button>
                  </div>
                </div>

                <ul className="space-y-3 mb-5">
                  {activeMatch.items.map((item) => (
                    <li
                      key={item.id}
                      className="p-3 rounded"
                      style={{ backgroundColor: "var(--color-bg-surface)" }}
                    >
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <p className="text-sm font-medium" style={{ color: "var(--color-text-primary)" }}>
                          {item.job_title}
                          <span className="font-normal" style={{ color: "var(--color-text-muted)" }}>
                            {" · "}{item.company_name}
                          </span>
                        </p>
                        <span className="text-sm font-bold" style={{ color: "var(--color-primary)" }}>
                          {Math.round(Number(item.overall_score))}
                        </span>
                      </div>
                      <div className="space-y-1 mb-2">
                        {SCORE_KEYS.map(({ key, label, max }) => {
                          const val = Number(item[key] ?? 0);
                          return (
                            <div key={key} className="flex items-center gap-2 text-xs">
                              <span className="w-8 shrink-0" style={{ color: "var(--color-text-muted)" }}>
                                {label}
                              </span>
                              <div className="flex-1 h-1.5 rounded-full" style={{ backgroundColor: "#e5e7eb" }}>
                                <div
                                  className="h-1.5 rounded-full"
                                  style={{
                                    width: `${Math.min(100, (val / max) * 100)}%`,
                                    backgroundColor: "var(--color-primary)",
                                  }}
                                />
                              </div>
                              <span style={{ color: "var(--color-text-secondary)" }}>{val}/{max}</span>
                            </div>
                          );
                        })}
                      </div>
                      {item.match_reason && (
                        <p className="text-xs mb-1" style={{ color: "var(--color-text-secondary)" }}>
                          {item.match_reason}
                        </p>
                      )}
                      {item.gap_analysis?.length > 0 && (
                        <p className="text-xs" style={{ color: "var(--color-warning)" }}>
                          差距：{item.gap_analysis.map((g) => `${g.skill}(${g.priority})`).join("、")}
                        </p>
                      )}
                      {item.improvement_plan && (
                        <p className="text-xs mt-1 whitespace-pre-wrap" style={{ color: "var(--color-text-muted)" }}>
                          {item.improvement_plan}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>

                <div
                  className="rounded-lg p-4 border"
                  style={{ borderColor: "var(--color-border, #e0e0e0)" }}
                >
                  <p className="text-sm font-medium mb-2" style={{ color: "var(--color-text-primary)" }}>
                    授权给职业成长合伙人
                  </p>
                  <p className="text-xs mb-3" style={{ color: "var(--color-text-muted)" }}>
                    当前：
                    {activeMatch.sharings?.some((s) => s.status === "active")
                      ? "已授权"
                      : "仅自己可见"}
                  </p>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {SHARE_DIMS.map((d) => {
                      const on = shareDims.includes(d.id);
                      return (
                        <button
                          key={d.id}
                          type="button"
                          onClick={() =>
                            setShareDims((prev) =>
                              on ? prev.filter((x) => x !== d.id) : [...prev, d.id],
                            )
                          }
                          className="text-xs px-2 py-1 rounded border cursor-pointer"
                          style={{
                            borderColor: on ? "var(--color-primary)" : "#e0e0e0",
                            backgroundColor: on ? "var(--color-primary)" : "transparent",
                            color: on ? "#fff" : "var(--color-text-secondary)",
                          }}
                        >
                          {d.label}
                        </button>
                      );
                    })}
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={sharingBusy || shareDims.length === 0}
                      onClick={() => void handleShare()}
                      className="px-3 py-1.5 rounded text-sm text-white border-none cursor-pointer disabled:opacity-50"
                      style={{ backgroundColor: "var(--color-primary)" }}
                    >
                      {sharingBusy ? "处理中…" : "更新授权"}
                    </button>
                    {activeMatch.sharings?.some((s) => s.status === "active") && (
                      <button
                        type="button"
                        disabled={sharingBusy}
                        onClick={() => void handleRevoke()}
                        className="px-3 py-1.5 rounded text-sm border cursor-pointer disabled:opacity-50"
                        style={{
                          borderColor: "#e0e0e0",
                          backgroundColor: "transparent",
                          color: "var(--color-text-secondary)",
                        }}
                      >
                        撤回授权
                      </button>
                    )}
                  </div>
                </div>
              </>
            ) : null}
          </div>
        )}

        {msg && (
          <p
            className="text-sm mt-3"
            style={{
              color:
                msg.includes("成功") || msg.includes("已") || msg.includes("导出")
                  ? "var(--color-success)"
                  : "var(--color-danger)",
            }}
          >
            {msg}
          </p>
        )}
      </section>

      <section>
        <h2 className="text-lg font-medium mb-4" style={{ color: "var(--color-text-primary)" }}>
          运营报告（日/周/月）
        </h2>

        <div
          className="rounded-lg p-6 mb-6"
          style={{
            backgroundColor: "var(--color-bg-card)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <h3 className="font-medium mb-4" style={{ color: "var(--color-text-primary)" }}>
            生成报告
          </h3>
          <div className="flex items-center gap-3">
            <select
              value={type}
              onChange={(e) => setType(e.target.value as ReportType)}
              className="border rounded-lg px-3 py-2 text-sm outline-none"
              style={{
                borderColor: "#e0e0e0",
                color: "var(--color-text-primary)",
                width: "160px",
              }}
            >
              <option value="daily">日报</option>
              <option value="weekly">周报</option>
              <option value="monthly">月报</option>
            </select>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="px-4 py-2 text-sm rounded-lg text-white border-none cursor-pointer disabled:opacity-50 transition-colors"
              style={{ backgroundColor: "var(--color-primary)" }}
            >
              {generating ? "生成中..." : `生成${typeMap[type].label}`}
            </button>
          </div>
        </div>

        <div className="space-y-4">
          {opsReports.length === 0 ? (
            <div className="text-center py-10" style={{ color: "var(--color-text-muted)" }}>
              <p>暂无运营报告</p>
            </div>
          ) : (
            opsReports.map((r) => (
              <div
                key={r.path}
                className="rounded-lg p-5"
                style={{
                  backgroundColor: "var(--color-bg-card)",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{typeMap[r.type]?.emoji ?? "📄"}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-medium" style={{ color: "var(--color-text-primary)" }}>
                        {typeMap[r.type]?.label ?? r.type}报告
                      </h3>
                      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                        {r.generated_at ? formatDate(r.generated_at) : ""}
                      </span>
                    </div>
                    <p className="text-sm line-clamp-1" style={{ color: "var(--color-text-secondary)" }}>
                      {r.path}
                    </p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
    </>
  );
}
