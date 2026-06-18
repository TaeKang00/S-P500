import { useContext, useEffect, useMemo, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { RefreshContext } from "../App.jsx";
import { api } from "../api/client.js";
import { gradeColor } from "../components/SignalBadge.jsx";
import { fmt } from "../lib/format.js";
import { isMarketOpen } from "../lib/market.js";
import { sectorKo } from "../lib/sectors.js";

function CompanyCell({ name }) {
  return (
    <span className="text-xs text-gray-300 font-medium truncate block cursor-default">
      {name}
    </span>
  );
}

function WatchlistButton({ ticker, added, busy, onAdd, onRemove }) {
  if (added) {
    return (
      <button
        onClick={() => onRemove(ticker)}
        disabled={busy}
        className="group text-xs text-up border border-up/30 hover:border-red-500/60 hover:text-red-400 hover:bg-red-500/10 disabled:opacity-40 px-2 py-1 rounded-sm transition-colors whitespace-nowrap"
      >
        <span className="group-hover:hidden">✓ 관심종목</span>
        <span className="hidden group-hover:inline">− 삭제</span>
      </button>
    );
  }
  return (
    <button
      onClick={() => onAdd(ticker)}
      disabled={busy}
      className="text-xs text-cyan hover:text-gray-100 disabled:opacity-40 px-2 py-1 transition-colors border border-line hover:border-cyan rounded-sm"
    >
      추가
    </button>
  );
}


export default function ListPage() {
  const { fullRefreshing, progress, yfinanceBlocked, handleFullRefresh, lastRefreshedAt, refreshTrigger, q } = useContext(RefreshContext);
  const marketOpen = isMarketOpen();

  const [stocks, setStocks] = useState([]);
  const [sectors, setSectors] = useState([]);
  const [sector, setSector] = useState("");
  const [gradeFilter, setGradeFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);
  const [sorting, setSorting] = useState([{ id: "rank", desc: false }]);

  async function load() {
    setLoading(true);
    try {
      const [list, sec] = await Promise.all([
        api.listStocks({ sector, q }),
        sectors.length ? Promise.resolve(sectors) : api.listSectors(),
      ]);
      setStocks(list);
      if (!sectors.length) setSectors(sec);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sector, q, refreshTrigger]);

  async function addToWatchlist(ticker) {
    setBusy(ticker);
    try {
      await api.addWatchlist(ticker);
      await load();
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(null);
    }
  }

  async function removeFromWatchlist(ticker) {
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

  const columns = [
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
          <CompanyCell name={info.getValue()} />
        ),
        size: 160,
      },
      {
        accessorKey: "market_cap",
        header: "시총",
        meta: { align: "right" },
        cell: (info) => (
          <span className="text-xs tnum text-gray-400">{fmt.marketCap(info.getValue())}</span>
        ),
        size: 80,
      },
      {
        accessorKey: "return_1y",
        header: "1년수익(%)",
        meta: { align: "right" },
        cell: (info) => {
          const v = info.getValue();
          if (v == null) return <span className="text-gray-600 text-xs">—</span>;
          const c = v >= 0 ? "text-emerald-400" : "text-red-400";
          return <span className={`text-xs tnum ${c}`}>{v >= 0 ? "+" : ""}{v.toFixed(1)}</span>;
        },
        size: 80,
      },
      {
        accessorKey: "return_3y_avg",
        header: "3년수익(%)",
        meta: { align: "right" },
        cell: (info) => {
          const v = info.getValue();
          if (v == null) return <span className="text-gray-600 text-xs">—</span>;
          const c = v >= 0 ? "text-emerald-400" : "text-red-400";
          return <span className={`text-xs tnum ${c}`}>{v >= 0 ? "+" : ""}{v.toFixed(1)}</span>;
        },
        size: 80,
      },
      {
        accessorKey: "tech_score",
        header: "점수",
        meta: { align: "right" },
        cell: (info) => {
          const s = info.row.original;
          if (s.tech_score == null) return <span className="text-gray-700 text-xs">—</span>;
          const color = gradeColor(s.tech_grade);
          return (
            <span className="font-mono font-bold tnum text-sm" style={{ color }}>
              {s.tech_score > 0 ? "+" : ""}{s.tech_score}
            </span>
          );
        },
        size: 80,
      },
      {
        id: "action",
        header: "",
        meta: { extraGap: true, align: "right" },
        cell: (info) => (
          <WatchlistButton
            ticker={info.row.original.ticker}
            added={info.row.original.in_watchlist}
            busy={busy === info.row.original.ticker}
            onAdd={addToWatchlist}
            onRemove={removeFromWatchlist}
          />
        ),
        size: 80,
      },
  ];

  const filteredStocks = useMemo(
    () => gradeFilter ? stocks.filter((s) => s.tech_grade === gradeFilter) : stocks,
    [stocks, gradeFilter]
  );

  const table = useReactTable({
    data: filteredStocks,
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
            전체종목 <span className="text-cyan">{filteredStocks.length}</span>
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <select
              value={sector}
              onChange={(e) => setSector(e.target.value)}
              className="appearance-none bg-ink-900 border border-line focus:border-cyan/50 rounded-sm px-3 pr-7 py-2 text-xs outline-none transition-colors w-[150px] text-gray-300 cursor-pointer"
            >
              <option value="">전체 섹터</option>
              {sectors.map((s) => (
                <option key={s} value={s}>{sectorKo(s)}</option>
              ))}
            </select>
            <svg className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-600 pointer-events-none" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="m6 9 6 6 6-6"/>
            </svg>
          </div>
          <div className="relative">
            <select
              value={gradeFilter}
              onChange={(e) => setGradeFilter(e.target.value)}
              className="appearance-none bg-ink-900 border border-line focus:border-cyan/50 rounded-sm px-3 pr-7 py-2 text-xs outline-none transition-colors w-[120px] text-gray-300 cursor-pointer"
            >
              <option value="">전체 시그널</option>
              <option value="STRONG_BUY">강매수</option>
              <option value="BUY_QUEUE">매수대기</option>
              <option value="HOLD">관망</option>
              <option value="SELL_QUEUE">매도대기</option>
              <option value="SELL">매도</option>
            </select>
            <svg className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-600 pointer-events-none" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="m6 9 6 6 6-6"/>
            </svg>
          </div>
          {fullRefreshing && progress ? (
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
                onClick={handleFullRefresh}
                disabled={fullRefreshing || marketOpen || yfinanceBlocked === true}
                title={
                  yfinanceBlocked === true
                    ? "Yahoo Finance 차단 중 — 새로고침 불가"
                    : marketOpen
                    ? "장 마감 후 새로고침 가능합니다 (ET 16:00 이후)"
                    : "503개 종목 전체 데이터 새로고침"
                }
                className="bg-ink-900 border border-line hover:border-cyan/50 rounded-sm px-3 py-2 text-xs text-muted hover:text-gray-200 transition-colors disabled:opacity-30 disabled:cursor-not-allowed whitespace-nowrap"
              >
                전체종목 업데이트
              </button>
              {lastRefreshedAt && (
                <span className="text-[10px] text-gray-600 tnum whitespace-nowrap">
                  {(() => {
                    const diffMin = Math.floor((Date.now() - lastRefreshedAt) / 60000);
                    if (diffMin < 1) return "방금 전";
                    if (diffMin < 60) return `${diffMin}분 전`;
                    const now = new Date();
                    const todayStart = new Date(now); todayStart.setHours(0, 0, 0, 0);
                    const time = lastRefreshedAt.toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" });
                    return lastRefreshedAt >= todayStart ? `오늘 ${time}` : lastRefreshedAt.toLocaleDateString("ko-KR", { month: "short", day: "numeric" }) + " " + time;
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
                        className={`${alignClass} text-[10px] text-muted py-3 font-medium cursor-pointer select-none hover:text-gray-200 whitespace-nowrap overflow-hidden ${h.column.columnDef.meta?.extraGap ? "pl-8 pr-4" : "px-4"}`}
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
                    데이터 불러오는 중…
                  </td>
                </tr>
              )}
              {!loading && filteredStocks.length === 0 && (
                <tr>
                  <td colSpan={columns.length} className="text-center py-10 text-muted text-xs">
                    {stocks.length === 0 ? "종목이 없습니다." : "검색 결과가 없습니다."}
                  </td>
                </tr>
              )}
              {table.getRowModel().rows.map((r) => (
                <tr key={r.id} className="row-hover border-b border-line/40 last:border-b-0">
                  {r.getVisibleCells().map((c) => {
                    const align = c.column.columnDef.meta?.align;
                    const alignClass = align === "right" ? "text-right" : align === "center" ? "text-center" : "";
                    return (
                      <td key={c.id} className={`py-3 align-middle ${alignClass} ${c.column.columnDef.meta?.extraGap ? "pl-8 pr-4" : "px-4"}`}>
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
    </div>
  );
}
