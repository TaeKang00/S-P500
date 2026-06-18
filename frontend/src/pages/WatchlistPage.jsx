import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import { RefreshContext } from "../App.jsx";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { api } from "../api/client.js";
import { SignalBadge, gradeColor } from "../components/SignalBadge.jsx";
import { fmt, trendClass } from "../lib/format.js";
import { sectorKo } from "../lib/sectors.js";

function ScoreDetail({ item, onClose }) {
  if (!item) return null;
  const s = item.score;
  const color = gradeColor(s.grade);

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex items-center justify-center p-6"
      onClick={onClose}
    >
      <div
        className="bg-ink-800 border border-line w-full max-w-sm rounded-sm overflow-hidden shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="px-4 py-3 border-b border-line flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-bold font-mono text-cyan">{item.ticker}</span>
              <SignalBadge grade={s.grade} />
            </div>
            <div className="text-xs text-gray-500">{item.company_name}</div>
          </div>
          <button onClick={onClose} className="text-gray-600 hover:text-gray-300 text-base leading-none shrink-0 mt-1">×</button>
        </div>

        {/* 총점 */}
        <div className="px-4 py-4 border-b border-line flex items-end gap-6">
          <div>
            <div className="text-[10px] text-muted mb-1">총점</div>
            <div className="font-mono text-3xl font-bold tnum leading-none" style={{ color }}>
              {s.total > 0 ? "+" : ""}{s.total}
            </div>
          </div>
          <div className="flex gap-4 pb-1">
            <div>
              <div className="text-[10px] text-muted mb-1">개별 (A)</div>
              <div className="font-mono text-sm tnum text-gray-400">{s.stock_score > 0 ? "+" : ""}{s.stock_score}</div>
            </div>
            <div>
              <div className="text-[10px] text-muted mb-1">타이밍 (B)</div>
              <div className="font-mono text-sm tnum text-gray-400">{s.market_score > 0 ? "+" : ""}{s.market_score}</div>
            </div>
          </div>
        </div>

        {/* 브레이크다운 */}
        <div className="max-h-[55vh] overflow-y-auto">
          <BreakdownSection title={`개별 종목 (A) · ${s.stock_score > 0 ? "+" : ""}${s.stock_score}점`} rows={s.stock_breakdown} />
          <BreakdownSection title={`시장 타이밍 (B) · ${s.market_score > 0 ? "+" : ""}${s.market_score}점`} rows={s.market_breakdown} />
        </div>
      </div>
    </div>
  );
}

function BreakdownSection({ title, rows }) {
  return (
    <div className="px-4 py-3 border-b border-line last:border-b-0">
      <div className="text-[10px] uppercase tracking-wider text-muted mb-2">{title}</div>
      {(rows ?? []).map((b, i) => {
        const ptColor = b.points > 0 ? "#10b981" : b.points < 0 ? "#ef4444" : "#4b5563";
        const ptBg    = b.points > 0 ? "#10b98118" : b.points < 0 ? "#ef444418" : "transparent";
        return (
          <div key={i} className="flex items-center justify-between gap-3 py-2 border-b border-line/10 last:border-b-0">
            <span className="text-xs text-gray-400 flex-1 leading-snug">{b.label}</span>
            <span
              className="text-xs font-mono tnum font-semibold w-8 text-center py-1 rounded-sm shrink-0"
              style={{ color: ptColor, background: ptBg }}
            >
              {b.points > 0 ? "+" : ""}{b.points}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function WatchlistPage() {
  const { fullRefreshing, watchlistLastRefreshedAt, setWatchlistLastRefreshedAt, q } = useContext(RefreshContext);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [progress, setProgress] = useState(null);
  const [, setTick] = useState(0);

  useEffect(() => {
    if (!watchlistLastRefreshedAt) return;
    const id = setInterval(() => setTick((n) => n + 1), 60_000);
    return () => clearInterval(id);
  }, [watchlistLastRefreshedAt]);
  const [selected, setSelected] = useState(null);
  const [sorting, setSorting] = useState([{ id: "score", desc: true }]);

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
          if (p.pct === 100) {
            setWatchlistLastRefreshedAt(new Date());
            await load();
          }
        }
      } catch {
        clearInterval(id);
        setRefreshing(false);
        setProgress(null);
      }
    }, 1000);
    return () => clearInterval(id);
  }, [refreshing]);

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

  const handleDelete = useCallback(async (ticker) => {
    if (!confirm(`${ticker}를 관심종목에서 제거하시겠습니까?`)) return;
    try {
      await api.removeWatchlist(ticker);
      setItems((prev) => prev.filter((i) => i.ticker !== ticker));
    } catch (e) {
      alert(e.message);
    }
  }, []);

  const columns = useMemo(
    () => [
      // ── 종목 정보 ──────────────────────────────
      {
        accessorKey: "ticker",
        header: "티커",
        cell: (info) => (
          <span className="text-cyan text-xs font-bold tracking-wide">{info.getValue()}</span>
        ),
        size: 72,
      },
      {
        accessorKey: "company_name",
        header: "기업명",
        cell: (info) => (
          <span className="text-xs text-gray-300 font-medium truncate block">
            {info.getValue()}
          </span>
        ),
        size: 160,
      },
      {
        accessorKey: "market_cap",
        header: "시총",
        meta: { align: "right" },
        cell: (info) => (
          <span className="text-xs tnum text-gray-500">{fmt.marketCap(info.getValue())}</span>
        ),
        size: 96,
      },
      // ── EPS ────────────────────────────────────
      {
        accessorFn: (row) => row.metrics.eps_growth,
        id: "eps",
        header: "EPS성장(%)",
        meta: { groupStart: true, align: "right" },
        cell: (info) => (
          <span className={`text-xs tnum font-medium ${trendClass(info.getValue())}`}>
            {fmt.pct(info.getValue(), 1)}
          </span>
        ),
        size: 84,
      },
      // ── 밸류에이션 ─────────────────────────────
      {
        accessorFn: (row) => row.metrics.forward_pe,
        id: "fwd_per",
        header: "선행PER",
        meta: { align: "right" },
        cell: (info) => (
          <span className="text-xs tnum text-gray-500">{fmt.num(info.getValue(), 1)}</span>
        ),
        size: 76,
      },
      {
        accessorFn: (row) => row.metrics.forward_pe_3y_avg,
        id: "per_3y",
        header: "평균PER",
        meta: { align: "right" },
        cell: (info) => (
          <span className="text-xs tnum text-gray-500">{fmt.num(info.getValue(), 1)}</span>
        ),
        size: 76,
      },
      // ── 수익률 ─────────────────────────────────
      {
        accessorKey: "return_1y",
        header: "1년수익(%)",
        meta: { align: "right" },
        cell: (info) => {
          const v = info.getValue();
          if (v == null) return <span className="text-gray-700 text-xs">—</span>;
          return (
            <span className={`text-xs tnum ${v >= 0 ? "text-green-400" : "text-red-400"}`}>
              {v >= 0 ? "+" : ""}{v.toFixed(1)}
            </span>
          );
        },
        size: 76,
      },
      {
        accessorKey: "return_3y_avg",
        header: "3년수익(%)",
        meta: { align: "right" },
        cell: (info) => {
          const v = info.getValue();
          if (v == null) return <span className="text-gray-700 text-xs">—</span>;
          return (
            <span className={`text-xs tnum ${v >= 0 ? "text-green-400" : "text-red-400"}`}>
              {v >= 0 ? "+" : ""}{v.toFixed(1)}
            </span>
          );
        },
        size: 76,
      },
      // ── 기술적 지표 ────────────────────────────
      {
        accessorFn: (row) => row.metrics.drawdown_52w,
        id: "drawdown",
        header: "52주하락(%)",
        meta: { align: "right" },
        cell: (info) => (
          <span className={`text-xs tnum ${trendClass(info.getValue())}`}>
            {fmt.pct(info.getValue())}
          </span>
        ),
        size: 76,
      },
      {
        accessorFn: (row) => row.metrics.ma200_deviation,
        id: "ma200",
        header: "200일선(%)",
        meta: { align: "right" },
        cell: (info) => (
          <span className={`text-xs tnum ${trendClass(info.getValue(), true)}`}>
            {fmt.pct(info.getValue())}
          </span>
        ),
        size: 76,
      },
      {
        accessorFn: (row) => row.metrics.debt_to_equity,
        id: "de",
        header: "부채비율",
        meta: { align: "right" },
        cell: (info) => {
          const v = info.getValue();
          const c = v == null ? "text-gray-700" : v <= 0.3 ? "text-up" : "text-gray-400";
          return <span className={`text-xs tnum ${c}`}>{fmt.num(v, 2)}</span>;
        },
        size: 76,
      },
      {
        accessorFn: (row) => row.metrics.rsi_14,
        id: "rsi",
        header: "RSI",
        meta: { align: "right" },
        cell: (info) => {
          const v = info.getValue();
          const c = v == null ? "text-gray-700" : v <= 25 ? "text-up" : v >= 75 ? "text-down" : "text-gray-400";
          return <span className={`text-xs tnum ${c}`}>{fmt.num(v, 1)}</span>;
        },
        size: 64,
      },
      // ── 시그널 ─────────────────────────────────
      {
        accessorFn: (row) => row.score.total,
        id: "score",
        header: "점수",
        meta: { groupStart: true, extraGap: true, align: "right" },
        cell: (info) => {
          const s = info.row.original.score;
          return (
            <span className="font-mono font-bold tnum text-base" style={{ color: gradeColor(s.grade) }}>
              {s.total > 0 ? "+" : ""}{s.total}
            </span>
          );
        },
        size: 72,
      },
      {
        id: "actions",
        header: "",
        meta: { align: "center" },
        cell: (info) => (
          <div className="flex items-center justify-center gap-2">
            <button
              onClick={() => setSelected(info.row.original)}
              className="text-xs uppercase tracking-wider text-muted hover:text-cyan px-2 py-1 border border-line hover:border-cyan rounded-sm transition-colors"
            >
              상세
            </button>
            <button
              onClick={() => handleDelete(info.row.original.ticker)}
              className="text-xs uppercase tracking-wider text-muted hover:text-down px-2 py-1 border border-line hover:border-down rounded-sm transition-colors"
            >
              삭제
            </button>
          </div>
        ),
        size: 108,
      },
    ],
    [handleDelete]
  );

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

  const summary = useMemo(() => {
    if (!items.length) return null;
    const buckets = { STRONG_BUY: 0, BUY_QUEUE: 0, HOLD: 0, SELL_QUEUE: 0, SELL: 0 };
    items.forEach((i) => { buckets[i.score.grade] = (buckets[i.score.grade] ?? 0) + 1; });
    return buckets;
  }, [items]);

  return (
    <div className="px-5 py-5">
      <div className="flex items-center justify-between gap-4 mb-5">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            관심종목 <span className="text-cyan">{filteredItems.length}</span>
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {summary && (
            <div className="flex items-center gap-6 px-4 py-2">
              <SignalBadgeMini grade="STRONG_BUY"  count={summary.STRONG_BUY} />
              <SignalBadgeMini grade="BUY_QUEUE"   count={summary.BUY_QUEUE} />
              <SignalBadgeMini grade="HOLD"        count={summary.HOLD} />
              <SignalBadgeMini grade="SELL_QUEUE"  count={summary.SELL_QUEUE} />
              <SignalBadgeMini grade="SELL"        count={summary.SELL} />
            </div>
          )}
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
            <>
              <button
                onClick={handleRefresh}
                disabled={refreshing || fullRefreshing}
                className="bg-ink-900 border border-line hover:border-cyan/50 rounded-sm px-3 py-2 text-xs text-muted hover:text-gray-200 transition-colors disabled:opacity-30 disabled:cursor-not-allowed whitespace-nowrap"
              >
                관심종목 업데이트
              </button>
              {watchlistLastRefreshedAt && (
                <span className="text-[10px] text-gray-600 tnum whitespace-nowrap">
                  {(() => {
                    const diffMin = Math.floor((Date.now() - watchlistLastRefreshedAt) / 60000);
                    if (diffMin < 1) return "방금 전";
                    if (diffMin < 60) return `${diffMin}분 전`;
                    const now = new Date();
                    const todayStart = new Date(now); todayStart.setHours(0, 0, 0, 0);
                    const time = watchlistLastRefreshedAt.toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" });
                    return watchlistLastRefreshedAt >= todayStart ? `오늘 ${time}` : watchlistLastRefreshedAt.toLocaleDateString("ko-KR", { month: "short", day: "numeric" }) + " " + time;
                  })()}
                </span>
              )}
            </>
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
                    const alignClass = align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";
                    return (
                      <th
                        key={h.id}
                        onClick={h.column.getToggleSortingHandler()}
                        style={{ width: h.getSize() }}
                        className={`${alignClass} text-[10px] text-gray-600 py-3 font-medium cursor-pointer select-none hover:text-gray-300 whitespace-nowrap overflow-hidden ${h.column.columnDef.meta?.extraGap ? "pl-28 pr-4" : h.column.columnDef.meta?.groupStart ? "pl-12 pr-4" : "px-4"}`}
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
                      ? <><span>관심종목이 없습니다.{" "}</span><span className="text-cyan">목록</span><span> 페이지에서 + 버튼으로 추가하세요.</span></>
                      : "검색 결과가 없습니다."}
                  </td>
                </tr>
              )}
              {table.getRowModel().rows.map((r) => (
                <tr key={r.id} className="row-hover border-b border-line/40 last:border-b-0">
                  {r.getVisibleCells().map((c) => {
                    const align = c.column.columnDef.meta?.align;
                    const alignClass = align === "right" ? "text-right" : align === "center" ? "text-center" : "";
                    return (
                      <td
                        key={c.id}
                        className={`py-3 ${alignClass} ${c.column.columnDef.meta?.extraGap ? "pl-28 pr-4" : c.column.columnDef.meta?.groupStart ? "pl-12 pr-4" : "px-4"}`}
                      >
                        {flexRender(c.column.columnDef.cell, c.getContext())}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ScoreDetail item={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function SignalBadgeMini({ grade, count }) {
  const LABELS = {
    STRONG_BUY: "강매수", BUY_QUEUE: "매수대기",
    HOLD: "관망", SELL_QUEUE: "매도대기", SELL: "매도",
  };
  const COLORS = {
    STRONG_BUY: "#10b981", BUY_QUEUE: "#7dd3fc",
    HOLD: "#6b7280", SELL_QUEUE: "#fb923c", SELL: "#ef4444",
  };
  const color = COLORS[grade];
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: color }} />
      <span className="text-gray-500">{LABELS[grade]}</span>
      <span className="font-mono tnum font-semibold" style={{ color }}>{count}</span>
    </div>
  );
}
