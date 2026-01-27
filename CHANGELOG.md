# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

#### [Issue #242] - Validation Chain Factory Signature Update (2026-01-27)

**Breaking Change**: Updated validation chain factory function signatures to properly support `StrategyValidator` dependency injection.

**Changes:**
- `create_default_validation_chain()` now requires `news_calendar_factory: NewsCalendarFactory` parameter
- `create_validation_chain()` now accepts optional `news_calendar_factory: NewsCalendarFactory | None` parameter
- Added runtime validation to prevent instantiation without required dependency

**Migration Guide:**
```python
# Before (broken)
orchestrator = create_default_validation_chain()

# After (correct)
from src.services.news_calendar_factory import NewsCalendarFactory
news_factory = NewsCalendarFactory(earnings_service, forex_service)
orchestrator = create_default_validation_chain(news_factory)
```

**Impact:**
- ✅ All 11 unit tests in `test_validation_chain.py` now pass (previously skipped)
- ✅ Consolidated `mock_news_calendar_factory` fixture to shared `conftest.py`
- ✅ Updated 23 test methods across 3 test files

**Files Modified:**
- `backend/src/signal_generator/validation_chain.py`
- `backend/tests/conftest.py`
- `backend/tests/unit/signal_generator/test_validation_chain.py`
- `backend/tests/integration/signal_generator/test_validation_chain_integration.py`
- `backend/tests/integration/signal_generator/test_realtime_validation_integration.py`

**References:**
- GitHub Issue: #242
- Pull Request: #262
