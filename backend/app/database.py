"""SQLAlchemy engine and session."""
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables — imported lazily to avoid circular deps."""
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    if DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
    _migrate_add_columns()


def _migrate_add_columns():
    """Add columns introduced after initial schema (SQLite ALTER TABLE)."""
    watchlist_cols = [
        ("forward_eps", "FLOAT"),
        ("trailing_eps", "FLOAT"),
        ("eps_y1", "FLOAT"),
        ("eps_y2", "FLOAT"),
        ("eps_y3", "FLOAT"),
        ("current_per", "FLOAT"),
        ("forward_pe", "FLOAT"),
        ("forward_pe_3y_avg", "FLOAT"),
        ("roe", "FLOAT"),
        ("fcf_yield", "FLOAT"),
        ("target_price_mean", "FLOAT"),
        ("target_price_high", "FLOAT"),
        ("target_price_low", "FLOAT"),
        ("recommendation", "TEXT"),
        ("analyst_count", "INTEGER"),
    ]
    stocks_cols = [
        ("drawdown_52w", "FLOAT"),
        ("ma200_deviation", "FLOAT"),
    ]
    with engine.connect() as conn:
        for col, col_type in watchlist_cols:
            try:
                conn.execute(text(f"ALTER TABLE watchlist ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception as exc:
                if "duplicate column" not in str(exc).lower():
                    logger.warning("Migration: unexpected error adding watchlist.%s: %s", col, exc)
        stocks_extra = [
            ("rsi_14", "FLOAT"),
            ("eps_growth", "FLOAT"),
            ("debt_to_equity", "FLOAT"),
            ("return_1y", "FLOAT"),
            ("return_3y_avg", "FLOAT"),
            ("trailing_eps", "FLOAT"),
            ("forward_eps", "FLOAT"),
            ("eps_y1", "FLOAT"),
            ("eps_y2", "FLOAT"),
            ("eps_y3", "FLOAT"),
            ("current_per", "FLOAT"),
            ("forward_pe_vs_avg", "FLOAT"),
        ]
        stocks_extra.append(("business_summary", "TEXT"))
        stocks_extra.append(("roe", "FLOAT"))
        stocks_extra.append(("fcf_yield", "FLOAT"))
        for col, col_type in stocks_cols + stocks_extra:
            try:
                conn.execute(text(f"ALTER TABLE stocks ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception as exc:
                if "duplicate column" not in str(exc).lower():
                    logger.warning("Migration: unexpected error adding stocks.%s: %s", col, exc)
