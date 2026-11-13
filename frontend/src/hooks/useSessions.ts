"use client";
import { useState, useCallback, useEffect } from "react";
import {
  listSessions,
  getSession,
  createSession,
  deleteSession as apiDeleteSession,
  setActiveSessionId,
  SessionInfo,
} from "@/lib/api";

const STORAGE_KEY = "echabot_active_session";

export function useSessions() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [restored, setRestored] = useState(false);

  // Sync module-level activeSessionId with state
  const updateActiveId = useCallback((id: string | null) => {
    setActiveId(id);
    setActiveSessionId(id);
    if (id) sessionStorage.setItem(STORAGE_KEY, id);
    else sessionStorage.removeItem(STORAGE_KEY);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const res = await listSessions();
      if (res.ok) setSessions(res.sessions);
    } catch {
      /* silent */
    }
  }, []);

  // On mount: load session list, restore last active session
  useEffect(() => {
    let cancelled = false;

    listSessions()
      .then((res) => {
        if (cancelled) return;
        if (res.ok) setSessions(res.sessions);

        const savedId = sessionStorage.getItem(STORAGE_KEY);
        if (savedId && res.sessions?.some((s) => s.id === savedId)) {
          setActiveId(savedId);
          setActiveSessionId(savedId);
        }
        setRestored(true);
      })
      .catch(() => {
        setRestored(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const switchTo = useCallback(
    async (id: string) => {
      setLoading(true);
      try {
        const res = await getSession(id);
        updateActiveId(id);
        return res.ok ? res.session : null;
      } catch {
        return null;
      } finally {
        setLoading(false);
      }
    },
    [updateActiveId]
  );

  const startNew = useCallback(async () => {
    try {
      const res = await createSession();
      if (res.ok) {
        updateActiveId(res.session_id);
        await refresh();
        return res.session_id;
      }
    } catch {
      /* silent */
    }
    return null;
  }, [refresh, updateActiveId]);

  const remove = useCallback(
    async (id: string) => {
      try {
        await apiDeleteSession(id);
        setSessions((prev) => prev.filter((s) => s.id !== id));
        if (activeId === id) updateActiveId(null);
      } catch {
        /* silent */
      }
    },
    [activeId, updateActiveId]
  );

  return { sessions, activeId, loading, restored, refresh, switchTo, startNew, remove };
}
