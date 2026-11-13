"use client";
import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";

interface DataTableProps {
  rows: Record<string, string>[];
}

export default function DataTable({ rows }: DataTableProps) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [ascending, setAscending] = useState(true);
  const columns = rows.length ? Object.keys(rows[0]) : [];
  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    return [...rows].sort((a, b) => {
      const av = a[sortKey] ?? "";
      const bv = b[sortKey] ?? "";
      const an = Number(av);
      const bn = Number(bv);
      const result = !Number.isNaN(an) && !Number.isNaN(bn) ? an - bn : av.localeCompare(bv);
      return ascending ? result : -result;
    });
  }, [rows, sortKey, ascending]);

  const sort = (key: string) => {
    if (key === sortKey) setAscending((v) => !v);
    else { setSortKey(key); setAscending(true); }
  };

  return (
    <div className="mt-3 max-h-80 overflow-auto rounded-lg border border-white/10">
      <table className="msg-table">
        <thead><tr>{columns.map((col) => <th key={col}><button onClick={() => sort(col)} className="flex items-center gap-1 text-left">{col}{sortKey === col ? (ascending ? <ArrowUp size={12} /> : <ArrowDown size={12} />) : <ChevronsUpDown size={12} className="text-zinc-600" />}</button></th>)}</tr></thead>
        <tbody>{sorted.map((row, i) => <tr key={i}>{columns.map((col) => <td key={col}>{String(row[col] ?? "")}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}
