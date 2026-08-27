/**
 * PlanetX StreamingText — pure UI component.
 * Blinking cursor for AI streaming; uses --px-chat-streaming-* tokens.
 */
import type { PlanetXStreamingTextProps } from "./types";

export default function PlanetXStreamingText({
  text,
  done = false,
  cursorBlink = true,
}: PlanetXStreamingTextProps) {
  return (
    <span
      style={{
        fontSize: "var(--px-font-size-sm)",
        lineHeight: "var(--px-line-height-relaxed)",
        color: "var(--px-color-text)",
        fontFamily: "var(--px-font-family)",
      }}
    >
      {text}
      {!done && (
        <span
          style={{
            display: "inline-block",
            width: "var(--px-chat-streaming-cursor-width)",
            height: "1em",
            background: "var(--px-chat-streaming-cursor)",
            marginLeft: 2,
            verticalAlign: "text-bottom",
            animation: cursorBlink ? "pxCursorBlink 1s step-end infinite" : "none",
          }}
        />
      )}
      <style>{`
        @keyframes pxCursorBlink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
      `}</style>
    </span>
  );
}
