/**
 * Register - SaaS registration page (MVP simplified).
 * Owner: szbenyx
 */
import { useState } from "react";
import { useNavigate, Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CLOSED_LOOP_EVENTS, trackEvent } from "@looma/shared-core";
import { useSaasAuthStore } from "./authStore";
import { useBrand } from "../../brand/useBrand";
import { LanguageSwitcher } from "../../components/LanguageSwitcher";

export default function Register() {
  const { t } = useTranslation();
  const brand = useBrand();
  const [searchParams] = useSearchParams();
  const fromShare = searchParams.get("from") === "share";
  const shareCode = searchParams.get("code") || undefined;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const { register, isAuthenticated } = useSaasAuthStore();
  const navigate = useNavigate();

  if (isAuthenticated) {
    navigate("/", { replace: true });
    return null;
  }

  const handleRegister = async () => {
    if (!email.trim() || !password) {
      setErrorMsg(t("auth.emailPasswordRequired"));
      return;
    }
    if (password !== confirmPassword) {
      setErrorMsg(t("auth.passwordMismatch"));
      return;
    }
    if (password.length < 6) {
      setErrorMsg(t("auth.passwordMinLength"));
      return;
    }

    setLoading(true);
    setErrorMsg("");
    try {
      await register(email, password, name.trim() || undefined);
      if (fromShare) {
        trackEvent(CLOSED_LOOP_EVENTS.HR_REGISTER_FROM_SHARE, {
          share_code: shareCode,
          properties: { from: searchParams.get("from") },
        });
      }
      navigate("/", { replace: true });
    } catch (err) {
      const msg = (err as { detail?: string })?.detail ?? t("auth.registerFailed");
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-blue-50">
      <div
        className="w-[420px] rounded-xl p-8"
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
            {t("auth.createAccount")}
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <input
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setErrorMsg("");
              }}
              placeholder={t("auth.nameOptional")}
              className="w-full px-4 py-3 text-sm rounded-lg border outline-none transition-colors"
              style={{
                borderColor: "#e0e0e0",
                color: "var(--color-text-primary)",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "var(--color-primary)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "#e0e0e0";
              }}
            />
          </div>
          <div>
            <input
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setErrorMsg("");
              }}
              placeholder={t("auth.emailPlaceholder")}
              className="w-full px-4 py-3 text-sm rounded-lg border outline-none transition-colors"
              style={{
                borderColor: "#e0e0e0",
                color: "var(--color-text-primary)",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "var(--color-primary)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "#e0e0e0";
              }}
            />
          </div>
          <div>
            <input
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setErrorMsg("");
              }}
              placeholder={t("auth.passwordMinPlaceholder")}
              className="w-full px-4 py-3 text-sm rounded-lg border outline-none transition-colors"
              style={{
                borderColor: "#e0e0e0",
                color: "var(--color-text-primary)",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "var(--color-primary)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "#e0e0e0";
              }}
            />
          </div>
          <div>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                setErrorMsg("");
              }}
              placeholder={t("auth.confirmPassword")}
              className="w-full px-4 py-3 text-sm rounded-lg border outline-none transition-colors"
              style={{
                borderColor: "#e0e0e0",
                color: "var(--color-text-primary)",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "var(--color-primary)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "#e0e0e0";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleRegister();
              }}
            />
          </div>

          {errorMsg && (
            <p className="text-sm" style={{ color: "var(--color-danger)" }}>
              {errorMsg}
            </p>
          )}

          <button
            onClick={handleRegister}
            disabled={loading}
            className="w-full py-3 text-sm rounded-lg text-white border-none cursor-pointer disabled:opacity-60 transition-colors font-medium"
            style={{ backgroundColor: "var(--color-primary)" }}
          >
            {loading ? t("auth.registering") : t("auth.register")}
          </button>
        </div>

        <div className="text-center mt-6">
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            {t("auth.hasAccount")}{" "}
            <Link
              to="/login"
              className="no-underline hover:underline"
              style={{ color: "var(--color-primary)" }}
            >
              {t("auth.login")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
