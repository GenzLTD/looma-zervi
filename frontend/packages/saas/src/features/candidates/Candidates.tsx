/**
 * Enterprise candidates list — import from PlanetX share codes.
 * Requires supporter+ (aligned with backend `@require_tier("supporter")`).
 *
 * Pilot UI: Untitled UI TableCard layout + existing Saas* primitives + brand tokens
 * (`--color-*` / Tailwind `t-*`). No default Untitled purple skin.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
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
import BrandEmptyArt from "../../brand/components/BrandEmptyArt";
import TierGatePanel from "../../brand/components/TierGatePanel";
import SaasButton from "../../brand/ui/SaasButton";
import SaasDataTable from "../../brand/ui/SaasDataTable";
import SaasInput from "../../brand/ui/SaasInput";
import { SaasEmptyState, SaasErrorState } from "../../brand/ui/SaasEmptyState";
import type { DataTableColumn } from "../../brand/ui/types";

type CandidateRow = Candidate & Record<string, unknown>;

type ProfileSlice = {
  personality_type?: string;
  personality_detail?: { emoji?: string; name?: string };
};

function getEnterpriseApi() {
  return createEnterpriseApi(createSaasApiClient());
}

function getProfile(c: Candidate): ProfileSlice | undefined {
  return c.profile_data as ProfileSlice | undefined;
}

function CandidateAvatar({ name }: { name: string }) {
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <span
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold"
      style={{
        backgroundColor: "var(--color-primary-light)",
        color: "var(--color-primary)",
      }}
      aria-hidden
    >
      {initial}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize"
      style={{
        backgroundColor: "var(--color-primary-light)",
        color: "var(--color-primary)",
      }}
    >
      {status}
    </span>
  );
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
    const name = user?.name || user?.email?.split("@")[0] || "Workspace";
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
      setMessage(
        result.imported === false
          ? t("candidates.importAlreadyExists")
          : t("candidates.importSuccess"),
      );
      setShareCode("");
      await loadData();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setTierBlocked(true);
        setMessage(null);
      } else {
        setMessage(t("candidates.importFailed"));
      }
    } finally {
      setImporting(false);
    }
  };

  const columns = useMemo<DataTableColumn<CandidateRow>[]>(
    () => [
      {
        key: "name",
        title: t("candidates.colName"),
        render: (row) => {
          const profile = getProfile(row);
          const typeName =
            profile?.personality_detail?.name ??
            profile?.personality_type ??
            t("candidates.unknownType");
          return (
            <Link
              to={`/candidates/${row.id}`}
              className="flex items-center gap-3 no-underline"
              style={{ color: "inherit" }}
            >
              <CandidateAvatar name={row.name} />
              <span className="min-w-0">
                <span
                  className="block truncate text-sm font-medium"
                  style={{ color: "var(--color-text-primary)" }}
                >
                  {row.name}
                </span>
                <span
                  className="block truncate text-xs sm:hidden"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  {typeName}
                </span>
              </span>
            </Link>
          );
        },
      },
      {
        key: "type",
        title: t("candidates.colType"),
        render: (row) => {
          const profile = getProfile(row);
          return (
            profile?.personality_detail?.name ??
            profile?.personality_type ??
            t("candidates.unknownType")
          );
        },
      },
      {
        key: "status",
        title: t("candidates.colStatus"),
        width: 120,
        render: (row) => <StatusBadge status={row.status ?? "new"} />,
      },
      {
        key: "actions",
        title: t("candidates.colActions"),
        width: 100,
        align: "right",
        render: (row) => (
          <Link
            to={`/candidates/${row.id}`}
            className="text-sm font-medium no-underline"
            style={{ color: "var(--color-primary)" }}
          >
            {t("candidates.view")}
          </Link>
        ),
      },
    ],
    [t],
  );

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
    return (
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        {t("candidates.loading")}
      </p>
    );
  }

  if (needsEnterprise) {
    return (
      <div className="mx-auto w-full max-w-xl animate-fade-in">
        <h1 className="text-display mb-2" style={{ color: "var(--color-text-primary)" }}>
          {t("candidates.title")}
        </h1>
        <p className="mb-6 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {t("candidates.needsEnterprise")}
        </p>
        <SaasButton
          onClick={() => void handleCreateEnterprise()}
          loading={creating}
          disabled={creating}
        >
          {creating ? t("candidates.creating") : t("candidates.createEnterprise")}
        </SaasButton>
        {message && (
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            {message}
          </p>
        )}
      </div>
    );
  }

  const tier = (user?.tier ?? "free") as Tier;
  const limit =
    tier in CANDIDATE_LIMITS
      ? CANDIDATE_LIMITS[tier as keyof typeof CANDIDATE_LIMITS]
      : CANDIDATE_LIMITS.free;
  const atCap = limit !== null && candidates.length >= limit;
  const rows = candidates as CandidateRow[];

  return (
    <div className="mx-auto w-full max-w-5xl animate-fade-in">
      {/* Untitled-style page header */}
      <div className="mb-6 flex flex-col gap-1">
        <h1 className="text-display" style={{ color: "var(--color-text-primary)" }}>
          {t("candidates.title")}
        </h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {enterprise?.name ? `${enterprise.name} · ` : ""}
          {t("candidates.importHint")}
        </p>
        <p
          className="text-xs"
          style={{ color: atCap ? "var(--color-warning)" : "var(--color-text-muted)" }}
        >
          {t("candidates.capacity", {
            used: candidates.length,
            limit: limit === null ? t("tier.unlimited") : String(limit),
          })}
          {atCap ? ` · ${t("candidates.capacityFull")}` : ""}
        </p>
      </div>

      {/* Import toolbar */}
      <div
        className="mb-6 flex flex-col gap-3 rounded-xl border p-4 shadow-sm sm:flex-row sm:items-end"
        style={{
          backgroundColor: "var(--color-bg-card)",
          borderColor: "var(--color-border)",
        }}
      >
        <div className="min-w-0 flex-1">
          <SaasInput
            value={shareCode}
            onChange={(v) => setShareCode(v.toUpperCase())}
            placeholder={t("candidates.shareCodePlaceholder")}
            label={t("candidates.shareCodeLabel")}
            disabled={importing || atCap}
            onKeyDown={(e) => {
              if (e.key === "Enter") void handleImport();
            }}
          />
        </div>
        <SaasButton
          onClick={() => void handleImport()}
          loading={importing}
          disabled={importing || !shareCode.trim() || atCap}
        >
          {importing ? t("candidates.importing") : t("candidates.import")}
        </SaasButton>
      </div>

      {message && (
        <p className="mb-4 text-sm" style={{ color: "var(--color-success)" }}>
          {message}
        </p>
      )}

      {/* TableCard shell (Untitled pattern) */}
      <div
        className="overflow-hidden rounded-xl border shadow-sm"
        style={{
          backgroundColor: "var(--color-bg-card)",
          borderColor: "var(--color-border)",
        }}
      >
        <div
          className="flex flex-col gap-1 border-b px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
          style={{ borderColor: "var(--color-border)" }}
        >
          <div>
            <h2 className="text-base font-semibold" style={{ color: "var(--color-text-primary)" }}>
              {t("candidates.tableTitle")}
            </h2>
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              {t("candidates.tableCount", { count: candidates.length })}
            </p>
          </div>
        </div>

        {listError ? (
          <SaasErrorState
            title={t("candidates.listLoadFailed")}
            message={listError}
            onRetry={() => void loadCandidates()}
          />
        ) : candidates.length === 0 ? (
          <SaasEmptyState
            icon={<BrandEmptyArt variant="candidates" size={140} />}
            title={t("candidates.emptyTitle")}
            description={t("candidates.empty")}
          />
        ) : (
          <SaasDataTable<CandidateRow>
            columns={columns}
            data={rows}
            rowKey="id"
            compact
            emptyText={t("candidates.empty")}
          />
        )}
      </div>
    </div>
  );
}
