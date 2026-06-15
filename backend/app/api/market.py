"""/api/market endpoints."""
import threading
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import refresh_state
from ..database import get_db
from ..models import MarketTiming
from ..schemas import MarketTimingOut, ScoreBreakdownEntry, UpdateStatus
from ..scheduler import get_next_run
from ..services import scoring
from ..services.updater import refresh_market_timing, run_daily_update

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/timing", response_model=MarketTimingOut)
def get_market_timing(db: Session = Depends(get_db)):
    mt = db.get(MarketTiming, 1)
    if mt is None:
        # Empty defaults — UI will show "—"
        return MarketTimingOut(
            spy_drawdown_52w=None,
            vix=None,
            fear_greed=None,
            timing_score=0,
            captured_at=None,
            breakdown=[],
        )
    score, entries = scoring.score_market_timing(mt.spy_drawdown_52w, mt.vix, mt.fear_greed)
    return MarketTimingOut(
        spy_drawdown_52w=mt.spy_drawdown_52w,
        vix=mt.vix,
        fear_greed=mt.fear_greed,
        timing_score=score,
        captured_at=mt.captured_at,
        next_update=get_next_run(),
        breakdown=[ScoreBreakdownEntry(**e.as_dict()) for e in entries],
    )


@router.post("/timing/refresh", response_model=UpdateStatus)
def refresh_timing(db: Session = Depends(get_db)):
    counts = refresh_market_timing(db)
    return UpdateStatus(ok=True, message="Market timing refreshed", counts=counts)


@router.post("/full-refresh", response_model=UpdateStatus)
def full_refresh():
    if refresh_state.get()["running"]:
        raise HTTPException(status_code=409, detail="이미 새로고침 중입니다.")
    threading.Thread(target=run_daily_update, daemon=True).start()
    return UpdateStatus(ok=True, message="새로고침 시작됨")


@router.get("/refresh-progress")
def get_refresh_progress():
    return refresh_state.get()
