"""Scrape S&P 500 constituents from Wikipedia."""
from __future__ import annotations

import io
import logging
from typing import List

import pandas as pd
import requests

from ..config import WIKIPEDIA_SP500_URL

logger = logging.getLogger(__name__)

UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124 Safari/537.36"
    )
}


def fetch_sp500_constituents() -> List[dict]:
    """
    Return a list of dicts: {ticker, company_name, sector}.

    Uses pandas.read_html with the first table on the Wikipedia page.
    Handles common ticker quirks (BRK.B -> BRK-B for yfinance).
    """
    logger.info("Fetching S&P 500 constituents from Wikipedia…")
    resp = requests.get(WIKIPEDIA_SP500_URL, headers=UA, timeout=20)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    df = tables[0]

    # Normalise column names — Wikipedia table headers occasionally shift.
    cols = {c.lower(): c for c in df.columns}
    sym_col = cols.get("symbol") or cols.get("ticker symbol")
    name_col = cols.get("security") or cols.get("company")
    sector_col = cols.get("gics sector")

    if not (sym_col and name_col):
        raise RuntimeError(f"Unexpected Wikipedia table columns: {list(df.columns)}")

    constituents: list[dict] = []
    for _, row in df.iterrows():
        ticker = str(row[sym_col]).strip()
        # yfinance uses dash, not dot, for class-share tickers (BRK-B, BF-B)
        yf_ticker = ticker.replace(".", "-")
        constituents.append({
            "ticker": yf_ticker,
            "company_name": str(row[name_col]).strip(),
            "sector": str(row[sector_col]).strip() if sector_col else None,
        })

    logger.info("Fetched %d constituents", len(constituents))
    return constituents
