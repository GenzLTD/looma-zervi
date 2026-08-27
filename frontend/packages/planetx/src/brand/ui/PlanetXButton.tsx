/**
 * PlanetX Button — pure UI component.
 * Variants: primary / accent / outline / ghost / danger
 * Sizes: sm / md / lg
 *
 * No store, no API — all data via props.
 */
import type { PlanetXButtonProps } from "./types";
import PlanetXIcon from "./PlanetXIcon";

export default function PlanetXButton({
  variant = "primary",
  size = "md",
  disabled = false,
  loading = false,
  fullWidth = false,
  leftIcon,
  rightIcon,
  children,
  onClick,
  type = "button",
}: PlanetXButtonProps) {
  const base: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "var(--px-btn-gap)",
    fontWeight: "var(--px-font-weight-bold)",
    borderRadius: "var(--px-btn-radius)",
    border: "none",
    cursor: disabled || loading ? "not-allowed" : "pointer",
    opacity: disabled ? 0.4 : 1,
    transition: "var(--px-anim-fast)",
    fontFamily: "var(--px-font-family)",
    width: fullWidth ? "100%" : "auto",
    pointerEvents: disabled || loading ? "none" : "auto",
  };

  const sizes: Record<string, React.CSSProperties> = {
    sm: { height: "var(--px-btn-height-sm)", padding: "var(--px-btn-padding-sm)", fontSize: "var(--px-btn-font-sm)" },
    md: { height: "var(--px-btn-height-md)", padding: "var(--px-btn-padding-md)", fontSize: "var(--px-btn-font-md)" },
    lg: { height: "var(--px-btn-height-lg)", padding: "var(--px-btn-padding-lg)", fontSize: "var(--px-btn-font-lg)" },
  };

  const variants: Record<string, React.CSSProperties> = {
    primary: {
      background: "var(--px-btn-bg-primary)",
      color: "var(--px-color-text-on-primary)",
      boxShadow: "var(--px-shadow-glow)",
    },
    accent: {
      background: "var(--px-btn-bg-accent)",
      color: "var(--px-color-text-on-accent)",
      boxShadow: "var(--px-shadow-accent)",
    },
    outline: {
      background: "transparent",
      color: "var(--px-color-primary)",
      border: "var(--px-btn-border-outline)",
    },
    ghost: {
      background: "var(--px-btn-bg-ghost)",
      color: "var(--px-color-text)",
      border: "var(--px-btn-border-ghost)",
    },
    danger: {
      background: "var(--px-btn-bg-danger)",
      color: "#fff",
    },
  };

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      style={{ ...base, ...sizes[size], ...variants[variant] }}
      onMouseEnter={(e) => {
        if (disabled || loading) return;
        if (variant === "primary") e.currentTarget.style.background = "var(--px-color-primary-hover)";
        if (variant === "accent") e.currentTarget.style.background = "var(--px-color-accent-hover)";
        if (variant === "outline" || variant === "ghost")
          e.currentTarget.style.background = "var(--px-btn-bg-ghost-hover)";
      }}
      onMouseLeave={(e) => {
        if (variant === "primary") e.currentTarget.style.background = "var(--px-btn-bg-primary)";
        if (variant === "accent") e.currentTarget.style.background = "var(--px-btn-bg-accent)";
        if (variant === "outline" || variant === "ghost") e.currentTarget.style.background = "transparent";
      }}
    >
      {loading && (
        <span className="px-anim-xSpin" style={{ display: "inline-flex" }}>
          <PlanetXIcon name="spinner" size={16} color="currentColor" />
        </span>
      )}
      {!loading && leftIcon}
      {children}
      {!loading && rightIcon}
    </button>
  );
}
