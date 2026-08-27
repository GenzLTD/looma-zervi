/**
 * Login - SaaS authentication page.
 * Owner: szbenyx
 */
import { useState } from "react";
import { useNavigate, Navigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useSaasAuthStore } from "./authStore";
import { useBrand } from "../../brand/useBrand";
import { LanguageSwitcher } from "../../components/LanguageSwitcher";
import SaasButton from "../../brand/ui/SaasButton";
import SaasInput from "../../brand/ui/SaasInput";

export default function Login() {
  const { t } = useTranslation();
  const brand = useBrand();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const { login, isAuthenticated } = useSaasAuthStore();
  const navigate = useNavigate();

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      setErrorMsg(t("auth.emailPasswordRequired"));
      return;
    }

    setLoading(true);
    setErrorMsg("");
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      const msg = (err as { detail?: string })?.detail ?? t("auth.loginFailed");
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-blue-50">
      <div
        className="w-[400px] rounded-xl p-8"
        style={{
          backgroundColor: "var(--color-bg-card)",
          boxShadow: "var(--shadow-lg)",
        }}
      >
        <div className="flex justify-end mb-2">
          <LanguageSwitcher />
        </div>

        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold" style={{ color: "var(--color-primary)" }}>
            {brand.name}
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-muted)" }}>
            {brand.slogan}
          </p>
        </div>

        <div className="space-y-4">
          <SaasInput
            type="email"
            value={email}
            onChange={(value) => {
              setEmail(value);
              setErrorMsg("");
            }}
            placeholder={t("auth.emailPlaceholder")}
            prefix="📧"
            onKeyDown={(e) => {
              if (e.key === "Enter") handleLogin();
            }}
          />

          <SaasInput
            type="password"
            value={password}
            onChange={(value) => {
              setPassword(value);
              setErrorMsg("");
            }}
            placeholder={t("auth.passwordPlaceholder")}
            prefix="🔐"
            onKeyDown={(e) => {
              if (e.key === "Enter") handleLogin();
            }}
          />

          {errorMsg && (
            <p className="text-sm" style={{ color: "var(--color-danger)" }}>
              {errorMsg}
            </p>
          )}

          <SaasButton
            variant="primary"
            fullWidth
            onClick={handleLogin}
            disabled={loading}
            loading={loading}
          >
            {loading ? t("auth.loggingIn") : t("auth.login")}
          </SaasButton>
        </div>

        <div className="text-center mt-6">
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            {t("auth.noAccount")}{" "}
            <Link
              to="/register"
              className="no-underline hover:underline"
              style={{ color: "var(--color-primary)" }}
            >
              {t("auth.registerNow")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
