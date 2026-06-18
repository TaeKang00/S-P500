import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { fmt, trendClass } from "../lib/format.js";
import { isMarketOpen } from "../lib/market.js";


function gradeFromScore(score) {
  if (score >= 8) return { label: "강한 매수 환경", color: "#10b981" };
  if (score >= 4) return { label: "매수 우호", color: "#22c55e" };
  if (score >= -1) return { label: "중립", color: "#9ca3af" };
  if (score >= -5) return { label: "위험 신호", color: "#f59e0b" };
  return { label: "과열/매도 환경", color: "#ef4444" };
}

function Cell({ label, value, score, valueClass, tooltip }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 border-r border-line last:border-r-0" title={tooltip}>
      <span className="text-[10px] text-muted shrink-0">
        {label}
      </span>
      <span className={`text-sm font-semibold tnum ${valueClass || "text-gray-100"}`}>
        {value}
      </span>
      {score != null && (
        <span className="font-mono text-[10px] px-1 rounded-sm bg-ink-700 text-cyan tnum">
          {score > 0 ? "+" : ""}{score}
        </span>
      )}
    </div>
  );
}

export function MarketTimingBar({ fullRefreshing, yfinanceBlocked, refreshTrigger }) {
  const [data, setData] = useState(null);
  const [timingRefreshing, setTimingRefreshing] = useState(false);

  async function load() {
    try {
      setData(await api.getMarketTiming());
    } catch (e) {
      console.error(e);
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (refreshTrigger > 0) {
      setData((prev) => prev ? { ...prev, captured_at: new Date().toISOString().replace("Z", "") } : prev);
      load();
    }
  }, [refreshTrigger]);

  async function handleTimingRefresh() {
    setTimingRefreshing(true);
    try {
      await api.refreshMarketTiming();
      setData((prev) => prev ? { ...prev, captured_at: new Date().toISOString().replace("Z", "") } : prev);
      await load();
    } catch (e) {
      alert("시장지표 갱신 실패: " + e.message);
    } finally {
      setTimingRefreshing(false);
    }
  }

  const score = data?.timing_score ?? 0;
  const grade = gradeFromScore(score);
  const findScore = (label) =>
    data?.breakdown?.find((b) => b.label.startsWith(label))?.points;

  return (
    <div className="bg-ink-800/60 border-t border-line flex items-stretch overflow-x-auto text-xs">
      <div className="flex items-center gap-2 px-3 border-r border-line shrink-0">
        <span className="text-[10px] text-muted">시장 타이밍</span>
        <span className="text-xs font-bold" style={{ color: grade.color }}>
          {grade.label}
        </span>
        <span className="font-mono text-[10px] px-1 rounded-sm bg-ink-700 text-cyan tnum">
          {score > 0 ? "+" : ""}{score}
        </span>
      </div>

      <Cell
        label="SPY 52w"
        value={fmt.percent(data?.spy_drawdown_52w)}
        score={findScore("SPY")}
        valueClass={trendClass(data?.spy_drawdown_52w)}
        tooltip="SPY 52주 고점 대비 하락률"
      />
      <Cell
        label="VIX"
        value={fmt.num(data?.vix, 2)}
        score={findScore("VIX")}
        tooltip="CBOE Volatility Index"
      />
      <Cell
        label="Fear & Greed"
        value={fmt.num(data?.fear_greed, 1)}
        score={findScore("Fear")}
        tooltip="CNN Fear & Greed Index (0=극도공포, 100=극도탐욕)"
      />

      <div className="ml-auto flex items-center gap-4 pr-3">
        <div className="flex items-center gap-2">
          <button
            onClick={handleTimingRefresh}
            disabled={timingRefreshing || fullRefreshing || yfinanceBlocked === true}
            title={
              yfinanceBlocked === true
                ? "Yahoo Finance 차단 중 — 새로고침 불가"
                : "SPY 52W · VIX · Fear & Greed 지표만 갱신"
            }
            className="flex items-center gap-2 text-xs text-muted hover:text-gray-200 px-2 py-1 transition-colors disabled:opacity-30 disabled:cursor-not-allowed whitespace-nowrap"
          >
            <span className={`w-2 h-2 rounded-full shrink-0 ${isMarketOpen() ? "bg-up pulse-dot" : "border border-gray-600"}`} />
            {timingRefreshing ? "갱신 중…" : "시장지표 업데이트"}
          </button>
        </div>
        {yfinanceBlocked === true && (
          <span className="text-[10px] text-red-400 leading-none">
            ⚠ 데이터 소스 차단됨
          </span>
        )}
      </div>
    </div>
  );
}
