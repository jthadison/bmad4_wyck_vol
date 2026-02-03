"""
Backend startup script with Windows event loop fix.

This script MUST be used to start the backend on Windows to ensure
psycopg3 compatibility with the async event loop.

Usage:
    poetry run python run.py

Or with reload:
    poetry run python run.py --reload
"""

import sys

# CRITICAL: Set event loop policy BEFORE importing anything else
# This must happen before uvicorn creates its event loop
if sys.platform == "win32":
    import asyncio

    # Use WindowsSelectorEventLoopPolicy for psycopg3 compatibility
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print("[STARTUP] Windows event loop policy set to WindowsSelectorEventLoopPolicy")

import uvicorn


def main() -> None:
    """Start the FastAPI application."""
    # Check for --reload flag
    reload_mode = "--reload" in sys.argv

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=reload_mode,
        # Force asyncio loop (not uvloop which isn't available on Windows anyway)
        loop="asyncio",
    )


if __name__ == "__main__":
    main()
