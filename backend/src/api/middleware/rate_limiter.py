"""
Rate Limiting Middleware - Story 23.11

In-memory sliding-window rate limiter for order submission endpoints.
Returns HTTP 429 Too Many Requests when the limit is exceeded.

Configuration:
  - max_requests: Maximum requests per window (default: 10)
  - window_seconds: Sliding window duration in seconds (default: 60)

Author: Story 23.11
"""

from __future__ import annotations

import time
from collections import defaultdict

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    In-memory sliding-window rate limiter middleware.

    Limits requests per client IP on configured path prefixes.
    Uses a simple in-memory dict with timestamp lists.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int = 10,
        window_seconds: int = 60,
        rate_limited_prefixes: list[str] | None = None,
        rate_limited_methods: set[str] | None = None,
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            app: ASGI application.
            max_requests: Max requests per window per client.
            window_seconds: Sliding window in seconds.
            rate_limited_prefixes: URL path prefixes to rate limit.
                Defaults to order-related prefixes.
            rate_limited_methods: HTTP methods to rate limit. Defaults to POST only.
        """
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.rate_limited_prefixes = rate_limited_prefixes or [
            "/api/v1/tradingview/webhook",
            "/api/v1/paper-trading/enable",
            "/api/v1/paper-trading/disable",
            "/api/v1/paper-trading/reset",
        ]
        self.rate_limited_methods = rate_limited_methods or {"POST"}
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _should_rate_limit(self, request: Request) -> bool:
        """Check if this request should be rate-limited based on path and method."""
        if request.method not in self.rate_limited_methods:
            return False
        path = request.url.path
        return any(path.startswith(prefix) for prefix in self.rate_limited_prefixes)

    def _get_client_key(self, request: Request) -> str:
        """
        Get a rate-limiting key for the client (IP-based).

        NOTE: Behind a reverse proxy, request.client.host is the proxy IP,
        not the real client. For production deployments, configure
        ProxyHeadersMiddleware (uvicorn --proxy-headers) so that
        request.client.host reflects the real client via X-Forwarded-For.
        """
        client_ip = request.client.host if request.client else "unknown"
        return client_ip

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self._should_rate_limit(request):
            return await call_next(request)

        client_key = self._get_client_key(request)
        now = time.monotonic()
        cutoff = now - self.window_seconds

        # Clean old timestamps and check count
        timestamps = [t for t in self._requests[client_key] if t > cutoff]

        if len(timestamps) >= self.max_requests:
            self._requests[client_key] = timestamps
            logger.warning(
                "rate_limit_exceeded",
                client=client_key,
                path=request.url.path,
                count=len(timestamps),
                limit=self.max_requests,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded: max {self.max_requests} requests "
                    f"per {self.window_seconds}s"
                },
                headers={"Retry-After": str(self.window_seconds)},
            )

        timestamps.append(now)
        self._requests[client_key] = timestamps

        # Prune empty client entries to prevent memory leak
        stale_keys = [k for k, v in self._requests.items() if not v]
        for k in stale_keys:
            del self._requests[k]

        return await call_next(request)
