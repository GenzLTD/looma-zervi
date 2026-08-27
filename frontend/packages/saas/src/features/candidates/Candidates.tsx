/**
 * Enterprise candidates list — import from PlanetX share codes.
 * Requires supporter+ (aligned with backend `@require_tier("supporter")`).
 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  CANDIDATE_LIMITS,
  createEnterpriseApi,
  hasMinTier,
  type Candidate,
  type EnterpriseProfile,
  type Tier,
} from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";
import { useSaasAuthStore } from "../auth/authStore";
import TierGatePanel from "../../brand/components/TierGatePanel";

function getEnterpriseApi() {
  return createEnterpriseApi(createSaasApiClient());
}

export default function Candidates() {
  const { t } = useTranslation();
  const { user } = useSaasAuthStore();
  const [enterprise, setEnterprise] = useState<EnterpriseProfile | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [shareCode, setShareCode] = useState("");
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [needsEnterprise, setNeedsEnterprise] = useState(false);
  const [tierBlocked, setTierBlocked] = useState(false);

  const canUseCandidates = hasMinTier(user?.tier, "supporter");

  const loadCandidates = useCallback(async () => {
    try {
      const list = await getEnterpriseApi().candidates();
      setCandidates(list.candidates ?? []);
      setListError(null);
    } catch (err) {
      setCandidates([]);
      if (err instanceof ApiError && err.status === 403) {
        setTierBlocked(true);
        setListError(null);
        return;
      }
      // Keep enterprise shell; never bounce back to the create panel.
      const detail =
        err instanceof ApiError
          ? (typeof err.body?.message === "string" && err.body.message) || err.message
          : null;
      setListError(detail || t("candidates.listLoadFailed"));
    }
  }, [t]);

  const loadData = useCallback(async () => {
    if (!canUseCandidates) {
      setLoading(false);
      setTierBlocked(true);
      return;
    }

    setLoading(true);
    setTierBlocked(false);
    setListError(null);
    const api = getEnterpriseApi();
    try {
      const profile = await api.profile();
      setEnterprise(profile);
      setNeedsEnterprise(false);
      await loadCandidates();
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNeedsEnterprise(true);
        setEnterprise(null);
        setCandidates([]);
      } else if (err instanceof ApiError && err.status === 403) {
        setTierBlocked(true);
        setEnterprise(null);
        setCandidates([]);
      } else {
        // Unknown/network errors must not force the create-enterprise panel.
        setMessage(t("candidates.loadEnterpriseFailed"));
      }
    } finally {
      setLoading(false);
    }
  }, [canUseCandidates, loadCandidates, t]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleCreateEnterprise = async () => {
    const name = user?.name || user?.email?.split("@")[0] || "我的企业";
    setCreating(true);
    setMessage(null);
    try {
      const created = await getEnterpriseApi().create({ name });
      setEnterprise({
        id: created.id,
        name: created.name,
        domain: created.domain,
        role: (created.role === "member" ? "member" : "admin") as EnterpriseProfile["role"],
      });
      setNeedsEnterprise(false);
      setMessage(t("candidates.createdSuccess"));
      await loadCandidates();
    } catch {
      setMessage(t("candidates.createFailed"));
    } finally {
      setCreating(false);
    }
  };

  const handleImport = async () => {
    const code = shareCode.trim().toUpperCase();
    if (!code) return;
    setImporting(true);
    setMessage(null);
    try {
      const result = await getEnterpriseApi().importFromShare(code);
      setMessage(result.imported === false ? "该候选人已在列表中" : "导入成功");
      setShareCode("");
      await loadData();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setTierBlocked(true);
        setMessage(null);
      } else {
        setMessage("导入失败：分享码无效或用户未完成测试");
      }
    } finally {
      setImporting(false);
    }
  };

  if (!canUseCandidates || tierBlocked) {
    return (
      <TierGatePanel
        title={t("candidates.title")}
        description={t("candidates.tierRequired")}
        minTier="supporter"
      />
    );
  }

  if (loading) {
    return <p style={{ color: "var(--color-text-muted)" }}>{t("candidates.loading")}</p>;
  }

  if (needsEnterprise) {
    return (
      <div className="max-w-xl">
        <h1 className="text-2xl font-bold mb-4" style={{ color: "var(--color-text-primary)" }}>
          {t("candidates.title")}
        </h1>
        <p className="text-sm mb-4" style={{ color: "var(--color-text-secondary)" }}>
          {t("candidates.needsEnterprise")}
        </p>
        <button
          onClick={() => void handleCreateEnterprise()}
          disabled={creating}
          className="px-4 py-2 rounded-lg text-sm text-white disabled:opacity-50"
          style={{ backgroundColor: "var(--color-primary)" }}
        >
          {creating ? t("candidates.creating") : t("candidates.createEnterprise")}
        </button>
        {message && <p className="text-sm mt-3" style={{ color: "var(--color-text-muted)" }}>{message}</p>}
      </div>
    );
  }

  const tier = (user?.tier ?? "free") as Tier;
  const limit =
    tier in CANDIDATE_LIMITS
      ? CANDIDATE_LIMITS[tier as keyof typeof CANDIDATE_LIMITS]
      : CANDIDATE_LIMITS.free;
  const atCap = limit !== null && candidates.length >= limit;

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--color-text-primary)" }}>
        {t("candidates.title")}
      </h1>
      <p className="text-sm mb-2" style={{ color: "var(--color-text-muted)" }}>
        {enterprise?.name} · {t("candidates.importHint")}
      </p>
      <p className="text-xs mb-6" style={{ color: atCap ? "var(--color-warning)" : "var(--color-text-muted)" }}>
        {t("candidates.capacity", {
          used: candidates.length,
          limit: limit === null ? t("tier.unlimited") : String(limit),
        })}
        {atCap ? ` · ${t("candidates.capacityFull")}` : ""}
      </p>

      <div
        className="flex gap-2 mb-6 p-4 rounded-xl"
        style={{ backgroundColor: "var(--color-bg-card)", boxShadow: "var(--shadow-sm)" }}
      >
        <input
          type="text"
          value={shareCode}
          onChange={(e) => setShareCode(e.target.value.toUpperCase())}
          placeholder={t("candidates.shareCodePlaceholder")}
          className="flex-1 px-3 py-2 rounded-lg text-sm border"
          style={{ borderColor: "var(--color-border)", backgroundColor: "var(--color-bg-surface)" }}
        />
        <button
          onClick={() => void handleImport()}
          disabled={importing || !shareCode.trim()}
          className="px-4 py-2 rounded-lg text-sm text-white disabled:opacity-50"
          style={{ backgroundColor: "var(--color-primary)" }}
        >
          {importing ? t("candidates.importing") : t("candidates.import")}
        </button>
      </div>

      {message && (
        <p className="text-sm mb-4" style={{ color: "var(--color-success)" }}>{message}</p>
      )}
      {listError && (
        <p className="text-sm mb-4" style={{ color: "var(--color-warning)" }}>{listError}</p>
      )}

      {candidates.length === 0 && !listError ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {t("candidates.empty")}
        </p>
      ) : (
        <ul className="space-y-3">
          {candidates.map((c) => {
            const profile = c.profile_data as { personality_type?: string; personality_detail?: { emoji?: string; name?: string } } | undefined;
            const emoji = profile?.personality_detail?.emoji ?? "🪐";
            const typeName = profile?.personality_detail?.name ?? profile?.personality_type ?? t("candidates.unknownType");
            return (
              <li key={c.id}>
                <Link
                  to={`/candidates/${c.id}`}
                  className="flex items-center gap-4 p-4 rounded-xl no-underline transition-shadow hover:shadow-md"
                  style={{ backgroundColor: "var(--color-bg-card)", boxShadow: "var(--shadow-sm)" }}
                >
                  <span className="text-3xl">{emoji}</span>
                  <div>
                    <p className="font-medium" style={{ color: "var(--color-text-primary)" }}>{c.name}</p>
                    <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                      {typeName} · {c.status ?? "new"}
                    </p>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
