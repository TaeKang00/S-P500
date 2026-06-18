"""/api/watchlist endpoints."""
import logging
import threading
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .. import refresh_state
from ..database import get_db
from ..models import MarketTiming, Stock, WatchlistItem
from ..schemas import (
    ScoreBreakdown,
    ScoreBreakdownEntry,
    UpdateStatus,
    WatchlistAddRequest,
    WatchlistItemOut,
    WatchlistMetrics,
)
from ..services import scoring, yfinance_svc
from ..services.updater import run_watchlist_refresh

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])
logger = logging.getLogger(__name__)


def _build_scored_item(item: WatchlistItem, market_score: int,
                       market_entries: list) -> WatchlistItemOut:
    stock_total, stock_entries = scoring.score_stock(item)
    total = stock_total + market_score
    key, label, color = scoring.grade_for(total)

    return WatchlistItemOut(
        id=item.stock.id,
        ticker=item.stock.ticker,
        company_name=item.stock.company_name,
        sector=item.stock.sector,
        market_cap=item.stock.market_cap,
        return_1y=item.stock.return_1y,
        return_3y_avg=item.stock.return_3y_avg,
        metrics=WatchlistMetrics(
            current_price=item.current_price,
            rsi_14=item.rsi_14,
            drawdown_52w=item.drawdown_52w,
            ma200_deviation=item.ma200_deviation,
            forward_pe=item.forward_pe,
            current_per=item.current_per,
            forward_pe_3y_avg=item.forward_pe_3y_avg,
            forward_pe_vs_avg=item.forward_pe_vs_avg,
            forward_eps=item.forward_eps,
            trailing_eps=item.trailing_eps,
            debt_to_equity=item.debt_to_equity,
            eps_growth=item.eps_growth,
            roe=item.roe,
            fcf_yield=item.fcf_yield,
            last_refreshed=item.last_refreshed,
        ),
        score=ScoreBreakdown(
            stock_score=stock_total,
            market_score=market_score,
            total=total,
            grade=key,
            grade_label=label,
            grade_color=color,
            stock_breakdown=[ScoreBreakdownEntry(**e.as_dict()) for e in stock_entries],
            market_breakdown=[ScoreBreakdownEntry(**e.as_dict()) for e in market_entries],
        ),
    )


def _current_market_score(db: Session):
    mt = db.get(MarketTiming, 1)
    if mt is None:
        return 0, []
    score, entries = scoring.score_market_timing(mt.spy_drawdown_52w, mt.vix, mt.fear_greed)
    return score, entries


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist(db: Session = Depends(get_db)):
    items = db.execute(select(WatchlistItem).options(joinedload(WatchlistItem.stock))).scalars().all()
    market_score, market_entries = _current_market_score(db)
    return [_build_scored_item(i, market_score, market_entries) for i in items]


@router.post("", response_model=WatchlistItemOut, status_code=status.HTTP_201_CREATED)
def add_to_watchlist(req: WatchlistAddRequest, db: Session = Depends(get_db)):
    ticker = req.ticker.upper().replace(".", "-")
    stock = db.execute(select(Stock).where(Stock.ticker == ticker)).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} not in S&P 500 list")

    existing = db.execute(
        select(WatchlistItem).where(WatchlistItem.stock_id == stock.id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Already in watchlist")

    # current_price ≈ current_per × trailing_eps (raw, unrounded — used for PER derivations)
    current_price_est = None
    if stock.current_per and stock.trailing_eps and stock.trailing_eps > 0:
        current_price_est = stock.current_per * stock.trailing_eps

    item = WatchlistItem(
        stock_id=stock.id,
        added_at=datetime.utcnow(),
        current_price=round(current_price_est, 2) if current_price_est is not None else None,
        drawdown_52w=stock.drawdown_52w,
        ma200_deviation=stock.ma200_deviation,
        rsi_14=stock.rsi_14,
        eps_growth=stock.eps_growth,
        debt_to_equity=stock.debt_to_equity,
        trailing_eps=stock.trailing_eps,
        forward_eps=stock.forward_eps,
        eps_y1=stock.eps_y1,
        eps_y2=stock.eps_y2,
        eps_y3=stock.eps_y3,
        current_per=stock.current_per,
        forward_pe_vs_avg=stock.forward_pe_vs_avg,
        roe=stock.roe,
        fcf_yield=stock.fcf_yield,
        last_refreshed=stock.last_updated,
    )
    # FWD PER = current_price / forward_eps
    if current_price_est and stock.forward_eps and stock.forward_eps > 0:
        item.forward_pe = current_price_est / stock.forward_eps
    # 3yr avg PER = current_per / (1 + forward_pe_vs_avg/100)
    # divisor must be positive — negative would produce a meaningless negative PER
    if stock.current_per and stock.forward_pe_vs_avg is not None:
        divisor = 1.0 + stock.forward_pe_vs_avg / 100.0
        if divisor > 0:
            item.forward_pe_3y_avg = stock.current_per / divisor
    db.add(item)
    db.commit()
    db.refresh(item)

    market_score, market_entries = _current_market_score(db)
    return _build_scored_item(item, market_score, market_entries)


@router.delete("/{ticker}", response_model=UpdateStatus)
def remove_from_watchlist(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.upper().replace(".", "-")
    stock = db.execute(select(Stock).where(Stock.ticker == ticker)).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    item = db.execute(
        select(WatchlistItem).where(WatchlistItem.stock_id == stock.id)
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Not in watchlist")
    db.delete(item)
    db.commit()
    return UpdateStatus(ok=True, message=f"{ticker} removed from watchlist")


@router.post("/refresh", response_model=UpdateStatus)
def refresh_now():
    """Start a background refresh of all watchlist detail metrics."""
    if refresh_state.get()["running"]:
        raise HTTPException(status_code=409, detail="이미 새로고침 중입니다.")
    threading.Thread(target=run_watchlist_refresh, daemon=True).start()
    return UpdateStatus(ok=True, message="관심종목 갱신 시작됨")
