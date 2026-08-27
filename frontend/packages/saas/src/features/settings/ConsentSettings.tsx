/**
 * ConsentSettings - PIPL consent status & revoke (T-space SaaS).
 * Three primary tiers for the jobseeker path + other scopes.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CONSENT_PACKAGES,
  CONSENT_PRIMARY_TIERS,
  CONSENT_SCOPE_DESCRIPTIONS,
  CONSENT_SCOPE_LABELS,
  createComplianceApi,
  type ConsentScope,
  type PrimaryConsentScope,
} from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";

const OTHER_SCOPES: ConsentScope[] = [
  "ask_rag",
  "profile_share",
  "mbti_analyze",
  "navigator_memory",
];

const TIER_HINT: Record<PrimaryConsentScope, string> = {
  jobseeker_core: "第 1 层 · 求职主路径必选",
  credit_query: "第 2 层 · 查企业风险时单独同意",
  report_share: "第 3 层 · 对外分享时单独同意",
};

function ScopeCard({
  scope,
  granted,
  revoking,
  onRevoke,
  hint,
  covered,
}: {
  scope: ConsentScope;
  granted: boolean;
  revoking: boolean;
  onRevoke: () => void;
  hint?: string;
  covered?: ConsentScope[];
}) {
  return (
    <div
      className="rounded-lg p-4 flex items-start justify-between gap-4"
      style={{
        backgroundColor: "var(--color-bg-card)",
        boxShadow: "var(--shadow-sm)",
        border: "1px solid #f0f0f0",
      }}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className="font-medium text-sm" style={{ color: "var(--color-text-primary)" }}>
            {CONSENT_SCOPE_LABELS[scope]}
          </span>
          <span
            className="text-xs px-2 py-0.5 rounded"
            style={{
              backgroundColor: granted ? "#e8f5e9" : "#f5f5f5",
              color: granted ? "var(--color-success)" : "var(--color-text-muted)",
            }}
          >
            {granted ? "已授权" : "未授权"}
          </span>
          {hint && (
            <span className="text-xs" style={{ color: "var(--color-primary)" }}>
              {hint}
            </span>
          )}
        </div>
        <p className="text-xs leading-relaxed" style={{ color: "var(--color-text-muted)" }}>
          {CONSENT_SCOPE_DESCRIPTIONS[scope]}
        </p>
        {covered && covered.length > 0 && (
          <p className="text-xs mt-2" style={{ color: "var(--color-text-muted)" }}>
            包含：{covered.map((s) => CONSENT_SCOPE_LABELS[s]).join("、")}
          </p>
        )}
      </div>
      {granted && (
        <button
          type="button"
          onClick={onRevoke}
          disabled={revoking}
          className="shrink-0 text-xs px-3 py-1.5 rounded border cursor-pointer bg-transparent transition-colors"
          style={{
            borderColor: "#e0e0e0",
            color: "var(--color-danger)",
            opacity: revoking ? 0.5 : 1,
          }}
        >
          {revoking ? "撤回中…" : "撤回授权"}
        </button>
      )}
    </div>
  );
}

export default function ConsentSettings() {
  const api = useMemo(() => createSaasApiClient(), []);
  const complianceApi = useMemo(() => createComplianceApi(api), [api]);
  const [status, setStatus] = useState<Partial<Record<ConsentScope, boolean>>>({});
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<ConsentScope | null>(null);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await complianceApi.status();
      setStatus(res.status);
    } catch {
      setMsg("加载授权状态失败，请确认已登录");
    } finally {
      setLoading(false);
    }
  }, [complianceApi]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const handleRevoke = async (scope: ConsentScope) => {
    if (!status[scope]) return;
    const label = CONSENT_SCOPE_LABELS[scope];
    if (!window.confirm(`确定撤回「${label}」授权？撤回后相关功能需重新同意。`)) return;

    setRevoking(scope);
    setMsg(null);
    try {
      await complianceApi.revoke(scope);
      setMsg(`已撤回：${label}`);
      await loadStatus();
    } catch {
      setMsg(`撤回失败：${label}`);
    } finally {
      setRevoking(null);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--color-text-primary)" }}>
        隐私授权管理
      </h1>
      <p className="text-sm mb-6" style={{ color: "var(--color-text-muted)" }}>
        求职主路径按三层授权：核心处理 → 企业风险 → 对外分享。依据《个人信息保护法》，您可随时查看与撤回；撤回后再次使用相关功能时将重新征求同意。
      </p>

      {msg && (
        <div
          className="mb-4 px-4 py-2 rounded text-sm"
          style={{ backgroundColor: "var(--color-bg-surface)", color: "var(--color-text-secondary)" }}
        >
          {msg}
        </div>
      )}

      {loading ? (
        <p style={{ color: "var(--color-text-muted)" }}>加载中…</p>
      ) : (
        <>
          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--color-text-primary)" }}>
            求职三层授权
          </h2>
          <div className="space-y-3 mb-8">
            {CONSENT_PRIMARY_TIERS.map((scope) => (
              <ScopeCard
                key={scope}
                scope={scope}
                granted={Boolean(status[scope])}
                revoking={revoking === scope}
                onRevoke={() => void handleRevoke(scope)}
                hint={TIER_HINT[scope]}
                covered={CONSENT_PACKAGES[scope]}
              />
            ))}
          </div>

          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--color-text-primary)" }}>
            其他能力授权
          </h2>
          <div className="space-y-3">
            {OTHER_SCOPES.map((scope) => (
              <ScopeCard
                key={scope}
                scope={scope}
                granted={Boolean(status[scope])}
                revoking={revoking === scope}
                onRevoke={() => void handleRevoke(scope)}
              />
            ))}
          </div>
        </>
      )}

      <button
        type="button"
        onClick={() => void loadStatus()}
        className="mt-6 text-sm bg-transparent border-none cursor-pointer"
        style={{ color: "var(--color-primary)" }}
      >
        刷新状态
      </button>
    </div>
  );
}
