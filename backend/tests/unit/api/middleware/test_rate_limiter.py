"""
Rate Limiter Middleware Unit Tests - Story 23.11

Tests the RateLimiterMiddleware:
- Requests within limit are allowed
- Excessive requests return 429
- Rate limit resets after window
- Non-rate-limited paths are unaffected
- Only POST methods are rate limited

Coverage target: >= 95%
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.rate_limiter import RateLimiterMiddleware


def _create_test_app(max_requests: int = 3, window_seconds: int = 60) -> FastAPI:
    """Create a minimal FastAPI app with rate limiting middleware."""
    app = FastAPI()

    @app.post("/api/v1/tradingview/webhook")
    async def webhook() -> dict:
        return {"status": "ok"}

    @app.post("/api/v1/paper-trading/enable")
    async def enable() -> dict:
        return {"status": "ok"}

    @app.get("/api/v1/tradingview/health")
    async def health() -> dict:
        return {"status": "healthy"}

    @app.post("/api/v1/other/endpoint")
    async def other() -> dict:
        return {"status": "ok"}

    app.add_middleware(
        RateLimiterMiddleware,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )

    return app


class TestRateLimiterAllowedRequests:
    """Test requests within the rate limit."""

    def test_requests_within_limit_allowed(self) -> None:
        """Requests within the limit should get 200 responses."""
        app = _create_test_app(max_requests=5)
        client = TestClient(app)

        for _ in range(5):
            resp = client.post("/api/v1/tradingview/webhook")
            assert resp.status_code == 200

    def test_first_request_always_allowed(self) -> None:
        """The first request should always be allowed."""
        app = _create_test_app(max_requests=1)
        client = TestClient(app)

        resp = client.post("/api/v1/tradingview/webhook")
        assert resp.status_code == 200


class TestRateLimiterBlocking:
    """Test that excessive requests are blocked."""

    def test_excessive_requests_return_429(self) -> None:
        """Requests exceeding the limit should return 429."""
        app = _create_test_app(max_requests=3)
        client = TestClient(app)

        # First 3 should pass
        for _ in range(3):
            resp = client.post("/api/v1/tradingview/webhook")
            assert resp.status_code == 200

        # 4th should be blocked
        resp = client.post("/api/v1/tradingview/webhook")
        assert resp.status_code == 429

    def test_429_response_has_retry_after_header(self) -> None:
        """429 response should include Retry-After header."""
        app = _create_test_app(max_requests=1, window_seconds=60)
        client = TestClient(app)

        client.post("/api/v1/tradingview/webhook")
        resp = client.post("/api/v1/tradingview/webhook")

        assert resp.status_code == 429
        assert resp.headers.get("retry-after") == "60"

    def test_429_response_body_has_detail(self) -> None:
        """429 response body should explain the rate limit."""
        app = _create_test_app(max_requests=1)
        client = TestClient(app)

        client.post("/api/v1/tradingview/webhook")
        resp = client.post("/api/v1/tradingview/webhook")

        assert resp.status_code == 429
        body = resp.json()
        assert "detail" in body
        assert "Rate limit exceeded" in body["detail"]

    def test_rate_limit_applies_to_paper_trading_endpoints(self) -> None:
        """Rate limit should also apply to paper trading POST endpoints."""
        app = _create_test_app(max_requests=2)
        client = TestClient(app)

        client.post("/api/v1/paper-trading/enable")
        client.post("/api/v1/paper-trading/enable")
        resp = client.post("/api/v1/paper-trading/enable")

        assert resp.status_code == 429


class TestRateLimiterBypass:
    """Test that non-rate-limited requests bypass the limiter."""

    def test_get_requests_not_rate_limited(self) -> None:
        """GET requests should not be rate limited."""
        app = _create_test_app(max_requests=1)
        client = TestClient(app)

        # Use up the POST limit
        client.post("/api/v1/tradingview/webhook")
        client.post("/api/v1/tradingview/webhook")  # Would be 429 for POST

        # GET should still work
        resp = client.get("/api/v1/tradingview/health")
        assert resp.status_code == 200

    def test_non_configured_paths_not_rate_limited(self) -> None:
        """Paths not in rate_limited_prefixes should not be rate limited."""
        app = _create_test_app(max_requests=1)
        client = TestClient(app)

        # Exhaust the rate limit on the configured path
        client.post("/api/v1/tradingview/webhook")

        # Non-configured path should still work (uses same IP but different path check)
        # Note: rate limiter is IP-based, so once one path is limited, others from same IP are too
        # But /api/v1/other/endpoint is NOT in the rate_limited_prefixes, so it should pass
        resp = client.post("/api/v1/other/endpoint")
        assert resp.status_code == 200


class TestRateLimiterReset:
    """Test that rate limits reset after the window."""

    def test_rate_limit_resets_after_window(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Rate limit should reset after the window expires."""
        import src.api.middleware.rate_limiter as rl_module

        current_time = 1000.0

        def mock_monotonic() -> float:
            return current_time

        monkeypatch.setattr(rl_module.time, "monotonic", mock_monotonic)

        app = _create_test_app(max_requests=1, window_seconds=60)
        client = TestClient(app)

        # First request passes
        resp = client.post("/api/v1/tradingview/webhook")
        assert resp.status_code == 200

        # Second immediately blocked
        resp = client.post("/api/v1/tradingview/webhook")
        assert resp.status_code == 429

        # Advance time past the window
        current_time = 1061.0

        # Should be allowed again
        resp = client.post("/api/v1/tradingview/webhook")
        assert resp.status_code == 200
