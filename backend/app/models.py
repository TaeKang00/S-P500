"""SQLAlchemy ORM models."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from .database import Base


class Stock(Base):
    """All S&P 500 constituents — minimal fields for the listing page."""
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True, nullable=False)
    company_name = Column(String, nullable=False)
    sector = Column(String, index=True)
    market_cap = Column(Float)            # USD
    rank = Column(Integer, index=True)    # by market cap, 1 = largest
    is_active = Column(Boolean, default=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    # Technical + fundamental snapshot — refreshed in daily bulk fetch
    drawdown_52w = Column(Float)
    ma200_deviation = Column(Float)
    rsi_14 = Column(Float)
    eps_growth = Column(Float)
    debt_to_equity = Column(Float)
    return_1y = Column(Float)
    return_3y_avg = Column(Float)
    # PER 관련 (income_stmt 포함 전 종목 병렬 조회)
    trailing_eps = Column(Float)
    forward_eps = Column(Float)
    eps_y1 = Column(Float)
    eps_y2 = Column(Float)
    eps_y3 = Column(Float)
    current_per = Column(Float)
    forward_pe_vs_avg = Column(Float)
    business_summary = Column(String)
    roe = Column(Float)        # Return on Equity (%)
    fcf_yield = Column(Float)  # FCF / Market Cap × 100 (%)

    watchlist_item = relationship("WatchlistItem", back_populates="stock", uselist=False)


class WatchlistItem(Base):
    """A user's watchlisted stock — extra fundamentals/technicals fetched only for these."""
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), unique=True, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)

    # Detailed metrics (refreshed daily)
    current_price = Column(Float)
    rsi_14 = Column(Float)
    drawdown_52w = Column(Float)            # percent, negative when below high
    ma200_deviation = Column(Float)         # percent vs 200-day MA
    forward_pe = Column(Float)              # FWD PER = price / forward EPS
    current_per = Column(Float)             # 현재 PER = price / TTM EPS
    forward_pe_3y_avg = Column(Float)       # 3년 평균 PER = price / 3yr avg EPS
    forward_pe_vs_avg = Column(Float)       # PER 괴리율 = (현재PER / 3yr평균PER - 1) × 100
    debt_to_equity = Column(Float)
    eps_growth = Column(Float)              # percent: (fwd_eps/trailing_eps - 1)*100
    # EPS components for 3yr avg PER and EPS growth
    forward_eps = Column(Float)
    trailing_eps = Column(Float)
    eps_y1 = Column(Float)                  # most recent fiscal year EPS
    eps_y2 = Column(Float)
    eps_y3 = Column(Float)
    roe = Column(Float)        # Return on Equity (%)
    fcf_yield = Column(Float)  # FCF / Market Cap × 100 (%)
    # Analyst consensus
    target_price_mean = Column(Float)
    target_price_high = Column(Float)
    target_price_low = Column(Float)
    recommendation = Column(String)   # "strong_buy" / "buy" / "hold" / "sell" / "strong_sell"
    analyst_count = Column(Integer)
    last_refreshed = Column(DateTime, default=datetime.utcnow)

    stock = relationship("Stock", back_populates="watchlist_item")


class MarketTiming(Base):
    """Latest snapshot of macro/market-timing indicators (single row, id=1)."""
    __tablename__ = "market_timing"

    id = Column(Integer, primary_key=True)            # always 1
    spy_drawdown_52w = Column(Float)                  # percent
    vix = Column(Float)
    fear_greed = Column(Float)                        # 0–100
    timing_score = Column(Integer)                    # cached sum
    captured_at = Column(DateTime, default=datetime.utcnow)
