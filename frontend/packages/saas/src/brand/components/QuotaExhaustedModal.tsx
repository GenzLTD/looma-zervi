/**
 * QuotaExhaustedModal — triggered when backend returns 429 quota_exceeded.
 * Owner: Jason (for SaaS closed-loop: Free → quota exhausted → upgrade prompt)
 */
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import SaasModal from "../ui/SaasModal";

export interface QuotaExhaustedModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function QuotaExhaustedModal({
  isOpen,
  onClose,
}: QuotaExhaustedModalProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const handleUpgrade = () => {
    onClose();
    navigate("/pricing");
  };

  return (
    <SaasModal
      isOpen={isOpen}
      onClose={onClose}
      title={t("quota.exhaustedTitle")}
      size="sm"
      footer={
        <>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm border-none cursor-pointer transition-colors"
            style={{
              backgroundColor: "var(--color-bg-surface)",
              color: "var(--color-text-secondary)",
            }}
          >
            {t("quota.dismiss")}
          </button>
          <button
            onClick={handleUpgrade}
            className="px-4 py-2 rounded-lg text-sm text-white border-none cursor-pointer transition-colors"
            style={{ backgroundColor: "var(--color-primary)" }}
          >
            {t("quota.upgradeToPro")}
          </button>
        </>
      }
    >
      <div className="flex flex-col items-center text-center gap-3 py-2">
        {/* Icon */}
        <div
          className="w-14 h-14 rounded-full flex items-center justify-center text-2xl"
          style={{ backgroundColor: "#fff3e0" }}
        >
          ⚡
        </div>

        <p style={{ color: "var(--color-text-primary)", fontSize: "var(--font-size-base)", margin: 0 }}>
          {t("quota.exhaustedMessage")}
        </p>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
          {t("quota.exhaustedHint")}
        </p>
      </div>
    </SaasModal>
  );
}
