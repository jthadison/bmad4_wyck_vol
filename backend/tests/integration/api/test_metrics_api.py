"""
Integration tests for Prometheus metrics endpoint (Story 19.20).

Tests verify that:
- /metrics endpoint exposes Prometheus-formatted metrics
- Custom signal scanner metrics are present
- Metrics can be incremented and observed
- Histogram buckets are correctly configured
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.observability.metrics import (
    active_symbols_count,
    pattern_detection_latency,
    pending_signals_count,
    scanner_health,
    signal_validation_latency,
    signals_approved_total,
    signals_generated_total,
    signals_rejected_total,
    websocket_notification_latency,
)


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestMetricsEndpoint:
    """Test suite for /metrics endpoint."""

    def test_metrics_endpoint_exists(self, client: TestClient):
        """Test that /metrics endpoint returns 200 OK."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_content_type(self, client: TestClient):
        """Test that /metrics returns Prometheus text format."""
        response = client.get("/metrics")
        # Prometheus uses text/plain with version suffix
        assert "text/plain" in response.headers["content-type"]

    def test_metrics_contains_prometheus_format(self, client: TestClient):
        """Test that response contains Prometheus-formatted metrics."""
        response = client.get("/metrics")
        content = response.text

        # Check for Prometheus format markers (HELP and TYPE declarations)
        assert "# HELP" in content
        assert "# TYPE" in content

    def test_custom_signal_metrics_present(self, client: TestClient):
        """Test that custom signal scanner metrics are exposed."""
        response = client.get("/metrics")
        content = response.text

        # Verify Story 19.20 metrics are present
        assert "signals_generated_total" in content
        assert "signals_approved_total" in content
        assert "signals_rejected_total" in content
        assert "pattern_detection_latency_seconds" in content
        assert "signal_validation_latency_seconds" in content
        assert "websocket_notification_latency_seconds" in content
        assert "active_symbols_count" in content
        assert "pending_signals_count" in content
        assert "scanner_health" in content

    def test_default_instrumentator_metrics_present(self, client: TestClient):
        """Test that default FastAPI instrumentator metrics are present."""
        response = client.get("/metrics")
        content = response.text

        # Verify default metrics from prometheus-fastapi-instrumentator
        assert "http_requests_total" in content or "http_request" in content
        assert "http_request_duration" in content or "http_request_size" in content


class TestCounterMetrics:
    """Test suite for Counter metrics."""

    def test_signals_generated_counter_increment(self, client: TestClient):
        """Test that signals_generated_total counter can be incremented."""
        # Increment the counter
        signals_generated_total.labels(pattern_type="SPRING", symbol="AAPL").inc()

        # Fetch metrics
        response = client.get("/metrics")
        content = response.text

        # Verify counter was incremented
        assert 'signals_generated_total{pattern_type="SPRING",symbol="AAPL"}' in content

    def test_signals_approved_counter_increment(self, client: TestClient):
        """Test that signals_approved_total counter can be incremented."""
        signals_approved_total.labels(pattern_type="SOS", approval_type="auto").inc()

        response = client.get("/metrics")
        content = response.text

        assert 'signals_approved_total{approval_type="auto",pattern_type="SOS"}' in content

    def test_signals_rejected_counter_increment(self, client: TestClient):
        """Test that signals_rejected_total counter can be incremented."""
        signals_rejected_total.labels(pattern_type="UTAD", rejection_stage="volume").inc()

        response = client.get("/metrics")
        content = response.text

        assert "signals_rejected_total" in content


class TestHistogramMetrics:
    """Test suite for Histogram metrics."""

    def test_pattern_detection_latency_histogram(self, client: TestClient):
        """Test that pattern_detection_latency histogram records observations."""
        # Observe some latencies
        pattern_detection_latency.labels(symbol="TSLA").observe(0.045)
        pattern_detection_latency.labels(symbol="TSLA").observe(0.032)

        response = client.get("/metrics")
        content = response.text

        # Verify histogram structure
        assert "pattern_detection_latency_seconds_bucket" in content
        assert "pattern_detection_latency_seconds_sum" in content
        assert "pattern_detection_latency_seconds_count" in content

        # Verify buckets are present (from Story 19.20 spec)
        assert 'le="0.01"' in content
        assert 'le="0.025"' in content
        assert 'le="0.05"' in content
        assert 'le="0.1"' in content

    def test_signal_validation_latency_histogram(self, client: TestClient):
        """Test that signal_validation_latency histogram records observations."""
        signal_validation_latency.labels(pattern_type="SPRING").observe(0.025)

        response = client.get("/metrics")
        content = response.text

        assert "signal_validation_latency_seconds_bucket" in content
        assert "signal_validation_latency_seconds_sum" in content
        assert "signal_validation_latency_seconds_count" in content

    def test_websocket_notification_latency_histogram(self, client: TestClient):
        """Test that websocket_notification_latency histogram records observations."""
        websocket_notification_latency.observe(0.150)

        response = client.get("/metrics")
        content = response.text

        assert "websocket_notification_latency_seconds_bucket" in content
        assert "websocket_notification_latency_seconds_sum" in content

        # Verify buckets from Story 19.20 spec
        assert 'le="0.1"' in content
        assert 'le="0.25"' in content
        assert 'le="0.5"' in content


class TestGaugeMetrics:
    """Test suite for Gauge metrics."""

    def test_active_symbols_gauge_set(self, client: TestClient):
        """Test that active_symbols_count gauge can be set."""
        active_symbols_count.set(15)

        response = client.get("/metrics")
        content = response.text

        assert "active_symbols_count 15" in content

    def test_pending_signals_gauge_set(self, client: TestClient):
        """Test that pending_signals_count gauge can be set."""
        pending_signals_count.set(7)

        response = client.get("/metrics")
        content = response.text

        assert "pending_signals_count 7" in content

    def test_scanner_health_gauge_healthy(self, client: TestClient):
        """Test that scanner_health gauge can indicate healthy status."""
        scanner_health.set(1)

        response = client.get("/metrics")
        content = response.text

        assert "scanner_health 1" in content

    def test_scanner_health_gauge_unhealthy(self, client: TestClient):
        """Test that scanner_health gauge can indicate unhealthy status."""
        scanner_health.set(0)

        response = client.get("/metrics")
        content = response.text

        assert "scanner_health 0" in content

    def test_gauge_can_increment_decrement(self, client: TestClient):
        """Test that gauges can be incremented and decremented."""
        # Set initial value
        active_symbols_count.set(10)

        # Increment
        active_symbols_count.inc(5)

        response = client.get("/metrics")
        content = response.text

        # Should now be 15
        assert "active_symbols_count 15" in content

        # Decrement
        active_symbols_count.dec(3)

        response = client.get("/metrics")
        content = response.text

        # Should now be 12
        assert "active_symbols_count 12" in content


class TestMetricsLabels:
    """Test suite for metric labels."""

    def test_metrics_have_correct_labels(self, client: TestClient):
        """Test that metrics expose the correct label names."""
        # Add some labeled metrics
        signals_generated_total.labels(pattern_type="SPRING", symbol="AAPL").inc()
        signals_approved_total.labels(pattern_type="SOS", approval_type="manual").inc()
        signals_rejected_total.labels(pattern_type="UTAD", rejection_stage="phase").inc()

        response = client.get("/metrics")
        content = response.text

        # Verify label structure
        assert "pattern_type=" in content
        assert "symbol=" in content
        assert "approval_type=" in content
        assert "rejection_stage=" in content


class TestMetricsEndpointPerformance:
    """Test suite for metrics endpoint performance."""

    def test_metrics_endpoint_responds_quickly(self, client: TestClient):
        """Test that /metrics endpoint responds in reasonable time."""
        import time

        start = time.time()
        response = client.get("/metrics")
        duration = time.time() - start

        assert response.status_code == 200
        # Metrics endpoint should respond in < 100ms
        assert duration < 0.1, f"Metrics endpoint took {duration}s (expected < 0.1s)"
