"use client";
import { useRef, useState } from "react";
import {
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Download,
  FileSpreadsheet,
  History,
  MessageSquarePlus,
  Trash2,
  Upload,
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
}: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const acceptFile = (file?: File) => {
    if (file && /\.(csv|xlsx?|xls)$/i.test(file.name)) onUpload(file);
  };

  if (collapsed) {
    return (
      <aside className="flex w-16 shrink-0 flex-col items-center border-r border-white/10 bg-[#0a0a0a] py-5">
        <button onClick={() => setCollapsed(false)} className="rounded-lg p-2 text-zinc-500 hover:bg-white/10 hover:text-white" title="Expand sidebar">
          <ChevronRight size={18} />
        </button>
        <BarChart3 size={21} className="mt-5 text-teal-400" />
        <button onClick={onNew} className="mt-8 rounded-lg p-2 text-zinc-400 hover:bg-white/10 hover:text-white" title="Chat baru">
          <MessageSquarePlus size={19} />
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex w-[280px] shrink-0 flex-col border-r border-white/10 bg-[#0a0a0a]">
      <div className="flex h-16 items-center justify-between border-b border-white/10 px-5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-400 text-black">
            <BarChart3 size={18} strokeWidth={2.5} />
          </div>
          <span className="font-semibold tracking-tight text-white">EchaBot</span>
        </div>
        <button onClick={() => setCollapsed(true)} className="rounded-lg p-1.5 text-zinc-600 hover:bg-white/10 hover:text-zinc-300" title="Collapse sidebar">
          <ChevronLeft size={17} />
        </button>
      </div>

      <div className="p-4">
        <button onClick={onNew} className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/15 bg-white/[.03] py-2.5 text-sm font-medium text-zinc-200 transition hover:bg-white/[.08]">
          <MessageSquarePlus size={16} /> Chat baru
        </button>
      </div>

      <div className="px-4">
        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); acceptFile(e.dataTransfer.files[0]); }}
          className={`cursor-pointer rounded-xl border border-dashed p-4 text-center transition ${dragOver ? "border-teal-400 bg-teal-400/10" : "border-white/15 hover:border-white/30 hover:bg-white/[.03]"}`}
        >
          <Upload size={19} className="mx-auto mb-2 text-zinc-400" />
          <p className="text-xs text-zinc-300">{uploading ? "Memproses..." : "Upload dataset"}</p>
          <p className="mt-1 text-[11px] text-zinc-600">CSV atau Excel</p>
          <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={(e) => acceptFile(e.target.files?.[0])} />
        </div>
        <button onClick={onSample} disabled={uploading} className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg py-2 text-xs text-zinc-500 transition hover:bg-white/[.04] hover:text-teal-300 disabled:opacity-50">
          <FileSpreadsheet size={14} /> Pakai sample Walmart Sales
        </button>
      </div>

      <div className="mx-4 my-4 h-px bg-white/10" />

      {datasetName && (
        <div className="mx-4 mb-3 rounded-lg border border-teal-400/20 bg-teal-400/[.06] px-3 py-2.5">
          <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-teal-300"><span className="h-1.5 w-1.5 rounded-full bg-teal-400" />Dataset aktif</div>
          <p className="mt-1 truncate text-xs text-zinc-300">{datasetName}</p>
          {datasets.length > 1 && (
            <select
              value={datasets.find((item) => item.active)?.id || ""}
              onChange={(event) => onDatasetSelect(event.target.value)}
              className="mt-2 w-full rounded-md border border-white/10 bg-black/20 px-2 py-1.5 text-[11px] text-zinc-300 outline-none focus:border-teal-400/50"
              aria-label="Pilih dataset aktif"
            >
              {datasets.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          )}
          <div className="mt-2 flex gap-1.5">
            <button onClick={() => onExport("pdf")} className="flex flex-1 items-center justify-center gap-1 rounded-md border border-white/10 py-1.5 text-[10px] text-zinc-400 transition hover:border-teal-400/40 hover:text-teal-300"><Download size={12} /> PDF</button>
            <button onClick={() => onExport("xlsx")} className="flex flex-1 items-center justify-center gap-1 rounded-md border border-white/10 py-1.5 text-[10px] text-zinc-400 transition hover:border-teal-400/40 hover:text-teal-300"><Download size={12} /> XLSX</button>
          </div>
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col px-4">
        <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-zinc-600"><History size={13} /> Riwayat chat</div>
        <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto">
          {sessions.length === 0 ? <p className="py-4 text-center text-xs text-zinc-700">Belum ada riwayat</p> : sessions.map((s) => (
            <div key={s.id} className={`group flex items-center rounded-lg transition ${activeId === s.id ? "bg-white/[.08]" : "hover:bg-white/[.04]"}`}>
              <button onClick={() => onSelect(s.id)} className="min-w-0 flex-1 truncate px-3 py-2 text-left text-xs text-zinc-400 group-hover:text-zinc-200">{s.title || "New Chat"}</button>
              <button onClick={() => onDelete(s.id)} className="mr-1 hidden rounded p-1 text-zinc-600 hover:bg-red-400/10 hover:text-red-400 group-hover:block" title="Hapus"><Trash2 size={13} /></button>
            </div>
          ))}
        </div>
      </div>
      <div className="border-t border-white/10 px-5 py-3 text-[11px] text-zinc-700">AI Data Analyst · v2.0</div>
    </aside>
  );
}
