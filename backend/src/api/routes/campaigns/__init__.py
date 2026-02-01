"""
Campaign API routes.

This package organizes campaign-related endpoints into focused modules:

- risk.py: Risk tracking and allocation audit trail (Story 7.4, 9.2)
- positions.py: Position tracking and exit rule management (Story 9.4, 9.5)
- performance.py: Performance metrics and P&L curves (Story 9.6)
- lifecycle.py: Campaign listing and lifecycle operations (Story 11.4)

All routes are aggregated under the /api/v1/campaigns prefix.
"""

from fastapi import APIRouter

from .lifecycle import get_campaigns_list
from .performance import router as performance_router
from .positions import router as positions_router
from .risk import router as risk_router

# Main router that aggregates all sub-routers
router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])

# Add the list campaigns endpoint directly (empty path not allowed in sub-routers)
router.add_api_route(
    "",
    get_campaigns_list,
    methods=["GET"],
    response_model=dict,
    summary="List Campaigns",
    description="Get list of campaigns with optional filtering.",
)

# Include sub-routers
# Note: Order matters - specific routes like /performance must be included
# before dynamic routes like /{campaign_id}/performance
router.include_router(performance_router)  # Includes /performance (aggregated)
router.include_router(risk_router)  # Includes /{campaign_id}/risk, etc.
router.include_router(positions_router)  # Includes /{campaign_id}/positions, etc.

__all__ = ["router"]
