"""Pydantic response/request models."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class StockBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StockListItem(StockBase):
    id: int
    ticker: str
    company_name: str
    sector: Optional[str] = None
    market_cap: Optional[float] = None
    rank: Optional[int] = None
    in_watchlist: bool = False
    return_1y: Optional[float] = None
    return_3y_avg: Optional[float] = None
    tech_score: Optional[int] = None
    tech_grade: Optional[str] = None
    tech_grade_label: Optional[str] = None
    tech_grade_color: Optional[str] = None


class WatchlistAddRequest(BaseModel):
    ticker: str


class WatchlistMetrics(StockBase):
    current_price: Optional[float] = None
    rsi_14: Optional[float] = None
    drawdown_52w: Optional[float] = None
    ma200_deviation: Optional[float] = None
    forward_pe: Optional[float] = None
    current_per: Optional[float] = None
    forward_pe_3y_avg: Optional[float] = None
    forward_pe_vs_avg: Optional[float] = None
    forward_eps: Optional[float] = None
    trailing_eps: Optional[float] = None
    debt_to_equity: Optional[float] = None
    eps_growth: Optional[float] = None
    roe: Optional[float] = None
    fcf_yield: Optional[float] = None
    target_price_mean: Optional[float] = None
    target_price_high: Optional[float] = None
    target_price_low: Optional[float] = None
    recommendation: Optional[str] = None
    analyst_count: Optional[int] = None
    last_refreshed: Optional[datetime] = None


class ScoreBreakdownEntry(BaseModel):
    label: str
    value: Optional[float] = None
    points: int


class ScoreBreakdown(BaseModel):
    stock_score: int
    market_score: int
    total: int
    grade: str
    grade_label: str
    grade_color: str
    stock_breakdown: list[ScoreBreakdownEntry]
    market_breakdown: list[ScoreBreakdownEntry]


class WatchlistItemOut(StockBase):
    id: int
    ticker: str
    company_name: str
    sector: Optional[str] = None
    market_cap: Optional[float] = None
    return_1y: Optional[float] = None
    return_3y_avg: Optional[float] = None
    metrics: WatchlistMetrics
    score: ScoreBreakdown


class MarketTimingOut(BaseModel):
    spy_drawdown_52w: Optional[float] = None
    vix: Optional[float] = None
    fear_greed: Optional[float] = None
    timing_score: int
    captured_at: Optional[datetime] = None
    next_update: Optional[str] = None
    breakdown: list[ScoreBreakdownEntry]


class UpdateStatus(BaseModel):
    ok: bool
    message: str
    counts: Optional[dict] = None
