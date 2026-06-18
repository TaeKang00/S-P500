"""
Run the API:        python run.py
Run the seed only:  python run.py --seed
"""
import argparse
import logging
import os
import sys

import uvicorn

from app.database import SessionLocal, init_db
from app.models import Stock
from app.services.updater import run_daily_update

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)
log = logging.getLogger("run")


def seed_if_empty():
    init_db()
    db = SessionLocal()
    try:
        count = db.query(Stock).count()
    finally:
        db.close()
    if count == 0:
        log.info("DB empty — running initial seed (this can take several minutes)…")
        run_daily_update()
    else:
        log.info("DB already has %d stocks — skipping initial seed", count)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="Run the full seed and exit")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8000)))
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    if args.seed:
        init_db()
        run_daily_update()
        return

    seed_if_empty()
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
