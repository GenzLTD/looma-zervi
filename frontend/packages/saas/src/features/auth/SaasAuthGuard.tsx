/**
 * SaaS Auth Guard - protects routes that require authentication.
 * Owner: szbenyx
 *
 * Checks for looma JWT in the auth store.
 * If not authenticated, redirects to /login.
 * On mount with a stored token, fetches profile to validate.
 */
import { ReactNode, useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useSaasAuthStore } from "./authStore";

export function SaasAuthGuard({ children }: { children?: ReactNode }) {
  const { t } = useTranslation();
  const { token, isAuthenticated, fetchProfile } = useSaasAuthStore();
  const location = useLocation();
  const [validating, setValidating] = useState(false);

  useEffect(() => {
    if (token && !isAuthenticated && !validating) {
      setValidating(true);
      fetchProfile()
        .catch(() => {
          useSaasAuthStore.getState().logout();
        })
        .finally(() => setValidating(false));
    }
  }, [token, isAuthenticated, fetchProfile, validating]);

  // Show loading while validating stored token
  if (token && !isAuthenticated && validating) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          color: "var(--color-text-secondary)",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <p>{t("auth.validating")}</p>
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children ? <>{children}</> : <Outlet />;
}
