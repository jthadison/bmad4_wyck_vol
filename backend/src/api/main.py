"""FastAPI application entry point for BMAD Wyckoff system."""

# Fix for Windows: psycopg3 requires SelectorEventLoop on Windows
# This must be set before any asyncio code runs
# NOTE: For best results, start the backend using `python run.py` which sets
# the policy before uvicorn is imported
import asyncio
import sys
from contextlib import asynccontextmanager

if sys.platform == "win32":
    # Check if we need to set the policy (may already be set by run.py)
    current_policy = asyncio.get_event_loop_policy()
    if not isinstance(current_policy, asyncio.WindowsSelectorEventLoopPolicy):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print("[WINDOWS FIX] Set event loop policy to WindowsSelectorEventLoopPolicy", flush=True)
    else:
        print("[WINDOWS FIX] SelectorEventLoop policy already set", flush=True)

import structlog
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes import (
    audit,
    auth,
    backtest,
    campaigns,
    charts,
    config,
    feedback,
    help,
    notifications,
    orchestrator,
    paper_trading,
    patterns,
    portfolio,
    risk,
    scanner,
    signal_approval,
    signals,
    summary,
    tradingview,
    user,
    watchlist,
)
from src.api.routes import settings as settings_routes
from src.api.websocket import websocket_endpoint
from src.config import settings
from src.market_data.adapters.alpaca_adapter import AlpacaAdapter
from src.market_data.service import MarketDataCoordinator
from src.orchestrator.service import get_orchestrator
from src.pattern_engine.realtime_scanner import (
    ScannerHealthResponse,
    get_scanner,
    init_scanner,
)
from src.tasks.circuit_breaker_scheduler import (
    start_circuit_breaker_scheduler,
    stop_circuit_breaker_scheduler,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    await startup_event()
    yield
    await shutdown_event()


app = FastAPI(
    title="BMAD Wyckoff Volume Pattern Detection API",
    description="API for Wyckoff pattern detection and trade signal generation",
    version="0.1.0",
    lifespan=lifespan,
)

# Setup Prometheus instrumentation (Story 19.20)
# Exposes default FastAPI metrics + custom metrics at /metrics endpoint
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=False,  # Always enable metrics
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics"],
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
)

# Instrument the app and expose /metrics endpoint
instrumentator.instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=True, should_gzip=False
)

# Include routers
app.include_router(auth.router)  # Authentication routes (Story 11.7)
app.include_router(user.router)  # User settings routes (Story 11.7)
app.include_router(campaigns.router)
app.include_router(portfolio.router)
app.include_router(orchestrator.router)
app.include_router(signals.router)
app.include_router(risk.router)
app.include_router(feedback.router)
app.include_router(patterns.router)
app.include_router(audit.router)
app.include_router(config.router)  # Configuration routes (Story 11.1)
app.include_router(charts.router)  # Chart data routes (Story 11.5)
app.include_router(backtest.router)  # Backtest preview routes (Story 11.2)
app.include_router(notifications.router)  # Notification routes (Story 11.6)
app.include_router(summary.router)  # Summary routes (Story 10.3)
app.include_router(help.router)  # Help system routes (Story 11.8a)
app.include_router(paper_trading.router)  # Paper trading routes (Story 12.8)
app.include_router(tradingview.router)  # TradingView webhook routes (Story 16.4a)
app.include_router(scanner.router)  # Multi-symbol scanner routes (Story 19.4)
app.include_router(signal_approval.router)  # Signal approval queue routes (Story 19.9)
app.include_router(settings_routes.router)  # Settings routes (Story 19.14)
app.include_router(watchlist.router)  # Watchlist management routes (Story 19.12)


# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_route(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time event streaming."""
    await websocket_endpoint(websocket)


# Custom middleware to ensure CORS headers on all responses, even errors
class CORSExceptionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to catch all exceptions and ensure CORS headers are present.

    This catches errors that occur before route handlers (e.g., dependency injection errors)
    which the global exception handler cannot catch.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            import logging
            import traceback

            logger = logging.getLogger(__name__)
            logger.error(
                f"Exception in middleware for {request.method} {request.url.path}: {exc}",
                exc_info=True,
            )
            logger.error(f"Traceback:\n{traceback.format_exc()}")

            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "error": str(exc)},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "*",
                    "Access-Control-Allow-Headers": "*",
                },
            )


# Add CORS exception middleware first (innermost layer)
app.add_middleware(CORSExceptionMiddleware)

# Configure CORS - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler to ensure CORS headers are always present
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler that ensures CORS headers are present even on errors.

    This prevents CORS errors in the browser when backend endpoints fail.
    """
    import logging
    import traceback

    logger = logging.getLogger(__name__)
    logger.error(
        f"Unhandled exception in {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )

    # Log full traceback for debugging
    logger.error(f"Traceback:\n{traceback.format_exc()}")

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


# Global coordinator instance
_coordinator: MarketDataCoordinator | None = None


async def startup_event() -> None:
    """
    FastAPI startup event handler.

    Initializes and starts the real-time market data feed, pattern scanner,
    and paper trading integration.
    """
    global _coordinator

    # Only start real-time feed if API keys are configured
    if settings.alpaca_api_key and settings.alpaca_secret_key:
        try:
            # Read enabled symbols from scanner watchlist DB
            from src.database import async_session_maker as _session_maker
            from src.models.scanner_persistence import AssetClass
            from src.repositories.scanner_repository import ScannerRepository

            alpaca_symbols: list[str] = []
            try:
                async with _session_maker() as session:
                    repo = ScannerRepository(session)
                    enabled = await repo.get_enabled_symbols()
                    # Filter to only asset classes Alpaca supports (stock, crypto)
                    alpaca_compatible = {AssetClass.STOCK, AssetClass.CRYPTO}
                    alpaca_symbols = [
                        s.symbol for s in enabled if s.asset_class in alpaca_compatible
                    ]
            except Exception as db_err:
                logger.warning(
                    "watchlist_db_read_failed",
                    error=str(db_err),
                    message="Falling back to settings.watchlist_symbols",
                )

            # Use DB symbols if available, otherwise fall back to config
            if alpaca_symbols:
                settings.watchlist_symbols = alpaca_symbols
                logger.info(
                    "watchlist_symbols_loaded_from_db",
                    count=len(alpaca_symbols),
                    symbols=alpaca_symbols,
                )
            else:
                logger.info(
                    "watchlist_using_config_defaults",
                    symbols=settings.watchlist_symbols,
                )

            # Create Alpaca adapter
            adapter = AlpacaAdapter(settings=settings, use_paper=False)

            # Create coordinator
            _coordinator = MarketDataCoordinator(
                adapter=adapter,
                settings=settings,
            )

            # Store on app.state for shutdown access
            app.state.market_data_coordinator = _coordinator

            # Start real-time feed
            await _coordinator.start()

            # Initialize and start real-time pattern scanner (Story 19.1)
            scanner = init_scanner()
            await scanner.start(_coordinator)
            logger.info("realtime_scanner_started_successfully")
        except Exception as e:
            logger.warning(
                "realtime_feed_startup_failed",
                error=str(e),
                message="Application will continue without real-time market data",
            )
    else:
        logger.info(
            "alpaca_api_keys_not_configured",
            message="Real-time market data feed disabled - set ALPACA_API_KEY and ALPACA_SECRET_KEY to enable",
        )

    # Initialize paper trading signal routing (Story 12.8)
    try:
        from src.database import async_session_maker
        from src.orchestrator.event_bus import get_event_bus
        from src.trading.signal_event_listener import register_signal_listener
        from src.trading.signal_router import get_signal_router

        # Get orchestrator event bus
        event_bus = get_event_bus()

        # Create signal router with database session factory
        signal_router = get_signal_router(async_session_maker)

        # Register signal listener with event bus
        register_signal_listener(event_bus, signal_router)

        logger.info("paper_trading_signal_routing_initialized")
    except Exception as e:
        logger.warning("paper_trading_signal_routing_failed", error=str(e))

    # Initialize signal approval expiration task (Story 19.9)
    try:
        from src.database import async_session_maker
        from src.tasks.signal_approval_tasks import init_expiration_task

        expiration_task = init_expiration_task(async_session_maker)
        asyncio.create_task(expiration_task.start())

        logger.info("signal_approval_expiration_task_initialized")
    except Exception as e:
        logger.warning("signal_approval_expiration_task_failed", error=str(e))

    # Initialize circuit breaker scheduler (Story 19.21)
    try:
        from src.api.dependencies import init_redis_client

        redis_client = init_redis_client()
        start_circuit_breaker_scheduler(redis_client)
        logger.info("circuit_breaker_scheduler_initialized")
    except Exception as e:
        logger.warning("circuit_breaker_scheduler_failed", error=str(e))

    # Initialize signal scanner service and auto-restart if needed (Story 20.5b)
    await _initialize_signal_scanner_service()

    # Initialize symbol search service (Story 21.4)
    await _initialize_search_service()


async def _initialize_signal_scanner_service() -> None:
    """
    Initialize the signal scanner service (Story 20.5b).

    Sets up the scanner service singleton with WebSocket manager.
    Auto-restarts scanner if it was running before shutdown.

    Note: The scanner service uses a session factory pattern - it creates
    new sessions for each operation internally rather than holding a
    persistent session reference.
    """
    try:
        from src.api.routes.scanner import set_scanner_service
        from src.api.websocket import manager as websocket_manager
        from src.database import async_session_maker
        from src.orchestrator.service import get_orchestrator
        from src.repositories.scanner_repository import ScannerRepository
        from src.services.signal_scanner_service import SignalScannerService

        # Check if scanner should auto-start (use temporary session)
        should_auto_start = False
        async with async_session_maker() as session:
            repository = ScannerRepository(session)
            config = await repository.get_config()
            should_auto_start = config.is_running

        # Create scanner service with session factory (Story 20.5b)
        # The service will create repository instances as needed
        scanner_service = SignalScannerService(
            session_factory=async_session_maker,
            websocket_manager=websocket_manager,
        )

        # Wire up orchestrator for symbol analysis
        scanner_service.set_orchestrator(get_orchestrator())

        # Register scanner service for API routes
        set_scanner_service(scanner_service)

        # Story 20.5b AC4/AC5: Auto-restart if was running before shutdown
        if should_auto_start:
            logger.info("scanner_auto_starting_was_running_before_shutdown")
            # Use broadcast=False to avoid double broadcast, then send auto_started event
            await scanner_service.start(broadcast=False)
            # Broadcast auto_started event (distinct from manual "started" event)
            await scanner_service._broadcast_status_change(is_running=True, event="auto_started")
        else:
            logger.info("scanner_not_auto_starting_was_stopped")

        logger.info("signal_scanner_service_initialized")
    except Exception as e:
        logger.error("signal_scanner_service_initialization_failed", error=str(e))
        # Don't crash the app - scanner can be started manually


async def _initialize_search_service() -> None:
    """
    Initialize the symbol search service (Story 21.4).

    Sets up the search service singleton with validation service and optional Redis.
    """
    try:
        from src.api.dependencies import init_redis_client
        from src.api.routes.scanner import get_validation_service, set_search_service
        from src.services.symbol_search import SymbolSearchService

        # Get validation service (may be None if not configured)
        validation_service = get_validation_service()

        if validation_service is None:
            # Create a minimal validation service for search
            from src.services.symbol_validation_service import SymbolValidationService

            validation_service = SymbolValidationService()
            logger.info("search_service_using_minimal_validation_service")

        # Try to get Redis for caching (optional)
        redis_client = None
        try:
            redis_client = init_redis_client()
        except Exception:
            logger.warning("search_service_redis_not_available_caching_disabled")

        # Create and register search service
        search_service = SymbolSearchService(
            validation_service=validation_service,
            redis=redis_client,
        )
        set_search_service(search_service)

        logger.info("symbol_search_service_initialized", has_redis=redis_client is not None)
    except Exception as e:
        logger.error("symbol_search_service_initialization_failed", error=str(e))
        # Don't crash the app - search endpoint will return 503


async def shutdown_event() -> None:
    """
    FastAPI shutdown event handler.

    Gracefully stops the real-time pattern scanner, market data feed,
    signal approval expiration task, and circuit breaker scheduler.
    """
    global _coordinator

    # Stop circuit breaker scheduler (Story 19.21)
    try:
        stop_circuit_breaker_scheduler()
    except Exception:
        pass

    # Stop signal approval expiration task (Story 19.9)
    try:
        from src.tasks.signal_approval_tasks import get_expiration_task

        expiration_task = get_expiration_task()
        if expiration_task:
            await expiration_task.stop()
    except Exception:
        pass

    # Stop scanner first (Story 19.1)
    try:
        scanner = get_scanner()
        await scanner.stop()
    except RuntimeError:
        # Scanner was never initialized
        pass

    # Stop signal scanner service (Story 20.5b)
    try:
        from src.api.routes.scanner import get_scanner_service

        scanner_service = await get_scanner_service()
        await scanner_service.stop()
    except Exception:
        # Scanner service was never initialized or already stopped
        pass

    # Stop market data coordinator
    if _coordinator:
        try:
            await _coordinator.stop()
            logger.info("market_data_coordinator_stopped")
        except Exception as e:
            logger.error("market_data_coordinator_stop_failed", error=str(e))

    # Close Redis connection (Story 19.21)
    try:
        from src.api.dependencies import close_redis_client

        await close_redis_client()
    except Exception:
        pass


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "BMAD Wyckoff API", "version": "0.1.0"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint for Docker and monitoring."""
    return {"status": "healthy"}


@app.get("/health/scanner", response_model=ScannerHealthResponse)
async def scanner_health_check() -> ScannerHealthResponse:
    """
    Health check endpoint for real-time pattern scanner (Story 19.1).

    Returns:
        ScannerHealthResponse with scanner health information.
    """
    try:
        scanner = get_scanner()
    except RuntimeError:
        return ScannerHealthResponse(
            status="not_configured",
            message="Real-time scanner not initialized (Alpaca API keys not configured)",
        )

    health = scanner.get_health()
    return ScannerHealthResponse(
        status=health.status,
        queue_depth=health.queue_depth,
        last_processed=health.last_processed.isoformat() if health.last_processed else None,
        avg_latency_ms=round(health.avg_latency_ms, 2),
        bars_processed=health.bars_processed,
        bars_dropped=health.bars_dropped,
        circuit_state=health.circuit_state,
        is_running=health.is_running,
    )


@app.get("/api/v1/health")
async def detailed_health_check() -> dict[str, object]:
    """
    Detailed health check endpoint.

    Returns comprehensive health status including real-time feed status.

    Returns:
        Dictionary with health information:
        - status: "healthy" or "degraded"
        - database: database connection status
        - realtime_feed: real-time data feed status (if enabled)
        - orchestrator: orchestrator status
    """
    health_status: dict[str, object] = {
        "status": "healthy",
        "database": "unknown",
        "realtime_feed": None,
        "orchestrator": None,
        "scanner": None,  # Story 19.1
    }

    # Check database connection
    try:
        from sqlalchemy import text

        from src.database import async_session_maker

        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check real-time feed status
    if _coordinator:
        try:
            feed_health = await _coordinator.health_check()
            health_status["realtime_feed"] = feed_health

            if not feed_health.get("is_healthy"):
                health_status["status"] = "degraded"
        except Exception as e:
            health_status["realtime_feed"] = {"error": str(e)}
            health_status["status"] = "degraded"
    else:
        health_status["realtime_feed"] = {"status": "not_configured"}

    # Check orchestrator status
    try:
        orch = get_orchestrator()
        orchestrator_health = orch.get_health()
        health_status["orchestrator"] = orchestrator_health

        if orchestrator_health.get("status") != "healthy":
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["orchestrator"] = {"error": str(e)}
        health_status["status"] = "degraded"

    # Check scanner status (Story 19.1)
    try:
        scanner = get_scanner()
        scanner_health = scanner.get_health()
        health_status["scanner"] = {
            "status": scanner_health.status,
            "queue_depth": scanner_health.queue_depth,
            "avg_latency_ms": round(scanner_health.avg_latency_ms, 2),
            "bars_processed": scanner_health.bars_processed,
            "is_running": scanner_health.is_running,
        }

        if scanner_health.status != "healthy":
            health_status["status"] = "degraded"
    except RuntimeError:
        health_status["scanner"] = {"status": "not_configured"}
    except Exception as e:
        health_status["scanner"] = {"error": str(e)}
        health_status["status"] = "degraded"

    return health_status
