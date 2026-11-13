"use client";
import Image from "next/image";
import { useState } from "react";
import { Bot, Check, Copy, Download, User } from "lucide-react";
import DataTable from "@/components/DataTable";
import { Message } from "@/hooks/useChat";

function renderText(text: string) {
  return text.split(/(```[\s\S]*?```|\*\*.*?\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.startsWith("```") && part.endsWith("```")) return <pre key={i} className="my-2 overflow-x-auto rounded-lg bg-black/50 p-3 text-xs text-zinc-300">{part.slice(3, -3).replace(/^\w+\n/, "")}</pre>;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={i} className="rounded bg-white/10 px-1 text-xs text-teal-300">{part.slice(1, -1)}</code>;
    return <span key={i}>{part}</span>;
  });
}

export default function MessageBubble({ message }: { message: Message }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";
  const copy = async () => { await navigator.clipboard.writeText(message.content); setCopied(true); setTimeout(() => setCopied(false), 1500); };
  return (
    <div className={`group flex gap-3 px-4 py-5 sm:px-8 ${isUser ? "bg-transparent" : "bg-white/[.018]"}`}>
      <div className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${isUser ? "bg-zinc-700 text-zinc-300" : "bg-teal-400 text-black"}`}>{isUser ? <User size={15} /> : <Bot size={16} />}</div>
      <div className="min-w-0 max-w-3xl flex-1 text-sm leading-7 text-zinc-300">
        {message.loading ? <div className="flex gap-1 py-2"><i className="h-1.5 w-1.5 animate-bounce rounded-full bg-teal-400 [animation-delay:-.3s]" /><i className="h-1.5 w-1.5 animate-bounce rounded-full bg-teal-400 [animation-delay:-.15s]" /><i className="h-1.5 w-1.5 animate-bounce rounded-full bg-teal-400" /></div> : <><div className="whitespace-pre-wrap">{renderText(message.content)}</div>{message.imageUrl && (
          <Image
            src={message.imageUrl}
            alt="Visualisasi dataset"
            width={800}
            height={500}
            unoptimized
            className="mt-4 h-auto max-w-full rounded-lg border border-white/10"
          />
        )}{message.rows && message.rows.length > 0 && <DataTable rows={message.rows} />}{message.table && <DataTable rows={Object.entries(message.table).map(([key, value]) => ({ metric: key, value: String(value) }))} />}</>}
        {!message.loading && message.content && <div className="mt-2 flex gap-1 opacity-0 transition group-hover:opacity-100"><button onClick={copy} className="rounded p-1.5 text-zinc-600 hover:bg-white/10 hover:text-zinc-300" title="Copy">{copied ? <Check size={13} className="text-teal-400" /> : <Copy size={13} />}</button>{message.downloadUrl && <a href={message.downloadUrl} download className="rounded p-1.5 text-zinc-600 hover:bg-white/10 hover:text-zinc-300" title="Download"><Download size={13} /></a>}</div>}
      </div>
    </div>
  );
}
