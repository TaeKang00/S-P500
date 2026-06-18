import { useContext, useEffect, useMemo, useState } from "react";
import { RefreshContext } from "../App.jsx";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { api } from "../api/client.js";
import { gradeColor } from "../components/SignalBadge.jsx";
import { fmt } from "../lib/format.js";

const REC_CONFIG = {
  strong_buy:  { label: "강매수", color: "#10b981" },
  buy:         { label: "매수",   color: "#7dd3fc" },
  hold:        { label: "관망",   color: "#6b7280" },
  sell:        { label: "매도",   color: "#fb923c" },
  strong_sell: { label: "강매도", color: "#ef4444" },
};

function RecBadge({ rec }) {
  const cfg = REC_CONFIG[rec] ?? { label: rec ?? "—", color: "#6b7280" };
  return (
    <span
      className="text-xs font-semibold px-2 py-1 rounded-sm"
      style={{ color: cfg.color, background: cfg.color + "22" }}
    >
      {cfg.label}
    </span>
  );
}

function AnalystDetail({ item, onClose }) {
  if (!item) return null;
  const m = item.metrics;
  const s = item.score;

  const cur = m.current_price;
  const tgt = m.target_price_mean;
  const upside = cur && tgt ? (tgt / cur - 1) * 100 : null;
  const upsideColor = upside == null ? "#6b7280" : upside >= 20 ? "#10b981" : upside >= 5 ? "#d1d5db" : upside >= 0 ? "#6b7280" : "#ef4444";

  const cfg = REC_CONFIG[m.recommendation] ?? { label: m.recommendation ?? "—", color: "#6b7280" };

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex items-center justify-center p-6"
      onClick={onClose}
    >
      <div
        className="bg-ink-800 border border-line w-full max-w-sm rounded-sm shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-line flex items-center justify-between gap-4">
          <div className="flex-1 min-w-0">
            <span className="text-sm font-bold font-mono text-cyan">{item.ticker}</span>
            <span className="text-xs text-gray-500 ml-2">{item.company_name}</span>
          </div>
          <button onClick={onClose} className="text-gray-600 hover:text-gray-300 text-lg leading-none shrink-0">×</button>
        </div>

        <div className="px-5 py-5 border-b border-line/30 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-gray-600 mb-2">애널리스트 의견</div>
            <span className="text-sm font-bold px-3 py-1.5 rounded-sm" style={{ color: cfg.color, background: cfg.color + "22" }}>
              {cfg.label}
            </span>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-gray-600 mb-1">참여 애널리스트</div>
            <span className="text-xl font-bold tnum text-gray-300">
              {m.analyst_count != null ? `${m.analyst_count}명` : "—"}
            </span>
          </div>
        </div>

        <div className="px-5 py-4 border-b border-line/30">
          <div className="text-[10px] text-gray-600 mb-3">목표주가</div>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "평균", value: m.target_price_mean, primary: true },
              { label: "최고", value: m.target_price_high },
              { label: "최저", value: m.target_price_low },
            ].map(({ label, value, primary }) => (
              <div key={label}>
                <div className="text-[10px] text-gray-600 mb-1">{label}</div>
                <span className={`text-sm tnum font-semibold ${primary ? "text-gray-100" : "text-gray-500"}`}>
                  {value != null ? `$${value.toFixed(1)}` : "—"}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="px-5 py-4 border-b border-line/30 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-gray-600 mb-1">현재가</div>
            <span className="text-sm tnum text-gray-400">{cur != null ? `$${cur.toFixed(1)}` : "—"}</span>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-gray-600 mb-1">상승여력</div>
            <span className="text-xl font-bold tnum" style={{ color: upsideColor }}>
              {upside != null ? `${upside >= 0 ? "+" : ""}${upside.toFixed(1)}%` : "—"}
            </span>
          </div>
        </div>

        <div className="px-5 py-4 flex items-center justify-between">
          <span className="text-xs text-gray-600">종합 점수</span>
          <span className="text-base font-bold font-mono tnum" style={{ color: gradeColor(s.grade) }}>
            {s.total > 0 ? "+" : ""}{s.total}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function TargetPage() {
  const { fullRefreshing, q } = useContext(RefreshContext);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [progress, setProgress] = useState(null);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(null);
  const [sorting, setSorting] = useState([{ id: "upside", desc: true }]);

  async function load() {
    setLoading(true);
    try {
      setItems(await api.listWatchlist());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!refreshing) return;
    const id = setInterval(async () => {
      try {
        const p = await api.getRefreshProgress();
        setProgress({ pct: p.pct, step: p.step });
        if (!p.running) {
          clearInterval(id);
          setRefreshing(false);
          setProgress(null);
          if (p.pct === 100) await load();
        }
      } catch {
        clearInterval(id);
        setRefreshing(false);
        setProgress(null);
      }
    }, 1000);
    return () => clearInterval(id);
  }, [refreshing]);

  async function handleRemove(ticker) {
    setBusy(ticker);
    try {
      await api.removeWatchlist(ticker);
      await load();
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(null);
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    setProgress({ pct: 0, step: "시작 중…" });
    try {
      await api.refreshWatchlist();
    } catch (e) {
      setRefreshing(false);
      setProgress(null);
      alert(e.message);
    }
  }

  const columns = useMemo(() => [
    {
      accessorKey: "ticker",
      header: "티커",
      cell: (info) => (
        <span className="text-cyan text-xs font-bold tracking-wide">{info.getValue()}</span>
      ),
      size: 80,
    },
    {
      accessorKey: "company_name",
      header: "기업명",
      cell: (info) => (
        <span className="text-xs text-gray-300 font-medium truncate min-w-0">{info.getValue()}</span>
      ),
      size: 160,
    },
    {
      accessorFn: (row) => {
        const cur = row.metrics.current_price;
        const tgt = row.metrics.target_price_mean;
        if (!cur || !tgt) return null;
        return (tgt / cur - 1) * 100;
      },
      id: "upside",
      header: "상승여력",
      meta: { align: "right" },
      cell: (info) => {
        const v = info.getValue();
        if (v == null) return <span className="text-gray-700 text-xs">—</span>;
        const c = v >= 20 ? "text-emerald-400" : v >= 5 ? "text-gray-300" : v >= 0 ? "text-gray-500" : "text-red-400";
        return (
          <span className={`text-xs tnum font-semibold ${c}`}>
            {v >= 0 ? "+" : ""}{v.toFixed(1)}%
          </span>
        );
      },
      size: 80,
    },
    {
      accessorFn: (row) => row.metrics.target_price_mean,
      id: "target_mean",
      header: "목표가",
      meta: { align: "right" },
      cell: (info) => {
        const v = info.getValue();
        if (v == null) return <span className="text-gray-700 text-xs">—</span>;
        return <span className="text-xs tnum text-gray-200 font-medium">${v.toFixed(1)}</span>;
      },
      size: 80,
    },
    {
      accessorFn: (row) => row.metrics.current_price,
      id: "current_price",
      header: "현재가",
      meta: { align: "right" },
      cell: (info) => {
        const v = info.getValue();
        if (v == null) return <span className="text-gray-700 text-xs">—</span>;
        return <span className="text-xs tnum text-gray-400">${v.toFixed(1)}</span>;
      },
      size: 80,
    },
    {
      accessorFn: (row) => row.metrics.analyst_count,
      id: "analyst_count",
      header: "애널리스트",
      meta: { align: "right" },
      cell: (info) => {
        const v = info.getValue();
        if (v == null) return <span className="text-gray-700 text-xs">—</span>;
        return <span className="text-xs tnum text-gray-500">{v}명</span>;
      },
      size: 80,
    },
    {
      accessorFn: (row) => row.score.total,
      id: "score",
      header: "점수",
      meta: { align: "right", extraGap: true },
      cell: (info) => {
        const s = info.row.original.score;
        return (
          <span className="font-mono font-bold tnum text-base" style={{ color: gradeColor(s.grade) }}>
            {s.total > 0 ? "+" : ""}{s.total}
          </span>
        );
      },
      size: 80,
    },
    {
      id: "action",
      header: "",
      meta: { align: "right" },
      cell: (info) => {
        const ticker = info.row.original.ticker;
        return (
          <button
            onClick={(e) => { e.stopPropagation(); handleRemove(ticker); }}
            disabled={busy === ticker}
            className="text-xs text-muted hover:text-gray-200 px-2 py-1 transition-colors border border-line hover:border-cyan/50 rounded-sm bg-ink-900 disabled:opacity-40"
          >
            삭제
          </button>
        );
      },
      size: 80,
    },
  ], [busy]);

  const filteredItems = useMemo(() => {
    if (!q) return items;
    const lower = q.toLowerCase();
    return items.filter((i) =>
      i.ticker.toLowerCase().includes(lower) ||
      i.company_name.toLowerCase().includes(lower)
    );
  }, [items, q]);

  const table = useReactTable({
    data: filteredItems,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="px-5 py-5">
      <div className="flex items-center justify-between gap-4 mb-5">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            목표가 <span className="text-cyan">{filteredItems.length}</span>
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {refreshing && progress ? (
            <div className="flex flex-col items-end gap-1 min-w-[180px]">
              <div className="flex justify-between items-center w-full">
                <span className="text-[10px] text-gray-500 truncate max-w-[130px]">{progress.step}</span>
                <span className="text-[10px] text-cyan tnum font-semibold ml-2">{progress.pct}%</span>
              </div>
              <div className="h-1 w-full bg-ink-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-cyan rounded-full transition-all duration-500"
                  style={{ width: `${progress.pct}%` }}
                />
              </div>
            </div>
          ) : (
            <button
              onClick={handleRefresh}
              disabled={refreshing || fullRefreshing}
              className="bg-ink-900 border border-line hover:border-cyan/50 rounded-sm px-3 py-2 text-xs text-muted hover:text-gray-200 transition-colors disabled:opacity-30 disabled:cursor-not-allowed whitespace-nowrap"
            >
              목표가 업데이트
            </button>
          )}
        </div>
      </div>

      <div className="border border-line rounded-sm overflow-hidden bg-ink-800/40">
        <div className="overflow-auto max-h-[calc(100vh-260px)]">
          <table className="w-full table-fixed">
            <thead className="sticky top-0 bg-ink-800 border-b border-line">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => {
                    const align = h.column.columnDef.meta?.align;
                    const extraGap = h.column.columnDef.meta?.extraGap;
                    const alignClass = align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";
                    return (
                      <th
                        key={h.id}
                        onClick={h.column.getToggleSortingHandler()}
                        style={{ width: h.getSize() }}
                        className={`${alignClass} text-[10px] text-gray-600 py-3 font-medium cursor-pointer select-none hover:text-gray-300 whitespace-nowrap overflow-hidden ${extraGap ? "pl-10 pr-6" : "px-6"}`}
                      >
                        <span className="inline-flex items-center gap-1">
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          {{ asc: "▲", desc: "▼" }[h.column.getIsSorted()] ?? ""}
                        </span>
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={columns.length} className="text-center py-10 text-muted text-xs">
                    불러오는 중…
                  </td>
                </tr>
              )}
              {!loading && filteredItems.length === 0 && (
                <tr>
                  <td colSpan={columns.length} className="text-center py-12 text-muted text-xs">
                    {items.length === 0
                      ? "관심종목이 없습니다. 목록 페이지에서 추가하세요."
                      : "검색 결과가 없습니다."}
                  </td>
                </tr>
              )}
              {table.getRowModel().rows.map((r) => (
                <tr
                  key={r.id}
                  className="row-hover border-b border-line/40 last:border-b-0 cursor-pointer"
                  onClick={() => setSelected(r.original)}
                >
                  {r.getVisibleCells().map((c) => {
                    const align = c.column.columnDef.meta?.align;
                    const extraGap = c.column.columnDef.meta?.extraGap;
                    const justifyClass = align === "right" ? "justify-end" : align === "center" ? "justify-center" : "justify-start";
                    return (
                      <td
                        key={c.id}
                        className={`py-4 ${extraGap ? "pl-10 pr-6" : "px-6"}`}
                      >
                        <div className={`flex items-center ${justifyClass}`}>
                          {flexRender(c.column.columnDef.cell, c.getContext())}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <AnalystDetail item={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
