"""/api/stocks endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MarketTiming, Stock, WatchlistItem
from ..schemas import StockListItem
from ..services import scoring

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


class _StockMetrics:
    """Adapter: lets score_stock() work with a Stock ORM row."""
    def __init__(self, s: Stock):
        self.drawdown_52w      = s.drawdown_52w
        self.eps_growth        = getattr(s, "eps_growth", None)
        self.debt_to_equity    = getattr(s, "debt_to_equity", None)
        self.forward_pe_vs_avg = getattr(s, "forward_pe_vs_avg", None)
        self.roe               = getattr(s, "roe", None)
        self.fcf_yield         = getattr(s, "fcf_yield", None)


def _grade_from_stock(s: Stock, market_score: int):
    """Full grade using all bulk-available metrics. Returns (score, key, label, color)."""
    if s.drawdown_52w is None:
        return None, None, None, None
    sc, _ = scoring.score_stock(_StockMetrics(s))
    total = sc + market_score
    return (total, *scoring.grade_for(total))


def _grade_from_watchlist(item: WatchlistItem, market_score: int):
    """Full grade using complete watchlist metrics. Returns (score, key, label, color)."""
    sc, _ = scoring.score_stock(item)
    total = sc + market_score
    return (total, *scoring.grade_for(total))


@router.get("", response_model=list[StockListItem])
def list_stocks(
    q: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=600),
    db: Session = Depends(get_db),
):
    stmt = select(Stock).where(Stock.is_active == True)  # noqa: E712
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(
            Stock.ticker.ilike(like),
            Stock.company_name.ilike(like),
        ))
    if sector:
        stmt = stmt.where(Stock.sector == sector)
    stmt = stmt.order_by(Stock.rank.asc().nulls_last()).limit(limit)
    stocks = db.execute(stmt).scalars().all()

    # Pre-compute full watchlist grades (includes PER deviation) keyed by stock_id
    mt = db.get(MarketTiming, 1)
    market_score = 0
    if mt:
        market_score, _ = scoring.score_market_timing(mt.spy_drawdown_52w, mt.vix, mt.fear_greed)

    wl_grades: dict[int, tuple] = {}
    for item in db.execute(select(WatchlistItem)).scalars().all():
        wl_grades[item.stock_id] = _grade_from_watchlist(item, market_score)

    result = []
    for s in stocks:
        if s.id in wl_grades:
            tech_score, grade_key, grade_label, grade_color = wl_grades[s.id]
        else:
            tech_score, grade_key, grade_label, grade_color = _grade_from_stock(s, market_score)

        result.append(StockListItem(
            id=s.id,
            ticker=s.ticker,
            company_name=s.company_name,
            sector=s.sector,
            market_cap=s.market_cap,
            rank=s.rank,
            in_watchlist=s.id in wl_grades,
            return_1y=getattr(s, "return_1y", None),
            return_3y_avg=getattr(s, "return_3y_avg", None),
            tech_score=tech_score,
            tech_grade=grade_key,
            tech_grade_label=grade_label,
            tech_grade_color=grade_color,
        ))
    return result


@router.get("/sectors", response_model=list[str])
def list_sectors(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Stock.sector)
        .where(Stock.is_active == True, Stock.sector.is_not(None))  # noqa: E712
        .distinct()
    ).all()
    return sorted({row[0] for row in rows if row[0]})


