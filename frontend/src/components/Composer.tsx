"use client";
import { FormEvent, useRef, useState } from "react";
import { ArrowUp, Paperclip } from "lucide-react";

interface ComposerProps { sending: boolean; onSend: (text: string) => void; onUpload: (file: File) => void; }
export default function Composer({ sending, onSend, onUpload }: ComposerProps) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const submit = (e: FormEvent) => { e.preventDefault(); if (value.trim() && !sending) { onSend(value.trim()); setValue(""); } };
  return <form onSubmit={submit} className="border-t border-white/10 bg-[#000] px-4 py-4 sm:px-8"><div className="mx-auto flex max-w-3xl items-end gap-2 rounded-xl border border-white/15 bg-[#0a0a0a] p-2 transition focus-within:border-white/30"><button type="button" onClick={() => inputRef.current?.click()} className="mb-0.5 rounded-lg p-2 text-zinc-600 hover:bg-white/10 hover:text-zinc-300" title="Lampirkan dataset"><Paperclip size={17} /><input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={(e) => { if (e.target.files?.[0]) onUpload(e.target.files[0]); }} /></button><textarea value={value} onChange={(e) => setValue(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(e); } }} placeholder="Tanya tentang dataset lo..." rows={1} className="max-h-32 min-h-[28px] flex-1 resize-none bg-transparent px-1 py-1.5 text-sm text-zinc-200 outline-none placeholder:text-zinc-600" /><button type="submit" disabled={sending || !value.trim()} className="rounded-lg bg-teal-400 p-2 text-black transition hover:bg-teal-300 disabled:cursor-not-allowed disabled:opacity-30"><ArrowUp size={17} strokeWidth={2.5} /></button></div><p className="mx-auto mt-2 max-w-3xl text-center text-[10px] text-zinc-700">EchaBot dapat membuat kesalahan. Verifikasi insight penting sebelum digunakan.</p></form>;
}
