"""
Backtest API routes.

This package organizes backtest-related endpoints into focused modules:

- preview.py: Backtest preview endpoints (Story 11.2)
- full.py: Full backtest endpoints (Story 12.1)
- reports.py: Report export endpoints (Story 12.6B)
- walk_forward.py: Walk-forward testing endpoints (Story 12.4)
- regression.py: Regression testing endpoints (Story 12.7)
- baseline.py: Regression baseline endpoints (Story 12.7)
- utils.py: Shared utilities (in-memory tracking, data fetching)

All routes are aggregated under the /api/v1/backtest prefix.
"""

from fastapi import APIRouter

from .baseline import router as baseline_router
from .full import router as full_router
from .preview import router as preview_router
from .regression import router as regression_router
from .reports import router as reports_router
from .walk_forward import router as walk_forward_router

# Main router that aggregates all sub-routers
router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])

# Include all sub-routers
router.include_router(preview_router)
router.include_router(full_router)
router.include_router(reports_router)
router.include_router(walk_forward_router)
router.include_router(regression_router)
router.include_router(baseline_router)

# Export in-memory tracking dicts for backwards compatibility
from .utils import backtest_runs, regression_test_runs, walk_forward_runs

__all__ = ["router", "backtest_runs", "walk_forward_runs", "regression_test_runs"]
