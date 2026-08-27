/**
 * PlanetX ToastBar — pure UI component.
 * Types: info / success / warning / error
 * Positioned at top center, slides in with fadeIn.
 */
import type { PlanetXToastBarProps, ToastType } from "./types";
import PlanetXIcon, { type PlanetXIconName } from "./PlanetXIcon";

const TYPE_STYLES: Record<
  ToastType,
  { color: string; border: string; bg: string; icon: PlanetXIconName }
> = {
  info: {
    color: "var(--px-color-cyan)",
    border: "1px solid rgba(0, 229, 255, 0.5)",
    bg: "rgba(0, 229, 255, 0.08)",
    icon: "info",
  },
  success: {
    color: "var(--px-color-accent)",
    border: "1px solid rgba(200, 255, 80, 0.5)",
    bg: "rgba(200, 255, 80, 0.08)",
    icon: "check",
  },
  warning: {
    color: "var(--px-color-warning)",
    border: "1px solid rgba(255, 165, 2, 0.5)",
    bg: "rgba(255, 165, 2, 0.08)",
    icon: "warning",
  },
  error: {
    color: "var(--px-color-danger)",
    border: "1px solid rgba(255, 71, 87, 0.5)",
    bg: "rgba(255, 71, 87, 0.08)",
    icon: "error",
  },
};

export default function PlanetXToastBar({
  message,
  type = "info",
  visible,
}: PlanetXToastBarProps) {
  if (!visible) return null;
  const s = TYPE_STYLES[type];

  return (
    <div
      className="px-anim-fadeIn"
      style={{
        position: "fixed",
        top: "var(--px-spacing-lg)",
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: "var(--px-z-toast)",
        display: "inline-flex",
        alignItems: "center",
        gap: "var(--px-spacing-sm)",
        padding: "10px 20px",
        borderRadius: "var(--px-radius-full)",
        fontSize: "var(--px-font-size-sm)",
        fontWeight: "var(--px-font-weight-bold)",
        color: s.color,
        background: s.bg,
        border: s.border,
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        boxShadow: "var(--px-shadow-card)",
        maxWidth: "90vw",
      }}
    >
      <PlanetXIcon name={s.icon} size={16} color="currentColor" />
      <span>{message}</span>
    </div>
  );
}
