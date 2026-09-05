import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import delete
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings
from app.db import async_session_factory
from app.models import SessionModel

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def cleanup_expired_sessions() -> int:
    """
    Deletes sessions that have been inactive longer than SESSION_TTL_SECONDS.
    Cascades automatically to collections, videos, chunks, and jobs.
    If SESSION_TTL_SECONDS <= 0, cleanup is disabled.
    """
    if settings.SESSION_TTL_SECONDS <= 0:
        logger.debug("Session TTL cleanup is disabled (SESSION_TTL_SECONDS <= 0).")
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.SESSION_TTL_SECONDS)
    logger.info(f"Running session cleanup for sessions inactive prior to {cutoff.isoformat()}")

    try:
        async with async_session_factory() as db:
            stmt = delete(SessionModel).where(SessionModel.last_active_at < cutoff)
            result = await db.execute(stmt)
            await db.commit()
            deleted_count = result.rowcount or 0
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired session(s).")
            return deleted_count
    except Exception as e:
        logger.error(f"Error during expired sessions cleanup: {e}", exc_info=True)
        return 0


def start_cleanup_scheduler():
    """Initializes and starts the periodic cleanup background scheduler."""
    if settings.SESSION_TTL_SECONDS > 0:
        # Run cleanup every 10 minutes
        scheduler.add_job(
            cleanup_expired_sessions,
            trigger="interval",
            minutes=10,
            id="session_cleanup_job",
            replace_existing=True
        )
        scheduler.start()
        logger.info("Session cleanup scheduler started (runs every 10 minutes).")
    else:
        logger.info("Session cleanup scheduler not started (SESSION_TTL_SECONDS=0).")


def stop_cleanup_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Session cleanup scheduler stopped.")
