"""
Database connection and session management.

This module provides SQLAlchemy async engine configuration, connection pooling,
and session factory for the BMAD Wyckoff system.

Connection Pool Configuration (AC: 9):
- Pool size: 10 base connections
- Max overflow: 10 (total 20 connections max)
- Pre-ping: Enabled (validates connections before use)
- Recycle: 3600 seconds (prevents stale connections)
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from src.config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy declarative base for ORM models
Base = declarative_base()


def create_engine() -> AsyncEngine:
    """
    Create and configure async SQLAlchemy engine with connection pooling.

    Returns:
        AsyncEngine: Configured async database engine

    Connection Pool Settings (AC: 9):
    - pool_size=10: Base pool size (middle of 5-20 range)
    - max_overflow=10: Allow bursts up to 20 total connections
    - pool_pre_ping=True: Validate connections before checkout
    - pool_recycle=3600: Recycle connections after 1 hour
    """
    engine = create_async_engine(
        str(settings.database_url),
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=settings.db_pool_pre_ping,
        pool_recycle=settings.db_pool_recycle,
        # Note: AsyncEngine handles pooling internally with async drivers
    )

    # Log pool configuration on startup
    @event.listens_for(engine.sync_engine, "connect")
    def receive_connect(dbapi_conn: Any, connection_record: Any) -> None:
        """Log successful database connections."""
        logger.debug("Database connection established")

    @event.listens_for(engine.sync_engine, "checkout")
    def receive_checkout(dbapi_conn: Any, connection_record: Any, connection_proxy: Any) -> None:
        """Log connection pool checkouts (useful for monitoring)."""
        logger.debug("Connection checked out from pool")

    return engine


# Global engine instance
# Defer creation in test environments where database URL may not be configured
try:
    engine: AsyncEngine = create_engine()
except Exception as e:
    # In test environments, the engine will be created by test fixtures
    logger.warning(f"Failed to create database engine at module load time: {e}")
    engine = None  # type: ignore

# Async session factory (AC: 9 - connection pooling)
# In test environments, this will be None and tests will create their own session makers
async_session_maker = (
    async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Prevent lazy-loading issues after commit
        autocommit=False,
        autoflush=False,
    )
    if engine
    else None
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Provides async database session with automatic cleanup.
    Use with FastAPI's Depends() for automatic session management.

    Yields:
        AsyncSession: Database session

    Example:
        ```python
        @app.get("/bars")
        async def get_bars(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(OHLCVBar))
            return result.scalars().all()
        ```
    """
    if async_session_maker is None:
        raise RuntimeError(
            "Database not initialized. Please ensure DATABASE_URL is configured correctly."
        )

    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database schema.

    Creates all tables defined in SQLAlchemy models.
    For production, use Alembic migrations instead.

    This function is useful for:
    - Testing (create fresh test database)
    - Development (quick schema setup)
    """
    async with engine.begin() as conn:
        # Import all models to ensure they're registered with Base
        # This will be populated as we create models in future tasks
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialized")


async def drop_db() -> None:
    """
    Drop all database tables.

    WARNING: This destroys all data. Only use for testing or development.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.info("Database schema dropped")


def get_pool_status() -> dict[str, Any]:
    """
    Get current connection pool statistics.

    Useful for monitoring and debugging connection pool issues.

    Returns:
        dict: Pool status including size, checked_out connections, etc.
    """
    pool_status = {
        "pool_size": engine.pool.size(),  # type: ignore[attr-defined]
        "checked_out": engine.pool.checkedout(),  # type: ignore[attr-defined]
        "overflow": engine.pool.overflow(),  # type: ignore[attr-defined]
        "total_connections": engine.pool.size() + engine.pool.overflow(),  # type: ignore[attr-defined]
    }
    return pool_status
