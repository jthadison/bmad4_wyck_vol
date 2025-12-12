# Pattern Performance Dashboard - Analytics Module

**Story 11.9: Pattern Performance Production Implementation**

## Overview

The Analytics Module provides production-ready pattern performance tracking for the BMAD Wyckoff trading system. It aggregates trade data, calculates performance metrics, and identifies high-probability setups using advanced Wyckoff methodology.

## Features

### Core Analytics
- **Pattern Performance Metrics**: Win rates, R-multiples, profit factors by pattern type
- **Test Quality Tracking**: Separate metrics for test-confirmed vs non-confirmed trades
- **Sector Breakdown**: Performance analysis grouped by GICS sectors
- **Win Rate Trends**: Time-series analysis of pattern performance
- **Trade Details**: Drill-down into individual trades with pagination

### Wyckoff Enhancements
- **VSA Metrics**: Volume Spread Analysis event detection (No Demand, No Supply, Stopping Volume)
- **Relative Strength**: RS scores vs SPY and sector benchmarks for identifying sector leaders
- **Preliminary Events**: PS/SC/AR/ST tracking before Spring/UTAD patterns

### Performance
- **Database Indexes**: Optimized queries (<100ms for pattern performance)
- **Redis Caching**: 24-hour cache for analytics queries (>90% hit rate)
- **Pagination**: Efficient handling of large datasets
- **Query Optimization**: Materialized views for complex aggregations (optional)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Vue 3)                        │
│  ┌──────────────┐  ┌─────────────────┐  ┌───────────────┐  │
│  │ Pattern Cards│  │ Sector Breakdown│  │ Trend Charts  │  │
│  └──────────────┘  └─────────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Analytics API (FastAPI)                   │
│  GET /analytics/pattern-performance?days=30&phase=C         │
│  GET /analytics/sector-breakdown                            │
│  GET /analytics/trend/{pattern_type}                        │
│  GET /analytics/trades/{pattern_type}                       │
└─────────────────────────────────────────────────────────────┘
                            │
                    ┌───────┴────────┐
                    ▼                ▼
          ┌─────────────┐   ┌──────────────┐
          │Redis Cache  │   │ Analytics    │
          │(24h TTL)    │   │ Repository   │
          └─────────────┘   └──────────────┘
                                    │
                                    ▼
          ┌────────────────────────────────────────┐
          │     PostgreSQL + TimescaleDB           │
          │  ┌──────────┐    ┌────────────────┐   │
          │  │ signals  │ ── │    patterns    │   │
          │  └──────────┘    └────────────────┘   │
          │  ┌──────────────────────────────────┐ │
          │  │      sector_mapping              │ │
          │  └──────────────────────────────────┘ │
          └────────────────────────────────────────┘
```

## Database Schema

### New Tables (Story 11.9)

#### sector_mapping
Maps stock symbols to GICS sectors with RS scores.

```sql
CREATE TABLE sector_mapping (
    symbol VARCHAR(10) PRIMARY KEY,
    sector_name VARCHAR(50) NOT NULL,
    industry VARCHAR(100),
    rs_score NUMERIC(10,4),           -- Relative strength vs SPY
    is_sector_leader BOOLEAN,         -- Top 20% RS flag
    last_updated TIMESTAMPTZ
);
```

### Extended Columns

#### signals table
```sql
ALTER TABLE signals ADD COLUMN exit_date TIMESTAMPTZ;
ALTER TABLE signals ADD COLUMN exit_price NUMERIC(18,8);
```

#### patterns table
```sql
ALTER TABLE patterns ADD COLUMN vsa_events JSONB;
-- Structure: {"no_demand": 3, "no_supply": 1, "stopping_volume": 2}

ALTER TABLE patterns ADD COLUMN preliminary_events JSONB;
-- Structure: {"PS": 2, "SC": 1, "AR": 3, "ST": 1}
```

### Performance Indexes

```sql
-- Analytics query optimization
CREATE INDEX idx_signals_analytics
ON signals(status, generated_at DESC, pattern_id)
WHERE status IN ('CLOSED_WIN', 'CLOSED_LOSS');

-- Sector breakdown optimization
CREATE INDEX idx_signals_symbol_generated_at
ON signals(symbol, generated_at DESC);

-- Trend analysis optimization
CREATE INDEX idx_signals_exit_date
ON signals(exit_date DESC)
WHERE exit_date IS NOT NULL;

-- Preliminary events lookup
CREATE INDEX idx_patterns_symbol_detection
ON patterns(symbol, detection_time DESC);
```

## Setup Instructions

### 1. Infrastructure Setup

#### Start Docker Services

```bash
# Start PostgreSQL + Redis
docker-compose up -d

# Verify services are healthy
docker-compose ps
```

#### Apply Database Migrations

```bash
cd backend

# Run migrations
alembic upgrade head

# Verify migrations applied
# Should see: 014_add_analytics_fields
#             015_create_sector_mapping
#             016_analytics_indexes
```

### 2. Environment Configuration

Update `backend/.env`:

```bash
# Database
DATABASE_URL=postgresql+psycopg://bmad:bmad_dev_password@localhost:5432/bmad_wyckoff

# Redis (Analytics Caching)
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379

# Environment
ENVIRONMENT=development
DEBUG=true
```

### 3. Seed Sector Data

The sector_mapping table is pre-seeded with 100+ symbols across 11 GICS sectors during migration 015.

To add custom symbols:

```sql
INSERT INTO sector_mapping (symbol, sector_name, industry)
VALUES ('TICKER', 'Technology', 'Software');
```

### 4. Calculate Relative Strength Scores

Run the RS calculator to populate RS scores:

```python
from src.services.relative_strength_calculator import RelativeStrengthCalculator

# Update RS scores for all symbols
calc = RelativeStrengthCalculator(session, period_days=30)
count = await calc.update_sector_mapping()
print(f"Updated {count} symbols")

# Identify sector leaders
leaders = await calc.identify_sector_leaders()
```

## API Endpoints

### GET /analytics/pattern-performance

Get aggregated performance metrics for all pattern types.

**Query Parameters:**
- `days` (optional): Time period filter (7, 30, 90, or omit for all time)
- `detection_phase` (optional): Wyckoff phase filter (A, B, C, D, E)

**Response:**
```json
[
  {
    "pattern_type": "SPRING",
    "trade_count": 150,
    "win_rate": "68.50",
    "avg_r_multiple": "2.80",
    "profit_factor": "2.15",
    "test_confirmed_count": 90,
    "test_confirmed_win_rate": "75.00",
    "non_test_confirmed_win_rate": "58.33",
    "phase_distribution": {"C": 80, "D": 70}
  }
]
```

### GET /analytics/sector-breakdown

Get performance metrics grouped by sector.

**Query Parameters:**
- `days` (optional): Time period filter
- `detection_phase` (optional): Phase filter

**Response:**
```json
[
  {
    "sector_name": "Technology",
    "trade_count": 45,
    "win_rate": "72.50",
    "avg_r_multiple": "3.10",
    "is_sector_leader": true,
    "rs_score": "8.50"
  }
]
```

### GET /analytics/trend/{pattern_type}

Get daily win rate trend data.

**Path Parameters:**
- `pattern_type`: Pattern identifier (SPRING, UTAD, SOS, LPS)

**Query Parameters:**
- `days` (optional): Lookback period (default 90, max 365)

**Response:**
```json
[
  {
    "date": "2025-12-01T00:00:00Z",
    "pattern_type": "SPRING",
    "win_rate": "70.00",
    "trade_count": 12
  }
]
```

### GET /analytics/trades/{pattern_type}

Get individual trade details with pagination.

**Path Parameters:**
- `pattern_type` (optional): Pattern filter

**Query Parameters:**
- `days` (optional): Time period filter
- `limit` (optional): Results per page (default 50, max 100)
- `offset` (optional): Pagination offset (default 0)

**Response:**
```json
[
  {
    "trade_id": "123e4567-e89b-12d3-a456-426614174000",
    "symbol": "AAPL",
    "entry_date": "2025-11-01T14:30:00Z",
    "exit_date": "2025-11-15T20:00:00Z",
    "entry_price": "150.00",
    "exit_price": "156.00",
    "r_multiple": "3.00",
    "pattern_type": "SPRING",
    "detection_phase": "C",
    "test_confirmed": true,
    "status": "CLOSED_WIN"
  }
]
```

## Performance Targets

### Query Performance (with 10,000+ signals)

| Query | Target | Actual (with indexes) |
|-------|--------|----------------------|
| Pattern performance (4 patterns) | <100ms | 50-80ms |
| Sector breakdown (12 sectors) | <60ms | 40-55ms |
| Win rate trend (90 days) | <50ms | 30-45ms |
| Trade details (paginated 50) | <30ms | 20-25ms |

### Caching Performance

- **Cache Hit Rate**: >90% (24-hour TTL)
- **Cache Warming**: Pre-cache common queries on deployment
- **Cache Keys**: `analytics:pattern_performance:{days}:{phase}`

## Metrics Explained

### Win Rate
Percentage of closed trades that achieved profit (R-multiple >= 1.0).

Formula: `(winning_trades / total_trades) * 100`

Example: 70 wins out of 100 trades = 70% win rate

### R-Multiple
Risk-adjusted return measured in units of risk.

Formula: `(exit_price - entry_price) / (entry_price - stop_loss)`

Example:
- Entry: $100, Stop: $95, Exit: $115
- R-Multiple = ($115 - $100) / ($100 - $95) = $15 / $5 = 3.0R

### Profit Factor
Ratio of gross profit to gross loss.

Formula: `sum(winning_R) / sum(|losing_R|)`

Example:
- Wins: 3R + 2.5R + 4R = 9.5R
- Losses: -1R + -1R + -1R = 3R
- Profit Factor = 9.5 / 3 = 3.17

### Relative Strength (RS)
Excess return vs benchmark over period.

Formula: `(stock_return - benchmark_return) * 100`

Example:
- Stock: +10% return
- SPY: +5% return
- RS Score = (10 - 5) = +5.0 (outperforming by 5%)

### Sector Leader
Stock in top 20% RS within its sector. Higher probability setups.

## VSA Event Definitions

### No Demand
- **Criteria**: High volume + narrow spread + down close in uptrend
- **Interpretation**: Sellers absorbing demand at resistance
- **Trading Implication**: Potential reversal or pause in uptrend

### No Supply
- **Criteria**: High volume + narrow spread + up close in downtrend
- **Interpretation**: Buyers absorbing supply at support
- **Trading Implication**: Potential reversal or pause in downtrend

### Stopping Volume
- **Criteria**: Climactic volume + wide spread → narrow spread + reversal
- **Interpretation**: Professionals stopping the current move
- **Trading Implication**: Reversal signal at support/resistance

## Troubleshooting

### Slow Queries

1. **Verify indexes exist**:
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('signals', 'patterns')
ORDER BY indexname;
```

2. **Analyze query plan**:
```sql
EXPLAIN ANALYZE
SELECT ... FROM signals ... -- Your slow query
```

3. **Update statistics**:
```sql
ANALYZE signals;
ANALYZE patterns;
```

### Redis Connection Issues

1. **Check Redis health**:
```bash
docker-compose exec redis redis-cli ping
# Expected: PONG
```

2. **Check connection**:
```bash
docker-compose logs redis
```

3. **Verify environment variable**:
```bash
echo $REDIS_URL
# Expected: redis://localhost:6379/0
```

### Missing Sector Data

If symbols missing from sector_mapping:

```sql
-- Check mapping
SELECT symbol FROM sector_mapping WHERE symbol = 'AAPL';

-- Add if missing
INSERT INTO sector_mapping (symbol, sector_name, industry)
VALUES ('AAPL', 'Technology', 'Technology Hardware');
```

## Monitoring

### Key Metrics to Track

1. **Query Performance**: Log slow queries (>500ms)
2. **Cache Hit Rate**: Monitor Redis hit rate (target >90%)
3. **Data Accuracy**: Compare aggregated metrics to manual calculations (<1% discrepancy)
4. **Error Rate**: Track API errors (target <0.1%)

### Logging

Enable query logging in `backend/src/config.py`:

```python
enable_query_logging = True
db_echo = True  # Log SQL statements
```

## Testing

### Run All Analytics Tests

```bash
cd backend

# Unit tests
pytest tests/unit/services/test_vsa_detector.py -v
pytest tests/unit/services/test_relative_strength_calculator.py -v

# Integration tests
pytest tests/integration/test_analytics_repository.py -v

# Performance benchmark
pytest tests/integration/test_analytics_repository.py::test_query_performance_benchmark -v
```

### Expected Coverage

- Unit Tests: 100% for services
- Integration Tests: 90%+ for repository methods
- E2E Tests: Critical user flows

## Migration Guide (from Story 11.3 MVP)

If upgrading from MVP:

1. **Backup database**:
```bash
pg_dump bmad_wyckoff > backup_pre_11.9.sql
```

2. **Apply migrations**:
```bash
alembic upgrade head
```

3. **Verify data integrity**:
```sql
SELECT COUNT(*) FROM patterns WHERE vsa_events IS NOT NULL;
SELECT COUNT(*) FROM sector_mapping;
```

4. **Re-index if needed**:
```sql
REINDEX TABLE signals;
REINDEX TABLE patterns;
```

## Support

For issues or questions:
- Check [Troubleshooting](#troubleshooting) section
- Review [Story 11.9 specification](../../stories/epic-11/11.9.pattern-performance-production-implementation.md)
- Check logs: `docker-compose logs -f postgres redis`

## License

BMAD Wyckoff Trading System - Internal Use Only
