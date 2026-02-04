"""
Backend startup script with Windows event loop fix.

This script MUST be used to start the backend on Windows to ensure
psycopg3 compatibility with the async event loop.

Usage:
    poetry run python run.py
    poetry run python run.py --reload
    poetry run python run.py --port 8080

The script sets WindowsSelectorEventLoopPolicy BEFORE any async imports,
which is required for psycopg3 to work correctly on Windows.
"""

import os
import sys

# CRITICAL: Set event loop policy BEFORE importing anything else
# This must happen before uvicorn creates its event loop
if sys.platform == "win32":
    import asyncio

    # Use WindowsSelectorEventLoopPolicy for psycopg3 compatibility
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Also set environment variable so reloaded subprocesses inherit the fix
    os.environ["BMAD_WINDOWS_LOOP_FIX"] = "1"

    print("[STARTUP] Windows: Set SelectorEventLoop policy for psycopg3 compatibility")

import uvicorn


def main() -> None:
    """Start the FastAPI application."""
    import argparse

    parser = argparse.ArgumentParser(description="Run BMAD Wyckoff backend")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    print(f"[STARTUP] Starting server on {args.host}:{args.port} (reload={args.reload})")

    uvicorn.run(
        "src.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        # Force asyncio loop (respects our WindowsSelectorEventLoopPolicy)
        loop="asyncio",
    )


if __name__ == "__main__":
    main()
