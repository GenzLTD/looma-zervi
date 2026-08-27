import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { HomePage } from "./pages/HomePage";
import { PricingPage } from "./pages/PricingPage";
import { PrivacyPage } from "./pages/PrivacyPage";
import { RefundPage } from "./pages/RefundPage";
import { TermsPage } from "./pages/TermsPage";

export function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/legal/privacy" element={<PrivacyPage />} />
          <Route path="/legal/terms" element={<TermsPage />} />
          <Route path="/legal/refund" element={<RefundPage />} />
          <Route path="/pricing.html" element={<Navigate to="/pricing" replace />} />
          <Route path="/legal/privacy.html" element={<Navigate to="/legal/privacy" replace />} />
          <Route path="/legal/terms.html" element={<Navigate to="/legal/terms" replace />} />
          <Route path="/legal/refund.html" element={<Navigate to="/legal/refund" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
