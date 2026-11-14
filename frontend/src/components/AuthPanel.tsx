"use client";

import { FormEvent, useState } from "react";
import { BarChart3, ArrowRight, Loader2 } from "lucide-react";
import { ApiError, login, register } from "@/lib/api";

interface AuthPanelProps {
  onAuthenticated: () => Promise<void>;
}

export default function AuthPanel({ onAuthenticated }: AuthPanelProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "register") await register(name, email, password);
      else await login(email, password);
      await onAuthenticated();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Tidak dapat terhubung ke server.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex h-full min-h-0 items-center justify-center bg-[#000] px-5">
      <section className="w-full max-w-md rounded-2xl border border-white/10 bg-[#0a0a0a] p-7 shadow-2xl shadow-black/40">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-400 text-black">
            <BarChart3 size={21} strokeWidth={2.5} />
          </div>
          <div>
            <p className="font-semibold tracking-tight text-white">EchaBot</p>
            <p className="text-xs text-zinc-500">AI data analyst</p>
          </div>
        </div>

        <div className="mb-6">
          <h1 className="text-xl font-medium text-white">
            {mode === "login" ? "Masuk ke workspace" : "Buat akun EchaBot"}
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            {mode === "login"
              ? "Lanjutkan analisis dataset kamu."
              : "Simpan sesi dan dataset kamu dengan aman."}
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          {mode === "register" && (
            <label className="block text-xs text-zinc-400">
              Nama
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                minLength={2}
                autoComplete="name"
                className="mt-1.5 w-full rounded-lg border border-white/10 bg-black px-3 py-2.5 text-sm text-white outline-none transition placeholder:text-zinc-700 focus:border-teal-400/60"
                placeholder="Nama kamu"
              />
            </label>
          )}
          <label className="block text-xs text-zinc-400">
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              autoComplete="email"
              className="mt-1.5 w-full rounded-lg border border-white/10 bg-black px-3 py-2.5 text-sm text-white outline-none transition placeholder:text-zinc-700 focus:border-teal-400/60"
              placeholder="kamu@contoh.com"
            />
          </label>
          <label className="block text-xs text-zinc-400">
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={8}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className="mt-1.5 w-full rounded-lg border border-white/10 bg-black px-3 py-2.5 text-sm text-white outline-none transition placeholder:text-zinc-700 focus:border-teal-400/60"
              placeholder="Minimal 8 karakter"
            />
          </label>
          {error && <p role="alert" className="rounded-lg border border-red-400/20 bg-red-400/5 px-3 py-2 text-xs text-red-300">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-teal-400 py-2.5 text-sm font-semibold text-black transition hover:bg-teal-300 disabled:cursor-wait disabled:opacity-60"
          >
            {submitting ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
            {mode === "login" ? "Masuk" : "Daftar"}
          </button>
        </form>

        <button
          type="button"
          onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}
          className="mt-5 w-full text-center text-xs text-zinc-500 transition hover:text-teal-300"
        >
          {mode === "login" ? "Belum punya akun? Daftar" : "Sudah punya akun? Masuk"}
        </button>
      </section>
    </main>
  );
}
