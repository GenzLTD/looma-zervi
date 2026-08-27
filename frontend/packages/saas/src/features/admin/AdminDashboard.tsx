/**
 * AdminDashboard — 管理看板
 * Owner: Jason
 *
 * 展示内测闭环数据：用户统计、漏斗转化、Phase 0 指标、系统健康。
 * 仅 admin 角色可见。
 */
import { useEffect, useMemo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { createAdminApi, type AdminStatsResponse, type AdminFunnelResponse, type AdminNarrativeResponse, type AdminHealthResponse } from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";

// ── helpers ──

function formatNumber(n: number | undefined | null): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

/** Display 0-100 percentage (backend returns percentage value directly) */
function pct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v.toFixed(1)}%`;
}

/** Display 0-1 ratio as percentage (funnel conversion returns ratio) */
function ratioPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function tierColor(tier: string): string {
  if (tier === "pro" || tier === "enterprise") return "var(--color-primary)";
  if (tier === "supporter") return "var(--color-warning)";
  return "var(--color-text-muted)";
}

function tierLabel(tier: string): string {
  const map: Record<string, string> = {
    free: "免费版",
    supporter: "支持版",
    pro: "专业版",
    enterprise: "企业版",
  };
  return map[tier] ?? tier;
}

const FUNNEL_STEP_LABELS: Record<string, string> = {
  quiz_complete: "答题完成",
  share_code_created: "创建分享码",
  share_link_copied: "复制分享链接",
  profile_view_public: "公开档案浏览",
  hr_register_from_share: "HR 从分享注册",
  candidate_imported: "导入候选人",
  trial_started: "开始试用",
};

const CONVERSION_LABELS: Record<string, string> = {
  share_after_quiz: "答题→分享",
  view_after_share: "分享→浏览",
  import_after_view: "浏览→导入",
  trial_after_import: "导入→试用",
};

// ── Card wrapper ──

function Card({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-lg p-5 ${className}`}
      style={{
        backgroundColor: "var(--color-bg-card)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <h3
        className="text-sm font-medium mb-3"
        style={{ color: "var(--color-text-secondary)" }}
      >
        {title}
      </h3>
      {children}
    </div>
  );
}

// ── Stat badge ──

function StatBadge({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="text-center">
      <div
        className="text-2xl font-bold"
        style={{ color: color ?? "var(--color-primary)" }}
      >
        {value}
      </div>
      <div
        className="text-xs mt-1"
        style={{ color: "var(--color-text-muted)" }}
      >
        {label}
      </div>
    </div>
  );
}

// ── Main component ──

export default function AdminDashboard() {
  const { t } = useTranslation();
  const api = useMemo(() => createAdminApi(createSaasApiClient()), []);

  const [stats, setStats] = useState<AdminStatsResponse | null>(null);
  const [funnel, setFunnel] = useState<AdminFunnelResponse | null>(null);
  const [narrative, setNarrative] = useState<AdminNarrativeResponse | null>(null);
  const [health, setHealth] = useState<AdminHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [funnelDays, setFunnelDays] = useState(30);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, f, n, h] = await Promise.all([
        api.stats(),
        api.funnel(funnelDays),
        api.narrative(),
        api.health(),
      ]);
      setStats(s);
      setFunnel(f);
      setNarrative(n);
      setHealth(h);
    } catch (e: unknown) {
      const msg =
        (e as { message?: string })?.message ??
        (e as { detail?: string })?.detail ??
        "加载管理数据失败";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [api, funnelDays]);

  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  // ── Loading ──
  if (loading) {
    return (
      <div className="max-w-6xl mx-auto py-8 text-center">
        <p style={{ color: "var(--color-text-muted)" }}>{t("common.loading")}</p>
      </div>
    );
  }

  // ── Error ──
  if (error) {
    return (
      <div className="max-w-6xl mx-auto py-8 text-center">
        <p className="text-sm mb-3" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
        <button
          onClick={fetchAll}
          className="px-4 py-2 text-sm rounded border-none cursor-pointer text-white"
          style={{ backgroundColor: "var(--color-primary)" }}
        >
          重试
        </button>
      </div>
    );
  }

  const dauMax = Math.max(
    1,
    ...(stats?.activity.dau_trend.map((d) => d.count) ?? [0]),
  );

  return (
    <div className="max-w-6xl mx-auto pb-12">
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1
            className="text-2xl font-bold mb-1"
            style={{ color: "var(--color-text-primary)" }}
          >
            管理看板
          </h1>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            内测闭环数据 ·{" "}
            {health?.environment
              ? `环境: ${health.environment}`
              : ""}
          </p>
        </div>
        <span
          className="text-xs px-2 py-1 rounded"
          style={{
            backgroundColor: "var(--color-primary)",
            color: "#fff",
            opacity: 0.8,
          }}
        >
          ADMIN
        </span>
      </div>

      {/* ── Row 1: User overview ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
        <Card title="总用户">
          <StatBadge
            label="注册用户"
            value={formatNumber(stats?.users.total)}
          />
        </Card>
        <Card title="本周新增">
          <StatBadge
            label="7 日新用户"
            value={formatNumber(stats?.users.new_this_week)}
            color="var(--color-success)"
          />
        </Card>
        <Card title="今日新增">
          <StatBadge
            label="今日注册"
            value={formatNumber(stats?.users.new_today)}
            color="var(--color-success)"
          />
        </Card>
        <Card title="早期用户">
          <StatBadge
            label="内测种子用户"
            value={formatNumber(stats?.users.early_adopters)}
            color="var(--color-warning)"
          />
        </Card>
        <Card title="管理员">
          <StatBadge
            label="Admin 账户"
            value={formatNumber(stats?.users.by_role?.admin)}
          />
        </Card>
        <Card title="数据库">
          <StatBadge
            label="DB 大小"
            value={stats?.system.db_size_mb != null ? `${stats.system.db_size_mb} MB` : "—"}
            color="var(--color-text-muted)"
          />
        </Card>
      </div>

      {/* ── Row 2: Tier distribution + Activity ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {/* Tier distribution */}
        <Card title="套餐分布">
          <div className="space-y-3">
            {stats?.users.by_tier &&
              Object.entries(stats.users.by_tier).map(([tierName, count]) => (
                <div key={tierName} className="flex items-center gap-3">
                  <span
                    className="text-sm w-16"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    {tierLabel(tierName)}
                  </span>
                  <div
                    className="flex-1 h-4 rounded-full overflow-hidden"
                    style={{ backgroundColor: "var(--color-bg-surface)" }}
                  >
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${Math.min(
                          (count / (stats.users.total || 1)) * 100,
                          100,
                        )}%`,
                        backgroundColor: tierColor(tierName),
                      }}
                    />
                  </div>
                  <span
                    className="text-sm font-medium w-10 text-right"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {count}
                  </span>
                </div>
              ))}
          </div>
        </Card>

        {/* Activity overview */}
        <Card title="内容统计">
          <div className="grid grid-cols-2 gap-4">
            <StatBadge
              label="问答查询"
              value={formatNumber(stats?.activity.total_queries)}
            />
            <StatBadge
              label="简历解析"
              value={formatNumber(stats?.activity.total_resumes)}
            />
            <StatBadge
              label="职位发布"
              value={formatNumber(stats?.activity.total_jobs)}
            />
            <StatBadge
              label="匹配次数"
              value={formatNumber(stats?.activity.total_matches)}
            />
            <StatBadge
              label="诗词收录"
              value={formatNumber(stats?.activity.total_poems)}
            />
            <StatBadge
              label="数据表数"
              value={health?.database.table_counts
                ? Object.keys(health.database.table_counts).length
                : "—"}
            />
          </div>
        </Card>
      </div>

      {/* ── Row 3: DAU trend ── */}
      {stats?.activity.dau_trend && stats.activity.dau_trend.length > 0 && (
        <Card title="日活趋势（近7天）" className="mb-6">
          <div className="flex items-end gap-3 h-32">
            {[...stats.activity.dau_trend].reverse().map((point) => (
              <div
                key={point.day}
                className="flex-1 flex flex-col items-center gap-1"
              >
                <span
                  className="text-xs font-medium"
                  style={{ color: "var(--color-text-primary)" }}
                >
                  {point.count}
                </span>
                <div
                  className="w-full rounded-t transition-all"
                  style={{
                    height: `${Math.max((point.count / dauMax) * 80, 4)}%`,
                    backgroundColor: "var(--color-primary)",
                    opacity: 0.75,
                    minHeight: "4px",
                  }}
                />
                <span
                  className="text-xs"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  {point.day.slice(5)}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── Row 4: Funnel + Narrative ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {/* Funnel */}
        <Card title={`转化漏斗（近 ${funnelDays} 天）`}>
          <div className="flex items-center gap-2 mb-3">
            {[7, 14, 30, 60].map((d) => (
              <button
                key={d}
                onClick={() => setFunnelDays(d)}
                className="px-2 py-0.5 text-xs rounded border-none cursor-pointer transition-colors"
                style={{
                  backgroundColor:
                    funnelDays === d
                      ? "var(--color-primary)"
                      : "var(--color-bg-surface)",
                  color:
                    funnelDays === d
                      ? "#fff"
                      : "var(--color-text-secondary)",
                }}
              >
                {d}天
              </button>
            ))}
          </div>
          {funnel?.steps ? (
            <div className="space-y-2">
              {Object.entries(FUNNEL_STEP_LABELS).map(([key, label]) => (
                <div key={key} className="flex items-center justify-between">
                  <span
                    className="text-sm"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    {label}
                  </span>
                  <span
                    className="text-sm font-medium"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {formatNumber(funnel.steps[key] ?? 0)}
                  </span>
                </div>
              ))}
              {/* Conversion rates */}
              <div
                className="mt-3 pt-3"
                style={{ borderTop: "1px solid var(--color-border)" }}
              >
                <p
                  className="text-xs mb-2"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  转化率
                </p>
                {Object.entries(CONVERSION_LABELS).map(([key, label]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span
                      className="text-sm"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      {label}
                    </span>
                    <span
                      className="text-sm font-medium"
                      style={{
                        color:
                          (funnel.conversion[key] ?? 0) > 0.5
                            ? "var(--color-success)"
                            : "var(--color-warning)",
                      }}
                    >
                      {ratioPct(funnel.conversion[key])}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p style={{ color: "var(--color-text-muted)" }}>暂无漏斗数据</p>
          )}
        </Card>

        {/* Narrative / Phase 0 */}
        <Card title="Phase 0 叙事指标">
          {narrative ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  会话总数
                </span>
                <span className="text-sm font-medium" style={{ color: "var(--color-text-primary)" }}>
                  {narrative.total_sessions}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  完成数
                </span>
                <span className="text-sm font-medium" style={{ color: "var(--color-text-primary)" }}>
                  {narrative.completed_sessions}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  完成率
                </span>
                <span
                  className="text-sm font-medium"
                  style={{
                    color:
                      (narrative.completion_rate ?? 0) > 0.5
                        ? "var(--color-success)"
                        : "var(--color-warning)",
                  }}
                >
                  {pct(narrative.completion_rate)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  反馈数
                </span>
                <span className="text-sm font-medium" style={{ color: "var(--color-text-primary)" }}>
                  {narrative.feedback_count}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  共鸣率
                </span>
                <span
                  className="text-sm font-medium"
                  style={{
                    color:
                      (narrative.resonance_rate ?? 0) > 0.5
                        ? "var(--color-success)"
                        : "var(--color-warning)",
                  }}
                >
                  {pct(narrative.resonance_rate)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  分享率
                </span>
                <span
                  className="text-sm font-medium"
                  style={{
                    color:
                      (narrative.share_rate ?? 0) > 0.3
                        ? "var(--color-success)"
                        : "var(--color-warning)",
                  }}
                >
                  {pct(narrative.share_rate)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  重玩意愿
                </span>
                <span
                  className="text-sm font-medium"
                  style={{
                    color:
                      (narrative.replay_intent_rate ?? 0) > 0.4
                        ? "var(--color-success)"
                        : "var(--color-warning)",
                  }}
                >
                  {pct(narrative.replay_intent_rate)}
                </span>
              </div>
            </div>
          ) : (
            <p style={{ color: "var(--color-text-muted)" }}>暂无叙事数据</p>
          )}
        </Card>
      </div>

      {/* ── Row 5: Recent users ── */}
      <Card title="最近注册用户" className="mb-6">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
                <th
                  className="text-left py-2 pr-4"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  用户
                </th>
                <th
                  className="text-left py-2 pr-4"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  邮箱
                </th>
                <th
                  className="text-left py-2 pr-4"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  套餐
                </th>
                <th
                  className="text-left py-2 pr-4"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  角色
                </th>
                <th
                  className="text-right py-2"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  注册时间
                </th>
              </tr>
            </thead>
            <tbody>
              {stats?.users.recent.map((u) => (
                <tr
                  key={u.id}
                  style={{ borderBottom: "1px solid var(--color-border)" }}
                >
                  <td
                    className="py-2 pr-4 truncate max-w-[120px]"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {u.name || "—"}
                  </td>
                  <td
                    className="py-2 pr-4 truncate max-w-[180px]"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    {u.email || "—"}
                  </td>
                  <td className="py-2 pr-4">
                    <span
                      className="text-xs px-1.5 py-0.5 rounded"
                      style={{
                        backgroundColor: tierColor(u.tier),
                        color: "#fff",
                        opacity: 0.8,
                      }}
                    >
                      {tierLabel(u.tier)}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    <span
                      className="text-xs"
                      style={{
                        color:
                          u.role === "admin"
                            ? "var(--color-warning)"
                            : "var(--color-text-muted)",
                      }}
                    >
                      {u.role === "admin" ? "管理员" : "用户"}
                    </span>
                  </td>
                  <td
                    className="py-2 text-right"
                    style={{ color: "var(--color-text-muted)" }}
                  >
                    {u.created_at?.slice(0, 10) ?? "—"}
                  </td>
                </tr>
              ))}
              {(!stats?.users.recent || stats.users.recent.length === 0) && (
                <tr>
                  <td
                    colSpan={5}
                    className="py-4 text-center"
                    style={{ color: "var(--color-text-muted)" }}
                  >
                    暂无用户
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ── Row 6: System health ── */}
      {health && (
        <Card title="系统健康">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p
                className="text-xs mb-1"
                style={{ color: "var(--color-text-muted)" }}
              >
                数据库
              </p>
              <p
                className="text-sm"
                style={{ color: "var(--color-text-primary)" }}
              >
                {health.database.size_mb} MB · {health.database.journal_mode}
              </p>
              <p
                className="text-xs mt-1"
                style={{ color: "var(--color-text-muted)" }}
              >
                {Object.keys(health.database.table_counts).length} 张数据表
              </p>
            </div>
            <div>
              <p
                className="text-xs mb-1"
                style={{ color: "var(--color-text-muted)" }}
              >
                LLM
              </p>
              <p
                className="text-sm"
                style={{ color: "var(--color-text-primary)" }}
              >
                {health.llm.provider}
              </p>
              <p
                className="text-xs mt-1"
                style={{ color: "var(--color-text-muted)" }}
              >
                Embedding: {health.llm.embedding_model}
              </p>
            </div>
            <div>
              <p
                className="text-xs mb-1"
                style={{ color: "var(--color-text-muted)" }}
              >
                Python
              </p>
              <p
                className="text-sm truncate"
                style={{ color: "var(--color-text-primary)" }}
              >
                {health.python.version.split(" ")[0]}
              </p>
              <p
                className="text-xs mt-1"
                style={{ color: "var(--color-text-muted)" }}
              >
                PID: {health.process.pid} · {health.platform}
              </p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
