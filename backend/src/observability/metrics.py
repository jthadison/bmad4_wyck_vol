"""
Prometheus Metrics for Production Monitoring (Story 12.9 Task 11).

Defines Prometheus metrics for tracking system performance in production:
- Signal generation latency
- Backtest execution duration
- Database query performance
- Pattern detection rates

Author: Story 12.9 Task 11
"""

from prometheus_client import Counter, Gauge, Histogram

# Signal Generation Metrics (Task 11 Subtask 11.3)
signal_generation_requests_total = Counter(
    "signal_generation_requests_total",
    "Total number of signal generation requests",
    labelnames=["symbol", "pattern_type"],
)

signal_generation_latency_seconds = Histogram(
    "signal_generation_latency_seconds",
    "Signal generation latency in seconds (NFR1: <1s target)",
    labelnames=["symbol", "pattern_type"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0],  # Buckets optimized for NFR1 <1s target
)

# Backtest Execution Metrics
backtest_executions_total = Counter(
    "backtest_executions_total",
    "Total number of backtest executions",
    labelnames=["symbol", "status"],
)

backtest_duration_seconds = Histogram(
    "backtest_duration_seconds",
    "Backtest execution duration in seconds (NFR7 target)",
    labelnames=["symbol"],
    buckets=[1, 5, 10, 30, 60, 120],  # Optimized for typical backtest durations
)

# Active Signals Gauge
active_signals_count = Gauge(
    "active_signals_count",
    "Current number of active trading signals",
    labelnames=["pattern_type"],
)

# Database Query Performance
database_query_duration_seconds = Histogram(
    "database_query_duration_seconds",
    "Database query execution time in seconds",
    labelnames=["query_type"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0],  # Millisecond to second range
)

# Pattern Detection Metrics
pattern_detections_total = Counter(
    "pattern_detections_total",
    "Total number of pattern detections",
    labelnames=["pattern_type", "symbol"],
)

# API Request Metrics
api_requests_total = Counter(
    "api_requests_total",
    "Total number of API requests",
    labelnames=["method", "endpoint", "status_code"],
)

api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "API request duration in seconds",
    labelnames=["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
)
