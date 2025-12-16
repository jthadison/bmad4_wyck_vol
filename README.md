# BMAD Wyckoff Volume Pattern Detection System

A sophisticated algorithmic trading system that detects Wyckoff accumulation/distribution patterns, analyzes volume relationships, and generates actionable trade signals for equity markets.

## Overview

This system implements the Wyckoff methodology for institutional volume pattern detection, combining classical technical analysis with modern data processing. The platform identifies key market structures (Springs, Upthrusts, Sign of Strength/Weakness), validates them through multi-timeframe volume analysis, and delivers real-time trade signals via a responsive web dashboard.

**Key Features:**
- Real-time pattern detection using Wyckoff methodology
- **Wyckoff schematic template matching** (Story 11.5.1) - Automated detection of 4 classic Wyckoff schematics (Accumulation #1/#2, Distribution #1/#2) with confidence scoring
- **Point & Figure cause-building tracking** (Story 11.5.1) - P&F column counting with ATR-based analysis and projected jump target calculation
- **Interactive schematic overlays** (Story 11.5.1) - Visual template overlays on charts with deviation highlighting
- Multi-timeframe volume analysis and correlation
- Automated trade signal generation with risk parameters
- Interactive dashboard with TradingView-style charts and advanced Wyckoff visualizations
- Backtesting engine for strategy validation
- PostgreSQL data persistence with TimescaleDB extension support

## Architecture

The system follows a modern monorepo architecture with Python FastAPI backend and Vue 3 frontend:

- **Backend:** FastAPI, SQLAlchemy, Pydantic models, pandas/numpy for calculations
- **Frontend:** Vue 3, TypeScript, PrimeVue, Lightweight Charts (TradingView)
- **Data:** PostgreSQL 15+ with TimescaleDB extension (optional for MVP)
- **Infrastructure:** Docker Compose for local development

For detailed architecture documentation, see [docs/architecture/](docs/architecture/).

For product requirements and roadmap, see [docs/prd/](docs/prd/).

## Prerequisites

Before setting up the project, ensure you have the following installed:

- **Python:** 3.11 or higher
- **Node.js:** 18 or higher
- **Poetry:** 1.7 or higher (Python dependency management)
- **Docker:** 24 or higher
- **Docker Compose:** 2.24 or higher
- **Git:** For version control

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd bmad-wyckoff
```

### 2. Environment Configuration

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys and configuration:
- `POLYGON_API_KEY`: Your Polygon.io API key for market data
- Database credentials (defaults provided for local development)

### 3. Backend Setup

Install Python dependencies using Poetry:

```bash
cd backend
poetry install
```

This creates a virtual environment and installs all required packages including:
- FastAPI, SQLAlchemy, Pydantic
- pandas, numpy for data processing
- pytest, mypy, ruff for development

### 4. Frontend Setup

Install Node.js dependencies:

```bash
cd frontend
npm install
```

This installs Vue 3, TypeScript, Vite, PrimeVue, and development tools.

### 5. Start Development Environment

Use Docker Compose to start all services (PostgreSQL, backend, frontend):

```bash
docker-compose up
```

Or run services individually:

**Backend (FastAPI):**
```bash
cd backend
poetry run uvicorn src.api.main:app --reload --port 8000
```

**Frontend (Vite dev server):**
```bash
cd frontend
npm run dev
```

The application will be available at:
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs (Swagger UI)

## Wyckoff Charting Enhancements (Story 11.5.1)

The system now includes advanced Wyckoff charting capabilities with automated schematic matching and cause-building analysis:

### Schematic Template Matching

Automatically identifies which of the 4 classic Wyckoff schematics best matches the current chart pattern:

- **Accumulation #1 (Spring)**: Classic accumulation with shakeout below Creek level
- **Accumulation #2 (LPS)**: Accumulation without Spring, uses Last Point of Support
- **Distribution #1 (UTAD)**: Distribution with Upthrust After Distribution above Ice level
- **Distribution #2 (LPSY)**: Distribution without UTAD, uses Last Point of Supply

**Algorithm Features**:

- Pattern sequence matching against expected events (PS, SC, AR, ST, SPRING/UTAD, SOS/SOW)
- Confidence scoring (60-95%) with bonuses for critical patterns (SPRING, UTAD, LPS, LPSY)
- Minimum 60% threshold for schematic match validation

**UI Components**:

- **SchematicBadge**: Clickable badge showing schematic type and confidence score
- **Detail Modal**: Pattern sequence, template data points, and trading interpretation guide
- Color-coded confidence levels (Green 80%+, Yellow 70-79%, Orange <70%)

### Point & Figure Cause-Building Tracking

Tracks the progress of cause-building (accumulation/distribution) using Point & Figure methodology:

**Algorithm**:

- Column counting based on ATR (Average True Range) threshold
- Target column calculation: `min(18, duration_bars / 5)`
- Projected jump calculation: `creek + (range_height × column_count × 0.5)`
- Progress percentage: `(column_count / target_column_count) × 100`

**UI Components**:

- **CauseBuildingPanel**: Progress bar with column count display
- Color-coded progress stages (Complete, Advanced, Building, Early, Initial)
- Projected jump target in dollars
- Expandable methodology explanation
- Optional mini histogram showing column accumulation

### Schematic Template Overlay

Visual overlay system that renders the matched Wyckoff template directly on the chart:

**Features**:

- Dashed blue line overlay scaled to chart time and price range
- Coordinate scaling from normalized percentages (0-100%) to actual chart coordinates
- Toggle on/off via chart visibility controls
- Automatic scaling to trading range (Creek to Ice levels)

**Implementation**:

- Utility module: `frontend/src/utils/schematicOverlay.ts`
- 5 exported functions: `scaleTemplateToChart()`, `renderSchematicOverlay()`, `removeSchematicOverlay()`, `calculateDeviation()`, `hasSignificantDeviation()`
- Integrated with Lightweight Charts v4.1+ line series API

### Projected Jump Line

Conditional rendering of projected price target based on cause-building progress:

**Display Rules**:

- Only shown when progress > 50%
- Dashed green horizontal line at projected jump price
- Price label: "Projected Jump: $XXX.XX"

**Usage**:

```typescript
// Automatically shown in PatternChart.vue when conditions met
if (causeBuildingData.progress_percentage > 50) {
  candlestickSeries.createPriceLine({
    price: causeBuildingData.projected_jump,
    color: '#16A34A', // Green
    lineStyle: 1, // Dashed
  })
}
```

### API Integration

All Wyckoff data is returned via the existing chart API endpoint:

**Endpoint**: `GET /api/v1/charts/data`

**Response Structure**:

```json
{
  "schematic_match": {
    "schematic_type": "ACCUMULATION_1",
    "confidence_score": 85,
    "template_data": [
      { "x_percent": 10.0, "y_percent": 20.0 },
      { "x_percent": 20.0, "y_percent": 5.0 }
    ]
  },
  "cause_building": {
    "column_count": 8,
    "target_column_count": 18,
    "projected_jump": 165.50,
    "progress_percentage": 44.4,
    "count_methodology": "P&F Count: Counted 8 wide-range bars..."
  }
}
```

### Performance

Backend algorithms are optimized for real-time chart rendering:

- **Schematic matching**: O(n×m) ~40 iterations, < 100ms
- **P&F counting**: O(n) ~100 bars, < 50ms
- **ATR calculation**: O(n) 14-period, < 10ms

## Development

### Running Tests

**Backend (pytest):**

```bash
cd backend
poetry run pytest
```

**Frontend (Vitest):**

```bash
cd frontend
npm run test
```

### Code Quality

Pre-commit hooks are configured to run automatically on commit:

- **Ruff:** Python linting and formatting (10-100x faster than Black)
- **mypy:** Python type checking (strict mode)
- **ESLint:** TypeScript/Vue linting
- **Prettier:** TypeScript/Vue formatting

To install pre-commit hooks:

```bash
poetry run pre-commit install
```

To run manually:

```bash
poetry run pre-commit run --all-files
```

### Linting and Formatting

**Backend:**

```bash
cd backend
poetry run ruff check .
poetry run ruff format .
poetry run mypy src/
```

**Frontend:**

```bash
cd frontend
npm run lint
npm run format
```

## Project Structure

```text
bmad-wyckoff/
├── backend/
│   ├── src/
│   │   ├── api/               # FastAPI routes
│   │   ├── models/            # Pydantic models (source of truth)
│   │   ├── pattern_engine/    # Pattern detection logic
│   │   ├── market_data/       # Data ingestion
│   │   ├── signal_generator/  # Trade signal generation
│   │   ├── risk_management/   # Risk validation
│   │   ├── backtesting/       # Backtesting engine
│   │   └── repositories/      # Data access layer
│   ├── tests/                 # pytest test suite
│   └── pyproject.toml         # Poetry configuration
├── frontend/
│   ├── src/
│   │   ├── components/        # Vue components
│   │   ├── stores/            # Pinia state management
│   │   ├── services/          # API clients
│   │   ├── types/             # Auto-generated TypeScript types
│   │   └── views/             # Page components
│   └── package.json
├── infrastructure/
│   └── docker/
│       └── docker-compose.yml
├── shared/
│   ├── fixtures/              # Shared test data
│   └── types/                 # Generated TypeScript output
└── docs/                      # Documentation

```

## Documentation

- **Architecture:** [docs/architecture/](docs/architecture/)
- **Product Requirements:** [docs/prd/](docs/prd/)
- **User Stories:** [docs/stories/](docs/stories/)

## Technology Stack

### Backend
- **Python:** 3.11+
- **Framework:** FastAPI 0.109+
- **ORM:** SQLAlchemy 2.0+
- **Validation:** Pydantic 2.5+
- **Data Processing:** pandas 2.2+, numpy 2.0+
- **Testing:** pytest 8.0+, mypy 1.8+
- **Code Quality:** Ruff 0.1+ (linting/formatting)

### Frontend
- **TypeScript:** 5.3+
- **Framework:** Vue 3.4+
- **UI Library:** PrimeVue 3.50+
- **Charting:** Lightweight Charts 4.1+ (TradingView)
- **State Management:** Pinia 2.1+
- **Build Tool:** Vite 5.0+
- **Styling:** Tailwind CSS 3.4+
- **Testing:** Vitest 1.2+

### Infrastructure
- **Database:** PostgreSQL 15+ (with TimescaleDB 2.13+ optional)
- **Caching:** Redis (optional)
- **Containerization:** Docker 24+, Docker Compose 2.24+

## Contributing

Please ensure all tests pass and code quality checks succeed before submitting pull requests:

```bash
# Backend
cd backend
poetry run pytest
poetry run mypy src/
poetry run ruff check .

# Frontend
cd frontend
npm run test
npm run lint
```

## License

[Add your license information here]

## Support

For issues and questions, please open an issue on the project repository.