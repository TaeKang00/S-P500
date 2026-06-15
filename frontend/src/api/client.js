const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function req(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  listStocks: ({ q, sector, limit = 500 } = {}) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (sector) params.set("sector", sector);
    params.set("limit", limit);
    return req(`/api/stocks?${params}`);
  },
  listSectors: () => req(`/api/stocks/sectors`),

  listWatchlist: () => req(`/api/watchlist`),
  addWatchlist: (ticker) =>
    req(`/api/watchlist`, { method: "POST", body: JSON.stringify({ ticker }) }),
  removeWatchlist: (ticker) =>
    req(`/api/watchlist/${ticker}`, { method: "DELETE" }),
  refreshWatchlist: () =>
    req(`/api/watchlist/refresh`, { method: "POST" }),

  getMarketTiming: () => req(`/api/market/timing`, { cache: "no-store" }),
  refreshMarketTiming: () =>
    req(`/api/market/timing/refresh`, { method: "POST" }),
  fullRefresh: () =>
    req(`/api/market/full-refresh`, { method: "POST" }),
  getRefreshProgress: () => req(`/api/market/refresh-progress`),
};
