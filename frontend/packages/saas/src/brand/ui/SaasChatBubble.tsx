/**
 * SaaS ChatBubble — pure UI component.
 * Roles: user / ai
 * Supports markdown rendering flag (internal team wires the renderer).
 */
import type { SaasChatBubbleProps } from "./types";

export default function SaasChatBubble({
  role,
  content,
  markdown = false,
  timestamp,
  avatar,
  loading = false,
}: SaasChatBubbleProps) {
  const isUser = role === "user";

  return (
    <div style={{
      display: "flex",
      gap: "var(--chat-bubble-gap)",
      flexDirection: isUser ? "row-reverse" : "row",
      marginBottom: "var(--chat-bubble-gap)",
    }}>
      {/* Avatar */}
      <div style={{
        width: 32,
        height: 32,
        borderRadius: "50%",
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 14,
        background: isUser ? "var(--chat-bubble-bg-user)" : "var(--color-bg-surface)",
        color: isUser ? "var(--chat-bubble-text-user)" : "var(--color-text-secondary)",
        border: isUser ? "none" : "1px solid var(--color-border)",
      }}>
        {avatar || (isUser ? "我" : "AI")}
      </div>

      {/* Bubble */}
      <div style={{
        maxWidth: "70%",
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
        gap: 4,
      }}>
        <div
          className={markdown ? "markdown-body" : undefined}
          style={{
            background: isUser ? "var(--chat-bubble-bg-user)" : "var(--chat-bubble-bg-ai)",
            color: isUser ? "var(--chat-bubble-text-user)" : "var(--chat-bubble-text-ai)",
            borderRadius: isUser
              ? "var(--chat-bubble-radius) var(--chat-bubble-radius) var(--radius-xs) var(--chat-bubble-radius)"
              : "var(--chat-bubble-radius) var(--chat-bubble-radius) var(--chat-bubble-radius) var(--radius-xs)",
            padding: "var(--chat-bubble-padding)",
            fontSize: "var(--font-size-sm)",
            lineHeight: "var(--line-height-normal)",
          }}
        >
          {loading ? (
            <span style={{ display: "inline-flex", gap: 4 }}>
              <Dot /> <Dot delay={0.15} /> <Dot delay={0.3} />
            </span>
          ) : (
            content
          )}
        </div>
        {timestamp && (
          <span style={{
            fontSize: "var(--font-size-xs)",
            color: "var(--color-text-muted)",
          }}>
            {timestamp}
          </span>
        )}
      </div>
    </div>
  );
}

function Dot({ delay = 0 }: { delay?: number }) {
  return (
    <span style={{
      width: 6,
      height: 6,
      borderRadius: "50%",
      background: "currentColor",
      display: "inline-block",
      animation: "xSpin 1s ease-in-out infinite",
      animationDelay: `${delay}s`,
      opacity: 0.6,
    }} />
  );
}
