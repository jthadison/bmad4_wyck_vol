# Analytics Router - Registration Status

## Current Status: NOT REGISTERED

The analytics router (`analytics.py`) is **not registered in `main.py`** until
Story 11.9 is complete. This is intentional to prevent users from accessing
endpoints that return placeholder data.

## Why Not Registered?

- Database queries return empty/zero data (MVP placeholders)
- Redis is not yet configured in Docker Compose
- Would create false expectations for users

## When Will It Be Registered?

Story 11.9 (Pattern Performance - Production Implementation) will:
1. Implement real database queries (Task 1)
2. Set up Redis infrastructure (Task 4)
3. Add database indexes (Task 2)
4. Register router in main.py as final step

## How to Test Locally (Developers Only)

To test the API endpoints before production:

```python
# backend/src/api/main.py
from src.api.routes import analytics

# Add after other routers
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
```

Then run: `poetry run uvicorn src.api.main:app --reload`

**IMPORTANT:** Do not commit this change. Router will be registered in Story 11.9.
