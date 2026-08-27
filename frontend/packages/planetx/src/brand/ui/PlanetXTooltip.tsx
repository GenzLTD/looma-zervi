/**
 * PlanetX Tooltip — pure UI component.
 * Positioning + arrow; deep-space theme via --px-tooltip-* tokens.
 */
import { useState, useRef, useEffect } from "react";
import type { PlanetXTooltipProps } from "./types";

export default function PlanetXTooltip({
  children,
  content,
  position = "top",
  delay = 200,
  maxWidth = "240px",
  disabled = false,
}: PlanetXTooltipProps) {
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
      marginBottom: "var(--px-spacing-sm)",
    },
    bottom: {
      top: "100%",
      left: "50%",
      transform: "translateX(-50%)",
      marginTop: "var(--px-spacing-sm)",
    },
    left: {
      right: "100%",
      top: "50%",
      transform: "translateY(-50%)",
      marginRight: "var(--px-spacing-sm)",
    },
    right: {
      left: "100%",
      top: "50%",
      transform: "translateY(-50%)",
      marginLeft: "var(--px-spacing-sm)",
    },
  };

  const arrowStyles: Record<string, React.CSSProperties> = {
    top: {
      top: "100%",
      left: "50%",
      transform: "translateX(-50%)",
      borderTopColor: "var(--px-tooltip-bg)",
    },
    bottom: {
      bottom: "100%",
      left: "50%",
      transform: "translateX(-50%)",
      borderBottomColor: "var(--px-tooltip-bg)",
    },
    left: {
      left: "100%",
      top: "50%",
      transform: "translateY(-50%)",
      borderLeftColor: "var(--px-tooltip-bg)",
    },
    right: {
      right: "100%",
      top: "50%",
      transform: "translateY(-50%)",
      borderRightColor: "var(--px-tooltip-bg)",
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
            zIndex: "var(--px-z-tooltip)",
            maxWidth,
            background: "var(--px-tooltip-bg)",
            color: "var(--px-tooltip-color)",
            borderRadius: "var(--px-tooltip-radius)",
            padding: "var(--px-tooltip-padding)",
            fontSize: "var(--px-tooltip-font-size)",
            lineHeight: "var(--px-tooltip-line-height)",
            boxShadow: "var(--px-tooltip-shadow)",
            animation: "pxTooltipFadeIn 150ms ease-out",
            ...positionStyles[position],
          }}
        >
          {typeof content === "string" ? (
            <div style={{ whiteSpace: "normal", wordWrap: "break-word" }}>{content}</div>
          ) : (
            content
          )}

          <div
            style={{
              position: "absolute",
              width: 0,
              height: 0,
              borderStyle: "solid",
              borderWidth: "var(--px-tooltip-arrow-size)",
              borderColor: "transparent",
              ...arrowStyles[position],
            }}
          />
        </div>
      )}

      <style>{`
        @keyframes pxTooltipFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
