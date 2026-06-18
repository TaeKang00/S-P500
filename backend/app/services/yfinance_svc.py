"""
yfinance wrappers.

Two distinct fetch surfaces:

 * `fetch_market_caps_bulk`  — light call used during the daily refresh of
   the *entire* S&P 500. We only need market cap to compute ranks.

 * `fetch_watchlist_detail`  — heavier call used only for tickers the user
   has actually added to the watchlist. Pulls price history (for RSI, 52w
   drawdown, MA200), forward PE, debt/equity and EPS growth.
"""
from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# ───────────────────────── helpers ─────────────────────────

def _clean(x):
    """Coerce nan/None to None."""
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def _rsi(series: pd.Series, period: int = 14) -> Optional[float]:
    if series is None or len(series) < period + 1:
        return None
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return _clean(float(val)) if pd.notna(val) else None


# ───────────────────────── market caps ─────────────────────────

def _extract_price_metrics(raw: "pd.DataFrame", tickers: list[str]) -> dict[str, dict]:
    """Extract RSI / return metrics from a downloaded close-price DataFrame."""
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"]
    elif "Close" in raw.columns and len(tickers) == 1:
        close = raw[["Close"]].rename(columns={"Close": tickers[0]})
    else:
        return {}

    result: dict[str, dict] = {}
    for t in tickers:
        if t not in close.columns:
            continue
        s = close[t].dropna()
        if len(s) < 15:
            continue
        m: dict = {}
        m["rsi_14"] = _rsi(s)
        n = len(s)
        if n >= 252:
            m["return_1y"] = _clean(float((s.iloc[-1] / s.iloc[-252] - 1) * 100))
        annual = []
        for lookback in [252, 504, 756]:
            if n >= lookback + 252:
                annual.append(float((s.iloc[-lookback] / s.iloc[-lookback - 252] - 1) * 100))
        if n >= 252:
            annual.insert(0, float((s.iloc[-1] / s.iloc[-252] - 1) * 100))
        annual = annual[:3]
        if annual:
            m["return_3y_avg"] = _clean(sum(annual) / len(annual))
        result[t] = m
    return result


def _download_chunk(chunk: list[str]) -> dict[str, dict]:
    """Download price history for a chunk; return empty dict on failure."""
    try:
        raw = yf.download(tickers=" ".join(chunk), period="3y",
                          auto_adjust=False, progress=False, threads=True)
        if not raw.empty:
            return _extract_price_metrics(raw, chunk)
    except Exception as exc:
        logger.warning("yf.download chunk(%d) failed: %s", len(chunk), exc)
    return {}


def _fetch_bulk_price_metrics(tickers: list[str], chunk_size: int = 100) -> dict[str, dict]:
    """Download 3Y of close prices in chunks (with sub-chunk fallback on failure)."""
    result: dict[str, dict] = {}
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i: i + chunk_size]
        got = _download_chunk(chunk)
        if got:
            result.update(got)
        else:
            # Retry with sub-chunks of 25 tickers
            for j in range(0, len(chunk), 25):
                sub = chunk[j: j + 25]
                sub_got = _download_chunk(sub)
                if sub_got:
                    result.update(sub_got)
                else:
                    # Per-ticker fallback for any still missing
                    for t in sub:
                        result.update(_download_chunk([t]))
    return result


def _fetch_fundamentals_parallel(
    tickers: list[str],
    max_workers: int = 8,
    on_progress=None,
    total_timeout: int = 480,
) -> dict[str, dict]:
    """Fetch .info + annual EPS (income_stmt) for all tickers in parallel."""
    import threading as _threading
    _done = 0
    _lock = _threading.Lock()
    total = len(tickers)
    _empty = {"info": {}, "eps_y1": None, "eps_y2": None, "eps_y3": None}

    def _one(t: str):
        nonlocal _done
        try:
            tk = yf.Ticker(t)
            info = tk.info or {}
            eps_y1, eps_y2, eps_y3 = _fetch_annual_eps(tk)
            data = {"info": info, "eps_y1": eps_y1, "eps_y2": eps_y2, "eps_y3": eps_y3}
        except Exception:
            data = dict(_empty)
        time.sleep(0.15)
        with _lock:
            _done += 1
            if on_progress:
                on_progress(_done, total)
        return t, data

    result: dict[str, dict] = {}
    pool = ThreadPoolExecutor(max_workers=max_workers)
    future_to_ticker = {pool.submit(_one, t): t for t in tickers}
    try:
        for future in as_completed(future_to_ticker, timeout=total_timeout):
            t = future_to_ticker[future]
            try:
                _, data = future.result()
                result[t] = data
            except Exception:
                result[t] = dict(_empty)
    except Exception:
        logger.warning("_fetch_fundamentals_parallel timed out after %ds — filling remaining with empty", total_timeout)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    for t in tickers:
        if t not in result:
            result[t] = dict(_empty)
    return result


def _fast_info_from_ticker(tk) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """(market_cap, price, drawdown_52w, ma200_deviation) from a Ticker's fast_info."""
    fi = tk.fast_info
    cap = getattr(fi, "market_cap", None)
    price = getattr(fi, "last_price", None)
    if cap is None:
        shares = getattr(fi, "shares", None)
        if price and shares:
            cap = price * shares
    cap = _clean(float(cap)) if cap else None

    drawdown = None
    year_high = getattr(fi, "year_high", None)
    if price and year_high and year_high > 0:
        drawdown = _clean((price / year_high - 1.0) * 100.0)

    ma200_dev = None
    ma200 = getattr(fi, "two_hundred_day_average", None)
    if price and ma200 and ma200 > 0:
        ma200_dev = _clean((price / ma200 - 1.0) * 100.0)

    return cap, price, drawdown, ma200_dev


def _process_fast_info_batch(
    batch: list[str],
    fundamentals_map: dict,
    price_metrics: dict,
) -> dict[str, dict]:
    """Process one chunk of tickers via fast_info + pre-fetched fundamentals/price data."""
    result: dict[str, dict] = {}

    batch_obj: Optional[object] = None
    try:
        batch_obj = yf.Tickers(" ".join(batch))
    except Exception as exc:  # noqa: BLE001
        logger.warning("yf.Tickers batch failed, falling back to individual calls: %s", exc)

    for t in batch:
        entry: dict = {}
        price: Optional[float] = None
        try:
            tk = batch_obj.tickers.get(t) if batch_obj is not None else None
            if tk is None:
                tk = yf.Ticker(t)  # individual fallback

            cap, price, drawdown, ma200_dev = _fast_info_from_ticker(tk)
            entry["market_cap"] = cap
            entry["drawdown_52w"] = drawdown
            entry["ma200_deviation"] = ma200_dev

        except Exception as exc:  # noqa: BLE001
            logger.debug("fast_info fetch failed for %s: %s", t, exc)

        pm = price_metrics.get(t, {})
        entry["rsi_14"] = pm.get("rsi_14")
        entry["return_1y"] = pm.get("return_1y")
        entry["return_3y_avg"] = pm.get("return_3y_avg")

        fund = fundamentals_map.get(t, {})
        info = fund.get("info", {})
        eps_y1 = fund.get("eps_y1")
        eps_y2 = fund.get("eps_y2")
        eps_y3 = fund.get("eps_y3")

        fwd_eps = _clean(info.get("forwardEps"))
        trail_eps = _clean(info.get("trailingEps"))
        entry["forward_eps"] = fwd_eps
        entry["trailing_eps"] = trail_eps
        entry["eps_y1"] = eps_y1
        entry["eps_y2"] = eps_y2
        entry["eps_y3"] = eps_y3

        if fwd_eps is not None and trail_eps and trail_eps > 0:
            entry["eps_growth"] = _clean((fwd_eps / trail_eps - 1.0) * 100.0)

        de = info.get("debtToEquity")
        if de is not None and not (isinstance(de, float) and math.isnan(de)):
            de = float(de)
            if de > 5:
                de = de / 100.0
            entry["debt_to_equity"] = _clean(de)

        summary = info.get("longBusinessSummary", "")
        if summary:
            entry["business_summary"] = summary[:600]

        roe_raw = info.get("returnOnEquity")
        if roe_raw is not None and not (isinstance(roe_raw, float) and math.isnan(roe_raw)):
            entry["roe"] = _clean(float(roe_raw) * 100.0)

        fcf_raw = info.get("freeCashflow")
        mcap_raw = info.get("marketCap") or (cap if cap else None)
        if fcf_raw is not None and mcap_raw and mcap_raw > 0:
            entry["fcf_yield"] = _clean(float(fcf_raw) / float(mcap_raw) * 100.0)

        if price and trail_eps and trail_eps > 0:
            current_per = price / trail_eps
            entry["current_per"] = _clean(current_per)
            eps_vals = [v for v in (eps_y1, eps_y2, eps_y3) if v is not None and v > 0]
            if eps_vals:
                avg_eps = sum(eps_vals) / len(eps_vals)
                avg_per = price / avg_eps
                if avg_per > 0:
                    entry["forward_pe_vs_avg"] = _clean((current_per / avg_per - 1.0) * 100.0)

        result[t] = entry
    return result


def fetch_market_caps_bulk(
    tickers: Iterable[str],
    chunk_size: int = 50,
    on_progress=None,
    on_fast_info_progress=None,
) -> dict[str, dict]:
    """
    For each ticker return a dict with market_cap, drawdown_52w, ma200_deviation, etc.

    Phase 1: price history + fundamentals (parallel, I/O-bound).
    Phase 2: fast_info chunks (sequential, rate-limit-safe).
    Phase 3: retry tickers still missing market_cap.
    """
    tickers = list(tickers)
    out: dict[str, dict] = {}

    logger.info("fetch_market_caps_bulk: parallel price + fundamentals for %d tickers", len(tickers))
    with ThreadPoolExecutor(max_workers=2) as outer:
        price_future = outer.submit(_fetch_bulk_price_metrics, tickers)
        fund_future = outer.submit(_fetch_fundamentals_parallel, tickers, 10, on_progress)
        price_metrics = price_future.result()
        fundamentals_map = fund_future.result()

    # Phase 2: fast_info — one progress tick per batch
    total_batches = max(1, (len(tickers) + chunk_size - 1) // chunk_size)
    logger.info("fetch_market_caps_bulk: fast_info %d batches for %d tickers", total_batches, len(tickers))
    for batch_idx, i in enumerate(range(0, len(tickers), chunk_size)):
        batch = tickers[i: i + chunk_size]
        out.update(_process_fast_info_batch(batch, fundamentals_map, price_metrics))
        if on_fast_info_progress:
            on_fast_info_progress(batch_idx + 1, total_batches)

    # Phase 3: retry tickers still missing market_cap (up to 60)
    missing = [t for t in tickers if not out.get(t, {}).get("market_cap")][:60]
    if missing:
        logger.info("fetch_market_caps_bulk: retrying %d tickers with no market_cap", len(missing))
        total_retry = len(missing)
        for retry_idx, t in enumerate(missing):
            try:
                cap, price, drawdown, ma200_dev = _fast_info_from_ticker(yf.Ticker(t))
                if cap:
                    entry = out.get(t, {})
                    entry["market_cap"] = cap
                    if drawdown is not None:
                        entry["drawdown_52w"] = drawdown
                    if ma200_dev is not None:
                        entry["ma200_deviation"] = ma200_dev
                    out[t] = entry
            except Exception as exc:  # noqa: BLE001
                logger.debug("retry failed for %s: %s", t, exc)
            time.sleep(0.3)
            if on_fast_info_progress:
                on_fast_info_progress(total_batches + retry_idx + 1, total_batches + total_retry)

    return out


# ───────────────────────── watchlist detail ─────────────────────────

@dataclass
class StockDetail:
    current_price: Optional[float] = None
    rsi_14: Optional[float] = None
    drawdown_52w: Optional[float] = None
    ma200_deviation: Optional[float] = None
    forward_pe: Optional[float] = None
    forward_eps: Optional[float] = None
    trailing_eps: Optional[float] = None
    eps_y1: Optional[float] = None  # most recent fiscal year EPS
    eps_y2: Optional[float] = None
    eps_y3: Optional[float] = None
    debt_to_equity: Optional[float] = None
    roe: Optional[float] = None        # Return on Equity (%)
    fcf_yield: Optional[float] = None  # FCF / Market Cap × 100 (%)


def fetch_watchlist_detail(ticker: str) -> StockDetail:
    """Pull all numbers needed by the scoring engine for one ticker."""
    tk = yf.Ticker(ticker)
    detail = StockDetail()

    # — Price history: 1y for RSI + 52w drawdown, but request a bit more for MA200.
    try:
        hist = tk.history(period="1y", auto_adjust=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("history(1y) failed for %s: %s", ticker, exc)
        hist = pd.DataFrame()

    if not hist.empty and "Close" in hist.columns:
        closes = hist["Close"].dropna()
        if not closes.empty:
            current = float(closes.iloc[-1])
            detail.current_price = _clean(current)
            detail.rsi_14 = _rsi(closes)

    # Use fast_info.year_high (intraday) for consistency with bulk fetch.
    try:
        fi = tk.fast_info
        year_high = getattr(fi, "year_high", None)
        price = getattr(fi, "last_price", None) or detail.current_price
        if price and year_high and year_high > 0:
            detail.drawdown_52w = _clean((price / year_high - 1.0) * 100.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("fast_info for drawdown failed for %s: %s", ticker, exc)

    # MA200 needs ~14 months of data
    try:
        hist_long = tk.history(period="14mo", auto_adjust=False)
        if not hist_long.empty and "Close" in hist_long.columns:
            closes_long = hist_long["Close"].dropna()
            if len(closes_long) >= 200:
                ma200 = float(closes_long.tail(200).mean())
                current = float(closes_long.iloc[-1])
                if ma200 > 0:
                    detail.ma200_deviation = _clean((current / ma200 - 1.0) * 100.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("history(14mo) failed for %s: %s", ticker, exc)

    # — Fundamentals: forward PE, debt/equity, EPS data.
    info = {}
    try:
        info = tk.info or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning(".info failed for %s: %s", ticker, exc)

    detail.forward_pe = _clean(info.get("forwardPE"))
    detail.forward_eps = _clean(info.get("forwardEps"))
    detail.trailing_eps = _clean(info.get("trailingEps"))

    roe_raw = info.get("returnOnEquity")
    if roe_raw is not None and not (isinstance(roe_raw, float) and math.isnan(roe_raw)):
        detail.roe = _clean(float(roe_raw) * 100.0)

    fcf_raw = info.get("freeCashflow")
    mcap_fi = getattr(tk.fast_info, "market_cap", None)
    mcap = mcap_fi or info.get("marketCap")
    if fcf_raw is not None and mcap and float(mcap) > 0:
        detail.fcf_yield = _clean(float(fcf_raw) / float(mcap) * 100.0)

    de = info.get("debtToEquity")
    if de is not None and not (isinstance(de, float) and math.isnan(de)):
        de = float(de)
        if de > 5:  # almost certainly a percent
            de = de / 100.0
        detail.debt_to_equity = _clean(de)

    # Historical annual EPS from income statement (last 3 fiscal years).
    detail.eps_y1, detail.eps_y2, detail.eps_y3 = _fetch_annual_eps(tk)

    return detail


def _fetch_annual_eps(tk) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (eps_y1, eps_y2, eps_y3) from the annual income statement."""
    try:
        income = tk.income_stmt
        if income is None or income.empty:
            return None, None, None
        for key in ("Diluted EPS", "Basic EPS", "EPS"):
            if key in income.index:
                row = income.loc[key].dropna()
                eps_y1 = _clean(float(row.iloc[0])) if len(row) > 0 else None
                eps_y2 = _clean(float(row.iloc[1])) if len(row) > 1 else None
                eps_y3 = _clean(float(row.iloc[2])) if len(row) > 2 else None
                return eps_y1, eps_y2, eps_y3
    except Exception as exc:  # noqa: BLE001
        logger.debug("annual EPS fetch failed: %s", exc)
    return None, None, None


# ───────────────────────── SPY / VIX ─────────────────────────

def fetch_spy_drawdown_52w() -> Optional[float]:
    try:
        spy = yf.Ticker("SPY").history(period="1y", auto_adjust=False)
        closes = spy["Close"].dropna()
        if closes.empty:
            return None
        current = float(closes.iloc[-1])
        high = float(closes.max())
        if high <= 0:
            return None
        return _clean((current / high - 1.0) * 100.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SPY drawdown fetch failed: %s", exc)
        return None


def fetch_vix() -> Optional[float]:
    try:
        vix = yf.Ticker("^VIX").history(period="5d", auto_adjust=False)
        closes = vix["Close"].dropna()
        if closes.empty:
            return None
        return _clean(float(closes.iloc[-1]))
    except Exception as exc:  # noqa: BLE001
        logger.warning("VIX fetch failed: %s", exc)
        return None
