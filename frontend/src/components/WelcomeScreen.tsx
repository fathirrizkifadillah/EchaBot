import { BarChart3, FileText, LineChart, Sparkles } from "lucide-react";

interface WelcomeScreenProps {
  onPrompt: (text: string) => void;
  hasDataset: boolean;
  className?: string;
}

export function WelcomeHeader({
  hasDataset,
  className = "",
}: {
  hasDataset: boolean;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center ${className}`}
      role="banner"
      aria-label="Pengenalan EchaBot"
    >
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-teal-400/30 bg-teal-400/10 text-teal-300 shadow-sm">
        <Sparkles size={24} aria-hidden="true" />
      </div>

      <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
        Apa yang ingin lo analisis?
      </h1>

      <p className="mt-2 max-w-md text-sm text-zinc-400">
        Upload dataset CSV atau Excel, lalu tanyakan apa pun tentang datanya.
      </p>

      {!hasDataset && (
        <p className="mt-4 rounded-lg border border-white/10 bg-white/[.03] px-3.5 py-1.5 text-xs text-zinc-500">
          Mulai dengan upload dataset atau pakai sample Walmart Sales di menu samping.
        </p>
      )}
    </div>
  );
}

export function WelcomePrompts({
  onPrompt,
  hasDataset,
  className = "",
}: {
  onPrompt: (text: string) => void;
  hasDataset: boolean;
  className?: string;
}) {
  if (!hasDataset) return null;

  const prompts = [
    {
      icon: BarChart3,
      label: "Ringkasan dataset",
      text: "Buatkan ringkasan dataset ini",
    },
    {
      icon: LineChart,
      label: "Lihat korelasi",
      text: "Tampilkan correlation heatmap",
    },
    {
      icon: FileText,
      label: "Cek kualitas data",
      text: "Jelaskan preprocessing dataset ini",
    },
  ];

  return (
    <div className={`flex flex-wrap justify-center gap-2 px-4 ${className}`}>
      {prompts.map(({ icon: Icon, label, text }) => (
        <button
          key={label}
          type="button"
          onClick={() => onPrompt(text)}
          className="flex min-h-[44px] cursor-pointer items-center gap-2 rounded-xl border border-white/10 bg-[#0d0d0d] px-3.5 py-2 text-xs text-zinc-300 transition-colors duration-150 hover:border-teal-400/40 hover:bg-teal-400/5 hover:text-teal-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400 active:scale-95"
          aria-label={`Prompt cepat: ${label}`}
        >
          <Icon size={14} className="text-teal-400" aria-hidden="true" />
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}

export default function WelcomeScreen({
  onPrompt,
  hasDataset,
  className = "",
}: WelcomeScreenProps) {
  return (
    <div
      className={`flex flex-1 flex-col items-center justify-center px-6 pb-20 text-center ${className}`}
      role="region"
      aria-label="Layar selamat datang"
    >
      <WelcomeHeader hasDataset={hasDataset} />
      <WelcomePrompts onPrompt={onPrompt} hasDataset={hasDataset} className="mt-6" />
    </div>
  );
}
