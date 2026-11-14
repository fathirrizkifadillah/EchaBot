"use client";
import { useState, useCallback, useEffect } from "react";
import {
  listSessions,
  getSession,
  createSession,
  deleteSession as apiDeleteSession,
  listDatasets,
  activateDataset as apiActivateDataset,
  setActiveSessionId,
  DatasetInfo,
  SessionInfo,
} from "@/lib/api";

const STORAGE_KEY = "echabot_active_session";

export function useSessions() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [restored, setRestored] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);

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
      if (res.ok) {
        setSessions(res.sessions);
        setUnauthorized(false);
      }
    } catch (error) {
      if (error instanceof Error && "status" in error && error.status === 401) {
        setUnauthorized(true);
      }
    }
  }, []);

  const loadDatasets = useCallback(async (id: string) => {
    try {
      const res = await listDatasets(id);
      if (res.ok) setDatasets(res.datasets);
      return res.ok ? res.datasets : [];
    } catch {
      setDatasets([]);
      return [];
    }
  }, []);

  // On mount: load session list, restore last active session
  useEffect(() => {
    let cancelled = false;

    listSessions()
      .then((res) => {
        if (cancelled) return;
        if (res.ok) {
          setSessions(res.sessions);
          setUnauthorized(false);
          const savedId = sessionStorage.getItem(STORAGE_KEY);
          if (savedId && res.sessions?.some((s) => s.id === savedId)) {
            setActiveId(savedId);
            setActiveSessionId(savedId);
            loadDatasets(savedId);
          }
        }
        setRestored(true);
      })
      .catch((error) => {
        if (error instanceof Error && "status" in error && error.status === 401) {
          setUnauthorized(true);
        }
        setRestored(true);
      });

    return () => { cancelled = true; };
  }, [loadDatasets]);

  const switchDataset = useCallback(
    async (datasetId: string) => {
      if (!activeId) return null;
      setLoading(true);
      try {
        const res = await apiActivateDataset(activeId, datasetId);
        if (!res.ok) return null;
        setDatasets(res.datasets);
        const detail = await getSession(activeId);
        return detail.ok ? detail.session : null;
      } catch {
        return null;
      } finally {
        setLoading(false);
      }
    },
    [activeId]
  );

  const switchTo = useCallback(
    async (id: string) => {
      setLoading(true);
      try {
        const res = await getSession(id);
        if (!res.ok) return null;
        updateActiveId(id);
        await loadDatasets(id);
        return res.session;
      } catch {
        return null;
      } finally {
        setLoading(false);
      }
    },
    [loadDatasets, updateActiveId]
  );

  const startNew = useCallback(async () => {
    try {
      const res = await createSession();
      if (res.ok) {
        setDatasets([]);
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

  return {
    sessions,
    activeId,
    datasets,
    loading,
    restored,
    unauthorized,
    refresh,
    loadDatasets,
    switchTo,
    switchDataset,
    startNew,
    remove,
  };
}
