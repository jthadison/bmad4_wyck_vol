# Smoke Tests

## Overview

Smoke tests validate critical deployment paths to ensure the application is functional after deployment.

## Test Coverage

1. **Homepage loads successfully** - Validates 200 status, page title, and app container
2. **API health endpoint responds** - Tests backend connectivity
3. **WebSocket connection establishes** - Validates real-time communication
4. **Signal dashboard renders** - Checks UI components load
5. **Chart component loads** - Validates Lightweight Charts initialization

## Running Tests

```bash
# Against local preview
npm run test:smoke

# Against deployed environment
DEPLOYMENT_URL=http://your-domain.com npm run test:smoke

# View test report
npm run test:smoke:report
```

## Requirements

- Playwright Test installed (`@playwright/test`)
- Deployment must be running
- Backend API must be healthy

## Test Configuration

See `playwright.config.ts` for configuration options.
