/**
 * Chat - RAG knowledge base Q&A page.
 * Owner: szbenyx
 *
 * Pure CSS + Tailwind (no tdesign-react).
 * Updated to use non-streaming API for contract consistency.
 */
import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { createSaasApiClient } from "../../api/saasApiClient";
import { useConsent } from "../../compliance/useConsent";
import { useChatNonStreaming, type DocSource } from "./useChatNonStreaming";
import QuotaExhaustedModal from "../../brand/components/QuotaExhaustedModal";

type ChatMode = "chat" | "deepseek" | "fast";

function truncate(s: string, maxLen: number): string {
  return s.length > maxLen ? s.slice(0, maxLen) + "..." : s;
}

export default function Chat() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<ChatMode>("chat");
  const reportId = (searchParams.get("report") || searchParams.get("match") || "").trim() || null;
  const api = useMemo(() => createSaasApiClient(), []);
  const { ensureConsent, consentPrompt } = useConsent(() => api);
  const ensureAskConsent = useCallback(
    () => ensureConsent("ask_rag"),
    [ensureConsent],
  );
  const { messages, isStreaming, error, quotaExhausted, sendStream, clear, resetQuotaError } = useChatNonStreaming({
    mode,
    ensureAskConsent,
    reportId,
    useLatestReport: !reportId,
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const autoSentRef = useRef(false);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(async () => {
    const q = input.trim();
    if (!q || isStreaming) return;
    const allowed = await ensureConsent("ask_rag");
    if (!allowed) return;
    setInput("");
    sendStream(q);
  }, [input, isStreaming, sendStream, ensureConsent]);

  // Dashboard quick-ask: /query?q=... → auto-send once
  useEffect(() => {
    const q = (searchParams.get("q") || "").trim();
    if (!q || autoSentRef.current || isStreaming) return;
    autoSentRef.current = true;
    setInput(q);
    void (async () => {
      const allowed = await ensureConsent("ask_rag");
      if (!allowed) {
        autoSentRef.current = false;
        return;
      }
      setInput("");
      sendStream(q);
      // Clear query param so refresh does not re-send
      const next = new URLSearchParams(searchParams);
      next.delete("q");
      setSearchParams(next, { replace: true });
    })();
  }, [searchParams, setSearchParams, ensureConsent, sendStream, isStreaming]);

  return (
    <>
    {consentPrompt}
    <QuotaExhaustedModal isOpen={quotaExhausted} onClose={resetQuotaError} />
    <div className="max-w-4xl mx-auto flex flex-col" style={{ height: "calc(100vh - 120px)" }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--color-text-primary)" }}>
            智能问答
          </h1>
          <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
            {reportId
              ? "回答将参考当前匹配报告（摘要），不会检索你的简历全文。"
              : "若你近期保存过匹配报告，回答可能附带最新报告摘要。"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Mode switcher */}
          <div
            className="flex rounded-md overflow-hidden border text-xs"
            style={{ borderColor: "var(--color-border)" }}
          >
            {(
              [
                { id: "chat", label: "对话", tip: "多轮上下文，适合追问" },
                { id: "deepseek", label: "深度", tip: "更多检索 + 较长推理" },
                { id: "fast", label: "快速", tip: "少检索 + 低温度短答" },
              ] as const
            ).map((m) => (
              <button
                key={m.id}
                type="button"
                title={m.tip}
                onClick={() => setMode(m.id)}
                className="px-3 py-1.5 border-none cursor-pointer transition-colors"
                style={{
                  backgroundColor: mode === m.id ? "var(--color-primary)" : "transparent",
                  color: mode === m.id ? "var(--color-text-on-primary)" : "var(--color-text-secondary)",
                }}
              >
                {m.label}
              </button>
            ))}
          </div>
          <button
            onClick={clear}
            className="text-sm bg-transparent border-none cursor-pointer p-1"
            style={{ color: "var(--color-text-muted)" }}
            title="清空对话"
          >
            ✕ 清空
          </button>
        </div>
      </div>
      <p className="text-xs mb-3 shrink-0" style={{ color: "var(--color-text-muted)" }}>
        {t("quota.rulesHint")}
      </p>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-2" style={{ color: "var(--color-text-muted)" }}>
            <span className="text-5xl opacity-20">💬</span>
            <p className="text-lg font-medium">开始一段新的对话</p>
            <p className="text-sm">基于您的知识库，获得智能、准确的回答</p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
          >
            {/* Avatar */}
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm"
              style={{
                backgroundColor:
                  msg.role === "user" ? "var(--chat-bubble-bg-user)" : "var(--color-bg-surface)",
                color:
                  msg.role === "user"
                    ? "var(--chat-bubble-text-user)"
                    : "var(--color-text-secondary)",
                border:
                  msg.role === "user" ? "none" : "1px solid var(--color-border)",
              }}
            >
              {msg.role === "user" ? "U" : "AI"}
            </div>

            {/* Message bubble */}
            <div
              className="max-w-[75%] text-sm leading-relaxed"
              style={{
                backgroundColor:
                  msg.role === "user"
                    ? "var(--chat-bubble-bg-user)"
                    : "var(--chat-bubble-bg-ai)",
                color:
                  msg.role === "user"
                    ? "var(--chat-bubble-text-user)"
                    : "var(--chat-bubble-text-ai)",
                borderRadius: "var(--chat-bubble-radius)",
                padding: "var(--chat-bubble-padding)",
                boxShadow: msg.role === "user" ? "none" : "var(--shadow-sm)",
                border: msg.role === "user" ? "none" : "1px solid var(--color-border-light)",
              }}
            >
              <div className="whitespace-pre-wrap break-words">{msg.content}</div>

              {/* Sources */}
              {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                <div
                  className="mt-3 pt-2"
                  style={{ borderTop: "1px solid var(--color-border-light)" }}
                >
                  <p className="text-xs mb-1" style={{ color: "var(--color-text-muted)" }}>
                    引用来源：
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {msg.sources.map((s: DocSource, i: number) => (
                      <span
                        key={i}
                        className="text-xs px-2 py-0.5 rounded border"
                        style={{
                          borderColor: "var(--color-border)",
                          color: "var(--color-text-secondary)",
                        }}
                      >
                        {truncate(s.filename, 20)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Error display */}
        {error && (
          <div className="text-center">
            <span
              className="inline-block text-sm px-3 py-1 rounded"
              style={{
                backgroundColor: "var(--color-danger-light)",
                color: "var(--color-danger)",
              }}
            >
              {error}
            </span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="mt-4 shrink-0">
        <div
          className="border-t mb-3"
          style={{ borderColor: "var(--color-border)" }}
        />
        <div className="flex gap-3 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={isStreaming ? "AI 正在回复..." : "输入您的问题，Enter 发送，Shift+Enter 换行"}
            disabled={isStreaming}
            rows={1}
            className="flex-1 px-4 py-2.5 text-sm resize-none outline-none transition-colors"
            style={{
              border: "var(--chat-input-border)",
              borderRadius: "var(--chat-input-radius)",
              color: "var(--color-text-primary)",
              backgroundColor: "var(--chat-input-bg)",
              minHeight: "var(--chat-input-height)",
              maxHeight: "120px",
            }}
            onFocus={(e) => {
              e.target.style.borderColor = "var(--color-border-focus)";
            }}
            onBlur={(e) => {
              e.target.style.border = "var(--chat-input-border)";
            }}
            onInput={(e) => {
              const el = e.target as HTMLTextAreaElement;
              el.style.height = "auto";
              el.style.height = Math.min(el.scrollHeight, 120) + "px";
            }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
            className="w-11 h-11 rounded-full flex items-center justify-center border-none cursor-pointer shrink-0 disabled:opacity-40 transition-colors"
            style={{
              backgroundColor: "var(--color-primary)",
              color: "var(--color-text-on-primary)",
            }}
            title="发送"
          >
            {isStreaming ? "⋯" : "↑"}
          </button>
        </div>
      </div>
    </div>
    </>
  );
}
