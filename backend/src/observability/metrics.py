"""
Prometheus Metrics for Production Monitoring.

Defines Prometheus metrics for tracking system performance in production:
- Signal generation latency
- Backtest execution duration
- Database query performance
- Pattern detection rates
- Real-time scanner metrics (Story 19.20)

Author: Story 12.9 Task 11, Story 19.20
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

# ===== Story 19.20: Real-Time Scanner Performance Metrics =====

# Signal Lifecycle Counters
signals_generated_total = Counter(
    "signals_generated_total",
    "Total number of signals generated",
    labelnames=["pattern_type", "symbol"],
)

signals_approved_total = Counter(
    "signals_approved_total",
    "Total number of signals approved",
    labelnames=["pattern_type", "approval_type"],  # manual, auto
)

signals_rejected_total = Counter(
    "signals_rejected_total",
    "Total number of signals rejected",
    labelnames=["pattern_type", "rejection_stage"],
)

# Performance Histograms
pattern_detection_latency = Histogram(
    "pattern_detection_latency_seconds",
    "Time to detect patterns on incoming bar",
    labelnames=["symbol"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0],
)

signal_validation_latency = Histogram(
    "signal_validation_latency_seconds",
    "Time to validate a detected pattern",
    labelnames=["pattern_type"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.2],
)

websocket_notification_latency = Histogram(
    "websocket_notification_latency_seconds",
    "Time from approval to WebSocket delivery",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0],
)

# System State Gauges
active_symbols_count = Gauge(
    "active_symbols_count",
    "Number of symbols currently being monitored",
)

pending_signals_count = Gauge(
    "pending_signals_count",
    "Number of signals awaiting approval",
)

scanner_health = Gauge(
    "scanner_health",
    "Scanner health status (1=healthy, 0=unhealthy)",
)
