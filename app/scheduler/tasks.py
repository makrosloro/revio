import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    assert _scheduler is not None, "Scheduler not initialized"
    return _scheduler


def create_scheduler() -> AsyncIOScheduler:
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="Europe/Madrid")
    return _scheduler


def setup_jobs(scheduler: AsyncIOScheduler) -> None:
    from app.services.review_service import poll_all_businesses, send_daily_digest

    scheduler.add_job(
        poll_all_businesses,
        trigger=IntervalTrigger(minutes=settings.POLLING_INTERVAL_MINUTES),
        id="poll_reviews",
        replace_existing=True,
        next_run_time=datetime.now(),
    )
    logger.info("Job poll_reviews registrado (cada %d min)", settings.POLLING_INTERVAL_MINUTES)

    scheduler.add_job(
        send_daily_digest,
        trigger=CronTrigger(
            hour=settings.DAILY_DIGEST_HOUR, minute=0, timezone="Europe/Madrid"
        ),
        id="daily_digest",
        replace_existing=True,
    )
    logger.info("Job daily_digest registrado (diario a las %d:00)", settings.DAILY_DIGEST_HOUR)
