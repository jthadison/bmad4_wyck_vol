# Backend Testing Guide

Comprehensive testing guide for the BMAD Wyckoff backend.

## Table of Contents

- [Testing Strategy](#testing-strategy)
- [Running Tests](#running-tests)
- [Test Organization](#test-organization)
- [Writing Tests](#writing-tests)
- [Fixtures and Mocks](#fixtures-and-mocks)
- [Coverage Requirements](#coverage-requirements)

## Testing Strategy

We follow the test pyramid approach:

```
         E2E Tests (Playwright)
        /                      \
    Integration Tests (pytest)  Component Tests (Vitest)
   /                              \
Backend Unit Tests (pytest)    Frontend Unit Tests (Vitest)
```

### Test Types

**Unit Tests** (`tests/unit/`):
- Test individual functions/classes in isolation
- Fast (<10ms per test)
- Mock all external dependencies
- High coverage (>90%)

**Integration Tests** (`tests/integration/`):
- Test component interactions
- Moderate speed (100ms-1s per test)
- Use real database (PostgreSQL service container)
- Mock only external APIs (Polygon.io, broker)

**Benchmark Tests** (`tests/benchmarks/`):
- Performance testing and regression detection
- Marked with `@pytest.mark.benchmark`
- Run separately from unit/integration tests

## Running Tests

### All Tests

```bash
poetry run pytest
```

### Unit Tests Only

```bash
poetry run pytest tests/unit
```

### Integration Tests

```bash
poetry run pytest tests/integration
```

### Specific Test File

```bash
poetry run pytest tests/unit/test_spring_detector.py
```

### Specific Test Function

```bash
poetry run pytest tests/unit/test_spring_detector.py::test_spring_detector_accepts_low_volume_breakdown
```

### With Coverage

```bash
poetry run pytest --cov=src --cov-report=html
```

Open `htmlcov/index.html` to view the coverage report.

### Watch Mode

```bash
poetry run ptw
```

Auto-runs tests when files change.

### Debug Failing Tests

```bash
poetry run pytest --pdb
```

Drops into debugger on test failure.

### Skip Slow Tests

```bash
poetry run pytest -m "not slow"
```

Excludes tests marked with `@pytest.mark.slow`.

### Run Only Slow Tests

```bash
pytest -m slow
```

### Extended Backtests (CI Only)

```bash
pytest -m extended
```

Runs 2-year backtests on 4 symbols (AAPL, MSFT, GOOGL, TSLA).

## Test Organization

```
tests/
├── unit/                   # Unit tests (fast, isolated)
│   ├── pattern_engine/     # Pattern detector tests
│   ├── backtesting/        # Backtesting engine tests
│   └── ...
├── integration/            # Integration tests (real DB)
│   ├── test_detector_accuracy.py
│   ├── test_backtest_integration.py
│   └── ...
├── benchmarks/             # Performance benchmarks
│   ├── test_signal_generation_latency.py
│   └── test_backtest_speed.py
├── mocks/                  # Mock adapters
│   ├── mock_polygon_adapter.py
│   ├── mock_broker_adapter.py
│   └── __init__.py
├── fixtures/               # Test data fixtures
│   ├── ohlcv_bars.py
│   ├── edge_cases.py
│   └── ...
├── datasets/               # Labeled pattern datasets (Git LFS)
│   └── labeled_patterns_v1.parquet
├── conftest.py             # Pytest fixtures
└── README.md               # This file
```

## Writing Tests

### Test Naming Convention

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

Use descriptive names:
- ✅ `test_spring_detector_rejects_high_volume_breakdown()`
- ❌ `test_spring()`

### Test Structure (AAA Pattern)

```python
def test_spring_detector_accepts_low_volume_breakdown():
    # Arrange
    detector = SpringDetector()
    bars = spring_pattern_bars()

    # Act
    result = detector.detect(bars)

    # Assert
    assert result is not None
    assert result.confidence > 0.75
```

### Using Fixtures

```python
def test_with_mock_data_feed(mock_data_feed, sample_ohlcv_bars):
    # mock_data_feed: MockPolygonAdapter instance
    # sample_ohlcv_bars: Dictionary of fixture scenarios

    mock_data_feed.fixture_data["AAPL"] = sample_ohlcv_bars["spring_pattern"]
    bars = await mock_data_feed.fetch_historical_bars("AAPL", ...)
    assert len(bars) == 100
```

### Async Tests

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

### Parametrized Tests

```python
@pytest.mark.parametrize("volume,expected", [
    (500000, False),  # Low volume - invalid
    (1700000, True),  # High volume - valid
])
def test_volume_validation(volume, expected):
    result = validate_volume(volume)
    assert result == expected
```

## Fixtures and Mocks

### Available Fixtures

**Database**:
- `db_engine`: Test database engine (in-memory SQLite)
- `db_session`: Database session (auto-rollback after test)
- `async_client`: Async HTTP client for API testing

**Authentication**:
- `auth_token`: JWT access token for test user
- `auth_headers`: Headers with Bearer token

**Mocks**:
- `mock_data_feed`: MockPolygonAdapter (no actual API calls)
- `mock_broker`: MockBrokerAdapter (simulates order fills)

**OHLCV Fixtures**:
- `sample_ohlcv_bars`: Dict with pattern scenarios (spring, SOS, UTAD, false spring)
- `edge_case_bars`: Dict with edge cases (zero volume, gaps, extreme spread, etc.)

### Creating Custom Fixtures

```python
@pytest.fixture
def my_custom_fixture():
    # Setup
    resource = create_resource()

    yield resource

    # Teardown
    resource.cleanup()
```

## Coverage Requirements

- **Target**: 90%+ test coverage (NFR8)
- **Enforcement**: PR CI pipeline fails if coverage < 90%
- **Exclusions**: Migration scripts, generated code, test files

### Generate Coverage Report

```bash
poetry run pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Coverage Configuration

See `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "*/migrations/*", "*/alembic/*"]

[tool.coverage.report]
fail_under = 90
show_missing = true
```

## Continuous Integration

Tests run automatically on:

- **Pre-commit**: Fast unit tests (excludes `@pytest.mark.slow`)
- **Pull Request**: All tests + accuracy tests + coverage check
- **Main Branch**: All tests + extended backtests

See `.github/workflows/pr-ci.yaml` for details.

## Troubleshooting

### Tests Hanging

Check for missing `await` in async tests or database connection issues.

### Import Errors

Ensure you're running from the `backend/` directory:

```bash
cd backend
poetry run pytest
```

### Database Errors

Integration tests require PostgreSQL. Use Docker Compose:

```bash
docker-compose up postgres
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wyckoff_test
poetry run pytest tests/integration
```

### Slow Test Suite

Run only fast tests:

```bash
pytest -m "not slow" -n auto
```

Use `-n auto` for parallel execution.

## Best Practices

1. **Isolate Tests**: Each test should be independent (no shared state)
2. **Mock External APIs**: Never make real API calls in tests
3. **Use Fixtures**: Reuse common setup via fixtures (DRY principle)
4. **Descriptive Names**: Test names should explain what is being tested
5. **AAA Pattern**: Arrange, Act, Assert for clear structure
6. **Fast Tests**: Keep unit tests fast (<10ms)
7. **Deterministic**: Use fixed seeds, freeze time, avoid randomness

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [Testing Guide](../../docs/testing-guide.md)
