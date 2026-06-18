"""Thread-safe refresh progress state shared across the process."""
import threading

_lock = threading.Lock()
_state: dict = {"running": False, "pct": 0, "step": "대기 중", "yfinance_blocked": None}


def try_start() -> bool:
    """Atomically check-and-set running. Returns True if successfully acquired."""
    with _lock:
        if _state["running"]:
            return False
        _state["running"] = True
        _state["pct"] = 0
        _state["step"] = ""
        return True


def update(pct: int, step: str = "") -> None:
    with _lock:
        _state["running"] = True
        _state["pct"] = pct
        _state["step"] = step


def finish() -> None:
    with _lock:
        _state["running"] = False
        _state["pct"] = 100
        _state["step"] = "완료"


def fail() -> None:
    with _lock:
        _state["running"] = False
        _state["pct"] = 0
        _state["step"] = "오류 발생"


def set_yfinance_status(blocked: bool) -> None:
    with _lock:
        _state["yfinance_blocked"] = blocked


def get() -> dict:
    with _lock:
        return dict(_state)
