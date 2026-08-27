/**
 * T-space App - B-end brand entry point.
 * Owner: szbenyx
 *
 * Routes:
 *   /           - Dashboard
 *   /trust      - Trust profile (attestation cards + share codes)
 *   /verify     - Public attestation verify via share_code
 *   /query      - RAG knowledge base chat
 *   /jobs       - Position matching
 *   /resume     - Resume parsing
 *   /reports    - Report center
 *   /login      - Login
 *   /register   - Registration
 */
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import "./i18n";
import { SaasAuthGuard } from "./features/auth/SaasAuthGuard";
import { SaasAdminGuard } from "./features/auth/SaasAdminGuard";
import { useSaasAuthStore } from "./features/auth/authStore";
import { AppLayout } from "./brand/components/AppLayout";
import ErrorBoundary from "./brand/components/ErrorBoundary";
import Login from "./features/auth/Login";
import Register from "./features/auth/Register";
import Dashboard from "./features/dashboard/Dashboard";
import Chat from "./features/chat/Chat";
import Poetry from "./features/poetry/Poetry";
import Challenge from "./features/poetry/Challenge";
import Jobs from "./features/hr/Jobs";
import Resume from "./features/hr/Resume";
import Reports from "./features/reports/Reports";
import Pricing from "./features/pricing/Pricing";
import CandidateShare from "./features/candidates/CandidateShare";
import Candidates from "./features/candidates/Candidates";
import CandidateDetail from "./features/candidates/CandidateDetail";
import ConsentSettings from "./features/settings/ConsentSettings";
import TrustProfile from "./features/trust/TrustProfile";
import TrustVerify from "./features/trust/TrustVerify";
import AdminDashboard from "./features/admin/AdminDashboard";
import { useSaasAnalytics } from "./analytics/useSaasAnalytics";
import { IS_OVERSEAS } from "./config/region";

/** 轻量 ErrorBoundary 包装器，用于隔离单个功能的崩溃 */
function FeatureGuard({ children }: { children: React.ReactNode }) {
  return <ErrorBoundary>{children}</ErrorBoundary>;
}

/** Vite `base` (e.g. `/tspace/`) → React Router basename without trailing slash. */
function routerBasename(): string | undefined {
  const raw = import.meta.env.BASE_URL || "/";
  if (raw === "/") return undefined;
  return raw.replace(/\/$/, "");
}

export default function App() {
  const tryAutoLogin = useSaasAuthStore((s) => s.tryAutoLogin);
  useSaasAnalytics();
  const { t, i18n } = useTranslation();

  // 动态 document.title 跟随品牌名 + i18n 切换
  useEffect(() => {
    document.title = t("brand.slogan")
      ? `${t("brand.name")} — ${t("brand.slogan")}`
      : t("brand.name");
  }, [t, i18n.language]);

  // 大陆：PlanetX 共享 token 自动登录（C→B）；海外 MVP 跳过
  useEffect(() => {
    if (!IS_OVERSEAS) tryAutoLogin();
  }, [tryAutoLogin]);

  return (
    <ErrorBoundary>
      <BrowserRouter basename={routerBasename()}>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Public pages — 自由浏览，无需登录 */}
          <Route element={<AppLayout />}>
            <Route path="/" element={<FeatureGuard><Dashboard /></FeatureGuard>} />
            <Route path="/pricing" element={<FeatureGuard><Pricing /></FeatureGuard>} />
            <Route path="/verify" element={<FeatureGuard><TrustVerify /></FeatureGuard>} />
            <Route path="/candidate/share/:code" element={<FeatureGuard><CandidateShare /></FeatureGuard>} />
          </Route>

          {/* Protected routes (需要登录的功能页) */}
          <Route element={<SaasAuthGuard />}>
            <Route element={<AppLayout />}>
              <Route path="/query" element={<FeatureGuard><Chat /></FeatureGuard>} />
              <Route path="/poetry" element={<FeatureGuard><Poetry /></FeatureGuard>} />
              <Route path="/poetry/challenge" element={<FeatureGuard><Challenge /></FeatureGuard>} />
              <Route path="/jobs" element={<FeatureGuard><Jobs /></FeatureGuard>} />
              <Route path="/resume" element={<FeatureGuard><Resume /></FeatureGuard>} />
              <Route path="/reports" element={<FeatureGuard><Reports /></FeatureGuard>} />
              <Route path="/trust" element={<FeatureGuard><TrustProfile /></FeatureGuard>} />
              <Route path="/candidates" element={<FeatureGuard><Candidates /></FeatureGuard>} />
              <Route path="/candidates/:id" element={<FeatureGuard><CandidateDetail /></FeatureGuard>} />
              <Route path="/settings/consent" element={<FeatureGuard><ConsentSettings /></FeatureGuard>} />
              <Route element={<SaasAdminGuard />}>
                <Route path="/admin" element={<FeatureGuard><AdminDashboard /></FeatureGuard>} />
              </Route>
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
