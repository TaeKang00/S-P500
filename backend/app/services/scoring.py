"""
Scoring engine.

Implements both rule-sets from the spec verbatim:
  A. Stock Metrics  (per-watchlisted-stock)
  B. Market Timing  (applied uniformly to every watchlisted stock)

Final grade is based on the sum of A + B.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScoreEntry:
    label: str
    value: Optional[float]
    points: int

    def as_dict(self):
        return {"label": self.label, "value": self.value, "points": self.points}


@dataclass
class TotalScore:
    stock_score: int
    market_score: int
    stock_breakdown: list = field(default_factory=list)
    market_breakdown: list = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.stock_score + self.market_score


# ─────────────────────────── A. STOCK METRICS ───────────────────────────

def _score_drawdown_52w(drawdown: Optional[float]) -> int:
    """52주 고점 대비 하락률 (drawdown is negative, e.g. -12.5 means down 12.5%)."""
    if drawdown is None:
        return 0
    if drawdown >= -5:
        return 0
    if -15 <= drawdown < -5:
        return 1
    if -30 <= drawdown < -15:
        return 2
    return 3  # drawdown < -30


def _score_ma200_deviation(dev: Optional[float]) -> int:
    """200일 이동평균 괴리율 (positive = above MA200)."""
    if dev is None:
        return 0
    if dev > 20:
        return -2
    if 10 <= dev <= 20:
        return -1
    if -5 <= dev < 10:
        return 0
    if -15 <= dev < -5:
        return 1
    return 2  # dev < -15


def _score_fwd_pe_vs_avg(diff: Optional[float]) -> int:
    """3년 평균 FWD PE 대비 차이(%) — diff > 0 means currently more expensive than 3y avg."""
    if diff is None:
        return 0
    if diff > 15:
        return -2
    if 5 <= diff <= 15:
        return -1
    if -5 <= diff < 5:
        return 0
    if -15 <= diff < -5:
        return 1
    return 2  # diff < -15


def _score_eps_growth(g: Optional[float]) -> int:
    """EPS Growth (%)."""
    if g is None:
        return 0
    if g >= 20:
        return 2
    if 5 <= g < 20:
        return 1
    if -5 <= g < 5:
        return 0
    if -20 <= g < -5:
        return -1
    return -2  # g < -20


def _score_rsi(rsi: Optional[float]) -> int:
    if rsi is None:
        return 0
    if rsi <= 25:
        return 1
    if rsi >= 75:
        return -1
    return 0


def _score_debt_equity(de: Optional[float]) -> int:
    if de is None:
        return 0
    return 1 if de <= 0.3 else 0


def score_partial_stock(drawdown_52w: Optional[float], ma200_deviation: Optional[float]) -> int:
    """Partial stock score using only fast_info data (no RSI/PER/EPS/D/E)."""
    return _score_drawdown_52w(drawdown_52w) + _score_ma200_deviation(ma200_deviation)


def score_stock(metrics) -> tuple[int, list[ScoreEntry]]:
    """Compute the per-stock score and a breakdown."""
    entries: list[ScoreEntry] = [
        ScoreEntry("52주 고점 대비 하락률 (%)", metrics.drawdown_52w,
                   _score_drawdown_52w(metrics.drawdown_52w)),
        ScoreEntry("200일 이동평균 괴리율 (%)", metrics.ma200_deviation,
                   _score_ma200_deviation(metrics.ma200_deviation)),
        ScoreEntry("PER 괴리율 (현재PER/3년평균)", metrics.forward_pe_vs_avg,
                   _score_fwd_pe_vs_avg(metrics.forward_pe_vs_avg)),
        ScoreEntry("EPS Growth (%)", metrics.eps_growth,
                   _score_eps_growth(metrics.eps_growth)),
        ScoreEntry("RSI (14)", metrics.rsi_14, _score_rsi(metrics.rsi_14)),
        ScoreEntry("Debt to Equity", metrics.debt_to_equity,
                   _score_debt_equity(metrics.debt_to_equity)),
    ]
    return sum(e.points for e in entries), entries


# ───────────────────────── B. MARKET TIMING ─────────────────────────

def _score_spy_drawdown(dd: Optional[float]) -> int:
    """SPY 52주 하락률 (negative). Spec uses ‘drop sizes’."""
    if dd is None:
        return 0
    if dd >= -5:
        return -1
    if -10 <= dd < -5:
        return 0
    if -20 <= dd < -10:
        return 1
    return 3  # dd < -20


def _score_vix(vix: Optional[float]) -> int:
    if vix is None:
        return 0
    if vix > 30:
        return 2
    if 20 <= vix <= 30:
        return 1
    if 15 <= vix < 20:
        return 0
    return -1  # vix < 15


def _score_fear_greed(fg: Optional[float]) -> int:
    if fg is None:
        return 0
    if fg <= 10:
        return 2
    if 10 < fg <= 30:
        return 1
    if 30 < fg < 70:
        return 0
    return -1  # fg >= 70


def score_market_timing(spy_dd: Optional[float],
                        vix: Optional[float],
                        fg: Optional[float]) -> tuple[int, list[ScoreEntry]]:
    entries = [
        ScoreEntry("SPY 52주 하락률 (%)", spy_dd, _score_spy_drawdown(spy_dd)),
        ScoreEntry("VIX 지수", vix, _score_vix(vix)),
        ScoreEntry("Fear & Greed Index", fg, _score_fear_greed(fg)),
    ]
    return sum(e.points for e in entries), entries


# ───────────────────────── FINAL GRADE ─────────────────────────

def grade_for(total: int) -> tuple[str, str, str]:
    """Return (key, label, color hex) for a combined score."""
    if total >= 8:
        return "STRONG_BUY", "매수 (강한 시그널)", "#10b981"
    if total >= 4:
        return "BUY_QUEUE", "매수 대기", "#22c55e"
    if total >= -1:
        return "HOLD", "관망", "#9ca3af"
    if total >= -5:
        return "SELL_QUEUE", "매도 대기", "#f59e0b"
    return "SELL", "매도", "#ef4444"
