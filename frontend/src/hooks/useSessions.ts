"use client";
import { useState, useCallback, useEffect } from "react";
import {
  listSessions,
  getSession,
  createSession,
  deleteSession as apiDeleteSession,
  SessionInfo,
} from "@/lib/api";

export function useSessions() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await listSessions();
      if (res.ok) setSessions(res.sessions);
    } catch {
      /* silent */
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const switchTo = useCallback(
    async (id: string) => {
      setLoading(true);
      try {
        const res = await getSession(id);
        setActiveId(id);
        return res.ok ? res.session : null;
      } catch {
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const startNew = useCallback(async () => {
    try {
      const res = await createSession();
      if (res.ok) {
        setActiveId(res.session_id);
        await refresh();
        return res.session_id;
      }
    } catch {
      /* silent */
    }
    return null;
  }, [refresh]);

  const remove = useCallback(
    async (id: string) => {
      try {
        await apiDeleteSession(id);
        setSessions((prev) => prev.filter((s) => s.id !== id));
        if (activeId === id) setActiveId(null);
      } catch {
        /* silent */
      }
    },
    [activeId]
  );

  return { sessions, activeId, loading, refresh, switchTo, startNew, remove };
}
