"use client";
import { useCallback, useState } from "react";
import Sidebar from "@/components/Sidebar";
import ChatPanel from "@/components/ChatPanel";
import { useChat } from "@/hooks/useChat";
import { useDataset } from "@/hooks/useDataset";
import { useSessions } from "@/hooks/useSessions";

export default function Home() {
  const chat = useChat();
  const dataset = useDataset();
  const sessions = useSessions();
  const [notice, setNotice] = useState<string | null>(null);

  const showNotice = useCallback((message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(null), 3000);
  }, []);

  const handleUpload = useCallback(async (file: File) => {
    const res = await dataset.upload(file);
    if (!res.ok) showNotice(res.message);
    else showNotice(`${file.name} siap dianalisis`);
  }, [dataset, showNotice]);

  const handleSample = useCallback(async () => {
    const res = await dataset.loadSample();
    if (!res.ok) showNotice(res.message);
    else showNotice("Sample Walmart Sales siap dianalisis");
  }, [dataset, showNotice]);

  const handleNew = useCallback(async () => {
    chat.clear();
    dataset.clear();
    await sessions.startNew();
  }, [chat, dataset, sessions]);

  const handleSelect = useCallback(async (id: string) => {
    const detail = await sessions.switchTo(id);
    if (detail) chat.loadHistory(detail.history || []);
  }, [sessions, chat]);

  return (
    <div className="flex h-full w-full overflow-hidden">
      <Sidebar
        sessions={sessions.sessions}
        activeId={sessions.activeId}
        datasetName={dataset.dataset?.name}
        uploading={dataset.uploading}
        onUpload={handleUpload}
        onSample={handleSample}
        onNew={handleNew}
        onSelect={handleSelect}
        onDelete={sessions.remove}
      />
      <ChatPanel
        messages={chat.messages}
        sending={chat.sending}
        hasDataset={Boolean(dataset.dataset)}
        onSend={chat.send}
        onPrompt={chat.send}
        onUpload={handleUpload}
      />
      {notice && <div className="fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-lg border border-teal-400/30 bg-[#111] px-4 py-2 text-xs text-teal-300 shadow-xl">{notice}</div>}
    </div>
  );
}
