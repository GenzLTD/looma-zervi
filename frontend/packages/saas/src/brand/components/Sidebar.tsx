/**
 * Sidebar - SaaS navigation shell.
 * Owner: szbenyx
 *
 * Pure CSS + HTML (no tdesign-react / tdesign-icons-react).
 * Uses @looma/shared-core for brand config and auth store.
 * Quota format aligned with backend: { tier, records }.
 *
 * Tier/role differentiation:
 * - admin: show Admin nav
 * - free: show lock badge on supporter+ features (still navigable → upgrade CTA)
 *
 * Style: 浅色 B 端 SaaS 侧边栏，白色底 + 深蓝文字 + 专业蓝激活态
 * Hidden on mobile (<md) — replaced by MobileDrawer.
 */
import { useMemo } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { hasMinTier, isAdmin, isPaidTier, type Tier } from "@looma/shared-core";
import { useSaasAuthStore } from "../../features/auth/authStore";
import { useBrand } from "../useBrand";
import { IS_OVERSEAS } from "../../config/region";

interface NavItem {
  path: string;
  labelKey: string;
  icon: string;
  overseasHidden?: boolean;
  mainlandHidden?: boolean;
  /** Minimum tier to unlock; free users see a lock badge. */
  minTier?: Tier;
}

function tierLabel(tier: string, t: (key: string) => string) {
  if (tier === "free") return t("tier.free");
  if (tier === "supporter") return t("tier.supporter");
  return t("tier.pro");
}

export default function Sidebar() {
  const { t } = useTranslation();
  const brand = useBrand();
  const { user, quota, logout } = useSaasAuthStore();
  const navigate = useNavigate();
  const userTier = user?.tier ?? quota?.tier ?? "free";

  const navItems: NavItem[] = useMemo(() => {
    const items: NavItem[] = [
      { path: "/", labelKey: "nav.dashboard", icon: "◉" },
      { path: "/trust", labelKey: "nav.trust", icon: "✦" },
      { path: "/query", labelKey: "nav.query", icon: "◈" },
      { path: "/poetry", labelKey: "nav.poetry", icon: "◇" },
      { path: "/poetry/challenge", labelKey: "nav.challenge", icon: "✧", mainlandHidden: true },
      {
        path: "/candidates",
        labelKey: IS_OVERSEAS ? "nav.profile" : "nav.candidates",
        icon: "◎",
        minTier: "supporter",
      },
      { path: "/jobs", labelKey: IS_OVERSEAS ? "nav.jobsOverseas" : "nav.jobs", icon: "◈" },
      { path: "/resume", labelKey: "nav.resume", icon: "◈" },
      { path: "/reports", labelKey: "nav.reports", icon: "◆" },
      { path: "/settings/consent", labelKey: "nav.consent", icon: "🛡" },
    ];
    if (isAdmin(user?.role)) {
      items.push({ path: "/admin", labelKey: "nav.admin", icon: "⚙" });
    }
    return items.filter(
      (item) =>
        !(IS_OVERSEAS && item.overseasHidden) &&
        !(!IS_OVERSEAS && item.mainlandHidden),
    );
  }, [user?.role]);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const askRecord = quota?.records?.find((r) => r.resource === "ask");
  const paid = isPaidTier(userTier);
  const usagePercent = askRecord && askRecord.daily_limit > 0
    ? Math.round((askRecord.used / askRecord.daily_limit) * 100)
    : 0;
  const remaining = askRecord
    ? Math.max(askRecord.daily_limit - askRecord.used, 0)
    : null;

  return (
    <aside
      className="hidden md:flex fixed left-0 top-0 bottom-0 flex-col z-50 border-r border-[var(--color-border)]"
      style={{
        width: "var(--sidebar-width)",
        backgroundColor: "var(--color-bg-sidebar)",
        color: "var(--color-text-sidebar)",
      }}
    >
      <div className="px-5 py-5 border-b border-[var(--color-border)]">
        <h1
          className="text-lg font-bold tracking-wide"
          style={{ color: "var(--color-text-primary)" }}
        >
          {brand.name}
        </h1>
        <p
          className="text-xs mt-1"
          style={{ color: "var(--color-text-sidebar-muted)" }}
        >
          {brand.slogan}
        </p>
      </div>

      <nav className="flex-1 py-4 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const locked = Boolean(
            item.minTier && user && !hasMinTier(userTier, item.minTier),
          );
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 text-sm transition-colors no-underline
                ${locked ? "opacity-55" : ""}
                ${isActive
                  ? "border-r-2 border-r-[var(--color-primary)]"
                  : "hover:bg-[var(--color-bg-sidebar-hover)]"
                }`
              }
              style={({ isActive }) => ({
                color: isActive
                  ? "var(--color-text-sidebar-active)"
                  : "var(--color-text-sidebar)",
                backgroundColor: isActive
                  ? "var(--color-bg-sidebar-active)"
                  : "transparent",
              })}
            >
              <span className="text-base">{item.icon}</span>
              <span className="flex-1 truncate">{t(item.labelKey)}</span>
              {locked && (
                <span
                  className="text-[10px] px-1.5 py-0.5 rounded border shrink-0"
                  style={{
                    borderColor: "var(--color-border)",
                    color: "var(--color-text-sidebar-muted)",
                  }}
                  title={t("tier.lockHint")}
                >
                  {t("tier.lockBadge")}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      {user && quota && (
        <div className="px-5 py-3 border-t border-[var(--color-border)]">
          <div className="flex items-center justify-between mb-2">
            <span
              className="text-xs"
              style={{ color: "var(--color-text-sidebar-muted)" }}
            >
              {t("dashboard.todayQuota")}
            </span>
            <span
              className="text-xs"
              style={{ color: "var(--color-text-sidebar)" }}
            >
              {paid
                ? t("tier.unlimited")
                : remaining !== null && askRecord
                  ? `${remaining}/${askRecord.daily_limit}`
                  : "—"}
            </span>
          </div>
          {!paid && (
            <div
              className="h-1.5 rounded-full overflow-hidden"
              style={{ backgroundColor: "var(--color-bg-sidebar-hover)" }}
            >
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{
                  width: `${Math.min(usagePercent, 100)}%`,
                  backgroundColor: usagePercent >= 80
                    ? "var(--color-warning, #f59e0b)"
                    : "var(--color-primary)",
                }}
              />
            </div>
          )}
          {!paid && (
            <p
              className="text-[10px] mt-1.5 leading-snug"
              style={{ color: "var(--color-text-sidebar-muted)" }}
            >
              {t("dashboard.quotaRulesHint")}
            </p>
          )}
          {!paid && usagePercent >= 80 && (
            <p
              className="text-[10px] mt-1.5"
              style={{ color: "var(--color-warning, #f59e0b)" }}
            >
              {t("tier.quotaNearLimit")}
            </p>
          )}
          <div className="mt-1.5 flex items-center justify-between">
            <span
              className="text-xs"
              style={{ color: "var(--color-text-sidebar-muted)" }}
            >
              {tierLabel(quota.tier, t)}
            </span>
            <NavLink
              to="/pricing"
              className="text-xs transition-colors no-underline hover:opacity-80"
              style={{ color: "var(--color-text-link)" }}
            >
              {paid ? t("dashboard.viewPlans") : t("dashboard.upgrade")}
            </NavLink>
          </div>
        </div>
      )}

      {user && (
        <div className="px-5 py-3 border-t border-[var(--color-border)] flex items-center justify-between">
          <div className="min-w-0 flex-1">
            <p
              className="text-sm truncate"
              style={{ color: "var(--color-text-primary)" }}
            >
              {user.name || user.email}
            </p>
            <p
              className="text-xs truncate"
              style={{ color: "var(--color-text-sidebar-muted)" }}
            >
              {user.email}
            </p>
          </div>
          <button
            onClick={handleLogout}
            className="ml-3 transition-colors bg-transparent border-none cursor-pointer text-lg leading-none p-1 hover:opacity-80"
            style={{ color: "var(--color-text-sidebar-muted)" }}
            title={t("auth.logout")}
          >
            ⏻
          </button>
        </div>
      )}
    </aside>
  );
}