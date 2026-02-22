# Story 25.6: Data Provider Factory with Fallback Chain

## Story
**As a** developer,
**I want** a centralized data provider factory that selects providers based on configuration and implements a fallback chain,
**So that** the system does not depend on a single hardcoded provider and can degrade gracefully when Alpaca is unavailable.

## Acceptance Criteria

**AC1**: DEFAULT_PROVIDER=polygon → PolygonAdapter returned from `get_historical_provider()`

**AC2**: Polygon fails (HTTP 429) → Yahoo fallback used → WARNING logged noting failure and fallback

**AC3**: Both Polygon and Yahoo fail → `DataProviderError` raised listing providers tried; NO synthetic data returned

**AC4**: `AUTO_EXECUTE_ORDERS=true` + missing Alpaca credentials → server startup fails immediately with actionable error message listing missing env vars

**AC5**: No direct instantiation of AlpacaAdapter/PolygonAdapter/YahooAdapter outside `factory.py` — all routes through `MarketDataProviderFactory`

**AC6**: `get_streaming_provider()` without Alpaca keys → `ConfigurationError` with required env var names

## Working Directory
E:/projects/claude_code/bmad4_wyck_vol/.worktrees/feat-story-25.6

See IMPLEMENTATION_BRIEF.md for full technical details.
