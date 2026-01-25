"""
Signal Approval Background Tasks (Story 19.9)

Background task for expiring stale signals in the approval queue.

Author: Story 19.9
"""

import asyncio

import structlog

from src.models.signal_approval import SignalApprovalConfig
from src.repositories.signal_approval_repository import SignalApprovalRepository
from src.services.signal_approval_service import SignalApprovalService

logger = structlog.get_logger(__name__)


class SignalApprovalExpirationTask:
    """
    Background task for expiring stale signals in the approval queue.

    Runs periodically to check for and expire signals that have exceeded
    their timeout without being approved or rejected.
    """

    def __init__(self, db_session_factory, config: SignalApprovalConfig | None = None):
        """
        Initialize signal approval expiration task.

        Args:
            db_session_factory: Factory function to create database sessions
            config: Optional configuration (uses defaults if not provided)
        """
        self.db_session_factory = db_session_factory
        self.config = config or SignalApprovalConfig()
        self.is_running = False
        self.check_interval = self.config.expiration_check_interval_seconds

        logger.info(
            "signal_approval_expiration_task_initialized",
            check_interval=self.check_interval,
        )

    async def start(self) -> None:
        """
        Start the background task.

        Runs continuously until stopped, checking for expired signals
        at the configured interval.
        """
        if self.is_running:
            logger.warning("signal_approval_expiration_task_already_running")
            return

        self.is_running = True
        logger.info("signal_approval_expiration_task_started")

        try:
            while self.is_running:
                try:
                    await self._expire_stale_signals()
                except Exception as e:
                    logger.error(
                        "signal_approval_expiration_task_failed",
                        error=str(e),
                        error_type=type(e).__name__,
                    )

                # Wait for next check interval
                await asyncio.sleep(self.check_interval)

        except asyncio.CancelledError:
            logger.info("signal_approval_expiration_task_cancelled")
            self.is_running = False
            raise

    async def stop(self) -> None:
        """
        Stop the background task gracefully.
        """
        if not self.is_running:
            logger.warning("signal_approval_expiration_task_not_running")
            return

        self.is_running = False
        logger.info("signal_approval_expiration_task_stopped")

    async def _expire_stale_signals(self) -> None:
        """
        Check for and expire stale signals.

        Creates a new database session for each check to avoid
        long-lived connections.
        """
        async with self.db_session_factory() as session:
            repository = SignalApprovalRepository(session)
            service = SignalApprovalService(repository=repository, config=self.config)

            expired_count = await service.expire_stale_signals()

            if expired_count > 0:
                logger.info(
                    "signal_approval_expiration_check_complete",
                    expired_count=expired_count,
                )


# Global task instance for singleton pattern
_expiration_task: SignalApprovalExpirationTask | None = None


def get_expiration_task() -> SignalApprovalExpirationTask | None:
    """
    Get the global expiration task instance.

    Returns:
        SignalApprovalExpirationTask if initialized, None otherwise
    """
    return _expiration_task


def init_expiration_task(db_session_factory) -> SignalApprovalExpirationTask:
    """
    Initialize the global expiration task.

    Args:
        db_session_factory: Factory function to create database sessions

    Returns:
        Initialized SignalApprovalExpirationTask
    """
    global _expiration_task
    _expiration_task = SignalApprovalExpirationTask(db_session_factory)
    return _expiration_task
