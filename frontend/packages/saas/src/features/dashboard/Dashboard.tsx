/**
 * Dashboard v3 — Figma 对齐版 (2026-08-09)
 * ============================================
 * v3 新增：
 *   1. 候选人能力雷达图 — 多维度 SVG 可视化
 *   2. 候选人详情卡 — 含匹配度 + 标签 + 操作按钮
 *   3. Top 候选人对比 — 快速浏览 top 3
 *
 * v2 已有（保留）：
 *   - 候选人 Pipeline 工作台
 *   - KPI 趋势卡
 *   - 最近活动时间线
 *
 * 原功能不变：健康状态/配额/快捷操作/快速提问
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { isPaidTier } from "@looma/shared-core";
import { useSaasAuthStore } from "../auth/authStore";
import { useBrand } from "../../brand/useBrand";
import BrandMark from "../../brand/components/BrandMark";
import CandidateRadarChart from "./CandidateRadarChart";
import CandidateDetailCard, { type CandidateDetail } from "./CandidateDetailCard";
import SaasIcon, { type SaasIconName } from "../../brand/ui/SaasIcon";

// ── Types ──────────────────────────────────────────────────────
interface HealthStatus {
  status: "healthy" | "degraded";
  version: string;
  uptime_seconds: number;
  llm_provider?: string;
  embedding_model?: string;
  vector_store_size?: number;
}

interface PipelineStage {
  key: string;
  label: string;
  count: number;
}

interface KpiCard {
  label: string;
  value: string;
  trend: "up" | "down" | "flat";
  trendLabel: string;
  color: string;
}

// ── Mock data (Figma 视觉对齐，后端就绪后可替换) ──────────────
const MOCK_PIPELINE: PipelineStage[] = [
  { key: "new", label: "新入库", count: 12 },
  { key: "review", label: "AI 初筛", count: 7 },
  { key: "interview", label: "面试中", count: 4 },
  { key: "offer", label: "Offer", count: 2 },
  { key: "rejected", label: "已归档", count: 3 },
];

const MOCK_KPIS: KpiCard[] = [
  { label: "本周新增候选人", value: "28", trend: "up", trendLabel: "+12%", color: "var(--tsp-chart-green)" },
  { label: "AI 问答处理", value: "146", trend: "up", trendLabel: "+8%", color: "var(--tsp-chart-blue)" },
  { label: "平均响应时间", value: "2.4s", trend: "down", trendLabel: "-0.3s", color: "var(--tsp-chart-purple)" },
];

const MOCK_ACTIVITIES: { time: string; text: string }[] = [
  { time: "今天 14:22", text: "候选人 张明 通过 AI 初筛 → 待面试" },
  { time: "今天 10:05", text: "新上传 3 份简历，AI 分析完成" },
  { time: "昨天 18:30", text: "Job #42 截止，共匹配 17 位候选人" },
  { time: "昨天 09:15", text: "套餐用量：今日已用 18/50 次" },
];

// ── P1 新增: Mock 候选人可视化数据 ────────────────────────────
const MOCK_CANDIDATES: CandidateDetail[] = [
  {
    id: "c-1",
    name: "张明",
    role: "高级前端工程师 · 6年",
    matchScore: 92,
    stage: "interview",
    tags: ["React", "TypeScript", "Node.js", "GraphQL", "微前端"],
    summary: "曾在阿里巴巴担任 P7 前端架构师，主导过双 11 大促前端方案。技术栈匹配度极高，沟通能力强，期望薪资在预算范围内。",
    dimensions: [
      { key: "tech", label: "技术能力", score: 94 },
      { key: "expertise", label: "领域经验", score: 88 },
      { key: "culture", label: "文化匹配", score: 90 },
      { key: "growth", label: "成长潜力", score: 85 },
      { key: "comms", label: "沟通表达", score: 92 },
      { key: "stability", label: "稳定性", score: 78 },
    ],
  },
  {
    id: "c-2",
    name: "李悦",
    role: "产品经理 · 4年",
    matchScore: 85,
    stage: "review",
    tags: ["B端产品", "数据驱动", "用户增长", "SaaS"],
    summary: "在腾讯担任产品经理，负责企业协同产品从 0 到 1。擅长数据分析与用户研究，有丰富的跨部门协作经验。",
    dimensions: [
      { key: "tech", label: "技术理解", score: 72 },
      { key: "expertise", label: "领域经验", score: 90 },
      { key: "culture", label: "文化匹配", score: 85 },
      { key: "growth", label: "成长潜力", score: 82 },
      { key: "comms", label: "沟通表达", score: 95 },
      { key: "stability", label: "稳定性", score: 70 },
    ],
  },
  {
    id: "c-3",
    name: "王浩",
    role: "后端架构师 · 8年",
    matchScore: 78,
    stage: "new",
    tags: ["Go", "K8s", "分布式", "高并发", "Rust"],
    summary: "字节跳动基础设施团队成员，参与过抖音春晚红包项目。分布式系统能力强，对新技术接纳度高，团队管理经验稍弱。",
    dimensions: [
      { key: "tech", label: "技术能力", score: 96 },
      { key: "expertise", label: "领域经验", score: 80 },
      { key: "culture", label: "文化匹配", score: 65 },
      { key: "growth", label: "成长潜力", score: 75 },
      { key: "comms", label: "沟通表达", score: 62 },
      { key: "stability", label: "稳定性", score: 88 },
    ],
  },
];

// ── Utils ──────────────────────────────────────────────────────
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

// ── Sub-components ─────────────────────────────────────────────

/** 候选人 Pipeline 横条 */
function CandidatePipeline({ stages }: { stages: PipelineStage[] }) {
  const total = stages.reduce((s, c) => s + c.count, 0);
  const keyColor: Record<string, string> = {
    new: "var(--tsp-pipeline-new)",
    review: "var(--tsp-pipeline-review)",
    interview: "var(--tsp-pipeline-interview)",
    offer: "var(--tsp-pipeline-offer)",
    rejected: "var(--tsp-pipeline-rejected)",
  };

  return (
    <div
      style={{
        padding: "20px",
        background: "var(--tsp-color-surface-card)",
        borderRadius: "var(--lo-radius-lg)",
        border: "1px solid var(--tsp-color-border-subtle)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div>
          <h3 style={{ fontSize: "var(--lo-font-size-sm)", fontWeight: 600, color: "var(--tsp-color-text-primary)", margin: 0 }}>
            候选人 Pipeline
          </h3>
          <span style={{ fontSize: 11, color: "var(--tsp-color-text-tertiary)" }}>
            Mock · 共 {total} 人
          </span>
        </div>
      </div>

      {/* Pipeline bar */}
      <div style={{
        display: "flex",
        borderRadius: "var(--lo-radius-sm)",
        overflow: "hidden",
        height: 10,
        marginBottom: 14,
      }}>
        {stages.map((s) => (
          <div
            key={s.key}
            title={`${s.label}: ${s.count}`}
            style={{
              flex: s.count || 0.5,
              background: keyColor[s.key] ?? "var(--tsp-color-border-default)",
              transition: "flex 0.4s ease",
            }}
          />
        ))}
      </div>

      {/* Stage labels + counts */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {stages.map((s) => (
          <div
            key={s.key}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              color: "var(--tsp-color-text-secondary)",
            }}
          >
            <span style={{
              width: 8, height: 8, borderRadius: "50%",
              background: keyColor[s.key] ?? "var(--tsp-color-border-default)",
              flexShrink: 0,
            }} />
            {s.label}
            <strong style={{ color: "var(--tsp-color-text-primary)" }}>{s.count}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

/** KPI 趋势卡 */
function KpiCards({ kpis }: { kpis: KpiCard[] }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
      {kpis.map((kpi) => (
        <div
          key={kpi.label}
          style={{
            padding: "16px",
            background: "var(--tsp-color-surface-card)",
            borderRadius: "var(--lo-radius-md)",
            border: "1px solid var(--tsp-color-border-subtle)",
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          <div style={{ fontSize: 11, color: "var(--tsp-color-text-tertiary)" }}>{kpi.label}</div>
          <div style={{ fontSize: "var(--lo-font-size-2xl)", fontWeight: 800, color: kpi.color }}>
            {kpi.value}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ fontSize: 16, lineHeight: 1 }}>
              {kpi.trend === "up" ? <SaasIcon name="trendUp" size={14} color="var(--tsp-color-success)" /> : kpi.trend === "down" ? <SaasIcon name="trendDown" size={14} color="var(--tsp-color-danger)" /> : "→"}
            </span>
            <span style={{
              fontSize: 11,
              color: kpi.trend === "up"
                ? "var(--tsp-color-success)"
                : kpi.trend === "down"
                  ? "var(--tsp-color-danger)"
                  : "var(--tsp-color-text-tertiary)",
            }}>
              {kpi.trendLabel}
            </span>
            <span style={{ fontSize: 10, color: "var(--tsp-color-text-tertiary)" }}>vs. 上周</span>
          </div>
        </div>
      ))}
    </div>
  );
}

/** 活动时间线 */
function ActivityTimeline({ activities }: { activities: { time: string; text: string }[] }) {
  return (
    <div
      style={{
        padding: "20px",
        background: "var(--tsp-color-surface-card)",
        borderRadius: "var(--lo-radius-lg)",
        border: "1px solid var(--tsp-color-border-subtle)",
      }}
    >
      <div style={{ marginBottom: 14 }}>
        <h3 style={{ fontSize: "var(--lo-font-size-sm)", fontWeight: 600, color: "var(--tsp-color-text-primary)", margin: 0 }}>
          最近动态
        </h3>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
        {activities.map((a, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              gap: 12,
              padding: "10px 0",
              borderBottom: i < activities.length - 1 ? "1px solid var(--tsp-color-border-subtle)" : "none",
            }}
          >
            <div style={{
              width: 32, flexShrink: 0, fontSize: 10,
              color: "var(--tsp-color-text-tertiary)", textAlign: "right",
              paddingTop: 2, lineHeight: 1.4,
            }}>
              {a.time}
            </div>
            <div style={{
              flexShrink: 0, width: 2,
              background: i < activities.length - 1 ? "var(--tsp-color-border-subtle)" : "transparent",
              position: "relative",
              borderRadius: 1,
            }}>
              <div style={{
                position: "absolute", top: 6, left: -3, width: 8, height: 8,
                borderRadius: "50%", background: "var(--tsp-brand-primary)",
              }} />
            </div>
            <div style={{ fontSize: 13, color: "var(--tsp-color-text-secondary)", lineHeight: 1.5 }}>
              {a.text}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────
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
      { icon: "robot" as SaasIconName, title: t("dashboard.featureAiTitle"), desc: t("dashboard.featureAiDesc") },
      { icon: "resume" as SaasIconName, title: t("dashboard.featureResumeTitle"), desc: t("dashboard.featureResumeDesc") },
      { icon: "chart" as SaasIconName, title: t("dashboard.featureReportTitle"), desc: t("dashboard.featureReportDesc") },
    ],
    [t],
  );

  useEffect(() => {
    if (isAuthenticated) void fetchQuota();
  }, [isAuthenticated, fetchQuota]);

  useEffect(() => {
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

  // ── 未登录引导页 — Untitled 骨架 + TSpace 品牌层 ────────────
  if (!isAuthenticated) {
    return (
      <div
        className="relative mx-auto max-w-3xl text-center animate-fade-in"
        style={{ paddingTop: "3rem", paddingBottom: "2rem" }}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 -top-8 mx-auto h-56 max-w-xl rounded-full opacity-70"
          style={{
            background:
              "radial-gradient(ellipse at center, var(--color-primary-light) 0%, transparent 70%)",
          }}
        />

        <div className="relative flex flex-col items-center">
          <BrandMark size={56} title={brand.name} className="mb-4" />
          <h1
            className="text-3xl font-bold mb-2 tracking-tight"
            style={{ color: "var(--color-text-primary)" }}
          >
            {brand.name}
          </h1>
          <p className="text-lg mb-8 max-w-md" style={{ color: "var(--color-text-secondary)" }}>
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

          <div className="grid w-full grid-cols-1 md:grid-cols-3 gap-4 mb-10 text-left">
            {featureCards.map((item) => (
              <div
                key={item.title}
                className="rounded-xl border p-5"
                style={{
                  backgroundColor: "var(--color-bg-card)",
                  borderColor: "var(--color-border)",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                <div style={{ marginBottom: 6 }}>
                  <SaasIcon name={item.icon} size={28} color="var(--color-primary)" />
                </div>
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

          <p
            className="mt-6 inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs"
            style={{
              color: "var(--color-text-secondary)",
              borderColor: "var(--color-border)",
              backgroundColor: "var(--color-bg-surface)",
            }}
          >
            <SaasIcon name="candidates" size={14} color="var(--color-primary)" />
            {t("dashboard.welcomeHint")}
          </p>
        </div>
      </div>
    );
  }

  // ── 已登录工作台 ───────────────────────────────────────────
  return (
    <div className="max-w-5xl mx-auto" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Header — brand mark + product line */}
      <div className="flex items-start gap-3">
        <BrandMark size={40} title={brand.name} />
        <div>
          <h1 style={{
            fontSize: "var(--lo-font-size-2xl)",
            fontWeight: 700,
            color: "var(--tsp-color-text-primary, var(--color-text-primary))",
            margin: 0,
          }}>
            {brand.name}
          </h1>
          <p style={{
            fontSize: "var(--lo-font-size-sm)",
            color: "var(--tsp-color-text-secondary, var(--color-text-secondary))",
            margin: "4px 0 0",
          }}>
            {t("dashboard.welcomeBack", { name: user?.name || user?.email || "" })}
          </p>
          <p style={{
            fontSize: 12,
            color: "var(--color-text-muted)",
            margin: "2px 0 0",
          }}>
            {brand.slogan}
          </p>
        </div>
      </div>

      {/* === NEW: KPI 趋势卡 === */}
      <KpiCards kpis={MOCK_KPIS} />

      {/* === NEW: 候选人 Pipeline === */}
      <CandidatePipeline stages={MOCK_PIPELINE} />

      {/* === P1 NEW: Top 候选人能力映射 === */}
      <div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 12,
        }}>
          <h3 style={{
            fontSize: 'var(--lo-font-size-sm)',
            fontWeight: 600,
            color: 'var(--tsp-color-text-primary)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}>
            <SaasIcon name="trophy" size={18} color="var(--tsp-chart-green)" />
            Top 候选人能力映射
          </h3>
          <span style={{ fontSize: 11, color: 'var(--tsp-color-text-tertiary)' }}>
            共 {MOCK_CANDIDATES.length} 位 · 按匹配度排序
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {MOCK_CANDIDATES.map((candidate) => (
            <CandidateDetailCard
              key={candidate.id}
              candidate={candidate}
              onAction={(action, c) => {
                // TODO: 接入真实路由
                console.log(`Action: ${action} for candidate ${c.id}`);
              }}
            />
          ))}
        </div>
      </div>

      {/* === P1 NEW: 能力对比雷达图（并排） === */}
      <div
        style={{
          padding: '20px',
          background: 'var(--tsp-color-surface-card)',
          borderRadius: 'var(--lo-radius-lg)',
          border: '1px solid var(--tsp-color-border-subtle)',
        }}
      >
        <h3 style={{
          fontSize: 'var(--lo-font-size-sm)',
          fontWeight: 600,
          color: 'var(--tsp-color-text-primary)',
          margin: '0 0 16px',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}>
          <SaasIcon name="chart" size={18} color="var(--tsp-chart-blue)" />
          候选人能力对比
        </h3>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 16,
        }}>
          {MOCK_CANDIDATES.map((candidate) => (
            <CandidateRadarChart
              key={candidate.id}
              dimensions={candidate.dimensions}
              size={200}
              candidateName={candidate.name}
            />
          ))}
        </div>
        <div style={{
          marginTop: 16,
          paddingTop: 14,
          borderTop: '1px solid var(--tsp-color-border-subtle)',
          fontSize: 11,
          color: 'var(--tsp-color-text-tertiary)',
          textAlign: 'center',
        }}>
          雷达图基于 AI 多维度评估模型，每 24 小时自动更新
        </div>
      </div>

      {/* === 原有: 系统健康 / 配额 / 快捷操作 === */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Health */}
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

        {/* Quota */}
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

        {/* Quick Actions */}
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

      {/* === NEW: 活动时间线 === */}
      <ActivityTimeline activities={MOCK_ACTIVITIES} />

      {/* === 原有: 快速提问 === */}
      <div
        className="rounded-lg p-5"
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
              borderColor: "var(--tsp-color-border-subtle)",
              color: "var(--tsp-color-text-primary)",
              background: "var(--tsp-color-surface-root)",
            }}
            onKeyDown={handleQuickQuery}
            onFocus={(e) => {
              e.target.style.borderColor = "var(--tsp-brand-primary)";
            }}
            onBlur={(e) => {
              e.target.style.borderColor = "var(--tsp-color-border-subtle)";
            }}
          />
          <button
            type="button"
            onClick={submitQuickQuery}
            disabled={!quickQuery.trim()}
            className="px-5 py-2.5 text-sm rounded-lg text-white cursor-pointer border-none transition-colors disabled:opacity-50"
            style={{
              backgroundColor: "var(--tsp-brand-primary)",
              height: "var(--tsp-btn-height)",
              borderRadius: "var(--tsp-btn-radius)",
              fontWeight: "var(--tsp-btn-font-weight)",
            }}
          >
            {t("dashboard.ask")}
          </button>
        </div>
      </div>

      {/* === 原有: Uptime === */}
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
