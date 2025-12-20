# Signal Scanning Guide - Manual API Usage

This guide shows you how to manually trigger Wyckoff pattern scans for trade signal generation.

## Quick Start

### Option 1: Using the Python Script (Recommended)

```bash
# Show API usage guide
cd backend
poetry run python scripts/manual_scan.py --help-api

# Scan a single symbol
poetry run python scripts/manual_scan.py AAPL

# Scan multiple symbols
poetry run python scripts/manual_scan.py AAPL TSLA NVDA

# Scan with different timeframe
poetry run python scripts/manual_scan.py AAPL --timeframe 1h

# Get more historical data
poetry run python scripts/manual_scan.py AAPL --lookback 730
```

### Option 2: Using cURL (Direct API)

```bash
# Scan a single symbol
curl -X GET 'http://localhost:8000/api/v1/orchestrator/analyze/AAPL?timeframe=1d'

# Scan multiple symbols
curl -X POST 'http://localhost:8000/api/v1/orchestrator/analyze' \
     -H 'Content-Type: application/json' \
     -d '{"symbols": ["AAPL", "TSLA", "NVDA"], "timeframe": "1d"}'

# Check orchestrator health
curl http://localhost:8000/api/v1/orchestrator/health
```

### Option 3: Using the Frontend UI

1. Open http://localhost:5174 in your browser
2. Navigate to the **Signals** or **Patterns** page
3. Use the UI controls to trigger scans

---

## API Endpoints Reference

### 1. Analyze Single Symbol

**Endpoint:** `GET /api/v1/orchestrator/analyze/{symbol}`

**Parameters:**
- `symbol` (path): Stock symbol (e.g., "AAPL")
- `timeframe` (query): Bar timeframe - `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w` (default: `1d`)

**Response:**
```json
[
  {
    "signal_id": "uuid",
    "symbol": "AAPL",
    "timeframe": "1d",
    "pattern_type": "SPRING",
    "phase": "C",
    "entry_price": "150.00",
    "stop_price": "145.00",
    "target_price": "170.00",
    "position_size": 100,
    "risk_amount": "500.00",
    "r_multiple": "4.0",
    "confidence_score": 85
  }
]
```

**Example:**
```bash
curl -X GET 'http://localhost:8000/api/v1/orchestrator/analyze/AAPL?timeframe=1d'
```

---

### 2. Analyze Multiple Symbols (Batch)

**Endpoint:** `POST /api/v1/orchestrator/analyze`

**Request Body:**
```json
{
  "symbols": ["AAPL", "TSLA", "NVDA"],
  "timeframe": "1d"
}
```

**Response:**
```json
{
  "signals": {
    "AAPL": [...],
    "TSLA": [...],
    "NVDA": [...]
  },
  "total_signals": 3,
  "symbols_analyzed": 3
}
```

**Example:**
```bash
curl -X POST 'http://localhost:8000/api/v1/orchestrator/analyze' \
     -H 'Content-Type: application/json' \
     -d '{"symbols": ["AAPL", "TSLA"], "timeframe": "1d"}'
```

---

### 3. Orchestrator Health Check

**Endpoint:** `GET /api/v1/orchestrator/health`

**Response:**
```json
{
  "status": "healthy",
  "components": {
    "container": {
      "status": "healthy",
      "loaded": ["volume_analyzer", "trading_range_detector", "risk_manager"],
      "failed": [],
      "loaded_count": 3,
      "failed_count": 0
    },
    "cache": {
      "hits": 125,
      "misses": 45,
      "hit_rate": 0.735,
      "size": 42
    },
    "event_bus": {
      "event_count": 234,
      "error_count": 0
    }
  },
  "metrics": {
    "analysis_count": 156,
    "signal_count": 23,
    "error_count": 2
  }
}
```

**Example:**
```bash
curl http://localhost:8000/api/v1/orchestrator/health
```

---

## System Requirements

### Configuration Checklist

- [x] **Backend Running**: http://localhost:8000
- [x] **Frontend Running**: http://localhost:5174
- [x] **Database**: PostgreSQL on port 5432
- [x] **Polygon API Key**: Configured in `.env`
- [x] **Database Migrations**: Applied

### Verify Configuration

```bash
# Check backend health
curl http://localhost:8000/api/v1/health

# Check orchestrator health
curl http://localhost:8000/api/v1/orchestrator/health

# Verify API key is configured
grep POLYGON_API_KEY .env
```

---

## Current Limitations & Known Issues

### Issue 1: Missing Pattern Detectors
**Status:** Some pattern detectors failed to load
**Impact:** Reduced pattern detection capabilities
**Loaded:** `volume_analyzer`, `trading_range_detector`, `risk_manager`
**Failed:** `pivot_detector`, `sos_detector`, `lps_detector`, etc.

**Resolution:** These are code import errors that need fixing in the backend.

### Issue 2: Data Repository Session Error
**Status:** `OHLCVRepository.__init__() missing 1 required positional argument: 'session'`
**Impact:** Signal scans return empty results
**Location:** [backend/src/orchestrator/service.py](backend/src/orchestrator/service.py)

**Workaround:** Currently investigating. The API accepts requests but cannot fetch market data.

### Issue 3: Empty Market Data
**Status:** `ohlcv_bars` table is empty
**Impact:** No historical data to analyze

**Solution:** Use the manual_scan.py script which includes data ingestion:
```bash
cd backend
poetry run python scripts/manual_scan.py AAPL
```

---

## Pattern Types Detected

The system detects the following Wyckoff patterns:

1. **SPRING** - Wyckoff Spring (accumulation shakeout)
2. **UTAD** - Upthrust After Distribution
3. **SOS** - Sign of Strength
4. **SOW** - Sign of Weakness
5. **LPS** - Last Point of Support
6. **ST** - Secondary Test
7. **AR** - Automatic Rally
8. **SC** - Selling Climax

---

## Timeframe Options

Available bar timeframes:
- **Intraday**: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`
- **Daily**: `1d`
- **Weekly**: `1w`

---

## Example Workflows

### Workflow 1: Quick Single Symbol Scan

```bash
# Step 1: Check system health
curl http://localhost:8000/api/v1/orchestrator/health

# Step 2: Run scan
curl -X GET 'http://localhost:8000/api/v1/orchestrator/analyze/AAPL?timeframe=1d'

# Step 3: View results (check for signals array)
```

### Workflow 2: Batch Scan Multiple Symbols

```bash
# Create request payload
cat > scan_request.json <<EOF
{
  "symbols": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"],
  "timeframe": "1d"
}
EOF

# Run batch scan
curl -X POST 'http://localhost:8000/api/v1/orchestrator/analyze' \
     -H 'Content-Type: application/json' \
     -d @scan_request.json | jq .

# jq formats JSON output nicely (optional)
```

### Workflow 3: Using Python Script with Data Ingestion

```bash
cd backend

# Scan with automatic data fetch from Polygon
poetry run python scripts/manual_scan.py AAPL TSLA NVDA

# This will:
# 1. Fetch 365 days of historical data from Polygon
# 2. Store in database
# 3. Run Wyckoff pattern analysis
# 4. Display any signals found
```

---

## Troubleshooting

### Problem: "No trade signals found"

**Possible Causes:**
1. No Wyckoff patterns present in the data (normal - patterns are rare)
2. Pattern detectors failed to load
3. Market data missing or incomplete
4. Confidence thresholds too high

**Solutions:**
- Try scanning more symbols
- Use different timeframes (1d, 1h, 4h)
- Check orchestrator health for failed components
- Review backend logs for errors

### Problem: API returns empty array `[]`

**Causes:**
- Database session error (known issue)
- No market data in database
- All patterns filtered by risk rules

**Check:**
```bash
# View backend logs
# Look for errors in the backend console output

# Check database has data
# Connect to PostgreSQL and query ohlcv_bars table
```

### Problem: Connection refused

**Cause:** Backend not running

**Solution:**
```bash
cd backend
poetry run uvicorn src.api.main:app --reload --port 8000
```

---

## API Documentation

Full interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Next Steps

1. **Fix Backend Issues**: Resolve the OHLCVRepository session error
2. **Load Market Data**: Populate historical bars for analysis
3. **Fix Pattern Detectors**: Repair import errors for failed components
4. **Test End-to-End**: Verify full pipeline from data fetch to signal generation

---

## Support

For issues with this system:
- Check backend console logs for errors
- Review orchestrator health endpoint
- Consult [README.md](README.md) for architecture details
- Review story documentation in [docs/stories/](docs/stories/)

---

**Generated**: 2025-12-19
**Application**: BMAD Wyckoff Volume Pattern Detection System
