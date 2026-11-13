"use client";
import { useState, useCallback, useRef } from "react";
import { sendMessage, ChatResponse, resolveApiUrl } from "@/lib/api";

export interface Message {
  id: string;
  role: "user" | "bot";
  content: string;
  imageUrl?: string;
  downloadUrl?: string;
  rows?: Record<string, string>[];
  table?: Record<string, string | number>;
  loading?: boolean;
}

let msgCounter = 0;
function uid() {
  return `msg-${Date.now()}-${++msgCounter}`;
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || sending) return;

      const userMsg: Message = { id: uid(), role: "user", content: text };
      const botPlaceholder: Message = {
        id: uid(),
        role: "bot",
        content: "",
        loading: true,
      };

      setMessages((prev) => [...prev, userMsg, botPlaceholder]);
      setSending(true);

      const history = messages
        .filter((m) => !m.loading)
        .map((m) => ({ role: m.role, content: m.content }));

      try {
        abortRef.current = new AbortController();
        const res: ChatResponse = await sendMessage(text, history);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botPlaceholder.id
              ? {
                  ...m,
                  content: res.message,
                  imageUrl: resolveApiUrl(res.image_url),
                  downloadUrl: resolveApiUrl(res.download_url),
                  rows: res.rows,
                  table: res.table,
                  loading: false,
                }
              : m
          )
        );
      } catch (err) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botPlaceholder.id
              ? {
                  ...m,
                  content:
                    err instanceof Error
                      ? err.message
                      : "Terjadi kesalahan.",
                  loading: false,
                }
              : m
          )
        );
      } finally {
        setSending(false);
        abortRef.current = null;
      }
    },
    [messages, sending]
  );

  const loadHistory = useCallback(
    (history: { role: string; content: string }[]) => {
      setMessages(
        history.map((h) => ({
          id: uid(),
          role: h.role as "user" | "bot",
          content: h.content,
        }))
      );
    },
    []
  );

  const clear = useCallback(() => setMessages([]), []);

  return { messages, sending, send, loadHistory, clear };
}
