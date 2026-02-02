"""
Performance benchmark suite for refactored code (Story 22.15).

This package contains performance benchmarks to verify no performance regression
after code refactoring. Benchmarks cover:

- Phase Detection: Wyckoff phase classification and event detection
- Campaign Detection: Pattern grouping and campaign lifecycle
- API Routes: Backtest preview and campaign list endpoints

Run benchmarks:
    cd backend
    poetry run pytest tests/benchmarks/ -v -m benchmark
    poetry run pytest tests/benchmarks/ -v -m benchmark -s  # Detailed output
"""
