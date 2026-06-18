"""
Daily update job.

Order of operations:
  1. Refresh the S&P 500 constituents list from Wikipedia.
  2. Refresh market cap for every constituent and recompute ranks.
  3. Refresh detailed metrics for *watchlisted* tickers only.
  4. Refresh market-timing snapshot (SPY/VIX/F&G).
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import MarketTiming, Stock, WatchlistItem
from .. import refresh_state
from . import market_data, scoring, wikipedia, yfinance_svc

logger = logging.getLogger(__name__)


# ───────────────────────── 1+2: constituents + market caps ─────────────────────────

def refresh_constituents_and_ranks(db: Session) -> dict:
    """Fetch Wikipedia list, update Stock rows, refresh market caps, recompute ranks."""
    rows = wikipedia.fetch_sp500_constituents()
    existing = {s.ticker: s for s in db.execute(select(Stock)).scalars().all()}
    wiki_tickers = set()

    for row in rows:
        wiki_tickers.add(row["ticker"])
        s = existing.get(row["ticker"])
        if s is None:
            s = Stock(
                ticker=row["ticker"],
                company_name=row["company_name"],
                sector=row["sector"],
                is_active=True,
            )
            db.add(s)
        else:
            s.company_name = row["company_name"]
            s.sector = row["sector"]
            s.is_active = True

    # Mark removed constituents inactive (don't delete — preserves history).
    for ticker, stock in existing.items():
        if ticker not in wiki_tickers:
            stock.is_active = False
    db.commit()

    # Refresh market caps for the currently-active set.
    active = db.execute(select(Stock).where(Stock.is_active == True)).scalars().all()  # noqa: E712

    def _on_fund_progress(done: int, total: int) -> None:
        pct = 10 + int(done / total * 50)  # 10% → 60%
        refresh_state.update(pct, f"재무데이터 조회 중… {done}/{total}")

    def _on_fast_info_progress(done: int, total: int) -> None:
        pct = 60 + int(done / total * 25)  # 60% → 85%
        refresh_state.update(pct, f"시세데이터 조회 중… {done}/{total}")

    refresh_state.update(8, "펀더멘털 데이터 조회 시작…")
    caps = yfinance_svc.fetch_market_caps_bulk(
        [s.ticker for s in active],
        on_progress=_on_fund_progress,
        on_fast_info_progress=_on_fast_info_progress,
    )

    # Guard: if ZERO tickers returned market_cap, something is badly wrong (auth failure).
    # Skip commit entirely to preserve existing data.
    valid_count = sum(1 for v in caps.values() if v.get("market_cap") is not None)
    if valid_count == 0:
        logger.error(
            "Bulk fetch returned 0 valid market caps — likely yfinance auth failure. "
            "Skipping DB update to preserve existing data.",
        )
        refresh_state.set_yfinance_status(True)
        return {"constituents": len(active), "with_market_cap": 0}

    refresh_state.set_yfinance_status(False)
    logger.info("Bulk fetch: %d/%d tickers returned market_cap data", valid_count, len(active))

    now = datetime.utcnow()
    for s in active:
        data = caps.get(s.ticker, {})
        # Only overwrite a field if we actually received a new value.
        # This preserves existing good data for tickers that failed this run.
        for attr, key in (
            ("market_cap", "market_cap"),
            ("drawdown_52w", "drawdown_52w"),
            ("ma200_deviation", "ma200_deviation"),
            ("rsi_14", "rsi_14"),
            ("eps_growth", "eps_growth"),
            ("debt_to_equity", "debt_to_equity"),
            ("return_1y", "return_1y"),
            ("return_3y_avg", "return_3y_avg"),
            ("trailing_eps", "trailing_eps"),
            ("forward_eps", "forward_eps"),
            ("eps_y1", "eps_y1"),
            ("eps_y2", "eps_y2"),
            ("eps_y3", "eps_y3"),
            ("current_per", "current_per"),
            ("forward_pe_vs_avg", "forward_pe_vs_avg"),
            ("business_summary", "business_summary"),
            ("roe", "roe"),
            ("fcf_yield", "fcf_yield"),
        ):
            val = data.get(key)
            if val is not None:
                setattr(s, attr, val)
        s.last_updated = now
    db.commit()

    # Recompute ranks by market cap (NULLs get pushed to the bottom).
    active_sorted = sorted(
        active,
        key=lambda s: (s.market_cap is None, -(s.market_cap or 0)),
    )
    for i, s in enumerate(active_sorted, start=1):
        s.rank = i if s.market_cap else None
    db.commit()
    logger.info("Refreshed %d constituents", len(active))
    return {"constituents": len(active), "with_market_cap": sum(1 for s in active if s.market_cap)}


# ───────────────────────── 단일 종목 즉시 갱신 ─────────────────────────

def refresh_single_item(ticker: str) -> None:
    """추가된 종목 하나만 백그라운드에서 상세 데이터 갱신."""
    db = SessionLocal()
    try:
        stock = db.execute(select(Stock).where(Stock.ticker == ticker)).scalar_one_or_none()
        if not stock:
            return
        item = db.execute(
            select(WatchlistItem).where(WatchlistItem.stock_id == stock.id)
        ).scalar_one_or_none()
        if not item:
            return

        try:
            detail = yfinance_svc.fetch_watchlist_detail(ticker)
        except Exception as exc:  # noqa: BLE001
            logger.warning("single item refresh failed for %s: %s", ticker, exc)
            return

        item.current_price = detail.current_price
        item.rsi_14 = detail.rsi_14
        item.drawdown_52w = detail.drawdown_52w
        item.ma200_deviation = detail.ma200_deviation
        item.forward_pe = detail.forward_pe
        item.forward_eps = detail.forward_eps
        item.trailing_eps = detail.trailing_eps
        item.eps_y1 = detail.eps_y1
        item.eps_y2 = detail.eps_y2
        item.eps_y3 = detail.eps_y3
        item.debt_to_equity = detail.debt_to_equity
        item.roe = detail.roe
        item.fcf_yield = detail.fcf_yield
        item.target_price_mean = detail.target_price_mean
        item.target_price_high = detail.target_price_high
        item.target_price_low = detail.target_price_low
        item.recommendation = detail.recommendation
        item.analyst_count = detail.analyst_count
        item.last_refreshed = datetime.utcnow()

        if detail.forward_eps is not None and detail.trailing_eps and detail.trailing_eps > 0:
            item.eps_growth = (detail.forward_eps / detail.trailing_eps - 1.0) * 100.0
        else:
            item.eps_growth = None

        if detail.current_price and detail.trailing_eps and detail.trailing_eps > 0:
            item.current_per = detail.current_price / detail.trailing_eps
        else:
            item.current_per = None

        eps_vals = [v for v in (detail.eps_y1, detail.eps_y2, detail.eps_y3)
                    if v is not None and v > 0]
        if eps_vals and detail.current_price:
            avg_eps = sum(eps_vals) / len(eps_vals)
            avg_per = detail.current_price / avg_eps
            item.forward_pe_3y_avg = avg_per
            if item.current_per and avg_per > 0:
                item.forward_pe_vs_avg = (item.current_per / avg_per - 1.0) * 100.0
            else:
                item.forward_pe_vs_avg = None
        else:
            item.forward_pe_3y_avg = None
            item.forward_pe_vs_avg = None

        db.commit()
        logger.info("single item refresh complete: %s", ticker)
    finally:
        db.close()


# ───────────────────────── 3+4: watchlist details + FWD PE history ─────────────────────────

def refresh_watchlist_details(db: Session, on_progress=None) -> dict:
    """For each watchlisted stock, fetch detail and recompute scores using updated formulas."""
    items: list[WatchlistItem] = db.execute(select(WatchlistItem)).scalars().all()
    total = len(items)
    refreshed = 0

    for i, item in enumerate(items):
        stock = item.stock
        if on_progress and total > 0:
            on_progress(int(i / total * 100), f"{stock.ticker} 갱신 중… ({i+1}/{total})")
        try:
            detail = yfinance_svc.fetch_watchlist_detail(stock.ticker)
        except Exception as exc:  # noqa: BLE001
            logger.warning("watchlist detail fetch failed for %s: %s", stock.ticker, exc)
            continue

        item.current_price = detail.current_price
        item.rsi_14 = detail.rsi_14
        item.drawdown_52w = detail.drawdown_52w
        item.ma200_deviation = detail.ma200_deviation
        item.forward_pe = detail.forward_pe
        item.forward_eps = detail.forward_eps
        item.trailing_eps = detail.trailing_eps
        item.eps_y1 = detail.eps_y1
        item.eps_y2 = detail.eps_y2
        item.eps_y3 = detail.eps_y3
        item.debt_to_equity = detail.debt_to_equity
        item.roe = detail.roe
        item.fcf_yield = detail.fcf_yield
        item.target_price_mean = detail.target_price_mean
        item.target_price_high = detail.target_price_high
        item.target_price_low = detail.target_price_low
        item.recommendation = detail.recommendation
        item.analyst_count = detail.analyst_count
        item.last_refreshed = datetime.utcnow()

        # EPS Growth = (Forward EPS / Trailing EPS - 1) × 100
        if detail.forward_eps is not None and detail.trailing_eps and detail.trailing_eps > 0:
            item.eps_growth = (detail.forward_eps / detail.trailing_eps - 1.0) * 100.0
        else:
            item.eps_growth = None

        # 현재 PER = 현재 주가 / TTM EPS
        if detail.current_price and detail.trailing_eps and detail.trailing_eps > 0:
            item.current_per = detail.current_price / detail.trailing_eps
        else:
            item.current_per = None

        # 3년 평균 PER = 현재 주가 / 3년 평균 EPS
        # PER 괴리율 = (현재 PER / 3년 평균 PER - 1) × 100
        eps_vals = [v for v in (detail.eps_y1, detail.eps_y2, detail.eps_y3)
                    if v is not None and v > 0]
        if eps_vals and detail.current_price:
            avg_eps = sum(eps_vals) / len(eps_vals)
            avg_per = detail.current_price / avg_eps
            item.forward_pe_3y_avg = avg_per
            if item.current_per and avg_per > 0:
                item.forward_pe_vs_avg = (item.current_per / avg_per - 1.0) * 100.0
            else:
                item.forward_pe_vs_avg = None
        else:
            item.forward_pe_3y_avg = None
            item.forward_pe_vs_avg = None

        refreshed += 1

    db.commit()
    logger.info("Refreshed %d watchlist details", refreshed)
    return {"watchlist_refreshed": refreshed}


# ───────────────────────── 5: market timing ─────────────────────────

def refresh_market_timing(db: Session) -> dict:
    spy_dd = yfinance_svc.fetch_spy_drawdown_52w()
    vix = yfinance_svc.fetch_vix()
    fg = market_data.fetch_fear_greed()
    total, _ = scoring.score_market_timing(spy_dd, vix, fg)

    row = db.get(MarketTiming, 1)
    if row is None:
        row = MarketTiming(id=1)
        db.add(row)
    row.spy_drawdown_52w = spy_dd
    row.vix = vix
    row.fear_greed = fg
    row.timing_score = total
    row.captured_at = datetime.utcnow()
    db.commit()
    logger.info("Refreshed market timing: SPY=%s VIX=%s F&G=%s score=%d",
                spy_dd, vix, fg, total)
    return {"spy_drawdown_52w": spy_dd, "vix": vix, "fear_greed": fg, "timing_score": total}


# ───────────────────────── orchestrator ─────────────────────────

def run_daily_update(_started: bool = False) -> dict:
    """Top-level entry. Safe to call manually too."""
    if not _started:
        if not refresh_state.try_start():
            logger.info("run_daily_update: already running — skipped")
            return {}
    logger.info("===== run_daily_update started at %s =====", datetime.utcnow())
    refresh_state.update(2, "종목 목록 갱신 중…")
    db = SessionLocal()
    counts: dict = {}
    try:
        result = refresh_constituents_and_ranks(db)
        counts.update(result)

        if result.get("with_market_cap", 0) == 0:
            logger.error("run_daily_update: market cap fetch returned 0 — aborting to preserve existing data")
            refresh_state.fail()
            return counts

        refresh_state.update(87, "데이터 저장 중…")
        refresh_state.update(90, "관심종목 업데이트 중…")

        def _wl_progress(pct: int, step: str) -> None:
            refresh_state.update(90 + int(pct * 7 / 100), step)

        counts.update(refresh_watchlist_details(db, on_progress=_wl_progress))
        refresh_state.update(97, "시장 타이밍 업데이트 중…")
        counts.update(refresh_market_timing(db))
        refresh_state.finish()
        return counts
    except Exception:
        refresh_state.fail()
        raise
    finally:
        db.close()
        logger.info("===== run_daily_update finished =====")
