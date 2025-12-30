"""
Locust Load Testing Configuration for Story 12.9 - Task 9

This file defines load testing scenarios for the Wyckoff trading system API.
It simulates concurrent symbol analysis requests to validate system performance
under realistic load.

Usage:
    # Run with Locust web UI (localhost:8089)
    cd backend
    poetry run locust -f benchmarks/locustfile.py --host http://localhost:8000

    # Run headless with 100 users, 10 users/sec spawn rate, 5 min duration
    poetry run locust -f benchmarks/locustfile.py \
        --host http://localhost:8000 \
        --users 100 \
        --spawn-rate 10 \
        --run-time 5m \
        --headless

    # Generate HTML report
    poetry run locust -f benchmarks/locustfile.py \
        --host http://localhost:8000 \
        --users 50 \
        --spawn-rate 5 \
        --run-time 2m \
        --headless \
        --html reports/load_test_report.html

Load Test Scenarios:
--------------------
1. Pattern Detection (70% of requests)
   - Detect Wyckoff patterns for a symbol
   - Realistic symbol distribution (AAPL, MSFT, GOOGL, etc.)

2. Signal Generation (20% of requests)
   - Generate trading signals from patterns
   - Validates full pipeline performance

3. Backtest Execution (10% of requests)
   - Run backtests for strategies
   - Heavy workload scenario

Performance Targets:
-------------------
- NFR1: Signal generation <1s per symbol
- Concurrent users: 100+ without degradation
- Error rate: <1%
- Response time p95: <2s
"""

from random import choice, randint

from locust import HttpUser, between, task


class WyckoffTradingUser(HttpUser):
    """
    Simulates a user of the Wyckoff trading system API.

    This user performs typical operations:
    - Pattern detection (most common)
    - Signal generation
    - Backtest execution
    """

    # Wait 1-3 seconds between requests (realistic user behavior)
    wait_time = between(1, 3)

    # Sample symbols for realistic load distribution
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "AMD", "NFLX", "SPY"]

    # Sample timeframes
    timeframes = ["1d", "1h", "4h"]

    def on_start(self):
        """
        Initialize user session.

        In a real system, this would authenticate and get a session token.
        For benchmarking, we'll use the API without auth.
        """
        # No authentication needed for benchmarking
        pass

    @task(70)
    def detect_patterns(self):
        """
        Detect Wyckoff patterns for a random symbol.

        This is the most common operation (70% of requests).
        Validates NFR1 signal generation performance.
        """
        symbol = choice(self.symbols)
        timeframe = choice(self.timeframes)

        # Note: Adjust endpoint URL based on your actual API structure
        with self.client.get(
            "/api/v1/patterns/detect",
            params={"symbol": symbol, "timeframe": timeframe},
            catch_response=True,
            name="/api/v1/patterns/detect",
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                # 404 is acceptable (no patterns found)
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(20)
    def generate_signals(self):
        """
        Generate trading signals for a random symbol.

        This validates full pipeline performance (20% of requests).
        """
        symbol = choice(self.symbols)
        timeframe = choice(self.timeframes)

        with self.client.post(
            "/api/v1/signals/generate",
            json={"symbol": symbol, "timeframe": timeframe},
            catch_response=True,
            name="/api/v1/signals/generate",
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
            elif response.status_code == 404:
                response.success()  # No patterns to generate signals from
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(10)
    def run_backtest(self):
        """
        Execute a backtest for a random symbol.

        Heavy workload scenario (10% of requests).
        Validates NFR7 backtest speed performance.
        """
        symbol = choice(self.symbols)
        start_date = "2023-01-01"
        end_date = "2024-01-01"

        with self.client.post(
            "/api/v1/backtests/run",
            json={
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "strategy": "wyckoff_spring",
            },
            catch_response=True,
            name="/api/v1/backtests/run",
        ) as response:
            if response.status_code in [200, 201, 202]:
                # 202 = Accepted (async backtest)
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(5)
    def get_active_signals(self):
        """
        Retrieve active signals for a user.

        Read-only query to validate database performance.
        """
        with self.client.get(
            "/api/v1/signals/active",
            params={"status": "ACTIVE", "limit": 50},
            catch_response=True,
            name="/api/v1/signals/active",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(3)
    def get_backtest_results(self):
        """
        Retrieve backtest results with pagination.

        Tests database query performance under load.
        """
        page = randint(1, 5)
        limit = 20

        with self.client.get(
            "/api/v1/backtests/results",
            params={"page": page, "limit": limit},
            catch_response=True,
            name="/api/v1/backtests/results",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(2)
    def get_metrics(self):
        """
        Retrieve Prometheus metrics.

        Lightweight endpoint for health monitoring.
        """
        with self.client.get(
            "/api/v1/metrics",
            catch_response=True,
            name="/api/v1/metrics",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")


# Alternative: Heavy load user for stress testing
class HeavyLoadUser(HttpUser):
    """
    Simulates a heavy load user for stress testing.

    This user performs only expensive operations:
    - Backtest execution (50%)
    - Pattern detection (30%)
    - Signal generation (20%)

    Use this to stress test the system and identify breaking points.
    """

    wait_time = between(0.5, 1.5)
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    timeframes = ["1d", "1h"]

    @task(50)
    def run_backtest(self):
        """Execute backtest (heavy workload)."""
        symbol = choice(self.symbols)
        with self.client.post(
            "/api/v1/backtests/run",
            json={
                "symbol": symbol,
                "start_date": "2023-01-01",
                "end_date": "2024-01-01",
                "strategy": "wyckoff_spring",
            },
            catch_response=True,
            name="/api/v1/backtests/run",
        ) as response:
            if response.status_code in [200, 201, 202]:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(30)
    def detect_patterns(self):
        """Detect patterns (expensive operation)."""
        symbol = choice(self.symbols)
        timeframe = choice(self.timeframes)
        with self.client.get(
            "/api/v1/patterns/detect",
            params={"symbol": symbol, "timeframe": timeframe},
            catch_response=True,
            name="/api/v1/patterns/detect",
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(20)
    def generate_signals(self):
        """Generate signals (moderate workload)."""
        symbol = choice(self.symbols)
        timeframe = choice(self.timeframes)
        with self.client.post(
            "/api/v1/signals/generate",
            json={"symbol": symbol, "timeframe": timeframe},
            catch_response=True,
            name="/api/v1/signals/generate",
        ) as response:
            if response.status_code in [200, 201, 404]:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")
