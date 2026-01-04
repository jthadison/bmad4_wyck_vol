"""
Windows-compatible startup script for the BMAD Wyckoff backend.

This script sets the correct event loop policy for Windows before starting uvicorn,
which is required for psycopg3 async support on Windows.
"""

import asyncio
import sys

if sys.platform == "win32":
    # Set Windows selector event loop policy for psycopg3 compatibility
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print("[Windows] Set SelectorEventLoop policy for psycopg3 compatibility")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload to avoid event loop policy issues
        log_level="info",
    )
