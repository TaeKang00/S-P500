"""CNN Fear & Greed Index fetcher."""
from __future__ import annotations

import logging
from typing import Optional

import requests

from ..config import FEAR_GREED_URL

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.cnn.com",
    "Referer": "https://www.cnn.com/",
}


def fetch_fear_greed() -> Optional[float]:
    """Return the current Fear & Greed index value (0–100), or None."""
    try:
        resp = requests.get(FEAR_GREED_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # Schema: {"fear_and_greed": {"score": 42.13, ...}, ...}
        score = data.get("fear_and_greed", {}).get("score")
        if score is None:
            return None
        return float(score)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fear & Greed fetch failed: %s", exc)
        return None
