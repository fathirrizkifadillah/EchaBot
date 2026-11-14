"use client";

import { useEffect, useRef, useState } from "react";
import {
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Download,
  FileSpreadsheet,
  History,
  LogIn,
  LogOut,
  MessageSquarePlus,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { DatasetInfo, SessionInfo } from "@/lib/api";

interface SidebarProps {
  sessions: SessionInfo[];
  activeId: string | null;
  datasetName?: string;
  datasets: DatasetInfo[];
  uploading: boolean;
  onUpload: (file: File) => void;
  onDatasetSelect: (id: string) => void;
  onExport: (format: "pdf" | "xlsx") => void;
  onSample: () => void;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onLogout?: () => void;
  onLogin?: () => void;
  isGuest?: boolean;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export default function Sidebar({
  sessions,
  activeId,
  datasetName,
  datasets,
  uploading,
  onUpload,
  onDatasetSelect,
  onExport,
  onSample,
  onNew,
  onSelect,
  onDelete,
  onLogout,
  onLogin,
  isGuest = true,
  mobileOpen = false,
  onMobileClose,
}: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const acceptFile = (file?: File) => {
    if (file && /\.(csv|xlsx?|xls)$/i.test(file.name)) {
      onUpload(file);
      if (mobileOpen && onMobileClose) onMobileClose();
    }
  };

  // Keyboard navigation: Escape key closes mobile drawer
  useEffect(() => {
    if (!mobileOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onMobileClose?.();
      }

      // Simple, robust focus trap inside mobile drawer
      if (e.key === "Tab" && drawerRef.current) {
        const focusables = drawerRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mobileOpen, onMobileClose]);

  // Lock body scroll while mobile drawer is open
  useEffect(() => {
    if (mobileOpen) {
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      // Auto-focus the close button or first element on drawer open
      closeButtonRef.current?.focus();
      return () => {
        document.body.style.overflow = originalOverflow;
      };
    }
  }, [mobileOpen]);

  const sidebarContent = (isMobile: boolean) => (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-white/10 px-5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-400 text-black">
            <BarChart3 size={18} strokeWidth={2.5} aria-hidden="true" />
          </div>
          <span className="font-semibold tracking-tight text-white">EchaBot</span>
          {isGuest && (
            <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-medium text-zinc-400">
              Guest
            </span>
          )}
        </div>

        {isMobile ? (
          <button
            ref={closeButtonRef}
            onClick={onMobileClose}
            className="flex h-10 w-10 min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-zinc-400 transition hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
            title="Tutup menu navigasi"
            aria-label="Tutup menu navigasi"
          >
            <X size={18} aria-hidden="true" />
          </button>
        ) : (
          <button
            onClick={() => setCollapsed(true)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-zinc-500 transition hover:bg-white/10 hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
            title="Ciutkan menu navigasi"
            aria-label="Ciutkan menu navigasi"
          >
            <ChevronLeft size={17} aria-hidden="true" />
          </button>
        )}
      </div>

      {/* Action: Chat Baru */}
      <div className="p-4">
        <button
          onClick={() => {
            onNew();
            if (isMobile && onMobileClose) onMobileClose();
          }}
          className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/[.04] py-2.5 text-sm font-medium text-zinc-200 transition hover:bg-white/[.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400 active:scale-95"
          aria-label="Mulai chat baru"
        >
          <MessageSquarePlus size={16} aria-hidden="true" />
          <span>Chat baru</span>
        </button>
      </div>

      {/* Dataset Upload Area */}
      <div className="px-4">
        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            acceptFile(e.dataTransfer.files[0]);
          }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          aria-label="Upload dataset file CSV atau Excel"
          className={`cursor-pointer rounded-xl border border-dashed p-4 text-center transition-colors duration-150 ${
            dragOver
              ? "border-teal-400 bg-teal-400/10"
              : "border-white/15 hover:border-white/30 hover:bg-white/[.03]"
          } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400`}
        >
          <Upload size={18} className="mx-auto mb-2 text-zinc-400" aria-hidden="true" />
          <p className="text-xs font-medium text-zinc-300">
            {uploading ? "Memproses..." : "Upload dataset"}
          </p>
          <p className="mt-1 text-[11px] text-zinc-500">CSV atau Excel (.xlsx, .xls)</p>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={(e) => acceptFile(e.target.files?.[0])}
            aria-hidden="true"
          />
        </div>

        <button
          onClick={() => {
            onSample();
            if (isMobile && onMobileClose) onMobileClose();
          }}
          disabled={uploading}
          className="mt-2 flex min-h-[44px] w-full items-center justify-center gap-2 rounded-lg py-2 text-xs text-zinc-400 transition hover:bg-white/[.04] hover:text-teal-300 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
          aria-label="Gunakan sample dataset Walmart Sales"
        >
          <FileSpreadsheet size={14} aria-hidden="true" />
          <span>Pakai sample Walmart Sales</span>
        </button>
      </div>

      <div className="mx-4 my-3 h-px bg-white/10" role="separator" />

      {/* Active Dataset & Export Controls */}
      {datasetName && (
        <div className="mx-4 mb-3 rounded-xl border border-teal-400/20 bg-teal-400/[.06] px-3.5 py-3">
          <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-teal-300">
            <span className="h-1.5 w-1.5 rounded-full bg-teal-400" />
            <span>Dataset aktif</span>
          </div>
          <p className="mt-1 truncate text-xs font-medium text-zinc-200" title={datasetName}>
            {datasetName}
          </p>

          {datasets.length > 1 && (
            <select
              value={datasets.find((item) => item.active)?.id || ""}
              onChange={(event) => onDatasetSelect(event.target.value)}
              className="mt-2 w-full rounded-md border border-white/15 bg-black/40 px-2 py-1.5 text-[11px] text-zinc-300 outline-none focus:border-teal-400/50"
              aria-label="Pilih dataset aktif"
            >
              {datasets.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          )}

          <div className="mt-2.5 flex gap-2">
            <button
              onClick={() => onExport("pdf")}
              className="flex min-h-[36px] flex-1 items-center justify-center gap-1 rounded-lg border border-white/10 py-1.5 text-[11px] text-zinc-300 transition hover:border-teal-400/40 hover:text-teal-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
              aria-label="Download export PDF"
            >
              <Download size={13} aria-hidden="true" />
              <span>PDF</span>
            </button>
            <button
              onClick={() => onExport("xlsx")}
              className="flex min-h-[36px] flex-1 items-center justify-center gap-1 rounded-lg border border-white/10 py-1.5 text-[11px] text-zinc-300 transition hover:border-teal-400/40 hover:text-teal-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
              aria-label="Download export XLSX"
            >
              <Download size={13} aria-hidden="true" />
              <span>XLSX</span>
            </button>
          </div>
        </div>
      )}

      {/* Chat History List */}
      <div className="flex min-h-0 flex-1 flex-col px-4">
        <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-zinc-500">
          <History size={13} aria-hidden="true" />
          <span>Riwayat chat</span>
        </div>

        <div className="min-h-0 flex-1 space-y-1 overflow-y-auto">
          {sessions.length === 0 ? (
            <p className="py-4 text-center text-xs text-zinc-600">Belum ada riwayat</p>
          ) : (
            sessions.map((s) => (
              <div
                key={s.id}
                className={`group flex items-center rounded-lg transition-colors ${
                  activeId === s.id ? "bg-white/[.08]" : "hover:bg-white/[.04]"
                }`}
              >
                <button
                  onClick={() => {
                    onSelect(s.id);
                    if (isMobile && onMobileClose) onMobileClose();
                  }}
                  className="min-h-[38px] min-w-0 flex-1 truncate px-3 py-2 text-left text-xs text-zinc-300 transition-colors group-hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
                  aria-label={`Buka chat: ${s.title || "New Chat"}`}
                >
                  {s.title || "New Chat"}
                </button>
                <button
                  onClick={() => onDelete(s.id)}
                  className="mr-1 hidden h-7 w-7 items-center justify-center rounded p-1 text-zinc-500 hover:bg-red-400/10 hover:text-red-400 group-hover:flex focus-visible:flex focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-400"
                  title="Hapus sesi chat"
                  aria-label={`Hapus sesi: ${s.title || "New Chat"}`}
                >
                  <Trash2 size={13} aria-hidden="true" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Footer Profile / Login / Logout */}
      <div className="border-t border-white/10 px-4 py-3">
        {onLogin && (
          <button
            onClick={() => {
              onLogin();
              if (isMobile && onMobileClose) onMobileClose();
            }}
            className="mb-2 flex min-h-[44px] w-full items-center gap-2 rounded-xl border border-teal-400/30 bg-teal-400/10 px-3 py-2 text-xs font-medium text-teal-300 transition hover:bg-teal-400/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
            aria-label="Masuk dengan akun"
          >
            <LogIn size={14} aria-hidden="true" />
            <span>Masuk / Login (Opsional)</span>
          </button>
        )}

        {onLogout && (
          <button
            onClick={() => {
              onLogout();
              if (isMobile && onMobileClose) onMobileClose();
            }}
            className="mb-2 flex min-h-[44px] w-full items-center gap-2 rounded-xl px-2 py-2 text-xs text-zinc-400 transition hover:bg-white/[.04] hover:text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
            aria-label="Keluar dari akun"
          >
            <LogOut size={14} aria-hidden="true" />
            <span>Keluar</span>
          </button>
        )}

        <p className="px-1 text-[11px] text-zinc-600">AI Data Analyst · v2.0</p>
      </div>
    </div>
  );

  return (
    <>
      {/* 1. Mobile & Tablet Backdrop Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/80 backdrop-blur-sm transition-opacity duration-300 lg:hidden"
          onClick={onMobileClose}
          aria-hidden="true"
        />
      )}

      {/* 2. Mobile & Tablet Drawer (Slide-Over) */}
      <div
        ref={drawerRef}
        id="mobile-sidebar-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Navigasi EchaBot"
        className={`fixed inset-y-0 left-0 z-50 flex w-[280px] max-w-[85vw] flex-col border-r border-white/10 bg-[#0a0a0a] shadow-2xl transition-transform duration-300 ease-out lg:hidden ${
          mobileOpen ? "translate-x-0" : "-translate-x-full pointer-events-none"
        }`}
      >
        {sidebarContent(true)}
      </div>

      {/* 3. Desktop Collapsed Sidebar */}
      {collapsed && (
        <aside
          className="hidden w-16 shrink-0 flex-col items-center border-r border-white/10 bg-[#0a0a0a] py-5 lg:flex"
          aria-label="Navigasi ringkas"
        >
          <button
            onClick={() => setCollapsed(false)}
            className="flex h-10 w-10 items-center justify-center rounded-lg text-zinc-400 transition hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
            title="Perluas sidebar"
            aria-label="Perluas sidebar"
          >
            <ChevronRight size={18} aria-hidden="true" />
          </button>
          <BarChart3 size={20} className="mt-5 text-teal-400" aria-hidden="true" />
          <button
            onClick={onNew}
            className="mt-8 flex h-10 w-10 items-center justify-center rounded-lg text-zinc-400 transition hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
            title="Chat baru"
            aria-label="Chat baru"
          >
            <MessageSquarePlus size={18} aria-hidden="true" />
          </button>
        </aside>
      )}

      {/* 4. Desktop Full Sidebar */}
      {!collapsed && (
        <aside
          className="hidden w-[280px] shrink-0 flex-col border-r border-white/10 bg-[#0a0a0a] lg:flex"
          aria-label="Navigasi sidebar"
        >
          {sidebarContent(false)}
        </aside>
      )}
    </>
  );
}
