"""FastAPI application entry point for BMAD Wyckoff system."""


from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    signals,
    summary,
    user,
)
from src.api.websocket import websocket_endpoint
from src.config import settings
from src.market_data.adapters.alpaca_adapter import AlpacaAdapter
from src.market_data.service import MarketDataCoordinator
from src.orchestrator.service import get_orchestrator

app = FastAPI(
    title="BMAD Wyckoff Volume Pattern Detection API",
    description="API for Wyckoff pattern detection and trade signal generation",
    version="0.1.0",
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


@app.on_event("startup")
async def startup_event() -> None:
    """
    FastAPI startup event handler.

    Initializes and starts the real-time market data feed and paper trading integration.
    """
    global _coordinator

    # Only start real-time feed if API keys are configured
    if settings.alpaca_api_key and settings.alpaca_secret_key:
        try:
            # Create Alpaca adapter
            adapter = AlpacaAdapter(settings=settings, use_paper=False)

            # Create coordinator
            _coordinator = MarketDataCoordinator(
                adapter=adapter,
                settings=settings,
            )

            # Start real-time feed
            await _coordinator.start()
        except Exception as e:
            print(f"WARNING: Failed to start real-time feed: {str(e)}")
            print("Application will continue without real-time market data.")
    else:
        print("WARNING: Alpaca API keys not configured. Real-time feed disabled.")

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

        print("Paper trading signal routing initialized successfully")
    except Exception as e:
        print(f"WARNING: Failed to initialize paper trading signal routing: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """
    FastAPI shutdown event handler.

    Gracefully stops the real-time market data feed.
    """
    global _coordinator

    if _coordinator:
        await _coordinator.stop()


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "BMAD Wyckoff API", "version": "0.1.0"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint for Docker and monitoring."""
    return {"status": "healthy"}


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
    }

    # Check database connection
    try:
        from src.database import async_session_maker

        async with async_session_maker() as session:
            await session.execute("SELECT 1")
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

    return health_status


@app.get("/api/v1/metrics")
async def metrics() -> str:
    """
    Prometheus metrics endpoint (Story 12.9 Task 11 Subtask 11.7).

    Exports performance metrics in Prometheus text format for monitoring:
    - Signal generation latency
    - Backtest execution duration
    - Database query performance
    - Pattern detection rates

    Returns:
        Prometheus-formatted metrics text (application/openmetrics-text)
    """
    from fastapi import Response
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    metrics_output = generate_latest()
    return Response(content=metrics_output, media_type=CONTENT_TYPE_LATEST)
