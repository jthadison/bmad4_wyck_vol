# BMAD Wyckoff Volume Pattern Detection System

A sophisticated algorithmic trading system that detects Wyckoff accumulation/distribution patterns, analyzes volume relationships, and generates actionable trade signals for equity markets.

## Overview

This system implements the Wyckoff methodology for institutional volume pattern detection, combining classical technical analysis with modern data processing. The platform identifies key market structures (Springs, Upthrusts, Sign of Strength/Weakness), validates them through multi-timeframe volume analysis, and delivers real-time trade signals via a responsive web dashboard.

**Key Features:**
- Real-time pattern detection using Wyckoff methodology
- Multi-timeframe volume analysis and correlation
- Automated trade signal generation with risk parameters
- Interactive dashboard with TradingView-style charts
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

```
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