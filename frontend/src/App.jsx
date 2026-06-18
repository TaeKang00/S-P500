import { createContext, useContext, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api/client.js";
import { MarketTimingBar } from "./components/MarketTimingBar.jsx";
import ListPage from "./pages/ListPage.jsx";
import TargetPage from "./pages/TargetPage.jsx";
import WatchlistPage from "./pages/WatchlistPage.jsx";

export const RefreshContext = createContext(null);

function TopNav() {
  const { fullRefreshing, progress, yfinanceBlocked, refreshTrigger, lastRefreshedAt, q, setQ } = useContext(RefreshContext);
  const linkClass = ({ isActive }) =>
    [
      "px-3 py-2 text-xs font-semibold tracking-wide border-b-2 transition-colors",
      isActive
        ? "text-white border-cyan"
        : "text-gray-500 border-transparent hover:text-gray-300",
    ].join(" ");

  return (
    <header className="border-b border-line bg-ink-900/80 backdrop-blur sticky top-0 z-30">
      <div className="px-5 h-14 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <NavLink to="/list" className="flex items-baseline gap-2 hover:opacity-80 transition-opacity">
            <span className="text-cyan text-lg font-bold tracking-tight">S&amp;P 500</span>
            <span className="text-[10px] text-gray-500 font-medium">Large-Cap Watchlist</span>
          </NavLink>
          <nav className="flex gap-1">
            <NavLink to="/list" className={linkClass}>전체종목</NavLink>
            <NavLink to="/watchlist" className={linkClass}>분석</NavLink>
            <NavLink to="/targets" className={linkClass}>목표가</NavLink>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="티커 또는 기업명을 검색해주세요."
              className="bg-transparent border border-line focus:border-cyan/50 rounded-sm pl-3 pr-7 py-2 text-xs outline-none transition-colors w-[260px] text-gray-300 placeholder:text-gray-600"
            />
            <svg className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-600 pointer-events-none" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
          </div>
        </div>
      </div>

      <MarketTimingBar
        fullRefreshing={fullRefreshing}
        yfinanceBlocked={yfinanceBlocked}
        refreshTrigger={refreshTrigger}
      />
    </header>
  );
}

export default function App() {
  const [fullRefreshing, setFullRefreshing] = useState(false);
  const [progress, setProgress] = useState(null);
  const [yfinanceBlocked, setYfinanceBlocked] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [lastRefreshedAt, setLastRefreshedAt] = useState(null);
  const [watchlistLastRefreshedAt, setWatchlistLastRefreshedAt] = useState(null);
  const [watchlistTrigger, setWatchlistTrigger] = useState(0);
  const [q, setQ] = useState("");

  useEffect(() => {
    api.getRefreshProgress().then((p) => {
      if (p.running) {
        setFullRefreshing(true);
        setProgress({ pct: p.pct, step: p.step });
      }
      if (p.yfinance_blocked !== undefined) setYfinanceBlocked(p.yfinance_blocked);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!fullRefreshing) return;
    const id = setInterval(async () => {
      try {
        const p = await api.getRefreshProgress();
        setProgress({ pct: p.pct, step: p.step });
        if (p.yfinance_blocked !== undefined) setYfinanceBlocked(p.yfinance_blocked);
        if (!p.running) {
          clearInterval(id);
          setFullRefreshing(false);
          setProgress(null);
          if (p.pct === 100) {
            setRefreshTrigger((t) => t + 1);
            setLastRefreshedAt(new Date());
          }
        }
      } catch {
        clearInterval(id);
        setFullRefreshing(false);
        setProgress(null);
      }
    }, 1000);
    return () => clearInterval(id);
  }, [fullRefreshing]);

  async function handleFullRefresh() {
    setFullRefreshing(true);
    setProgress({ pct: 0, step: "시작 중…" });
    try {
      await api.fullRefresh();
    } catch {
      setFullRefreshing(false);
      setProgress(null);
    }
  }

  return (
    <RefreshContext.Provider value={{ fullRefreshing, progress, yfinanceBlocked, refreshTrigger, lastRefreshedAt, handleFullRefresh, watchlistLastRefreshedAt, setWatchlistLastRefreshedAt, watchlistTrigger, setWatchlistTrigger, q, setQ }}>
      <div className="min-h-screen flex flex-col">
        <TopNav />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Navigate to="/list" replace />} />
            <Route path="/list" element={<ListPage />} />
            <Route path="/watchlist" element={<WatchlistPage />} />
            <Route path="/targets" element={<TargetPage />} />
          </Routes>
        </main>
        <footer className="border-t border-line px-5 py-3 text-[10px] text-muted tracking-wide flex justify-between">
          <span>Data: yfinance • Wikipedia • CNN F&amp;G</span>
          <span>이 도구는 투자 자문이 아니며 정보 제공 목적으로만 사용됩니다.</span>
        </footer>
      </div>
    </RefreshContext.Provider>
  );
}
