"use client";

import { useCallback, useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import ChatPanel from "@/components/ChatPanel";
import { useChat } from "@/hooks/useChat";
import { useDataset } from "@/hooks/useDataset";
import { useSessions } from "@/hooks/useSessions";
import { downloadExport, getSession, refreshAccessToken, logout } from "@/lib/api";
import AuthPanel from "@/components/AuthPanel";
import { X } from "lucide-react";

export default function Home() {
  const chat = useChat();
  const dataset = useDataset();
  const sessions = useSessions();
  const [notice, setNotice] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Check existing session/cookie on load; fallback directly to Guest Mode
  useEffect(() => {
    refreshAccessToken()
      .then((valid) => {
        setAuthenticated(valid);
        setAuthChecked(true);
      })
      .catch(() => {
        setAuthenticated(false);
        setAuthChecked(true);
      });
  }, []);

  const showNotice = useCallback((message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(null), 3000);
  }, []);

  const handleAuthenticated = useCallback(async () => {
    const valid = await refreshAccessToken();
    setAuthenticated(valid);
    setShowAuthModal(false);
    if (valid) {
      await sessions.refresh();
      showNotice("Berhasil masuk.");
    }
  }, [sessions, showNotice]);

  const handleLogout = useCallback(async () => {
    await logout();
    setAuthenticated(false);
    chat.clear();
    dataset.clear();
    await sessions.refresh();
    showNotice("Berhasil keluar. Beralih ke Guest mode.");
  }, [chat, dataset, sessions, showNotice]);

  // Auto-restore active session after reload
  useEffect(() => {
    if (!sessions.restored || !sessions.activeId) return;
    let cancelled = false;

    getSession(sessions.activeId)
      .then((res) => {
        if (cancelled || !res.ok) return;
        chat.loadHistory(res.session.history || []);
        if (res.session.dataset_name) {
          dataset.setActive(
            res.session.dataset_name,
            res.session.dataset_preview || [],
            res.session.dataset_report || {}
          );
        }
      })
      .catch(() => {
        /* silent */
      });

    return () => {
      cancelled = true;
    };
    // Only run once on restore
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessions.restored]);

  const handleUpload = useCallback(
    async (file: File) => {
      let sessionId = sessions.activeId;
      if (!sessionId) {
        sessionId = await sessions.startNew();
        if (!sessionId) {
          showNotice("Gagal membuat sesi baru.");
          return;
        }
      }
      const res = await dataset.upload(file);
      if (!res.ok) {
        showNotice(res.message);
      } else {
        await sessions.refresh();
        await sessions.loadDatasets(sessionId);
        showNotice(`${file.name} siap dianalisis`);
      }
    },
    [dataset, sessions, showNotice]
  );

  const handleSample = useCallback(async () => {
    let sessionId = sessions.activeId;
    if (!sessionId) {
      sessionId = await sessions.startNew();
      if (!sessionId) {
        showNotice("Gagal membuat sesi baru.");
        return;
      }
    }
    const res = await dataset.loadSample();
    if (!res.ok) {
      showNotice(res.message);
    } else {
      await sessions.refresh();
      await sessions.loadDatasets(sessionId);
      showNotice("Sample Walmart Sales siap dianalisis");
    }
  }, [dataset, sessions, showNotice]);

  const handleDatasetSelect = useCallback(
    async (datasetId: string) => {
      const detail = await sessions.switchDataset(datasetId);
      if (!detail) {
        showNotice("Gagal mengganti dataset.");
        return;
      }
      if (detail.dataset_name) {
        dataset.setActive(
          detail.dataset_name,
          detail.dataset_preview || [],
          detail.dataset_report || {}
        );
      } else {
        dataset.clear();
      }
      showNotice(`Dataset aktif: ${detail.dataset_name || "tidak ada"}`);
    },
    [sessions, dataset, showNotice]
  );

  const handleExport = useCallback(
    async (format: "pdf" | "xlsx") => {
      try {
        await downloadExport(format);
        showNotice(`Export ${format.toUpperCase()} berhasil diunduh`);
      } catch (error) {
        showNotice(error instanceof Error ? error.message : "Export gagal.");
      }
    },
    [showNotice]
  );

  const handleSend = useCallback(
    async (text: string) => {
      await chat.send(text);
      await sessions.refresh();
    },
    [chat, sessions]
  );

  const handleNew = useCallback(async () => {
    chat.clear();
    dataset.clear();
    await sessions.startNew();
  }, [chat, dataset, sessions]);

  const handleSelect = useCallback(
    async (id: string) => {
      const detail = await sessions.switchTo(id);
      if (!detail) return;
      chat.loadHistory(detail.history || []);
      if (detail.dataset_name) {
        dataset.setActive(
          detail.dataset_name,
          detail.dataset_preview || [],
          detail.dataset_report || {}
        );
      } else {
        dataset.clear();
      }
    },
    [sessions, chat, dataset]
  );

  if (!authChecked) {
    return (
      <main className="flex h-dvh items-center justify-center bg-black text-xs text-zinc-500">
        Menyiapkan workspace EchaBot...
      </main>
    );
  }

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-black text-zinc-100">
      {/* 1. Left Sidebar (Desktop + Mobile Slide-Over Drawer) */}
      <Sidebar
        sessions={sessions.sessions}
        activeId={sessions.activeId}
        datasetName={dataset.dataset?.name}
        datasets={sessions.datasets}
        uploading={dataset.uploading}
        onUpload={handleUpload}
        onDatasetSelect={handleDatasetSelect}
        onExport={handleExport}
        onSample={handleSample}
        onNew={handleNew}
        onSelect={handleSelect}
        onDelete={sessions.remove}
        isGuest={!authenticated}
        onLogin={!authenticated ? () => setShowAuthModal(true) : undefined}
        onLogout={authenticated ? handleLogout : undefined}
        mobileOpen={mobileNavOpen}
        onMobileClose={() => setMobileNavOpen(false)}
      />

      {/* 2. Main Chat Panel */}
      <ChatPanel
        messages={chat.messages}
        sending={chat.sending}
        hasDataset={Boolean(dataset.dataset)}
        onSend={handleSend}
        onPrompt={handleSend}
        onUpload={handleUpload}
        onToggleMobileNav={() => setMobileNavOpen((prev) => !prev)}
        isMobileNavOpen={mobileNavOpen}
      />

      {/* 3. Optional Authentication Modal for Guest Users */}
      {showAuthModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Modal autentikasi akun"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
        >
          <div className="relative w-full max-w-md rounded-2xl border border-white/15 bg-[#0e0e0e] p-6 shadow-2xl">
            <button
              onClick={() => setShowAuthModal(false)}
              className="absolute right-4 top-4 flex h-9 w-9 min-h-[44px] min-w-[44px] items-center justify-center rounded-xl text-zinc-400 transition hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
              aria-label="Tutup jendela login"
            >
              <X size={18} aria-hidden="true" />
            </button>
            <AuthPanel onAuthenticated={handleAuthenticated} />
          </div>
        </div>
      )}

      {/* 4. Global Notification Toast */}
      {notice && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-xl border border-teal-400/30 bg-[#111] px-4 py-2.5 text-xs font-medium text-teal-300 shadow-2xl"
        >
          {notice}
        </div>
      )}
    </div>
  );
}
