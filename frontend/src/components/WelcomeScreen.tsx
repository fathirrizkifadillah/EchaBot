import { BarChart3, FileText, LineChart, Sparkles } from "lucide-react";

interface WelcomeScreenProps { onPrompt: (text: string) => void; hasDataset: boolean; }

export default function WelcomeScreen({ onPrompt, hasDataset }: WelcomeScreenProps) {
  const prompts = hasDataset ? [
    { icon: BarChart3, label: "Ringkasan dataset", text: "Buatkan ringkasan dataset ini" },
    { icon: LineChart, label: "Lihat korelasi", text: "Tampilkan correlation heatmap" },
    { icon: FileText, label: "Cek kualitas data", text: "Jelaskan preprocessing dataset ini" },
  ] : [];
  return <div className="flex flex-1 flex-col items-center justify-center px-6 pb-20 text-center"><div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-teal-400/30 bg-teal-400/10 text-teal-300"><Sparkles size={26} /></div><h1 className="text-2xl font-semibold tracking-tight text-white">Apa yang ingin lo analisis?</h1><p className="mt-2 max-w-md text-sm text-zinc-500">Upload dataset CSV atau Excel, lalu tanyakan apa pun tentang datanya.</p>{!hasDataset && <p className="mt-6 rounded-lg border border-white/10 bg-white/[.03] px-4 py-2 text-xs text-zinc-600">Mulai dengan upload dataset atau pakai sample Walmart Sales.</p>}{prompts.length > 0 && <div className="mt-8 flex flex-wrap justify-center gap-2">{prompts.map(({ icon: Icon, label, text }) => <button key={label} onClick={() => onPrompt(text)} className="flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-zinc-400 transition hover:border-teal-400/40 hover:bg-teal-400/5 hover:text-teal-300"><Icon size={14} />{label}</button>)}</div>}</div>;
}
