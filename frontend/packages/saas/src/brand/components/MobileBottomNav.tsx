/**
 * MobileBottomNav — mobile bottom tab bar.
 * Replaces sidebar on small screens (<md).
 *
 * Shows 5 core nav items with icons.
 */
import { useLocation, useNavigate } from "react-router-dom";
import SaasIcon, { type SaasIconName } from "../ui/SaasIcon";

interface NavItem {
  path: string;
  label: string;
  icon: SaasIconName;
}

const NAV_ITEMS: NavItem[] = [
  { path: "/", label: "首页", icon: "dashboard" },
  { path: "/query", label: "对话", icon: "chat" },
  { path: "/candidates", label: "候选人", icon: "candidates" },
  { path: "/resume", label: "简历", icon: "resume" },
  { path: "/pricing", label: "定价", icon: "pricing" },
];

export default function MobileBottomNav() {
  const location = useLocation();
  const navigate = useNavigate();

  /** Check if path matches current location */
  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around md:hidden"
      style={{
        height: "56px",
        backgroundColor: "var(--color-bg-card)",
        borderTop: "1px solid var(--color-border)",
        paddingBottom: "env(safe-area-inset-bottom, 0px)",
      }}
    >
      {NAV_ITEMS.map((item) => {
        const active = isActive(item.path);
        return (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className="flex flex-col items-center justify-center gap-0.5 flex-1 h-full"
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: active
                ? "var(--color-primary)"
                : "var(--color-text-muted)",
              fontSize: "var(--font-size-xs)",
              transition: "color var(--transition-fast)",
            }}
          >
            <SaasIcon name={item.icon} size={20} />
            <span
              style={{
                fontSize: "10px",
                fontWeight: active
                  ? "var(--font-weight-semibold)"
                  : "var(--font-weight-normal)",
              }}
            >
              {item.label}
            </span>
            {active && (
              <span
                style={{
                  position: "absolute",
                  top: 0,
                  width: "24px",
                  height: "2px",
                  borderRadius: "1px",
                  backgroundColor: "var(--color-primary)",
                }}
              />
            )}
          </button>
        );
      })}
    </nav>
  );
}