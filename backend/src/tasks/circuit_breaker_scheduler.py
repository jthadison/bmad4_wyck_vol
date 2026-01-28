"""
Circuit Breaker Scheduler (Story 19.21)

Implements midnight ET reset for circuit breakers using APScheduler.

Author: Story 19.21
"""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from redis.asyncio import Redis

from src.services.circuit_breaker_service import CircuitBreakerService

logger = structlog.get_logger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


async def reset_all_circuit_breakers(redis: Redis) -> int:
    """
    Reset all open circuit breakers at midnight ET.

    Called by the scheduler at midnight Eastern Time.

    Args:
        redis: Redis client

    Returns:
        Number of circuit breakers reset
    """
    cb_service = CircuitBreakerService(redis)

    try:
        # Get all users with open circuit breakers
        open_breakers = await cb_service.get_all_open_breakers()

        if not open_breakers:
            logger.info("midnight_reset_no_open_breakers")
            return 0

        # Reset each breaker
        reset_count = 0
        for user_id in open_breakers:
            try:
                await cb_service.reset_breaker(user_id, manual=False)
                reset_count += 1
                logger.info(
                    "midnight_reset_breaker_reset",
                    user_id=str(user_id),
                )
            except Exception as e:
                logger.error(
                    "midnight_reset_breaker_failed",
                    user_id=str(user_id),
                    error=str(e),
                )

        logger.info(
            "midnight_reset_complete",
            total_open=len(open_breakers),
            reset_count=reset_count,
        )

        return reset_count

    except Exception as e:
        logger.error("midnight_reset_failed", error=str(e))
        return 0


def create_circuit_breaker_scheduler(redis: Redis) -> AsyncIOScheduler:
    """
    Create and configure the circuit breaker scheduler.

    Schedules the reset_all_circuit_breakers function to run
    at midnight Eastern Time daily.

    Args:
        redis: Redis client for circuit breaker operations

    Returns:
        Configured AsyncIOScheduler instance
    """
    global _scheduler

    if _scheduler is not None:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="America/New_York")

    # Schedule midnight reset job
    _scheduler.add_job(
        reset_all_circuit_breakers,
        trigger=CronTrigger(hour=0, minute=0, timezone="America/New_York"),
        args=[redis],
        id="circuit_breaker_midnight_reset",
        name="Reset all circuit breakers at midnight ET",
        replace_existing=True,
    )

    logger.info("circuit_breaker_scheduler_configured")

    return _scheduler


def start_circuit_breaker_scheduler(redis: Redis) -> None:
    """
    Start the circuit breaker scheduler.

    Should be called during application startup.

    Args:
        redis: Redis client
    """
    scheduler = create_circuit_breaker_scheduler(redis)

    if not scheduler.running:
        scheduler.start()
        logger.info("circuit_breaker_scheduler_started")
    else:
        logger.info("circuit_breaker_scheduler_already_running")


def stop_circuit_breaker_scheduler() -> None:
    """
    Stop the circuit breaker scheduler.

    Should be called during application shutdown.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("circuit_breaker_scheduler_stopped")
        _scheduler = None


def get_scheduler() -> AsyncIOScheduler | None:
    """
    Get the current scheduler instance.

    Returns:
        AsyncIOScheduler or None if not initialized
    """
    return _scheduler
