/**
 * SaaS Admin Guard — protects /admin from non-admin users.
 * Backend `_require_admin` remains the authority; this is UX + route hardening.
 */
import { ReactNode } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { isAdmin } from "@looma/shared-core";
import { useSaasAuthStore } from "./authStore";

export function SaasAdminGuard({ children }: { children?: ReactNode }) {
  const { t } = useTranslation();
  const { token, user } = useSaasAuthStore();

  // Profile still loading after token restore
  if (token && !user) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "40vh",
          color: "var(--color-text-secondary)",
        }}
      >
        <p>{t("auth.validating")}</p>
      </div>
    );
  }

  if (!isAdmin(user?.role)) {
    return <Navigate to="/" replace />;
  }

  return children ? <>{children}</> : <Outlet />;
}
