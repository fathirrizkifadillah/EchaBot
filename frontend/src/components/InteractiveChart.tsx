"use client";
import React, { useState, useEffect } from "react";
import Image from "next/image";
import { BarChart3, Image as ImageIcon, Download } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { ChartConfig } from "@/lib/api";

interface InteractiveChartProps {
  chart?: ChartConfig;
  imageUrl?: string;
  downloadUrl?: string;
}

export default function InteractiveChart({
  chart,
  imageUrl,
  downloadUrl,
}: InteractiveChartProps) {
  const [mounted, setMounted] = useState(false);
  const [mode, setMode] = useState<"interactive" | "image">(
    chart && chart.data && chart.data.length > 0 ? "interactive" : "image"
  );

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!chart && !imageUrl) {
    return null;
  }

  const hasChartData = Boolean(chart && chart.data && chart.data.length > 0);
  const activeChart = chart && hasChartData ? chart : null;

  return (
    <div className="mt-4 overflow-hidden rounded-xl border border-white/10 bg-zinc-900/60 p-3 sm:p-4">
      {/* Header with Title and Mode Switcher */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-2.5">
        <span className="text-xs font-medium text-zinc-300">
          {chart?.title || "Visualisasi Dataset"}
        </span>

        <div className="flex items-center gap-1.5">
          {hasChartData && imageUrl && (
            <div className="flex rounded-lg bg-zinc-800/80 p-0.5 text-xs">
              <button
                type="button"
                onClick={() => setMode("interactive")}
                className={`flex items-center gap-1 rounded-md px-2 py-1 transition ${
                  mode === "interactive"
                    ? "bg-teal-500/20 font-medium text-teal-300"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
                title="Tampilkan grafik interaktif"
              >
                <BarChart3 size={12} />
                <span>Interaktif</span>
              </button>
              <button
                type="button"
                onClick={() => setMode("image")}
                className={`flex items-center gap-1 rounded-md px-2 py-1 transition ${
                  mode === "image"
                    ? "bg-teal-500/20 font-medium text-teal-300"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
                title="Tampilkan gambar PNG statis"
              >
                <ImageIcon size={12} />
                <span>PNG</span>
              </button>
            </div>
          )}

          {downloadUrl && (
            <a
              href={downloadUrl}
              download
              className="flex items-center gap-1 rounded-lg border border-white/10 bg-zinc-800/60 px-2 py-1 text-xs text-zinc-400 transition hover:bg-white/10 hover:text-zinc-200"
              title="Unduh grafik"
            >
              <Download size={12} />
              <span className="hidden sm:inline">Unduh</span>
            </a>
          )}
        </div>
      </div>

      {/* Body: Interactive Recharts vs Static Image */}
      {mode === "interactive" && activeChart && mounted ? (
        <div className="h-72 w-full pt-2 sm:h-80">
          <ResponsiveContainer width="100%" height="100%">
            {activeChart.type === "line" ? (
              <LineChart
                data={activeChart.data}
                margin={{ top: 10, right: 15, left: -10, bottom: 25 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  dataKey={activeChart.xKey}
                  stroke="#71717a"
                  fontSize={11}
                  tickLine={false}
                  angle={-25}
                  textAnchor="end"
                  interval="preserveStartEnd"
                />
                <YAxis
                  stroke="#71717a"
                  fontSize={11}
                  tickLine={false}
                  tickFormatter={(v) => (typeof v === "number" ? v.toLocaleString() : v)}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    borderColor: "#3f3f46",
                    borderRadius: "8px",
                    fontSize: "12px",
                    color: "#f4f4f5",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey={activeChart.yKey}
                  stroke="#14b8a6"
                  strokeWidth={2.2}
                  dot={{ r: 2.5, fill: "#14b8a6" }}
                  activeDot={{ r: 5, fill: "#2dd4bf" }}
                />
              </LineChart>
            ) : activeChart.type === "scatter" ? (
              <ScatterChart
                margin={{ top: 10, right: 15, left: -10, bottom: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  dataKey={activeChart.xKey}
                  type="number"
                  stroke="#71717a"
                  fontSize={11}
                  tickLine={false}
                  name={activeChart.xKey}
                  tickFormatter={(v) => (typeof v === "number" ? v.toLocaleString() : v)}
                />
                <YAxis
                  dataKey={activeChart.yKey}
                  type="number"
                  stroke="#71717a"
                  fontSize={11}
                  tickLine={false}
                  name={activeChart.yKey}
                  tickFormatter={(v) => (typeof v === "number" ? v.toLocaleString() : v)}
                />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  contentStyle={{
                    backgroundColor: "#18181b",
                    borderColor: "#3f3f46",
                    borderRadius: "8px",
                    fontSize: "12px",
                    color: "#f4f4f5",
                  }}
                />
                <Scatter data={activeChart.data} fill="#38bdf8" fillOpacity={0.75} />
              </ScatterChart>
            ) : (
              <BarChart
                data={activeChart.data}
                margin={{ top: 10, right: 15, left: -10, bottom: 25 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  dataKey={activeChart.xKey}
                  stroke="#71717a"
                  fontSize={11}
                  tickLine={false}
                  angle={-25}
                  textAnchor="end"
                  interval="preserveStartEnd"
                />
                <YAxis
                  stroke="#71717a"
                  fontSize={11}
                  tickLine={false}
                  tickFormatter={(v) => (typeof v === "number" ? v.toLocaleString() : v)}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    borderColor: "#3f3f46",
                    borderRadius: "8px",
                    fontSize: "12px",
                    color: "#f4f4f5",
                  }}
                />
                <Bar dataKey={activeChart.yKey} fill="#14b8a6" radius={[4, 4, 0, 0]} />
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      ) : imageUrl ? (
        <div className="overflow-hidden rounded-lg">
          <Image
            src={imageUrl}
            alt={chart?.title || "Visualisasi dataset"}
            width={800}
            height={500}
            unoptimized
            className="h-auto max-w-full rounded-lg"
          />
        </div>
      ) : (
        <div className="flex h-40 items-center justify-center text-xs text-zinc-500">
          Memuat visualisasi...
        </div>
      )}
    </div>
  );
}
