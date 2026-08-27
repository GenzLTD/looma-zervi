/**
 * SaaS Tooltip — pure UI component.
 * Features: positioning (top/bottom/left/right), delay, arrow, rich content.
 *
 * No store, no API — all data via props.
 */
import { useState, useRef, useEffect } from "react";
import type { SaasTooltipProps } from "./types";

export default function SaasTooltip({
  children,
  content,
  position = "top",
  delay = 200,
  maxWidth = "240px",
  disabled = false,
}: SaasTooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [timeoutId, setTimeoutId] = useState<ReturnType<typeof setTimeout> | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const showTooltip = () => {
    if (disabled) return;
    if (timeoutId) clearTimeout(timeoutId);
    const id = setTimeout(() => setIsVisible(true), delay);
    setTimeoutId(id);
  };

  const hideTooltip = () => {
    if (timeoutId) clearTimeout(timeoutId);
    setTimeoutId(null);
    setIsVisible(false);
  };

  useEffect(() => {
    return () => {
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [timeoutId]);

  const positionStyles: Record<string, React.CSSProperties> = {
    top: {
      bottom: "100%",
      left: "50%",
      transform: "translateX(-50%)",
      marginBottom: "var(--spacing-sm)",
    },
    bottom: {
      top: "100%",
      left: "50%",
      transform: "translateX(-50%)",
      marginTop: "var(--spacing-sm)",
    },
    left: {
      right: "100%",
      top: "50%",
      transform: "translateY(-50%)",
      marginRight: "var(--spacing-sm)",
    },
    right: {
      left: "100%",
      top: "50%",
      transform: "translateY(-50%)",
      marginLeft: "var(--spacing-sm)",
    },
  };

  const arrowStyles: Record<string, React.CSSProperties> = {
    top: {
      top: "100%",
      left: "50%",
      transform: "translateX(-50%)",
      borderTopColor: "var(--tooltip-bg)",
    },
    bottom: {
      bottom: "100%",
      left: "50%",
      transform: "translateX(-50%)",
      borderBottomColor: "var(--tooltip-bg)",
    },
    left: {
      left: "100%",
      top: "50%",
      transform: "translateY(-50%)",
      borderLeftColor: "var(--tooltip-bg)",
    },
    right: {
      right: "100%",
      top: "50%",
      transform: "translateY(-50%)",
      borderRightColor: "var(--tooltip-bg)",
    },
  };

  return (
    <div
      style={{
        position: "relative",
        display: "inline-block",
      }}
      onMouseEnter={showTooltip}
      onMouseLeave={hideTooltip}
      onFocus={showTooltip}
      onBlur={hideTooltip}
    >
      {children}

      {isVisible && (
        <div
          ref={tooltipRef}
          style={{
            position: "absolute",
            zIndex: "var(--z-tooltip)",
            maxWidth,
            background: "var(--tooltip-bg)",
            color: "var(--tooltip-color)",
            borderRadius: "var(--tooltip-radius)",
            padding: "var(--tooltip-padding)",
            fontSize: "var(--tooltip-font-size)",
            lineHeight: "var(--tooltip-line-height)",
            boxShadow: "var(--tooltip-shadow)",
            animation: "fadeIn 150ms ease-out",
            ...positionStyles[position],
          }}
        >
          {typeof content === "string" ? (
            <div style={{ whiteSpace: "normal", wordWrap: "break-word" }}>{content}</div>
          ) : (
            content
          )}

          {/* Arrow */}
          <div
            style={{
              position: "absolute",
              width: 0,
              height: 0,
              borderStyle: "solid",
              borderWidth: "var(--tooltip-arrow-size)",
              borderColor: "transparent",
              ...arrowStyles[position],
            }}
          />
        </div>
      )}

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: ${position === "top" || position === "bottom" ? "translateX(-50%) translateY(4px)" : "translateY(-50%) translateX(4px)"}; }
          to { opacity: 1; transform: ${position === "top" || position === "bottom" ? "translateX(-50%) translateY(0)" : "translateY(-50%) translateX(0)"}; }
        }
      `}</style>
    </div>
  );
}
