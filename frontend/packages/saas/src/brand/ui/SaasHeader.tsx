/**
 * SaaS Header — pure UI component.
 * Top bar with title, search, notifications, user menu.
 */
import { useTranslation } from "react-i18next";
import type { SaasHeaderProps } from "./types";

export default function SaasHeader({
  title,
  user,
  notifications = 0,
  onLogout,
  onNotificationsClick,
  searchPlaceholder,
  onSearch,
}: SaasHeaderProps) {
  const { t } = useTranslation();
  const placeholder = searchPlaceholder ?? t("common.searchPlaceholder");
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 24px",
        height: "var(--header-height)",
        background: "var(--color-bg-card)",
        borderBottom: "1px solid var(--color-border-light)",
        flexShrink: 0,
        gap: "var(--radius-lg)",
      }}
    >
      {/* Left: Title */}
      {title && (
        <span style={{
          fontSize: "var(--font-size-base)",
          fontWeight: "var(--font-weight-semibold)",
          color: "var(--color-text-primary)",
        }}>
          {title}
        </span>
      )}

      {/* Center: Search */}
      {onSearch && (
        <div style={{ flex: 1, maxWidth: 400, margin: "0 auto" }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--radius-sm)",
            height: 32,
            padding: "0 12px",
            background: "var(--color-bg-surface)",
            borderRadius: "var(--input-radius)",
            border: "1px solid var(--color-border-light)",
          }}>
            <span style={{ color: "var(--color-text-muted)", fontSize: 14 }}>🔍</span>
            <input
              type="text"
              placeholder={placeholder}
              onChange={(e) => onSearch(e.target.value)}
              style={{
                flex: 1,
                border: "none",
                outline: "none",
                background: "transparent",
                fontSize: "var(--font-size-sm)",
                color: "var(--color-text-primary)",
              }}
            />
          </div>
        </div>
      )}

      {/* Right: Notifications + User */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--radius-lg)" }}>
        {/* Notifications */}
        <button
          onClick={onNotificationsClick}
          style={{
            position: "relative",
            background: "transparent",
            border: "none",
            cursor: "pointer",
            fontSize: 18,
            color: "var(--color-text-secondary)",
            padding: 4,
          }}
        >
          🔔
          {notifications > 0 && (
            <span style={{
              position: "absolute",
              top: 0,
              right: 0,
              background: "var(--color-danger)",
              color: "#fff",
              fontSize: 10,
              padding: "1px 5px",
              borderRadius: "var(--radius-full)",
              fontWeight: "var(--font-weight-bold)",
              lineHeight: 1.4,
            }}>
              {notifications > 99 ? "99+" : notifications}
            </span>
          )}
        </button>

        {/* User */}
        {user && (
          <div style={{ display: "flex", alignItems: "center", gap: "var(--radius-sm)" }}>
            <div style={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              background: "var(--color-primary-light)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 14,
              fontWeight: "var(--font-weight-semibold)",
              color: "var(--color-primary)",
            }}>
              {user.avatar || (user.name || user.email || "?").charAt(0).toUpperCase()}
            </div>
            <span style={{
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text-secondary)",
              maxWidth: 120,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}>
              {user.name || user.email}
            </span>
            {onLogout && (
              <button
                onClick={onLogout}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--color-danger)",
                  cursor: "pointer",
                  fontSize: "var(--font-size-sm)",
                  padding: "4px 8px",
                }}
              >
                {t("auth.logoutShort")}
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
