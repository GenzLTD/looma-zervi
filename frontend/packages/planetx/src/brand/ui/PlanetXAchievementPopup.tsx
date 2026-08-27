/**
 * PlanetX AchievementPopup — pure UI component.
 * Shows a centered popup with bounceIn animation + claimPulse.
 */
import type { PlanetXAchievementPopupProps } from "./types";
import PlanetXIcon from "./PlanetXIcon";

export default function PlanetXAchievementPopup({
  visible,
  title,
  description,
  icon,
  onClose,
}: PlanetXAchievementPopupProps) {
  if (!visible) return null;

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "var(--px-modal-overlay)",
          zIndex: "var(--px-z-popup)",
        }}
      />
      <div
        className="px-anim-bounceIn"
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          zIndex: "var(--px-z-popup)",
          maxWidth: "var(--px-modal-max-width)",
          width: "90%",
          textAlign: "center",
          background: "var(--px-modal-bg)",
          border: "var(--px-modal-border)",
          borderRadius: "var(--px-modal-radius)",
          padding: "var(--px-modal-padding)",
          boxShadow: "var(--px-modal-shadow)",
        }}
      >
        <div
          className="px-anim-claimPulse"
          style={{
            marginBottom: "var(--px-spacing-sm)",
            display: "flex",
            justifyContent: "center",
            color: "var(--px-color-gold)",
          }}
        >
          {icon ?? <PlanetXIcon name="trophy" size={48} color="currentColor" />}
        </div>
        <div
          style={{
            fontSize: "var(--px-font-size-lg)",
            fontWeight: "var(--px-font-weight-black)",
            color: "var(--px-color-gold)",
          }}
        >
          {title}
        </div>
        {description && (
          <div
            style={{
              fontSize: "var(--px-font-size-sm)",
              color: "var(--px-color-text-muted)",
              marginTop: "var(--px-spacing-xs)",
            }}
          >
            {description}
          </div>
        )}
      </div>
    </>
  );
}
