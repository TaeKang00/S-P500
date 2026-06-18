"""
Scoring engine.

A. Stock Metrics  (per-watchlisted-stock)   max +11
B. Market Timing  (applied uniformly)        max +6

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
    """52주 고점 대비 하락률. MA200과 이중 계산 방지를 위해 최대 +2 캡."""
    if drawdown is None:
        return 0
    if drawdown >= -5:
        return 0
    if -15 <= drawdown < -5:
        return 1
    return 2  # -15% 이하 모두 +2 (기존 -30% 이하 +3 제거)


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


def _score_roe(roe: Optional[float]) -> int:
    """ROE (%). 자기자본 대비 수익률 — 퀄리티 핵심 지표."""
    if roe is None:
        return 0
    if roe >= 20:
        return 2
    if 10 <= roe < 20:
        return 1
    if 5 <= roe < 10:
        return 0
    if 0 <= roe < 5:
        return -1
    return -2  # roe < 0


def _score_fcf_yield(fcf_yield: Optional[float]) -> int:
    """FCF Yield = FCF / 시총 × 100 (%). 실제 현금 창출력."""
    if fcf_yield is None:
        return 0
    if fcf_yield >= 5:
        return 2
    if 3 <= fcf_yield < 5:
        return 1
    if 1 <= fcf_yield < 3:
        return 0
    return -1  # < 1% or negative


def _score_debt_equity(de: Optional[float]) -> int:
    """D/E 기준 완화(0.3→0.5) + 고부채 페널티 추가."""
    if de is None:
        return 0
    if de <= 0.5:
        return 1
    if de > 2.0:
        return -1
    return 0


def score_partial_stock(drawdown_52w: Optional[float]) -> int:
    """Partial stock score using only fast_info data (drawdown only)."""
    return _score_drawdown_52w(drawdown_52w)


def score_stock(metrics) -> tuple[int, list[ScoreEntry]]:
    """Compute the per-stock score and a breakdown."""
    per_score = _score_fwd_pe_vs_avg(metrics.forward_pe_vs_avg)

    # PEG 조정: EPS 성장 20%+ 이면서 PER이 3년 평균보다 높은 경우 페널티 1점 완화.
    # 고성장 기업은 프리미엄 PER이 일부 정당화됨.
    peg_label = "PER 괴리율 (현재PER/3년평균)"
    if (metrics.eps_growth is not None and metrics.eps_growth >= 20
            and metrics.forward_pe_vs_avg is not None and metrics.forward_pe_vs_avg > 5
            and per_score < 0):
        per_score += 1
        peg_label += " *성장주조정"

    entries: list[ScoreEntry] = [
        ScoreEntry("52주 고점 대비 하락률 (%)", metrics.drawdown_52w,
                   _score_drawdown_52w(metrics.drawdown_52w)),
        ScoreEntry(peg_label, metrics.forward_pe_vs_avg, per_score),
        ScoreEntry("EPS Growth (%)", metrics.eps_growth,
                   _score_eps_growth(metrics.eps_growth)),
        ScoreEntry("Debt to Equity", metrics.debt_to_equity,
                   _score_debt_equity(metrics.debt_to_equity)),
        ScoreEntry("ROE (%)", getattr(metrics, "roe", None),
                   _score_roe(getattr(metrics, "roe", None))),
        ScoreEntry("FCF Yield (%)", getattr(metrics, "fcf_yield", None),
                   _score_fcf_yield(getattr(metrics, "fcf_yield", None))),
    ]
    return sum(e.points for e in entries), entries


# ───────────────────────── B. MARKET TIMING ─────────────────────────

def _score_spy_drawdown(dd: Optional[float]) -> int:
    """SPY 52주 하락률. 급락 시 과도 가산 방지를 위해 최대 +2 캡."""
    if dd is None:
        return 0
    if dd >= -5:
        return -1
    if -10 <= dd < -5:
        return 0
    if -20 <= dd < -10:
        return 1
    return 2  # dd < -20 (기존 +3에서 조정)


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
