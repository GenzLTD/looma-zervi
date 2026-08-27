/**
 * useChatNonStreaming - Non-streaming chat for SaaS RAG knowledge base.
 * Replacement for useChat to fix contract inconsistency with backend.
 * Owner: Jason (for MVP pressure test fix)
 *
 * Uses createChatApi().ask() instead of SSE streaming.
 * Backend compatibility: matches mini-program and shared-core contract.
 */
import { useState, useCallback, useMemo } from "react";
import { ApiError, createChatApi, type DocSource as ApiDocSource } from "@looma/shared-core";
import { createSaasApiClient } from "../../api/saasApiClient";
import { useSaasAuthStore } from "../auth/authStore";

export interface DocSource {
  filename: string;
  chunk_id?: string;
  score?: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  sources?: DocSource[];
}

interface UseChatNonStreamingOptions {
  mode?: "chat" | "deepseek" | "fast";
  /** Pre-check / retry when backend returns consent_required */
  ensureAskConsent?: () => Promise<boolean>;
  /** Saved match report id for summary-level Ask context */
  reportId?: string | null;
  /** Default true: backend may attach latest report when reportId omitted */
  useLatestReport?: boolean;
}

let _uid = 0;
function uid(): string {
  return `msg_${Date.now()}_${++_uid}`;
}

function mapSources(sources?: ApiDocSource[]): DocSource[] | undefined {
  if (!sources?.length) return undefined;
  return sources.map((s, i) => ({
    filename: s.chunk_text?.slice(0, 80) || `Source ${i + 1}`,
    score: s.score,
  }));
}

function errorBody(err: unknown): Record<string, any> {
  if (err instanceof ApiError) return err.body ?? {};
  if (err && typeof err === "object" && "body" in err) {
    const body = (err as { body?: Record<string, any> }).body;
    if (body && typeof body === "object") return body;
  }
  return {};
}

function errorStatus(err: unknown): number | undefined {
  if (err instanceof ApiError) return err.status;
  if (err && typeof err === "object" && "status" in err) {
    const status = (err as { status?: number }).status;
    return typeof status === "number" ? status : undefined;
  }
  return undefined;
}

export function useChatNonStreaming(options: UseChatNonStreamingOptions = {}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quotaExhausted, setQuotaExhausted] = useState(false);
  const fetchQuota = useSaasAuthStore((s) => s.fetchQuota);

  const apiClient = useMemo(() => createSaasApiClient(), []);
  const chatApi = useMemo(() => createChatApi(apiClient), [apiClient]);

  /** Non-streaming request using createChatApi().ask() */
  const send = useCallback(
    async (query: string) => {
      setError(null);
      setQuotaExhausted(false);
      setIsLoading(true);

      const userMsg: ChatMessage = {
        id: uid(),
        role: "user",
        content: query,
        created_at: new Date().toISOString(),
      };
      const assistantId = uid();

      setMessages((prev) => [
        ...prev,
        userMsg,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          created_at: new Date().toISOString(),
        },
      ]);

      const attemptRequest = async (): Promise<void> => {
        try {
          const mode = options.mode ?? "chat";
          // 对话模式带多轮；深度带少量上下文；快速不带历史以降低延迟
          const historyLimit = mode === "chat" ? 10 : mode === "deepseek" ? 4 : 0;
          const response = await chatApi.ask({
            query,
            mode,
            session_history:
              historyLimit > 0
                ? messages.slice(-historyLimit).map((m) => ({
                    role: m.role,
                    content: m.content,
                  }))
                : undefined,
            report_id: options.reportId || undefined,
            use_latest_report: options.useLatestReport ?? true,
          });

          setMessages((prev) =>
            prev.map((m): ChatMessage =>
              m.id === assistantId
                ? {
                    ...m,
                    content: response.answer,
                    sources: mapSources(response.sources),
                  }
                : m
            )
          );

          void fetchQuota();
          setIsLoading(false);
        } catch (err: unknown) {
          const status = errorStatus(err);
          const errData = errorBody(err);
          const errMsg =
            (err instanceof Error && err.message) || "请求失败";

          // Handle consent required (single re-attempt after consent — not a quota burn loop)
          if (
            status === 403 &&
            errData.error === "consent_required" &&
            options.ensureAskConsent
          ) {
            const allowed = await options.ensureAskConsent();
            if (allowed) return attemptRequest();
            setError(errData.message || "需要授权后才能使用 AI 问答");
            setIsLoading(false);
            return;
          }

          // Handle quota exhausted (429)
          if (status === 429 || errData.error === "quota_exceeded") {
            setError(errData.message || "当日配额已用尽");
            setQuotaExhausted(true);
            void fetchQuota();
            setIsLoading(false);
            return;
          }

          // Never auto-retry: each /v1/ask consumes quota server-side.
          setError(errData.message || errMsg);
          void fetchQuota();
          setIsLoading(false);
        }
      };

      await attemptRequest();
    },
    [
      messages,
      options.mode,
      options.ensureAskConsent,
      options.reportId,
      options.useLatestReport,
      chatApi,
      fetchQuota,
    ]
  );

  const clear = useCallback(() => {
    setMessages([]);
    setError(null);
    setQuotaExhausted(false);
    setIsLoading(false);
  }, []);

  const resetQuotaError = useCallback(() => {
    setError(null);
    setQuotaExhausted(false);
  }, []);

  return {
    messages,
    isStreaming: isLoading, // Keep same interface as useChat
    error,
    quotaExhausted,
    sendStream: send, // Keep same interface as useChat
    clear,
    resetQuotaError,
  };
}
