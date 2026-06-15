"""APScheduler-based daily refresh."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import UPDATE_HOUR, UPDATE_MINUTE
from .services.updater import run_daily_update

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        run_daily_update,
        trigger=CronTrigger(hour=UPDATE_HOUR, minute=UPDATE_MINUTE),
        id="daily_update",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Scheduler started: daily update at %02d:%02d UTC", UPDATE_HOUR, UPDATE_MINUTE)
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def get_next_run() -> str | None:
    """Return ISO string of the next scheduled update (UTC), or None."""
    if _scheduler is None:
        return None
    job = _scheduler.get_job("daily_update")
    if job is None or job.next_run_time is None:
        return None
    return job.next_run_time.isoformat()
