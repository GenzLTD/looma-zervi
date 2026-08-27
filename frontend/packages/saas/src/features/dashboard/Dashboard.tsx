/**
 * Dashboard - SaaS main dashboard with health status, quota, and quick actions.
 * Owner: szbenyx
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { isPaidTier } from "@looma/shared-core";
import { useSaasAuthStore } from "../auth/authStore";
import { useBrand } from "../../brand/useBrand";

interface HealthStatus {
  status: "healthy" | "degraded";
  version: string;
  uptime_seconds: number;
  llm_provider?: string;
  embedding_model?: string;
  vector_store_size?: number;
}

function normalizeHealth(data: Record<string, unknown>): HealthStatus {
  const raw = data.status;
  const healthy = raw === "healthy" || raw === "ok";
  return {
    status: healthy ? "healthy" : "degraded",
    version: String(data.version ?? "v1"),
    uptime_seconds: Number(data.uptime_seconds ?? 0),
    llm_provider: typeof data.llm_provider === "string" ? data.llm_provider : undefined,
    embedding_model: typeof data.embedding_model === "string" ? data.embedding_model : undefined,
    vector_store_size:
      typeof data.vector_store_size === "number" ? data.vector_store_size : undefined,
  };
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

function tierLabel(tier: string, t: (key: string) => string) {
  if (tier === "free") return t("tier.free");
  if (tier === "supporter") return t("tier.supporter");
  return t("tier.pro");
}

export default function Dashboard() {
  const { t } = useTranslation();
  const brand = useBrand();
  const navigate = useNavigate();
  const { user, quota, isAuthenticated, fetchQuota } = useSaasAuthStore();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [quickQuery, setQuickQuery] = useState("");

  const featureCards = useMemo(
    () => [
      { icon: "🧠", title: t("dashboard.featureAiTitle"), desc: t("dashboard.featureAiDesc") },
      { icon: "📄", title: t("dashboard.featureResumeTitle"), desc: t("dashboard.featureResumeDesc") },
      { icon: "📊", title: t("dashboard.featureReportTitle"), desc: t("dashboard.featureReportDesc") },
    ],
    [t],
  );

  useEffect(() => {
    if (isAuthenticated) void fetchQuota();
  }, [isAuthenticated, fetchQuota]);

  useEffect(() => {
    // Prefer same-origin absolute `/health` (Vite proxy). If VITE_API_BASE is set,
    // use that host — never resolve relative to `/tspace/` base.
    const base = API_BASE ? API_BASE.replace(/\/$/, "") : "";
    const healthUrl = base ? `${base}/health` : "/health";
    setHealthLoading(true);
    fetch(healthUrl)
      .then(async (r) => {
        if (!r.ok) return null;
        const ct = r.headers.get("content-type") || "";
        if (!ct.includes("application/json")) return null;
        return r.json();
      })
      .then((data) => {
        if (data) setHealth(normalizeHealth(data));
        else setHealth({ status: "degraded", version: "v1", uptime_seconds: 0 });
      })
      .catch(() => {
        setHealth({ status: "degraded", version: "v1", uptime_seconds: 0 });
      })
      .finally(() => setHealthLoading(false));
  }, []);

  const askRecord = quota?.records?.find((r) => r.resource === "ask");
  const paid = isPaidTier(user?.tier ?? quota?.tier);
  const usagePercent = askRecord && askRecord.daily_limit > 0
    ? Math.round((askRecord.used / askRecord.daily_limit) * 100)
    : 0;

  const submitQuickQuery = () => {
    const q = quickQuery.trim();
    if (!q) return;
    navigate(`/query?q=${encodeURIComponent(q)}`);
  };

  const handleQuickQuery = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") submitQuickQuery();
  };

  const healthLabel = healthLoading
    ? t("dashboard.systemChecking")
    : health?.status === "healthy"
      ? t("dashboard.systemHealthy")
      : t("dashboard.systemDegraded");
  const healthOk = !healthLoading && health?.status === "healthy";

  if (!isAuthenticated) {
    return (
      <div className="max-w-3xl mx-auto text-center" style={{ paddingTop: "4rem" }}>
        <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--color-text-primary)" }}>
          {brand.name}
        </h1>
        <p className="text-lg mb-8" style={{ color: "var(--color-text-secondary)" }}>
          {brand.slogan}
        </p>

        <div className="flex justify-center gap-4 mb-10">
          <Link
            to="/register"
            className="px-6 py-3 rounded-lg text-white text-sm font-medium no-underline transition-opacity hover:opacity-90"
            style={{ backgroundColor: "var(--color-primary)" }}
          >
            {t("dashboard.freeRegister")}
          </Link>
          <Link
            to="/login"
            className="px-6 py-3 rounded-lg text-sm font-medium no-underline border transition-colors"
            style={{
              borderColor: "var(--color-primary)",
              color: "var(--color-primary)",
            }}
          >
            {t("dashboard.hasAccountLogin")}
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
          {featureCards.map((item) => (
            <div
              key={item.title}
              className="rounded-lg p-5 text-left"
              style={{
                backgroundColor: "var(--color-bg-card)",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <div className="text-2xl mb-2">{item.icon}</div>
              <h3 className="text-sm font-medium mb-1" style={{ color: "var(--color-text-primary)" }}>
                {item.title}
              </h3>
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {item.desc}
              </p>
            </div>
          ))}
        </div>

        {(health || healthLoading) && (
          <div className="flex items-center justify-center gap-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{
                backgroundColor: healthOk
                  ? "var(--color-success)"
                  : healthLoading
                    ? "var(--color-text-muted)"
                    : "var(--color-warning)",
              }}
            />
            <span>{t("dashboard.systemLabel")} {healthLabel}</span>
            {health?.version && (
              <>
                <span>·</span>
                <span>v{health.version}</span>
              </>
            )}
          </div>
        )}

        <p className="text-xs mt-6" style={{ color: "var(--color-text-muted)" }}>
          {t("dashboard.welcomeHint")}
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--color-text-primary)" }}>
        {brand.name}
      </h1>
      <p className="text-sm mb-6" style={{ color: "var(--color-text-secondary)" }}>
        {t("dashboard.welcomeBack", { name: user?.name || user?.email || "" })}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div
          className="rounded-lg p-5"
          style={{
            backgroundColor: "var(--color-bg-card)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <h3 className="text-sm font-medium mb-3" style={{ color: "var(--color-text-secondary)" }}>
            {t("dashboard.systemStatus")}
          </h3>
          <div className="flex items-center gap-2 mb-3">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full"
              style={{
                backgroundColor: healthLoading
                  ? "var(--color-text-muted)"
                  : healthOk
                    ? "var(--color-success)"
                    : "var(--color-warning)",
              }}
            />
            <span
              className="font-medium text-sm"
              style={{
                color: healthLoading
                  ? "var(--color-text-muted)"
                  : healthOk
                    ? "var(--color-success)"
                    : "var(--color-warning)",
              }}
            >
              {healthLabel}
            </span>
          </div>
          <div className="text-xs space-y-1" style={{ color: "var(--color-text-muted)" }}>
            {health?.llm_provider && <p>LLM: {health.llm_provider}</p>}
            {health?.embedding_model && <p>{t("dashboard.embedding")}: {health.embedding_model}</p>}
            {health?.vector_store_size != null && (
              <p>{t("dashboard.vectorStore", { count: health.vector_store_size })}</p>
            )}
          </div>
        </div>

        <div
          className="rounded-lg p-5"
          style={{
            backgroundColor: "var(--color-bg-card)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <h3 className="text-sm font-medium mb-3" style={{ color: "var(--color-text-secondary)" }}>
            {t("dashboard.todayQuota")}
          </h3>
          {quota && askRecord ? (
            <>
              {paid ? (
                <div className="mb-3">
                  <span
                    className="text-2xl font-bold"
                    style={{ color: "var(--color-primary)" }}
                  >
                    {t("tier.unlimited")}
                  </span>
                </div>
              ) : (
                <>
                  <div className="flex items-baseline gap-1 mb-3">
                    <span
                      className="text-3xl font-bold"
                      style={{ color: "var(--color-primary)" }}
                    >
                      {askRecord.daily_limit - askRecord.used}
                    </span>
                    <span style={{ color: "var(--color-text-muted)" }}>
                      / {askRecord.daily_limit} {t("dashboard.timesUnit")}
                    </span>
                  </div>
                  <div
                    className="h-2 rounded-full overflow-hidden"
                    style={{ backgroundColor: "var(--color-bg-surface)" }}
                  >
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${Math.min(usagePercent, 100)}%`,
                        backgroundColor:
                          usagePercent > 80 ? "var(--color-warning)" : "var(--color-primary)",
                      }}
                    />
                  </div>
                </>
              )}
              {!paid && (
                <p className="text-[11px] mt-2 leading-snug" style={{ color: "var(--color-text-muted)" }}>
                  {t("dashboard.quotaRulesHint")}
                </p>
              )}
              <div className="flex items-center justify-between mt-2">
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {tierLabel(quota.tier, t)}
                </p>
                <Link
                  to="/pricing"
                  className="text-xs no-underline hover:underline"
                  style={{ color: "var(--color-primary)" }}
                >
                  {paid ? t("dashboard.viewPlans") : t("dashboard.upgrade")}
                </Link>
              </div>
            </>
          ) : (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              {t("common.loading")}
            </p>
          )}
        </div>

        <div
          className="rounded-lg p-5"
          style={{
            backgroundColor: "var(--color-bg-card)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <h3 className="text-sm font-medium mb-3" style={{ color: "var(--color-text-secondary)" }}>
            {t("dashboard.quickActions")}
          </h3>
          <div className="space-y-2">
            <Link
              to="/query"
              className="block w-full text-center px-4 py-2 text-sm rounded-md border transition-colors no-underline"
              style={{
                borderColor: "var(--color-primary)",
                color: "var(--color-primary)",
              }}
            >
              {t("dashboard.startQuery")}
            </Link>
            <Link
              to="/resume"
              className="block w-full text-center px-4 py-2 text-sm rounded-md border transition-colors no-underline"
              style={{
                borderColor: "var(--color-primary)",
                color: "var(--color-primary)",
              }}
            >
              {t("dashboard.parseResume")}
            </Link>
            <Link
              to="/jobs"
              className="block w-full text-center px-4 py-2 text-sm rounded-md border transition-colors no-underline"
              style={{
                borderColor: "var(--color-primary)",
                color: "var(--color-primary)",
              }}
            >
              {t("dashboard.jobMatch")}
            </Link>
          </div>
        </div>
      </div>

      <div
        className="rounded-lg p-5 mb-6"
        style={{
          backgroundColor: "var(--color-bg-card)",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <h3 className="text-sm font-medium mb-3" style={{ color: "var(--color-text-secondary)" }}>
          {t("dashboard.quickQuery")}
        </h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={quickQuery}
            onChange={(e) => setQuickQuery(e.target.value)}
            placeholder={t("dashboard.quickQueryPlaceholder")}
            className="flex-1 px-4 py-2.5 text-sm rounded-lg border outline-none transition-colors"
            style={{
              borderColor: "#e0e0e0",
              color: "var(--color-text-primary)",
            }}
            onKeyDown={handleQuickQuery}
            onFocus={(e) => {
              e.target.style.borderColor = "var(--color-primary)";
            }}
            onBlur={(e) => {
              e.target.style.borderColor = "#e0e0e0";
            }}
          />
          <button
            type="button"
            onClick={submitQuickQuery}
            disabled={!quickQuery.trim()}
            className="px-5 py-2.5 text-sm rounded-lg text-white cursor-pointer border-none transition-colors disabled:opacity-50"
            style={{ backgroundColor: "var(--color-primary)" }}
          >
            {t("dashboard.ask")}
          </button>
        </div>
      </div>

      {health && health.uptime_seconds > 0 && (
        <p className="text-xs text-center" style={{ color: "var(--color-text-muted)" }}>
          {t("dashboard.uptime", {
            version: health.version,
            hours: Math.floor(health.uptime_seconds / 3600),
            minutes: Math.floor((health.uptime_seconds % 3600) / 60),
          })}
        </p>
      )}
    </div>
  );
}
