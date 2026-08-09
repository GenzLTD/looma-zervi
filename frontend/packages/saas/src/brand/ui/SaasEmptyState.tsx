/**
 * SaaS EmptyState + ErrorState — pure UI components.
 */
import type { ReactNode } from "react";
import type { SaasEmptyStateProps, SaasErrorStateProps } from "./types";

export function SaasEmptyState({
  icon = "📭",
  title,
  description,
  actionLabel,
  onAction,
}: SaasEmptyStateProps) {
  const iconNode: ReactNode = icon;
  const iconIsGraphic = typeof icon !== "string";

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "48px 24px",
      gap: "var(--radius-md)",
    }}>
      <div style={iconIsGraphic ? undefined : { fontSize: 48, opacity: 0.6 }}>
        {iconNode}
      </div>
      <div style={{
        fontSize: "var(--font-size-base)",
        fontWeight: "var(--font-weight-medium)",
        color: "var(--color-text-primary)",
      }}>
        {title}
      </div>
      {description && (
        <div style={{
          fontSize: "var(--font-size-sm)",
          color: "var(--color-text-muted)",
          textAlign: "center",
          maxWidth: 320,
        }}>
          {description}
        </div>
      )}
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          style={{
            marginTop: "var(--radius-sm)",
            padding: "8px 20px",
            border: "none",
            borderRadius: "var(--btn-radius)",
            background: "var(--btn-bg-primary)",
            color: "var(--btn-text-primary)",
            fontSize: "var(--font-size-sm)",
            fontWeight: "var(--btn-font-weight)",
            cursor: "pointer",
            transition: "var(--transition-fast)",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--btn-bg-primary-hover)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "var(--btn-bg-primary)"; }}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

export function SaasErrorState({
  title = "出错了",
  message,
  onRetry,
}: SaasErrorStateProps) {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "48px 24px",
      gap: "var(--radius-md)",
    }}>
      <div style={{ fontSize: 48 }}>⚠️</div>
      <div style={{
        fontSize: "var(--font-size-base)",
        fontWeight: "var(--font-weight-medium)",
        color: "var(--color-danger)",
      }}>
        {title}
      </div>
      <div style={{
        fontSize: "var(--font-size-sm)",
        color: "var(--color-text-muted)",
        textAlign: "center",
        maxWidth: 320,
      }}>
        {message}
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            marginTop: "var(--radius-sm)",
            padding: "8px 20px",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--btn-radius)",
            background: "var(--color-bg-card)",
            color: "var(--color-text-primary)",
            fontSize: "var(--font-size-sm)",
            fontWeight: "var(--btn-font-weight)",
            cursor: "pointer",
            transition: "var(--transition-fast)",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--color-bg-hover)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "var(--color-bg-card)"; }}
        >
          重试
        </button>
      )}
    </div>
  );
}
