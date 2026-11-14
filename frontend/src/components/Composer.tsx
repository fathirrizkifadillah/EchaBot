"use client";

import { FormEvent, forwardRef, useImperativeHandle, useRef, useState } from "react";
import { ArrowUp, Paperclip } from "lucide-react";

export interface ComposerHandle {
  focus: () => void;
  setValue: (val: string) => void;
}

interface ComposerProps {
  sending: boolean;
  onSend: (text: string) => void;
  onUpload: (file: File) => void;
  placeholder?: string;
  className?: string;
}

const Composer = forwardRef<ComposerHandle, ComposerProps>(function Composer(
  { sending, onSend, onUpload, placeholder = "Tanya tentang dataset lo...", className = "" },
  ref
) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useImperativeHandle(ref, () => ({
    focus: () => textareaRef.current?.focus(),
    setValue: (val: string) => setValue(val),
  }));

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed && !sending) {
      onSend(trimmed);
      setValue("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onUpload(file);
      e.target.value = "";
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={`w-full px-4 sm:px-8 ${className}`}
      role="region"
      aria-label="Area penulisan pesan"
    >
      <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-white/15 bg-[#0a0a0a] p-2 transition-colors duration-150 focus-within:border-teal-400/40 focus-within:ring-1 focus-within:ring-teal-400/30">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="flex h-10 w-10 min-h-[44px] min-w-[44px] shrink-0 items-center justify-center rounded-xl text-zinc-500 transition-colors hover:bg-white/10 hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
          title="Lampirkan dataset"
          aria-label="Lampirkan dataset"
        >
          <Paperclip size={18} aria-hidden="true" />
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={handleFileChange}
            aria-hidden="true"
          />
        </button>

        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={1}
          aria-label="Pesan untuk EchaBot"
          className="max-h-36 min-h-[36px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none"
        />

        <button
          type="submit"
          disabled={sending || !value.trim()}
          className="flex h-10 w-10 min-h-[44px] min-w-[44px] shrink-0 items-center justify-center rounded-xl bg-teal-400 text-black transition hover:bg-teal-300 active:scale-95 disabled:cursor-not-allowed disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
          title="Kirim pesan"
          aria-label="Kirim pesan"
        >
          <ArrowUp size={18} strokeWidth={2.5} aria-hidden="true" />
        </button>
      </div>

      <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-zinc-600">
        EchaBot dapat membuat kesalahan. Verifikasi insight penting sebelum digunakan.
      </p>
    </form>
  );
});

export default Composer;
