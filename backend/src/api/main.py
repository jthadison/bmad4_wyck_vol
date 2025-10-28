"""FastAPI application entry point for BMAD Wyckoff system."""

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.market_data.adapters.alpaca_adapter import AlpacaAdapter
from src.market_data.service import MarketDataCoordinator

app = FastAPI(
    title="BMAD Wyckoff Volume Pattern Detection API",
    description="API for Wyckoff pattern detection and trade signal generation",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global coordinator instance
_coordinator: Optional[MarketDataCoordinator] = None


@app.on_event("startup")
async def startup_event():
    """
    FastAPI startup event handler.

    Initializes and starts the real-time market data feed.
    """
    global _coordinator

    # Only start real-time feed if API keys are configured
    if settings.alpaca_api_key and settings.alpaca_secret_key:
        # Create Alpaca adapter
        adapter = AlpacaAdapter(settings=settings, use_paper=False)

        # Create coordinator
        _coordinator = MarketDataCoordinator(
            adapter=adapter,
            settings=settings,
        )

        # Start real-time feed
        await _coordinator.start()
    else:
        print("WARNING: Alpaca API keys not configured. Real-time feed disabled.")


@app.on_event("shutdown")
async def shutdown_event():
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
async def detailed_health_check() -> dict:
    """
    Detailed health check endpoint.

    Returns comprehensive health status including real-time feed status.

    Returns:
        Dictionary with health information:
        - status: "healthy" or "degraded"
        - database: database connection status
        - realtime_feed: real-time data feed status (if enabled)
    """
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "realtime_feed": None,
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

    return health_status
