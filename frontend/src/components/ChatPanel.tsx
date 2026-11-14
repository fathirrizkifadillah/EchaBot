"use client";

import { useEffect, useRef } from "react";
import { Menu } from "lucide-react";
import MessageBubble from "@/components/MessageBubble";
import Composer, { ComposerHandle } from "@/components/Composer";
import { WelcomeHeader, WelcomePrompts } from "@/components/WelcomeScreen";
import { Message } from "@/hooks/useChat";

interface ChatPanelProps {
  messages: Message[];
  sending: boolean;
  hasDataset: boolean;
  onSend: (text: string) => void;
  onPrompt: (text: string) => void;
  onUpload: (file: File) => void;
  onToggleMobileNav?: () => void;
  isMobileNavOpen?: boolean;
}

export default function ChatPanel({
  messages,
  sending,
  hasDataset,
  onSend,
  onPrompt,
  onUpload,
  onToggleMobileNav,
  isMobileNavOpen = false,
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<ComposerHandle>(null);
  const isWelcome = messages.length === 0;

  // Auto-scroll to latest message
  useEffect(() => {
    if (!isWelcome) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isWelcome]);

  const handlePromptSelect = (text: string) => {
    onPrompt(text);
    // Keep focus active in composer
    composerRef.current?.focus();
  };

  return (
    <main
      className="relative flex min-w-0 flex-1 flex-col bg-black h-dvh overflow-hidden"
      role="main"
      aria-label="Area percakapan data analyst"
    >
      {/* 1. Topbar Header */}
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-white/10 px-4 sm:px-8">
        <div className="flex items-center gap-3">
          {/* Mobile/Tablet Navigation Hamburger Button */}
          <button
            type="button"
            onClick={onToggleMobileNav}
            className="flex h-10 w-10 min-h-[44px] min-w-[44px] items-center justify-center rounded-xl text-zinc-400 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400 lg:hidden"
            aria-label={isMobileNavOpen ? "Tutup menu navigasi" : "Buka menu navigasi"}
            aria-expanded={isMobileNavOpen}
            aria-controls="mobile-sidebar-drawer"
          >
            <Menu size={20} aria-hidden="true" />
          </button>

          <div>
            <h2 className="text-sm font-semibold tracking-tight text-zinc-100">
              Data Analyst
            </h2>
            <p className="text-[11px] text-zinc-500">Tanya apa pun tentang data lo</p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-zinc-400">
          <span className="h-1.5 w-1.5 rounded-full bg-teal-400 animate-pulse" aria-hidden="true" />
          <span>Online</span>
        </div>
      </header>

      {/* 2. Main Chat Canvas & Centered Welcome Area */}
      <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
        {/* Messages Stream View */}
        <div
          className={`flex-1 overflow-y-auto px-4 py-4 transition-opacity duration-300 ${
            isWelcome ? "pointer-events-none opacity-0" : "opacity-100"
          }`}
          aria-live="polite"
        >
          <div className="mx-auto max-w-4xl space-y-4">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Welcome Hero Content (Title, Subtitle) */}
        <div
          className={`pointer-events-none absolute inset-x-0 top-0 flex flex-col items-center justify-center px-4 transition-all duration-300 ease-out motion-reduce:transition-none ${
            isWelcome
              ? "opacity-100 translate-y-0"
              : "opacity-0 -translate-y-8"
          }`}
          style={{ height: "calc(50% + 20px)" }}
        >
          <div className="pointer-events-auto w-full max-w-xl">
            <WelcomeHeader hasDataset={hasDataset} />
          </div>
        </div>

        {/* Unified Composer Dock with Centered Welcome Transition */}
        <div
          className={`relative w-full transition-transform duration-300 ease-out motion-reduce:transition-none ${
            isWelcome
              ? "-translate-y-[calc(50dvh-130px)] sm:-translate-y-[calc(50dvh-150px)]"
              : "translate-y-0 border-t border-white/10 bg-black pb-3 pt-3"
          }`}
        >
          <Composer
            ref={composerRef}
            sending={sending}
            onSend={onSend}
            onUpload={onUpload}
          />

          {/* Prompt suggestions positioned under the centered composer */}
          <div
            className={`mt-4 transition-all duration-300 ease-out motion-reduce:transition-none ${
              isWelcome
                ? "opacity-100 translate-y-0"
                : "pointer-events-none opacity-0 -translate-y-2 hidden"
            }`}
          >
            <WelcomePrompts onPrompt={handlePromptSelect} hasDataset={hasDataset} />
          </div>
        </div>
      </div>
    </main>
  );
}
