/**
 * PlanetX ChatBubble — pure UI component.
 * Roles: user / ai. Deep-space theme via --px-chat-* tokens.
 */
import type { PlanetXChatBubbleProps } from "./types";

export default function PlanetXChatBubble({
  role,
  content,
  markdown = false,
  timestamp,
  avatar,
  loading = false,
}: PlanetXChatBubbleProps) {
  const isUser = role === "user";

  return (
    <div
      style={{
        display: "flex",
        gap: "var(--px-chat-bubble-gap)",
        flexDirection: isUser ? "row-reverse" : "row",
        marginBottom: "var(--px-chat-bubble-gap)",
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 14,
          background: isUser
            ? "var(--px-chat-bubble-bg-user)"
            : "var(--px-color-bg-surface)",
          color: isUser
            ? "var(--px-chat-bubble-text-user)"
            : "var(--px-color-text-muted)",
          border: isUser ? "none" : "1px solid var(--px-border-default)",
        }}
      >
        {avatar || (isUser ? "我" : "AI")}
      </div>

      <div
        style={{
          maxWidth: "70%",
          display: "flex",
          flexDirection: "column",
          alignItems: isUser ? "flex-end" : "flex-start",
          gap: "var(--px-spacing-xs)",
        }}
      >
        <div
          className={markdown ? "markdown-body" : undefined}
          style={{
            background: isUser
              ? "var(--px-chat-bubble-bg-user)"
              : "var(--px-chat-bubble-bg-ai)",
            color: isUser
              ? "var(--px-chat-bubble-text-user)"
              : "var(--px-chat-bubble-text-ai)",
            borderRadius: isUser
              ? "var(--px-chat-bubble-radius) var(--px-chat-bubble-radius) var(--px-radius-xs) var(--px-chat-bubble-radius)"
              : "var(--px-chat-bubble-radius) var(--px-chat-bubble-radius) var(--px-chat-bubble-radius) var(--px-radius-xs)",
            padding: "var(--px-chat-bubble-padding)",
            fontSize: "var(--px-font-size-sm)",
            lineHeight: "var(--px-line-height-normal)",
          }}
        >
          {loading ? (
            <span style={{ display: "inline-flex", gap: "var(--px-spacing-xs)" }}>
              <Dot /> <Dot delay={0.15} /> <Dot delay={0.3} />
            </span>
          ) : (
            content
          )}
        </div>
        {timestamp && (
          <span
            style={{
              fontSize: "var(--px-font-size-xs)",
              color: "var(--px-color-text-dim)",
            }}
          >
            {timestamp}
          </span>
        )}
      </div>
      <style>{`
        @keyframes pxChatDot {
          0%, 80%, 100% { opacity: 0.3; transform: translateY(0); }
          40% { opacity: 1; transform: translateY(-2px); }
        }
      `}</style>
    </div>
  );
}

function Dot({ delay = 0 }: { delay?: number }) {
  return (
    <span
      style={{
        width: 6,
        height: 6,
        borderRadius: "50%",
        background: "currentColor",
        display: "inline-block",
        animation: "pxChatDot 1s ease-in-out infinite",
        animationDelay: `${delay}s`,
        opacity: 0.6,
      }}
    />
  );
}
