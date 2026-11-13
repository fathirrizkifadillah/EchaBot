"use client";
import { useCallback, useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import ChatPanel from "@/components/ChatPanel";
import { useChat } from "@/hooks/useChat";
import { useDataset } from "@/hooks/useDataset";
import { useSessions } from "@/hooks/useSessions";
import { downloadExport, getSession } from "@/lib/api";

export default function Home() {
  const chat = useChat();
  const dataset = useDataset();
  const sessions = useSessions();
  const [notice, setNotice] = useState<string | null>(null);

  const showNotice = useCallback((message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(null), 3000);
  }, []);

  // Auto-restore active session after reload
  useEffect(() => {
    if (!sessions.restored || !sessions.activeId) return;
    let cancelled = false;

    getSession(sessions.activeId).then((res) => {
      if (cancelled || !res.ok) return;
      chat.loadHistory(res.session.history || []);
      if (res.session.dataset_name) {
        dataset.setActive(
          res.session.dataset_name,
          res.session.dataset_preview || [],
          res.session.dataset_report || {}
        );
      }
    }).catch(() => { /* silent */ });

    return () => { cancelled = true; };
    // Only run once on restore
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessions.restored]);

  const handleUpload = useCallback(async (file: File) => {
    let sessionId = sessions.activeId;
    if (!sessionId) {
      sessionId = await sessions.startNew();
      if (!sessionId) {
        showNotice("Gagal membuat sesi baru.");
        return;
      }
    }
    const res = await dataset.upload(file);
    if (!res.ok) showNotice(res.message);
    else {
      await sessions.refresh();
      await sessions.loadDatasets(sessionId);
      showNotice(`${file.name} siap dianalisis`);
    }
  }, [dataset, sessions, showNotice]);

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
    if (!res.ok) showNotice(res.message);
    else {
      await sessions.refresh();
      await sessions.loadDatasets(sessionId);
      showNotice("Sample Walmart Sales siap dianalisis");
    }
  }, [dataset, sessions, showNotice]);

  const handleDatasetSelect = useCallback(async (datasetId: string) => {
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
    } else dataset.clear();
    showNotice(`Dataset aktif: ${detail.dataset_name || "tidak ada"}`);
  }, [sessions, dataset, showNotice]);

  const handleExport = useCallback(async (format: "pdf" | "xlsx") => {
    try {
      await downloadExport(format);
      showNotice(`Export ${format.toUpperCase()} berhasil diunduh`);
    } catch (error) {
      showNotice(error instanceof Error ? error.message : "Export gagal.");
    }
  }, [showNotice]);

  const handleSend = useCallback(async (text: string) => {
    await chat.send(text);
    await sessions.refresh();
  }, [chat, sessions]);

  const handleNew = useCallback(async () => {
    chat.clear();
    dataset.clear();
    await sessions.startNew();
  }, [chat, dataset, sessions]);

  const handleSelect = useCallback(async (id: string) => {
    const detail = await sessions.switchTo(id);
    if (!detail) return;
    chat.loadHistory(detail.history || []);
    if (detail.dataset_name) {
      dataset.setActive(
        detail.dataset_name,
        detail.dataset_preview || [],
        detail.dataset_report || {}
      );
    } else dataset.clear();
  }, [sessions, chat, dataset]);

  return (
    <div className="flex h-full w-full overflow-hidden">
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
      />
      <ChatPanel
        messages={chat.messages}
        sending={chat.sending}
        hasDataset={Boolean(dataset.dataset)}
        onSend={handleSend}
        onPrompt={handleSend}
        onUpload={handleUpload}
      />
      {notice && <div className="fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-lg border border-teal-400/30 bg-[#111] px-4 py-2 text-xs text-teal-300 shadow-xl">{notice}</div>}
    </div>
  );
}
