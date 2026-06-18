"""FastAPI application entrypoint."""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import market, stocks, watchlist
from .config import CORS_ORIGINS
from .database import SessionLocal, init_db
from . import refresh_state
from .scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)
# Yahoo Finance restricts quoteSummary (fundamentals) to paid subscribers — 401s are
# expected and already handled in yfinance_svc.py. Suppress to avoid log spam.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


def _auto_seed_if_empty() -> None:
    """Trigger a full refresh in the background if financial data is missing or incomplete."""
    from sqlalchemy import func, select
    from .models import Stock
    from .services.updater import run_daily_update

    db = SessionLocal()
    try:
        count_with_data = db.execute(
            select(func.count()).select_from(Stock).where(Stock.market_cap.isnot(None))
        ).scalar() or 0
    finally:
        db.close()

    if count_with_data < 100:
        logger.info("No financial data found — auto-starting initial full refresh")
        threading.Thread(target=run_daily_update, daemon=True).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    threading.Thread(target=_auto_seed_if_empty, daemon=True).start()
    yield
    stop_scheduler()


app = FastAPI(
    title="S&P 500 Watchlist API",
    version="1.0.0",
    description="Backend for the S&P 500 watchlist & scoring dashboard.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router)
app.include_router(watchlist.router)
app.include_router(market.router)


@app.get("/api/health")
def health():
    return {"ok": True}
