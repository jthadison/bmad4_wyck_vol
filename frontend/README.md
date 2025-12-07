# BMAD Wyckoff Trading Platform - Frontend

Vue 3 frontend application for the BMAD Wyckoff trading platform. Built with modern tooling for real-time signal visualization, portfolio management, and trade execution monitoring.

## Tech Stack

- **Framework**: Vue 3.4+ with Composition API (`<script setup>`)
- **Build Tool**: Vite 5.0+ (fast HMR, optimized builds)
- **Language**: TypeScript 5.3+ (strict mode enabled)
- **Styling**: Tailwind CSS 3.4+ (dark theme)
- **UI Components**: PrimeVue 3.50+ (DataTable, Charts, Dialogs)
- **State Management**: Pinia 2.1+ (official Vue store)
- **HTTP Client**: Axios 1.6+
- **WebSocket**: Native WebSocket API with reconnection
- **Router**: Vue Router 4.x
- **Testing**: Vitest 1.2+ with @vue/test-utils

## Prerequisites

- Node.js 18+
- npm 10+
- Backend API running on `http://localhost:8000` (development)

## Getting Started

### Installation

```bash
cd frontend
npm install
```

### Development

Start the dev server with hot module replacement:

```bash
npm run dev
```

The application will be available at `http://localhost:5173`

### Build for Production

```bash
npm run build
```

Build output will be in the `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── components/          # Reusable Vue components
│   │   ├── charts/          # Chart components (ChartView, PatternOverlay)
│   │   ├── signals/         # Signal components (SignalDashboard, SignalCard)
│   │   ├── campaigns/       # Campaign components (CampaignView)
│   │   └── ui/              # PrimeVue wrapper components
│   ├── views/               # Page-level components
│   │   ├── DashboardView.vue
│   │   ├── BacktestView.vue
│   │   └── SettingsView.vue
│   ├── composables/         # Vue composables
│   │   ├── useChart.ts
│   │   ├── useWebSocket.ts
│   │   ├── useSignals.ts
│   │   └── useApi.ts
│   ├── stores/              # Pinia stores
│   │   ├── barStore.ts      # OHLCV bars for charting
│   │   ├── patternStore.ts  # Detected patterns (Spring, SOS, etc.)
│   │   ├── signalStore.ts   # Trade signals
│   │   ├── campaignStore.ts # Multi-phase position campaigns
│   │   └── portfolioStore.ts # Portfolio metrics (heat %, capacity)
│   ├── services/            # API client, WebSocket, utilities
│   │   ├── api.ts           # Axios HTTP client
│   │   ├── websocket.ts     # WebSocket client with reconnection
│   │   └── errorHandler.ts  # API error parsing
│   ├── types/               # TypeScript type definitions
│   │   └── index.ts         # Placeholder types (will be auto-generated)
│   ├── router/              # Vue Router configuration
│   │   └── index.ts
│   ├── assets/              # Static assets
│   ├── App.vue
│   ├── main.ts
│   └── style.css
├── tests/                   # Vitest unit tests
├── public/                  # Static public assets
├── .env.development         # Development environment variables
├── .env.production          # Production environment variables
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
├── package.json
└── README.md
```

## Environment Variables

### Development (`.env.development`)

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
```

### Production (`.env.production`)

```env
VITE_API_BASE_URL=https://api.bmad-wyckoff.com/api/v1
VITE_WS_URL=wss://api.bmad-wyckoff.com/ws
```

Access environment variables in code:

```typescript
const apiUrl = import.meta.env.VITE_API_BASE_URL
```

⚠️ **IMPORTANT**: Use `import.meta.env` (Vite convention), NOT `process.env`.

## Type Codegen Workflow

Types are auto-generated from backend Pydantic models to ensure frontend/backend type safety.

### Current Status (Story 10.1)

Placeholder types are manually defined in `src/types/index.ts`.

### Future (Story 10.10)

1. Backend models are defined in `backend/src/models/` using Pydantic
2. Run codegen: `npm run codegen`
3. Types are generated to `frontend/src/types/`
4. Import types: `import { Signal, Pattern } from '@/types'`

⚠️ **CRITICAL RULE**: Never manually edit generated type files after codegen is set up.

## Scripts

```bash
npm run dev          # Start dev server with HMR
npm run build        # Type-check and build for production
npm run preview      # Preview production build locally
npm run type-check   # Run TypeScript type checking
npm run lint         # Lint and auto-fix code (ESLint)
npm run format       # Format code (Prettier)
npm run test         # Run tests in watch mode
npm run test:run     # Run tests once (CI)
npm run test:ui      # Run tests with UI
npm run coverage     # Generate coverage report
```

## Testing

The project uses Vitest for fast unit testing with Vue Test Utils.

### Run Tests

```bash
npm run test        # Watch mode
npm run test:run    # Run once (CI)
npm run test:ui     # UI mode
npm run coverage    # Coverage report
```

### Test Files

- Tests are located in `tests/` directory
- Test files use `.test.ts` or `.spec.ts` extension
- Example: `tests/App.test.ts`

### Coverage Target

80%+ coverage for core setup code (API client, WebSocket, stores).

## PrimeVue Components

Initialized components (Story 10.1):

- **Button** - Action buttons throughout UI
- **Card** - Container for signal cards, campaign details
- **Badge** - Status indicators (executed/rejected signals)
- **Tabs** - Tabbed views (Executed/Pending/Rejected signals)
- **Table** - Trade audit log table
- **Dialog** - Rejection detail modal

Theme: `lara-dark-blue` (dark mode for traders)

For full PrimeVue documentation: https://primevue.org/

## Folder Structure Documentation

### `components/`

Reusable Vue components organized by feature area.

### `views/`

Page-level components mapped to routes.

### `composables/`

Vue composables for shared reactive logic (useWebSocket, useSignals, etc.).

### `stores/`

Pinia stores for state management. 5 primary stores:

1. **barStore** - OHLCV bars for charting
2. **patternStore** - Detected patterns (Spring, SOS, UTAD, LPS)
3. **signalStore** - Trade signals (PENDING, APPROVED, REJECTED, FILLED)
4. **campaignStore** - Multi-phase position campaigns
5. **portfolioStore** - Portfolio metrics (heat %, capacity)

### `services/`

Non-reactive services for API calls, WebSocket management, utilities.

### `types/`

TypeScript type definitions. Currently placeholder types, will be auto-generated from Pydantic models in Story 10.10.

## Code Quality

### ESLint

Configuration: `.eslintrc.cjs`

- Extends: `vue/vue3-recommended`, `@typescript-eslint/recommended`, `prettier`
- Parser: `vue-eslint-parser` with `@typescript-eslint/parser`
- Vue-specific rules: Single-word component names allowed for views

### Prettier

Configuration: `.prettierrc`

```json
{
  "semi": false,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5"
}
```

### TypeScript

Strict mode enabled with additional checks:

- `noUnusedLocals`
- `noUnusedParameters`
- `noFallthroughCasesInSwitch`
- `noImplicitReturns`

## API Integration

### REST API

The frontend uses Axios for REST API calls. The API client is configured in `src/services/api.ts`.

**Key Features**:

- Base URL from environment variables
- Request ID header for tracing (`X-Request-ID`)
- Automatic conversion of Decimal strings to Big.js objects
- Standardized error handling

### WebSocket

Real-time updates use native WebSocket API with reconnection logic.

**Key Features**:

- Exponential backoff reconnection (1s, 2s, 4s, 8s, max 30s)
- Sequence number tracking for missed messages
- Message buffering during reconnection
- Event-based subscription system

**Message Types**:

- `connected` - Connection established
- `pattern_detected` - New pattern detected
- `signal_generated` - New trade signal
- `batch_update` - Batch of updates

## Routes

- `/` - Dashboard (Live Signals)
- `/backtest` - Backtesting Interface (Epic 11)
- `/settings` - Application Settings (Epic 11)

## Financial Precision

⚠️ **CRITICAL**: Never use JavaScript `number` type for prices or percentages.

Always use `Big.js` for financial calculations:

```typescript
import Big from 'big.js'

// Correct
const price: Big = new Big('123.456789')

// Incorrect (precision loss)
const price: number = 123.456789
```

The API client automatically converts Decimal strings from the backend to Big.js objects.

## Development Notes

- Vite dev server proxies `/api` and `/ws` to backend (`http://localhost:8000`)
- Hot Module Replacement (HMR) is enabled for fast development
- Path alias `@` maps to `./src` for cleaner imports
- Use `<script setup lang="ts">` for Composition API components

## Deployment

Production build artifacts are in `dist/` after running `npm run build`.

Deploy `dist/` contents to static hosting (Netlify, Vercel, Cloudflare Pages, etc.).

## License

Proprietary - BMAD Wyckoff Trading Platform

## Support

For issues or questions, contact the development team.
