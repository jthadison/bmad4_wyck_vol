"""
Benchmark Configuration (Story 12.9 Task 1 Subtask 1.3).

Defines configuration parameters for performance benchmarking suite including:
- Warmup rounds to account for caching effects
- Benchmark rounds for statistical significance
- Timeout limits per benchmark
- Target threshold values for NFR1 and NFR7 compliance

Author: Story 12.9 Task 1
"""

from decimal import Decimal
from typing import Final

# Benchmark Execution Configuration
WARMUP_ROUNDS: Final[int] = 3  # Discard first 3 runs for cache warmup
BENCHMARK_ROUNDS: Final[int] = 10  # Run each benchmark 10 times
TIMEOUT_SECONDS: Final[int] = 60  # Maximum 60 seconds per benchmark

# NFR Performance Targets (from PRD)
# NFR1: Signal generation latency <1 second per symbol per bar
NFR1_TARGET_SECONDS: Final[Decimal] = Decimal("1.0")

# NFR7: Backtest speed >100 bars/second
NFR7_TARGET_BARS_PER_SECOND: Final[int] = 100

# Component-Level Performance Budgets (breakdown of NFR1)
VOLUME_ANALYSIS_TARGET_MS: Final[int] = 50  # <50ms per bar
SPRING_DETECTION_TARGET_MS: Final[int] = 200  # <200ms per bar
SOS_DETECTION_TARGET_MS: Final[int] = 150  # <150ms per bar
UTAD_DETECTION_TARGET_MS: Final[int] = 150  # <150ms per bar

# Database Query Performance Targets
OHLCV_QUERY_TARGET_MS: Final[int] = 50  # <50ms for OHLCV range query
PATTERN_QUERY_TARGET_MS: Final[int] = 30  # <30ms for pattern lookup
SIGNAL_QUERY_TARGET_MS: Final[int] = 40  # <40ms for signal history
AUDIT_LOG_QUERY_TARGET_MS: Final[int] = 100  # <100ms for audit logs

# Regression Detection Threshold
REGRESSION_THRESHOLD_PERCENT: Final[Decimal] = Decimal("10.0")  # Fail if >10% slower

# Load Testing Configuration
CONCURRENT_SYMBOLS: Final[int] = 100  # Simulate 100 concurrent symbols
LOAD_TEST_DURATION_MINUTES: Final[int] = 5  # Run load test for 5 minutes
LOAD_TEST_SPAWN_RATE: Final[int] = 10  # Spawn 10 users per second

# Benchmark Data Sizes
SYNTHETIC_BARS_SMALL: Final[int] = 100  # Small dataset for microbenchmarks
SYNTHETIC_BARS_MEDIUM: Final[int] = 1000  # Medium dataset for component benchmarks
SYNTHETIC_BARS_LARGE: Final[int] = 10000  # Large dataset for integration benchmarks

# Database Test Data Volumes (Task 4 Subtask 4.2)
TEST_DB_SYMBOLS: Final[int] = 10  # Number of symbols in test database
TEST_DB_BARS_PER_SYMBOL: Final[int] = 10000  # Bars per symbol
TEST_DB_TOTAL_BARS: Final[int] = TEST_DB_SYMBOLS * TEST_DB_BARS_PER_SYMBOL  # 100,000 bars
TEST_DB_PATTERNS: Final[int] = 1000  # Pattern detections
TEST_DB_SIGNALS: Final[int] = 500  # Signals generated
TEST_DB_AUDIT_LOGS: Final[int] = 200  # Audit log entries
