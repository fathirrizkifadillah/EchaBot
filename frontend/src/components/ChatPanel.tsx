"use client";
import { useEffect, useRef } from "react";
import MessageBubble from "@/components/MessageBubble";
import WelcomeScreen from "@/components/WelcomeScreen";
import Composer from "@/components/Composer";
import { Message } from "@/hooks/useChat";

interface ChatPanelProps {
  messages: Message[];
  sending: boolean;
  hasDataset: boolean;
  onSend: (text: string) => void;
  onPrompt: (text: string) => void;
  onUpload: (file: File) => void;
}
export default function ChatPanel({ messages, sending, hasDataset, onSend, onPrompt, onUpload }: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  return <main className="flex min-w-0 flex-1 flex-col bg-black"><header className="flex h-16 shrink-0 items-center justify-between border-b border-white/10 px-5 sm:px-8"><div><h2 className="text-sm font-medium text-zinc-200">Data Analyst</h2><p className="text-[11px] text-zinc-600">Tanya apa pun tentang data lo</p></div><div className="flex items-center gap-2 text-[11px] text-zinc-600"><span className="h-1.5 w-1.5 rounded-full bg-teal-400" />Online</div></header><div className="min-h-0 flex-1 overflow-y-auto">{messages.length === 0 ? <WelcomeScreen onPrompt={onPrompt} hasDataset={hasDataset} /> : <div className="mx-auto max-w-4xl py-4">{messages.map((message) => <MessageBubble key={message.id} message={message} />)}<div ref={bottomRef} /></div>}</div><Composer sending={sending} onSend={onSend} onUpload={onUpload} /></main>;
}
