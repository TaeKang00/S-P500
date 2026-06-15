"""Application configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'data' / 'sp500.db'}",
)

# Make sure data dir exists
(BASE_DIR / "data").mkdir(exist_ok=True)

# External data sources
WIKIPEDIA_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

# Scheduler — daily update at 21:30 UTC (US market close ~4:00 PM ET + 30 min buffer)
UPDATE_HOUR = int(os.getenv("UPDATE_HOUR", "21"))
UPDATE_MINUTE = int(os.getenv("UPDATE_MINUTE", "30"))

# CORS
_extra = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    *[o.strip() for o in _extra.split(",") if o.strip()],
]
